#ifndef SIREN_H
#define SIREN_H

#include <Arduino.h>

// Siren + status-LED control over an MCP23017 I2C expander (FEAT-003).
//
// ============================================================================
//  !!!  SIREN IS MANUAL-ONLY  !!!
//  The siren relay is actuated ONLY in response to an operator MQTT command
//  (yg2ufh/ews/<kab>/<id>/siren/cmd). It is NEVER auto-triggered from sensor
//  readings or threshold crossings. Tilt/weather thresholds publish an ALARM
//  for humans to act on; they MUST NOT call setSiren(). Keep this invariant.
// ============================================================================
//
// The MCP23017 is driven through a tiny inline register helper (no extra lib):
// GPA0..GPA4 are the status LEDs + siren relay, GPB0..GPB3 are buttons / spare.

namespace Siren_Utils {
    void setup();                       // init MCP23017 (I2C), all outputs off
    void setSiren(bool on);             // MANUAL-ONLY relay drive (see header note)
    bool isSirenOn();

    void setLed(uint8_t bit, bool on);  // GPA LED helper (MCP_LED_* bit)

    // Act on an inbound MQTT siren command. Accepts "ON", "OFF" or "PATTERN:x".
    void handleCmd(const String& payload);
}

#endif // SIREN_H
