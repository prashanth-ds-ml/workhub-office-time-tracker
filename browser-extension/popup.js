async function render() {
  const { workhub_email: email } = await chrome.storage.local.get("workhub_email");
  const emailEl = document.getElementById("email");
  const noteEl = document.getElementById("note");
  if (email) {
    emailEl.textContent = email;
    emailEl.className = "status ok";
    noteEl.textContent = "You'll get a reminder at 11am if you haven't punched in.";
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

render();
