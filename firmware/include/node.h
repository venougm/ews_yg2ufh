#ifndef NODE_H
#define NODE_H

#include <Arduino.h>
#include "sensors.h"   // SensorReading, surfaced to the display via Node::status()

// NODE role (FEAT-003). Every Config.sensors.intervalSec seconds the node reads
// its enabled sensors and ships the data by the best available path:
//   - WiFi + MQTT up  -> publish the FAT JSON directly to the broker
//   - otherwise        -> build a COMPACT DATA packet and LoRa-transmit to the
//                         gateway, which expands + publishes it
// A JOIN packet is sent once on boot so the gateway can register the node and
// learn its location metadata + active sensor list.
// Snapshot of the node's send state for the OLED display (additive, read-only).
struct NodeStatus {
    uint32_t      seq;          // last send sequence number
    int           secsToNext;   // seconds until the next scheduled send
    bool          viaWifi;      // true when WiFi+MQTT path is up (else LoRa)
    SensorReading reading;      // latest reading captured at the last send
};

namespace Node {
    void setup();   // init sensors, send JOIN, prime the send timer
    void loop();    // feed sensors + send on the interval
    NodeStatus status();        // display data source (read-only snapshot)
}

#endif // NODE_H
