@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo PCIe TX EQ Simulator Build
echo ========================================
echo.

if not exist "main.py" (
    echo ERROR: main.py not found.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    pause
    exit /b 1
)

if not exist "PCIe_TX_EQ_Simulator.spec" (
    echo ERROR: PCIe_TX_EQ_Simulator.spec not found.
    pause
    exit /b 1
)

if not exist ".venv-build\Scripts\python.exe" (
    echo Creating local build virtual environment: .venv-build
    py -3.11 -m venv .venv-build
    if errorlevel 1 (
        echo py -3.11 was not available. Trying: python -m venv .venv-build
        python -m venv .venv-build
        if errorlevel 1 (
            echo ERROR: Failed to create .venv-build. Install Python 3.11 or update PATH.
            pause
            exit /b 1
        )
    )
) else (
    echo Reusing local build virtual environment: .venv-build
)

call ".venv-build\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: Failed to activate .venv-build.
    pause
    exit /b 1
)

echo.
echo Upgrading build tools...
python -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip/setuptools/wheel.
    pause
    exit /b 1
)

echo.
echo Installing runtime dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements.txt dependencies.
    pause
    exit /b 1
)

echo.
echo Installing PyInstaller...
python -m pip install pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller.
    pause
    exit /b 1
)

echo.
echo Cleaning old build output...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo.
echo Building with PyInstaller spec...
pyinstaller --clean --noconfirm PCIe_TX_EQ_Simulator.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Build completed.
echo EXE location:
echo dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe
echo.
echo Distribute the whole folder:
echo dist\PCIe_TX_EQ_Simulator
echo Do not distribute only the .exe file.
pause
