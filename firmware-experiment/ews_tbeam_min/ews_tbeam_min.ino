/*
 * EWS T-Beam — firmware EKSPERIMEN minimal (Arduino IDE)
 * ------------------------------------------------------
 * Tujuan: buktikan jalur HARDWARE ASLI -> WiFi -> MQTT -> backend EWS -> dashboard,
 * SEBELUM sensor dipasang. Belum pakai GPS/baterai (ditambah bertahap nanti).
 *
 * Yang dikirim: uptime, RSSI WiFi, suhu chip ESP32 (kalau tersedia), firmware tag.
 * Dipetakan ke skema EWS field-opsional:
 *   health.uptime, health.rssi, health.fw
 *   weather.temp  <- suhu chip ESP32 (DEMO, bukan suhu cuaca asli)
 *
 * Topik publish: yg2ufh/ews/<KABUPATEN>/<NODE_ID>/data  (JSON)
 *
 * === SETUP ARDUINO IDE (sekali) ===
 * 1) File > Preferences > Additional Boards Manager URLs, tambahkan:
 *      https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
 * 2) Tools > Board > Boards Manager > cari "esp32" (by Espressif) > Install.
 * 3) Tools > Board > ESP32 Arduino > pilih "T-Beam" (atau "ESP32 Dev Module").
 * 4) Sketch > Include Library > Manage Libraries, install:
 *      - "PubSubClient" (by Nick O'Leary)
 *      - "ArduinoJson" (by Benoit Blanchon)
 * 5) Colok T-Beam via USB, pilih Port yang muncul (Tools > Port).
 * 6) EDIT 6 nilai di bawah (WiFi, broker, node), lalu Upload (panah kanan).
 * 7) Buka Serial Monitor (115200 baud) untuk lihat log konek + kirim.
 *
 * CATATAN: MQTT di sini TANPA TLS (port 1883). Untuk uji/eksperimen OK; untuk
 * produksi nanti pertimbangkan TLS (8883).
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ====================== EDIT DI SINI ======================
const char* WIFI_SSID = "ISI_NAMA_WIFI";
const char* WIFI_PASS = "ISI_PASSWORD_WIFI";

const char* MQTT_HOST = "ISI_ALAMAT_BROKER";  // IP publik/domain server (atau IP lokal jika sejaringan)
const int   MQTT_PORT = 1883;
const char* MQTT_USER = "ews";
const char* MQTT_PASS = "ISI_PASSWORD_EWS";   // password mosquitto user ews

const char* NODE_ID   = "slm-tbeam-01";       // harus sama dgn yg didaftarkan di dashboard
const char* PROVINSI  = "diy";
const char* KABUPATEN = "sleman";
const char* KECAMATAN = "ngemplak";
const unsigned long INTERVAL_MS = 60000;      // kirim tiap 60 detik
// ==========================================================

const char* MQTT_CLIENT_ID = "ews-tbeam-01";  // beda dari backend & node lain

WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastSend = 0;
unsigned long seq = 0;

// Suhu internal chip ESP32 (°C). Tidak semua core punya; dibungkus aman.
extern "C" {
  uint8_t temprature_sens_read();  // (ejaan memang 'temprature' di SDK lama)
}
float esp32TempC() {
  // Nilai kasar dari sensor internal (bukan presisi). Untuk DEMO saja.
  float f = (temprature_sens_read() - 32) / 1.8;
  if (f < -40 || f > 125) return NAN;  // nilai tak masuk akal -> abaikan
  return f;
}

void connectWifi() {
  Serial.print("WiFi connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nWiFi OK, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi GAGAL (akan retry).");
  }
}

void connectMqtt() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqtt.connected()) {
    Serial.print("MQTT connecting... ");
    bool ok = mqtt.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS);
    if (ok) {
      Serial.println("OK");
    } else {
      Serial.print("gagal rc=");
      Serial.print(mqtt.state());
      Serial.println(" (retry 3s)");
      delay(3000);
      if (WiFi.status() != WL_CONNECTED) connectWifi();
    }
  }
}

void publishData() {
  JsonDocument doc;                        // ArduinoJson v7
  doc["id"] = NODE_ID;
  doc["provinsi"] = PROVINSI;
  doc["kabupaten"] = KABUPATEN;
  doc["kecamatan"] = KECAMATAN;
  doc["ts"] = (unsigned long)(millis() / 1000);  // detik sejak boot (sementara)
  doc["seq"] = ++seq;

  float t = esp32TempC();
  if (!isnan(t)) {
    doc["weather"]["temp"] = roundf(t * 10) / 10.0;  // suhu chip (DEMO)
  }

  doc["health"]["uptime"] = (unsigned long)(millis() / 1000);
  doc["health"]["rssi"] = WiFi.RSSI();
  doc["health"]["fw"] = "tbeam-exp-0.1";

  char topic[128];
  snprintf(topic, sizeof(topic), "yg2ufh/ews/%s/%s/data", KABUPATEN, NODE_ID);

  char payload[512];
  size_t n = serializeJson(doc, payload, sizeof(payload));

  bool ok = mqtt.publish(topic, (const uint8_t*)payload, n, false);
  Serial.print(ok ? "terkirim -> " : "GAGAL kirim -> ");
  Serial.println(topic);
  Serial.println(payload);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n=== EWS T-Beam experiment ===");
  connectWifi();
  mqtt.setBufferSize(640);  // cukup untuk payload JSON
  connectMqtt();
  publishData();            // kirim sekali di awal
  lastSend = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  if (millis() - lastSend >= INTERVAL_MS) {
    publishData();
    lastSend = millis();
  }
}
