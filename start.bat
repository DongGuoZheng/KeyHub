@echo off
set "VENV_DIR=.venv"

if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo Installing requirements...
pip install -r requirements.txt

echo Starting KeyHub...
start http://localhost:5000
python app.py

pause
