@echo off
setlocal
py -m PyInstaller --noconfirm --clean --onefile --windowed --name InvoicePrizeChecker --icon "assets\invoice_prize_icon.ico" --add-data "assets\invoice_prize_icon.ico;assets" app.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo Built: dist\InvoicePrizeChecker.exe
endlocal

