# Welcome to WorkHub

WorkHub is our team's attendance and time-tracking tool. This guide covers everything you need: creating your account, and installing the small Windows app that opens WorkHub for you and reminds you so you never forget to punch in or out.

Takes about 5 minutes total.

---

## Part 1: Create your account

1. Open **[workhub-office-time-tracker.vercel.app](https://workhub-office-time-tracker.vercel.app)** in your browser.
2. Click **"New to WorkHub? Create an account"**.
3. Fill in:
   - **Full name**
   - **Company email** (your `@sims.healthcare` address)
   - **Password** (at least 6 characters — pick your own, this is your private password)
   - **Account type**: choose **Employee**
   - **Security question** and **Security answer**: pick something only you'd know (e.g. "What street did you grow up on?"). **Remember this** — it's how you reset your password later if you forget it. There is no "email me a code" option, so if you forget both your password and your answer, you'll need to ask an admin to help.
4. Click **Create account**. You're in.

## Part 2: Using WorkHub day-to-day

- **Punch in** when you start work (Office or Home), **punch out** when you're done, for the day. Use the bar at the bottom of the screen.
- The **Calendar** tab shows your attendance history, color-coded: green = on time, orange = late, red = missed.
- **Attendance** tab shows your full session history for the month.
- **Announcements** tab has company updates.

If you ever forget your password: click **Forgot password?** on the login screen, enter your email, and answer your security question.

---

## Part 3: Install the WorkHub Reminder app (recommended)

This small Windows app does two things:

- **Opens WorkHub in your browser** every time you sign in to your laptop or wake it from sleep.
- **Reminds you to punch in and out**, on working days only (no reminders on holidays or Sundays). It follows the company calendar.

| Reminder | When (Indian Standard Time) |
|---|---|
| Punch in | 10:30 AM – 11:00 AM |
| Punch out | 5:30 PM – 6:00 PM |
| Punch out on a **half day** | 2:30 PM – 3:00 PM |

The popup appears once per window. It doesn't check whether you've already punched, so just dismiss it if you have. If your laptop isn't set to IST, the popup shows your local time in brackets too.

One-time setup, about 2 minutes. No admin rights or Python needed. Windows laptops only.

### Install

1. Download **`WorkHubReminder.zip`** from the link you were sent.
2. Right-click the zip and choose **Extract All**.
3. Open the extracted folder and double-click **`WorkHubReminder.exe`**.
4. **If Windows shows a blue "Windows protected your PC" screen:** click **More info**, then **Run anyway**. This is normal, because the app isn't code-signed.
5. You'll see a **"WorkHub Reminder installed"** popup and WorkHub will open in your browser. You're done.

The app copies itself to a permanent folder, so you can delete the downloaded zip and folder afterwards.

### Check that it works

- **Restart your laptop.** A few seconds after you sign in, WorkHub should open by itself.
- **Close the lid and open it again.** After about 15 seconds WorkHub should open again.
- **See a sample popup:** open PowerShell and run
  `& "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --preview`

### Troubleshooting

- **Windows or antivirus blocks or deletes the file:** ask IT to allow `%LOCALAPPDATA%\WorkHub\WorkHubReminder.exe`, then run it again.
- **WorkHub doesn't open after waking from sleep:** message your admin. It's a known Windows quirk that they can look into.
- **No popup at a reminder time:** the app has to be running when the window starts. If your laptop was off or asleep for the whole window, there's no popup for that window.

### Updating

If you're sent a new version, **uninstall the old one first** (steps below), then install the new one as in "Install" above. Running the new file without uninstalling will not update the installed copy.

### Uninstall

Open PowerShell and run these four lines (the first one stops the running app; it's fine if it says the process wasn't found):

```powershell
taskkill /f /im WorkHubReminder.exe
& "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-startup
& "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe" --uninstall-resume-trigger
del "$env:LOCALAPPDATA\WorkHub\WorkHubReminder.exe"
```

---

## Questions or issues?

Reach out to your admin/manager on WorkHub if anything doesn't work as expected.
