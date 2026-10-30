#ifndef LORA_H
#define LORA_H

#include <Arduino.h>

// RadioLib SX1276 driver for the EWS T-Beam. Mirrors the CA2RXU lora_utils flow
// (SPI.begin -> radio.begin -> setDio0Action -> apply RF params -> startReceive)
// but drops the APRS "\x3c\xff\x01" prefix and the APRS/blacklist handling.
// Payloads are the compact EWS LoRa JSON (see ews_packet.h).

struct LoRaRx {
    bool   valid = false;   // true when a payload was received this call
    String payload;         // raw received payload (no prefix)
    int    rssi = 0;        // dBm
    float  snr = 0;         // dB
};

namespace LoRa_Utils {
    void setup();                           // SPI + radio.begin + RF params from Config + start RX
    bool transmit(const String& payload);   // TX with NO APRS prefix; returns true on success
    LoRaRx receive();                        // flag-driven RX; .valid=false when nothing pending
}

#endif // LORA_H
