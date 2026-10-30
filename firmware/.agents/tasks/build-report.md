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
