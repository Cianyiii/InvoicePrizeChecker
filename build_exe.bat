@echo off
setlocal
py -m PyInstaller --noconfirm --clean InvoicePrizeChecker.spec
if errorlevel 1 exit /b %errorlevel%
echo.
echo Built: dist\InvoicePrizeChecker_IconUpdated.exe
endlocal

