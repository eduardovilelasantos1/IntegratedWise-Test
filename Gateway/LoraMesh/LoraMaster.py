#!/usr/bin/env python3
"""
LoraMaster.py
Versão refatorada / final
- Lê pacotes ADC do slave (0xB0)
- Solicita RSSI (0xD5) ao gateway/modem e salva em read/rssi.json
- Mantém dados do endpoint em read/dados_endpoint.json
- Conta tempo sem comunicação (comm_time) desde o start e reseta ao receber pacote
- Mantém prints atuais (formatados) para facilitar debug
"""

# ================================================================
#  FIX PARA PERMITIR IMPORTAR Alarms DE FORA DA PASTA ATUAL
# ================================================================
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# ================================================================

import os
import sys
import time
import json
import serial
from datetime import datetime, timezone

# ================================================================
#  IMPORTAÇÃO DO GERENCIADOR DE ALARMES
# ================================================================
from Alarms.alarms import AlarmManager
# ================================================================

# ---------------- PATHS / SETUP ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.append(PROJECT_ROOT)

SENSOR_DATA_FILE = os.path.join(PROJECT_ROOT, "read", "dados_endpoint.json")
RSSI_FILE = os.path.join(PROJECT_ROOT, "read", "rssi.json")
RECONFIG_FLAG = os.path.join(PROJECT_ROOT, "configs", "reconfig.flag")
MIN_MAX_FILE = os.path.join(PROJECT_ROOT, "configs", "config_min_max.json")
BATTERY_FILE = os.path.join(PROJECT_ROOT, "battery", "battery_data.json")

# =====================================================
#  ⭐ ARQUIVO communication_time.json
# =====================================================
COMM_TIME_FILE = os.path.join(PROJECT_ROOT, "LoraMesh", "communication_time.json")

def save_comm_time():
    try:
        elapsed = round(time.time() - last_comm_reset_ts, 1)
        obj = {
            "last_update": datetime.utcnow().isoformat(),
            "elapsed_sec": elapsed
        }
        safe_write_json(COMM_TIME_FILE, obj)
    except:
        pass

# ---------------- IMPORTS LOCAIS ----------------
try:
    from config_loader import load_lora_config, map_config_to_bytes, calcular_crc
    from battery.battery_consumption import BatteryMonitor
except Exception as e:
    print(f"[ERRO CRITICO] Imports: {e}")
    raise

# ---------------- CONSTS ----------------
PORT = "/dev/serial0"
BAUD = 9600
SERIAL_TIMEOUT = 2.0

SLAVE_ID = 1
CMD_ADC = 0xB0
CMD_RSSI = 0xD5
CMD_CONFIG_SLEEP = 0x50
CMD_CONFIG_MODE = 0xC1
CMD_CONFIG_RADIO = 0xD6

CMD_READ_RESP_SIZE = 23
FRAME_FULL_SIZE = CMD_READ_RESP_SIZE + 2
RETRY_TIMEOUT = 2.0

RSSI_MIN_PACKET = 9
RSSI_MAX_PACKET = 32

BITS_MIN_4MA = 1023.75
BITS_MAX_20MA = 5118.75
BITS_RANGE = BITS_MAX_20MA - BITS_MIN_4MA

SENSOR_KEYS = [
    "channel_1","channel_2","channel_3",
    "channel_4","channel_5","channel_6"
]

DEFAULT_ACTIVE_WINDOW_SEC = 5.0
CONST_SLEEP_CURRENT_MA = 13.2
RESISTOR_CORRECTION_FACTOR = 1.0

program_start_ts = time.time()
last_comm_reset_ts = program_start_ts
last_packet_arrival = None

# ---------------- HELPERS ----------------
def safe_write_json(path, obj):
    try:
        with open(path, "w") as f:
            json.dump(obj, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except:
        pass


def abrir_serial():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=SERIAL_TIMEOUT)
        time.sleep(1)
        print(f"[SYSTEM] Porta {PORT} aberta. Aguardando dados...")
        return ser
    except Exception as e:
        print(f"[ERRO SERIAL] {e}")
        raise


def make_cmd_frame(dest_id, cmd):
    raw = dest_id.to_bytes(2, "little") + bytes([cmd])
    crc = calcular_crc(raw)
    return raw + crc.to_bytes(2, "little")


def load_min_max_config():
    try:
        return json.load(open(MIN_MAX_FILE, "r"))
    except:
        return {}


def bits_to_real(bits, cfg_sensor):
    try:
        v_min = float(cfg_sensor.get("min", 0.0))
        v_max = float(cfg_sensor.get("max", 100.0))
    except:
        v_min, v_max = 0.0, 100.0

    if bits < BITS_MIN_4MA:
        bits = BITS_MIN_4MA

    ratio = (bits - BITS_MIN_4MA) / BITS_RANGE
    return round((ratio * (v_max - v_min)) + v_min, 2)


def parse_adc_frame(frame: bytes):
    if len(frame) != CMD_READ_RESP_SIZE:
        raise ValueError(f"Tam: {len(frame)}")

    crc_calc = calcular_crc(frame[:-2])
    crc_recv = int.from_bytes(frame[-2:], "little")

    if crc_recv != crc_calc:
        raise ValueError("Erro CRC")

    src = int.from_bytes(frame[0:2], "little")
    cmd = frame[2]

    valores = []
    offset = 3
    for _ in range(6):
        valores.append(int.from_bytes(frame[offset:offset+2], "little"))
        offset += 2

    bus_raw = int.from_bytes(frame[offset:offset+2], "little"); offset += 2
    shunt_raw = int.from_bytes(frame[offset:offset+2], "little", signed=True); offset += 2
    sleep_reported_sec = int.from_bytes(frame[offset:offset+2], "little")

    return src, cmd, valores, bus_raw, shunt_raw, sleep_reported_sec


def save_endpoint_data(valores_bits, voltage_v, curr, accumulated_mah, pct, days, avg_ma, extra=None):
    extra = extra or {}
    min_max_cfg = load_min_max_config()

    data_sensors = {}

    for i, bits in enumerate(valores_bits):
        if i < len(SENSOR_KEYS):
            key = SENSOR_KEYS[i]
            val = bits_to_real(bits, min_max_cfg.get(key, {}))
            data_sensors[key] = val

    data_sensors["battery_voltage"] = voltage_v
    data_sensors["battery_avg_current"] = round(avg_ma, 2)
    data_sensors["consumo_mah"] = round(accumulated_mah, 4)
    data_sensors["bat_percent"] = pct
    data_sensors["bat_days"] = days

    data_sensors["comm_time"] = round(time.time() - last_comm_reset_ts, 1)

    if "snr_ida" in extra: data_sensors["snr_ida"] = extra["snr_ida"]
    if "snr_volta" in extra: data_sensors["snr_volta"] = extra["snr_volta"]
    if "rssi_ida" in extra: data_sensors["rssi_ida"] = extra["rssi_ida"]
    if "rssi_volta" in extra: data_sensors["rssi_volta"] = extra["rssi_volta"]

    data_sensors["comm_loss_counter"] = 0

    try:
        with open(SENSOR_DATA_FILE, "w") as f:
            json.dump(data_sensors, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except:
        pass

    return data_sensors
def solicitar_rssi(ser, target_id=SLAVE_ID, timeout=0.35):
    try:
        print("\n[DEBUG RSSI] Enviando solicitação RSSI...")
        frame = bytearray([
            target_id & 0xFF, (target_id >> 8) & 0xFF,
            CMD_RSSI, 0x00
        ])

        crc = calcular_crc(frame)
        frame.extend(crc.to_bytes(2, "little"))

        print(f"[DEBUG RSSI] TX Frame: {frame.hex().upper()}")

        ser.reset_input_buffer()
        ser.write(frame)
        ser.flush()

        t0 = time.time()
        buf = bytearray()

        header = bytes([
            target_id & 0xFF, (target_id >> 8) & 0xFF, CMD_RSSI
        ])

        while time.time() - t0 < timeout:
            if ser.in_waiting:
                chunk = ser.read(ser.in_waiting)
                buf.extend(chunk)
                print(f"[DEBUG RSSI] RX Chunk: {buf.hex().upper()}")

                idx = buf.find(header)

                if idx != -1 and len(buf) - idx >= RSSI_MIN_PACKET:

                    pkt = buf[idx: idx + min(RSSI_MAX_PACKET, len(buf)-idx)]

                    if len(pkt) >= 9:
                        gw = pkt[3] | (pkt[4] << 8)
                        rssi_ida = -int(pkt[5])
                        rssi_volta = -int(pkt[6])
                        snr_ida = int(pkt[7])
                        snr_volta = int(pkt[8])

                        obj = {
                            "gateway_id": gw,
                            "rssi_ida": rssi_ida,
                            "rssi_volta": rssi_volta,
                            "snr_ida": snr_ida,
                            "snr_volta": snr_volta,
                            "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                        }

                        print(f"[DEBUG RSSI] OBJETO FINAL: {obj}")

                        safe_write_json(RSSI_FILE, obj)
                        return obj

            time.sleep(0.01)

        print("[DEBUG RSSI] Tempo excedido — sem resposta válida.")
        return None

    except Exception as e:
        print(f"[ERRO RSSI] {e}")
        return None

# ============================================================
#   ENVIO REAL DAS CONFIGURAÇÕES LoRa PARA O MÓDULO
# ============================================================
def aplicar_config_lora(ser, cfg):
    print("\n========== APLICANDO CONFIGURAÇÃO LoRa ==========")
    print(cfg)

    try:
        # 1) CONFIG RADIO
        frame = bytearray([
            SLAVE_ID & 0xFF, (SLAVE_ID >> 8) & 0xFF,
            CMD_CONFIG_RADIO,
            cfg["power"],
            cfg["bw"],
            cfg["sf"],
            cfg["cr"]
        ])
        crc = calcular_crc(frame)
        frame.extend(crc.to_bytes(2, "little"))
        ser.write(frame); ser.flush()
        time.sleep(0.15)

        # 2) MODE A/C
        frame = bytearray([
            SLAVE_ID & 0xFF, (SLAVE_ID >> 8) & 0xFF,
            CMD_CONFIG_MODE,
            cfg["classe"]
        ])
        crc = calcular_crc(frame)
        frame.extend(crc.to_bytes(2, "little"))
        ser.write(frame); ser.flush()
        time.sleep(0.15)

        # 3) WAKE / SLEEP
        frame = bytearray([
            SLAVE_ID & 0xFF, (SLAVE_ID >> 8) & 0xFF,
            CMD_CONFIG_SLEEP,
            cfg["wake"]
        ])
        crc = calcular_crc(frame)
        frame.extend(crc.to_bytes(2, "little"))
        ser.write(frame); ser.flush()
        time.sleep(0.15)

        print("========== CONFIGURAÇÃO LoRa APLICADA ==========\n")

    except Exception as e:
        print("[ERRO aplicar_config_lora]", e)

# ============================================================
#                           MAIN LOOP
# ============================================================
def main():
    global last_packet_arrival, last_comm_reset_ts

    ser = abrir_serial()
    alarm_manager = AlarmManager()

    try:
        bat_monitor = BatteryMonitor(BATTERY_FILE)
        print("[BAT] Inicializando Monitor (Modo Detalhado)...")
    except Exception as e:
        print(f"[ERRO] BatteryMonitor: {e}")
        return

    last_success_time = time.time()
    pending_config = None
    logic_total_cycle_time = 30
    active_window_sec = DEFAULT_ACTIVE_WINDOW_SEC

    serial_buffer = bytearray()

    while True:

        save_comm_time()

        try:
            # ======================================================
            # FLAG DE RECONFIGURAÇÃO LoRa
            # ======================================================
            if os.path.exists(RECONFIG_FLAG):
                print("\n🚩 RECONFIGURAÇÃO LoRa SOLICITADA")

                cfg_json = load_lora_config()
                if cfg_json:
                    pending_config = map_config_to_bytes(cfg_json)
                    aplicar_config_lora(ser, pending_config)

                try:
                    os.remove(RECONFIG_FLAG)
                except:
                    pass

            # ======================================================
            # LEITURA DAS CONFIGS ATUAIS
            # ======================================================
            cfg_temp = load_lora_config()
            if cfg_temp:
                logic_total_cycle_time = int(cfg_temp.get("wake_interval", logic_total_cycle_time))

                if cfg_temp.get("classe") in ["C", 0x02]:
                    logic_total_cycle_time = 2

                raw_win = str(cfg_temp.get("janela", str(DEFAULT_ACTIVE_WINDOW_SEC)))
                try:
                    active_window_sec = float(raw_win.lower().replace("s", "").strip())
                except:
                    pass

            # ======================================================
            # AVALIA ALARMES CONTINUAMENTE
            # ======================================================
            try:
                if os.path.exists(SENSOR_DATA_FILE):
                    with open(SENSOR_DATA_FILE, "r") as f:
                        dados = json.load(f)
                else:
                    dados = {}

                if os.path.exists(COMM_TIME_FILE):
                    with open(COMM_TIME_FILE, "r") as f:
                        comm = json.load(f)
                        dados["comm_time"] = comm.get("elapsed_sec", 0)

                if os.path.exists(BATTERY_FILE):
                    with open(BATTERY_FILE, "r") as f:
                        bat = json.load(f)
                        dados["bat_percent"] = bat.get("percent", 0)
                        dados["bat_days"] = bat.get("days", 0)
                        dados["battery_voltage"] = bat.get("voltage", 0)

                alarm_manager.evaluate(dados)

            except Exception as e:
                print("[ERRO evaluate] ", e)

            # ======================================================
            # SOLICITA ADC
            # ======================================================
            ser.reset_input_buffer()
            ser.write(make_cmd_frame(SLAVE_ID, CMD_ADC))
            t0 = time.time()

            while time.time() - t0 < RETRY_TIMEOUT:

                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    serial_buffer.extend(chunk)

                    header_seq = bytes([
                        SLAVE_ID & 0xFF, (SLAVE_ID >> 8) & 0xFF, CMD_ADC
                    ])
                    start_idx = serial_buffer.find(header_seq)

                    if start_idx != -1 and (len(serial_buffer) - start_idx) >= FRAME_FULL_SIZE:

                        raw_frame = serial_buffer[start_idx : start_idx + FRAME_FULL_SIZE]

                        try:
                            src, cmd, sensores, bus_raw, shunt_raw, sleep_reported_s = \
                                parse_adc_frame(raw_frame[:CMD_READ_RESP_SIZE])

                            serial_buffer = serial_buffer[start_idx + FRAME_FULL_SIZE:]

                            current_arrival = time.time()
                            last_comm_reset_ts = current_arrival
                            save_comm_time()

                            multiplier = 1.0
                            if last_packet_arrival is not None:
                                real_interval = current_arrival - last_packet_arrival
                                if logic_total_cycle_time > 0 and real_interval < 3600:
                                    multiplier = round(real_interval / logic_total_cycle_time)
                                    if multiplier < 1:
                                        multiplier = 1

                            last_packet_arrival = current_arrival

                            try:
                                ret = bat_monitor.process_data(
                                    bus_raw, shunt_raw, cycle_multiplier=multiplier
                                )
                            except TypeError:
                                ret = bat_monitor.process_data(bus_raw, shunt_raw)

                            if len(ret) >= 4:
                                vv, curr_orig, mah, pct = ret[:4]
                                days = ret[4] if len(ret) > 4 else 0
                            else:
                                vv = curr_orig = mah = pct = days = 0

                            curr = curr_orig * RESISTOR_CORRECTION_FACTOR

                            t_sleep_effective = float(sleep_reported_s)

                            if logic_total_cycle_time > t_sleep_effective:
                                t_cycle_calc = float(logic_total_cycle_time)
                                t_active_calc = t_cycle_calc - t_sleep_effective
                            else:
                                t_active_calc = active_window_sec
                                t_cycle_calc = t_sleep_effective + t_active_calc

                            if t_cycle_calc > 0:
                                avg_logic_ma = (
                                    (curr * t_active_calc)
                                    + (CONST_SLEEP_CURRENT_MA * t_sleep_effective)
                                ) / t_cycle_calc
                            else:
                                avg_logic_ma = curr

                            rssi_obj = solicitar_rssi(ser, SLAVE_ID, timeout=0.25)

                            extra = {}
                            if rssi_obj:
                                extra["rssi_ida"] = rssi_obj["rssi_ida"]
                                extra["rssi_volta"] = rssi_obj["rssi_volta"]
                                extra["snr_ida"] = rssi_obj["snr_ida"]
                                extra["snr_volta"] = rssi_obj["snr_volta"]

                            dados_finais = save_endpoint_data(
                                sensores, vv, curr, mah, pct, days, avg_logic_ma, extra=extra
                            )

                            try:
                                limite = logic_total_cycle_time * 1.5
                                dados_finais["online"] = (dados_finais["comm_time"] < limite)
                            except:
                                dados_finais["online"] = False

                            safe_write_json(SENSOR_DATA_FILE, dados_finais)
                            alarm_manager.evaluate(dados_finais)

                            ts = datetime.now().strftime("%H:%M:%S")
                            sens_str = ", ".join([
                                f"{dados_finais[k]:.1f}"
                                for k in SENSOR_KEYS if k in dados_finais
                            ])

                            print(f"\n[{ts}] 📡 PACOTE RECEBIDO (ID: {src})")
                            print("=" * 50)
                            print(f" ⚙️  TELEMETRIA DE TEMPO")
                            print(f"    • Tempo Dormido (Reportado): {t_sleep_effective:.0f} s")
                            print(f"    • Tempo Ativo Total (Calc) : {t_active_calc:.1f} s")
                            print(f"    • Ciclo Total (Config)     : {t_cycle_calc:.1f} s")
                            if multiplier > 1:
                                print(f"    ⚠️ ALERTA: {int(multiplier)-1} Pacote(s) Perdido(s).")
                            print("-" * 50)

                            print(f" 🔌  CONSUMO DE CORRENTE")
                            print(f"    • Ativo (Instantâneo)    : {curr:.2f} mA")
                            print(f"    • Sleep (Configurado)    : {CONST_SLEEP_CURRENT_MA:.2f} mA")
                            print(f"    • MÉDIA PONDERADA REAL   : {avg_logic_ma:.2f} mA")
                            print("-" * 50)

                            print(f" 🔋  STATUS BATERIA")
                            print(f"    • Tensão                 : {vv:.2f} V")
                            print(f"    • Consumo Acumulado      : {mah:.4f} mAh")
                            print(f"    • Autonomia Estimada     : {days:.1f} Dias")
                            print("-" * 50)

                            print(f" 📊  SENSORES: [{sens_str}]")
                            print("=" * 50)

                            comm_elapsed = round(time.time() - last_comm_reset_ts, 1)
                            print(f" 📡 Tempo sem comunicação (resetado): {comm_elapsed:.1f} s")

                            last_success_time = time.time()
                            break

                        except Exception as e:
                            print(f"[ERRO PARSE] {e}")
                            serial_buffer = serial_buffer[start_idx + 1:]

                time.sleep(0.02)

            time.sleep(1)

        except KeyboardInterrupt:
            print("[SYSTEM] KeyboardInterrupt received, exiting.")
            break

        except Exception as e:
            print(f"[ERRO MAIN] {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
