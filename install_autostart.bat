@echo off
chcp 65001 >nul
setlocal
rem === Karyer Local Server - Windows avtomatik ishga tushirishni YOQISH ===
rem DIQQAT: bu faylda ASCII bo'lmagan belgi (masalan uzun tire) BO'LMASIN.
rem chcp 65001 dan keyin cmd.exe fayl bo'ylab bayt-offsetdan adashadi va
rem keyingi satrlarni kesib o'qiydi ("'cp' is not recognized" kabi xatolar).
rem Kompyuter yoqilganda dastur fonda (tray) avtomatik ishlaydi.
rem Tarqatma turi o'zi aniqlanadi: Karyer.exe bo'lsa u, bo'lmasa pythonw.

set "PROJ=%~dp0"
set "PROJ=%PROJ:~0,-1%"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "OUT=%STARTUP%\KaryerServer.vbs"

> "%OUT%" echo Set sh = CreateObject("WScript.Shell")
>> "%OUT%" echo sh.CurrentDirectory = "%PROJ%"
if exist "%PROJ%\Karyer.exe" (
    >> "%OUT%" echo sh.Run """%PROJ%\Karyer.exe""", 0, False
    set "REJIM=exe"
) else (
    >> "%OUT%" echo sh.Run "pythonw.exe boshlash.py", 0, False
    set "REJIM=Python"
)

echo.
echo   [OK] Avtomatik ishga tushirish YOQILDI (%REJIM% rejimi).
echo   Endi kompyuter yoqilganda dastur o'zi fonda ishlaydi.
echo   (Soat yonidagi ikonkadan boshqarasiz.)
echo.
echo   Hoziroq ishga tushirish uchun "Karyer Server.bat" ni ikki marta bosing.
echo.
pause
