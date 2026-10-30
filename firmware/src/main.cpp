#include <Arduino.h>
#include <Wire.h>
#include <XPowersLib.h>
#include "board_pinout.h"
#include "configuration.h"
#include "display.h"
#include "wifi_manager.h"
#include "lora.h"
#include "mqtt.h"
#include "node.h"
#include "gateway.h"

// EWS T-Beam firmware — boot foundation (FEAT-001) + role dispatch (FEAT-003).
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

    // Role dispatch (FEAT-003). In AP mode we stay in setup/config only (the
    // web config UI lands in FEAT-004); otherwise bring up transport and run the
    // role selected by Config.identity.role. The MCP23017 role jumper is NEVER
    // consulted — role comes only from config.
    if (WiFiManager::isApMode()) {
        // TODO(feat-004): start the AP-mode web configuration server here.
        Serial.println("AP mode: web config placeholder (FEAT-004)");
        return;
    }

    // STA mode: init the radio always. Configure the MQTT client now (cheap,
    // no connection yet); the actual connect happens in the role loop only once
    // WiFi is up (MQTT_Utils::connect() bails out while offline).
    LoRa_Utils::setup();
    MQTT_Utils::setup();

    if (Config.identity.role == 1) {
        Serial.println("Role: GATEWAY");
        Gateway::setup();
    } else {
        Serial.println("Role: NODE");
        Node::setup();
    }
}

void loop() {
    WiFiManager::checkWiFi();

    // In AP mode there is no role loop yet (web config arrives in FEAT-004).
    if (WiFiManager::isApMode()) return;

    if (Config.identity.role == 1) {
        Gateway::loop();
    } else {
        Node::loop();
    }
}
