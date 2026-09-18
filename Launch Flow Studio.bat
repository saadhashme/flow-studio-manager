@echo off
title Launching Flow Studio Manager...
cd /d "%~dp0"
if exist "dist\win-unpacked\Flow Studio Manager.exe" (
    start "" "dist\win-unpacked\Flow Studio Manager.exe"
) else (
    npm start
)
exit
