#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "configuration.h"
#include "board_pinout.h"
#include "display.h"
#include "wifi_manager.h"
#include "lora.h"
#include "mqtt.h"
#include "node.h"
#include "gateway.h"
#include "siren.h"

// SSD1306 multi-page status renderer (FEAT-001). Strings/layouts mirror
// docs/mockup/oled-screens.svg and PANDUAN-PERANGKAT.md section 5 exactly.
// Everything here is a no-op while Config.display.enabled is false. No delay()
// is used; rotation + timeout are driven from millis() so loop() stays
// non-blocking. The display only READS siren state — it never actuates it.

extern Configuration Config;

#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT  64

#define ROTATE_MS      4000UL    // auto-rotate interval (~4 s)
#define ALARM_MS       5000UL    // transient ALARM overlay duration

static Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
static bool displayReady = false;

namespace {
    using DisplayUtils::Page;

    // millis-based render state.
    Page          currentPage = Page::BOOT;
    unsigned long lastRotate  = 0;    // last auto-rotate tick
    unsigned long lastEvent   = 0;    // last activity (for timeout blanking)
    unsigned long alarmUntil  = 0;    // ALARM overlay active while millis() < this
    uint8_t       setupPct    = 0;    // SETUP_TRANSITION progress 0..100
    bool          screenOn    = true; // false once blanked by timeout

    // Latched ALARM overlay content.
    String alarmLevel, alarmNode, alarmReason;

    // --- small render helpers ------------------------------------------------

    // Top-right status dot (filled when online/active).
    void drawDot(bool on) {
        if (on) oled.fillCircle(SCREEN_WIDTH - 4, 3, 2, SSD1306_WHITE);
    }

    void header(const String& left, const String& roleTag, bool dotOn) {
        oled.setCursor(0, 0);
        oled.print(left);
        oled.print("  ");
        oled.print(roleTag);
        drawDot(dotOn);
        oled.drawLine(0, 10, SCREEN_WIDTH - 1, 10, SSD1306_WHITE);
    }

    // "T27.4 H82% 1008" — weather one-liner from a reading.
    String weatherLine(const SensorReading& r) {
        char buf[22];
        snprintf(buf, sizeof(buf), "T%.1f H%d%% %d",
                 r.temp, (int)r.hum, (int)r.press);
        return String(buf);
    }

    // "Bat12.8 PV18.2 87" — power one-liner from a reading.
    String powerLine(const SensorReading& r) {
        char buf[22];
        snprintf(buf, sizeof(buf), "Bat%.1f PV%.1f %d",
                 r.battV, r.pvV, r.soc);
        return String(buf);
    }

    // SensorReading carries gpsFix but NO satellite count, so we render
    // "GPS:fix" / "GPS:--" and never fabricate a satellite number. A real count
    // would require a TinyGPSPlus satellites() getter on the sensor read path.
    String gpsLine(const SensorReading& r) {
        return r.gpsFix ? String("GPS:fix") : String("GPS:--");
    }

    // "3h20m" style uptime from millis().
    String uptimeStr() {
        unsigned long s = millis() / 1000UL;
        unsigned long h = s / 3600UL;
        unsigned long m = (s % 3600UL) / 60UL;
        char buf[12];
        if (h > 0) snprintf(buf, sizeof(buf), "%luh%lum", h, m);
        else       snprintf(buf, sizeof(buf), "%lum", m);
        return String(buf);
    }

    void line(uint8_t row, const String& s) {
        oled.setCursor(0, 12 + row * 11);   // rows below the 10px header + divider
        oled.print(s);
    }

    // --- page renderers ------------------------------------------------------

    void renderBoot() {
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.println("EWS T-Beam");
        oled.println("YG2UFH");
        oled.println("booting...");
        oled.display();
    }

    void renderApSetup() {
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.println("== MODE SETUP ==");
        oled.print("WiFi:");
        oled.println(WiFiManager::apSsid());
        oled.print("Pass:");
        oled.println(Config.wifiAutoAP.apPassword);
        oled.println("192.168.4.1");
        oled.display();
    }

    void renderGwA() {
        GatewayStatus g = Gateway::status();
        bool online = WiFiManager::isConnected() && MQTT_Utils::isConnected();

        oled.clearDisplay();
        oled.setTextSize(1);
        header(Config.identity.nodeId, "[GW]", online);

        char buf[22];
        snprintf(buf, sizeof(buf), "WiFi %d  MQTT:%s",
                 WiFiManager::getRSSI(),
                 MQTT_Utils::isConnected() ? "OK" : "--");
        line(0, buf);

        line(1, "IP " + WiFiManager::getIP());

        snprintf(buf, sizeof(buf), "Nodes:%d Rx%lu Tx%lu",
                 g.nodeCount,
                 (unsigned long)g.rxTotal, (unsigned long)g.txTotal);
        line(2, buf);

        if (g.lastNodeId != "") {
            snprintf(buf, sizeof(buf), "Last %s  %lus",
                     g.lastNodeId.c_str(), (unsigned long)g.lastAgeSec);
            line(3, buf);
        } else {
            line(3, "Last --");
        }
        oled.display();
    }

    void renderGwB() {
        GatewayStatus g = Gateway::status();
        SensorReading r = Sensors_Utils::readEnabled();
        bool online = WiFiManager::isConnected() && MQTT_Utils::isConnected();

        oled.clearDisplay();
        oled.setTextSize(1);
        header(Config.identity.nodeId, "[GW]", online);

        line(0, weatherLine(r));
        line(1, powerLine(r));
        line(2, String("Siren: ") + (g.sirenOn ? "ON" : "OFF"));
        line(3, "Up " + uptimeStr() + " fw" + EWS_FW_VERSION);
        oled.display();
    }

    void renderNodeA() {
        NodeStatus n = Node::status();

        oled.clearDisplay();
        oled.setTextSize(1);
        // Dot = active: a node is "active" once it is running its send loop.
        header(Config.identity.nodeId, "[NODE]", true);

        line(0, weatherLine(n.reading));
        line(1, powerLine(n.reading));
        line(2, gpsLine(n.reading));

        char buf[22];
        snprintf(buf, sizeof(buf), "LoRa>GW #%lu %ds",
                 (unsigned long)n.seq, n.secsToNext);
        line(3, buf);
        oled.display();
    }

    void renderNodeB() {
        NodeStatus n = Node::status();

        oled.clearDisplay();
        oled.setTextSize(1);
        header(Config.identity.nodeId, "[NODE]", true);

        line(0, weatherLine(n.reading));
        line(1, gpsLine(n.reading));
        line(2, "IP " + WiFiManager::getIP());

        char buf[22];
        snprintf(buf, sizeof(buf), "WiFi>MQTT #%lu", (unsigned long)n.seq);
        line(3, buf);
        oled.display();
    }

    void renderAlarm() {
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.print("!! ");
        oled.print(alarmLevel);
        oled.println(" !!");
        oled.drawLine(0, 12, SCREEN_WIDTH - 1, 12, SSD1306_WHITE);
        oled.setCursor(0, 18);
        oled.print(alarmNode);
        oled.print(" ");
        oled.println(alarmReason);
        oled.setCursor(0, 46);
        oled.println("verifikasi!");
        oled.display();
    }

    void renderSetupTransition() {
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setCursor(0, 0);
        oled.println("Tahan utk SETUP..");

        // Progress bar: frame + proportional fill.
        const int x = 0, y = 16, w = SCREEN_WIDTH - 1, h = 14;
        oled.drawRect(x, y, w, h, SSD1306_WHITE);
        int fill = (int)((long)(w - 4) * setupPct / 100);
        if (fill > 0) oled.fillRect(x + 2, y + 2, fill, h - 4, SSD1306_WHITE);

        oled.setCursor(0, 38);
        oled.println("lepas = batal");
        oled.setCursor(0, 50);
        oled.println("3 dtk -> mode AP");
        oled.display();
    }

    void renderPage(Page p) {
        switch (p) {
            case Page::BOOT:             renderBoot();            break;
            case Page::AP_SETUP:         renderApSetup();         break;
            case Page::GW_A:             renderGwA();             break;
            case Page::GW_B:             renderGwB();             break;
            case Page::NODE_A:           renderNodeA();           break;
            case Page::NODE_B:           renderNodeB();           break;
            case Page::ALARM:            renderAlarm();           break;
            case Page::SETUP_TRANSITION: renderSetupTransition(); break;
        }
    }

    // Wake the screen (re-power + mark activity) if it was blanked.
    void wake() {
        lastEvent = millis();
        if (!screenOn && displayReady) {
            oled.ssd1306_command(SSD1306_DISPLAYON);
            screenOn = true;
        }
    }
}

namespace DisplayUtils {

    bool isEnabled() {
        return Config.display.enabled;
    }

    void setup() {
        displayReady = false;
        if (!Config.display.enabled) {
            Serial.println("Display disabled by config");
            return;
        }

        if (!oled.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
            Serial.println("SSD1306 not found");
            return;
        }

        displayReady = true;
        oled.setRotation(Config.display.turn180 ? 2 : 0);
        oled.setTextSize(1);
        oled.setTextColor(SSD1306_WHITE);
        screenOn   = true;
        lastEvent  = millis();
        lastRotate = millis();
        showBootPage();
    }

    void showStatus(const String& msg) {
        if (!displayReady) return;
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setTextColor(SSD1306_WHITE);
        oled.setCursor(0, 0);
        oled.println("EWS T-Beam");
        oled.println(msg);
        oled.display();
        wake();
    }

    void showBootPage() {
        if (!displayReady) return;
        currentPage = Page::BOOT;
        renderBoot();
        wake();
    }

    void showPage(Page p) {
        if (!displayReady) return;
        currentPage = p;
        renderPage(p);
        wake();
    }

    void setSetupProgress(uint8_t pct) {
        if (!displayReady) return;
        if (pct > 100) pct = 100;
        setupPct = pct;
        currentPage = Page::SETUP_TRANSITION;
        renderSetupTransition();
        wake();
    }

    // Render-only transient overlay. NO SIAGA/AWAS detection lives here and this
    // NEVER calls Siren_Utils::setSiren() — the siren is MANUAL-ONLY. There is no
    // real alarm decision in node/gateway today, so this stays callable but
    // uncalled.
    // TODO: call where a real alarm decision exists.
    void showAlarm(const String& level, const String& node, const String& reason) {
        if (!displayReady) return;
        alarmLevel  = level;
        alarmNode   = node;
        alarmReason = reason;
        alarmUntil  = millis() + ALARM_MS;
        currentPage = Page::ALARM;
        renderAlarm();
        wake();
    }

    void loop() {
        if (!displayReady) return;

        unsigned long now = millis();

        // Transient ALARM overlay takes priority until it expires.
        if (alarmUntil != 0) {
            if (now < alarmUntil) {
                return;   // keep showing the alarm (already rendered)
            }
            alarmUntil = 0;     // expired: fall back to normal rotation
            lastRotate = now;
            lastEvent  = now;   // treat the alarm as recent activity
        }

        // Timeout blanking: timeout==0 means always on; >0 blanks after N s.
        int timeoutS = Config.display.timeout;
        if (timeoutS > 0 && screenOn &&
            (now - lastEvent) > (unsigned long)timeoutS * 1000UL) {
            oled.clearDisplay();
            oled.display();
            oled.ssd1306_command(SSD1306_DISPLAYOFF);
            screenOn = false;
        }
        if (!screenOn) return;   // stay dark until an event wakes us

        // Auto-rotate the role-relevant pages every ~4 s (non-blocking).
        if (now - lastRotate < ROTATE_MS) return;
        lastRotate = now;

        if (WiFiManager::isApMode()) {
            // AP/setup mode shows only the setup info page.
            currentPage = Page::AP_SETUP;
        } else if (Config.identity.role == 1) {
            // GATEWAY: alternate GW_A / GW_B.
            currentPage = (currentPage == Page::GW_A) ? Page::GW_B : Page::GW_A;
        } else {
            // NODE: NODE_A always; NODE_B only when it has WiFi (failover view).
            if (currentPage == Page::NODE_A && WiFiManager::isConnected()) {
                currentPage = Page::NODE_B;
            } else {
                currentPage = Page::NODE_A;
            }
        }
        renderPage(currentPage);
    }

}
