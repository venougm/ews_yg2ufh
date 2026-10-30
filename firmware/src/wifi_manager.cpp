#include <WiFi.h>
#include "configuration.h"
#include "wifi_manager.h"

extern Configuration Config;

namespace {
    bool apMode = false;
    unsigned long lastCheck = 0;
    const unsigned long CHECK_INTERVAL_MS = 30000;
    IPAddress apIP(192, 168, 4, 1);
    IPAddress apGateway(192, 168, 4, 1);
    IPAddress apSubnet(255, 255, 255, 0);

    bool hasConfiguredAP() {
        for (size_t i = 0; i < Config.wifiAPs.size(); i++) {
            if (Config.wifiAPs[i].ssid != "") return true;
        }
        return false;
    }

    String apSsid() {
        if (Config.identity.nodeId != "") return "EWS-" + Config.identity.nodeId;
        return "YG2UFH-EWS-Setup";
    }
}

namespace WiFiManager {

    void connectSTA() {
        apMode = false;
        WiFi.mode(WIFI_STA);

        for (size_t i = 0; i < Config.wifiAPs.size(); i++) {
            if (Config.wifiAPs[i].ssid == "") continue;
            Serial.print("WiFi connecting to ");
            Serial.println(Config.wifiAPs[i].ssid);
            WiFi.begin(Config.wifiAPs[i].ssid.c_str(), Config.wifiAPs[i].password.c_str());

            unsigned long start = millis();
            unsigned long timeoutMs = (unsigned long)Config.wifiAutoAP.timeout * 1000UL;
            if (timeoutMs == 0) timeoutMs = 10000UL;
            while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs) {
                delay(500);
                Serial.print(".");
            }
            if (WiFi.status() == WL_CONNECTED) {
                Serial.print("\nWiFi OK, IP: ");
                Serial.println(WiFi.localIP());
                return;
            }
            Serial.println("\nWiFi connect failed for this AP");
        }
    }

    void startAP() {
        apMode = true;
        WiFi.mode(WIFI_AP);
        WiFi.softAPConfig(apIP, apGateway, apSubnet);
        String ssid = apSsid();
        WiFi.softAP(ssid.c_str(), Config.wifiAutoAP.apPassword.c_str());
        Serial.print("SoftAP started: ");
        Serial.print(ssid);
        Serial.print(" @ ");
        Serial.println(WiFi.softAPIP());
    }

    void begin() {
        if (!hasConfiguredAP()) {
            Serial.println("No WiFi credentials, starting AP mode");
            startAP();
            return;
        }
        connectSTA();
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("STA failed, falling back to AP mode");
            startAP();
        }
    }

    void checkWiFi() {
        if (apMode) return;
        if (millis() - lastCheck < CHECK_INTERVAL_MS) return;
        lastCheck = millis();
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("WiFi lost, reconnecting...");
            connectSTA();
        }
    }

    bool isConnected() {
        return WiFi.status() == WL_CONNECTED;
    }

    bool isApMode() {
        return apMode;
    }

}
