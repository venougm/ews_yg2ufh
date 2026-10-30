#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>

// WiFi: STA to configured APs with softAP fallback at 192.168.4.1.
// Simplified from the CA2RXU wifi_utils/network_manager (no backupDigi / APRS).
namespace WiFiManager {
    void begin();           // decide STA vs AP based on config, then connect
    void connectSTA();      // try configured APs
    void startAP();         // softAP fallback, IP 192.168.4.1
    void checkWiFi();       // reconnect attempt every ~30s when in STA mode
    bool isConnected();
    bool isApMode();
}

#endif // WIFI_MANAGER_H
