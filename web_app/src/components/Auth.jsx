import React, { useEffect, useState } from "react";
import { Activity, Eye, EyeOff, ShieldCheck } from "lucide-react";

const DEFAULT_COMPANY_DOMAIN = "sims.healthcare";
const domainPattern = domain => `[^@\\s]+@${domain.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`;

export default function Auth({ api, companyEmail, config, onAuth }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "User", bootstrap_secret: "", reset_token: "", new_password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const companyDomain = config.company_email_domain || DEFAULT_COMPANY_DOMAIN;
  const resetMinutes = config.password_reset_minutes || 30;
  const resetAvailable = config.password_reset_self_service !== false;
  const allowSelfRegistration = config.allow_self_registration !== false;

  useEffect(() => {
    if (!allowSelfRegistration && mode === "register" && form.role === "User") {
      setForm(current => ({ ...current, role: "Manager" }));
    }
  }, [allowSelfRegistration, form.role, mode]);

  const submit = async e => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (!companyEmail(form.email, companyDomain)) throw new Error(`Use your @${companyDomain} company email address.`);
      if (mode === "forgot") {
        const result = await api("/auth/forgot-password", { method: "POST", body: { email: form.email } });
        setNotice(result.reset_token ? `${result.message} Code: ${result.reset_token}` : `If an active account exists, a reset code has been sent. The code expires in ${resetMinutes} minutes.`);
        setForm({ ...form, reset_token: result.reset_token || "" });
        setMode("reset");
        return;
      }
      if (mode === "reset") {
        const result = await api("/auth/reset-password", {
          method: "POST",
          body: { email: form.email, token: form.reset_token, new_password: form.new_password },
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
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const title = mode === "login" ? "Sign in to your workspace" : mode === "register" ? "Join your company workspace" : mode === "forgot" ? "Reset your password" : "Create a new password";
  const eyebrow = mode === "login" ? "WELCOME BACK" : mode === "register" ? "CREATE ACCOUNT" : "ACCOUNT RECOVERY";

  return <div className="auth-shell">
    <section className="auth-brand">
      <div className="product-brand auth-product-brand"><img className="launcher-mark auth-launcher" src="/med360-launcher.svg" alt="Med 360+" /><div><strong>WorkHub</strong><span>by Med 360+ Smart Health</span></div></div>
      <div><span className="eyebrow">WORKHUB 1.1</span><h1>Time, attendance and your company calendar in one place.</h1>
      <p>A focused employee workspace for the Med 360+ team.</p></div>
      <div className="auth-points"><span><ShieldCheck /> Secure company access</span><span><Activity /> Live attendance tracking</span></div>
    </section>
    <section className="auth-card">
      <div className="mobile-logo"><img className="launcher-mark mobile-launcher" src="/med360-launcher.svg" alt="Med 360+" /><span>WorkHub</span></div>
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p className="muted">{mode === "login" ? "Enter your credentials to continue." : mode === "register" ? (allowSelfRegistration ? "Your account connects to the shared company calendar." : "Employee self-registration is disabled. Only administrators with the bootstrap key can create an account here.") : mode === "forgot" ? (resetAvailable ? "Use your company email to receive a reset code." : "Self-service password reset is not available right now. Contact an administrator to regain access.") : `Enter the reset code from your email. Codes expire in ${resetMinutes} minutes.`}</p>
      <form onSubmit={submit}>
        {mode === "register" && <label>Full name<input required value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} placeholder="Jane Smith" /></label>}
        <label>Company email<input required type="email" pattern={domainPattern(companyDomain)} title={`Use your @${companyDomain} email`} value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} placeholder={`you@${companyDomain}`} /></label>
        {mode === "reset" && <label>Reset code<input required inputMode="numeric" value={form.reset_token} onChange={e => setForm({ ...form, reset_token: e.target.value })} placeholder="6-digit code" /></label>}
        {mode === "reset" && <label>New password<span className="password-field"><input required type={showNewPassword ? "text" : "password"} minLength="6" value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} placeholder="........" /><button type="button" className="password-toggle" onClick={() => setShowNewPassword(!showNewPassword)} title={showNewPassword ? "Hide password" : "Show password"}>{showNewPassword ? <EyeOff /> : <Eye />}</button></span></label>}
        {(mode === "login" || mode === "register") && <label>Password<span className="password-field"><input required type={showPassword ? "text" : "password"} minLength="6" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} placeholder="........" /><button type="button" className="password-toggle" onClick={() => setShowPassword(!showPassword)} title={showPassword ? "Hide password" : "Show password"}>{showPassword ? <EyeOff /> : <Eye />}</button></span></label>}
        {mode === "register" && <><label>Account type<select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}><option value="Manager">Manager</option><option value="Boss">Boss</option>{allowSelfRegistration && <option value="User">Employee</option>}</select></label>
        {(form.role === "Manager" || form.role === "Boss") && <label>{form.role} bootstrap key<input required value={form.bootstrap_secret} onChange={e => setForm({ ...form, bootstrap_secret: e.target.value })} /></label>}</>}
        {error && <div className="error">{error}</div>}
        {notice && <div className="notice">{notice}</div>}
        <button className="primary wide" disabled={busy}>{busy ? "Connecting..." : mode === "login" ? "Sign in" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset code" : "Update password"}</button>
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
