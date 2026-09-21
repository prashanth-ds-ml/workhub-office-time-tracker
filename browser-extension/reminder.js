const params = new URLSearchParams(location.search);
document.getElementById("title").textContent = params.get("title") || "WorkHub Reminder";
document.getElementById("message").textContent = params.get("message") || "";

document.getElementById("dismiss").addEventListener("click", () => window.close());
document.getElementById("open-workhub").addEventListener("click", () => setTimeout(() => window.close(), 300));

function centerSelf() {
  const left = Math.max(0, Math.round((screen.availWidth - window.outerWidth) / 2) + (screen.availLeft || 0));
  const top = Math.max(0, Math.round((screen.availHeight - window.outerHeight) / 2) + (screen.availTop || 0));
  window.moveTo(left, top);
}

// outerWidth/outerHeight can be 0 for one frame right after a popup window
// opens, so retry on the next tick rather than centering against 0x0.
requestAnimationFrame(() => requestAnimationFrame(centerSelf));
