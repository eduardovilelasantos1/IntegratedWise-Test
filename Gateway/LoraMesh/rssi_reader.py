import time
from datetime import datetime, timezone
from config_loader import calcular_crc
from logging_config import setup_logger

logger = setup_logger("rssi_reader", "lora_master.log")

CMD_RSSI = 0xD5

def request_rssi(ser, slave_id, timeout=0.3):
    frame = bytearray([slave_id & 0xFF, slave_id >> 8, CMD_RSSI, 0x00])
    crc = calcular_crc(frame)
    frame.extend(crc.to_bytes(2, "little"))

    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()

    start = time.time()
    buf = bytearray()

    while time.time() - start < timeout:
        if ser.in_waiting:
            buf.extend(ser.read(ser.in_waiting))
            if len(buf) >= 9:
                return {
                    "rssi_ida": -int(buf[5]),
                    "rssi_volta": -int(buf[6]),
                    "snr_ida": int(buf[7]),
                    "snr_volta": int(buf[8]),
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
        time.sleep(0.01)

    logger.warning("Timeout RSSI")
    return None
