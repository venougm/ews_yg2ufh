/* ============================================================
   EWS YG2UFH dashboard — real data only.

   Data sources (FEAT-001 contract):
     GET  /api/nodes?kabupaten=&kecamatan=   -> list[NodeOut]
     GET  /api/kabupaten                     -> list[KabupatenOut]
     GET  /api/kabupaten/{kab}/kecamatan     -> list[KecamatanOut]
     WS   /ws/live                           -> {type:'reading'} / {type:'alarm'}

   NO localStorage data source. The mockup files are visual reference only.
   ============================================================ */

const SLEMAN_FALLBACK = [-7.698, 110.41]; // map center when no node has coords
const COLORS = { green: "#2ea043", amber: "#d29922", red: "#e23b3b", blue: "#2f81f7" };

const state = {
  nodes: {},        // node_id -> NodeOut (latest known)
  markers: {},      // node_id -> Leaflet marker
  filterKab: "",
  filterKec: "",
  muted: false,
  map: null,
  nodeLayer: null,
};

/* ---------------- clock ---------------- */
function tick() {
  const el = document.getElementById("clock");
  if (!el) return;
  const d = new Date();
  const tgl = d.toLocaleDateString("id-ID", { weekday: "long", day: "2-digit", month: "short", year: "numeric" });
  const jam = d.toLocaleTimeString("id-ID", { hour12: false });
  el.textContent = tgl + " · " + jam;
}
setInterval(tick, 1000);
tick();

/* ---------------- helpers ---------------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function nodeKind(node) {
  const t = (node.tipe || "").toLowerCase();
  return t.includes("gateway") || t === "gw" ? "gateway" : "node";
}

/* Resolve a dashboard status for color/label from a NodeOut.
   Priority: offline > awas > siaga > online. */
function nodeStatus(node) {
  if (node.status === "offline") return "offline";
  const lvl = node.alarm && node.alarm.level;
  if (lvl === "awas") return "awas";
  if (lvl === "siaga") return "siaga";
  return "online";
}

function statusColor(st) {
  if (st === "offline" || st === "awas") return COLORS.red;
  if (st === "siaga") return COLORS.amber;
  return COLORS.green;
}

function statusLabel(st) {
  return { online: "ONLINE", siaga: "SIAGA", awas: "AWAS", offline: "OFFLINE" }[st] || "ONLINE";
}

function fmtWeather(p) {
  // Hanya tampilkan field cuaca yang dikirim node; yang kosong disembunyikan.
  const w = (p && p.weather) || {};
  const parts = [];
  if (w.temp != null) parts.push(`${w.temp}°C`);
  if (w.hum != null) parts.push(`${w.hum}%`);
  if (w.press != null) parts.push(`${w.press} hPa`);
  return parts.length ? parts.join(" · ") : "—";
}
function fmtPower(p) {
  // EPEVER: tampilkan hanya field yang DIKIRIM node. Field yang tidak ada
  // (null/undefined) tidak ditampilkan sama sekali — bukan "–".
  const pw = (p && p.power) || {};
  const parts = [];
  if (pw.batt_v != null) parts.push(`Batt ${pw.batt_v} V`);   // tegangan aki
  if (pw.pv_v != null) parts.push(`PV ${pw.pv_v} V`);         // tegangan solar cell
  if (pw.load_a != null) parts.push(`Beban ${pw.load_a} A`);  // penggunaan daya
  if (pw.soc != null) parts.push(`${pw.soc}%`);               // kapasitas aki
  return parts.length ? parts.join(" · ") : "—";
}
function tiltValue(p) {
  const t = (p && p.tilt) || {};
  if (typeof t.delta === "number") return t.delta;
  if (typeof t.x === "number") return t.x;
  return null;
}

/* ---------------- rendering ---------------- */
function visibleNodes() {
  return Object.values(state.nodes).sort((a, b) => a.node_id.localeCompare(b.node_id));
}

function renderCards() {
  const wrap = document.getElementById("cards");
  const empty = document.getElementById("cardsEmpty");
  const nodes = visibleNodes();
  wrap.innerHTML = "";
  document.getElementById("nodeCount").textContent = `${nodes.length} node`;

  if (!nodes.length) {
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");

  for (const node of nodes) {
    const st = nodeStatus(node);
    const dot = { online: "dot-green", siaga: "dot-amber", awas: "dot-red", offline: "dot-red" }[st];
    const pillColor = st === "siaga" ? "color:var(--amber)" : (st === "awas" || st === "offline") ? "color:var(--accent)" : "";
    const tilt = tiltValue(node.payload);
    const health = (node.payload && node.payload.health) || {};
    const rssi = health.rssi != null ? `RSSI ${health.rssi}` : "";

    let tiltCls = "ok", tiltTxt = "—";
    if (tilt != null) {
      tiltTxt = `Δ ${tilt}°`;
      if (st === "awas") { tiltCls = "danger"; tiltTxt += " ⚠"; }
      else if (st === "siaga") { tiltCls = "warn"; tiltTxt += " ⚠"; }
      else { tiltCls = "ok"; tiltTxt += " OK"; }
    }

    const card = document.createElement("div");
    card.className = "card card-click";
    card.id = "card-" + cssId(node.node_id);
    if (st === "awas") card.classList.add("alarm-awas");
    else if (st === "siaga") card.classList.add("alarm-siaga");
    card.title = "Lihat detail & grafik " + node.node_id;
    card.onclick = () => openDetail(node.node_id);

    card.innerHTML = `
      <h3><span class="status-dot ${dot}"></span>${esc(node.node_id)}
        <span class="pill" style="${pillColor}">${statusLabel(st)}</span>
        <span class="go">detail →</span></h3>
      <div class="field"><div class="lbl">Cuaca</div><div class="val">${esc(fmtWeather(node.payload))}</div></div>
      <div class="field"><div class="lbl">Daya (EPEVER)</div><div class="val">${esc(fmtPower(node.payload))}</div></div>
      <div class="field"><div class="lbl">Tilt <span class="meta">${esc(rssi)}</span></div>
        <div class="val ${tiltCls}">${esc(tiltTxt)}</div></div>`;
    wrap.appendChild(card);
  }
}

function cssId(id) {
  return String(id).replace(/[^a-zA-Z0-9_-]/g, "_");
}

function openDetail(id) {
  location.href = "node.html?id=" + encodeURIComponent(id);
}

/* ---------------- Leaflet map ---------------- */
function initMap() {
  const map = L.map("map", { zoomControl: true }).setView(SLEMAN_FALLBACK, 12);
  state.map = map;
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19, attribution: "© OpenStreetMap",
  }).addTo(map);
  state.nodeLayer = L.layerGroup().addTo(map);
}

function makeIcon(node) {
  const st = nodeStatus(node);
  const c = nodeKind(node) === "gateway" ? COLORS.red : statusColor(st);
  const square = nodeKind(node) === "gateway";
  return L.divIcon({
    className: "",
    html: `<div style="width:16px;height:16px;background:${c};border:2px solid #0d0f12;
      border-radius:${square ? "3px" : "50%"};box-shadow:0 0 0 2px ${c}44"></div>`,
    iconSize: [16, 16], iconAnchor: [8, 8], popupAnchor: [0, -10],
  });
}

function popupHtml(node) {
  const st = nodeStatus(node);
  const coord = node.lat != null && node.lon != null
    ? `<span style="color:#8b949e">${node.lat.toFixed(4)}, ${node.lon.toFixed(4)}</span>` : "";
  return `<b>${esc(node.node_id)}</b><br>${statusLabel(st)}` +
    (tiltValue(node.payload) != null ? ` · tilt Δ${tiltValue(node.payload)}°` : "") +
    `<br>${coord}`;
}

function redrawMarkers() {
  if (!state.nodeLayer) return;
  state.nodeLayer.clearLayers();
  state.markers = {};
  const pts = [];
  for (const node of visibleNodes()) {
    if (node.lat == null || node.lon == null) continue;
    const m = L.marker([node.lat, node.lon], { icon: makeIcon(node) })
      .bindPopup(popupHtml(node));
    m.on("click", () => openDetail(node.node_id));
    m.addTo(state.nodeLayer);
    state.markers[node.node_id] = m;
    pts.push([node.lat, node.lon]);
  }
  if (pts.length === 1) state.map.setView(pts[0], 13);
  else if (pts.length > 1) state.map.fitBounds(pts, { padding: [40, 40], maxZoom: 14 });
}

/* ---------------- auth error handling ---------------- */
/* Thrown by fetchJson on 401/403 so callers can show a friendly message.
   401 -> session expired (show login overlay); 403 -> needs admin. */
class AuthError extends Error {
  constructor(status) {
    super(status === 401 ? "Sesi habis, silakan login lagi." : "Aksi ini hanya untuk admin.");
    this.status = status;
  }
}

/* Show the login overlay again (reuses auth.js if present). */
function showLoginOverlay() {
  if (window.showLoginOverlay && window.showLoginOverlay !== showLoginOverlay) {
    window.showLoginOverlay();
    return;
  }
  const ov = document.getElementById("loginOverlay");
  if (ov) ov.classList.remove("hidden");
}

/* ---------------- data loading ---------------- */
async function fetchJson(url) {
  const r = await fetch(url);
  if (r.status === 401 || r.status === 403) {
    if (r.status === 401) showLoginOverlay();
    throw new AuthError(r.status);
  }
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

async function loadNodes() {
  const params = new URLSearchParams();
  if (state.filterKab) params.set("kabupaten", state.filterKab);
  if (state.filterKec) params.set("kecamatan", state.filterKec);
  const qs = params.toString();
  const list = await fetchJson("/api/nodes" + (qs ? "?" + qs : ""));
  state.nodes = {};
  for (const n of list) state.nodes[n.node_id] = n;
  renderCards();
  redrawMarkers();
}

async function loadKabupaten() {
  const sel = document.getElementById("selKab");
  try {
    const list = await fetchJson("/api/kabupaten");
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

async function loadKecamatan(kab) {
  const sel = document.getElementById("selKec");
  sel.innerHTML = '<option value="">Semua kecamatan</option>';
  if (!kab) return;
  try {
    const list = await fetchJson(`/api/kabupaten/${encodeURIComponent(kab)}/kecamatan`);
    for (const k of list) {
      const opt = document.createElement("option");
      opt.value = k.id;
      opt.textContent = k.nama || k.id;
      sel.appendChild(opt);
    }
  } catch (e) {
    console.warn("kecamatan load failed", e);
  }
}

/* ---------------- Web Audio beep (no media file) ---------------- */
let audioCtx = null;
function beep(level) {
  if (state.muted) return;
  try {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "square";
    // AWAS = higher, more urgent tone than SIAGA.
    osc.frequency.value = level === "awas" ? 880 : 523;
    gain.gain.setValueAtTime(0.001, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.2, audioCtx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.5);
  } catch (e) {
    console.warn("beep failed", e);
  }
}

/* ---------------- MUTE toggle ---------------- */
function clearAllBlink() {
  document.querySelectorAll(".alarm-awas, .alarm-siaga").forEach((el) => {
    el.classList.remove("alarm-awas", "alarm-siaga");
  });
}
function setupMute() {
  const btn = document.getElementById("btnMute");
  btn.addEventListener("click", () => {
    state.muted = !state.muted;
    btn.textContent = state.muted ? "🔇 Dibisukan" : "🔊 Bisukan";
    if (state.muted) {
      // Muting silences the beep and clears current blink until a NEW alarm.
      clearAllBlink();
      document.getElementById("alarmBar").classList.add("hidden");
    }
  });
}

/* ---------------- alarm handling ---------------- */
function showAlarmBar(level, text) {
  const bar = document.getElementById("alarmBar");
  bar.classList.remove("hidden", "awas", "siaga");
  bar.classList.add(level === "awas" ? "awas" : "siaga");
  document.getElementById("alarmBarText").textContent = text;
}

function showBanner(level, title, sub) {
  const b = document.getElementById("banner");
  b.classList.remove("hidden");
  const dot = document.getElementById("bannerDot");
  dot.className = "status-dot " + (level === "awas" ? "dot-red" : "dot-amber");
  dot.style.width = "14px"; dot.style.height = "14px";
  document.getElementById("bannerTitle").textContent = title;
  document.getElementById("bannerSub").textContent = sub;
}

function logAlarm(level, source, reason) {
  const log = document.getElementById("alarmLog");
  if (log.firstChild && log.firstChild.textContent === "menunggu data…") log.innerHTML = "";
  const row = document.createElement("div");
  row.className = "row " + (level === "awas" ? "awas" : "siaga");
  const t = new Date().toLocaleTimeString("id-ID", { hour12: false });
  row.textContent = `${t}  ${level.toUpperCase()}  ${source}  ${reason}`;
  log.insertBefore(row, log.firstChild);
  while (log.children.length > 30) log.removeChild(log.lastChild);
}

function blinkCard(nodeId, level) {
  const card = document.getElementById("card-" + cssId(nodeId));
  if (!card) return;
  card.classList.remove("alarm-awas", "alarm-siaga");
  if (state.muted) return; // muted: no new blink until unmuted + new alarm
  card.classList.add(level === "awas" ? "alarm-awas" : "alarm-siaga");
}

function handleAlarm(msg) {
  const level = msg.level === "awas" ? "awas" : "siaga";
  const source = msg.source || "—";
  const reason = msg.reason || "";
  logAlarm(level, source, reason);
  showAlarmBar(level, `${level.toUpperCase()} — ${source} · ${reason}`);
  showBanner(level, `${level.toUpperCase()} — ${source}`, reason + " · perlu verifikasi operator");
  blinkCard(source, level);
  beep(level);
}

function handleReading(msg) {
  const nodeId = msg.node_id;
  if (!nodeId) return;
  const existing = state.nodes[nodeId];
  // Merge live reading into the known node. If it is a brand-new node that
  // passes the active filter path we still show it (filtering by kabupaten).
  const merged = Object.assign({}, existing || { node_id: nodeId }, {
    kabupaten: msg.kabupaten ?? (existing && existing.kabupaten),
    ts: msg.ts,
    received_at: msg.received_at,
    payload: msg.payload,
    alarm: msg.alarm || null,
    status: "online",
  });
  // Respect the active kabupaten filter for live inserts.
  if (!existing && state.filterKab && merged.kabupaten !== state.filterKab) return;

  state.nodes[nodeId] = merged;
  renderCards();
  // Reapply any active alarm blink that renderCards may have reset.
  const st = nodeStatus(merged);
  if (!state.muted && (st === "awas" || st === "siaga")) blinkCard(nodeId, st);

  // Update marker in place when possible.
  if (state.markers[nodeId] && merged.lat != null && merged.lon != null) {
    state.markers[nodeId].setIcon(makeIcon(merged)).setPopupContent(popupHtml(merged));
  } else if (merged.lat != null && merged.lon != null) {
    redrawMarkers();
  }
}

/* ---------------- WebSocket (reconnecting) ---------------- */
function setBroker(ok) {
  const dot = document.getElementById("brokerDot");
  const txt = document.getElementById("brokerText");
  dot.className = "status-dot " + (ok ? "dot-green" : "dot-amber");
  txt.textContent = ok ? "Live terhubung" : "menyambung ulang…";
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/live`);
  ws.onopen = () => setBroker(true);
  ws.onclose = () => {
    setBroker(false);
    setTimeout(connectWs, 2000); // reconnect on close
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "reading") handleReading(msg);
    else if (msg.type === "alarm") handleAlarm(msg);
  };
}

/* ---------------- edit ambang (threshold) ---------------- */
let thrCache = [];   // list dari GET /api/thresholds

async function openThr() {
  const err = document.getElementById("thrErr");
  err.textContent = "";
  try {
    thrCache = await fetchJson("/api/thresholds");
  } catch (e) {
    thrCache = [{ scope: "global", tilt_siaga: 2.0, tilt_awas: 5.0 }];
  }
  // bangun daftar scope: global + tiap node yang dikenal (untuk override)
  const sel = document.getElementById("thrScope");
  sel.innerHTML = "";
  const scopes = ["global", ...visibleNodes().map((n) => "node:" + n.node_id)];
  for (const sc of scopes) {
    const opt = document.createElement("option");
    opt.value = sc;
    opt.textContent = sc === "global" ? "Global (default semua node)" : sc;
    sel.appendChild(opt);
  }
  fillThrFields("global");
  document.getElementById("thrModal").classList.remove("hidden");
}

function fillThrFields(scope) {
  const row = thrCache.find((r) => r.scope === scope);
  const glob = thrCache.find((r) => r.scope === "global") || { tilt_siaga: 2.0, tilt_awas: 5.0 };
  // untuk node tanpa override, tampilkan nilai global sebagai titik awal
  document.getElementById("thrSiaga").value = (row ? row.tilt_siaga : glob.tilt_siaga);
  document.getElementById("thrAwas").value = (row ? row.tilt_awas : glob.tilt_awas);
}

async function saveThr() {
  const err = document.getElementById("thrErr");
  const scope = document.getElementById("thrScope").value;
  const siaga = parseFloat(document.getElementById("thrSiaga").value);
  const awas = parseFloat(document.getElementById("thrAwas").value);
  if (isNaN(siaga) || isNaN(awas)) { err.textContent = "Nilai ambang harus angka."; return; }
  if (siaga <= 0 || awas <= 0) { err.textContent = "Ambang harus lebih dari 0."; return; }
  if (awas <= siaga) { err.textContent = "Ambang AWAS harus lebih besar dari SIAGA."; return; }
  try {
    const r = await fetch("/api/thresholds", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope, tilt_siaga: siaga, tilt_awas: awas }),
    });
    if (r.status === 401) {
      err.style.color = "";
      err.textContent = "Sesi habis, silakan login lagi.";
      showLoginOverlay();
      return;
    }
    if (r.status === 403) {
      err.style.color = "";
      err.textContent = "Aksi ini hanya untuk admin.";
      return;
    }
    if (!r.ok) throw new Error("PUT -> " + r.status);
    err.style.color = "var(--green)";
    err.textContent = "Tersimpan. Ambang untuk " + scope + " = SIAGA " + siaga + "° / AWAS " + awas + "°.";
    // refresh cache supaya pilihan scope lain ikut terbarui
    thrCache = await fetchJson("/api/thresholds");
    setTimeout(() => { err.style.color = ""; err.textContent = ""; }, 2500);
  } catch (e) {
    err.style.color = "";
    err.textContent = "Gagal menyimpan: " + e.message;
  }
}

function setupThr() {
  document.getElementById("btnThr").addEventListener("click", openThr);
  document.getElementById("thrCancel").addEventListener("click", () =>
    document.getElementById("thrModal").classList.add("hidden"));
  document.getElementById("thrSave").addEventListener("click", saveThr);
  document.getElementById("thrScope").addEventListener("change", (e) => fillThrFields(e.target.value));
}

/* ---------------- wiring ---------------- */
function setupFilters() {
  const selKab = document.getElementById("selKab");
  const selKec = document.getElementById("selKec");
  selKab.addEventListener("change", async () => {
    state.filterKab = selKab.value;
    state.filterKec = "";
    await loadKecamatan(state.filterKab);
    await loadNodes();
  });
  selKec.addEventListener("change", async () => {
    state.filterKec = selKec.value;
    await loadNodes();
  });
}

/* ---------------- RBAC UI visibility (convenience only) ----------------
   The backend is the real enforcer (FEAT-001). Hiding controls here just
   avoids showing non-admins buttons that would 403 anyway.
     monitor -> view only
     operator -> view (siren control belongs here once it exists; TAHAP 1 has
                 no siren UI, so operator currently sees nothing extra)
     admin   -> everything incl. #btnThr (Edit Ambang) + #btnUsers (Kelola User)
   NOTE: when a physical-siren button is added, show it for operator+admin. */
function applyRbacVisibility(role) {
  const isAdmin = role === "admin";
  const btnThr = document.getElementById("btnThr");     // KEBUTUHAN A: admin only
  const btnUsers = document.getElementById("btnUsers"); // user mgmt: admin only
  if (btnThr) btnThr.classList.toggle("hidden", !isAdmin);
  if (btnUsers) btnUsers.classList.toggle("hidden", !isAdmin);
  // Node/gateway/region management (FEAT-002): admin only, same pattern.
  ["btnAddNode", "btnAddGateway", "btnDevices"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("hidden", !isAdmin);
  });
}
window.applyRbacVisibility = applyRbacVisibility;

/* Refresh hooks consumed by nodes_admin.js after a mutation (map + cards +
   filter dropdown refresh without a full page reload). Guarded by existence
   checks on the caller side. */
window.loadNodes = loadNodes;
window.redrawMarkers = redrawMarkers;
window.visibleNodes = visibleNodes;
window.loadKabupaten = loadKabupaten;

let _dashboardStarted = false;
async function init() {
  if (_dashboardStarted) return; // guard against double-init
  _dashboardStarted = true;
  initMap();
  setupMute();
  setupFilters();
  setupThr();
  await loadKabupaten();
  await loadNodes();
  connectWs();
}

/* auth.js calls this only after a confirmed login (no DOMContentLoaded auto-run). */
window.initDashboard = init;
