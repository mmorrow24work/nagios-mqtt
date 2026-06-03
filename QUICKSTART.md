# QUICKSTART — Nagios MQTT Monitoring Lab

Full step-by-step setup from a fresh clone to a live Nagios dashboard with 15 simulated MQTT sensor sites.

---

## Prerequisites

- Docker + Docker Compose
- GitHub CLI (`gh auth login` completed)
- Port 8080 free (Nagios web UI)
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

The first run pulls `jasonrivers/nagios` (~275 MB) and builds the sidecar image. Subsequent starts are fast.

Verify all containers are up:

```bash
docker compose ps
```

Expected:

```
NAME             IMAGE                       STATUS
mqtt-broker      eclipse-mosquitto:2         Up
nagios           jasonrivers/nagios:latest   Up
nagios-sidecar   nagios-mqtt-sidecar         Up
publisher        alpine:3.20                 Up
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
INFO Reloading Nagios config in container nagios
INFO Nagios config reloaded
INFO Created config for site2 at /opt/nagios/etc/conf.d/site2.cfg
...
INFO Created config for site15 at /opt/nagios/etc/conf.d/site15.cfg
```

Once all 15 sites appear, Ctrl-C out of the log tail.

---

## 4. Log in to Nagios

Open **http://localhost:8080/nagios**

| Credential | Value |
|---|---|
| Username | `nagiosadmin` |
| Password | `nagios` |

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
docker exec mqtt-broker mosquitto_sub -h localhost -t 'lab/#' -v -C 20
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
docker exec nagios bash -c 'kill -HUP $(pgrep -x nagios | head -1)'

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
| Nagios web UI | 8080 | 80 |
| MQTT broker | 1884 | 1883 |

> MQTT is exposed on **1884** (not the default 1883) to avoid clashing with other Mosquitto stacks that may be running. To connect an external MQTT client use `localhost:1884`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` on 1883 | Another Mosquitto is running — the compose file uses 1884; if 1884 is also taken, edit `docker-compose.yml` |
| `port is already allocated` on 8080 | Edit `docker-compose.yml` to change the Nagios host port |
| Sidecar exits — command pipe not found | Nagios is slow to start — sidecar retries for 5 min; run `docker compose up -d sidecar` to restart it once Nagios is ready |
| Services stuck PENDING | Reload did not apply — run `docker exec nagios bash -c 'kill -HUP $(pgrep -x nagios \| head -1)'` |
| Sidecar `Nagios reload failed` | Docker socket not mounted — check `volumes: - /var/run/docker.sock:/var/run/docker.sock` in `docker-compose.yml` |
| All services UNKNOWN after 2 min | Check publisher logs — `docker compose logs publisher`; broker connectivity issue |
