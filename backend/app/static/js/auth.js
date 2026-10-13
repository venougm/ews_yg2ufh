/* ============================================================
   EWS YG2UFH auth — real login overlay + /api/me gating (KEBUTUHAN B).

   Contract (FEAT-001):
     GET  /api/me     -> 200 {authenticated:false} | {authenticated:true, username, role}
     POST /api/login  body {username,password} -> 200 {username,role} | 401
     POST /api/logout -> 200 {ok:true}

   All fetches are same-origin so the 'ews_session' cookie is sent automatically.
   This script loads BEFORE dashboard.js and only calls window.initDashboard()
   after a confirmed login.
   ============================================================ */

const ROLE_LABEL = { monitor: "monitor", operator: "operator", admin: "admin" };

/* GET /api/me -> parsed object (always 200). */
async function getMe() {
  const r = await fetch("/api/me");
  if (!r.ok) throw new Error("GET /api/me -> " + r.status);
  return r.json();
}

/* POST /api/login. On 401 throw a friendly message; other errors bubble up. */
async function doLogin(username, password) {
  const r = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (r.status === 401) throw new Error("username atau password salah");
  if (!r.ok) throw new Error("gagal masuk (" + r.status + ")");
  return r.json();
}

async function doLogout() {
  try { await fetch("/api/logout", { method: "POST" }); }
  catch (e) { console.warn("logout failed", e); }
}

function showLoginOverlay() {
  const ov = document.getElementById("loginOverlay");
  if (ov) ov.classList.remove("hidden");
  const u = document.getElementById("loginUser");
  if (u) u.focus();
}
/* Expose so dashboard.js can reuse the real overlay on a 401. */
window.showLoginOverlay = showLoginOverlay;

function hideLoginOverlay() {
  const ov = document.getElementById("loginOverlay");
  if (ov) ov.classList.add("hidden");
}

/* Reflect the signed-in user in the topbar and apply RBAC UI visibility. */
function applyRole(role, username) {
  const nameEl = document.getElementById("userName");
  if (nameEl) nameEl.textContent = username || "—";

  const badge = document.getElementById("roleBadge");
  if (badge) {
    badge.className = "role-badge role-" + (ROLE_LABEL[role] ? role : "monitor");
    badge.textContent = ROLE_LABEL[role] || role || "";
  }

  const btnLogout = document.getElementById("btnLogout");
  if (btnLogout) btnLogout.classList.remove("hidden");

  // dashboard.js defines applyRbacVisibility (hides #btnThr / #btnUsers for non-admin).
  if (window.applyRbacVisibility) window.applyRbacVisibility(role);
}

/* Reset the topbar back to the logged-out state. */
function resetTopbar() {
  const nameEl = document.getElementById("userName");
  if (nameEl) nameEl.textContent = "—";
  const badge = document.getElementById("roleBadge");
  if (badge) { badge.className = "role-badge"; badge.textContent = ""; }
  ["btnLogout", "btnUsers"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
  });
}

async function handleLoginSubmit() {
  const err = document.getElementById("loginErr");
  const u = document.getElementById("loginUser").value.trim();
  const p = document.getElementById("loginPass").value;
  err.textContent = "";
  if (!u || !p) { err.textContent = "Isi nama pengguna dan kata sandi."; return; }
  const btn = document.getElementById("loginBtn");
  btn.disabled = true;
  try {
    await doLogin(u, p);
    document.getElementById("loginPass").value = "";
    hideLoginOverlay();
    await boot(); // re-check /api/me, then start the dashboard
  } catch (e) {
    err.textContent = e.message || "Gagal masuk.";
  } finally {
    btn.disabled = false;
  }
}

/* Entry point: gate the dashboard behind a confirmed login. */
async function boot() {
  let me;
  try {
    me = await getMe();
  } catch (e) {
    console.error(e);
    const err = document.getElementById("loginErr");
    if (err) err.textContent = "Tidak dapat menghubungi server.";
    showLoginOverlay();
    return;
  }

  if (!me.authenticated) {
    resetTopbar();
    showLoginOverlay();
    return;
  }

  hideLoginOverlay();
  applyRole(me.role, me.username);
  if (window.initDashboard) window.initDashboard();
}

document.addEventListener("DOMContentLoaded", () => {
  const loginBtn = document.getElementById("loginBtn");
  if (loginBtn) loginBtn.addEventListener("click", handleLoginSubmit);

  // Enter key submits the login form.
  ["loginUser", "loginPass"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") handleLoginSubmit();
    });
  });

  const btnLogout = document.getElementById("btnLogout");
  if (btnLogout) btnLogout.addEventListener("click", async () => {
    await doLogout();
    resetTopbar();
    showLoginOverlay();
  });

  boot();
});
