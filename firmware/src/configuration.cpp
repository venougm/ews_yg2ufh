#include <ArduinoJson.h>
#include <SPIFFS.h>
#include "configuration.h"
#include "board_pinout.h"

// Load/save EWS config JSON on SPIFFS. Mirrors CA2RXU configuration.cpp:
//   - SPIFFS.begin(false) then (true) format fallback
//   - no config file -> setDefaultValues() + writeFile() + restart
//   - readFile() with a needsRewrite flag: any missing/null field triggers a
//     rewrite + restart so the on-flash config always matches the struct schema.

bool Configuration::writeFile() {
    Serial.println("Saving configuration...");

    JsonDocument data;
    File configFile = SPIFFS.open(_filePath, "w");

    if (!configFile) {
        Serial.println("Error: Could not open config file for writing");
        return false;
    }

    data["identity"]["role"]            = identity.role;
    data["identity"]["nodeId"]          = identity.nodeId;
    data["identity"]["networkId"]       = identity.networkId;
    data["identity"]["provinsi"]        = identity.provinsi;
    data["identity"]["kabupaten"]       = identity.kabupaten;
    data["identity"]["kecamatan"]       = identity.kecamatan;
    data["identity"]["kelurahan"]       = identity.kelurahan;
    data["identity"]["locationName"]    = identity.locationName;
    data["identity"]["latitude"]        = identity.latitude;
    data["identity"]["longitude"]       = identity.longitude;

    if (wifiAPs.size() > 0 && wifiAPs[0].ssid != "") { // don't save the empty Auto-AP placeholder SSID
        for (size_t i = 0; i < wifiAPs.size(); i++) {
            data["wifi"]["AP"][i]["ssid"]       = wifiAPs[i].ssid;
            data["wifi"]["AP"][i]["password"]   = wifiAPs[i].password;
        }
    }

    data["wifi"]["autoAP"]["enabled"]       = wifiAutoAP.enabled;
    data["wifi"]["autoAP"]["apPassword"]    = wifiAutoAP.apPassword;
    data["wifi"]["autoAP"]["timeout"]       = wifiAutoAP.timeout;

    data["lora"]["freq"]                = lora.freq;
    data["lora"]["sf"]                  = lora.sf;
    data["lora"]["cr"]                  = lora.cr;
    data["lora"]["bw"]                  = lora.bw;
    data["lora"]["power"]               = lora.power;
    data["lora"]["syncWord"]            = lora.syncWord;
    data["lora"]["cadActive"]           = lora.cadActive;

    data["mqtt"]["active"]              = mqtt.active;
    data["mqtt"]["server"]              = mqtt.server;
    data["mqtt"]["port"]                = mqtt.port;
    data["mqtt"]["username"]            = mqtt.username;
    data["mqtt"]["password"]            = mqtt.password;
    data["mqtt"]["clientId"]            = mqtt.clientId;

    data["sensors"]["bme280"]           = sensors.bme280;
    data["sensors"]["mq135"]            = sensors.mq135;
    data["sensors"]["rain"]             = sensors.rain;
    data["sensors"]["anemo"]            = sensors.anemo;
    data["sensors"]["tilt"]             = sensors.tilt;
    data["sensors"]["ads1115"]          = sensors.ads1115;
    data["sensors"]["epever"]           = sensors.epever;
    data["sensors"]["gps"]              = sensors.gps;
    data["sensors"]["intervalSec"]      = sensors.intervalSec;

    data["siren"]["enabled"]            = siren.enabled;
    data["siren"]["missThresholdSec"]   = siren.missThresholdSec;

    data["thresholds"]["tiltSiaga"]     = thresholds.tiltSiaga;
    data["thresholds"]["tiltAwas"]      = thresholds.tiltAwas;

    data["display"]["enabled"]          = display.enabled;
    data["display"]["timeout"]          = display.timeout;
    data["display"]["turn180"]          = display.turn180;

    serializeJson(data, configFile);
    configFile.close();
    return true;
}

bool Configuration::readFile() {
    Serial.println("Reading config..");
    File configFile = SPIFFS.open(_filePath, "r");

    if (!configFile) {
        Serial.println("Config file not found");
        return false;
    }

    bool needsRewrite = false;
    JsonDocument data;
    DeserializationError error = deserializeJson(data, configFile);
    if (error) {
        Serial.println("Failed to read file, using default configuration");
    }

    if (data["identity"]["role"].isNull() ||
        data["identity"]["nodeId"].isNull() ||
        data["identity"]["networkId"].isNull() ||
        data["identity"]["provinsi"].isNull() ||
        data["identity"]["kabupaten"].isNull() ||
        data["identity"]["kecamatan"].isNull() ||
        data["identity"]["kelurahan"].isNull() ||
        data["identity"]["locationName"].isNull() ||
        data["identity"]["latitude"].isNull() ||
        data["identity"]["longitude"].isNull()) needsRewrite = true;
    identity.role           = data["identity"]["role"] | 0;
    identity.nodeId         = data["identity"]["nodeId"] | "";
    identity.networkId      = data["identity"]["networkId"] | "ews1";
    identity.provinsi       = data["identity"]["provinsi"] | "";
    identity.kabupaten      = data["identity"]["kabupaten"] | "";
    identity.kecamatan      = data["identity"]["kecamatan"] | "";
    identity.kelurahan      = data["identity"]["kelurahan"] | "";
    identity.locationName   = data["identity"]["locationName"] | "";
    identity.latitude       = data["identity"]["latitude"] | 0.0;
    identity.longitude      = data["identity"]["longitude"] | 0.0;

    JsonArray WiFiArray = data["wifi"]["AP"];
    for (size_t i = 0; i < WiFiArray.size(); i++) {
        WiFi_AP wifiap;
        wifiap.ssid     = WiFiArray[i]["ssid"].as<String>();
        wifiap.password = WiFiArray[i]["password"].as<String>();
        wifiAPs.push_back(wifiap);
    }

    if (data["wifi"]["autoAP"]["enabled"].isNull() ||
        data["wifi"]["autoAP"]["apPassword"].isNull() ||
        data["wifi"]["autoAP"]["timeout"].isNull()) needsRewrite = true;
    wifiAutoAP.enabled      = data["wifi"]["autoAP"]["enabled"] | true;
    wifiAutoAP.apPassword   = data["wifi"]["autoAP"]["apPassword"] | "1234567890";
    wifiAutoAP.timeout      = data["wifi"]["autoAP"]["timeout"] | 10;

    if (data["lora"]["freq"].isNull() ||
        data["lora"]["sf"].isNull() ||
        data["lora"]["cr"].isNull() ||
        data["lora"]["bw"].isNull() ||
        data["lora"]["power"].isNull() ||
        data["lora"]["syncWord"].isNull() ||
        data["lora"]["cadActive"].isNull()) needsRewrite = true;
    lora.freq               = data["lora"]["freq"] | 915000000;
    lora.sf                 = data["lora"]["sf"] | 9;
    lora.cr                 = data["lora"]["cr"] | 5;
    lora.bw                 = data["lora"]["bw"] | 125000;
    lora.power              = data["lora"]["power"] | 20;
    lora.syncWord           = data["lora"]["syncWord"] | 0x12;
    lora.cadActive          = data["lora"]["cadActive"] | false;

    if (data["mqtt"]["active"].isNull() ||
        data["mqtt"]["server"].isNull() ||
        data["mqtt"]["port"].isNull() ||
        data["mqtt"]["username"].isNull() ||
        data["mqtt"]["password"].isNull() ||
        data["mqtt"]["clientId"].isNull()) needsRewrite = true;
    mqtt.active             = data["mqtt"]["active"] | false;
    mqtt.server             = data["mqtt"]["server"] | "";
    mqtt.port               = data["mqtt"]["port"] | 1883;
    mqtt.username           = data["mqtt"]["username"] | "";
    mqtt.password           = data["mqtt"]["password"] | "";
    mqtt.clientId           = data["mqtt"]["clientId"] | "";

    if (data["sensors"]["bme280"].isNull() ||
        data["sensors"]["mq135"].isNull() ||
        data["sensors"]["rain"].isNull() ||
        data["sensors"]["anemo"].isNull() ||
        data["sensors"]["tilt"].isNull() ||
        data["sensors"]["ads1115"].isNull() ||
        data["sensors"]["epever"].isNull() ||
        data["sensors"]["gps"].isNull() ||
        data["sensors"]["intervalSec"].isNull()) needsRewrite = true;
    sensors.bme280          = data["sensors"]["bme280"] | false;
    sensors.mq135           = data["sensors"]["mq135"] | false;
    sensors.rain            = data["sensors"]["rain"] | false;
    sensors.anemo           = data["sensors"]["anemo"] | false;
    sensors.tilt            = data["sensors"]["tilt"] | false;
    sensors.ads1115         = data["sensors"]["ads1115"] | false;
    sensors.epever          = data["sensors"]["epever"] | false;
    sensors.gps             = data["sensors"]["gps"] | false;
    sensors.intervalSec     = data["sensors"]["intervalSec"] | 60;

    if (data["siren"]["enabled"].isNull() ||
        data["siren"]["missThresholdSec"].isNull()) needsRewrite = true;
    siren.enabled           = data["siren"]["enabled"] | false;
    siren.missThresholdSec  = data["siren"]["missThresholdSec"] | 180;

    if (data["thresholds"]["tiltSiaga"].isNull() ||
        data["thresholds"]["tiltAwas"].isNull()) needsRewrite = true;
    thresholds.tiltSiaga    = data["thresholds"]["tiltSiaga"] | 5.0;
    thresholds.tiltAwas     = data["thresholds"]["tiltAwas"] | 10.0;

    if (data["display"]["enabled"].isNull() ||
        data["display"]["timeout"].isNull() ||
        data["display"]["turn180"].isNull()) needsRewrite = true;
    display.enabled         = data["display"]["enabled"] | true;
    display.timeout         = data["display"]["timeout"] | 0;
    display.turn180         = data["display"]["turn180"] | false;

    if (wifiAPs.size() == 0) { // keep an empty placeholder so Auto-AP has a slot
        WiFi_AP wifiap;
        wifiap.ssid = "";
        wifiap.password = "";
        wifiAPs.push_back(wifiap);
    }
    configFile.close();

    if (needsRewrite) {
        Serial.println("Config JSON incomplete, rewriting...");
        writeFile();
        delay(1000);
        ESP.restart();
    }
    Serial.println("Config read successfully");
    return true;
}

void Configuration::setDefaultValues() {
    identity.role           = 0;        // NODE
    identity.nodeId         = "";
    identity.networkId      = "ews1";
    identity.provinsi       = "";
    identity.kabupaten      = "";
    identity.kecamatan      = "";
    identity.kelurahan      = "";
    identity.locationName   = "";
    identity.latitude       = 0.0;
    identity.longitude      = 0.0;

    WiFi_AP wifiap;
    wifiap.ssid             = "";
    wifiap.password         = "";
    wifiAPs.push_back(wifiap);

    wifiAutoAP.enabled      = true;
    wifiAutoAP.apPassword   = "1234567890";
    wifiAutoAP.timeout      = 10;

    lora.freq               = 915000000;
    lora.sf                 = 9;
    lora.cr                 = 5;
    lora.bw                 = 125000;
    lora.power              = 20;
    lora.syncWord           = 0x12;
    lora.cadActive          = false;

    mqtt.active             = false;
    mqtt.server             = "";
    mqtt.port               = 1883;
    mqtt.username           = "";
    mqtt.password           = "";
    mqtt.clientId           = "";

    sensors.bme280          = false;
    sensors.mq135           = false;
    sensors.rain            = false;
    sensors.anemo           = false;
    sensors.tilt            = false;
    sensors.ads1115         = false;
    sensors.epever          = false;
    sensors.gps             = false;
    sensors.intervalSec     = 60;

    siren.enabled           = false;
    siren.missThresholdSec  = 180;

    thresholds.tiltSiaga    = 5.0;
    thresholds.tiltAwas     = 10.0;

    display.enabled         = true;
    display.timeout         = 0;
    display.turn180         = false;

    Serial.println("New Data Created... All is Written!");
}

void Configuration::setup() {
    if (!SPIFFS.begin(false)) {
        Serial.println("SPIFFS Mount Failed, formatting...");
        if (!SPIFFS.begin(true)) {
            Serial.println("SPIFFS Format Failed");
            return;
        }
    }
    Serial.println("SPIFFS Ready");

    if (!SPIFFS.exists(_filePath)) {
        Serial.println("Config not found, creating default...");
        setDefaultValues();
        writeFile();
        delay(1000);
        ESP.restart();
    }

    readFile();
}
