#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <XPowersLib.h>
#include "board_pinout.h"
#include "configuration.h"
#include "display.h"
#include "wifi_manager.h"
#include "lora.h"
#include "mqtt.h"
#include "web_config.h"
#include "node.h"
#include "gateway.h"
#include "forceap.h"

// EWS T-Beam firmware — boot foundation (FEAT-001) + role dispatch (FEAT-003).
// Boot order per plan: Serial -> I2C -> AXP2101 power rails (LoRa+GPS) -> config
// -> display -> WiFi (STA or auto-AP). Role dispatch and transport are added by
// later FEATs. The MCP23017 role jumper (GPB2) is NEVER read for role logic;
// role comes only from Config.identity.role.

Configuration Config;

static XPowersAXP2101 PMU;
static bool pmuReady = false;

// ---- FEAT-002: USER-button -> temporary AP config mode ---------------------
// forceAp uses a CLEAN REBOOT (not a live STA->AP teardown): main.cpp decides
// AP-vs-STA exactly once in setup(), so the button path persists a one-shot NVS
// flag (ForceAp::request()) and ESP.restart()s; the next setup() reads-and-clears
// the flag and comes up in AP mode. The button-triggered AP is TEMPORARY and
// reverts to client mode after AP_CONFIG_TIMEOUT_MS with no client connected; a
// first-boot unconfigured AP (apFromButton == false) does NOT arm the timeout.
static const unsigned long AP_CONFIG_TIMEOUT_MS = 300000;  // 5 min
static bool apFromButton = false;
static unsigned long apStart = 0;          // millis() when a forced AP began

// USER-button (GPIO38, INPUT_PULLUP, active-low) non-blocking hold FSM. Polled
// in loop() only in STA/client mode; a ~3 s hold enters AP config, release
// before that cancels.
static const unsigned long BTN_HOLD_MS = 3000;
enum class BtnState { IDLE, PRESSING };
static BtnState btnState = BtnState::IDLE;
static unsigned long btnPressStart = 0;

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

    // Optional OLED (guarded by Config.display.enabled). Show the splash early
    // so it is visible during the rest of boot.
    DisplayUtils::setup();
    DisplayUtils::showBootPage();

    // USER button for the "re-enter AP config" hold gesture (active-low).
    pinMode(BTN_USER_PIN, INPUT_PULLUP);

    // FEAT-002: a prior ~3 s button hold persisted a one-shot forceAp flag and
    // rebooted. Read-and-clear it before deciding STA vs AP; when set, route
    // straight into the temporary AP + web config path regardless of saved WiFi.
    if (ForceAp::take()) {
        Serial.println("forceAp: entering temporary AP config mode");
        apFromButton = true;
        WiFiManager::startAP();
        DisplayUtils::showPage(DisplayUtils::Page::AP_SETUP);
        WebConfig::setup();
        apStart = millis();
        return;
    }

    // STA if WiFi is configured, else softAP for web-based setup.
    WiFiManager::begin();

    // Role dispatch (FEAT-003). In AP mode we stay in setup/config only (the
    // web config UI lands in FEAT-004); otherwise bring up transport and run the
    // role selected by Config.identity.role. The MCP23017 role jumper is NEVER
    // consulted — role comes only from config.
    if (WiFiManager::isApMode()) {
        // AP mode: serve the web configuration UI (FEAT-004). On "Simpan &
        // Jalankan" the server saves the config and reboots into client mode.
        // This is the first-boot unconfigured AP — apFromButton stays false, so
        // loop() does NOT arm the AP_CONFIG_TIMEOUT_MS timeout.
        Serial.println("AP mode: starting web config server");
        DisplayUtils::showPage(DisplayUtils::Page::AP_SETUP);
        WebConfig::setup();
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
        DisplayUtils::showPage(DisplayUtils::Page::GW_A);
    } else {
        Serial.println("Role: NODE");
        Node::setup();
        DisplayUtils::showPage(DisplayUtils::Page::NODE_A);
    }
}

// Non-blocking USER-button FSM (STA/client mode only). A ~3 s hold shows the
// SETUP_TRANSITION progress bar then persists the forceAp flag and reboots into
// AP config mode; a release before 3 s cancels and resumes the normal pages.
static void pollUserButton() {
    bool pressed = (digitalRead(BTN_USER_PIN) == LOW);   // active-low
    unsigned long now = millis();

    switch (btnState) {
        case BtnState::IDLE:
            if (pressed) {
                btnState = BtnState::PRESSING;
                btnPressStart = now;
                DisplayUtils::setSetupProgress(0);
                DisplayUtils::showPage(DisplayUtils::Page::SETUP_TRANSITION);
            }
            break;

        case BtnState::PRESSING:
            if (!pressed) {
                // Released before the hold completed -> cancel. The normal page
                // rotation resumes on the next DisplayUtils::loop().
                btnState = BtnState::IDLE;
                if (Config.identity.role == 1) {
                    DisplayUtils::showPage(DisplayUtils::Page::GW_A);
                } else {
                    DisplayUtils::showPage(DisplayUtils::Page::NODE_A);
                }
            } else {
                unsigned long held = now - btnPressStart;
                uint8_t pct = (uint8_t)min(100UL, held * 100UL / BTN_HOLD_MS);
                DisplayUtils::setSetupProgress(pct);
                if (held >= BTN_HOLD_MS) {
                    Serial.println("USER button held 3s -> requesting AP config mode");
                    ForceAp::request();
                    ESP.restart();
                }
            }
            break;
    }
}

void loop() {
    WiFiManager::checkWiFi();

    // In AP mode run only the web config server (service HTTP + handle reboot).
    if (WiFiManager::isApMode()) {
        WebConfig::loop();
        DisplayUtils::loop();   // keep the AP_SETUP page alive

        // A button-triggered AP is TEMPORARY: if nobody connects within
        // AP_CONFIG_TIMEOUT_MS, reboot back to client mode. A first-boot
        // unconfigured AP (apFromButton == false) runs indefinitely. Any
        // connected station keeps the window open (slides apStart forward).
        if (apFromButton) {
            if (WiFi.softAPgetStationNum() > 0) {
                apStart = millis();   // activity -> keep the AP alive
            } else if (millis() - apStart >= AP_CONFIG_TIMEOUT_MS) {
                Serial.println("Temporary AP idle timeout -> rebooting to client mode");
                ESP.restart();
            }
        }
        return;
    }

    // STA/client mode: watch the USER button for the AP-config hold gesture.
    pollUserButton();

    if (Config.identity.role == 1) {
        Gateway::loop();
    } else {
        Node::loop();
    }

    // Drive the OLED page rotation + timeout blanking (no-op when disabled).
    DisplayUtils::loop();
}
