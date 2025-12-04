@echo off
echo Iniciando NYX - Mouse Virtual...
cd /d "%~dp0"
venv\Scripts\activate
python src/main.py
pause