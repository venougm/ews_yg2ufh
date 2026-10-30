#include <ArduinoJson.h>
#include "ews_packet.h"

// Compact minimal-JSON LoRa packet encode/decode. See include/ews_packet.h for
// the full on-air format spec. ArduinoJson v7 JsonDocument throughout.

namespace {

    // Write the always-present header (n/d/s/t) into a doc.
    void writeHeader(JsonDocument& doc, const EwsPacket& p) {
        doc["n"] = p.networkId;
        doc["d"] = p.nodeId;
        doc["s"] = p.seq;
        doc["t"] = p.msgType;
    }

    // Write kab/kec/kel location slugs (DATA + JOIN carry all three).
    void writeLocation(JsonDocument& doc, const EwsPacket& p) {
        doc["kab"] = p.kabupaten;
        doc["kec"] = p.kecamatan;
        doc["kel"] = p.kelurahan;
    }

}

namespace EwsPacketCodec {

    String buildData(const EwsPacket& p) {
        JsonDocument doc;
        writeHeader(doc, p);
        writeLocation(doc, p);

        if (p.weather.present) {
            JsonObject w = doc["w"].to<JsonObject>();
            w["t"] = p.weather.t;
            w["h"] = p.weather.h;
            w["p"] = p.weather.p;
        }
        if (p.power.present) {
            JsonObject pw = doc["pw"].to<JsonObject>();
            pw["bv"]  = p.power.bv;
            pw["pv"]  = p.power.pv;
            pw["soc"] = p.power.soc;
        }
        if (p.tilt.present) {
            JsonObject ti = doc["ti"].to<JsonObject>();
            ti["x"]  = p.tilt.x;
            ti["y"]  = p.tilt.y;
            ti["dl"] = p.tilt.dl;
        }
        if (p.rain.present) {
            JsonObject r = doc["r"].to<JsonObject>();
            r["mm"] = p.rain.mm;
        }
        if (p.gps.present) {
            JsonObject g = doc["g"].to<JsonObject>();
            g["la"] = p.gps.la;
            g["lo"] = p.gps.lo;
            g["fx"] = p.gps.fx;
        }

        String out;
        serializeJson(doc, out);
        return out;
    }

    String buildJoin(const EwsPacket& p) {
        JsonDocument doc;
        writeHeader(doc, p);
        writeLocation(doc, p);
        doc["prov"] = p.provinsi;

        JsonArray sen = doc["sen"].to<JsonArray>();
        for (uint8_t i = 0; i < p.sensorCount && i < 8; i++) {
            sen.add(p.sensors[i]);
        }

        String out;
        serializeJson(doc, out);
        return out;
    }

    String buildAck(const EwsPacket& p) {
        JsonDocument doc;
        writeHeader(doc, p);

        String out;
        serializeJson(doc, out);
        return out;
    }

    String buildCmd(const EwsPacket& p) {
        JsonDocument doc;
        writeHeader(doc, p);
        doc["cmd"] = p.cmd;
        doc["val"] = p.val;

        String out;
        serializeJson(doc, out);
        return out;
    }

    bool parse(const String& payload, EwsPacket& out) {
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, payload);
        if (err) return false;

        // Header is mandatory.
        if (doc["n"].isNull() || doc["d"].isNull() ||
            doc["s"].isNull() || doc["t"].isNull()) {
            return false;
        }

        out.networkId = doc["n"].as<String>();
        out.nodeId    = doc["d"].as<String>();
        out.seq       = doc["s"].as<uint32_t>();
        out.msgType   = doc["t"].as<String>();

        // Location slugs (present on DATA + JOIN; harmless defaults otherwise).
        out.kabupaten = doc["kab"] | "";
        out.kecamatan = doc["kec"] | "";
        out.kelurahan = doc["kel"] | "";

        // JOIN extras.
        out.provinsi = doc["prov"] | "";
        out.sensorCount = 0;
        if (!doc["sen"].isNull()) {
            JsonArray sen = doc["sen"].as<JsonArray>();
            for (JsonVariant v : sen) {
                if (out.sensorCount >= 8) break;
                out.sensors[out.sensorCount++] = v.as<String>();
            }
        }

        // CMD extras.
        out.cmd = doc["cmd"] | "";
        out.val = doc["val"] | 0L;

        // DATA sensor groups.
        if (!doc["w"].isNull()) {
            out.weather.present = true;
            out.weather.t = doc["w"]["t"] | 0.0f;
            out.weather.h = doc["w"]["h"] | 0.0f;
            out.weather.p = doc["w"]["p"] | 0.0f;
        }
        if (!doc["pw"].isNull()) {
            out.power.present = true;
            out.power.bv  = doc["pw"]["bv"]  | 0.0f;
            out.power.pv  = doc["pw"]["pv"]  | 0.0f;
            out.power.soc = doc["pw"]["soc"] | 0;
        }
        if (!doc["ti"].isNull()) {
            out.tilt.present = true;
            out.tilt.x  = doc["ti"]["x"]  | 0.0f;
            out.tilt.y  = doc["ti"]["y"]  | 0.0f;
            out.tilt.dl = doc["ti"]["dl"] | 0.0f;
        }
        if (!doc["r"].isNull()) {
            out.rain.present = true;
            out.rain.mm = doc["r"]["mm"] | 0.0f;
        }
        if (!doc["g"].isNull()) {
            out.gps.present = true;
            out.gps.la = doc["g"]["la"] | 0.0;
            out.gps.lo = doc["g"]["lo"] | 0.0;
            out.gps.fx = doc["g"]["fx"] | 0;
        }

        return true;
    }

}
