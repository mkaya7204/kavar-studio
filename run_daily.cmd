@echo off
rem Task Scheduler entry point: run_daily.cmd produce | run_daily.cmd publish 1 ...
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PATH=C:\Users\mkaya\.local\bin;C:\ffmpeg\bin;%PATH%
if not exist output\logs mkdir output\logs
"C:\Python314\python.exe" daily.py %* >> output\logs\task.log 2>&1
