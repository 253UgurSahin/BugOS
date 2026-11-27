@echo off
rem BugOS Switch starten. Dubbelklik op dit bestand.
rem Windows 11 opent dit in Terminal, en daar werkt -WindowStyle Hidden niet: dan bleef er een zwart venster open.
rem Daarom via conhost --headless (geen venster) en met start, zodat dit venster meteen weer dichtgaat.
if exist "%SystemRoot%\System32\conhost.exe" (
    start "" "%SystemRoot%\System32\conhost.exe" --headless powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0BugOS-Switch.ps1"
) else (
    start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0BugOS-Switch.ps1"
)
