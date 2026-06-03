#!/usr/bin/env python3
"""
Nagios MQTT Sidecar
Watches MQTT lab/# topics and:
  - Generates Nagios host/service config files for newly discovered sites
  - Submits passive check results via Nagios external command pipe
"""

import os
import time
import logging
import subprocess
import paho.mqtt.client as mqtt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)

# ── Config from environment ───────────────────────────────────────────────────
MQTT_BROKER      = os.environ.get('MQTT_BROKER',      'mqtt-broker')
MQTT_PORT        = int(os.environ.get('MQTT_PORT',    '1883'))
MQTT_TOPIC       = os.environ.get('MQTT_TOPIC',       'lab/#')
NAGIOS_CMD       = os.environ.get('NAGIOS_CMD_FILE',  '/opt/nagios/var/rw/nagios.cmd')
NAGIOS_CONF      = os.environ.get('NAGIOS_CONF_DIR',  '/opt/nagios/etc/conf.d')
NAGIOS_CONTAINER = os.environ.get('NAGIOS_CONTAINER', 'nagios')

provisioned = set()
last_reload = 0.0

# ── Thresholds ────────────────────────────────────────────────────────────────
# Sensor data: temp base=17°C ±5, power base=350W ±70, humidity fixed 65%
THRESHOLDS = {
    'temp':     {'warn': 20.0, 'crit': 22.0, 'unit': 'C'},
    'humidity': {'warn': 75.0, 'crit': 85.0, 'unit': '%'},
    'power':    {'warn': 390.0, 'crit': 415.0, 'unit': 'W'},
}
SVC_MAP = {'temp': 'Temperature', 'humidity': 'Humidity', 'power': 'Power'}


# ── Nagios external command pipe ──────────────────────────────────────────────
def write_cmd(command: str):
    ts = int(time.time())
    line = f'[{ts}] {command}\n'.encode()
    try:
        fd = os.open(NAGIOS_CMD, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, line)
        os.close(fd)
    except OSError as e:
        log.warning(f'Write to nagios.cmd failed: {e}')


def passive_result(host: str, service: str, rc: int, output: str):
    write_cmd(f'PROCESS_SERVICE_CHECK_RESULT;{host};{service};{rc};{output}')


def check_value(value: float, warn: float, crit: float, unit: str) -> tuple[int, str]:
    if value >= crit:
        return 2, f'CRITICAL: {value}{unit} (threshold {crit}{unit})'
    if value >= warn:
        return 1, f'WARNING: {value}{unit} (threshold {warn}{unit})'
    return 0, f'OK: {value}{unit}'


# ── Nagios config generation ──────────────────────────────────────────────────
def create_site_config(site: str) -> bool:
    cfg = os.path.join(NAGIOS_CONF, f'{site}.cfg')
    if os.path.exists(cfg):
        return False

    content = f"""define host {{
    use                     linux-server
    host_name               {site}
    alias                   {site}
    address                 127.0.0.1
    notification_period     24x7
    active_checks_enabled   0
    passive_checks_enabled  1
    check_freshness         1
    freshness_threshold     300
}}

define service {{
    use                     generic-service
    host_name               {site}
    service_description     Temperature
    check_command           check_dummy!3!No data received
    active_checks_enabled   0
    passive_checks_enabled  1
    check_freshness         1
    freshness_threshold     120
    notification_period     24x7
}}

define service {{
    use                     generic-service
    host_name               {site}
    service_description     Humidity
    check_command           check_dummy!3!No data received
    active_checks_enabled   0
    passive_checks_enabled  1
    check_freshness         1
    freshness_threshold     120
    notification_period     24x7
}}

define service {{
    use                     generic-service
    host_name               {site}
    service_description     Power
    check_command           check_dummy!3!No data received
    active_checks_enabled   0
    passive_checks_enabled  1
    check_freshness         1
    freshness_threshold     120
    notification_period     24x7
}}
"""
    os.makedirs(NAGIOS_CONF, exist_ok=True)
    with open(cfg, 'w') as f:
        f.write(content)
    log.info(f'Created config for {site} at {cfg}')
    return True


def reload_nagios():
    """Send SIGHUP to the Nagios process via docker exec to reload config."""
    global last_reload
    now = time.time()
    if now - last_reload < 15:
        return
    last_reload = now
    log.info(f'Reloading Nagios config in container {NAGIOS_CONTAINER}')
    try:
        result = subprocess.run(
            ['docker', 'exec', NAGIOS_CONTAINER,
             'bash', '-c', 'kill -HUP $(pgrep -x nagios | head -1)'],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            log.info('Nagios config reloaded')
        else:
            log.error(f'Nagios reload stderr: {result.stderr.decode().strip()}')
    except Exception as e:
        log.error(f'Nagios reload failed: {e}')


# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        log.info(f'Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}')
        client.subscribe(MQTT_TOPIC)
        log.info(f'Subscribed to {MQTT_TOPIC}')
    else:
        log.error(f'MQTT connection failed rc={rc}')


def on_message(client, userdata, msg):
    parts = msg.topic.split('/')
    if len(parts) != 3:
        return
    _, metric, site = parts
    if not site.startswith('site'):
        return

    payload = msg.payload.decode().strip()

    if site not in provisioned:
        created = create_site_config(site)
        provisioned.add(site)
        if created:
            time.sleep(1)
            reload_nagios()

    t = THRESHOLDS.get(metric)
    svc = SVC_MAP.get(metric)
    if t and svc:
        try:
            v = float(payload)
            rc, out = check_value(v, t['warn'], t['crit'], t['unit'])
            passive_result(site, svc, rc, out)
        except ValueError:
            pass


# ── Startup ───────────────────────────────────────────────────────────────────
def wait_for_cmd_pipe():
    log.info(f'Waiting for Nagios command pipe at {NAGIOS_CMD}')
    for i in range(60):
        if os.path.exists(NAGIOS_CMD):
            log.info('Nagios command pipe is ready')
            return
        log.info(f'  {i + 1}/60 — retrying in 5s')
        time.sleep(5)
    log.error('Nagios command pipe not found after 5 minutes — exiting')
    raise SystemExit(1)


if __name__ == '__main__':
    wait_for_cmd_pipe()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    log.info(f'Connecting to MQTT {MQTT_BROKER}:{MQTT_PORT}')
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()
