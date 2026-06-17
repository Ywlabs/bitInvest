@echo off
setlocal EnableExtensions
wscript.exe //B "%~dp0launch_worker.vbs" trading
exit /b %ERRORLEVEL%
