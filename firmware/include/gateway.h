#ifndef GATEWAY_H
#define GATEWAY_H

#include <Arduino.h>

// GATEWAY role (FEAT-003). Listens on LoRa and bridges the mesh to MQTT:
//   - DATA  -> expand the compact packet into fat MQTT JSON (filling kabupaten/
//              kecamatan/kelurahan from the packet, falling back to the node's
//              JOIN registration) and publish to the node's data topic.
//   - JOIN  -> register the node (id, location hierarchy incl. kelurahan,
//              active sensor list) so later DATA packets can be enriched.
//   - node-missing detection: last_seen[node] older than missThresholdSec ->
//              publish status "offline"; publish "online" when heard again.
//   - siren/cmd: subscribe to node siren topics and forward the command to the
//              local siren (handleCmd) + publish siren/state.
// Health fields (rssi/snr/uptime/fw) are attached to each relayed reading.
// Snapshot of gateway state for the OLED display (additive, read-only).
struct GatewayStatus {
    int      nodeCount;     // number of registered nodes
    uint32_t rxTotal;       // LoRa_Utils::rxCount()
    uint32_t txTotal;       // LoRa_Utils::txCount()
    String   lastNodeId;    // id of the most recently heard node ("" if none)
    uint32_t lastAgeSec;    // seconds since that node was last heard
    bool     sirenOn;       // Siren_Utils::isSirenOn() (READ ONLY)
};

namespace Gateway {
    void setup();   // register MQTT callbacks, subscribe to siren/cmd
    void loop();    // service LoRa RX, MQTT, and node-missing detection
    GatewayStatus status();     // display data source (read-only snapshot)
}

#endif // GATEWAY_H
