#ifndef NODE_H
#define NODE_H

#include <Arduino.h>

// NODE role (FEAT-003). Every Config.sensors.intervalSec seconds the node reads
// its enabled sensors and ships the data by the best available path:
//   - WiFi + MQTT up  -> publish the FAT JSON directly to the broker
//   - otherwise        -> build a COMPACT DATA packet and LoRa-transmit to the
//                         gateway, which expands + publishes it
// A JOIN packet is sent once on boot so the gateway can register the node and
// learn its location metadata + active sensor list.
namespace Node {
    void setup();   // init sensors, send JOIN, prime the send timer
    void loop();    // feed sensors + send on the interval
}

#endif // NODE_H
