#ifndef BOARD_PINOUT_H
#define BOARD_PINOUT_H

// Single source of truth for the LilyGO T-Beam v1.2 hardware pin map.
// Per SPEC-REV-B.md and the EWS task spec. Where the CA2RXU v1.2_915 variant
// disagrees (RST=14), the TASK SPEC WINS: RST=23, DIO0=26.

// ---- LoRa SX1276 (T-Beam) ----
#define HAS_SX1276
#define RADIO_SCK_PIN   5
#define RADIO_MISO_PIN  19
#define RADIO_MOSI_PIN  27
#define RADIO_CS_PIN    18     // NSS
#define RADIO_RST_PIN   23
#define RADIO_DIO0_PIN  26

// ---- I2C shared bus ----
#define I2C_SDA 21
#define I2C_SCL 22

// ---- I2C addresses ----
#define OLED_ADDR     0x3C
#define BME280_ADDR   0x76
#define MCP23017_ADDR 0x20
#define ADS1115_ADDR  0x48

// ---- GPS NEO-6M on Serial1 ----
#define GPS_RX_PIN 34   // ESP RX (verify vs TinyGPSPlus wiring)
#define GPS_TX_PIN 12   // ESP TX

// ---- Direct GPIO ----
#define MQ135_ADC_PIN     35   // input-only ADC
#define RAIN_PULSE_PIN    33   // pull-up, interrupt
#define ANEMO_PULSE_PIN   32   // pull-up, interrupt
#define RS485_DI_PIN      13
#define RS485_RO_PIN      25
#define RS485_DERE_PIN    4
#define DFPLAYER_TX_PIN   2
#define DFPLAYER_RX_PIN   15

// ---- MCP23017 bit map (port A = 0..7, port B = 8..15) ----
#define MCP_LED_POWER   0   // GPA0
#define MCP_LED_LORA    1   // GPA1
#define MCP_LED_ALARM   2   // GPA2
#define MCP_LED_FAULT   3   // GPA3
#define MCP_SIREN_RELAY 4   // GPA4  (MANUAL-ONLY)
#define MCP_BTN_TEST    8   // GPB0 pull-up active-low
#define MCP_BTN_SILENCE 9   // GPB1 pull-up active-low
#define MCP_ROLE_JUMPER 10  // GPB2  (IGNORED for role logic)
#define MCP_SPARE       11  // GPB3

// ---- ADS1115 channels ----
#define ADS_BATT_CH 0   // AIN0 battery V via divider
#define ADS_PV_CH   1   // AIN1 PV V via divider

#endif // BOARD_PINOUT_H
