# Building the PCIe TX EQ Simulator

This guide explains how to package the PCIe TX EQ Simulator into a standalone Windows executable.

## Why `--onedir` instead of `--onefile`?

This project is packaged using PyInstaller's `--onedir` mode (outputting a folder with the executable and its dependencies) rather than `--onefile` (a single compressed `.exe`). 

When a `--onefile` executable is run, it must silently extract its dependencies into a temporary directory before execution. Many antivirus solutions flag this behavior as suspicious and may falsely quarantine the program. By using `--onedir`, we avoid this issue and ensure the simulator launches quickly and reliably without triggering false positives.

## Prerequisites

1. **Python 3**: Make sure Python 3 is installed and added to your system `PATH`.
2. **Virtual Environment (Optional but Recommended)**:
   It's best practice to build the executable within a clean virtual environment to minimize the package size.
   ```cmd
   python -m venv venv
   call venv\Scripts\activate
   ```

## Development and Testing

If you just want to run the code normally:
1. Install the required libraries:
   ```cmd
   pip install -r requirements.txt
   ```
2. Run the application:
   ```cmd
   python main.py
   ```

## Packaging the Application

To build the executable:

1. Double-click the `build_exe.bat` file, or run it from the command line:
   ```cmd
   build_exe.bat
   ```
2. The script will automatically:
   - Install dependencies from `requirements.txt`
   - Install `pyinstaller`
   - Clean up any previous build artifacts
   - Build the application in `--onedir` mode

## Distributing the Application

Once the build is complete:
- Your executable will be located at: `dist\PCIe_TX_EQ_Simulator\PCIe_TX_EQ_Simulator.exe`
- **IMPORTANT**: When distributing the application to other users, you **MUST zip and share the entire `dist\PCIe_TX_EQ_Simulator` folder**. Do not just send the `.exe` file by itself, as it relies on the other files in the directory to run.
