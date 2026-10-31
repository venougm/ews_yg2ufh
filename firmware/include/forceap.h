#ifndef FORCEAP_H
#define FORCEAP_H

#include <Preferences.h>

// One-shot "force AP" flag persisted in NVS via the ESP32-core Preferences
// library (namespace "ews", key "forceAp"). Holding the USER button (IO38) for
// ~3 s sets this flag and reboots; setup() reads-and-clears it to route into a
// temporary AP config mode regardless of saved WiFi. No new library is used.
namespace ForceAp {

    static const char* NS  = "ews";
    static const char* KEY = "forceAp";

    // Persist the one-shot request, then the caller ESP.restart()s.
    inline void request() {
        Preferences prefs;
        prefs.begin(NS, false);          // read/write
        prefs.putBool(KEY, true);
        prefs.end();
    }

    // Read the flag and, if set, clear it (one-shot). Returns its previous value.
    inline bool take() {
        Preferences prefs;
        prefs.begin(NS, false);          // read/write (need to clear)
        bool forced = prefs.getBool(KEY, false);
        if (forced) prefs.remove(KEY);
        prefs.end();
        return forced;
    }

}

#endif // FORCEAP_H
