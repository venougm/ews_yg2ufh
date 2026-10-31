#include <RadioLib.h>
#include <SPI.h>
#include "board_pinout.h"
#include "configuration.h"
#include "lora.h"

// RadioLib SX1276 TX/RX. Per the task spec the Module is constructed with
// (CS, DIO0, RST) — the T-Beam SX1276 exposes DIO0 as the TX-done / RX-done IRQ.
// No APRS prefix is added on transmit and no APRS parsing is done on receive.

extern Configuration Config;

// SX1276 radio = new Module(NSS, DIO0, RST)
static SX1276 radio = new Module(RADIO_CS_PIN, RADIO_DIO0_PIN, RADIO_RST_PIN);

namespace {
    // DIO0 fires on TX-done and RX-done; the loop polls this flag.
    volatile bool operationDone = true;
    bool transmitFlag = true;   // true after a TX (or at boot) so receive() re-arms RX

    // Display counters (additive, no effect on TX/RX logic).
    uint32_t txCounter = 0;
    uint32_t rxCounter = 0;
    int      lastRssiVal = 0;
    float    lastSnrVal = 0;

    IRAM_ATTR void setFlag() {
        operationDone = true;
    }
}

namespace LoRa_Utils {

    void setup() {
        SPI.begin(RADIO_SCK_PIN, RADIO_MISO_PIN, RADIO_MOSI_PIN, RADIO_CS_PIN);

        float freqMHz = (float)Config.lora.freq / 1000000.0f;
        int state = radio.begin(freqMHz);
        if (state != RADIOLIB_ERR_NONE) {
            Serial.print("LoRa begin failed, code ");
            Serial.println(state);
            return;
        }

        radio.setDio0Action(setFlag, RISING);

        radio.setSpreadingFactor(Config.lora.sf);
        radio.setCodingRate(Config.lora.cr);
        radio.setBandwidth((float)Config.lora.bw / 1000.0f);   // Hz -> kHz
        radio.setOutputPower(Config.lora.power);
        radio.setSyncWord((uint8_t)Config.lora.syncWord);
        radio.setCRC(true);
        radio.autoLDRO();

        Serial.print("LoRa init done @ ");
        Serial.print(freqMHz);
        Serial.println(" MHz");

        // Start listening; receive() flips transmitFlag so RX re-arms as needed.
        radio.startReceive();
        transmitFlag = false;
        operationDone = false;
    }

    bool transmit(const String& payload) {
        // Optional Channel Activity Detection before TX.
        if (Config.lora.cadActive) {
            int cad = radio.scanChannel();
            // Busy/failed channel: skip this TX rather than step on traffic.
            if (cad != RADIOLIB_CHANNEL_FREE) {
                Serial.println("LoRa channel busy (CAD), TX skipped");
                return false;
            }
        }

        // NO APRS prefix. Use the byte-buffer overload so a const payload works
        // (RadioLib's transmit(String&) takes a non-const reference).
        int state = radio.transmit((const uint8_t*)payload.c_str(), payload.length());
        transmitFlag = true;
        operationDone = false;

        if (state == RADIOLIB_ERR_NONE) {
            txCounter++;
            Serial.print("---> LoRa Tx: ");
            Serial.println(payload);
            return true;
        }
        Serial.print("LoRa Tx failed, code ");
        Serial.println(state);
        return false;
    }

    LoRaRx receive() {
        LoRaRx rx;
        if (!operationDone) return rx;
        operationDone = false;

        if (transmitFlag) {
            // The IRQ that just fired was TX-done: re-arm the receiver.
            radio.startReceive();
            transmitFlag = false;
            return rx;
        }

        String packet;
        int state = radio.readData(packet);
        if (state == RADIOLIB_ERR_NONE && packet.length() > 0) {
            rx.valid   = true;
            rx.payload = packet;
            rx.rssi    = (int)radio.getRSSI();
            rx.snr     = radio.getSNR();
            rxCounter++;
            lastRssiVal = rx.rssi;
            lastSnrVal  = rx.snr;
            Serial.print("<--- LoRa Rx: ");
            Serial.println(packet);
            Serial.printf("(RSSI:%d / SNR:%.1f)\n", rx.rssi, rx.snr);
        }

        // Go back to listening for the next packet.
        radio.startReceive();
        return rx;
    }

    // ---- Display data sources (additive) --------------------------------
    uint32_t txCount() { return txCounter; }
    uint32_t rxCount() { return rxCounter; }
    int      lastRssi() { return lastRssiVal; }
    float    lastSnr()  { return lastSnrVal; }

}
