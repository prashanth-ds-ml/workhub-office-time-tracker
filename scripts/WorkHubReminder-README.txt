WorkHub Punch-In/Out Reminder
=============================

What this does
--------------
- Opens WorkHub in your browser once whenever you log in, or when this
  laptop wakes up from sleep.
- Shows a reminder popup if you haven't punched in by ~11am, or haven't
  punched out by ~6pm.

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

Uninstall
---------
Open a terminal (PowerShell) and run:
  & "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-startup
  & "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-resume-trigger
Then delete that same file:
  del "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe"
