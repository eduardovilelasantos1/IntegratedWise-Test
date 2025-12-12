import os
import json
import time

try:
    import RPi.GPIO as GPIO
    RPI_AVAILABLE = True
except ImportError:
    RPI_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

CONFIG_ALARMS = os.path.join(PROJECT_ROOT, "configs", "config_alarmes.json")
STATUS_FILE   = os.path.join(BASE_DIR, "alarmes_status.json")

RELAY_GPIO_MAP = {
    "relay_1": 21,
    "relay_2": 20,
    "relay_3": 16,
    "relay_4": 12,
    "relay_5": 7,
    "relay_6": 26,
    "relay_7": 19,
    "relay_8": 13,
    "relay_9": 6
}

class AlarmManager:

    def __init__(self):
        self.config = self._load_config()
        self.status = self._load_status()

        # >>> ADIÇÃO: registrar timestamp da última modificação
        self.last_config_mtime = os.path.getmtime(CONFIG_ALARMS)
        # <<<

        if RPI_AVAILABLE:
            GPIO.setmode(GPIO.BCM)
            for relay, pin in RELAY_GPIO_MAP.items():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

    # -----------------------
    def _reload_config_if_changed(self):
        """Recarrega config se o arquivo foi modificado."""
        try:
            current_mtime = os.path.getmtime(CONFIG_ALARMS)
            if current_mtime != self.last_config_mtime:
                self.config = self._load_config()
                self.last_config_mtime = current_mtime
                print("[ALARM] Configurações recarregadas (alteração detectada).")
        except:
            pass

    # -----------------------
    def _load_config(self):
        try:
            with open(CONFIG_ALARMS, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_status(self):
        try:
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {f"relay_{i}": False for i in range(1, 10)}

    def _save_status(self):
        try:
            with open(STATUS_FILE, "w") as f:
                json.dump(self.status, f, indent=4)
        except:
            pass

    # -----------------------
    def evaluate(self, sensor_data: dict):

        # >>> ADIÇÃO: antes de avaliar alarmes, verificar se config mudou
        self._reload_config_if_changed()
        # <<<

        changed = False

        for relay_id in self.status.keys():

            cfg = self.config.get(relay_id, {})
            source = cfg.get("source", "")
            limit = cfg.get("limit_real", None)
            mode  = cfg.get("type", "high")

            if not source or limit is None:
                if self.status[relay_id] is not False:
                    self.status[relay_id] = False
                    changed = True
                continue

            if source not in sensor_data:
                continue

            current_value = sensor_data[source]

            if mode == "high":
                trigger = current_value >= limit
            else:
                trigger = current_value <= limit

            if trigger != self.status[relay_id]:
                self.status[relay_id] = trigger
                changed = True
                print(f"[ALARM] {relay_id} mudou para {trigger} -- Valor: {current_value} Limite: {limit}")

            if RPI_AVAILABLE:
                pin = RELAY_GPIO_MAP[relay_id]
                GPIO.output(pin, GPIO.HIGH if trigger else GPIO.LOW)

        if changed:
            self._save_status()
