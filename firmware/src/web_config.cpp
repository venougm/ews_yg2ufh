#include <WiFi.h>
#include <WebServer.h>
#include <SPIFFS.h>
#include <ArduinoJson.h>
#include "configuration.h"
#include "web_config.h"

// AP-mode web configuration server. One WebServer on port 80. Static web assets
// (index.html / style.css / script.js / wilayah.json) are served straight from
// SPIFFS; the browser JS loads GET /api/config + GET /api/wilayah to render the
// form, then POSTs the edited config back to /api/config which saves it via
// Config.writeFile() and reboots the device into WiFi client mode.
//
// JSON keys here MUST match src/configuration.cpp (writeFile/readFile) so a saved
// config round-trips through the needsRewrite migration unchanged.

extern Configuration Config;

namespace {
    WebServer server(80);

    // --- static assets --------------------------------------------------------

    // Stream a SPIFFS file with an explicit content type. Returns false (and
    // leaves the response untouched) when the file is missing.
    bool serveFile(const char* path, const char* contentType) {
        if (!SPIFFS.exists(path)) return false;
        File f = SPIFFS.open(path, "r");
        if (!f) return false;
        server.streamFile(f, contentType);
        f.close();
        return true;
    }

    void handleRoot() {
        if (!serveFile("/index.html", "text/html")) {
            server.send(200, "text/html",
                "<h1>EWS Setup</h1><p>index.html belum di-upload ke SPIFFS. "
                "Jalankan: <code>pio run -t uploadfs</code>.</p>");
        }
    }

    void handleStyle()  { if (!serveFile("/style.css", "text/css"))        server.send(404, "text/plain", "not found"); }
    void handleScript() { if (!serveFile("/script.js", "application/javascript")) server.send(404, "text/plain", "not found"); }

    // Serve the wilayah tree verbatim from SPIFFS (it is already the exact shape
    // the dropdowns expect).
    void handleWilayah() {
        if (!serveFile("/wilayah.json", "application/json")) {
            server.send(200, "application/json", "{}");
        }
    }

    // --- GET /api/config ------------------------------------------------------

    // Serialize the live Configuration into the same JSON shape writeFile() uses,
    // so the form shows exactly what is (or will be) stored. Passwords are
    // returned as-is; the AP is local-only during setup.
    void handleGetConfig() {
        JsonDocument data;

        data["identity"]["role"]            = Config.identity.role;
        data["identity"]["nodeId"]          = Config.identity.nodeId;
        data["identity"]["networkId"]       = Config.identity.networkId;
        data["identity"]["provinsi"]        = Config.identity.provinsi;
        data["identity"]["kabupaten"]       = Config.identity.kabupaten;
        data["identity"]["kecamatan"]       = Config.identity.kecamatan;
        data["identity"]["kelurahan"]       = Config.identity.kelurahan;
        data["identity"]["locationName"]    = Config.identity.locationName;
        data["identity"]["latitude"]        = Config.identity.latitude;
        data["identity"]["longitude"]       = Config.identity.longitude;

        // Expose the first (primary) configured AP, if any.
        String ssid = "", pass = "";
        for (size_t i = 0; i < Config.wifiAPs.size(); i++) {
            if (Config.wifiAPs[i].ssid != "") { ssid = Config.wifiAPs[i].ssid; pass = Config.wifiAPs[i].password; break; }
        }
        data["wifi"]["ssid"]                = ssid;
        data["wifi"]["password"]            = pass;
        data["wifi"]["autoAP"]["enabled"]   = Config.wifiAutoAP.enabled;
        data["wifi"]["autoAP"]["apPassword"]= Config.wifiAutoAP.apPassword;
        data["wifi"]["autoAP"]["timeout"]   = Config.wifiAutoAP.timeout;

        data["lora"]["freq"]                = Config.lora.freq;
        data["lora"]["sf"]                  = Config.lora.sf;
        data["lora"]["cr"]                  = Config.lora.cr;
        data["lora"]["bw"]                  = Config.lora.bw;
        data["lora"]["power"]               = Config.lora.power;
        data["lora"]["syncWord"]            = Config.lora.syncWord;
        data["lora"]["cadActive"]           = Config.lora.cadActive;

        data["mqtt"]["active"]              = Config.mqtt.active;
        data["mqtt"]["server"]              = Config.mqtt.server;
        data["mqtt"]["port"]                = Config.mqtt.port;
        data["mqtt"]["username"]            = Config.mqtt.username;
        data["mqtt"]["password"]            = Config.mqtt.password;
        data["mqtt"]["clientId"]            = Config.mqtt.clientId;

        data["sensors"]["bme280"]           = Config.sensors.bme280;
        data["sensors"]["mq135"]            = Config.sensors.mq135;
        data["sensors"]["rain"]             = Config.sensors.rain;
        data["sensors"]["anemo"]            = Config.sensors.anemo;
        data["sensors"]["tilt"]             = Config.sensors.tilt;
        data["sensors"]["ads1115"]          = Config.sensors.ads1115;
        data["sensors"]["epever"]           = Config.sensors.epever;
        data["sensors"]["gps"]              = Config.sensors.gps;
        data["sensors"]["intervalSec"]      = Config.sensors.intervalSec;

        data["siren"]["enabled"]            = Config.siren.enabled;
        data["siren"]["missThresholdSec"]   = Config.siren.missThresholdSec;

        data["thresholds"]["tiltSiaga"]     = Config.thresholds.tiltSiaga;
        data["thresholds"]["tiltAwas"]      = Config.thresholds.tiltAwas;

        data["display"]["enabled"]          = Config.display.enabled;
        data["display"]["timeout"]          = Config.display.timeout;
        data["display"]["turn180"]          = Config.display.turn180;

        data["fw"] = EWS_FW_VERSION;

        String out;
        serializeJson(data, out);
        server.send(200, "application/json", out);
    }

    // --- POST /api/config -----------------------------------------------------

    // Flagged true from handlePostConfig so loop() can reboot AFTER the HTTP
    // response has been flushed to the browser.
    bool rebootPending = false;
    unsigned long rebootAt = 0;

    // Apply only the fields present in the posted JSON; fall back to the current
    // value otherwise so a partial form never wipes settings. Returns an error
    // string (empty on success).
    String applyConfig(JsonDocument& data) {
        // --- validate the few fields that must not be empty/garbage ---
        String nodeId    = data["identity"]["nodeId"]    | Config.identity.nodeId;
        String kabupaten = data["identity"]["kabupaten"] | Config.identity.kabupaten;
        int    role      = data["identity"]["role"]      | Config.identity.role;

        if (nodeId == "")    return "node_id wajib diisi";
        if (kabupaten == "") return "Kabupaten/Kota wajib dipilih (masuk ke topic MQTT)";
        if (role != 0 && role != 1) return "Peran tidak valid";

        Config.identity.role         = role;
        Config.identity.nodeId       = nodeId;
        Config.identity.networkId    = data["identity"]["networkId"]    | Config.identity.networkId;
        Config.identity.provinsi     = data["identity"]["provinsi"]     | Config.identity.provinsi;
        Config.identity.kabupaten    = kabupaten;
        Config.identity.kecamatan    = data["identity"]["kecamatan"]    | Config.identity.kecamatan;
        Config.identity.kelurahan    = data["identity"]["kelurahan"]    | Config.identity.kelurahan;
        Config.identity.locationName = data["identity"]["locationName"] | Config.identity.locationName;
        Config.identity.latitude     = data["identity"]["latitude"]     | Config.identity.latitude;
        Config.identity.longitude    = data["identity"]["longitude"]    | Config.identity.longitude;

        // WiFi: the form carries a single primary AP; store it as wifiAPs[0].
        if (!data["wifi"]["ssid"].isNull()) {
            String ssid = data["wifi"]["ssid"] | "";
            String pass = data["wifi"]["password"] | "";
            Config.wifiAPs.clear();
            WiFi_AP ap;
            ap.ssid = ssid;
            ap.password = pass;
            Config.wifiAPs.push_back(ap);
        }
        Config.wifiAutoAP.enabled    = data["wifi"]["autoAP"]["enabled"]    | Config.wifiAutoAP.enabled;
        Config.wifiAutoAP.apPassword = data["wifi"]["autoAP"]["apPassword"] | Config.wifiAutoAP.apPassword;
        Config.wifiAutoAP.timeout    = data["wifi"]["autoAP"]["timeout"]    | Config.wifiAutoAP.timeout;

        Config.lora.freq       = data["lora"]["freq"]      | Config.lora.freq;
        Config.lora.sf         = data["lora"]["sf"]        | Config.lora.sf;
        Config.lora.cr         = data["lora"]["cr"]        | Config.lora.cr;
        Config.lora.bw         = data["lora"]["bw"]        | Config.lora.bw;
        Config.lora.power      = data["lora"]["power"]     | Config.lora.power;
        Config.lora.syncWord   = data["lora"]["syncWord"]  | Config.lora.syncWord;
        Config.lora.cadActive  = data["lora"]["cadActive"] | Config.lora.cadActive;

        Config.mqtt.active     = data["mqtt"]["active"]    | Config.mqtt.active;
        Config.mqtt.server     = data["mqtt"]["server"]    | Config.mqtt.server;
        Config.mqtt.port       = data["mqtt"]["port"]      | Config.mqtt.port;
        Config.mqtt.username   = data["mqtt"]["username"]  | Config.mqtt.username;
        Config.mqtt.password   = data["mqtt"]["password"]  | Config.mqtt.password;
        Config.mqtt.clientId   = data["mqtt"]["clientId"]  | Config.mqtt.clientId;

        Config.sensors.bme280      = data["sensors"]["bme280"]      | Config.sensors.bme280;
        Config.sensors.mq135       = data["sensors"]["mq135"]       | Config.sensors.mq135;
        Config.sensors.rain        = data["sensors"]["rain"]        | Config.sensors.rain;
        Config.sensors.anemo       = data["sensors"]["anemo"]       | Config.sensors.anemo;
        Config.sensors.tilt        = data["sensors"]["tilt"]        | Config.sensors.tilt;
        Config.sensors.ads1115     = data["sensors"]["ads1115"]     | Config.sensors.ads1115;
        Config.sensors.epever      = data["sensors"]["epever"]      | Config.sensors.epever;
        Config.sensors.gps         = data["sensors"]["gps"]         | Config.sensors.gps;
        Config.sensors.intervalSec = data["sensors"]["intervalSec"] | Config.sensors.intervalSec;

        Config.siren.enabled          = data["siren"]["enabled"]          | Config.siren.enabled;
        Config.siren.missThresholdSec = data["siren"]["missThresholdSec"] | Config.siren.missThresholdSec;

        Config.thresholds.tiltSiaga = data["thresholds"]["tiltSiaga"] | Config.thresholds.tiltSiaga;
        Config.thresholds.tiltAwas  = data["thresholds"]["tiltAwas"]  | Config.thresholds.tiltAwas;

        Config.display.enabled = data["display"]["enabled"] | Config.display.enabled;
        Config.display.timeout = data["display"]["timeout"] | Config.display.timeout;
        Config.display.turn180 = data["display"]["turn180"] | Config.display.turn180;

        return "";
    }

    void handlePostConfig() {
        if (!server.hasArg("plain")) {
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"body kosong\"}");
            return;
        }

        JsonDocument data;
        DeserializationError err = deserializeJson(data, server.arg("plain"));
        if (err) {
            server.send(400, "application/json", "{\"ok\":false,\"error\":\"JSON tidak valid\"}");
            return;
        }

        String validationError = applyConfig(data);
        if (validationError != "") {
            JsonDocument resp;
            resp["ok"] = false;
            resp["error"] = validationError;
            String out;
            serializeJson(resp, out);
            server.send(400, "application/json", out);
            return;
        }

        if (!Config.writeFile()) {
            server.send(500, "application/json", "{\"ok\":false,\"error\":\"gagal menyimpan ke SPIFFS\"}");
            return;
        }

        server.send(200, "application/json",
            "{\"ok\":true,\"message\":\"Config tersimpan, perangkat reboot ke mode client\"}");

        // Reboot shortly after so the response reaches the browser first.
        rebootPending = true;
        rebootAt = millis() + 1200;
    }

    void handleNotFound() {
        // Help captive-portal style clients find the form.
        server.sendHeader("Location", "/", true);
        server.send(302, "text/plain", "");
    }
}

namespace WebConfig {

    void setup() {
        server.on("/",             HTTP_GET,  handleRoot);
        server.on("/index.html",   HTTP_GET,  handleRoot);
        server.on("/style.css",    HTTP_GET,  handleStyle);
        server.on("/script.js",    HTTP_GET,  handleScript);
        server.on("/wilayah.json", HTTP_GET,  handleWilayah);
        server.on("/api/config",   HTTP_GET,  handleGetConfig);
        server.on("/api/wilayah",  HTTP_GET,  handleWilayah);
        server.on("/api/config",   HTTP_POST, handlePostConfig);
        server.onNotFound(handleNotFound);

        server.begin();
        Serial.println("Web config server started on http://192.168.4.1");
    }

    void loop() {
        server.handleClient();

        if (rebootPending && (long)(millis() - rebootAt) >= 0) {
            Serial.println("Config saved, rebooting to client mode...");
            delay(100);
            ESP.restart();
        }
    }

}
