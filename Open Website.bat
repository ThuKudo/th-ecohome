@echo off
start "" powershell -WindowStyle Hidden -Command "Set-Location '%~dp0'; ..\..\venv\Scripts\python.exe 'webapp.py'"
