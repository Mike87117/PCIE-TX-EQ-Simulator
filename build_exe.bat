@echo off
setlocal

echo Building PCIe TX EQ Simulator Windows EXE
echo.
echo Recommended: run this inside a clean virtual environment to keep the package small.
echo Example:
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo.

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m pip install pyinstaller
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller PCIETXEQ5.spec
if errorlevel 1 exit /b 1

echo.
echo Build complete:
echo dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe

endlocal
