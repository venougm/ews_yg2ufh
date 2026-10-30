#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

// Sensor HAL (FEAT-003). Per-flag readers behind the Config.sensors.* booleans:
//   bme280   -> weather (temp/hum/press)            via Adafruit_BME280 (I2C)
//   ads1115  -> power   (batt_v/pv_v via divider)    via Adafruit_ADS1X15 (I2C)
//   epever   -> power   (batt_v/pv_v/load_a/soc)     via ModbusMaster over RS485
//   rain     -> rain    (mm, tipping-bucket pulses)  via GPIO ISR
//   anemo    -> weather (wind, Hz from pulses)       via GPIO ISR
//   mq135    -> air     (raw ADC)                    via analogRead
//   gps      -> gps     (lat/lon/fix)                via TinyGPSPlus on Serial1
//
// readEnabled() fills a Reading struct, setting the `present` flag ONLY for the
// groups whose sensor flag is enabled in Config.sensors. Disabled groups stay
// `present = false` so node.cpp / gateway.cpp emit only enabled groups.

struct SensorReading {
    // weather (bme280 + anemo)
    bool   weatherPresent = false;
    float  temp = 0, hum = 0, press = 0;
    bool   windPresent = false;
    float  windHz = 0;              // raw anemometer pulse frequency (Hz)

    // power (ads1115 and/or epever)
    bool   powerPresent = false;
    float  battV = 0, pvV = 0, loadA = 0;
    int    soc = 0;

    // air quality (mq135)
    bool   airPresent = false;
    int    airRaw = 0;              // raw 12-bit ADC counts

    // rain (tipping bucket)
    bool   rainPresent = false;
    float  rainMm = 0;

    // gps
    bool   gpsPresent = false;
    double lat = 0, lon = 0;
    bool   gpsFix = false;
};

namespace Sensors_Utils {
    void setup();                       // init enabled sensors (I2C/RS485/ISR/GPS)
    void loop();                        // feed GPS serial + keep pulse counters live
    SensorReading readEnabled();        // read only the enabled sensor groups
}

#endif // SENSORS_H
