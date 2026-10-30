/* EWS T-Beam web config — AP setup form logic.
   Flow: load GET /api/wilayah (dropdown source) + GET /api/config (current
   values) -> render form -> on "Simpan & Jalankan" POST /api/config, which the
   firmware saves via Config.writeFile() then reboots into WiFi client mode.
   Mirrors the behaviour/layout of docs/mockup/device-setup.html. */

let WILAYAH = {};      // { prov: { nama, kab:{ kab:{ nama, kec:{ kec:{ nama, kel:{ slug:label } } } } } } }
let currentRole = 0;   // 0 = NODE, 1 = GATEWAY

function $(id){ return document.getElementById(id); }
function toggleSec(h){ h.parentElement.classList.toggle('collapsed'); }

function pickRole(r){
  currentRole = r;
  $('roleGw').classList.toggle('active', r === 1);
  $('roleNode').classList.toggle('active', r === 0);
  // MQTT is most relevant for the gateway; keep it usable but de-emphasised for a node.
  $('cardMqtt').style.opacity = r === 1 ? '1' : '.7';
}

/* ---- LoRa preset helper (SF/BW shortcut, same intent as the mockup) ---- */
function applyPreset(v){
  if (v === 'jauh'){ $('loraSf').value = '10'; $('loraBw').value = '125000'; }
  else if (v === 'cepat'){ $('loraSf').value = '7'; $('loraBw').value = '250000'; }
}

/* =========================================================
   WILAYAH BERTINGKAT (dropdown, bukan ketik bebas -> anti-typo)
   Struktur: Provinsi -> Kabupaten -> Kecamatan -> Kelurahan/Desa.
   Option menampilkan nama; value = slug (dipakai di topic MQTT).
   Sumber: GET /api/wilayah (data/wilayah.json di SPIFFS).
   ========================================================= */
function opt(v, t){ const o = document.createElement('option'); o.value = v; o.textContent = t; return o; }

function fillProv(selected){
  const s = $('selProv'); s.innerHTML = '';
  for (const k in WILAYAH) s.appendChild(opt(k, WILAYAH[k].nama));
  if (selected && WILAYAH[selected]) s.value = selected;
  fillKab();
}
function fillKab(selected){
  const prov = $('selProv').value;
  const s = $('selKab'); s.innerHTML = '';
  const kab = (WILAYAH[prov] && WILAYAH[prov].kab) || {};
  for (const k in kab) s.appendChild(opt(k, kab[k].nama));
  if (selected && kab[selected]) s.value = selected;
  fillKec();
}
function fillKec(selected){
  const prov = $('selProv').value, kab = $('selKab').value;
  const s = $('selKec'); s.innerHTML = '';
  const node = WILAYAH[prov] && WILAYAH[prov].kab && WILAYAH[prov].kab[kab];
  const kec = (node && node.kec) || {};
  for (const k in kec) s.appendChild(opt(k, kec[k].nama));
  if (selected && kec[selected]) s.value = selected;
  fillKel();
}
function fillKel(selected){
  const prov = $('selProv').value, kab = $('selKab').value, kec = $('selKec').value;
  const s = $('selKel'); s.innerHTML = '';
  const pNode = WILAYAH[prov] && WILAYAH[prov].kab && WILAYAH[prov].kab[kab];
  const kNode = pNode && pNode.kec && pNode.kec[kec];
  const kel = (kNode && kNode.kel) || {};
  for (const slug in kel) s.appendChild(opt(slug, kel[slug]));
  if (selected && kel[selected]) s.value = selected;
}

/* ---- load current config into the form ---- */
function populate(cfg){
  const id = cfg.identity || {};
  pickRole(id.role === 1 ? 1 : 0);
  $('nodeId').value = id.nodeId || '';
  $('locationName').value = id.locationName || '';
  $('networkId').value = id.networkId || '';
  $('latitude').value = (id.latitude !== undefined) ? id.latitude : '';
  $('longitude').value = (id.longitude !== undefined) ? id.longitude : '';
  // cascading dropdowns, pre-select stored slugs
  fillProv(id.provinsi);
  fillKab(id.kabupaten);
  fillKec(id.kecamatan);
  fillKel(id.kelurahan);

  const w = cfg.wifi || {};
  $('wifiSsid').value = w.ssid || '';
  $('wifiPassword').value = w.password || '';
  $('autoApEnabled').checked = !!(w.autoAP && w.autoAP.enabled);
  $('apPassword').value = (w.autoAP && w.autoAP.apPassword) || '1234567890';

  const m = cfg.mqtt || {};
  $('mqttActive').checked = !!m.active;
  $('mqttServer').value = m.server || '';
  $('mqttPort').value = (m.port !== undefined) ? m.port : 1883;
  $('mqttUsername').value = m.username || '';
  $('mqttPassword').value = m.password || '';
  $('mqttClientId').value = m.clientId || '';

  const l = cfg.lora || {};
  $('loraFreqMhz').value = l.freq ? (l.freq / 1e6).toFixed(1) : '915.0';
  $('loraSf').value = String(l.sf || 10);
  $('loraBw').value = String(l.bw || 125000);
  $('loraCr').value = String(l.cr || 5);
  $('loraPower').value = (l.power !== undefined) ? l.power : 20;
  $('loraCad').checked = !!l.cadActive;

  const s = cfg.sensors || {};
  $('senBme280').checked = !!s.bme280;
  $('senMq135').checked = !!s.mq135;
  $('senRain').checked = !!s.rain;
  $('senAnemo').checked = !!s.anemo;
  $('senTilt').checked = !!s.tilt;
  $('senEpever').checked = !!s.epever;
  $('senAds1115').checked = !!s.ads1115;
  $('senGps').checked = !!s.gps;
  $('intervalSec').value = (s.intervalSec !== undefined) ? s.intervalSec : 60;

  const si = cfg.siren || {};
  $('sirenEnabled').checked = !!si.enabled;
  $('missThresholdSec').value = (si.missThresholdSec !== undefined) ? si.missThresholdSec : 180;

  const th = cfg.thresholds || {};
  $('tiltSiaga').value = (th.tiltSiaga !== undefined) ? th.tiltSiaga : 5.0;
  $('tiltAwas').value = (th.tiltAwas !== undefined) ? th.tiltAwas : 10.0;
}

/* ---- gather the form into the config JSON shape the firmware expects ---- */
function gather(){
  const freqMhz = parseFloat($('loraFreqMhz').value) || 915.0;
  return {
    identity: {
      role: currentRole,
      nodeId: $('nodeId').value.trim(),
      networkId: $('networkId').value.trim() || 'ews1',
      provinsi: $('selProv').value,
      kabupaten: $('selKab').value,
      kecamatan: $('selKec').value,
      kelurahan: $('selKel').value,
      locationName: $('locationName').value.trim(),
      latitude: parseFloat($('latitude').value) || 0.0,
      longitude: parseFloat($('longitude').value) || 0.0
    },
    wifi: {
      ssid: $('wifiSsid').value,
      password: $('wifiPassword').value,
      autoAP: {
        enabled: $('autoApEnabled').checked,
        apPassword: $('apPassword').value || '1234567890',
        timeout: 10
      }
    },
    lora: {
      freq: Math.round(freqMhz * 1e6),
      sf: parseInt($('loraSf').value, 10),
      cr: parseInt($('loraCr').value, 10),
      bw: parseInt($('loraBw').value, 10),
      power: parseInt($('loraPower').value, 10) || 20,
      syncWord: 18,
      cadActive: $('loraCad').checked
    },
    mqtt: {
      active: $('mqttActive').checked,
      server: $('mqttServer').value.trim(),
      port: parseInt($('mqttPort').value, 10) || 1883,
      username: $('mqttUsername').value,
      password: $('mqttPassword').value,
      clientId: $('mqttClientId').value.trim()
    },
    sensors: {
      bme280: $('senBme280').checked,
      mq135: $('senMq135').checked,
      rain: $('senRain').checked,
      anemo: $('senAnemo').checked,
      tilt: $('senTilt').checked,
      ads1115: $('senAds1115').checked,
      epever: $('senEpever').checked,
      gps: $('senGps').checked,
      intervalSec: parseInt($('intervalSec').value, 10) || 60
    },
    siren: {
      enabled: $('sirenEnabled').checked,
      missThresholdSec: parseInt($('missThresholdSec').value, 10) || 180
    },
    thresholds: {
      tiltSiaga: parseFloat($('tiltSiaga').value) || 5.0,
      tiltAwas: parseFloat($('tiltAwas').value) || 10.0
    },
    display: { enabled: true, timeout: 0, turn180: false }
  };
}

function showToast(ok, title, desc){
  const t = $('toast');
  t.classList.toggle('err', !ok);
  $('toastTitle').innerHTML = (ok ? '<b>✓ ' : '<b>✕ ') + title + '</b>';
  $('toastDesc').textContent = desc || '';
  t.classList.add('show');
  if (ok) setTimeout(() => t.classList.remove('show'), 6000);
  else setTimeout(() => t.classList.remove('show'), 4500);
}

function doApply(){
  const cfg = gather();
  if (!cfg.identity.nodeId){ showToast(false, 'node_id wajib diisi.', 'Isi node_id lalu coba lagi.'); return; }
  if (!cfg.identity.kabupaten){ showToast(false, 'Kabupaten/Kota wajib dipilih.', 'Pilih wilayah dari dropdown.'); return; }

  const btn = $('btnApply'); btn.disabled = true;
  fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg)
  }).then(r => r.json().then(j => ({ ok: r.ok, j })))
    .then(({ ok, j }) => {
      if (ok && j.ok){
        showToast(true, 'Config tersimpan. Perangkat reboot…',
          'Beralih dari AP ke WiFi client ' + (cfg.wifi.ssid || '(belum diisi)') + '. Buka halaman status di IP baru alat.');
      } else {
        btn.disabled = false;
        showToast(false, (j && j.error) || 'Gagal menyimpan.', 'Periksa isian lalu coba lagi.');
      }
    }).catch(() => {
      // POST may not return if the device reboots immediately; treat as success hint.
      showToast(true, 'Perintah terkirim.', 'Jika alat reboot, koneksi AP akan terputus. Buka halaman status di IP baru.');
    });
}

/* ---- bootstrap ---- */
function init(){
  pickRole(0);
  Promise.all([
    fetch('/api/wilayah').then(r => r.json()).catch(() => ({})),
    fetch('/api/config').then(r => r.json()).catch(() => ({}))
  ]).then(([wilayah, cfg]) => {
    // strip the leading _comment key from wilayah.json
    if (wilayah && wilayah._comment) delete wilayah._comment;
    WILAYAH = wilayah || {};
    populate(cfg || {});
  });
}
document.addEventListener('DOMContentLoaded', init);
