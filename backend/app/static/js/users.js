/* ============================================================
   EWS YG2UFH — admin-only 'Kelola User' panel (KEBUTUHAN B user mgmt).

   Contract (FEAT-001, admin only — backend enforces):
     GET    /api/users              -> 200 [{username, role, created_at}]
     POST   /api/users {u,p,role}   -> 201 {username,role,created_at}
                                       400 role tidak valid | 409 username sudah ada
     DELETE /api/users/{username}   -> 200 {ok:true}
                                       400 tidak boleh menghapus akun sendiri | 404

   Opened by #btnUsers (shown only for admins by dashboard.js). All fetches are
   same-origin so the session cookie is sent automatically.
   ============================================================ */

function escU(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function usersModal() { return document.getElementById("usersModal"); }
function usersErr(msg, ok) {
  const el = document.getElementById("usersErr");
  if (!el) return;
  el.style.color = ok ? "var(--green)" : "";
  el.textContent = msg || "";
}

/* 401/403 are possible if the session expired between opening and acting. */
function handleAuthStatus(status) {
  if (status === 401) {
    usersErr("Sesi habis, silakan login lagi.");
    if (window.showLoginOverlay) window.showLoginOverlay();
    return true;
  }
  if (status === 403) {
    usersErr("Aksi ini hanya untuk admin.");
    return true;
  }
  return false;
}

async function loadUsers() {
  const list = document.getElementById("usersList");
  list.innerHTML = '<div class="dim">Memuat…</div>';
  const r = await fetch("/api/users");
  if (handleAuthStatus(r.status)) { list.innerHTML = ""; return; }
  if (!r.ok) { list.innerHTML = '<div class="dim">Gagal memuat pengguna.</div>'; return; }
  const users = await r.json();
  if (!users.length) { list.innerHTML = '<div class="dim">Belum ada pengguna.</div>'; return; }

  list.innerHTML = "";
  for (const u of users) {
    const row = document.createElement("div");
    row.className = "user-row";
    row.innerHTML =
      `<span class="user-name">${escU(u.username)}</span>` +
      `<span class="role-badge role-${escU(u.role)}">${escU(u.role)}</span>` +
      `<span class="spacer"></span>` +
      `<button class="btn-del" data-username="${escU(u.username)}">Hapus</button>`;
    row.querySelector(".btn-del").addEventListener("click", () => deleteUser(u.username));
    list.appendChild(row);
  }
}

async function deleteUser(username) {
  if (!confirm(`Hapus pengguna "${username}"?`)) return;
  const r = await fetch("/api/users/" + encodeURIComponent(username), { method: "DELETE" });
  if (handleAuthStatus(r.status)) return;
  if (r.status === 400) { usersErr("Tidak boleh menghapus akun sendiri."); return; }
  if (r.status === 404) { usersErr("Pengguna tidak ditemukan."); return; }
  if (!r.ok) { usersErr("Gagal menghapus pengguna."); return; }
  usersErr(`Pengguna "${username}" dihapus.`, true);
  await loadUsers();
}

async function addUser() {
  const username = document.getElementById("newUser").value.trim();
  const password = document.getElementById("newPass").value;
  const role = document.getElementById("newRole").value;
  if (!username || !password) { usersErr("Isi username dan password."); return; }

  const r = await fetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, role }),
  });
  if (handleAuthStatus(r.status)) return;
  if (r.status === 409) { usersErr("Username sudah ada."); return; }
  if (r.status === 400) { usersErr("Peran tidak valid."); return; }
  if (!r.ok) { usersErr("Gagal menambah pengguna."); return; }
  usersErr(`Pengguna "${username}" ditambahkan.`, true);
  document.getElementById("newUser").value = "";
  document.getElementById("newPass").value = "";
  await loadUsers();
}

function openUsers() {
  usersErr("");
  usersModal().classList.remove("hidden");
  loadUsers();
}
function closeUsers() { usersModal().classList.add("hidden"); }

document.addEventListener("DOMContentLoaded", () => {
  const btnUsers = document.getElementById("btnUsers");
  if (btnUsers) btnUsers.addEventListener("click", openUsers);
  const closeBtn = document.getElementById("usersClose");
  if (closeBtn) closeBtn.addEventListener("click", closeUsers);
  const addBtn = document.getElementById("usersAdd");
  if (addBtn) addBtn.addEventListener("click", addUser);
});
