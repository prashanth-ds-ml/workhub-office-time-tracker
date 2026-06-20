@echo off

REM Create a Python 3.10.11 virtual environment
python -m venv .venv

REM Activate the venv and install requirements
call .venv\Scripts\activate.bat

pip install -r requirements.txt

echo Virtual environment ready.