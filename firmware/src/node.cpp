#include <WiFi.h>
#include <ArduinoJson.h>
#include "configuration.h"
#include "sensors.h"
#include "ews_packet.h"
#include "lora.h"
#include "mqtt.h"
#include "siren.h"
#include "wifi_manager.h"
#include "node.h"

// NODE role. Reads enabled sensors on the interval and sends the result over
// MQTT (when WiFi+MQTT are up) as fat JSON, else over LoRa as a compact DATA
// packet. The fat JSON mirrors the experiment sketch field mapping
// (firmware-experiment/ews_tbeam_min/ews_tbeam_min.ino) and the EWS payload
// schema, and carries the full location hierarchy INCLUDING kelurahan.

extern Configuration Config;

namespace {

    unsigned long lastSend = 0;
    uint32_t      seq      = 0;

    // Build the compact on-air DATA packet from a reading, enabling only the
    // sensor groups that are present.
    void fillCompact(EwsPacket& p, const SensorReading& r) {
        p.networkId = Config.identity.networkId;
        p.nodeId    = Config.identity.nodeId;
        p.seq       = seq;
        p.msgType   = "DATA";
        p.kabupaten = Config.identity.kabupaten;
        p.kecamatan = Config.identity.kecamatan;
        p.kelurahan = Config.identity.kelurahan;

        if (r.weatherPresent) {
            p.weather.present = true;
            p.weather.t = r.temp;
            p.weather.h = r.hum;
            p.weather.p = r.press;
        }
        if (r.powerPresent) {
            p.power.present = true;
            p.power.bv  = r.battV;
            p.power.pv  = r.pvV;
            p.power.soc = r.soc;
        }
        if (r.gpsPresent) {
            p.gps.present = true;
            p.gps.la = r.lat;
            p.gps.lo = r.lon;
            p.gps.fx = r.gpsFix ? 1 : 0;
        }
        if (r.rainPresent) {
            p.rain.present = true;
            p.rain.mm = r.rainMm;
        }
    }

    // Build the fat MQTT JSON from a reading. Only enabled groups are included
    // (field-optional schema). Location hierarchy always carries provinsi,
    // kabupaten, kecamatan AND kelurahan as metadata.
    String buildFatJson(const SensorReading& r) {
        JsonDocument doc;
        doc["id"]        = Config.identity.nodeId;
        doc["provinsi"]  = Config.identity.provinsi;
        doc["kabupaten"] = Config.identity.kabupaten;
        doc["kecamatan"] = Config.identity.kecamatan;
        doc["kelurahan"] = Config.identity.kelurahan;
        doc["ts"]        = (unsigned long)(millis() / 1000);
        doc["seq"]       = seq;

        if (r.weatherPresent) {
            JsonObject w = doc["weather"].to<JsonObject>();
            w["temp"]  = r.temp;
            w["hum"]   = r.hum;
            w["press"] = r.press;
        }
        if (r.windPresent) {
            // Wind rides in the weather group when there's no BME280 block yet.
            doc["weather"]["wind"] = r.windHz;
        }
        if (r.powerPresent) {
            JsonObject pw = doc["power"].to<JsonObject>();
            pw["batt_v"] = r.battV;
            pw["pv_v"]   = r.pvV;
            pw["load_a"] = r.loadA;
            pw["soc"]    = r.soc;
        }
        if (r.airPresent) {
            doc["air"]["raw"] = r.airRaw;
        }
        if (r.rainPresent) {
            doc["rain"]["mm"] = r.rainMm;
        }
        if (r.gpsPresent) {
            JsonObject g = doc["gps"].to<JsonObject>();
            g["lat"] = r.lat;
            g["lon"] = r.lon;
            g["fix"] = r.gpsFix;
        }

        JsonObject h = doc["health"].to<JsonObject>();
        h["uptime"] = (unsigned long)(millis() / 1000);
        h["rssi"]   = WiFiManager::isConnected() ? WiFi.RSSI() : 0;
        h["fw"]     = EWS_FW_VERSION;

        String out;
        serializeJson(doc, out);
        return out;
    }

    // Build + LoRa-transmit the JOIN packet so the gateway can register us.
    void sendJoin() {
        EwsPacket p;
        p.networkId = Config.identity.networkId;
        p.nodeId    = Config.identity.nodeId;
        p.seq       = ++seq;
        p.msgType   = "JOIN";
        p.kabupaten = Config.identity.kabupaten;
        p.kecamatan = Config.identity.kecamatan;
        p.kelurahan = Config.identity.kelurahan;
        p.provinsi  = Config.identity.provinsi;

        // Active sensor short-key list (mirrors the compact group keys).
        if (Config.sensors.bme280 || Config.sensors.anemo) p.sensors[p.sensorCount++] = "w";
        if (Config.sensors.ads1115 || Config.sensors.epever) p.sensors[p.sensorCount++] = "pw";
        if (Config.sensors.tilt) p.sensors[p.sensorCount++] = "ti";
        if (Config.sensors.rain) p.sensors[p.sensorCount++] = "r";
        if (Config.sensors.gps)  p.sensors[p.sensorCount++] = "g";

        LoRa_Utils::transmit(EwsPacketCodec::buildJoin(p));
    }

    void sendReading() {
        SensorReading r = Sensors_Utils::readEnabled();

        // Prefer the direct MQTT path when the network is available.
        if (WiFiManager::isConnected() && MQTT_Utils::isConnected()) {
            MQTT_Utils::publishData(buildFatJson(r));
            return;
        }

        // Fallback: compact DATA packet over LoRa to the gateway.
        EwsPacket p;
        fillCompact(p, r);
        LoRa_Utils::transmit(EwsPacketCodec::buildData(p));
    }
}

namespace Node {

    void setup() {
        Sensors_Utils::setup();
        Siren_Utils::setup();
        // Siren on a node is MANUAL-ONLY, driven solely by inbound MQTT siren/cmd.
        MQTT_Utils::onSirenCmd([](const String& payload) {
            Siren_Utils::handleCmd(payload);
            MQTT_Utils::publishSirenState(Siren_Utils::isSirenOn() ? "on" : "off");
        });
        sendJoin();
        // Send the first reading immediately on the next loop pass.
        lastSend = millis() - (unsigned long)Config.sensors.intervalSec * 1000UL;
    }

    void loop() {
        Sensors_Utils::loop();
        MQTT_Utils::loop();

        unsigned long intervalMs = (unsigned long)Config.sensors.intervalSec * 1000UL;
        if (millis() - lastSend >= intervalMs) {
            seq++;
            sendReading();
            lastSend = millis();
        }
    }
}
