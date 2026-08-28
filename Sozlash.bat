@echo off
chcp 65001 >nul
rem === Sozlamalar oynasini ochish (tahrirlash) ===
rem Tarqatma turi o'zi aniqlanadi: Karyer.exe bo'lsa u ishlatiladi,
rem bo'lmasa Python manbadan (ishlab chiqish rejimi).
cd /d "%~dp0"
if exist "Karyer.exe" (
    "Karyer.exe" --setup
) else (
    python main.py --setup
)
