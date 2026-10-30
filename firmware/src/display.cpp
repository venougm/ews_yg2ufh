#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "configuration.h"
#include "board_pinout.h"
#include "display.h"

extern Configuration Config;

#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64

static Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
static bool displayReady = false;

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
        oled.clearDisplay();
        oled.setTextSize(1);
        oled.setTextColor(SSD1306_WHITE);
        oled.setCursor(0, 0);
        oled.println("EWS T-Beam");
        oled.display();
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
    }

}
