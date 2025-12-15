import json
import os
import time
from logging_config import setup_logger

logger = setup_logger("telemetry", "lora_master.log")

def write_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logger.error(f"Erro ao salvar {path}: {e}")

def comm_time(last_reset):
    return round(time.time() - last_reset, 1)
