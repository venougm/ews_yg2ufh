#ifndef EWS_PACKET_H
#define EWS_PACKET_H

#include <Arduino.h>

// ===========================================================================
// EWS LoRa compact packet codec (FEAT-002)
// ===========================================================================
//
// Over-air packets are COMPACT minimal-JSON (NOT the fat MQTT JSON). One line,
// small, human-debuggable. No APRS prefix, no aprslib. The gateway expands the
// short keys back into the fat MQTT JSON.
//
// TODO: can become a packed-binary codec later.
//
// Header fields (always present on every packet):
//   n  network_id   (e.g. "ews1")
//   d  node_id      (e.g. "slm-01")
//   s  seq          (uint32)
//   t  msg_type     "DATA" | "JOIN" | "ACK" | "CMD"
//
// Location slugs carried so the gateway can fill MQTT metadata. DATA and JOIN
// both carry kab (kabupaten), kec (kecamatan) AND kel (kelurahan). The kelurahan
// slug is payload metadata only; it is NOT part of the MQTT topic.
//
// ---------------------------------------------------------------------------
// DATA  (node -> gateway): only enabled sensor groups, short keys
//   {"n":"ews1","d":"slm-01","s":1234,"t":"DATA",
//    "kab":"sleman","kec":"depok","kel":"caturtunggal",
//    "w":{"t":27.4,"h":82.1,"p":1008.3},
//    "pw":{"bv":12.8,"pv":18.2,"soc":87},
//    "ti":{"x":5.2,"y":1.1,"dl":0.3},
//    "r":{"mm":0.0},
//    "g":{"la":-7.72,"lo":110.38,"fx":1}}
//
//   Group short keys -> MQTT-JSON mapping (done by the gateway):
//     w  -> weather { t->temp, h->hum, p->press }
//     pw -> power   { bv->batt_v, pv->pv_v, soc }
//     ti -> tilt    { x, y, dl->delta }
//     r  -> rain    { mm }
//     g  -> gps     { la->lat, lo->lon, fx->fix }
//
// JOIN  (node registers): identity + active sensor list so the gateway can fill
//        metadata from a registration table.
//   {"n":"ews1","d":"slm-01","s":1,"t":"JOIN",
//    "kab":"sleman","kec":"depok","kel":"caturtunggal",
//    "prov":"diy","sen":["w","pw","ti","r","g"]}
//
// ACK   (gateway -> node): acknowledges a seq
//   {"n":"ews1","d":"slm-gw-01","s":1234,"t":"ACK"}
//
// CMD   (gateway -> node): e.g. set send interval
//   {"n":"ews1","d":"slm-01","s":0,"t":"CMD","cmd":"interval","val":60}
// ===========================================================================

// One optional-group flag + its values. `present` gates serialization/parsing.
struct EwsWeather { bool present = false; float t = 0, h = 0, p = 0; };
struct EwsPower   { bool present = false; float bv = 0, pv = 0; int soc = 0; };
struct EwsTilt    { bool present = false; float x = 0, y = 0, dl = 0; };
struct EwsRain    { bool present = false; float mm = 0; };
struct EwsGps     { bool present = false; double la = 0, lo = 0; int fx = 0; };

// Decoded / to-be-encoded compact packet.
struct EwsPacket {
    // header
    String   networkId;
    String   nodeId;
    uint32_t seq = 0;
    String   msgType;           // "DATA" | "JOIN" | "ACK" | "CMD"

    // location slugs (DATA + JOIN)
    String   kabupaten;         // kab
    String   kecamatan;         // kec
    String   kelurahan;         // kel

    // JOIN extras
    String   provinsi;          // prov
    String   sensors[8];        // sen[]
    uint8_t  sensorCount = 0;

    // CMD extras
    String   cmd;
    long     val = 0;

    // DATA sensor groups
    EwsWeather weather;
    EwsPower   power;
    EwsTilt    tilt;
    EwsRain    rain;
    EwsGps     gps;
};

namespace EwsPacketCodec {
    // Serialize compact single-line JSON. Each returns the payload String.
    String buildData(const EwsPacket& p);
    String buildJoin(const EwsPacket& p);
    String buildAck(const EwsPacket& p);
    String buildCmd(const EwsPacket& p);

    // Deserialize a received compact payload into out. Returns false on parse
    // error or missing header fields.
    bool parse(const String& payload, EwsPacket& out);
}

#endif // EWS_PACKET_H
