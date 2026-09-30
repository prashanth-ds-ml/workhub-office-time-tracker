const API_BASE = "https://workhub-office-time-tracker.vercel.app/api";
const APP_URL = "https://workhub-office-time-tracker.vercel.app";
const APP_URL_PATTERN = "https://workhub-office-time-tracker.vercel.app/*";

const CHECK_ALARM = "workhub-window-check";
const CHECK_INTERVAL_MINUTES = 5;

// Only fire within these windows: 10:45-11:00 for punch-in, 17:30-18:00 for punch-out.
const MORNING_WINDOW = { startH: 10, startM: 45, endH: 11, endM: 0 };
const EVENING_WINDOW = { startH: 17, startM: 30, endH: 18, endM: 0 };

chrome.runtime.onInstalled.addListener(() => {
  scheduleWindowCheck();
  injectIntoOpenTabs();
});
chrome.runtime.onStartup.addListener(scheduleWindowCheck);

function scheduleWindowCheck() {
  chrome.alarms.create(CHECK_ALARM, { periodInMinutes: CHECK_INTERVAL_MINUTES, when: Date.now() + 1000 });
}

// Content scripts only auto-inject into pages loaded *after* install/update,
// so a WorkHub tab that was already open never syncs its auth token until
// the user manually reloads it. Inject into any already-open tabs so the
// extension works right away without that manual step.
async function injectIntoOpenTabs() {
  try {
    const tabs = await chrome.tabs.query({ url: APP_URL_PATTERN });
    for (const tab of tabs) {
      if (tab.id == null) continue;
      chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] }).catch(() => {});
    }
  } catch (err) {
    // ignore - falls back to the normal content-script injection on next load
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "WORKHUB_AUTH_SYNC") {
    chrome.storage.local.set({ workhub_token: message.token, workhub_email: message.email });
  } else if (message?.type === "WORKHUB_MANUAL_CHECK") {
    checkPunchInAndNotify({ forceNotifyIfPunched: true });
  } else if (message?.type === "WORKHUB_PREVIEW_POPUP") {
    showReminderPopup(
      "WorkHub: You haven't punched in",
      "This is a preview — it's 11am and you haven't started your workday yet. Don't forget to punch in!"
    );
  } else if (message?.type === "WORKHUB_OPEN_APP") {
    focusOrOpenWorkhubTab();
  }
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === CHECK_ALARM) checkTimeWindows();
});

function isWithinWindow(now, win) {
  const minutes = now.getHours() * 60 + now.getMinutes();
  const start = win.startH * 60 + win.startM;
  const end = win.endH * 60 + win.endM;
  return minutes >= start && minutes < end;
}

async function checkTimeWindows() {
  const now = new Date();
  const todayKey = now.toDateString();

  if (isWithinWindow(now, MORNING_WINDOW)) {
    const { workhub_morning_notified: notifiedDate } = await chrome.storage.local.get("workhub_morning_notified");
    if (notifiedDate !== todayKey) {
      const notified = await checkPunchInAndNotify();
      if (notified) await chrome.storage.local.set({ workhub_morning_notified: todayKey });
    }
  }

  if (isWithinWindow(now, EVENING_WINDOW)) {
    const { workhub_evening_notified: notifiedDate } = await chrome.storage.local.get("workhub_evening_notified");
    if (notifiedDate !== todayKey) {
      const notified = await checkPunchOutAndNotify();
      if (notified) await chrome.storage.local.set({ workhub_evening_notified: todayKey });
    }
  }
}

async function fetchTodayAttendance() {
  const { workhub_token: token } = await chrome.storage.local.get("workhub_token");
  if (!token) return { error: "no-token" };

  try {
    const response = await fetch(`${API_BASE}/attendance/today`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.status === 401 || response.status === 403) {
      await chrome.storage.local.remove(["workhub_token", "workhub_email"]);
      return { error: "unauthorized" };
    }
    if (!response.ok) return { error: "request-failed" };
    return { data: await response.json() };
  } catch (err) {
    return { error: "network" };
  }
}

function notify(message) {
  chrome.notifications.create(`workhub-check-${Date.now()}`, {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: "WorkHub Reminder",
    message,
    priority: 1,
  });
}

async function checkPunchInAndNotify(options = {}) {
  const { data, error } = await fetchTodayAttendance();
  if (error) {
    if (options.forceNotifyIfPunched) notify("No WorkHub session found. Log in on the WorkHub site first.");
    return false;
  }

  const needsPunchIn = (data.alerts || []).includes("No active session started for a working day.");
  if (!needsPunchIn) {
    if (options.forceNotifyIfPunched) {
      if (data.session?.is_active) {
        notify("You're already punched in. No reminder needed.");
      } else if (data.session) {
        notify("You've already completed a session today. No reminder needed.");
      } else {
        notify("Today isn't a working day. No reminder needed.");
      }
    }
    return false;
  }

  await showReminderPopup(
    "WorkHub: You haven't punched in",
    "It's almost 11am and you haven't started your workday yet. Don't forget to punch in!"
  );
  return true;
}

async function checkPunchOutAndNotify(options = {}) {
  const { data, error } = await fetchTodayAttendance();
  if (error) {
    if (options.forceNotifyIfPunched) notify("No WorkHub session found. Log in on the WorkHub site first.");
    return false;
  }

  const stillActive = Boolean(data.session?.is_active);
  if (!stillActive) {
    if (options.forceNotifyIfPunched) {
      if (data.session) {
        notify("You've already punched out. No reminder needed.");
      } else {
        notify("You haven't punched in yet today. No reminder needed.");
      }
    }
    return false;
  }

  await showReminderPopup(
    "WorkHub: You haven't punched out",
    "It's almost 6pm and your session is still active. Don't forget to punch out!"
  );
  return true;
}

// Reuses an already-open, already-authenticated WorkHub tab instead of opening
// a fresh one - a new tab has no session (WorkHub keeps auth in sessionStorage,
// which is per-tab) and would just bounce straight to the login page.
async function focusOrOpenWorkhubTab() {
  try {
    const tabs = await chrome.tabs.query({ url: APP_URL_PATTERN });
    if (tabs.length) {
      const tab = tabs[0];
      await chrome.tabs.update(tab.id, { active: true });
      if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true });
      return;
    }
  } catch (err) {
    // fall through to opening a new tab
  }
  chrome.tabs.create({ url: APP_URL });
}

const POPUP_WIDTH = 320 + 52; // card width + horizontal padding
const POPUP_HEIGHT = 320;
const popupWindowByNotification = new Map();

async function showReminderPopup(title, message) {
  // Center against the browser window the user is actually looking at,
  // not the primary display — on multi-monitor setups those can differ,
  // which is what pushed the popup to one side instead of true center.
  let left, top;
  try {
    const win = await chrome.windows.getLastFocused({ windowTypes: ["normal"] });
    const winLeft = win.left ?? 0;
    const winTop = win.top ?? 0;
    const winWidth = win.width ?? POPUP_WIDTH;
    const winHeight = win.height ?? POPUP_HEIGHT;
    left = Math.round(winLeft + (winWidth - POPUP_WIDTH) / 2);
    top = Math.round(winTop + (winHeight - POPUP_HEIGHT) / 2);
  } catch (err) {
    left = undefined;
    top = undefined;
  }

  const url = `reminder.html?${new URLSearchParams({ title, message }).toString()}`;
  const popupWindow = await chrome.windows.create({
    url,
    type: "popup",
    width: POPUP_WIDTH,
    height: POPUP_HEIGHT,
    left,
    top,
    focused: true,
  });

  // Windows (and some Linux/macOS window managers) block background apps from
  // stealing focus, so the popup window above can open without ever coming to
  // the front - it just flashes in the taskbar. A system notification bypasses
  // that restriction and always surfaces, so pair the popup with one.
  const notificationId = `workhub-popup-${Date.now()}`;
  popupWindowByNotification.set(notificationId, popupWindow.id);
  chrome.notifications.create(notificationId, {
    type: "basic",
    iconUrl: "icons/icon128.png",
    title,
    message,
    priority: 2,
    requireInteraction: true,
  });
}

chrome.notifications.onClicked.addListener(notificationId => {
  const windowId = popupWindowByNotification.get(notificationId);
  if (windowId != null) chrome.windows.update(windowId, { focused: true }).catch(() => {});
  chrome.notifications.clear(notificationId);
});
