import os
import time
import json

from serial_io import open_serial
from adc_parser import parse_adc_frame
from rssi_reader import request_rssi
from lora_configurator import apply_lora_config
from telemetry_writer import write_json, comm_time

from config_loader import load_lora_config, map_config_to_bytes
from battery.battery_consumption import BatteryMonitor
from Alarms.alarms import AlarmManager
from logging_config import setup_logger

logger = setup_logger("lora_master", "lora_master.log")

PORT = "/dev/serial0"
BAUD = 9600
TIMEOUT = 2.0
SLAVE_ID = 1

BASE = os.path.dirname(__file__)
SENSOR_FILE = os.path.join(BASE, "..", "read", "dados_endpoint.json")
COMM_FILE   = os.path.join(BASE, "communication_time.json")
BAT_FILE    = os.path.join(BASE, "..", "battery", "battery_data.json")
FLAG_FILE   = os.path.join(BASE, "..", "configs", "reconfig.flag")

def main():
    ser = open_serial(PORT, BAUD, TIMEOUT)

    alarm = AlarmManager()
    battery = BatteryMonitor(BAT_FILE)

    last_comm = time.time()

    while True:
        try:
            write_json(COMM_FILE, {"elapsed_sec": comm_time(last_comm)})

            if os.path.exists(FLAG_FILE):
                cfg = map_config_to_bytes(load_lora_config())
                apply_lora_config(ser, SLAVE_ID, cfg)
                os.remove(FLAG_FILE)

            ser.write(bytes([SLAVE_ID, 0x00, 0xB0]))
            time.sleep(0.3)

            if ser.in_waiting >= 25:
                frame = ser.read(25)
                src, sensores, bus, shunt, sleep = parse_adc_frame(frame[:23])
                last_comm = time.time()

                bat = battery.process_data(bus, shunt)
                dados = {
                    "channel_1": sensores[0],
                    "channel_2": sensores[1],
                    "channel_3": sensores[2],
                    "channel_4": sensores[3],
                    "channel_5": sensores[4],
                    "channel_6": sensores[5],
                    "battery_voltage": bat[0],
                    "bat_percent": bat[3],
                    "bat_days": bat[4],
                    "comm_time": comm_time(last_comm)
                }

                write_json(SENSOR_FILE, dados)
                alarm.evaluate(dados)

                logger.info(
                    f"[{time.strftime('%H:%M:%S')}] PACOTE RECEBIDO (ID:{src}) "
                    f"SENSORES: {sensores}"
                )

            time.sleep(1)

        except Exception as e:
            logger.error(f"Erro no loop principal: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
