/* ============================================================
   EWS YG2UFH node-detail — real data only.

   Data sources (FEAT-001 contract):
     GET /api/nodes/{id}             -> NodeOut (404 if unknown)
     GET /api/nodes/{id}/history?hours=48 -> list[HistoryPointOut] (oldest first)
     GET /api/thresholds             -> list[ThresholdOut] (global + node:<id>)

   Reads node_id from the URL query string. NO localStorage, no dummy data.
   ============================================================ */

const COLORS = { green: "#2ea043", amber: "#d29922", red: "#e23b3b", blue: "#2f81f7", dim: "#8b949e" };
const GRID = "#2c333b";
const HISTORY_HOURS = 48;

function qs(name) { return new URLSearchParams(location.search).get(name); }
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function fetchJson(url) {
  const r = await fetch(url);
  if (r.status === 404) return { _notFound: true };
  if (!r.ok) throw new Error(`${url} -> ${r.status}`);
  return r.json();
}

function nodeStatus(node) {
  if (node.status === "offline") return "offline";
  const lvl = node.alarm && node.alarm.level;
  if (lvl === "awas") return "awas";
  if (lvl === "siaga") return "siaga";
  return "online";
}
function statusMeta(st) {
  return {
    online:  { dot: "dot-green", pill: "online",  text: "ONLINE" },
    siaga:   { dot: "dot-amber", pill: "siaga",   text: "SIAGA" },
    awas:    { dot: "dot-red",   pill: "awas",    text: "AWAS" },
    offline: { dot: "dot-red",   pill: "offline", text: "OFFLINE" },
  }[st] || { dot: "dot-green", pill: "online", text: "ONLINE" };
}

/* resolve SIAGA/AWAS for this node: node override if present, else global. */
function resolveThreshold(thresholds, nodeId) {
  const scope = "node:" + nodeId;
  const override = thresholds.find((t) => t.scope === scope);
  if (override) return { siaga: override.tilt_siaga, awas: override.tilt_awas };
  const global = thresholds.find((t) => t.scope === "global");
  return { siaga: global ? global.tilt_siaga : 2, awas: global ? global.tilt_awas : 5 };
}

/* ---------------- Chart.js helpers ---------------- */
function chartOpts(extra) {
  return Object.assign({
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: COLORS.dim, boxWidth: 12, font: { size: 11 } } } },
    scales: {
      x: { ticks: { color: COLORS.dim, maxTicksLimit: 8, font: { size: 10 } }, grid: { color: GRID } },
      y: { ticks: { color: COLORS.dim, font: { size: 10 } }, grid: { color: GRID } },
    },
  }, extra || {});
}
function line(ctx, labels, datasets, extra) {
  return new Chart(ctx, {
    type: "line",
    data: { labels, datasets: datasets.map((d) => Object.assign({ tension: .3, pointRadius: 0, borderWidth: 2 }, d)) },
    options: chartOpts(extra),
  });
}

function histLabels(history) {
  return history.map((h) => {
    const d = h.ts ? new Date(h.ts * 1000) : new Date(h.received_at);
    return d.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", hour12: false });
  });
}
function pick(history, path) {
  return history.map((h) => {
    let v = h.payload;
    for (const key of path) v = v && typeof v === "object" ? v[key] : undefined;
    return typeof v === "number" ? v : null;
  });
}
function tiltSeries(history) {
  return history.map((h) => {
    const t = (h.payload && h.payload.tilt) || {};
    if (typeof t.delta === "number") return t.delta;
    if (typeof t.x === "number") return t.x;
    return null;
  });
}

/* ---------------- render ---------------- */
function renderNotFound(id) {
  document.getElementById("content").innerHTML =
    `<div class="notfound">Perangkat <b>${esc(id || "(kosong)")}</b> tidak ditemukan.
     <br><br><a class="back" href="/">← kembali ke dashboard</a></div>`;
}

function renderNode(node, history, thr) {
  const st = nodeStatus(node);
  const m = statusMeta(st);
  const health = (node.payload && node.payload.health) || {};
  const loc = [node.kecamatan, node.kabupaten].filter(Boolean).join(", ");
  const coord = node.lat != null && node.lon != null
    ? `${node.lat.toFixed(4)}, ${node.lon.toFixed(4)}` : "—";

  document.getElementById("content").innerHTML = `
    <div class="head-card">
      <div>
        <h1><span class="status-dot ${m.dot}"></span>${esc(node.node_id)}</h1>
        <div class="loc">${esc(loc || node.nama || "")}</div>
      </div>
      <span class="pill-lg ${m.pill}">${m.text}</span>
      <span class="spacer"></span>
      <div class="kv">
        <div><div class="k">node_id</div><div class="v">${esc(node.node_id)}</div></div>
        <div><div class="k">Koordinat</div><div class="v">${esc(coord)}</div></div>
      </div>
    </div>

    <div class="grid">
      <div class="card">
        <h3>Tilt / Kemiringan</h3>
        <div class="csub">garis ambang SIAGA ${thr.siaga}° / AWAS ${thr.awas}° — memicu NOTIFIKASI, bukan sirine</div>
        <div class="chartbox"><canvas id="cTilt"></canvas></div>
      </div>
      <div class="card">
        <h3>Cuaca (BME280)</h3>
        <div class="csub">suhu · kelembapan · tekanan</div>
        <div class="chartbox"><canvas id="cWeather"></canvas>
          <div class="chart-empty hidden" id="weatherEmpty">Belum ada data cuaca.</div></div>
      </div>
      <div class="card">
        <h3>Daya (EPEVER)</h3>
        <div class="csub">tegangan aki · tegangan solar (PV) · beban</div>
        <div class="chartbox"><canvas id="cPower"></canvas>
          <div class="chart-empty hidden" id="powerEmpty">Belum ada data daya.</div></div>
      </div>
      <div class="card">
        <h3>Kesehatan Perangkat</h3>
        <div class="csub">kualitas sinyal & status (data terakhir)</div>
        <div class="stat-row">
          <div class="stat"><div class="s-lbl">RSSI</div><div class="s-val">${fmt(health.rssi, " dBm")}</div></div>
          <div class="stat"><div class="s-lbl">SNR</div><div class="s-val">${fmt(health.snr, " dB")}</div></div>
          <div class="stat"><div class="s-lbl">Uptime</div><div class="s-val">${fmtUptime(health.uptime)}</div></div>
          <div class="stat"><div class="s-lbl">Firmware</div><div class="s-val">${esc(health.fw ?? "—")}</div></div>
        </div>
        <div class="chartbox" style="height:120px;margin-top:10px"><canvas id="cRssi"></canvas></div>
      </div>
    </div>`;

  if (!history.length) return; // nothing to chart yet

  const L = histLabels(history);

  // Tilt + dashed threshold lines (resolved SIAGA / AWAS).
  const tilt = tiltSeries(history);
  const yMax = Math.max(thr.awas + 1, ...tilt.filter((v) => v != null), 6);
  line(document.getElementById("cTilt"), L, [
    { label: "Tilt Δ (°)", data: tilt, borderColor: COLORS.green, backgroundColor: "rgba(46,160,67,.08)", fill: true },
    { label: `SIAGA ${thr.siaga}°`, data: L.map(() => thr.siaga), borderColor: COLORS.amber, borderDash: [5, 5], pointRadius: 0 },
    { label: `AWAS ${thr.awas}°`, data: L.map(() => thr.awas), borderColor: COLORS.red, borderDash: [5, 5], pointRadius: 0 },
  ], { scales: {
      x: { ticks: { color: COLORS.dim, maxTicksLimit: 8, font: { size: 10 } }, grid: { color: GRID } },
      y: { min: 0, max: yMax, ticks: { color: COLORS.dim, font: { size: 10 } }, grid: { color: GRID } },
  }});

  // Weather — hanya garis yang punya data yang digambar.
  const wTemp = pick(history, ["weather", "temp"]);
  const wHum = pick(history, ["weather", "hum"]);
  const wPress = pick(history, ["weather", "press"]);
  const weatherSets = [
    { label: "Suhu (°C)", data: wTemp, borderColor: COLORS.red },
    { label: "Lembap (%)", data: wHum, borderColor: COLORS.blue },
    { label: "Tekanan (hPa)", data: wPress, borderColor: COLORS.dim },
  ].filter((d) => hasData(d.data));
  renderChartOrEmpty("cWeather", "weatherEmpty", L, weatherSets);

  // Power (EPEVER): baterai (batt_v), solar cell (pv_v), beban/penggunaan daya (load_a).
  // Field yang tidak pernah dikirim node TIDAK digambar.
  const pBatt = pick(history, ["power", "batt_v"]);
  const pPv = pick(history, ["power", "pv_v"]);
  const pLoad = pick(history, ["power", "load_a"]);
  const powerSets = [
    { label: "Baterai (V)", data: pBatt, borderColor: COLORS.green },
    { label: "PV / solar (V)", data: pPv, borderColor: COLORS.amber },
    { label: "Beban (A)", data: pLoad, borderColor: COLORS.blue },
  ].filter((d) => hasData(d.data));
  renderChartOrEmpty("cPower", "powerEmpty", L, powerSets);

  // RSSI.
  line(document.getElementById("cRssi"), L, [
    { label: "RSSI (dBm)", data: pick(history, ["health", "rssi"]), borderColor: COLORS.blue,
      backgroundColor: "rgba(47,129,247,.08)", fill: true },
  ]);
}

/* true jika seri punya minimal satu nilai angka (bukan semua null) */
function hasData(arr) { return Array.isArray(arr) && arr.some((v) => v != null); }

/* Gambar chart hanya jika ada dataset berisi; jika tidak, tampilkan pesan
   "belum ada data" dan sembunyikan canvas-nya (data tidak ada = tidak tampil). */
function renderChartOrEmpty(canvasId, emptyId, labels, datasets) {
  const canvas = document.getElementById(canvasId);
  const empty = document.getElementById(emptyId);
  if (!datasets.length) {
    if (canvas) canvas.style.display = "none";
    if (empty) empty.classList.remove("hidden");
    return;
  }
  if (canvas) canvas.style.display = "";
  if (empty) empty.classList.add("hidden");
  line(canvas, labels, datasets);
}

function fmt(v, unit) { return v == null ? "—" : `${v}${unit || ""}`; }
function fmtUptime(sec) {
  if (sec == null) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}j ${m}m`;
}

/* ---------------- entry ---------------- */
(async function () {
  const id = qs("id");
  if (!id) { renderNotFound(id); return; }
  document.title = "Detail " + id + " — EWS YG2UFH";
  try {
    const node = await fetchJson("/api/nodes/" + encodeURIComponent(id));
    if (node._notFound) { renderNotFound(id); return; }
    const [history, thresholds] = await Promise.all([
      fetchJson(`/api/nodes/${encodeURIComponent(id)}/history?hours=${HISTORY_HOURS}`),
      fetchJson("/api/thresholds"),
    ]);
    const thr = resolveThreshold(Array.isArray(thresholds) ? thresholds : [], id);
    renderNode(node, Array.isArray(history) ? history : [], thr);
  } catch (e) {
    console.error(e);
    document.getElementById("content").innerHTML =
      `<div class="notfound">Gagal memuat data node <b>${esc(id)}</b>.
       <br><br><a class="back" href="/">← kembali ke dashboard</a></div>`;
  }
})();
