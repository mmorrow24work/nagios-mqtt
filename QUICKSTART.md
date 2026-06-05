# QUICKSTART — Nagios MQTT Monitoring Lab

Full step-by-step setup from a fresh clone to a live Nagios dashboard with 15 simulated MQTT sensor sites.

---

## Prerequisites

- Docker + Docker Compose
- GitHub CLI (`gh auth login` completed)
- Port 8088 free (Nagios web UI)
- Port 1884 free (Mosquitto MQTT — uses 1884 to avoid clashing with other stacks)

---

## 1. Clone the repo

```bash
gh repo clone mmorrow24work/nagios-mqtt ~/git/nagios-mqtt
cd ~/git/nagios-mqtt
```

---

## 2. Start the stack

```bash
docker compose up -d --build
```

The first run builds the custom Nagios image (enables Apache form auth modules) and the sidecar image. Subsequent starts are fast.

Verify all containers are up:

```bash
docker compose ps
```

Expected:

```
NAME                        IMAGE                STATUS
nagios-mqtt-mqtt-broker-1   eclipse-mosquitto:2  Up
nagios-mqtt-nagios-1        nagios-mqtt-nagios   Up
nagios-mqtt-publisher-1     alpine:3.20          Up
nagios-mqtt-sidecar-1       nagios-mqtt-sidecar  Up
```

---

## 3. Wait for site discovery (~30s)

Watch the sidecar auto-provision all 15 sites:

```bash
docker compose logs -f sidecar
```

You should see:

```
INFO Waiting for Nagios command pipe at /opt/nagios/var/rw/nagios.cmd
INFO Nagios command pipe is ready
INFO Connected to MQTT broker mqtt-broker:1883
INFO Subscribed to lab/#
INFO Created config for site1 at /opt/nagios/etc/conf.d/site1.cfg
INFO Reloading Nagios config in container ... (service=nagios)
INFO Nagios config reloaded
INFO Created config for site2 at /opt/nagios/etc/conf.d/site2.cfg
...
INFO Created config for site15 at /opt/nagios/etc/conf.d/site15.cfg
```

Once all 15 sites appear, Ctrl-C out of the log tail.

---

## 4. Log in to Nagios

Open **http://localhost:8088/nagios/**

| Credential | Value |
|---|---|
| Username | `nagiosadmin` |
| Password | `nagios` |

> Chrome and Edge suppress HTTP Basic Auth dialogs. This stack uses Apache form-based login — a standard HTML form is served at `/nagios/login.html` and works in all browsers.

---

## 5. Verify services are OK

Navigate to **Current Status → Services** (or click *Service Detail* in the left sidebar).

You should see 15 hosts (`site1` – `site15`), each with 3 services:

| Service | Expected status | Example value |
|---|---|---|
| Temperature | OK | `OK: 14.0C` |
| Humidity | OK | `OK: 65.0%` |
| Power | OK | `OK: 295.8W` |

The **Tactical Overview** (`tac.cgi`) gives a quick health summary — 45 passive service checks all green.

---

## 6. Verify raw MQTT data

```bash
# Subscribe and watch live sensor messages
docker exec nagios-mqtt-mqtt-broker-1 mosquitto_sub -h localhost -t 'lab/#' -v -C 20
```

You'll see a stream of:

```
lab/temp/site1 14.0
lab/humidity/site1 65.0
lab/power/site1 295.8
lab/location/site1 51.5278,-0.1330
lab/discovery [{"#{SITE}":"site1"},...]
...
```

---

## 7. Grafana dashboards

Three dashboards are available on the standalone Grafana instance (port 5000), reading from the `datasource-nagios` Prometheus datasource at port 9090.

> **Prerequisite:** The [prometheus-mqtt](https://github.com/mmorrow24work/prometheus-mqtt) stack must be running (provides Prometheus at port 9090 and Grafana at port 3000).

### Provision dashboards

```bash
python3 scripts/provision_grafana_dashboards.py
```

This creates or restores all three dashboards. Re-run any time after a Grafana data volume wipe.

### Dashboard URLs

| Dashboard | URL |
|---|---|
| IoT Sensor Lab — M6 Corridor (Nagios) | http://localhost:5000/d/nagios-iot-sensors/ |
| Nagios Service Health — M6 Corridor | http://localhost:5000/d/nagios-service-health/ |
| IoT Sensor Lab (Nagios) — Operational Insights | http://localhost:5000/d/nagios-iot-showcase/ |

### IoT Sensor Lab — M6 Corridor (Nagios)

Fleet summary stats, current values per site, time-series for all three metrics, top-10 power bar chart.

![IoT Sensors Dashboard](docs/screenshots/grafana-iot-sensors.png)

### Nagios Service Health — M6 Corridor

Breach counts mapped to Nagios WARN/CRIT thresholds, threshold-line time series.

![Service Health Dashboard](docs/screenshots/grafana-service-health.png)

### IoT Sensor Lab (Nagios) — Operational Insights

Operational insights view cloned from the prometheus-mqtt showcase dashboard.

![Operational Insights Dashboard](docs/screenshots/grafana-iot-showcase.png)

---

## 8. Grafana API — editing dashboards

All dashboard operations can be done via the Grafana HTTP API. Default credentials: `admin` / `admin`.

### Fetch a dashboard (read current JSON)

```bash
curl -s -u admin:admin \
  http://localhost:5000/api/dashboards/uid/nagios-iot-sensors \
  | python3 -m json.tool > /tmp/nagios-iot-sensors.json
```

### Update a dashboard (push edited JSON back)

Edit `/tmp/nagios-iot-sensors.json`, then:

```bash
# Extract just the dashboard object and wrap it for the API
python3 - <<'EOF'
import json

with open("/tmp/nagios-iot-sensors.json") as f:
    raw = json.load(f)

payload = {
    "dashboard": raw["dashboard"],
    "overwrite": True,
    "folderId": 0,
    "message": "manual edit"
}

import urllib.request, base64
req = urllib.request.Request(
    "http://localhost:5000/api/dashboards/db",
    data=json.dumps(payload).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": "Basic " + base64.b64encode(b"admin:admin").decode()
    },
    method="POST"
)
with urllib.request.urlopen(req) as r:
    print(json.load(r))
EOF
```

### List all dashboards

```bash
curl -s -u admin:admin http://localhost:5000/api/search?type=dash-db \
  | python3 -c "import sys,json; [print(d['uid'], d['title']) for d in json.load(sys.stdin)]"
```

### List datasources

```bash
curl -s -u admin:admin http://localhost:5000/api/datasources \
  | python3 -c "import sys,json; [print(d['name'], d['uid'], d['url']) for d in json.load(sys.stdin)]"
```

### Delete a dashboard

```bash
curl -s -u admin:admin -X DELETE \
  http://localhost:5000/api/dashboards/uid/nagios-iot-sensors
```

---

## Useful commands

```bash
# Watch sidecar provisioning
docker compose logs -f sidecar

# Watch Nagios passive check processing
docker compose logs -f nagios | grep "PASSIVE SERVICE CHECK"

# Tail all container logs
docker compose logs -f

# Rebuild sidecar after code changes
docker compose build sidecar && docker compose up -d sidecar

# Manually reload Nagios config
docker exec nagios-mqtt-nagios-1 bash -c 'kill -HUP $(pgrep -x nagios | head -1)'

# Stop everything (keeps volumes)
docker compose down

# Stop and remove all data volumes
docker compose down -v
```

---

## Sensor simulation

The publisher simulates 15 sensor sites (site1–site15) spaced along the **M6 motorway corridor** from London to Newcastle:

| Metric | Simulation |
|---|---|
| Temperature | Sinusoidal diurnal cycle — base 17°C ±5°C, peaks ~14:00 UTC |
| Humidity | Constant 65% |
| Power | Sinusoidal with 1hr lag behind temperature — base 350W ±70W |
| Location | GPS coordinates interpolated along M6 waypoints (London → Birmingham → Manchester → Newcastle) |

Data publishes every **10 seconds** to `lab/{metric}/site{N}` topics.

---

## Thresholds

Passive check return codes are evaluated by the sidecar before submission:

| Metric | OK | WARNING | CRITICAL |
|---|---|---|---|
| Temperature | < 20°C | 20–22°C | ≥ 22°C |
| Humidity | < 75% | 75–85% | ≥ 85% |
| Power | < 390W | 390–415W | ≥ 415W |

To adjust, edit `THRESHOLDS` in `sidecar/sidecar.py` and rebuild: `docker compose build sidecar && docker compose up -d sidecar`.

---

## Port reference

| Service | Host port | Container port |
|---|---|---|
| Nagios web UI | 8088 | 80 |
| MQTT broker | 1884 | 1883 |

> MQTT is exposed on **1884** (not the default 1883) to avoid clashing with other Mosquitto stacks that may be running. To connect an external MQTT client use `localhost:1884`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` on 1884 | Another Mosquitto is running — edit `docker-compose.yml` to change the host port |
| `port is already allocated` on 8088 | Edit `docker-compose.yml` to change the Nagios host port |
| Sidecar exits — command pipe not found | Nagios is slow to start — sidecar retries for 5 min; run `docker compose up -d sidecar` to restart it once Nagios is ready |
| Services stuck PENDING | Reload did not apply — run `docker exec nagios-mqtt-nagios-1 bash -c 'kill -HUP $(pgrep -x nagios \| head -1)'` |
| Sidecar `Nagios reload failed` | Docker socket not mounted — check `volumes: - /var/run/docker.sock:/var/run/docker.sock` in `docker-compose.yml` |
| All services UNKNOWN after 2 min | Check publisher logs — `docker compose logs publisher`; broker connectivity issue |
| Grafana dashboards show no data | Ensure prometheus-mqtt stack is running and `datasource-nagios` datasource is reachable — run `python3 scripts/provision_grafana_dashboards.py` to re-provision |
