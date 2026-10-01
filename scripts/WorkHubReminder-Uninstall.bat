@echo off
rem Removes the WorkHub Reminder app: stops it, removes its startup entries, deletes it.
echo Removing WorkHub Reminder...
taskkill /f /im WorkHubReminder.exe >nul 2>&1
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WorkHub Reminder Daemon.vbs" >nul 2>&1
schtasks /delete /tn "WorkHub Open On Resume" /f >nul 2>&1
timeout /t 2 /nobreak >nul
del /q "%LOCALAPPDATA%\WorkHub\WorkHubReminder.exe" >nul 2>&1
del /q "%APPDATA%\WorkHub\reminder_state.json" >nul 2>&1
echo.
echo Done. WorkHub Reminder has been removed from this computer.
pause
