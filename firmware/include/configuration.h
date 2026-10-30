#ifndef CONFIGURATION_H
#define CONFIGURATION_H

#include <Arduino.h>
#include <vector>

// EWS T-Beam configuration. Mirrors the CA2RXU style: nested config classes held
// by a single Configuration object, loaded from /ews_conf.json on SPIFFS with a
// needsRewrite migration + ESP.restart() pattern. All APRS/beacon/digi fields are
// DROPPED. ONE firmware, TWO roles (NODE / GATEWAY) selected here via identity.role.

class Identity {
public:
    int     role;           // 0 = NODE, 1 = GATEWAY
    String  nodeId;
    String  networkId;
    String  provinsi;       // lowercase slug (e.g. "diy")
    String  kabupaten;      // lowercase slug (e.g. "sleman")
    String  kecamatan;      // lowercase slug (e.g. "pakem")
    String  kelurahan;      // lowercase slug; payload metadata only, NOT in MQTT topic
    String  locationName;
    double  latitude;       // manual, NOT GPS
    double  longitude;      // manual, NOT GPS
};

class WiFi_AP {
public:
    String  ssid;
    String  password;
};

class WiFi_Auto_AP {
public:
    bool    enabled;
    String  apPassword;     // default "1234567890"
    int     timeout;
};

class LoRaCfg {
public:
    long    freq;           // default 915000000
    int     sf;
    int     cr;
    long    bw;
    int     power;
    int     syncWord;
    bool    cadActive;
};

class MqttCfg {
public:
    bool    active;
    String  server;
    int     port;           // default 1883
    String  username;
    String  password;
    String  clientId;
};

class Sensors {
public:
    bool    bme280;
    bool    mq135;
    bool    rain;
    bool    anemo;
    bool    tilt;
    bool    ads1115;
    bool    epever;
    bool    gps;
    int     intervalSec;    // node send interval, default 60
};

class Siren {
public:
    bool    enabled;
    int     missThresholdSec;   // gateway node-missing detection, default 180
};

class Thresholds {
public:
    double  tiltSiaga;
    double  tiltAwas;
};

class Display {
public:
    bool    enabled;
    int     timeout;
    bool    turn180;
};

class Configuration {
public:
    Identity                    identity;
    std::vector<WiFi_AP>        wifiAPs;
    WiFi_Auto_AP                wifiAutoAP;
    LoRaCfg                     lora;
    MqttCfg                     mqtt;
    Sensors                     sensors;
    Siren                       siren;
    Thresholds                  thresholds;
    Display                     display;

    void    setup();
    void    setDefaultValues();
    bool    writeFile();

private:
    bool    readFile();
    const char* _filePath = "/ews_conf.json";
};

#endif // CONFIGURATION_H
