# Build Report — EWS T-Beam firmware

## FEAT-002 (transport layer) — items 4, 5, 6, 7

Command:
`python -m platformio run -e ttgo-t-beam-ews -d c:\aws-kiro\EWS_YG2UFH\.worktrees\ews-firmware\firmware`

Result: **SUCCESS, 0 errors.**

- RAM:  3.6% (46880 / 1310720 bytes)
- Flash: 46.6% (916917 / 1966080 bytes)
- Took ~65 s.

Dependency graph linked cleanly: RadioLib 7.8.1, ArduinoJson 7.4.3,
PubSubClient 2.8.0, Adafruit BME280/ADS1X15/SSD1306/GFX/Unified Sensor,
ModbusMaster, XPowersLib, TinyGPSPlus.

What landed:
- Item 4 (wifi_manager): already present and wired into main.cpp — STA connect
  with softAP fallback (EWS-<nodeId> / YG2UFH-EWS-Setup, AP pass from config,
  192.168.4.1), checkWiFi() ~30s, isConnected()/isApMode(). No change needed.
- Item 5 (ews_packet): compact minimal-JSON codec with header n/d/s/t and
  short-key bodies. DATA and JOIN both carry kab/kec/kel slugs. Format documented
  in include/ews_packet.h. buildData/buildJoin/buildAck/buildCmd + parse().
- Item 6 (lora): RadioLib SX1276 = new Module(RADIO_CS_PIN, RADIO_DIO0_PIN,
  RADIO_RST_PIN), setDio0Action, freq/SF/CR/BW/power/syncWord from config, optional
  CAD, transmit() with NO APRS prefix, receive() -> payload + RSSI/SNR. SPI.begin
  with board pins.
- Item 7 (mqtt): PubSubClient over WiFiClient, setBufferSize(1024), connect with
  clientId (+optional user/pass) and Last Will offline retained on the status
  topic, publishData (retained=false), publishStatus/publishSirenState retained,
  subscribe siren/cmd. Topic base uses the kabupaten slug + node_id (kelurahan is
  JSON-payload only, not in the topic).

Fixes applied to get a clean build:
- platformio.ini: added `-D RADIOLIB_EXCLUDE_RFM2X=1` (RadioLib 7.8.1 aliases
  RFM22/RFM23 to Si4432/Si4431, which were already excluded, breaking compile).
- lora.cpp: used the byte-buffer transmit overload because RadioLib's
  `transmit(String&)` takes a non-const reference and the payload is const.

## FEAT-003 (sensor HAL + siren + node/gateway roles) — items 8, 9, 10, 11, 13

Command:
`python -m platformio run -e ttgo-t-beam-ews -d c:\aws-kiro\EWS_YG2UFH\.worktrees\ews-firmware\firmware`

Result: **SUCCESS, 0 errors.**

- RAM:   3.7% (47912 / 1310720 bytes)
- Flash: 49.0% (963401 / 1966080 bytes)
- Took ~67 s.

What landed:
- Item 8 (sensors): per-flag readers behind Config.sensors.* — BME280 (Adafruit,
  I2C) -> weather; ADS1115 battery/PV via divider math (GAIN_ONE LSB * divider)
  -> power; EPEVER Tracer over RS485 (ModbusMaster on UART2 + DE/RE on
  RS485_DERE_PIN, input registers 0x3100 PV V / 0x3104 batt V / 0x310C load A /
  0x311A SOC) -> power; rain + anemometer pulse ISRs (FALLING, pull-up) ->
  rain mm / wind Hz; MQ-135 analogRead -> air raw; GPS TinyGPSPlus on Serial1
  (9600) fed from loop(). readEnabled() sets each group's `present` flag only for
  enabled sensors.
- Item 9 (siren): MCP23017 driven over I2C with a tiny inline register helper
  (IODIRA/B, GPPUB, OLATA shadow) — no extra lib. setSiren() is MANUAL-ONLY with
  a prominent invariant comment; it is reached only from handleCmd(), which the
  MQTT siren/cmd callback invokes. handleCmd() accepts "ON" / "OFF" / "PATTERN:x".
  Relay + ALARM LED start de-energized at boot.
- Item 10 (node): every Config.sensors.intervalSec reads enabled sensors; if
  WiFi+MQTT up publishes fat JSON directly, else builds a compact DATA packet and
  LoRa-transmits. JOIN sent on boot with the active sensor short-key list. Fat
  JSON includes only enabled groups and carries the full location hierarchy
  INCLUDING `kelurahan` alongside provinsi/kabupaten/kecamatan, plus
  health.uptime/rssi/fw — mirrors the experiment sketch field mapping.
- Item 11 (gateway): LoRa RX -> parse -> on DATA expand the compact packet into
  fat MQTT JSON (fills kabupaten/kecamatan/kelurahan from the packet, falling back
  to the JOIN registration table; kelurahan carried through to the published
  JSON) and publishes to the node's data topic; on JOIN registers the node;
  last_seen[node]-based node-missing detection -> publishes status offline past
  missThresholdSec and online when heard again; subscribes + acts on each node's
  siren/cmd (-> Siren_Utils::handleCmd + publishes siren/state). Health
  rssi/snr/uptime/fw added to each relayed reading.
- Item 13 (main role dispatch): AP mode -> web_config placeholder (FEAT-004); else
  Node or Gateway by Config.identity.role (jumper IGNORED). LoRa init always in
  STA mode; MQTT configured in STA mode, connect deferred until WiFi is up.

Supporting changes:
- mqtt.h/.cpp: added gateway-side helpers (nodeBaseTopic, publishTo, subscribe,
  onRawMessage) so the gateway can publish/subscribe for arbitrary node topics.
- configuration.h: added EWS_FW_VERSION ("0.1.0") for the health.fw field.

No new build fixes were required beyond the FEAT-002 ones; the build was green on
the first run after the new modules were added.
