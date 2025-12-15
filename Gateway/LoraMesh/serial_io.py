import time
import serial
from logging_config import setup_logger

logger = setup_logger("serial_io", "lora_master.log")

def open_serial(port, baud, timeout):
    try:
        ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(1)
        logger.info(f"Serial aberta em {port} @ {baud}")
        return ser
    except Exception as e:
        logger.error(f"Erro ao abrir serial: {e}")
        raise
