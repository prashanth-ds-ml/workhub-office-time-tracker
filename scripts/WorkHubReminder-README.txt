WorkHub Punch-In/Out Reminder
=============================

What this does
--------------
- Opens WorkHub in your browser once whenever you log in, or when this
  laptop wakes up from sleep.
- Shows reminder popups on working days only (none on holidays or Sundays):
    Punch in   10:30 AM - 11:00 AM IST
    Punch out   5:30 PM -  6:00 PM IST
    Punch out   2:30 PM -  3:00 PM IST on half days (e.g. Saturday half days)
  Times are Indian Standard Time, whatever your laptop's timezone is. The
  popup shows the current time in IST (and your local time if it differs).
  The popup shows once per window. It does not check whether you already
  punched, so just dismiss it if you have.

Install (one time)
-------------------
1. Double-click WorkHubReminder.exe.
2. You'll see a one-time "WorkHub Reminder installed" popup and a WorkHub
   browser tab will open. That's it - nothing else to configure.
3. It copies itself to a permanent folder automatically, so you can leave
   the downloaded file wherever you like (Downloads, Desktop, etc.) - it
   doesn't need to stay there.

From now on, it runs quietly in the background every time you log in or
wake this laptop, with no icon or window - just the reminder popups when
you actually need them.

No installer, no admin rights, and no Python needed.

Updating to a new version
-------------------------
Uninstall the old one first (below), then run the new WorkHubReminder.exe.

Uninstall
---------
Open a terminal (PowerShell) and run:
  taskkill /f /im WorkHubReminder.exe
  & "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-startup
  & "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-resume-trigger
Then delete that same file:
  del "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe"
