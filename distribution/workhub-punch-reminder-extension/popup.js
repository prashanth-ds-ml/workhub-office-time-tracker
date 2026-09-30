async function render() {
  const { workhub_email: email } = await chrome.storage.local.get("workhub_email");
  const emailEl = document.getElementById("email");
  const noteEl = document.getElementById("note");
  if (email) {
    emailEl.textContent = email;
    emailEl.className = "status ok";
    noteEl.textContent = "You'll get a reminder between 10:45-11:00am if you haven't punched in, and between 5:30-6:00pm if you haven't punched out.";
  } else {
    emailEl.textContent = "not detected";
    emailEl.className = "status warn";
    noteEl.textContent = "Open workhub-office-time-tracker.vercel.app and log in, then reopen this popup.";
  }
}

document.getElementById("check-now").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "WORKHUB_MANUAL_CHECK" });
  window.close();
});

document.getElementById("preview").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "WORKHUB_PREVIEW_POPUP" });
  window.close();
});

render();
