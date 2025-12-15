import time
from config_loader import calcular_crc
from logging_config import setup_logger

logger = setup_logger("lora_config", "lora_master.log")

CMD_CONFIG_RADIO = 0xD6
CMD_CONFIG_MODE  = 0xC1
CMD_CONFIG_SLEEP = 0x50

def apply_lora_config(ser, slave_id, cfg):
    logger.info(f"Aplicando config LoRa: {cfg}")

    def send(cmd, payload):
        frame = bytearray([slave_id & 0xFF, slave_id >> 8, cmd]) + payload
        crc = calcular_crc(frame)
        frame.extend(crc.to_bytes(2, "little"))
        ser.write(frame)
        ser.flush()
        time.sleep(0.15)

    send(CMD_CONFIG_RADIO, bytes([cfg["power"], cfg["bw"], cfg["sf"], cfg["cr"]]))
    send(CMD_CONFIG_MODE,  bytes([cfg["classe"]]))
    send(CMD_CONFIG_SLEEP, bytes([cfg["wake"]]))

    logger.info("Configuração LoRa aplicada")
