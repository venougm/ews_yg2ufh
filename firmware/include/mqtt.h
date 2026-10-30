#ifndef MQTT_H
#define MQTT_H

#include <Arduino.h>

// Native-JSON MQTT client (PubSubClient over WiFiClient). No APRS, no aprslib.
//
// Topic scheme (base built from the kabupaten SLUG + node_id; the kelurahan slug
// is NOT in the topic, it travels only inside the JSON payload):
//
//   yg2ufh/ews/<kabupaten>/<nodeId>/data         node telemetry (retained=false)
//   yg2ufh/ews/<kabupaten>/<nodeId>/status        online/offline (retained)
//   yg2ufh/ews/<kabupaten>/<nodeId>/siren/state    siren state     (retained)
//   yg2ufh/ews/<kabupaten>/<nodeId>/siren/cmd      siren command   (subscribed)
//
// The status topic also carries the Last Will of "offline" (retained), so a
// dropped connection is seen by the broker as offline without an explicit publish.

namespace MQTT_Utils {
    // Callback signature for an inbound siren command payload.
    typedef void (*SirenCmdCallback)(const String& payload);

    void setup();                                   // bind WiFiClient, buffer size, server, callback
    bool connect();                                 // connect with clientId (+LWT); true if connected
    void loop();                                    // PubSubClient keepalive + inbound dispatch
    bool isConnected();

    void publishData(const String& json);           // -> .../data  (retained=false)
    void publishStatus(const char* status);         // -> .../status (retained)
    void publishSirenState(const char* state);      // -> .../siren/state (retained)

    void onSirenCmd(SirenCmdCallback cb);            // register inbound siren/cmd handler

    String baseTopic();                              // yg2ufh/ews/<kabupaten>/<nodeId>
}

#endif // MQTT_H
