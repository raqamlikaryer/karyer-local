@echo off
chcp 65001 >nul
rem === HAMMASINI avtomatik: o'rnatish + avtostart + fon rejimda ishga tushirish ===
rem Tarqatma turi o'zi aniqlanadi: Karyer.exe bo'lsa u ishlatiladi,
rem bo'lmasa Python manbadan (ishlab chiqish rejimi).
cd /d "%~dp0"
if exist "Karyer.exe" (
    start "" "Karyer.exe"
) else (
    python boshlash.py
)
