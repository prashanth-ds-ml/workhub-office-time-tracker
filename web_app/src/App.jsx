import { useCallback, useEffect, useState } from "react";
import {
  Activity, BarChart3, Bell, BriefcaseBusiness, CalendarDays, ChevronLeft,
  ChevronRight, ChevronsLeft, ChevronsRight, CircleStop, Clock3, Coffee,
  Download, Eye, EyeOff, Gauge, LogOut, Menu, Megaphone, Play, Plus,
  RefreshCw, Settings2, ShieldCheck, Users, X
} from "lucide-react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const INDIA_TIME_ZONE = "Asia/Kolkata";
const eventColors = {
  WORKING_DAY: "blue", HALF_DAY: "amber", FULL_DAY_SATURDAY: "teal",
  HOLIDAY: "purple", COMP_OFF: "pink", LONG_WEEKEND: "red", COMPANY_EVENT: "cyan"
};
const nav = [
  ["dashboard", "Overview", Gauge], ["calendar", "Calendar", CalendarDays],
  ["attendance", "Attendance", Clock3], ["announcements", "Announcements", Bell],
  ["employees", "Employees", Users, true], ["policies", "Policies", Settings2, true],
  ["reports", "Reports", BarChart3, true]
];
const dateFormatter = (options = {}) => new Intl.DateTimeFormat("en-IN", { timeZone: INDIA_TIME_ZONE, ...options });
const indiaParts = (value = new Date()) => {
  const parts = dateFormatter({
    year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(new Date(value));
  return Object.fromEntries(parts.filter(part => part.type !== "literal").map(part => [part.type, part.value]));
};
const today = () => {
  const { year, month, day } = indiaParts();
  return `${year}-${month}-${day}`;
};
const currentMonth = () => today().slice(0, 7);
const monthTitle = key => dateFormatter({ month: "long", year: "numeric" }).format(new Date(`${key}-01T12:00:00Z`));
const indiaDateLabel = value => dateFormatter({ weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
const indiaTimeLabel = value => dateFormatter({ hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).format(new Date(value));
const formatDuration = ms => {
  const total = Math.max(0, Math.floor(ms / 1000));
  const hours = String(Math.floor(total / 3600)).padStart(2, "0");
  const minutes = String(Math.floor(total % 3600 / 60)).padStart(2, "0");
  const seconds = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${seconds}`;
};
const parseDate = value => new Date(value);
const elapsedMs = (start, end) => Math.max(0, parseDate(end).getTime() - parseDate(start).getTime());
const shiftMonth = (month, delta) => {
  const [year, monthIndex] = month.split("-").map(Number);
  return new Date(Date.UTC(year, monthIndex - 1 + delta, 1)).toISOString().slice(0, 7);
};
const shiftYear = (month, delta) => {
  const [year, monthIndex] = month.split("-").map(Number);
  return new Date(Date.UTC(year + delta, monthIndex - 1, 1)).toISOString().slice(0, 7);
};
const mins = value => {
  const n = Math.max(0, Number(value || 0));
  return `${Math.floor(n / 60)}h ${Math.round(n % 60)}m`;
};
const COMPANY_DOMAIN = "sims.healthcare";
const companyEmail = value => value.trim().toLowerCase().endsWith(`@${COMPANY_DOMAIN}`);
const readStoredJson = (storage, key) => {
  try { return JSON.parse(storage.getItem(key) || "null"); }
  catch { storage.removeItem(key); return null; }
};
const emptyWorkspace = { overview:null, employees:[], analytics:null, policy:null, sessions:[], announcements:[] };

async function api(path, { token, method = "GET", body } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(`${API_URL}${path}`, {
      method, signal: controller.signal,
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.detail || data.message || `Request failed (${response.status})`);
      error.status = response.status;
      throw error;
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The server is taking too long to respond. Please retry.");
    throw error;
  } finally { clearTimeout(timer); }
}

function Auth({ onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "User", bootstrap_secret: "", reset_token: "", new_password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const submit = async e => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      if (!companyEmail(form.email)) throw new Error(`Use your @${COMPANY_DOMAIN} company email address.`);
      if (mode === "forgot") {
        const result = await api("/auth/forgot-password", { method: "POST", body: { email: form.email } });
        setNotice(result.reset_token ? `${result.message} Code: ${result.reset_token}` : "If an active account exists, a reset code has been sent. The code expires in 30 minutes.");
        setForm({ ...form, reset_token: result.reset_token || "" });
        setMode("reset");
        return;
      }
      if (mode === "reset") {
        const result = await api("/auth/reset-password", {
          method: "POST",
          body: { email: form.email, token: form.reset_token, new_password: form.new_password }
        });
        setNotice(result.message);
        setForm({ ...form, password: "", reset_token: "", new_password: "" });
        setMode("login");
        return;
      }
      const body = mode === "login"
        ? { email: form.email, password: form.password }
        : { username: form.username, email: form.email, password: form.password, role: form.role, bootstrap_secret: form.bootstrap_secret };
      onAuth(await api(mode === "login" ? "/login" : "/register", { method: "POST", body }));
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const title = mode === "login" ? "Sign in to your workspace" : mode === "register" ? "Join your company workspace" : mode === "forgot" ? "Reset your password" : "Create a new password";
  const eyebrow = mode === "login" ? "WELCOME BACK" : mode === "register" ? "CREATE ACCOUNT" : "ACCOUNT RECOVERY";
  return <div className="auth-shell">
    <section className="auth-brand">
      <div className="product-brand auth-product-brand"><img className="launcher-mark auth-launcher" src="/med360-launcher.svg" alt="Med 360+" /><div><strong>WorkHub</strong><span>by Med 360+ Smart Health</span></div></div>
      <div><span className="eyebrow">WORKHUB 1.1</span><h1>Time, attendance and your company calendar—finally in one place.</h1>
      <p>A focused employee workspace for the Med 360+ team.</p></div>
      <div className="auth-points"><span><ShieldCheck /> Secure company access</span><span><Activity /> Live attendance tracking</span></div>
    </section>
    <section className="auth-card">
      <div className="mobile-logo"><img className="launcher-mark mobile-launcher" src="/med360-launcher.svg" alt="Med 360+" /><span>WorkHub</span></div>
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p className="muted">{mode === "login" ? "Enter your credentials to continue." : mode === "register" ? "Your account connects to the shared company calendar." : mode === "forgot" ? "Use your company email to receive a reset code." : "Enter the reset code from your email. Codes expire in 30 minutes."}</p>
      <form onSubmit={submit}>
        {mode === "register" && <label>Full name<input required value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="Jane Smith" /></label>}
        <label>Company email<input required type="email" pattern={`[^@\\s]+@${COMPANY_DOMAIN.replace(".", "\\.")}`} title={`Use your @${COMPANY_DOMAIN} email`} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder={`you@${COMPANY_DOMAIN}`} /></label>
        {mode === "reset" && <label>Reset code<input required inputMode="numeric" value={form.reset_token} onChange={e => setForm({ ...form, reset_token: e.target.value })} placeholder="6-digit code" /></label>}
        {mode === "reset" && <label>New password<span className="password-field"><input required type={showNewPassword ? "text" : "password"} minLength="6" value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} placeholder="••••••••" /><button type="button" className="password-toggle" onClick={() => setShowNewPassword(!showNewPassword)} title={showNewPassword ? "Hide password" : "Show password"}>{showNewPassword ? <EyeOff /> : <Eye />}</button></span></label>}
        {(mode === "login" || mode === "register") && <label>Password<span className="password-field"><input required type={showPassword ? "text" : "password"} minLength="6" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="••••••••" /><button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} title={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff /> : <Eye />}</button></span></label>}
        {mode === "register" && <><label>Account type<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}><option value="User">Employee</option><option value="Admin">Administrator</option></select></label>
        {form.role === "Admin" && <label>Admin bootstrap key<input required value={form.bootstrap_secret} onChange={e => setForm({ ...form, bootstrap_secret: e.target.value })} /></label>}</>}
        {error && <div className="error">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        <button className="primary wide" disabled={busy}>{busy ? "Connecting…" : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset code" : "Update password"}</button>
      </form>
      <div className="auth-links">
        {mode === "login" && <button className="text-button" onClick={() => { setMode("forgot"); setError(""); setNotice(""); }}>Forgot password?</button>}
        <button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setNotice(""); }}>
          {mode === "login" ? "New to WorkHub? Create an account" : "Already have an account? Sign in"}
        </button>
      </div>
    </section>
  </div>;
}

function Modal({ title, children, onClose }) {
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="modal" onMouseDown={e => e.stopPropagation()}>
    <header><h3>{title}</h3><button className="icon-button" onClick={onClose}><X /></button></header>{children}
  </div></div>;
}

function Stat({ label, value, hint, tone = "blue", icon: Icon = Activity }) {
  return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon /></div><div><span>{label}</span><strong>{value}</strong><small>{hint}</small></div></article>;
}

function InlineEmpty({ title, detail }) {
  return <div className="inline-empty"><strong>{title}</strong><span>{detail}</span></div>;
}

function ClockBadge({ serverOffsetMs = 0 }) {
  const [now, setNow] = useState(() => Date.now() + serverOffsetMs);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() + serverOffsetMs), 1000);
    return () => clearInterval(timer);
  }, [serverOffsetMs]);
  return <span className="connected"><i/> API connected · {indiaDateLabel(now)} · {indiaTimeLabel(now)} IST</span>;
}

function LiveTimer({ session, active, onBreak, serverOffsetMs = 0 }) {
  const [now, setNow] = useState(() => Date.now() + serverOffsetMs);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now() + serverOffsetMs), 1000);
    return () => clearInterval(timer);
  }, [serverOffsetMs]);
  const liveTimerMs = session
    ? elapsedMs(session.start, session.active_break?.start || now)
      - (session.breaks || []).reduce((sum, brk) => brk.end ? sum + elapsedMs(brk.start, brk.end) : sum, 0)
      - (session.active_break ? elapsedMs(session.active_break.start, now) : 0)
    : 0;
  return <div className="live-timer"><span>Live timer · Server IST</span><strong>{formatDuration(liveTimerMs)}</strong><small>{active ? (onBreak ? "Break paused from focus time" : "Counting active work time") : "Waiting to start"}</small></div>;
}

function Calendar({ events, month, setMonth, onAdd, admin }) {
  const [animKey, setAnimKey] = useState(0);
  useEffect(() => { setAnimKey(key => key + 1); }, [month]);
  const [year, monthIndex] = month.split("-").map(Number);
  const first = new Date(Date.UTC(year, monthIndex - 1, 1));
  const start = (first.getUTCDay() + 6) % 7;
  const count = new Date(Date.UTC(year, monthIndex, 0)).getUTCDate();
  const map = Object.fromEntries(events.map(e => [e.date, e]));
  return <section className="panel calendar-panel calendar-swap" key={animKey}>
    <div className="panel-head"><div><h3>{monthTitle(month)}</h3><p>Company schedule and attendance expectations</p></div>
      <div className="actions">
        <button className="icon-button" onClick={() => setMonth(shiftYear(month, -1))} title="Previous year"><ChevronsLeft /></button>
        <button className="icon-button" onClick={() => setMonth(shiftMonth(month, -1))} title="Previous month"><ChevronLeft /></button>
        <button className="ghost" onClick={() => setMonth(currentMonth())}>Today</button>
        <button className="icon-button" onClick={() => setMonth(shiftMonth(month, 1))} title="Next month"><ChevronRight /></button>
        <button className="icon-button" onClick={() => setMonth(shiftYear(month, 1))} title="Next year"><ChevronsRight /></button>
        {admin && <button className="primary" onClick={onAdd}><Plus /> Add event</button>}
      </div>
    </div>
    <div className="weekdays">{["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(x => <span key={x}>{x}</span>)}</div>
    <div className="calendar-grid">
      {Array.from({ length: start }).map((_, i) => <div className="day empty" key={`e${i}`} />)}
      {Array.from({ length: count }).map((_, i) => {
        const date = `${month}-${String(i + 1).padStart(2, "0")}`, event = map[date];
        return <div className={`day ${date === today() ? "current" : ""}`} key={date}><b>{i + 1}</b>
          {event && <span className={`event ${eventColors[event.event_type] || "blue"}`} title={event.description}>{event.title}</span>}
        </div>;
      })}
    </div>
  </section>;
}

function Dashboard({ overview, serverOffsetMs = 0 }) {
  const [clockTick, setClockTick] = useState(() => Date.now() + serverOffsetMs);
  useEffect(() => {
    const timer = setInterval(() => setClockTick(Date.now() + serverOffsetMs), 1000);
    return () => clearInterval(timer);
  }, [serverOffsetMs]);
  const t = overview.today || {}, summary = overview.month_summary || {}, policy = t.policy || {};
  const upcomingHolidays = overview.upcoming_holidays || [];
  const liveSession = t.session;
  const liveTimerMs = liveSession
    ? elapsedMs(liveSession.start, liveSession.active_break?.start || clockTick)
      - (liveSession.breaks || []).reduce((sum, brk) => brk.end ? sum + elapsedMs(brk.start, brk.end) : sum, 0)
      - (liveSession.active_break ? elapsedMs(liveSession.active_break.start, clockTick) : 0)
    : 0;
  const liveTimer = formatDuration(liveTimerMs);
  return <>
    <div className="hero-row">
      <div>
        <span className="eyebrow">{indiaDateLabel(clockTick).toUpperCase()}</span>
        <h2>{t.calendar_event?.title || "Your workday"}</h2>
        <p>{t.calendar_event?.description || "Stay focused and make today count."}</p>
      </div>
      <div className={`day-pill ${eventColors[t.calendar_event?.event_type] || "blue"}`}>{(t.calendar_event?.event_type || "WORKING DAY").replaceAll("_", " ")}</div>
    </div>
    <div className="stats">
      <Stat label="Work completed" value={mins(t.work_done_minutes)} hint={`${mins(t.remaining_minutes)} remaining`} icon={Clock3} />
      <Stat label="Break used" value={mins(t.breaks_used_minutes)} hint={`${mins(t.break_remaining_minutes)} available`} tone="amber" icon={Coffee} />
      <Stat label="Monthly progress" value={`${summary.completed || 0}/${summary.working_days || 0}`} hint="target days completed" tone="green" icon={CalendarDays} />
      <Stat label="Target today" value={`${policy.target_work_hours || 0}h`} hint={`${policy.max_break_minutes || 0}m break allowance`} tone="purple" icon={Gauge} />
    </div>
    <div className="two-col">
      <section className="panel">
        <div className="panel-head"><div><h3>Month at a glance</h3><p>{monthTitle(overview.month)}</p></div></div>
        <div className="summary-list">{[
          ["Working days", summary.working_days], ["Completed", summary.completed], ["Workdays left", summary.remaining_working_days],
          ["Days left in month", summary.days_left_in_month], ["Holidays", summary.holidays], ["Half days", summary.half_days], ["Long weekends", summary.long_weekends]
        ].map(([a,b]) => <div key={a}><span>{a}</span><strong>{b || 0}</strong></div>)}</div>
      </section>
      <section className="panel">
        <div className="panel-head"><div><h3>Latest announcements</h3><p>Updates from your company</p></div></div>
        <div className="feed">{overview.announcements?.slice(0,4).map(a => <article key={a.id}><div className="feed-icon"><Megaphone /></div><div><strong>{a.title}</strong><p>{a.content}</p><small>{a.effective_date}</small></div></article>)}{!overview.announcements?.length && <div className="empty-state">No announcements yet.</div>}</div>
      </section>
    </div>
    <section className="panel upcoming-panel">
      <div className="panel-head"><div><h3>Upcoming holidays</h3><p>Next off-days in Indian time</p></div></div>
      <div className="upcoming-grid">
        {upcomingHolidays.length ? upcomingHolidays.map(item => (
          <article key={`${item.date}-${item.title}`}>
            <div className={`feed-icon ${eventColors[item.event_type] || "purple"}`}><CalendarDays /></div>
            <div>
              <strong>{item.title}</strong>
              <p>{item.date}</p>
              <small>{item.days_until === 0 ? "Today" : `${item.days_until} day${item.days_until === 1 ? "" : "s"} away`}</small>
            </div>
          </article>
        )) : <div className="empty-state">No upcoming holidays found.</div>}
      </div>
    </section>
  </>;
}

function Forms({ type, token, users, policy, onDone, onClose }) {
  const [form, setForm] = useState(type === "event" ? { event_type:"WORKING_DAY", date:today(), title:"", description:"" } :
    type === "announcement" ? { title:"", content:"", effective_date:today() } :
    type === "employee" ? { username:"", email:"", password:"", role:"User" } :
    { office_hours: policy?.office_hours || { start:"09:00", end:"18:00" }, rules: policy?.rules || { min_work_hours:6, max_work_hours:9, min_break_minutes:20, max_break_minutes:90 } });
  const [error, setError] = useState("");
  const submit = async e => {
    e.preventDefault(); setError("");
    try {
      const routes = { event:"/calendar/events", announcement:"/announcements", employee:"/admin/users", policy:"/company/work-policy" };
      await api(routes[type], { token, method:"POST", body:form }); onDone(); onClose();
    } catch (err) { setError(err.message); }
  };
  return <form className="modal-form" onSubmit={submit}>
    {type === "event" && <><label>Event type<select value={form.event_type} onChange={e=>setForm({...form,event_type:e.target.value})}>{Object.keys(eventColors).map(x=><option key={x}>{x}</option>)}</select></label><label>Date<input type="date" required value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></label><label>Title<input required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Description<textarea value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/></label></>}
    {type === "announcement" && <><label>Title<input required value={form.title} onChange={e=>setForm({...form,title:e.target.value})}/></label><label>Message<textarea required value={form.content} onChange={e=>setForm({...form,content:e.target.value})}/></label><label>Effective date<input type="date" value={form.effective_date} onChange={e=>setForm({...form,effective_date:e.target.value})}/></label></>}
    {type === "employee" && <><label>Full name<input required value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></label><label>Company email<input required type="email" pattern={`[^@\\s]+@${COMPANY_DOMAIN.replace(".", "\\.")}`} placeholder={`employee@${COMPANY_DOMAIN}`} value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></label><label>Temporary password<input required minLength="6" type="password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/></label><label>Role<select value={form.role} onChange={e=>setForm({...form,role:e.target.value})}><option>User</option><option>Admin</option></select></label></>}
    {type === "policy" && <><div className="form-grid"><label>Office starts<input type="time" value={form.office_hours.start} onChange={e=>setForm({...form,office_hours:{...form.office_hours,start:e.target.value}})}/></label><label>Office ends<input type="time" value={form.office_hours.end} onChange={e=>setForm({...form,office_hours:{...form.office_hours,end:e.target.value}})}/></label></div><div className="form-grid">{Object.entries(form.rules).map(([key,val])=><label key={key}>{key.replaceAll("_"," ")}<input type="number" step="0.5" value={val} onChange={e=>setForm({...form,rules:{...form.rules,[key]:Number(e.target.value)}})}/></label>)}</div></>}
    {error && <div className="error">{error}</div>}<div className="modal-actions"><button type="button" className="ghost" onClick={onClose}>Cancel</button><button className="primary">Save changes</button></div>
  </form>;
}

export default function App() {
  const savedUser = readStoredJson(localStorage, "workhub_user");
  const saved = savedUser ? { user: savedUser, token: sessionStorage.getItem("workhub_token") || "" } : null;
  const [auth, setAuth] = useState(saved), [page, setPage] = useState("dashboard"), [month, setMonth] = useState(today().slice(0,7));
  const [data, setData] = useState(() => {
    if (!savedUser) return emptyWorkspace;
    return readStoredJson(sessionStorage, `workhub_data:${savedUser.id}:${today().slice(0,7)}`)
      || emptyWorkspace;
  });
  const [busy, setBusy] = useState(false), [sectionBusy, setSectionBusy] = useState(""), [error, setError] = useState(""), [modal, setModal] = useState(null), [mobile, setMobile] = useState(false);
  const [serverOffsetMs, setServerOffsetMs] = useState(() => Number(sessionStorage.getItem("workhub_server_offset_ms") || 0));
  const admin = auth?.user?.role === "Admin";
  const hasOverview = Boolean(data.overview);
  const acceptAuth = value => {
    localStorage.setItem("workhub_user", JSON.stringify(value.user));
    sessionStorage.setItem("workhub_token", value.access_token);
    localStorage.removeItem("workhub_auth");
    setAuth({ user: value.user, token: value.access_token });
  };
  const logout = useCallback(async () => {
    try { await api("/logout", { token: auth?.token, method: "POST" }); } catch { /* local sign-out still proceeds */ }
    localStorage.removeItem("workhub_user");
    localStorage.removeItem("workhub_auth");
    sessionStorage.removeItem("workhub_token");
    setAuth(null);
  }, [auth]);
  const load = useCallback(async () => {
    if (!auth) return; setBusy(true); setError("");
    try {
      const workspace = await api(`/web/bootstrap?month=${month}`, { token: auth.token });
      if (workspace.generated_at) {
        const offset = Date.parse(workspace.generated_at) - Date.now();
        if (Number.isFinite(offset)) {
          setServerOffsetMs(offset);
          sessionStorage.setItem("workhub_server_offset_ms", String(offset));
        }
      }
      setData(previous => {
        const next = { ...emptyWorkspace, ...previous, ...workspace };
        sessionStorage.setItem(`workhub_data:${auth.user.id}:${month}`, JSON.stringify(next));
        return next;
      });
      if (workspace.user) {
        localStorage.setItem("workhub_user", JSON.stringify(workspace.user));
      }
    } catch (err) { if (err.status === 401 || err.status === 403) logout(); else setError(err.message); } finally { setBusy(false); }
  }, [auth, month, logout]);
  const loadSection = useCallback(async section => {
    if (!auth || !hasOverview) return;
    if (section === "dashboard" || section === "calendar") return;
    setSectionBusy(section); setError("");
    try {
      if (section === "attendance") {
        const result = await api(`/web/attendance?month=${month}`, { token: auth.token });
        setData(previous => ({ ...previous, sessions: result.sessions || [] }));
      } else if (section === "announcements") {
        const result = await api("/web/announcements?limit=50", { token: auth.token });
        setData(previous => ({
          ...previous,
          announcements: result.announcements || [],
          overview: { ...previous.overview, unread_announcements: result.unread_announcements || 0 }
        }));
      } else if (section === "employees" && admin) {
        const employees = await api("/admin/users", { token: auth.token });
        setData(previous => ({ ...previous, employees }));
      } else if (section === "policies" && admin) {
        const policy = await api("/company/work-policy", { token: auth.token });
        setData(previous => ({ ...previous, policy }));
      } else if (section === "reports" && admin) {
        const analytics = await api(`/admin/analytics?month=${month}`, { token: auth.token });
        setData(previous => ({ ...previous, analytics }));
      }
    } catch (err) {
      if (err.status === 401 || err.status === 403) logout(); else setError(err.message);
    } finally { setSectionBusy(""); }
  }, [auth, hasOverview, month, admin, logout]);
  const updateToday = useCallback(todaySummary => {
    setData(previous => ({
      ...previous,
      overview: previous.overview ? {
        ...previous.overview,
        today: todaySummary,
        alerts: todaySummary.alerts || previous.overview.alerts || []
      } : previous.overview
    }));
  }, []);
  const refreshToday = useCallback(async () => {
    if (!auth) return;
    updateToday(await api("/attendance/today", { token: auth.token }));
  }, [auth, updateToday]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadSection(page); }, [page, loadSection]);
  useEffect(() => {
    const refreshVisibleWorkspace = () => { if (document.visibilityState === "visible") load(); };
    document.addEventListener("visibilitychange", refreshVisibleWorkspace);
    return () => document.removeEventListener("visibilitychange", refreshVisibleWorkspace);
  }, [load]);
  const action = async kind => {
    const session = data.overview?.today?.session, id = session?.id;
    if (kind !== "start" && !id) {
      setError("No active session is available for that action.");
      return;
    }
    const path = kind === "start" ? `/sessions/${auth.user.id}/start` : kind === "stop" ? `/sessions/${id}/stop` : kind === "break" ? `/sessions/${id}/break/start` : `/sessions/${id}/break/stop`;
    setBusy(true);
    try {
      const result = await api(path,{token:auth.token,method:"POST"});
      const currentToday = data.overview.today;
      if (kind === "start") {
        updateToday({ ...currentToday, session: { ...result, breaks: result.breaks || [], active_break: null, is_active: true } });
      } else if (kind === "break") {
        updateToday({ ...currentToday, session: { ...session, active_break: result, is_active: true } });
      } else if (kind === "resume") {
        const endedBreak = { ...(session.active_break || result), end: result.end };
        updateToday({ ...currentToday, session: { ...session, active_break: null, breaks: [...(session.breaks || []), endedBreak], is_active: true } });
      } else if (kind === "stop") {
        updateToday({ ...currentToday, session: { ...session, ...result, active_break: null, is_active: false } });
      }
      await refreshToday();
      if (page === "attendance") loadSection("attendance");
    } catch(err){ setError(err.message); } finally{setBusy(false);}
  };
  const markRead = async id => { await api(`/announcements/${id}/read`,{token:auth.token,method:"POST"}); loadSection("announcements"); };
  const toggleUser = async user => { await api(`/admin/users/${user.id}`,{token:auth.token,method:"PATCH",body:{is_active:!user.is_active}}); loadSection("employees"); };
  if (!auth) return <Auth onAuth={acceptAuth} />;
  if (!data.overview) return <div className="loading-screen"><RefreshCw className="spin"/><h2>Opening your workspace</h2><p>Preparing your dashboard and calendar.</p>{error&&<div className="error">{error}</div>}</div>;
  const session = data.overview.today?.session, active = session?.is_active, onBreak = session?.active_break;
  const title = nav.find(x=>x[0]===page)?.[1] || "WorkHub";
  return <div className="app-shell">
    <aside className={mobile ? "open" : ""}><div className="logo"><img className="launcher-mark sidebar-launcher" src="/med360-launcher.svg" alt="Med 360+" /><div><strong>WorkHub</strong><span>Med 360+ workspace</span></div><button className="icon-button close-nav" onClick={()=>setMobile(false)}><X/></button></div>
      <nav>{nav.filter(x=>!x[3]||admin).map(([key,label,Icon])=><button key={key} className={page===key?"active":""} onClick={()=>{setPage(key);setMobile(false)}}><Icon/>{label}{key==="announcements"&&data.overview.unread_announcements>0&&<i>{data.overview.unread_announcements}</i>}</button>)}</nav>
      <div className="sidebar-user"><div className="avatar">{auth.user.username.slice(0,2).toUpperCase()}</div><div><strong>{auth.user.username}</strong><span>{auth.user.role}</span></div><button className="icon-button" onClick={logout}><LogOut/></button></div>
    </aside>
    <main><header className="topbar"><button className="icon-button menu" onClick={()=>setMobile(true)}><Menu/></button><div><h1>{title}</h1><p>{admin ? "Admin console" : "Employee workspace"}</p></div>
      <div className="top-actions"><ClockBadge serverOffsetMs={serverOffsetMs} /><button className="icon-button" onClick={load}><RefreshCw className={busy?"spin":""}/></button></div></header>
      <div className="content">{error&&<div className="banner error">{error}<button onClick={()=>setError("")}><X/></button></div>}
        {sectionBusy===page&&<div className="section-loading"><RefreshCw className="spin"/> Loading {title.toLowerCase()}…</div>}
        {page==="dashboard"&&<Dashboard overview={data.overview} serverOffsetMs={serverOffsetMs}/>}
        {page==="calendar"&&<Calendar events={data.overview.calendar_month||[]} month={month} setMonth={setMonth} admin={admin} onAdd={()=>setModal("event")}/>}
        {page==="attendance"&&<section className="panel"><div className="panel-head"><div><h3>Attendance history</h3><p>Your recorded work sessions</p></div></div>{data.sessions.length?<div className="table-wrap"><table><thead><tr><th>Date</th><th>Started</th><th>Ended</th><th>Work</th><th>Break</th><th>Status</th></tr></thead><tbody>{data.sessions.map(s=><tr key={s.id}><td>{s.attendance_date || dateFormatter({ day:"2-digit", month:"short", year:"numeric" }).format(new Date(s.start))}</td><td>{s.start_time || dateFormatter({ hour:"2-digit", minute:"2-digit", hour12:true }).format(new Date(s.start))}</td><td>{s.end_time || (s.end?dateFormatter({ hour:"2-digit", minute:"2-digit", hour12:true }).format(new Date(s.end)):"—")}</td><td>{mins(s.work_minutes)}</td><td>{mins(s.break_minutes)}</td><td><span className={`status ${s.is_active?"green":"gray"}`}>{s.is_active?"Active":"Completed"}</span></td></tr>)}</tbody></table></div>:<InlineEmpty title="No attendance records for this month" detail="Start a work session and it will appear here."/>}</section>}
        {page==="announcements"&&<section className="panel"><div className="panel-head"><div><h3>Company announcements</h3><p>Important news and team updates</p></div>{admin&&<button className="primary" onClick={()=>setModal("announcement")}><Plus/> Post announcement</button>}</div>{data.announcements.length?<div className="announcement-grid">{data.announcements.map(a=><article className={a.is_read?"read":""} key={a.id}><div className="feed-icon"><Megaphone/></div><div><small>{a.effective_date}</small><h3>{a.title}</h3><p>{a.content}</p>{!a.is_read&&<button className="text-button" onClick={()=>markRead(a.id)}>Mark as read</button>}</div></article>)}</div>:<InlineEmpty title="No announcements yet" detail={admin ? "Post an announcement to notify the team." : "Team updates will appear here."}/>}</section>}
        {page==="employees"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Employees</h3><p>Manage access and review current status</p></div><button className="primary" onClick={()=>setModal("employee")}><Plus/> Add employee</button></div>{data.employees.length?<div className="table-wrap"><table><thead><tr><th>Employee</th><th>Role</th><th>Office hours</th><th>Status</th><th></th></tr></thead><tbody>{data.employees.map(u=><tr key={u.id}><td><strong>{u.username}</strong><small>{u.email}</small></td><td>{u.role}</td><td>{u.office_hours?`${u.office_hours.start} – ${u.office_hours.end}`:"Company default"}</td><td><span className={`status ${u.is_active?"green":"red"}`}>{u.is_active?"Active":"Disabled"}</span></td><td><button className="ghost" onClick={()=>toggleUser(u)}>{u.is_active?"Disable":"Enable"}</button></td></tr>)}</tbody></table></div>:<InlineEmpty title="No employees loaded" detail="Use Add employee to create the first account."/>}</section>}
        {page==="policies"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Company work policy</h3><p>Applied to every employee</p></div><button className="primary" onClick={()=>setModal("policy")}><Settings2/> Edit policy</button></div>{data.policy?<div className="policy-grid"><Stat label="Office hours" value={`${data.policy?.office_hours?.start||"—"} – ${data.policy?.office_hours?.end||"—"}`} hint="standard working window" icon={Clock3}/>{Object.entries(data.policy?.rules||{}).map(([k,v])=><Stat key={k} label={k.replaceAll("_"," ")} value={k.includes("hours")?`${v}h`:`${v}m`} hint="company-wide rule" tone="purple" icon={ShieldCheck}/>)}</div>:<InlineEmpty title="Policy is loading" detail="Company working hours and rules will appear here."/>}</section>}
        {page==="reports"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Employee analytics · {monthTitle(month)}</h3><p>Work and break totals for the selected month</p></div><button className="ghost" onClick={()=>window.print()}><Download/> Export / Print</button></div>{data.analytics?<><div className="stats compact"><Stat label="Active employees" value={data.analytics?.summary?.active_employees||0} icon={Users}/><Stat label="Average work/day" value={mins(data.analytics?.summary?.average_work_minutes)} tone="green" icon={Clock3}/><Stat label="Average break/day" value={mins(data.analytics?.summary?.average_break_minutes)} tone="amber" icon={Coffee}/></div><div className="table-wrap"><table><thead><tr><th>Employee</th><th>Days</th><th>Avg work</th><th>Avg break</th><th>Total work</th><th>Completion</th></tr></thead><tbody>{data.analytics?.employees?.map(e=><tr key={e.user_id}><td><strong>{e.username}</strong><small>{e.role}</small></td><td>{e.days_worked}</td><td>{mins(e.average_work_minutes)}</td><td>{mins(e.average_break_minutes)}</td><td>{mins(e.total_work_minutes)}</td><td>{e.completion_rate}%</td></tr>)}</tbody></table></div></>:<InlineEmpty title="Reports are loading" detail="Monthly analytics will appear after the report data loads."/>}</section>}
      </div>
      <div className="tracker-bar"><div><span className={`pulse ${active?"on":""}`}/><div><strong>{onBreak?"On break":active?"Work session active":"Ready to start"}</strong><small>{active?`${mins(data.overview.today.work_done_minutes)} focused today`:"Start when your workday begins"}</small></div><LiveTimer session={session} active={active} onBreak={onBreak} serverOffsetMs={serverOffsetMs}/></div><div className="actions">{!active?<button className="primary" onClick={()=>action("start")}><Play/> Start work</button>:onBreak?<><button className="primary" onClick={()=>action("resume")}><Play/> Resume work</button><button className="danger" onClick={()=>action("stop")}><CircleStop/> Stop work</button></>:<><button className="ghost" onClick={()=>action("break")}><Coffee/> Start break</button><button className="danger" onClick={()=>action("stop")}><CircleStop/> Stop work</button></>}</div></div>
    </main>
    {modal&&<Modal title={{event:"Add calendar event",announcement:"Post announcement",employee:"Add employee",policy:"Edit company policy"}[modal]} onClose={()=>setModal(null)}><Forms type={modal} token={auth.token} users={data.employees} policy={data.policy} onDone={load} onClose={()=>setModal(null)}/></Modal>}
  </div>;
}
