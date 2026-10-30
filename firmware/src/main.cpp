#include <Arduino.h>
#include <Wire.h>
#include <XPowersLib.h>
#include "board_pinout.h"
#include "configuration.h"
#include "display.h"
#include "wifi_manager.h"
#include "lora.h"
#include "mqtt.h"

// EWS T-Beam firmware — boot foundation (FEAT-001).
// Boot order per plan: Serial -> I2C -> AXP2101 power rails (LoRa+GPS) -> config
// -> display -> WiFi (STA or auto-AP). Role dispatch and transport are added by
// later FEATs. The MCP23017 role jumper (GPB2) is NEVER read for role logic;
// role comes only from Config.identity.role.

Configuration Config;

static XPowersAXP2101 PMU;
static bool pmuReady = false;

// Bring up the AXP2101 PMIC and enable the LoRa + GPS power rails. Must run before
// any radio.begin() or GPS use on the T-Beam v1.2. On the standard (non-S3) T-Beam
// the LoRa rail is ALDO2 and the GPS rail is ALDO3.
static void powerInit() {
    pmuReady = PMU.begin(Wire, AXP2101_SLAVE_ADDRESS, I2C_SDA, I2C_SCL);
    if (!pmuReady) {
        Serial.println("AXP2101 init failed!");
        return;
    }
    Serial.println("AXP2101 init done!");

    // LoRa power rail
    PMU.setALDO2Voltage(3300);
    PMU.enableALDO2();

    // GPS power rail
    PMU.setALDO3Voltage(3300);
    PMU.enableALDO3();

    // Battery charging defaults
    PMU.setChargeTargetVoltage(XPOWERS_AXP2101_CHG_VOL_4V2);
    PMU.setChargerConstantCurr(XPOWERS_AXP2101_CHG_CUR_800MA);
    PMU.setSysPowerDownVoltage(2600);
    PMU.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);

    // Let the rails settle before anything downstream powers up.
    delay(50);
}

void setup() {
    Serial.begin(115200);
    delay(300);
    Serial.println("\n=== EWS T-Beam firmware ===");

    Wire.begin(I2C_SDA, I2C_SCL);

    // Power rails first so LoRa/GPS are live for later FEATs.
    powerInit();

    // Load configuration (may restart on first boot / incomplete config).
    Config.setup();

    // Optional OLED (guarded by Config.display.enabled).
    DisplayUtils::setup();

    // STA if WiFi is configured, else softAP for web-based setup.
    WiFiManager::begin();

    if (WiFiManager::isApMode()) {
        DisplayUtils::showStatus("AP setup mode");
    } else if (WiFiManager::isConnected()) {
        DisplayUtils::showStatus("WiFi connected");
    } else {
        DisplayUtils::showStatus("WiFi offline");
    }

    // Transport bring-up (FEAT-002): init the radio always; MQTT only matters in
    // STA mode. Role behavior that uses these lands in a later FEAT.
    if (!WiFiManager::isApMode()) {
        LoRa_Utils::setup();
        MQTT_Utils::setup();
    }
}

void loop() {
    WiFiManager::checkWiFi();

    // Heartbeat until role dispatch / transport arrive in later FEATs.
    static unsigned long lastBeat = 0;
    if (millis() - lastBeat >= 10000) {
        lastBeat = millis();
        Serial.printf("heartbeat uptime=%lus wifi=%d ap=%d\n",
                      (unsigned long)(millis() / 1000),
                      WiFiManager::isConnected() ? 1 : 0,
                      WiFiManager::isApMode() ? 1 : 0);
    }
}
