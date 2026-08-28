# Exe qurish va yangi karyerga tarqatish

Bu qo'llanma **dasturchi uchun**: `Karyer.exe` tarqatmasini yig'ish va uni
Pythonsiz kompyuterlarga o'rnatish.

Nima uchun kerak: exe bilan har bir karyerga Python o'rnatish va ~2-3 GB
kutubxona yuklash shart emas — flashkadan bitta papka ko'chiriladi. Internet
sekin joylarda bu bir necha soatlik farq.

---

## 1. Qurish (bir marta, dasturchi kompyuterida)

Kerak: Python 3.13 va loyihaning barcha kutubxonalari o'rnatilgan bo'lsin
(`boshlash.py` bir marta ishga tushirilgan bo'lsa — yetadi).

```
pip install pyinstaller
python -m PyInstaller Karyer.spec --noconfirm
```

Natija: `dist/Karyer/` (~1 GB, `Karyer.exe` + `_internal/`). 8–15 daqiqa.

> **Diqqat:** build paytida hech bir konsol/Explorer oynasi `dist/Karyer`
> ichida turmasin — PyInstaller papkani o'chira olmay `WinError 32` beradi.

### Build'dan keyin yoniga ko'chiriladigan fayllar

`Karyer.spec` bularni **ataylab** ichiga olmaydi (hajmi katta va alohida
yangilanadi) — qo'lda ko'chiring:

| Nima | Qayerdan |
|---|---|
| `ffmpeg/` papkasi | loyiha ildizidan |
| `yolov8n.pt` | loyiha ildizidan |
| `Holat.bat`, `Holat.ps1` | loyiha ildizidan |
| `Sozlash.bat`, `Karyer Server.bat` | loyiha ildizidan |
| `install_autostart.bat`, `uninstall_autostart.bat` | loyiha ildizidan |
| `O'RNATISH.md` | loyiha ildizidan |

`.bat` va `.ps1` fayllar **ikkala rejimni ham biladi**: yonida `Karyer.exe`
bo'lsa uni chaqiradi, bo'lmasa Python manbadan ishlaydi. Alohida versiya
saqlash shart emas.

### Tarqatmada BO'LMASLIGI kerak

Yig'ishdan oldin tekshiring — bular **bitta karyerga xos** va ularni boshqa
karyerga ko'chirish xavfli (api_key va kamera parollari ichida):

```
config.json          karyer_server.db*        videos/
*.log                captures/                images/
```

Toza tarqatma ildizi shunday ko'rinadi:

```
Karyer/
  ├─ Karyer.exe
  ├─ _internal/            (PyInstaller)
  ├─ ffmpeg/ffmpeg.exe
  ├─ yolov8n.pt
  └─ *.bat, Holat.ps1, O'RNATISH.md
```

---

## 2. Yangi karyerga o'rnatish

Python o'rnatish **shart emas**. `Karyer/` papkasini flashkadan ko'chiring
(masalan `C:\Karyer\`) va:

**1)** Serverdan token oling (web-main → karyer sahifasi → kalit tugmasi), so'ng:

```
Karyer.exe --provision <TOKEN>
```

**2)** Zona va tarozini sozlang — `Sozlash.bat` (parol `!QAZ`)

**3)** Ishga tushiring — `Karyer Server.bat`
   (o'zi avtostartni ham yoqadi)

**4)** Avto-kirishni yoqing — `netplwiz`, parol maydonlarini bo'sh qoldiring
   (batafsil: `O'RNATISH.md` 8-qadam)

**5)** Tekshiring — `Holat.bat`, to'rttala qator ham `[  OK  ]` bo'lsin

Config, baza va videolar `Karyer.exe` yonida saqlanadi — papkani boshqa
kompyuterga ko'chirsangiz hammasi birga ketadi.

---

## 3. Kodni yangilaganda

Exe **avtomatik yangilanmaydi**. Kod o'zgarsa qaytadan qurish va yangi
`_internal/` bilan `Karyer.exe` ni ko'chirish kerak. Karyerdagi `config.json`,
baza va videolarga tegmang — ular joyida qoladi.

Kichik tuzatishlar uchun Python rejimi qulayroq (`git pull` yetadi), shuning
uchun bitta karyerni Python'da qoldirib sinash mantiqiy.

---

## 4. Muammolar

| Belgi | Sabab / davo |
|---|---|
| `WinError 32` build paytida | Biror oyna `dist/Karyer` ichida turibdi — chiqing |
| Exe ochilmayapti, xato ko'rinmayapti | `Karyer.spec` da `console=False` — vaqtincha `True` qilib qayta quring |
| Antivirus o'chirib yubordi | PyInstaller exe'lariga false-positive bo'ladi — istisno qo'shing |
| Video yozilmayapti | `ffmpeg/ffmpeg.exe` exe yonidami? |
| Yo'nalish har doim noma'lum | Zona chizilmagan (`Sozlash.bat`) yoki `yolov8n.pt` yo'q |
| `Holat.bat` "ishlamayapti" deydi | Dastur 47653-portni ushlaydi; ~1 daqiqa kutib qayta bosing |

Tashxis fayllari exe yonida hosil bo'ladi: `link_debug.log`, `det_debug.log`,
`anpr_debug.log`, `video_debug.log`, `img_debug.log`.
