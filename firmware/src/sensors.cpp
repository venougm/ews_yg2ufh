#include <Wire.h>
#include <Adafruit_BME280.h>
#include <Adafruit_ADS1X15.h>
#include <ModbusMaster.h>
#include <TinyGPSPlus.h>
#include "board_pinout.h"
#include "configuration.h"
#include "sensors.h"

// Sensor HAL. Each reader is guarded by its Config.sensors.* flag so a device
// only pays for the sensors it declares. See sensors.h for the flag->group map.

extern Configuration Config;

namespace {

    // ---- I2C sensors -------------------------------------------------------
    Adafruit_BME280     bme;
    Adafruit_ADS1115    ads;
    bool bmeReady = false;
    bool adsReady = false;

    // ---- ADS1115 divider math ---------------------------------------------
    // The battery / PV lines feed the ADS1115 through a resistor divider. With
    // the gain set to GAIN_ONE the full-scale input is +/-4.096 V and the raw
    // count-to-volt factor is 4.096/32768. DIVIDER scales the measured node
    // voltage back up to the real rail voltage (R_top + R_bottom) / R_bottom.
    const float ADS_LSB_VOLT = 4.096f / 32768.0f;   // volts per count @ GAIN_ONE
    const float BATT_DIVIDER = 6.0f;                 // e.g. 100k/20k -> ~6x (<=15V)
    const float PV_DIVIDER   = 6.0f;                 // e.g. 100k/20k -> ~6x

    // ---- EPEVER Tracer over RS485 (ModbusMaster) ---------------------------
    // Common Tracer MPPT input registers (function 0x04):
    //   0x3100 PV array voltage        (scale 1/100)
    //   0x3104 battery voltage         (scale 1/100)
    //   0x310C load current            (scale 1/100)
    //   0x311A battery SOC             (percent, scale 1)
    HardwareSerial  rs485Serial(2);     // UART2 for the RS485 transceiver
    ModbusMaster    epever;
    bool epeverReady = false;

    const uint16_t EPEVER_REG_PV_VOLT   = 0x3100;
    const uint16_t EPEVER_REG_BATT_VOLT = 0x3104;
    const uint16_t EPEVER_REG_LOAD_CURR = 0x310C;
    const uint16_t EPEVER_REG_SOC       = 0x311A;

    // DE/RE direction control for the half-duplex RS485 transceiver.
    void preTransmission()  { digitalWrite(RS485_DERE_PIN, HIGH); }
    void postTransmission() { digitalWrite(RS485_DERE_PIN, LOW); }

    // ---- Pulse-counting sensors (rain + anemometer) ------------------------
    volatile uint32_t rainPulses  = 0;
    volatile uint32_t anemoPulses = 0;
    uint32_t          anemoWindowStart = 0;

    // Tipping-bucket calibration: mm of rain per bucket tip.
    const float RAIN_MM_PER_PULSE = 0.2794f;

    IRAM_ATTR void rainISR()  { rainPulses++; }
    IRAM_ATTR void anemoISR() { anemoPulses++; }

    // ---- GPS ---------------------------------------------------------------
    TinyGPSPlus     gps;
    HardwareSerial  gpsSerial(1);       // Serial1 for NEO-6M
    bool gpsBegun = false;

    void setupBme() {
        bmeReady = bme.begin(BME280_ADDR, &Wire);
        if (!bmeReady) Serial.println("BME280 init failed");
    }

    void setupAds() {
        adsReady = ads.begin(ADS1115_ADDR, &Wire);
        if (adsReady) {
            ads.setGain(GAIN_ONE);      // +/-4.096 V full scale
        } else {
            Serial.println("ADS1115 init failed");
        }
    }

    void setupEpever() {
        pinMode(RS485_DERE_PIN, OUTPUT);
        digitalWrite(RS485_DERE_PIN, LOW);
        rs485Serial.begin(115200, SERIAL_8N1, RS485_RO_PIN, RS485_DI_PIN);
        epever.begin(1, rs485Serial);   // Tracer default slave id = 1
        epever.preTransmission(preTransmission);
        epever.postTransmission(postTransmission);
        epeverReady = true;
    }

    void setupPulse() {
        if (Config.sensors.rain) {
            pinMode(RAIN_PULSE_PIN, INPUT_PULLUP);
            attachInterrupt(digitalPinToInterrupt(RAIN_PULSE_PIN), rainISR, FALLING);
        }
        if (Config.sensors.anemo) {
            pinMode(ANEMO_PULSE_PIN, INPUT_PULLUP);
            attachInterrupt(digitalPinToInterrupt(ANEMO_PULSE_PIN), anemoISR, FALLING);
        }
        anemoWindowStart = millis();
    }

    void setupGps() {
        gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
        gpsBegun = true;
    }

    // Read battery/PV voltage from the ADS1115 via the resistor dividers.
    void readAds(SensorReading& r) {
        if (!adsReady) return;
        int16_t rawBatt = ads.readADC_SingleEnded(ADS_BATT_CH);
        int16_t rawPv   = ads.readADC_SingleEnded(ADS_PV_CH);
        r.battV = rawBatt * ADS_LSB_VOLT * BATT_DIVIDER;
        r.pvV   = rawPv   * ADS_LSB_VOLT * PV_DIVIDER;
        r.powerPresent = true;
    }

    // Read battery/PV/load/SOC from the EPEVER Tracer over Modbus.
    void readEpever(SensorReading& r) {
        if (!epeverReady) return;

        uint8_t res = epever.readInputRegisters(EPEVER_REG_PV_VOLT, 1);
        if (res == epever.ku8MBSuccess) {
            r.pvV = epever.getResponseBuffer(0) / 100.0f;
            r.powerPresent = true;
        }
        res = epever.readInputRegisters(EPEVER_REG_BATT_VOLT, 1);
        if (res == epever.ku8MBSuccess) {
            r.battV = epever.getResponseBuffer(0) / 100.0f;
            r.powerPresent = true;
        }
        res = epever.readInputRegisters(EPEVER_REG_LOAD_CURR, 1);
        if (res == epever.ku8MBSuccess) {
            r.loadA = epever.getResponseBuffer(0) / 100.0f;
            r.powerPresent = true;
        }
        res = epever.readInputRegisters(EPEVER_REG_SOC, 1);
        if (res == epever.ku8MBSuccess) {
            r.soc = epever.getResponseBuffer(0);
            r.powerPresent = true;
        }
    }
}

namespace Sensors_Utils {

    void setup() {
        if (Config.sensors.bme280)  setupBme();
        if (Config.sensors.ads1115) setupAds();
        if (Config.sensors.epever)  setupEpever();
        if (Config.sensors.rain || Config.sensors.anemo) setupPulse();
        if (Config.sensors.gps)     setupGps();
    }

    // Keep the GPS parser fed; pulse counters update from their ISRs.
    void loop() {
        if (Config.sensors.gps && gpsBegun) {
            while (gpsSerial.available() > 0) {
                gps.encode(gpsSerial.read());
            }
        }
    }

    SensorReading readEnabled() {
        SensorReading r;

        // Weather from BME280.
        if (Config.sensors.bme280 && bmeReady) {
            r.temp  = bme.readTemperature();
            r.hum   = bme.readHumidity();
            r.press = bme.readPressure() / 100.0f;      // Pa -> hPa
            r.weatherPresent = true;
        }

        // Wind: pulse frequency over the elapsed window since the last read.
        if (Config.sensors.anemo) {
            noInterrupts();
            uint32_t pulses = anemoPulses;
            anemoPulses = 0;
            interrupts();
            uint32_t now = millis();
            float secs = (now - anemoWindowStart) / 1000.0f;
            anemoWindowStart = now;
            r.windHz = (secs > 0) ? (pulses / secs) : 0;
            r.windPresent = true;
        }

        // Power from ADS1115 (divider) and/or EPEVER Modbus.
        if (Config.sensors.ads1115) readAds(r);
        if (Config.sensors.epever)  readEpever(r);

        // Air quality: raw MQ-135 ADC counts.
        if (Config.sensors.mq135) {
            r.airRaw = analogRead(MQ135_ADC_PIN);
            r.airPresent = true;
        }

        // Rain: accumulate tipping-bucket pulses since the last read.
        if (Config.sensors.rain) {
            noInterrupts();
            uint32_t pulses = rainPulses;
            rainPulses = 0;
            interrupts();
            r.rainMm = pulses * RAIN_MM_PER_PULSE;
            r.rainPresent = true;
        }

        // GPS fix from the TinyGPSPlus parser (fed in loop()).
        if (Config.sensors.gps) {
            if (gps.location.isValid()) {
                r.lat    = gps.location.lat();
                r.lon    = gps.location.lng();
                r.gpsFix = true;
            } else {
                r.gpsFix = false;
            }
            r.gpsPresent = true;
        }

        return r;
    }
}
