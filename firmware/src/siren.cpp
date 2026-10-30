#include <Wire.h>
#include "board_pinout.h"
#include "configuration.h"
#include "siren.h"

// MCP23017-driven siren relay + status LEDs over the shared I2C bus.
//
// ============================================================================
//  !!!  SIREN IS MANUAL-ONLY  !!!
//  setSiren() is reached ONLY from Siren_Utils::handleCmd(), which is itself
//  invoked ONLY by the MQTT siren/cmd callback. There is deliberately NO path
//  from sensor data or thresholds to setSiren(). Do not add one.
// ============================================================================

extern Configuration Config;

namespace {

    // ---- Minimal MCP23017 register helper (no external library) -----------
    // Bank-0 register addresses (default IOCON.BANK = 0).
    const uint8_t MCP_IODIRA = 0x00;    // port A direction (1=input)
    const uint8_t MCP_IODIRB = 0x01;    // port B direction
    const uint8_t MCP_GPPUB  = 0x0D;    // port B pull-ups
    const uint8_t MCP_GPIOA  = 0x12;    // port A value
    const uint8_t MCP_OLATA  = 0x14;    // port A output latch

    bool    mcpReady = false;
    uint8_t olatA    = 0x00;    // shadow of the port-A output latch
    bool    sirenOn  = false;

    void mcpWrite(uint8_t reg, uint8_t val) {
        Wire.beginTransmission(MCP23017_ADDR);
        Wire.write(reg);
        Wire.write(val);
        Wire.endTransmission();
    }

    // Flush the shadow latch to the chip.
    void writeOlatA() { mcpWrite(MCP_OLATA, olatA); }

    // Set/clear one GPA bit in the shadow latch and push it out.
    void setPortABit(uint8_t bit, bool on) {
        if (on) olatA |= (uint8_t)(1 << bit);
        else    olatA &= (uint8_t)~(1 << bit);
        if (mcpReady) writeOlatA();
    }
}

namespace Siren_Utils {

    void setup() {
        // Probe the expander; skip quietly if the siren board is absent.
        Wire.beginTransmission(MCP23017_ADDR);
        mcpReady = (Wire.endTransmission() == 0);
        if (!mcpReady) {
            Serial.println("MCP23017 not found, siren disabled");
            return;
        }

        // Port A: GPA0..GPA4 outputs (LEDs + relay), rest output-low.
        mcpWrite(MCP_IODIRA, 0x00);
        // Port B: all inputs (buttons / jumper / spare) with pull-ups.
        mcpWrite(MCP_IODIRB, 0xFF);
        mcpWrite(MCP_GPPUB,  0xFF);

        // All outputs off at boot — relay must start de-energized.
        olatA   = 0x00;
        sirenOn = false;
        writeOlatA();
        Serial.println("MCP23017 siren init done");
    }

    // MANUAL-ONLY. Reached solely via handleCmd(). See the header invariant.
    void setSiren(bool on) {
        if (!Config.siren.enabled) return;
        sirenOn = on;
        setPortABit(MCP_SIREN_RELAY, on);
        setPortABit(MCP_LED_ALARM, on);     // mirror relay on the ALARM LED
    }

    bool isSirenOn() { return sirenOn; }

    void setLed(uint8_t bit, bool on) {
        setPortABit(bit, on);
    }

    // "ON" / "OFF" / "PATTERN:x". PATTERN currently maps to a solid ON; the
    // pattern engine is left for a later FEAT but the command is accepted now.
    void handleCmd(const String& payload) {
        String cmd = payload;
        cmd.trim();
        cmd.toUpperCase();

        if (cmd == "ON") {
            setSiren(true);
        } else if (cmd == "OFF") {
            setSiren(false);
        } else if (cmd.startsWith("PATTERN:")) {
            // TODO(feat-later): drive the named blink/wail pattern. For now a
            // pattern request simply energizes the relay (still manual-only).
            setSiren(true);
        } else {
            Serial.print("Siren cmd ignored: ");
            Serial.println(payload);
        }
    }
}
