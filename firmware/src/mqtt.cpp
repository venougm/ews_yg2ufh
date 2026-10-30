#include <WiFi.h>
#include <PubSubClient.h>
#include "configuration.h"
#include "mqtt.h"

// PubSubClient MQTT with EWS native-JSON topics + Last Will. Topic base uses the
// kabupaten slug + node_id (kelurahan is JSON-only, never in the topic).

extern Configuration Config;

namespace {
    WiFiClient wifiClient;
    PubSubClient client(wifiClient);
    MQTT_Utils::SirenCmdCallback sirenCb = nullptr;

    String b;   // cached base topic, built in setup()

    String tStatus()     { return b + "/status"; }
    String tData()       { return b + "/data"; }
    String tSirenState() { return b + "/siren/state"; }
    String tSirenCmd()   { return b + "/siren/cmd"; }

    // Effective client id: configured value, else derived from the node id.
    String clientId() {
        if (Config.mqtt.clientId != "") return Config.mqtt.clientId;
        if (Config.identity.nodeId != "") return "ews-" + Config.identity.nodeId;
        return "ews-node";
    }

    void onMessage(char* topic, byte* payload, unsigned int length) {
        String t(topic);
        String msg;
        msg.reserve(length);
        for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];

        if (t == tSirenCmd() && sirenCb) {
            sirenCb(msg);
        }
    }
}

namespace MQTT_Utils {

    String baseTopic() { return b; }

    void setup() {
        b = "yg2ufh/ews/" + Config.identity.kabupaten + "/" + Config.identity.nodeId;

        client.setServer(Config.mqtt.server.c_str(), Config.mqtt.port);
        client.setBufferSize(1024);     // fat JSON doesn't fit the default 256 bytes
        client.setCallback(onMessage);
    }

    bool connect() {
        if (!Config.mqtt.active) return false;
        if (client.connected()) return true;

        String cid = clientId();
        String willTopic = tStatus();

        bool ok;
        if (Config.mqtt.username != "") {
            // connect(id, user, pass, willTopic, willQos, willRetain, willMsg)
            ok = client.connect(cid.c_str(),
                                Config.mqtt.username.c_str(),
                                Config.mqtt.password.c_str(),
                                willTopic.c_str(), 0, true, "offline");
        } else {
            ok = client.connect(cid.c_str(),
                                willTopic.c_str(), 0, true, "offline");
        }

        if (ok) {
            Serial.println("MQTT connected");
            publishStatus("online");
            client.subscribe(tSirenCmd().c_str());
        } else {
            Serial.print("MQTT connect failed, state ");
            Serial.println(client.state());
        }
        return ok;
    }

    void loop() {
        if (!Config.mqtt.active) return;
        if (!client.connected()) {
            connect();
            return;
        }
        client.loop();
    }

    bool isConnected() {
        return client.connected();
    }

    void publishData(const String& json) {
        if (!client.connected()) return;
        client.publish(tData().c_str(), json.c_str(), false);   // retained=false
    }

    void publishStatus(const char* status) {
        if (!client.connected()) return;
        client.publish(tStatus().c_str(), status, true);        // retained
    }

    void publishSirenState(const char* state) {
        if (!client.connected()) return;
        client.publish(tSirenState().c_str(), state, true);     // retained
    }

    void onSirenCmd(SirenCmdCallback cb) {
        sirenCb = cb;
    }

}
