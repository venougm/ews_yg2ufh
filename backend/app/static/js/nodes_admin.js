/* ============================================================
   EWS YG2UFH — admin-only node/gateway/region management (FEAT-002).

   Contract (FEAT-001, admin only — backend is the real enforcer):
     GET    /api/nodes                      -> 200 [NodeOut]
     POST   /api/nodes {node_id,...,lokasi} -> 201 NodeOut | 409 node_id sudah
                                               terdaftar | 422 validasi
     PUT    /api/nodes/{node_id} {...}       -> 200 NodeOut (node_id path-locked)
     DELETE /api/nodes/{node_id}            -> 200 {ok:true} | 404
     GET    /api/kabupaten                  -> 200 [{id,nama,provinsi}]
     POST   /api/kabupaten {id,nama,provinsi} -> 201
     GET    /api/kabupaten/{kab}/kecamatan  -> 200 [{id,nama,kabupaten_id}]
     POST   /api/kabupaten/{kab}/kecamatan {id,nama,kabupaten_id} -> 201

   All mutating calls return 401 (anon) / 403 (non-admin). Fetches are
   same-origin so the 'ews_session' cookie is sent automatically.

   Opened by #btnAddNode / #btnAddGateway / #btnDevices (shown only for admins
   by dashboard.js applyRbacVisibility). node_id is the MQTT-matching identity
   and is LOCKED on edit (case-sensitive) — see docs/decisions.md.
   ============================================================ */

function escN(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- modal helpers ---------------- */
function nodeModal() { return document.getElementById("nodeModal"); }
function devicesModal() { return document.getElementById("devicesModal"); }

function nodeErr(msg, ok) {
  const el = document.getElementById("nodeErr");
  if (!el) return;
  el.style.color = ok ? "var(--green)" : "";
  el.textContent = msg || "";
}
function devicesErr(msg, ok) {
  const el = document.getElementById("devicesErr");
  if (!el) return;
  el.style.color = ok ? "var(--green)" : "";
  el.textContent = msg || "";
}

/* 401/403 can happen if the session expired between opening and acting.
   401 reopens the login overlay; 403 shows a friendly admin-only message. */
function handleAuthStatus(status, setErr) {
  if (status === 401) {
    if (setErr) setErr("Sesi habis, silakan login lagi.");
    if (window.showLoginOverlay) window.showLoginOverlay();
    return true;
  }
  if (status === 403) {
    if (setErr) setErr("Aksi ini hanya untuk admin.");
    return true;
  }
  return false;
}

/* Refresh the dashboard (map + cards) after a mutation, guarded so this file
   is resilient if a hook is missing. */
function refreshDashboard() {
  if (window.loadNodes) window.loadNodes();
}

/* ---------------- region dropdowns ---------------- */
async function populateKabDropdown(selectedId) {
  const sel = document.getElementById("nodeKab");
  if (!sel) return;
  sel.innerHTML = '<option value="">— pilih —</option>';
  try {
    const r = await fetch("/api/kabupaten");
    if (handleAuthStatus(r.status, nodeErr)) return;
    if (!r.ok) return;
    const list = await r.json();
    for (const k of list) {
      const opt = document.createElement("option");
      opt.value = k.id;
      opt.textContent = k.nama || k.id;
      sel.appendChild(opt);
    }
  } catch (e) {
    console.warn("kabupaten load failed", e);
    return;
  }
  if (selectedId != null) sel.value = selectedId;
}

async function populateKecDropdown(kab, selectedId) {
  const sel = document.getElementById("nodeKec");
  if (!sel) return;
  sel.innerHTML = '<option value="">— pilih —</option>';
  if (!kab) return;
  try {
    const r = await fetch("/api/kabupaten/" + encodeURIComponent(kab) + "/kecamatan");
    if (handleAuthStatus(r.status, nodeErr)) return;
    if (!r.ok) return;
    const list = await r.json();
    for (const k of list) {
      const opt = document.createElement("option");
      opt.value = k.id;
      opt.textContent = k.nama || k.id;
      sel.appendChild(opt);
    }
  } catch (e) {
    console.warn("kecamatan load failed", e);
    return;
  }
  if (selectedId != null) sel.value = selectedId;
}

/* ---------------- node form modal ---------------- */
let nodeMode = "add";          // 'add' | 'edit'
let nodeEditId = null;         // locked node_id when editing

async function openNodeModal(mode, nodeOrTipe) {
  nodeMode = mode === "edit" ? "edit" : "add";
  nodeErr("");
  const idInp = document.getElementById("nodeId");
  const title = document.getElementById("nodeTitle");

  if (nodeMode === "edit") {
    const node = nodeOrTipe || {};
    nodeEditId = node.node_id;
    title.textContent = "Edit Node";
    idInp.value = node.node_id || "";
    idInp.readOnly = true;
    idInp.classList.add("node-id-locked");
    document.getElementById("nodeNama").value = node.nama || "";
    document.getElementById("nodeTipe").value =
      (node.tipe || "").toLowerCase().includes("gateway") ? "gateway" : "node";
    document.getElementById("nodeLat").value = node.lat != null ? node.lat : "";
    document.getElementById("nodeLon").value = node.lon != null ? node.lon : "";
    document.getElementById("nodeLokasi").value = node.lokasi || "";
    await populateKabDropdown(node.kabupaten || "");
    await populateKecDropdown(node.kabupaten || "", node.kecamatan || "");
  } else {
    const presetTipe = typeof nodeOrTipe === "string" ? nodeOrTipe : "node";
    nodeEditId = null;
    title.textContent = presetTipe === "gateway" ? "Tambah Gateway" : "Tambah Node";
    idInp.value = "";
    idInp.readOnly = false;
    idInp.classList.remove("node-id-locked");
    document.getElementById("nodeNama").value = "";
    document.getElementById("nodeTipe").value = presetTipe === "gateway" ? "gateway" : "node";
    document.getElementById("nodeLat").value = "";
    document.getElementById("nodeLon").value = "";
    document.getElementById("nodeLokasi").value = "";
    await populateKabDropdown("");
    await populateKecDropdown("");
  }
  nodeModal().classList.remove("hidden");
}

function closeNodeModal() { nodeModal().classList.add("hidden"); }

async function saveNode() {
  const idRaw = document.getElementById("nodeId").value.trim();
  const nama = document.getElementById("nodeNama").value.trim();
  const tipe = document.getElementById("nodeTipe").value;
  const kabupaten = document.getElementById("nodeKab").value || null;
  const kecamatan = document.getElementById("nodeKec").value || null;
  const latRaw = document.getElementById("nodeLat").value.trim();
  const lonRaw = document.getElementById("nodeLon").value.trim();
  const lokasi = document.getElementById("nodeLokasi").value.trim() || null;

  const node_id = nodeMode === "edit" ? nodeEditId : idRaw;
  if (!node_id) { nodeErr("node_id wajib diisi."); return; }

  const lat = latRaw === "" ? null : parseFloat(latRaw);
  const lon = lonRaw === "" ? null : parseFloat(lonRaw);
  if (lat != null && isNaN(lat)) { nodeErr("Latitude harus angka."); return; }
  if (lon != null && isNaN(lon)) { nodeErr("Longitude harus angka."); return; }

  const body = {
    nama: nama || null,
    tipe,
    kabupaten,
    kecamatan,
    lat,
    lon,
    lokasi,
  };

  let url, method;
  if (nodeMode === "edit") {
    url = "/api/nodes/" + encodeURIComponent(node_id);
    method = "PUT";
  } else {
    body.node_id = node_id;
    url = "/api/nodes";
    method = "POST";
  }

  let r;
  try {
    r = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (e) {
    nodeErr("Gagal menghubungi server.");
    return;
  }
  if (handleAuthStatus(r.status, nodeErr)) return;
  if (r.status === 409) { nodeErr("node_id sudah terdaftar."); return; }
  if (r.status === 422 || r.status === 400) {
    nodeErr("Data tidak valid (cek node_id serta rentang lat/lon).");
    return;
  }
  if (!r.ok) { nodeErr("Gagal menyimpan perangkat."); return; }

  closeNodeModal();
  refreshDashboard();
  if (!devicesModal().classList.contains("hidden")) loadDevices();
}

async function deleteNode(nodeId) {
  if (!confirm(
    'Hapus pendaftaran "' + nodeId + '"? Ini menghapus pendaftaran dashboard; ' +
    "alat fisik tetap mengirim ke MQTT sampai dimatikan."
  )) return;

  let r;
  try {
    r = await fetch("/api/nodes/" + encodeURIComponent(nodeId), { method: "DELETE" });
  } catch (e) {
    devicesErr("Gagal menghubungi server.");
    return;
  }
  if (handleAuthStatus(r.status, devicesErr)) return;
  if (r.status === 404) { devicesErr("Perangkat tidak ditemukan."); return; }
  if (!r.ok) { devicesErr("Gagal menghapus perangkat."); return; }
  devicesErr('Pendaftaran "' + nodeId + '" dihapus.', true);
  refreshDashboard();
  await loadDevices();
}

/* ---------------- Perangkat Terdaftar panel ---------------- */
async function loadDevices() {
  const list = document.getElementById("devicesList");
  list.innerHTML = '<div class="dim">Memuat…</div>';
  let r;
  try {
    r = await fetch("/api/nodes");
  } catch (e) {
    list.innerHTML = '<div class="dim">Gagal memuat perangkat.</div>';
    return;
  }
  if (handleAuthStatus(r.status, devicesErr)) { list.innerHTML = ""; return; }
  if (!r.ok) { list.innerHTML = '<div class="dim">Gagal memuat perangkat.</div>'; return; }
  const nodes = await r.json();
  if (!nodes.length) { list.innerHTML = '<div class="dim">Belum ada perangkat.</div>'; return; }

  list.innerHTML = "";
  for (const node of nodes) {
    const tipe = (node.tipe || "node").toLowerCase().includes("gateway") ? "gateway" : "node";
    const coord = node.lat != null && node.lon != null
      ? node.lat + ", " + node.lon : "—";
    const region = [node.kabupaten, node.kecamatan].filter(Boolean).join(" / ") || "—";
    const status = node.status || "—";

    const row = document.createElement("div");
    row.className = "user-row";
    row.innerHTML =
      '<span class="user-name">' + escN(node.node_id) + "</span>" +
      '<span class="role-badge role-' + (tipe === "gateway" ? "operator" : "monitor") + '">' +
        escN(tipe) + "</span>" +
      '<span class="dim" style="font-size:12px">' + escN(region) +
        " · " + escN(coord) + " · " + escN(status) + "</span>" +
      '<span class="spacer"></span>' +
      '<button class="btn-thr" style="margin-right:6px">Edit</button>' +
      '<button class="btn-del">Hapus</button>';
    const btns = row.querySelectorAll("button");
    btns[0].addEventListener("click", () => openNodeModal("edit", node));
    btns[1].addEventListener("click", () => deleteNode(node.node_id));
    list.appendChild(row);
  }
}

/* Refresh the kabupaten selectors used both in the devices panel (kecamatan
   add) and the dashboard region filter. */
async function populateKecKabDropdown() {
  const sel = document.getElementById("kecKab");
  if (!sel) return;
  sel.innerHTML = '<option value="">— kabupaten —</option>';
  try {
    const r = await fetch("/api/kabupaten");
    if (handleAuthStatus(r.status, devicesErr)) return;
    if (!r.ok) return;
    const list = await r.json();
    for (const k of list) {
      const opt = document.createElement("option");
      opt.value = k.id;
      opt.textContent = k.nama || k.id;
      sel.appendChild(opt);
    }
  } catch (e) {
    console.warn("kabupaten load failed", e);
  }
}

async function addKabupaten() {
  const id = document.getElementById("kabId").value.trim();
  const nama = document.getElementById("kabNama").value.trim();
  const provinsi = document.getElementById("kabProv").value.trim();
  if (!id || !nama || !provinsi) { devicesErr("Isi id, nama, dan provinsi kabupaten."); return; }

  let r;
  try {
    r = await fetch("/api/kabupaten", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, nama, provinsi }),
    });
  } catch (e) {
    devicesErr("Gagal menghubungi server.");
    return;
  }
  if (handleAuthStatus(r.status, devicesErr)) return;
  if (!r.ok) { devicesErr("Gagal menambah kabupaten."); return; }
  devicesErr('Kabupaten "' + nama + '" ditambahkan.', true);
  document.getElementById("kabId").value = "";
  document.getElementById("kabNama").value = "";
  document.getElementById("kabProv").value = "";
  await populateKecKabDropdown();
  if (window.loadKabupaten) window.loadKabupaten();
}

async function addKecamatan() {
  const kab = document.getElementById("kecKab").value;
  const id = document.getElementById("kecId").value.trim();
  const nama = document.getElementById("kecNama").value.trim();
  if (!kab) { devicesErr("Pilih kabupaten untuk kecamatan."); return; }
  if (!id || !nama) { devicesErr("Isi id dan nama kecamatan."); return; }

  let r;
  try {
    r = await fetch("/api/kabupaten/" + encodeURIComponent(kab) + "/kecamatan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, nama, kabupaten_id: kab }),
    });
  } catch (e) {
    devicesErr("Gagal menghubungi server.");
    return;
  }
  if (handleAuthStatus(r.status, devicesErr)) return;
  if (!r.ok) { devicesErr("Gagal menambah kecamatan."); return; }
  devicesErr('Kecamatan "' + nama + '" ditambahkan.', true);
  document.getElementById("kecId").value = "";
  document.getElementById("kecNama").value = "";
}

function openDevices() {
  devicesErr("");
  devicesModal().classList.remove("hidden");
  loadDevices();
  populateKecKabDropdown();
}
function closeDevices() { devicesModal().classList.add("hidden"); }

/* ---------------- wiring ---------------- */
document.addEventListener("DOMContentLoaded", () => {
  const btnAddNode = document.getElementById("btnAddNode");
  if (btnAddNode) btnAddNode.addEventListener("click", () => openNodeModal("add", "node"));
  const btnAddGateway = document.getElementById("btnAddGateway");
  if (btnAddGateway) btnAddGateway.addEventListener("click", () => openNodeModal("add", "gateway"));
  const btnDevices = document.getElementById("btnDevices");
  if (btnDevices) btnDevices.addEventListener("click", openDevices);

  const nodeCancel = document.getElementById("nodeCancel");
  if (nodeCancel) nodeCancel.addEventListener("click", closeNodeModal);
  const nodeSave = document.getElementById("nodeSave");
  if (nodeSave) nodeSave.addEventListener("click", saveNode);

  // Reload kecamatan when the kabupaten selection changes in the node form.
  const nodeKab = document.getElementById("nodeKab");
  if (nodeKab) nodeKab.addEventListener("change", () => populateKecDropdown(nodeKab.value));

  const devicesClose = document.getElementById("devicesClose");
  if (devicesClose) devicesClose.addEventListener("click", closeDevices);
  const kabAdd = document.getElementById("kabAdd");
  if (kabAdd) kabAdd.addEventListener("click", addKabupaten);
  const kecAdd = document.getElementById("kecAdd");
  if (kecAdd) kecAdd.addEventListener("click", addKecamatan);
});
