function syncAuthFromPage() {
  try {
    const raw = sessionStorage.getItem("workhub_auth");
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed?.token && parsed?.user?.email) {
      chrome.runtime.sendMessage({
        type: "WORKHUB_AUTH_SYNC",
        token: parsed.token,
        email: parsed.user.email,
      });
    }
  } catch (err) {
    // sessionStorage entry missing or malformed; nothing to sync
  }
}

syncAuthFromPage();
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") syncAuthFromPage();
});
window.addEventListener("focus", syncAuthFromPage);
setInterval(syncAuthFromPage, 5 * 60 * 1000);
