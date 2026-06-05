#!/usr/bin/env python3
"""
Push Nagios-labelled Grafana dashboards to the standalone Grafana instance (port 5000).
Datasource: datasource-nagios -> prometheus-mqtt-prometheus-1:9090
"""
import json, sys
import urllib.request, urllib.error

GRAFANA_URL = "http://localhost:5000"
GRAFANA_AUTH = ("admin", "admin")
DS = {"type": "prometheus", "uid": "datasource-nagios"}

def api(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{GRAFANA_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    import base64
    creds = base64.b64encode(b"admin:admin").decode()
    req.add_header("Authorization", f"Basic {creds}")
    try:
        with urllib.request.urlopen(req) as r:
            resp = json.load(r)
            print(f"  {path}: {resp.get('status','ok')} uid={resp.get('uid','')}")
    except urllib.error.HTTPError as e:
        print(f"  ERROR {path}: {e.code} {e.read().decode()}")


# ── Shared helpers ────────────────────────────────────────────────────────────

def stat(id, title, expr, unit, steps, w, x, y, h=4, graph="none", legend="{{site}}"):
    return {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "thresholds": {"mode": "absolute", "steps": steps},
                "unit": unit,
                "mappings": [],
            }, "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "colorMode": "background", "graphMode": graph,
            "justifyMode": "auto", "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "auto",
        },
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": legend, "refId": "A"}],
        "title": title, "type": "stat",
    }


def timeseries(id, title, expr, unit, steps, w, x, y, h=9):
    return {
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "drawStyle": "line", "fillOpacity": 10, "lineInterpolation": "smooth",
                    "lineWidth": 2, "pointSize": 5, "showPoints": "never",
                    "spanNulls": False, "axisCenteredZero": False, "axisColorMode": "text",
                    "axisPlacement": "auto", "barAlignment": 0, "gradientMode": "none",
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "scaleDistribution": {"type": "linear"},
                    "stacking": {"group": "A", "mode": "none"},
                    "thresholdsStyle": {"mode": "line"},
                },
                "thresholds": {"mode": "absolute", "steps": steps},
                "unit": unit, "mappings": [],
            }, "overrides": []
        },
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "id": id,
        "options": {
            "legend": {"calcs": ["lastNotNull", "min", "max"], "displayMode": "table",
                       "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "none"},
        },
        "targets": [{"datasource": DS, "expr": expr, "legendFormat": "{{site}}", "refId": "A"}],
        "title": title, "type": "timeseries",
    }


def row(id, title, y):
    return {"collapsed": False, "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
            "id": id, "title": title, "type": "row"}


# ── Dashboard 1: IoT Sensors (Nagios) ────────────────────────────────────────

TEMP_STEPS  = [{"color":"blue","value":None},{"color":"green","value":12},
               {"color":"yellow","value":20},{"color":"red","value":25}]
POWER_STEPS = [{"color":"green","value":None},{"color":"yellow","value":350},
               {"color":"red","value":400}]
HUM_STEPS   = [{"color":"green","value":None},{"color":"yellow","value":70},
               {"color":"red","value":85}]
COUNT_STEPS = [{"color":"green","value":None},{"color":"yellow","value":1},
               {"color":"red","value":3}]

sensors_dashboard = {
    "id": None, "uid": "nagios-iot-sensors",
    "title": "IoT Sensor Lab — M6 Corridor (Nagios)",
    "description": "MQTT sensor metrics via Prometheus — M6 corridor sites (Nagios lab)",
    "tags": ["datasource-nagios", "mqtt", "iot", "nagios"],
    "refresh": "30s", "schemaVersion": 38, "graphTooltip": 1,
    "time": {"from": "now-1h", "to": "now"}, "timepicker": {}, "timezone": "browser",
    "annotations": {"list": []}, "links": [],
    "panels": [
        row(20, "Fleet Summary", 0),
        stat(21, "Avg Temperature",
             'avg(mqtt_consumer_value{metric_type="temp"})',
             "celsius", TEMP_STEPS, 4, 0, 1, graph="area", legend="Avg °C"),
        stat(22, "Max Temperature",
             'max(mqtt_consumer_value{metric_type="temp"})',
             "celsius", TEMP_STEPS, 4, 4, 1, legend="Max °C"),
        stat(23, "Sites > 21 °C",
             'count(mqtt_consumer_value{metric_type="temp"} > 21) or vector(0)',
             "short", COUNT_STEPS, 4, 8, 1, legend="Sites"),
        stat(24, "Avg Power",
             'avg(mqtt_consumer_value{metric_type="power"})',
             "watt", POWER_STEPS, 4, 12, 1, graph="area", legend="Avg W"),
        stat(25, "Max Power",
             'max(mqtt_consumer_value{metric_type="power"})',
             "watt", POWER_STEPS, 4, 16, 1, legend="Max W"),
        stat(26, "Sites > 400 W",
             'count(mqtt_consumer_value{metric_type="power"} > 400) or vector(0)',
             "short", COUNT_STEPS, 4, 20, 1, legend="Sites"),

        row(1, "Current Values", 5),
        stat(2, "Temperature by Site",
             'mqtt_consumer_value{metric_type="temp"}',
             "celsius", TEMP_STEPS, 8, 0, 6, h=8),
        stat(3, "Power by Site",
             'mqtt_consumer_value{metric_type="power"}',
             "watt", POWER_STEPS, 8, 8, 6, h=8),
        stat(4, "Humidity by Site",
             'mqtt_consumer_value{metric_type="humidity"}',
             "percent", HUM_STEPS, 8, 16, 6, h=8),

        row(5, "Time Series", 14),
        timeseries(6, "Temperature — All Sites",
                   'mqtt_consumer_value{metric_type="temp"}', "celsius", TEMP_STEPS, 12, 0, 15),
        timeseries(7, "Power — All Sites",
                   'mqtt_consumer_value{metric_type="power"}', "watt", POWER_STEPS, 12, 12, 15),
        timeseries(8, "Humidity — All Sites",
                   'mqtt_consumer_value{metric_type="humidity"}', "percent", HUM_STEPS, 12, 0, 24),

        {   # bar chart — top 10 by power
            "datasource": DS,
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "custom": {"fillOpacity": 80, "gradientMode": "none",
                               "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                               "lineWidth": 1},
                    "thresholds": {"mode": "absolute", "steps": POWER_STEPS},
                    "unit": "watt", "mappings": [],
                }, "overrides": []
            },
            "gridPos": {"h": 9, "w": 12, "x": 12, "y": 24}, "id": 9,
            "options": {
                "barRadius": 0.03, "barWidth": 0.8, "fullHighlight": False,
                "groupWidth": 0.7, "orientation": "auto", "stacking": "none",
                "legend": {"calcs": ["lastNotNull"], "displayMode": "list",
                           "placement": "bottom", "showLegend": True},
                "tooltip": {"mode": "single", "sort": "desc"},
                "xTickLabelRotation": -45, "xTickLabelSpacing": 0,
            },
            "targets": [{"datasource": DS,
                         "expr": 'topk(10, mqtt_consumer_value{metric_type="power"})',
                         "legendFormat": "{{site}}", "instant": True,
                         "refId": "A", "format": "table"}],
            "title": "Top 10 Sites by Power (current)", "type": "barchart",
        },
    ],
}

# ── Dashboard 2: Nagios Service Health ───────────────────────────────────────

ALERT_STEPS = [{"color":"green","value":None},{"color":"yellow","value":1},
               {"color":"red","value":5}]
OK_STEPS    = [{"color":"red","value":None},{"color":"yellow","value":30},
               {"color":"green","value":44}]

health_dashboard = {
    "id": None, "uid": "nagios-service-health",
    "title": "Nagios Service Health — M6 Corridor",
    "description": "Nagios passive check service health derived from MQTT telemetry thresholds",
    "tags": ["datasource-nagios", "nagios", "health"],
    "refresh": "30s", "schemaVersion": 38, "graphTooltip": 1,
    "time": {"from": "now-1h", "to": "now"}, "timepicker": {}, "timezone": "browser",
    "annotations": {"list": []}, "links": [],
    "panels": [
        row(10, "Threshold Breach Summary", 0),

        stat(11, "Temp Sites in WARNING",
             'count(mqtt_consumer_value{metric_type="temp"} >= 20 and '
             'mqtt_consumer_value{metric_type="temp"} < 22) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"yellow","value":1}],
             4, 0, 1, legend="Sites"),
        stat(12, "Temp Sites CRITICAL (≥22°C)",
             'count(mqtt_consumer_value{metric_type="temp"} >= 22) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"red","value":1}],
             4, 4, 1, legend="Sites"),
        stat(13, "Power Sites in WARNING",
             'count(mqtt_consumer_value{metric_type="power"} >= 390 and '
             'mqtt_consumer_value{metric_type="power"} < 415) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"yellow","value":1}],
             4, 8, 1, legend="Sites"),
        stat(14, "Power Sites CRITICAL (≥415W)",
             'count(mqtt_consumer_value{metric_type="power"} >= 415) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"red","value":1}],
             4, 12, 1, legend="Sites"),
        stat(15, "Humidity Sites in WARNING",
             'count(mqtt_consumer_value{metric_type="humidity"} >= 75 and '
             'mqtt_consumer_value{metric_type="humidity"} < 85) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"yellow","value":1}],
             4, 16, 1, legend="Sites"),
        stat(16, "Humidity Sites CRITICAL (≥85%)",
             'count(mqtt_consumer_value{metric_type="humidity"} >= 85) or vector(0)',
             "short", [{"color":"green","value":None},{"color":"red","value":1}],
             4, 20, 1, legend="Sites"),

        row(17, "Per-Metric Breach Timeline", 5),
        timeseries(18, "Temperature — Threshold Lines (WARN 20°C / CRIT 22°C)",
                   'mqtt_consumer_value{metric_type="temp"}', "celsius",
                   [{"color":"green","value":None},{"color":"yellow","value":20},
                    {"color":"red","value":22}], 24, 0, 6, h=9),
        timeseries(19, "Power — Threshold Lines (WARN 390W / CRIT 415W)",
                   'mqtt_consumer_value{metric_type="power"}', "watt",
                   [{"color":"green","value":None},{"color":"yellow","value":390},
                    {"color":"red","value":415}], 24, 0, 15, h=9),
    ],
}


# ── Post both dashboards ──────────────────────────────────────────────────────

for db in [sensors_dashboard, health_dashboard]:
    print(f"Posting: {db['title']}")
    api("/api/dashboards/db", {
        "dashboard": db,
        "overwrite": True,
        "folderId": 0,
        "message": "provisioned by nagios-mqtt",
    })

print("Done.")
