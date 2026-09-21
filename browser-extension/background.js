const API_BASE = "https://workhub-office-time-tracker.vercel.app/api";
const ALARM_DAILY = "workhub-punch-check-daily";
const ALARM_FOLLOWUP = "workhub-punch-check-followup";
const REMINDER_HOUR = 11;
const REMINDER_MINUTE = 0;
const FOLLOWUP_DELAY_MS = 60 * 60 * 1000;

chrome.runtime.onInstalled.addListener(scheduleDailyAlarm);
chrome.runtime.onStartup.addListener(scheduleDailyAlarm);

function nextOccurrence(hour, minute) {
  const now = new Date();
  const target = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
  if (target.getTime() <= now.getTime()) target.setDate(target.getDate() + 1);
  return target.getTime();
}

function scheduleDailyAlarm() {
  chrome.alarms.create(ALARM_DAILY, { when: nextOccurrence(REMINDER_HOUR, REMINDER_MINUTE) });
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "WORKHUB_AUTH_SYNC") {
    chrome.storage.local.set({ workhub_token: message.token, workhub_email: message.email });
  } else if (message?.type === "WORKHUB_MANUAL_CHECK") {
    checkPunchInAndNotify(true, { forceNotifyIfPunched: true });
  }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === ALARM_DAILY) {
    await checkPunchInAndNotify(true);
    scheduleDailyAlarm();
  } else if (alarm.name === ALARM_FOLLOWUP) {
    await checkPunchInAndNotify(false);
  }
});

async function checkPunchInAndNotify(isFirstCheck, options = {}) {
  const { workhub_token: token } = await chrome.storage.local.get("workhub_token");
  if (!token) {
    if (options.forceNotifyIfPunched) {
      chrome.notifications.create(`workhub-check-${Date.now()}`, {
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "WorkHub Reminder",
        message: "No WorkHub session found. Log in on the WorkHub site first.",
        priority: 1,
      });
    }
    return;
  }

  let data;
  try {
    const response = await fetch(`${API_BASE}/attendance/today`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.status === 401 || response.status === 403) {
      await chrome.storage.local.remove(["workhub_token", "workhub_email"]);
      return;
    }
    if (!response.ok) return;
    data = await response.json();
  } catch (err) {
    return;
  }

  const needsPunchIn = (data.alerts || []).includes("No active session started for a working day.");
  if (!needsPunchIn) {
    if (options.forceNotifyIfPunched) {
      chrome.notifications.create(`workhub-check-${Date.now()}`, {
        type: "basic",
        iconUrl: "icons/icon128.png",
        title: "WorkHub Reminder",
        message: "You're already punched in (or today isn't a working day). No reminder needed.",
        priority: 1,
      });
    }
    return;
  }

  await showReminderPopup(
    "WorkHub: You haven't punched in",
    isFirstCheck
      ? "It's 11am and you haven't started your workday yet. Don't forget to punch in!"
      : "Still not punched in on WorkHub — punch in when you're ready."
  );

  if (isFirstCheck) {
    chrome.alarms.create(ALARM_FOLLOWUP, { when: Date.now() + FOLLOWUP_DELAY_MS });
  }
}

const POPUP_WIDTH = 320 + 52; // card width + horizontal padding
const POPUP_HEIGHT = 320;

async function showReminderPopup(title, message) {
  let left, top;
  try {
    const displays = await chrome.system.display.getInfo();
    const primary = displays.find((d) => d.isPrimary) || displays[0];
    const area = primary.workArea;
    left = Math.round(area.left + (area.width - POPUP_WIDTH) / 2);
    top = Math.round(area.top + (area.height - POPUP_HEIGHT) / 2);
  } catch (err) {
    left = undefined;
    top = undefined;
  }

  const url = `reminder.html?${new URLSearchParams({ title, message }).toString()}`;
  chrome.windows.create({
    url,
    type: "popup",
    width: POPUP_WIDTH,
    height: POPUP_HEIGHT,
    left,
    top,
    focused: true,
  });
}
