const params = new URLSearchParams(location.search);
document.getElementById("title").textContent = params.get("title") || "WorkHub Reminder";
document.getElementById("message").textContent = params.get("message") || "";

document.getElementById("dismiss").addEventListener("click", () => window.close());
document.getElementById("open-workhub").addEventListener("click", () => setTimeout(() => window.close(), 300));
