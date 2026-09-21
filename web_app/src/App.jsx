import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, BarChart3, Bell, BriefcaseBusiness, CalendarDays, ChevronLeft,
  ChevronRight, ChevronsLeft, ChevronsRight, CircleStop, Clock3, Coffee,
  Download, Eye, EyeOff, Gauge, History, LogOut, Menu, Megaphone, Play, Plus,
  RefreshCw, Settings2, ShieldCheck, Users, X
} from "lucide-react";
import AuthScreen from "./components/Auth";
import FormsDialog from "./components/Forms";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const INDIA_TIME_ZONE = "Asia/Kolkata";
const eventColors = {
  WORKING_DAY: "blue", HALF_DAY: "amber", FULL_DAY_SATURDAY: "teal",
  HOLIDAY: "purple", COMP_OFF: "pink", LONG_WEEKEND: "red", COMPANY_EVENT: "cyan"
};
const attendanceColors = { on_time: "day-attendance-green", late: "day-attendance-orange", absent: "day-attendance-red" };
const nav = [
  ["dashboard", "Overview", Gauge], ["calendar", "Calendar", CalendarDays],
  ["attendance", "Attendance", Clock3], ["announcements", "Announcements", Bell],
  ["employees", "Employees", Users, true], ["policies", "Policies", Settings2, true],
  ["reports", "Reports", BarChart3, true], ["audit", "Audit Log", History, true]
];
const dateFormatter = (options = {}) => new Intl.DateTimeFormat("en-IN", { timeZone: INDIA_TIME_ZONE, ...options });
const indiaParts = (value = new Date()) => {
  const parts = dateFormatter({
    year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(new Date(value));
  return Object.fromEntries(parts.filter(part => part.type !== "literal").map(part => [part.type, part.value]));
};
const isoDateFromParts = ({ year, month, day }) => `${year}-${month}-${day}`;
const today = () => {
  const { year, month, day } = indiaParts();
  return isoDateFromParts({ year, month, day });
};
const normalizeIsoDate = value => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const isoMatch = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  const { year, month, day } = indiaParts(parsed);
  return `${year}-${month}-${day}`;
};
const normalizeIsoMonth = value => {
  const raw = String(value || "").trim();
  const isoMatch = raw.match(/^(\d{4})-(\d{2})/);
  if (isoMatch) return `${isoMatch[1]}-${isoMatch[2]}`;
  const parsed = new Date(`${raw}-01T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return raw;
  return normalizeIsoDate(parsed).slice(0, 7);
};
const currentMonth = () => today().slice(0, 7);
const monthTitle = key => dateFormatter({ month: "long", year: "numeric" }).format(new Date(`${key}-01T12:00:00Z`));
const indiaDateLabel = value => dateFormatter({ weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(value));
const indiaTimeLabel = value => dateFormatter({ hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).format(new Date(value));
const parseDate = value => new Date(value);
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
const csvCell = value => `"${String(value ?? "").replaceAll("\"", "\"\"")}"`;
const downloadCsv = (filename, rows) => {
  const blob = new Blob([rows.map(row => row.map(csvCell).join(",")).join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};
const DEFAULT_COMPANY_DOMAIN = "sims.healthcare";
const companyEmail = (value, domain) => value.trim().toLowerCase().endsWith(`@${domain}`);
const readStoredJson = (storage, key) => {
  try { return JSON.parse(storage.getItem(key) || "null"); }
  catch { storage.removeItem(key); return null; }
};
const AUTH_STORAGE_KEY = "workhub_auth";
const TOKEN_STORAGE_KEY = "workhub_token";
const SERVER_OFFSET_STORAGE_KEY = "workhub_server_offset_ms";
const workspaceStorageKey = (userId, month) => `workhub_data:${userId}:${month}`;
const clearWorkhubSessionState = () => {
  const keys = [];
  for (let index = 0; index < sessionStorage.length; index += 1) {
    const key = sessionStorage.key(index);
    if (key && (key === AUTH_STORAGE_KEY || key === TOKEN_STORAGE_KEY || key === SERVER_OFFSET_STORAGE_KEY || key.startsWith("workhub_data:"))) {
      keys.push(key);
    }
  }
  keys.forEach(key => sessionStorage.removeItem(key));
};
const emptyWorkspace = { overview:null, employees:[], analytics:null, policy:null, sessions:[], announcements:[], auditLog:[] };
const mergeWorkspaceSnapshot = (previous, workspace) => ({
  ...emptyWorkspace,
  ...previous,
  ...workspace,
  sessions: Array.isArray(workspace.sessions) && workspace.sessions.length ? workspace.sessions : previous.sessions,
  announcements: Array.isArray(workspace.announcements) && workspace.announcements.length ? workspace.announcements : previous.announcements,
  employees: Array.isArray(workspace.employees) && workspace.employees.length ? workspace.employees : previous.employees,
  analytics: workspace.analytics ?? previous.analytics,
  policy: workspace.policy ?? previous.policy,
});

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
        const attendanceClass = attendanceColors[event?.attendance_status] || "";
        return <div className={`day ${date === today() ? "current" : ""} ${attendanceClass}`} key={date}><b>{i + 1}</b>
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
  const nextHoliday = upcomingHolidays[0];
  const holidaySummary = overview.holiday_summary || {};
  return <>
    <div className="hero-row">
      <div className="hero-copy">
        <span className="eyebrow">{indiaDateLabel(clockTick).toUpperCase()}</span>
        <h2>{t.calendar_event?.title || "Your workday"}</h2>
        <p>{t.calendar_event?.description || "Stay focused and make today count."}</p>
        <div className="hero-chips">
          <span>{todayStatusLabel(t)}</span>
          <span>{summary.completed || 0}/{summary.working_days || 0} completed</span>
          <span>{overview.unread_announcements || 0} unread announcements</span>
          <span>{nextHoliday ? `Next off: ${nextHoliday.title}` : "No upcoming holiday"}</span>
        </div>
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
        <div className="panel-head"><div><h3>Month at a glance</h3><p>{monthTitle(overview.month)}</p></div><span className="panel-badge">{summary.remaining_working_days || 0} workdays left</span></div>
        <div className="summary-list">{[
          ["Working days", summary.working_days], ["Completed", summary.completed], ["Workdays left", summary.remaining_working_days],
          ["Days left in month", summary.days_left_in_month], ["Holidays", summary.holidays], ["Half days", summary.half_days], ["Long weekends", summary.long_weekends],
          [`Holidays completed (${holidaySummary.year || ""})`, holidaySummary.completed], [`Holidays left (${holidaySummary.year || ""})`, holidaySummary.left]
        ].map(([a,b]) => <div key={a}><span>{a}</span><strong>{b || 0}</strong></div>)}</div>
      </section>
      <section className="panel">
        <div className="panel-head"><div><h3>Latest announcements</h3><p>Updates from your company</p></div><span className="panel-badge">{overview.unread_announcements || 0} unread</span></div>
        <div className="feed">{overview.announcements?.slice(0,4).map(a => <article key={a.id}><div className="feed-icon"><Megaphone /></div><div><strong>{a.title}</strong><p>{a.content}</p><small>{a.effective_date}</small></div></article>)}{!overview.announcements?.length && <div className="empty-state">No announcements yet.</div>}</div>
      </section>
    </div>
    <section className="panel upcoming-panel">
      <div className="panel-head"><div><h3>Upcoming holidays</h3><p>Next off-days in Indian time</p></div><span className="panel-badge">{upcomingHolidays.length} found</span></div>
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

function todayStatusLabel(todaySummary) {
  const session = todaySummary?.session;
  if (session?.active_break) return "On break";
  if (session?.is_active) return "Working now";
  return "Ready to start";
}

export default function App() {
  const saved = readStoredJson(sessionStorage, AUTH_STORAGE_KEY);
  const [auth, setAuth] = useState(saved), [page, setPage] = useState("dashboard"), [month, setMonth] = useState(currentMonth());
  const selectedMonth = normalizeIsoMonth(month);
  const [publicConfig, setPublicConfig] = useState({
    company_email_domain: DEFAULT_COMPANY_DOMAIN,
    password_reset_minutes: 30,
    password_reset_self_service: false,
    allow_self_registration: false,
  });
  const [publicConfigReady, setPublicConfigReady] = useState(false);
  const [data, setData] = useState(() => {
    if (!saved?.user?.id) return emptyWorkspace;
    return readStoredJson(sessionStorage, workspaceStorageKey(saved.user.id, selectedMonth))
      || emptyWorkspace;
  });
  const [busy, setBusy] = useState(false), [sectionBusy, setSectionBusy] = useState(""), [error, setError] = useState(""), [modal, setModal] = useState(null), [mobile, setMobile] = useState(false);
  const [reportRange, setReportRange] = useState({ from: "", to: "" });
  const [serverOffsetMs, setServerOffsetMs] = useState(() => Number(sessionStorage.getItem("workhub_server_offset_ms") || 0));
  const admin = auth?.user?.role === "Admin";
  const hasOverview = Boolean(data.overview);
  const latestMonthRef = useRef(selectedMonth);
  useEffect(() => {
    latestMonthRef.current = selectedMonth;
  }, [selectedMonth]);
  const persistWorkspace = useCallback((next, userId = auth?.user?.id, selectedMonth = month) => {
    if (!userId) return;
    sessionStorage.setItem(workspaceStorageKey(userId, normalizeIsoMonth(selectedMonth)), JSON.stringify(next));
  }, [auth, month]);
  useEffect(() => {
    if (!auth?.user?.id) {
      setData(emptyWorkspace);
      return;
    }
    setData(readStoredJson(sessionStorage, workspaceStorageKey(auth.user.id, selectedMonth)) || emptyWorkspace);
  }, [auth, selectedMonth]);
  useEffect(() => {
    if (!mobile) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobile]);
  useEffect(() => {
    let cancelled = false;
    api("/web/config").then(result => {
      if (cancelled) return;
      setPublicConfig({
        company_email_domain: result.company_email_domain || DEFAULT_COMPANY_DOMAIN,
        password_reset_minutes: Number(result.password_reset_minutes || 30),
        password_reset_self_service: result.password_reset_self_service !== false,
        allow_self_registration: result.allow_self_registration !== false,
      });
      setPublicConfigReady(true);
    }).catch(() => {
      if (!cancelled) setPublicConfigReady(true);
    });
    return () => { cancelled = true; };
  }, []);
  const acceptAuth = value => {
    clearWorkhubSessionState();
    const nextAuth = { user: value.user, token: value.access_token };
    sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextAuth));
    sessionStorage.setItem(TOKEN_STORAGE_KEY, value.access_token);
    setData(emptyWorkspace);
    setPage("dashboard");
    setMonth(currentMonth());
    setServerOffsetMs(0);
    setAuth(nextAuth);
  };
  const logout = useCallback(async () => {
    try { await api("/logout", { token: auth?.token, method: "POST" }); } catch { /* local sign-out still proceeds */ }
    clearWorkhubSessionState();
    setData(emptyWorkspace);
    setPage("dashboard");
    setMonth(currentMonth());
    setServerOffsetMs(0);
    setAuth(null);
  }, [auth]);
  const load = useCallback(async () => {
    if (!auth) return; setBusy(true); setError("");
    try {
      const requestedMonth = selectedMonth;
      const workspace = await api(`/web/bootstrap?month=${selectedMonth}`, { token: auth.token });
      if (latestMonthRef.current !== requestedMonth) return;
      if (workspace.generated_at) {
        const offset = Date.parse(workspace.generated_at) - Date.now();
        if (Number.isFinite(offset)) {
          setServerOffsetMs(offset);
          sessionStorage.setItem("workhub_server_offset_ms", String(offset));
        }
      }
      setData(previous => {
        const next = mergeWorkspaceSnapshot(previous, workspace);
        persistWorkspace(next, auth.user.id, selectedMonth);
        return next;
      });
      if (workspace.user) {
        const nextAuth = { user: workspace.user, token: auth.token };
        sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextAuth));
        if (JSON.stringify(auth.user) !== JSON.stringify(workspace.user)) setAuth(nextAuth);
      }
    } catch (err) { if (err.status === 401 || err.status === 403) logout(); else setError(err.message); } finally { setBusy(false); }
  }, [auth, selectedMonth, logout, persistWorkspace]);
  const loadSection = useCallback(async section => {
    if (!auth || !hasOverview) return;
    if (section === "dashboard" || section === "calendar") return;
    setSectionBusy(section); setError("");
    try {
      const requestedMonth = selectedMonth;
      if (section === "attendance") {
        const result = await api(`/web/attendance?month=${requestedMonth}`, { token: auth.token });
        if (latestMonthRef.current !== requestedMonth) return;
        setData(previous => {
          const next = { ...previous, sessions: result.sessions || [] };
          persistWorkspace(next);
          return next;
        });
      } else if (section === "announcements") {
        const result = await api("/web/announcements?limit=50", { token: auth.token });
        if (latestMonthRef.current !== requestedMonth) return;
        setData(previous => {
          const next = {
            ...previous,
            announcements: result.announcements || [],
            overview: { ...previous.overview, unread_announcements: result.unread_announcements || 0 }
          };
          persistWorkspace(next);
          return next;
        });
      } else if (section === "employees" && admin) {
        const employees = await api("/admin/users", { token: auth.token });
        if (latestMonthRef.current !== requestedMonth) return;
        setData(previous => {
          const next = { ...previous, employees };
          persistWorkspace(next);
          return next;
        });
      } else if (section === "policies" && admin) {
        const policy = await api("/company/work-policy", { token: auth.token });
        if (latestMonthRef.current !== requestedMonth) return;
        setData(previous => {
          const next = { ...previous, policy };
          persistWorkspace(next);
          return next;
        });
      } else if (section === "reports" && admin) {
        const query = reportRange.from && reportRange.to
          ? `from=${reportRange.from}&to=${reportRange.to}`
          : `month=${requestedMonth}`;
        const analytics = await api(`/admin/analytics?${query}`, { token: auth.token });
        setData(previous => {
          const next = { ...previous, analytics };
          persistWorkspace(next);
          return next;
        });
      } else if (section === "audit" && admin) {
        const auditLog = await api("/admin/audit-log?limit=100", { token: auth.token });
        setData(previous => {
          const next = { ...previous, auditLog };
          persistWorkspace(next);
          return next;
        });
      }
    } catch (err) {
      if (err.status === 401 || err.status === 403) logout(); else setError(err.message);
    } finally { setSectionBusy(""); }
  }, [auth, hasOverview, month, admin, logout, persistWorkspace, reportRange]);
  const updateToday = useCallback(todaySummary => {
    setData(previous => {
      const next = {
        ...previous,
        overview: previous.overview ? {
          ...previous.overview,
          today: todaySummary,
          alerts: todaySummary.alerts || previous.overview.alerts || []
        } : previous.overview
      };
      persistWorkspace(next);
      return next;
    });
  }, [persistWorkspace]);
  const refreshToday = useCallback(async () => {
    if (!auth) return;
    updateToday(await api("/attendance/today", { token: auth.token }));
  }, [auth, updateToday]);
  const handleModalDone = useCallback(async modalType => {
    await load();
    const sectionByModal = {
      announcement: "announcements",
      employee: "employees",
      policy: "policies",
    };
    const section = sectionByModal[modalType];
    if (section) await loadSection(section);
  }, [load, loadSection]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadSection(page); }, [page, loadSection]);
  useEffect(() => {
    if (page === "attendance" || page === "reports") {
      loadSection(page);
    }
  }, [month, page, loadSection]);
  useEffect(() => {
    const refreshVisibleWorkspace = () => {
      if (document.visibilityState !== "visible") return;
      load();
      loadSection(page);
    };
    document.addEventListener("visibilitychange", refreshVisibleWorkspace);
    return () => document.removeEventListener("visibilitychange", refreshVisibleWorkspace);
  }, [load, loadSection, page]);
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
  const exportAnalytics = () => {
    if (!data.analytics) return;
    const summary = data.analytics.summary || {};
    const rows = [
      ["Report", "Employee Analytics"],
      ["Period", data.analytics.label || month],
      ["Employees", summary.employees ?? 0],
      ["Active employees", summary.active_employees ?? 0],
      ["Average work minutes", summary.average_work_minutes ?? 0],
      ["Average break minutes", summary.average_break_minutes ?? 0],
      ["Total work minutes", summary.total_work_minutes ?? 0],
      [],
      ["Employee", "Role", "Days worked", "Completed days", "Completion rate", "Average work minutes", "Average break minutes", "Total work minutes", "Total break minutes"],
      ...(data.analytics.employees || []).map(employee => [
        employee.username,
        employee.role,
        employee.days_worked,
        employee.completed_days,
        employee.completion_rate,
        employee.average_work_minutes,
        employee.average_break_minutes,
        employee.total_work_minutes,
        employee.total_break_minutes,
      ]),
    ];
    downloadCsv(`workhub-analytics-${data.analytics.range?.start || month}_${data.analytics.range?.end || ""}.csv`, rows);
  };
  if (!auth && !publicConfigReady) return <div className="loading-screen"><RefreshCw className="spin"/><h2>Opening your workspace</h2><p>Loading company sign-in settings.</p></div>;
  if (!auth) return <AuthScreen api={api} companyEmail={companyEmail} config={publicConfig} onAuth={acceptAuth} />;
  if (!data.overview) return <div className="loading-screen"><RefreshCw className="spin"/><h2>Opening your workspace</h2><p>Preparing your dashboard and calendar.</p>{error&&<div className="error">{error}</div>}</div>;
  const session = data.overview.today?.session, active = session?.is_active, onBreak = session?.active_break;
  const todayStatus = onBreak ? "On break" : active ? "Working now" : "Ready to start";
  const todayDetail = active
    ? `${mins(data.overview.today.work_done_minutes)} completed today · ${mins(data.overview.today.remaining_minutes)} remaining`
    : `Target today: ${mins((data.overview.today?.policy?.target_work_hours || 0) * 60)}`;
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
        {page==="attendance"&&<section className="panel"><div className="panel-head"><div><h3>Attendance history</h3><p>Your recorded work sessions</p></div><span className="panel-badge">{data.sessions.length} records</span></div>{data.sessions.length?<div className="table-wrap"><table><thead><tr><th>Date</th><th>Started</th><th>Ended</th><th>Work</th><th>Break</th><th>Status</th></tr></thead><tbody>{data.sessions.map(s=><tr key={s.id}><td>{s.attendance_date || dateFormatter({ day:"2-digit", month:"short", year:"numeric" }).format(new Date(s.start))}</td><td>{s.start_time || dateFormatter({ hour:"2-digit", minute:"2-digit", hour12:true }).format(new Date(s.start))}</td><td>{s.end_time || (s.end?dateFormatter({ hour:"2-digit", minute:"2-digit", hour12:true }).format(new Date(s.end)):"—")}</td><td>{mins(s.work_minutes)}</td><td>{mins(s.break_minutes)}</td><td><span className={`status ${s.is_active?"green":"gray"}`}>{s.is_active?"Active":"Completed"}</span></td></tr>)}</tbody></table></div>:<InlineEmpty title="No attendance records for this month" detail="Start a work session and it will appear here."/>}</section>}
        {page==="announcements"&&<section className="panel"><div className="panel-head"><div><h3>Company announcements</h3><p>Important news and team updates</p></div>{admin&&<button className="primary" onClick={()=>setModal("announcement")}><Plus/> Post announcement</button>}</div>{data.announcements.length?<div className="announcement-grid">{data.announcements.map(a=><article className={a.is_read?"read":""} key={a.id}><div className="feed-icon"><Megaphone/></div><div><small>{a.effective_date}</small><h3>{a.title}</h3><p>{a.content}</p>{!a.is_read&&<button className="text-button" onClick={()=>markRead(a.id)}>Mark as read</button>}</div></article>)}</div>:<InlineEmpty title="No announcements yet" detail={admin ? "Post an announcement to notify the team." : "Team updates will appear here."}/>}</section>}
        {page==="employees"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Employees</h3><p>Manage access and review current status</p></div><button className="primary" onClick={()=>setModal("employee")}><Plus/> Add employee</button></div>{data.employees.length?<div className="table-wrap"><table><thead><tr><th>Employee</th><th>Role</th><th>Office hours</th><th>Status</th><th></th></tr></thead><tbody>{data.employees.map(u=><tr key={u.id}><td><strong>{u.username}</strong><small>{u.email}</small></td><td>{u.role}</td><td>{u.office_hours?`${u.office_hours.start} – ${u.office_hours.end}`:"Company default"}</td><td><span className={`status ${u.is_active?"green":"red"}`}>{u.is_active?"Active":"Disabled"}</span></td><td><button className="ghost" onClick={()=>toggleUser(u)}>{u.is_active?"Disable":"Enable"}</button></td></tr>)}</tbody></table></div>:<InlineEmpty title="No employees loaded" detail="Use Add employee to create the first account."/>}</section>}
        {page==="policies"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Company work policy</h3><p>Applied to every employee</p></div><button className="primary" onClick={()=>setModal("policy")}><Settings2/> Edit policy</button></div>{data.policy?<div className="policy-grid"><Stat label="Office hours" value={`${data.policy?.office_hours?.start||"—"} – ${data.policy?.office_hours?.end||"—"}`} hint="standard working window" icon={Clock3}/>{Object.entries(data.policy?.rules||{}).map(([k,v])=><Stat key={k} label={k.replaceAll("_"," ")} value={k.includes("hours")?`${v}h`:`${v}m`} hint="company-wide rule" tone="purple" icon={ShieldCheck}/>)}</div>:<InlineEmpty title="Policy is loading" detail="Company working hours and rules will appear here."/>}</section>}
        {page==="reports"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Employee analytics · {data.analytics?.label || monthTitle(month)}</h3><p>Work and break totals for the selected period</p></div><div className="actions"><span className="panel-badge">{data.analytics?.summary?.active_employees||0} active</span><button className="ghost" onClick={exportAnalytics} disabled={!data.analytics}><Download/> Export CSV</button></div></div>
          <div className="report-range">
            <label>From<input type="date" value={reportRange.from} onChange={e=>setReportRange(r=>({...r, from: e.target.value}))} /></label>
            <label>To<input type="date" value={reportRange.to} onChange={e=>setReportRange(r=>({...r, to: e.target.value}))} /></label>
            <button className="ghost" disabled={!reportRange.from || !reportRange.to} onClick={()=>loadSection("reports")}>Apply range</button>
            {(reportRange.from || reportRange.to) && <button className="text-button" onClick={()=>{ setReportRange({from:"",to:""}); loadSection("reports"); }}>Clear</button>}
          </div>
          {data.analytics?<><div className="stats compact"><Stat label="Active employees" value={data.analytics?.summary?.active_employees||0} icon={Users}/><Stat label="Average work/day" value={mins(data.analytics?.summary?.average_work_minutes)} tone="green" icon={Clock3}/><Stat label="Average break/day" value={mins(data.analytics?.summary?.average_break_minutes)} tone="amber" icon={Coffee}/></div><div className="table-wrap"><table><thead><tr><th>Employee</th><th>Days</th><th>Avg work</th><th>Avg break</th><th>Total work</th><th>Completion</th></tr></thead><tbody>{data.analytics?.employees?.map(e=><tr key={e.user_id}><td><strong>{e.username}</strong><small>{e.role}</small></td><td>{e.days_worked}</td><td>{mins(e.average_work_minutes)}</td><td>{mins(e.average_break_minutes)}</td><td>{mins(e.total_work_minutes)}</td><td>{e.completion_rate}%</td></tr>)}</tbody></table></div></>:<InlineEmpty title="Reports are loading" detail="Analytics will appear after the report data loads."/>}</section>}
        {page==="audit"&&admin&&<section className="panel"><div className="panel-head"><div><h3>Audit log</h3><p>Admin role changes, account status changes, and calendar edits</p></div><span className="panel-badge">{data.auditLog.length} recent</span></div>{data.auditLog.length?<div className="table-wrap"><table><thead><tr><th>When</th><th>Admin</th><th>Action</th><th>Target</th><th>Details</th></tr></thead><tbody>{data.auditLog.map(e=><tr key={e.id}><td>{dateFormatter({ day:"2-digit", month:"short", year:"numeric", hour:"2-digit", minute:"2-digit", hour12:true }).format(new Date(e.created_at))}</td><td>{e.actor_email}</td><td>{e.action.replaceAll("_"," ")}</td><td>{e.target}</td><td>{e.details || "—"}</td></tr>)}</tbody></table></div>:<InlineEmpty title="No audit entries yet" detail="Role changes, account status changes, and calendar edits will show up here."/>}</section>}
      </div>
      <div className="tracker-bar"><div><span className={`pulse ${active?"on":""}`}/><div><strong>{todayStatus}</strong><small>{todayDetail}</small></div></div><div className="actions">{!active?<button className="primary" onClick={()=>action("start")}><Play/> Punch in</button>:onBreak?<><button className="primary" onClick={()=>action("resume")}><Play/> Resume work</button><button className="danger" onClick={()=>action("stop")}><CircleStop/> Stop work</button></>:<><button className="ghost" onClick={()=>action("break")}><Coffee/> Start break</button><button className="danger" onClick={()=>action("stop")}><CircleStop/> Stop work</button></>}</div></div>
    </main>
    {modal&&<Modal title={{event:"Add calendar event",announcement:"Post announcement",employee:"Add employee",policy:"Edit company policy"}[modal]} onClose={()=>setModal(null)}><FormsDialog api={api} config={publicConfig} eventColors={eventColors} normalizeIsoDate={normalizeIsoDate} onClose={()=>setModal(null)} onDone={handleModalDone} policy={data.policy} today={today} token={auth.token} type={modal} /></Modal>}
  </div>;
}
