#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>

// SSD1306 OLED helper. All calls are no-ops when Config.display.enabled is false,
// so the rest of the firmware can call them unconditionally.
namespace DisplayUtils {
    void setup();                       // init OLED if enabled
    void showStatus(const String& msg); // single status line (no-op when disabled)
    bool isEnabled();
}

#endif // DISPLAY_H
