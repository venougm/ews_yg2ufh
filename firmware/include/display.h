#ifndef DISPLAY_H
#define DISPLAY_H

#include <Arduino.h>

// SSD1306 OLED helper. EVERY call is a no-op when Config.display.enabled is
// false, so the rest of the firmware can call these unconditionally.
//
// Page renderer (FEAT-001): loop() auto-rotates the role-relevant pages every
// ~4 s (millis-based, no delay()), honours Config.display.timeout blanking
// (0 = always on, >0 = blank after N seconds, wake on event), and overlays a
// transient ALARM page when showAlarm() has been called. Pages mirror
// docs/mockup/oled-screens.svg + PANDUAN-PERANGKAT.md section 5 exactly.
namespace DisplayUtils {
    enum class Page {
        BOOT,               // splash
        AP_SETUP,           // mode AP (setup) info
        GW_A,               // gateway: network + nodes
        GW_B,               // gateway: sensor + siren + uptime
        NODE_A,             // node: sensor + GPS + LoRa send line
        NODE_B,             // node (failover): sensor + GPS + IP + WiFi send line
        ALARM,              // transient SIAGA/AWAS overlay
        SETUP_TRANSITION    // progress bar while USER button is held
    };

    void setup();                        // init OLED if enabled
    void showStatus(const String& msg);  // single status line (no-op when disabled)
    bool isEnabled();

    void loop();                         // non-blocking rotation + timeout blanking
    void showPage(Page p);               // render a specific page now
    void showBootPage();                 // render the BOOT splash now
    void setSetupProgress(uint8_t pct);  // 0..100, drives SETUP_TRANSITION bar
    void showAlarm(const String& level,  // "AWAS" / "SIAGA"
                   const String& node,
                   const String& reason); // start a transient ALARM overlay
}

#endif // DISPLAY_H
