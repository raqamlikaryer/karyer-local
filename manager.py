#!/usr/bin/env python3
"""
StationManager — barcha stansiyalar va outbox yuboruvchini boshqaradi.

start_all() / stop_all() / restart() — bloklaydigan sikldan xoli, shuning uchun
ham konsol (main.py), ham tray xizmati (tray.py) ishlatadi.
"""

import os
import json
import shutil
import time
import uuid
import threading

import db
import config as cfgmod
from api_client import ApiClient
from outbox import OutboxSender
from station import make_station

BASE_DIR = cfgmod.app_dir()


def _abs(path):
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def _recover_unsent(cfg):
    """Eski versiya restart paytida navbatga tushirmay qoldirgan hodisalarni
    (bazada bor, outbox'da yo'q) qayta navbatga qo'yadi. Payload weigh_events
    qatoridan tiklanadi; camera_name/is_main stansiya configidan olinadi."""
    st_map = {}
    for s in cfg.get("stations", []):
        st_map[s.get("name")] = (s.get("camera_name") or s.get("name"),
                                 bool(s.get("is_main")))
    try:
        rows = db.fetch_unqueued_events(days=3)
    except Exception as e:
        print(f"[recover] baza xatosi: {e}")
        return 0
    n = 0
    for (eid, quarry_id, station, plate, direction, weight,
         unit, event_time, video_path, image_paths) in rows:
        cam, is_main = st_map.get(station, (station, False))
        if video_path and not os.path.exists(video_path):
            video_path = None   # fayl yo'q — kutmaymiz
        try:
            imgs = json.loads(image_paths or "[]")
        except Exception:
            imgs = []
        payload = {
            "event_uid": str(uuid.uuid4()),
            "quarry_id": quarry_id,
            "camera_name": cam,
            "is_main": is_main,
            "plate": plate,
            "direction": direction,
            "weight": weight,
            "unit": unit or "kg",
            "event_time": event_time,
            "video_path": video_path,
            "image_paths": [p for p in imgs if os.path.exists(p)],
        }
        db.enqueue_outbox(eid, payload)
        n += 1
    if n:
        print(f"[recover] {n} ta yuborilmay qolgan hodisa navbatga qayta qo'yildi")
    return n


def _free_gb(path):
    try:
        return shutil.disk_usage(path).free / (1024 ** 3)
    except OSError:
        return float("inf")   # o'lchay olmadik — qorovulni ishga solmaymiz


def _media_files(dirs):
    """(mtime, path) juftliklari, ESKISIDAN boshlab saralangan."""
    out = []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            p = os.path.join(d, name)
            try:
                if os.path.isfile(p):
                    out.append((os.path.getmtime(p), p))
            except OSError:
                pass
    out.sort()
    return out


def cleanup_media_once(dirs, ret=None):
    """Eski media fayllarni o'chiradi. Ikki qoida bir vaqtda ishlaydi:

      1. muddat — `media_days` dan eski fayl ketadi;
      2. disk qorovuli — bo'sh joy `min_free_gb` dan kam qolsa, muddati
         kelmaganlari ham eskisidan boshlab ketadi (disk to'lsa dastur video
         yoza olmay qoladi — ya'ni to'lib qolish eski faylni saqlashdan qimmat).

    Ikkala qoida ham NAVBATDAGI hodisaning fayllariga tegmaydi va oxirgi
    soatda yozilganini chetlab o'tadi (klip hali yozilayotgan bo'lishi mumkin).
    """
    ret = ret or cfgmod.default_retention()
    keep_days = float(ret.get("media_days", 30))
    min_free = float(ret.get("min_free_gb", 5))

    try:
        protected = db.pending_media_paths()
    except Exception as e:
        # Navbatni o'qiy olmadik — hech narsa o'chirmaymiz. Ortiqcha fayl
        # saqlash, yuborilmagan hodisani hujjatsiz qoldirishdan arzon.
        print(f"[media] navbatni o'qib bo'lmadi, tozalash o'tkazib yuborildi: {e}")
        return 0

    now = time.time()
    cutoff = now - keep_days * 86400
    fresh = now - 3600          # oxirgi soat — tegmaymiz

    def _drop(path):
        try:
            os.remove(path)
            return True
        except OSError:
            return False        # Windows'da ffmpeg ushlab turgan bo'lishi mumkin

    removed, kept, young = 0, 0, []
    for mtime, p in _media_files(dirs):
        if os.path.normcase(os.path.abspath(p)) in protected or mtime > fresh:
            kept += 1
            continue
        if mtime < cutoff:
            if _drop(p):
                removed += 1
        else:
            young.append(p)

    freed = 0
    if min_free > 0 and dirs:
        for p in young:         # eskisidan boshlab: _media_files saralab bergan
            if _free_gb(dirs[0]) >= min_free:
                break
            if _drop(p):
                freed += 1

    if removed or freed:
        msg = f"[media] {removed} ta eski fayl tozalandi (> {keep_days:.0f} kun)"
        if freed:
            msg += f" + {freed} ta disk joyi uchun (< {min_free:.0f} GB qolgandi)"
        if kept:
            msg += f"; {kept} ta saqlab qolindi (navbatda yoki yangi)"
        print(msg)
    return removed + freed


def _cleanup_media_loop(dirs, ret=None):
    """Tozalashni fon oqimida davriy ishga tushiradi (dastur bilan yashaydi)."""
    ret = ret or cfgmod.default_retention()
    interval_h = float(ret.get("interval_hours", 12))

    def _run():
        while True:
            try:
                cleanup_media_once(dirs, ret)
                db.prune_sent(days=int(ret.get("sent_rows_days", 30)))
            except Exception as e:
                print(f"[media] tozalash xatosi: {e}")
            time.sleep(max(600.0, interval_h * 3600))

    t = threading.Thread(target=_run, name="media-cleanup", daemon=True)
    t.start()
    return t


class StationManager:
    def __init__(self, sim=False):
        self.sim = sim
        self.stations = []
        self.sender = None
        self.running = False
        self.quarry_id = ""
        self.live = None        # LiveManager (live.enabled=true bo'lsagina)
        self.heartbeat = None   # HeartbeatSender

    def start_all(self, cfg=None):
        """config bo'yicha stansiyalar + outboxni ishga tushiradi."""
        if self.running:
            return
        cfg = cfg or cfgmod.load_config() or cfgmod.default_config()

        db.init_db()
        _recover_unsent(cfg)   # restartda yo'qolgan hodisalarni qayta navbatga
        # Restart ko'pincha "sozlamani tuzatdim" degani — navbat kutib turmasin.
        woken = db.reset_retry_schedule()
        if woken:
            print(f"[outbox] {woken} ta navbatdagi hodisa darhol urinishga qo'yildi")

        save_dir = _abs(cfg.get("save_dir", "captures"))
        video_dir = _abs(cfg.get("video_dir", "videos"))
        # media retention — birinchi start'da bir marta boshlaymiz (restartda emas)
        if not getattr(StationManager, "_cleanup_started", False):
            StationManager._cleanup_started = True
            _cleanup_media_loop([save_dir, video_dir],
                                cfg.get("retention") or cfgmod.default_retention())
        self.quarry_id = cfg.get("quarry_id", "")
        media_cfg = cfg.get("media", cfgmod.default_media())

        self.sender = OutboxSender(ApiClient(cfg.get("server", {})))
        self.sender.start()

        self.stations = []
        for st_cfg in cfg.get("stations", []):
            st = make_station(st_cfg, self.quarry_id, save_dir, video_dir,
                              sim=self.sim, media_cfg=media_cfg)
            st.start()
            self.stations.append(st)

        self.running = True

        # --- LIVE (ixtiyoriy, default O'CHIQ) -------------------------------
        # live.enabled=false bo'lsa hech narsa ishga tushmaydi; har qanday
        # xato asosiy oqimni (stansiyalar/outbox) buza olmasligi uchun try ichida.
        try:
            if (cfg.get("live") or {}).get("enabled"):
                from live_manager import LiveManager
                from heartbeat import HeartbeatSender
                self.live = LiveManager(cfg, self.stations)
                self.heartbeat = HeartbeatSender(cfg, self, self.live)
                self.heartbeat.start()
        except Exception as e:
            print(f"[live] modul ishga tushmadi (asosiy ishga ta'sir yo'q): {e}")
            self.live = None
            self.heartbeat = None

        print(f"✅ {len(self.stations)} ta stansiya ishlayapti | "
              f"karyer={self.quarry_id} | {'SIM' if self.sim else 'REAL'} rejim")
        return len(self.stations)

    def stop_all(self):
        """Barcha stansiyalar va outboxni to'xtatadi."""
        if not self.running:
            return
        if self.heartbeat:
            try:
                self.heartbeat.stop()
            except Exception:
                pass
            self.heartbeat = None
        if self.live:
            try:
                self.live.stop_all()
            except Exception:
                pass
            self.live = None
        for st in self.stations:
            try:
                st.stop()
            except Exception as e:
                print(f"stansiya to'xtatishda xato: {e}")
        if self.sender:
            self.sender.stop()
        self.stations = []
        self.sender = None
        self.running = False
        print("⏸ To'xtatildi")

    def restart(self, cfg=None):
        """Sozlamalar o'zgargach yangi config bilan qayta ishga tushiradi."""
        self.stop_all()
        return self.start_all(cfg)

    def status(self):
        return {
            "running": self.running,
            "stations": len(self.stations),
            "quarry_id": self.quarry_id,
            "pending": db.pending_count() if self.running else 0,
            # None bo'lmasa — API kalit yaroqsiz, odam aralashuvi kerak.
            "auth_error": getattr(self.sender, "auth_error", None) if self.sender else None,
        }
