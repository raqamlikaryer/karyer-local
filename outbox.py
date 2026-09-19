#!/usr/bin/env python3
"""
Outbox — serverga ishonchli yuborish (TZ 4).

Fon oqimi navbatdagi (pending) yozuvlarni oladi va serverga yuboradi.
Muvaffaqiyat -> 'sent'. Xato -> eksponensial backoff bilan qayta rejalashtiriladi
(ma'lumot yo'qolmaydi). Internet/server tiklanganda o'zi yuboradi.
"""

import time
import json
import threading

import db
from api_client import AUTH_ERR


# backoff: urinish -> kutish (soniya), maksimumi 5 daqiqa
def _backoff(attempts):
    return min(300, 5 * (2 ** min(attempts, 6)))   # 5,10,20,40,80,160,300...


# Kalit xatosida qayta urinish oralig'i. Tarmoq xatosidan farqli — bu o'zi
# tuzalmaydi, shuning uchun tez-tez urinishning ma'nosi yo'q; kalit
# yangilangach shu oraliqda o'zi qayta ulanadi.
AUTH_RETRY_S = 300


class OutboxSender:
    def __init__(self, api_client, poll_interval=2.0):
        self.api = api_client
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None
        # Oxirgi kalit xatosi matni (yo'q bo'lsa None). Tray shu orqali
        # "kalit yaroqsiz" deb ogohlantiradi — aks holda xato faqat logda
        # qolib, navbat jimgina o'sib boraverardi.
        self.auth_error = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, name="outbox", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        print("[outbox] Yuborish xizmati ishga tushdi")
        warned = False
        while self._running:
            # server sozlanmagan/o'chirilgan — urinmaymiz, navbat kutib turadi
            if not self.api.enabled or not self.api.url:
                if not warned:
                    print("[outbox] Server sozlanmagan — hodisalar navbatda to'planadi")
                    warned = True
                time.sleep(10)
                continue
            warned = False

            rows = []
            try:
                rows = db.fetch_pending(limit=20)
            except Exception as e:
                print(f"[outbox] baza xatosi: {e}")

            if not rows:
                time.sleep(self.poll_interval)
                continue

            for outbox_id, event_id, payload_str, attempts in rows:
                if not self._running:
                    break
                try:
                    payload = json.loads(payload_str)
                except Exception:
                    payload = {"raw": payload_str}

                ok, info = self.api.send(payload)
                if ok:
                    if self.auth_error:
                        print("[outbox] 🔑 API kalit qayta ishladi — navbat yuborilmoqda")
                        self.auth_error = None
                    db.mark_sent(outbox_id)
                    print(f"[outbox] ✅ yuborildi (id={outbox_id}) {info}")
                elif info.startswith(AUTH_ERR):
                    # Kalit almashtirilgan yoki bekor qilingan. Hodisalar joyida
                    # qoladi — kalit tuzatilgach hammasi ketadi. Ogohlantirish
                    # bir marta chiqadi: har 5 daqiqada logni to'ldirmasin.
                    if self.auth_error != info:
                        self.auth_error = info
                        print(f"[outbox] ⛔ API KALIT YAROQSIZ: {info}\n"
                              f"          Navbat ({db.pending_count()} hodisa) SAQLANMOQDA — "
                              f"hech nima yo'qolmaydi.\n"
                              f"          Sozlash oynasi -> \"Serverdan olish\" bilan yangi "
                              f"token kiriting.")
                    db.mark_retry(outbox_id, attempts, info, AUTH_RETRY_S)
                elif "tayyor emas" in info:
                    # video hali yozilyapti — bu xato emas, urinish hisoblanmaydi
                    db.mark_retry(outbox_id, attempts, info, 5)
                else:
                    attempts += 1
                    delay = _backoff(attempts)
                    db.mark_retry(outbox_id, attempts, info, delay)
                    print(f"[outbox] ⏳ xato (id={outbox_id}, urinish={attempts}): "
                          f"{info} — {delay:.0f}s dan keyin qayta")
            time.sleep(self.poll_interval)
