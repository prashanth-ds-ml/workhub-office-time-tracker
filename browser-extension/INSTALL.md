# Installing the WorkHub Punch-In Reminder (Microsoft Edge)

This is a one-time setup, about 2 minutes. You won't need to repeat this unless told there's an update.

1. Download and unzip **workhub-punch-reminder-extension.zip** somewhere you won't move it later (e.g. `Documents\WorkHub Extension`).
2. Open Edge and go to `edge://extensions`.
3. Turn on **Developer mode** (toggle in the bottom-left of the page).
4. Click **Load unpacked**.
5. Select the unzipped folder (the one containing `manifest.json`).
6. The WorkHub icon should now appear in your toolbar.
7. Open **workhub-office-time-tracker.vercel.app** in a tab and log in as usual. This lets the extension know who you are.

That's it. You'll now automatically get a popup reminder:
- Between **10:45–11:00 AM** if you haven't punched in yet.
- Between **5:30–6:00 PM** if you haven't punched out yet.

No reminder if you've already punched in/out, or if it isn't a working day.

**Troubleshooting:**
- If the extension icon shows "not detected" for your login, make sure a WorkHub tab is open and you're logged in, then click the extension icon again.
- You can test it anytime with the **"Preview reminder popup"** button in the extension icon's popup.
