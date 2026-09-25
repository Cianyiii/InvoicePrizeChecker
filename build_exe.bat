@echo off
setlocal
py -m PyInstaller --noconfirm --clean --onefile --windowed --name InvoicePrizeChecker app.py
if errorlevel 1 exit /b %errorlevel%
echo.
echo Built: dist\InvoicePrizeChecker.exe
endlocal

