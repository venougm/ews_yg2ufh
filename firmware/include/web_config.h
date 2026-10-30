#ifndef WEB_CONFIG_H
#define WEB_CONFIG_H

#include <Arduino.h>

// AP-mode web configuration server (FEAT-004): a plain WebServer (from the
// Arduino core) serving a sectioned HTML settings form from SPIFFS plus a
// small JSON API.
//
//   GET  /                -> index.html (AP: setup form; STA: status page)
//   GET  /api/config      -> current Configuration as JSON
//   GET  /api/wilayah     -> the wilayah.json tree (cascading dropdown source)
//   POST /api/config      -> validate, Config.writeFile(), reply, reboot to client
//
// The UI layout/theme mirror docs/mockup/device-setup.html (AP) and
// docs/mockup/device-status.html (client). Wilayah fields are cascading
// <select> dropdowns (anti-typo) whose submitted values are lowercase slugs.
namespace WebConfig {
    void setup();   // mount routes + begin() the server (call once in AP mode)
    void loop();    // service HTTP clients (call from the main loop in AP mode)
}

#endif // WEB_CONFIG_H
