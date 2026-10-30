#include <ArduinoJson.h>
#include <vector>
#include "configuration.h"
#include "ews_packet.h"
#include "lora.h"
#include "mqtt.h"
#include "siren.h"
#include "gateway.h"

// GATEWAY role. Receives compact LoRa packets, enriches them with the location
// metadata learned at JOIN time (kabupaten/kecamatan/kelurahan), expands them to
// fat MQTT JSON and publishes on behalf of each node. Also tracks liveness for
// node-missing detection and relays siren commands to the local siren.

extern Configuration Config;

namespace {

    // Per-node registration + liveness, keyed by node_id.
    struct NodeEntry {
        String        nodeId;
        String        kabupaten;
        String        kecamatan;
        String        kelurahan;
        String        provinsi;
        unsigned long lastSeen = 0;     // millis() of last packet
        bool          online   = false;
    };

    std::vector<NodeEntry> nodes;
    bool wasConnected = false;          // MQTT connection edge for re-subscribe

    NodeEntry* findNode(const String& id) {
        for (auto& n : nodes) {
            if (n.nodeId == id) return &n;
        }
        return nullptr;
    }

    NodeEntry* ensureNode(const String& id) {
        NodeEntry* n = findNode(id);
        if (n) return n;
        NodeEntry e;
        e.nodeId = id;
        nodes.push_back(e);
        return &nodes.back();
    }

    // Subscribe to every known node's siren/cmd topic (also used on reconnect).
    void subscribeSirenCmds() {
        for (auto& n : nodes) {
            String base = MQTT_Utils::nodeBaseTopic(n.kabupaten, n.nodeId);
            MQTT_Utils::subscribe(base + "/siren/cmd");
        }
    }

    // Build the fat MQTT JSON for a relayed node reading. Location hierarchy is
    // taken from the packet when present, else the JOIN registration; kelurahan
    // is carried through to the published JSON. Health rssi/snr/uptime/fw added.
    String expandToFatJson(const EwsPacket& p, const NodeEntry& n, int rssi, float snr) {
        JsonDocument doc;
        doc["id"] = p.nodeId;

        String prov = (p.provinsi != "")  ? p.provinsi  : n.provinsi;
        String kab  = (p.kabupaten != "") ? p.kabupaten : n.kabupaten;
        String kec  = (p.kecamatan != "") ? p.kecamatan : n.kecamatan;
        String kel  = (p.kelurahan != "") ? p.kelurahan : n.kelurahan;
        doc["provinsi"]  = prov;
        doc["kabupaten"] = kab;
        doc["kecamatan"] = kec;
        doc["kelurahan"] = kel;

        doc["ts"]  = (unsigned long)(millis() / 1000);
        doc["seq"] = p.seq;

        if (p.weather.present) {
            JsonObject w = doc["weather"].to<JsonObject>();
            w["temp"]  = p.weather.t;
            w["hum"]   = p.weather.h;
            w["press"] = p.weather.p;
        }
        if (p.power.present) {
            JsonObject pw = doc["power"].to<JsonObject>();
            pw["batt_v"] = p.power.bv;
            pw["pv_v"]   = p.power.pv;
            pw["soc"]    = p.power.soc;
        }
        if (p.tilt.present) {
            JsonObject ti = doc["tilt"].to<JsonObject>();
            ti["x"]     = p.tilt.x;
            ti["y"]     = p.tilt.y;
            ti["delta"] = p.tilt.dl;
        }
        if (p.rain.present) {
            doc["rain"]["mm"] = p.rain.mm;
        }
        if (p.gps.present) {
            JsonObject g = doc["gps"].to<JsonObject>();
            g["lat"] = p.gps.la;
            g["lon"] = p.gps.lo;
            g["fix"] = p.gps.fx ? true : false;
        }

        JsonObject h = doc["health"].to<JsonObject>();
        h["rssi"]   = rssi;
        h["snr"]    = snr;
        h["uptime"] = (unsigned long)(millis() / 1000);
        h["fw"]     = EWS_FW_VERSION;

        String out;
        serializeJson(doc, out);
        return out;
    }

    // Publish status (online/offline, retained) for a node.
    void publishNodeStatus(const NodeEntry& n, const char* status) {
        String base = MQTT_Utils::nodeBaseTopic(n.kabupaten, n.nodeId);
        MQTT_Utils::publishTo(base + "/status", status, true);
    }

    void handleJoin(const EwsPacket& p) {
        NodeEntry* n = ensureNode(p.nodeId);
        n->kabupaten = p.kabupaten;
        n->kecamatan = p.kecamatan;
        n->kelurahan = p.kelurahan;
        n->provinsi  = p.provinsi;
        n->lastSeen  = millis();
        if (!n->online) {
            n->online = true;
            publishNodeStatus(*n, "online");
        }
        // Start listening for this node's siren commands.
        String base = MQTT_Utils::nodeBaseTopic(n->kabupaten, n->nodeId);
        MQTT_Utils::subscribe(base + "/siren/cmd");
        Serial.print("Gateway: node joined ");
        Serial.println(p.nodeId);
    }

    void handleData(const EwsPacket& p, int rssi, float snr) {
        NodeEntry* n = ensureNode(p.nodeId);
        // Fill/refresh metadata from the DATA packet when it carries slugs.
        if (p.kabupaten != "") n->kabupaten = p.kabupaten;
        if (p.kecamatan != "") n->kecamatan = p.kecamatan;
        if (p.kelurahan != "") n->kelurahan = p.kelurahan;
        n->lastSeen = millis();
        if (!n->online) {
            n->online = true;
            publishNodeStatus(*n, "online");
        }

        String json = expandToFatJson(p, *n, rssi, snr);
        String base = MQTT_Utils::nodeBaseTopic(n->kabupaten, n->nodeId);
        MQTT_Utils::publishTo(base + "/data", json, false);
    }

    // Node-missing detection: flip to offline when silent past the threshold.
    void checkMissing() {
        unsigned long now = millis();
        unsigned long thresholdMs =
            (unsigned long)Config.siren.missThresholdSec * 1000UL;
        for (auto& n : nodes) {
            if (n.online && (now - n.lastSeen) > thresholdMs) {
                n.online = false;
                publishNodeStatus(n, "offline");
                Serial.print("Gateway: node missing ");
                Serial.println(n.nodeId);
            }
        }
    }

    // Raw MQTT hook: act on any node's siren/cmd topic.
    void onRaw(const String& topic, const String& payload) {
        if (topic.endsWith("/siren/cmd")) {
            Siren_Utils::handleCmd(payload);
            // Reflect the resulting state back to the broker.
            const char* state = Siren_Utils::isSirenOn() ? "on" : "off";
            String stateTopic = topic.substring(0, topic.length() -
                                                 strlen("/cmd")) + "/state";
            MQTT_Utils::publishTo(stateTopic, state, true);
        }
    }
}

namespace Gateway {

    void setup() {
        MQTT_Utils::onRawMessage(onRaw);
        Siren_Utils::setup();
    }

    void loop() {
        MQTT_Utils::loop();

        // On a fresh MQTT connection, (re)subscribe to known node siren topics.
        bool connected = MQTT_Utils::isConnected();
        if (connected && !wasConnected) {
            subscribeSirenCmds();
        }
        wasConnected = connected;

        // Service inbound LoRa packets.
        LoRaRx rx = LoRa_Utils::receive();
        if (rx.valid) {
            EwsPacket p;
            if (EwsPacketCodec::parse(rx.payload, p)) {
                if (p.msgType == "DATA") {
                    handleData(p, rx.rssi, rx.snr);
                } else if (p.msgType == "JOIN") {
                    handleJoin(p);
                }
            }
        }

        checkMissing();
    }
}
