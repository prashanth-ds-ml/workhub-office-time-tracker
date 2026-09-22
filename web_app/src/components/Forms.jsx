import React, { useState } from "react";

const DEFAULT_COMPANY_DOMAIN = "sims.healthcare";
const domainPattern = domain => `[^@\\s]+@${domain.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`;
const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

export default function Forms({ api, config, eventColors, normalizeIsoDate, onClose, onDone, policy, today, token, type }) {
  const [form, setForm] = useState(type === "event" ? { event_type: "WORKING_DAY", date: today(), title: "", description: "" } :
    type === "announcement" ? { title: "", content: "", effective_date: today() } :
    type === "employee" ? { username: "", email: "", password: "", role: "User", bootstrap_secret: "" } :
    { office_hours: policy?.office_hours || { start: "09:00", end: "18:00" }, rules: policy?.rules || { min_work_hours: 6, max_work_hours: 9, min_break_minutes: 20, max_break_minutes: 90 } });
  const [error, setError] = useState("");
  const companyDomain = config.company_email_domain || DEFAULT_COMPANY_DOMAIN;

  const submit = async e => {
    e.preventDefault();
    setError("");
    try {
      const routes = { event: "/calendar/events", announcement: "/announcements", employee: "/admin/users", policy: "/company/work-policy" };
      const body = { ...form };
      if (type === "event") body.date = normalizeIsoDate(body.date);
      if (type === "announcement" && body.effective_date) body.effective_date = normalizeIsoDate(body.effective_date);
      if (type === "event" && !isoDatePattern.test(body.date)) throw new Error("Please choose a valid event date.");
      if (type === "announcement" && body.effective_date && !isoDatePattern.test(body.effective_date)) throw new Error("Please choose a valid effective date.");
      await api(routes[type], { token, method: "POST", body });
      await onDone(type);
      onClose();
    } catch (err) {
      setError(err.message);
    }
  };

  return <form className="modal-form" onSubmit={submit}>
    {type === "event" && <><label>Event type<select value={form.event_type} onChange={e => setForm({ ...form, event_type: e.target.value })}>{Object.keys(eventColors).map(x => <option key={x}>{x}</option>)}</select></label><label>Date<input type="date" required value={form.date} onChange={e => setForm({ ...form, date: normalizeIsoDate(e.target.value) })} /></label><label>Title<input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></label><label>Description<textarea value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label></>}
    {type === "announcement" && <><label>Title<input required value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></label><label>Message<textarea required value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} /></label><label>Effective date<input type="date" value={form.effective_date} onChange={e => setForm({ ...form, effective_date: normalizeIsoDate(e.target.value) })} /></label></>}
    {type === "employee" && <><label>Full name<input required value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} /></label><label>Company email<input required type="email" pattern={domainPattern(companyDomain)} placeholder={`employee@${companyDomain}`} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></label><label>Temporary password<input required minLength="6" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} /></label><label>Role<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}><option>User</option><option>Manager</option><option>Boss</option></select></label>{(form.role === "Manager" || form.role === "Boss") && <label>{form.role} bootstrap key<input required value={form.bootstrap_secret} onChange={e => setForm({ ...form, bootstrap_secret: e.target.value })} /></label>}</>}
    {type === "policy" && <><div className="form-grid"><label>Office starts<input type="time" value={form.office_hours.start} onChange={e => setForm({ ...form, office_hours: { ...form.office_hours, start: e.target.value } })} /></label><label>Office ends<input type="time" value={form.office_hours.end} onChange={e => setForm({ ...form, office_hours: { ...form.office_hours, end: e.target.value } })} /></label></div><div className="form-grid">{Object.entries(form.rules).map(([key, val]) => <label key={key}>{key.replaceAll("_", " ")}<input type="number" step="0.5" value={val} onChange={e => setForm({ ...form, rules: { ...form.rules, [key]: Number(e.target.value) } })} /></label>)}</div></>}
    {error && <div className="error">{error}</div>}<div className="modal-actions"><button type="button" className="ghost" onClick={onClose}>Cancel</button><button className="primary">Save changes</button></div>
  </form>;
}
