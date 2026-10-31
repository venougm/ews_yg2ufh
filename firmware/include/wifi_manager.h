#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>

// WiFi: STA to configured APs with softAP fallback at 192.168.4.1.
// Minimal WiFi manager (no APRS/digipeater logic).
namespace WiFiManager {
    void begin();           // decide STA vs AP based on config, then connect
    void connectSTA();      // try configured APs
    void startAP();         // softAP fallback, IP 192.168.4.1
    void checkWiFi();       // reconnect attempt every ~30s when in STA mode
    bool isConnected();
    bool isApMode();

    // ---- Display data sources (additive, const-correct) -----------------
    String getIP();         // WiFi.localIP().toString() when connected, else ""
    int    getRSSI();       // WiFi.RSSI() when connected, else 0
    String apSsid();        // AP SSID: "EWS-"+nodeId, else "YG2UFH-EWS-Setup"
}

#endif // WIFI_MANAGER_H
