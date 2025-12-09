import serial
import time
import os
import sys
import json
from datetime import datetime

# ==================== SETUP PATHS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
sys.path.append(PROJECT_ROOT)

try:
    from config_loader import load_lora_config, map_config_to_bytes, calcular_crc
    from battery.battery_consumption import BatteryMonitor
except ImportError as e:
    print(f"[ERRO CRITICO] Imports: {e}")
    sys.exit(1)

# ==================== CONFIGS ====================
PORT = "/dev/serial0"
BAUD = 9600
SERIAL_TIMEOUT = 2.0
SLAVE_ID = 1
CMD_ADC = 0xB0
CMD_CONFIG_RADIO = 0xD6 
CMD_CONFIG_MODE = 0xC1 
CMD_CONFIG_SLEEP = 0x50

# Estrutura: Header(3) + Sensores(12) + Bus(2) + Shunt(2) + Sleep(2) = 21 bytes de DADOS
CMD_READ_RESP_SIZE = 23 
EXTRA_BYTES = 2         
FRAME_FULL_SIZE = CMD_READ_RESP_SIZE + EXTRA_BYTES 
RETRY_TIMEOUT = 2.0

# Caminhos
RECONFIG_FLAG = os.path.join(PROJECT_ROOT, "configs", "reconfig.flag")
SENSOR_DATA_FILE = os.path.join(PROJECT_ROOT, "read", "dados_endpoint.json")
MIN_MAX_FILE = os.path.join(PROJECT_ROOT, "configs", "config_min_max.json")
BATTERY_FILE = os.path.join(PROJECT_ROOT, "battery", "battery_data.json")

# Constantes 4-20mA
BITS_MIN_4MA = 1023.75
BITS_MAX_20MA = 5118.75
BITS_RANGE = BITS_MAX_20MA - BITS_MIN_4MA
SENSOR_KEYS = ["channel_1", "channel_2", "channel_3", "channel_4", "channel_5", "channel_6"]

# === CONSTANTES DE HARDWARE/LOGICA (ATUALIZADO) ===
# Valor padrão caso não consiga ler do JSON
DEFAULT_ACTIVE_WINDOW_SEC = 5.0  

# CORREÇÃO CRÍTICA: Corrente real da placa em Sleep (13.2 mA)
CONST_SLEEP_CURRENT_MA = 13.2 

RESISTOR_CORRECTION_FACTOR = 1.0 

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

def parse_adc_frame(frame):
    if len(frame) != CMD_READ_RESP_SIZE: raise ValueError(f"Tam: {len(frame)}")
    
    # Valida CRC (tudo menos os ultimos 2 bytes)
    crc_calc = calcular_crc(frame[:-2])
    crc_recv = int.from_bytes(frame[-2:], "little")
    if crc_recv != crc_calc: raise ValueError("Erro CRC")
    
    src = int.from_bytes(frame[0:2], "little")
    cmd = frame[2]
    valores = []
    offset = 3
    for _ in range(6):
        valores.append(int.from_bytes(frame[offset:offset+2], "little"))
        offset += 2
    bus_raw = int.from_bytes(frame[offset:offset+2], "little")
    offset += 2
    shunt_raw = int.from_bytes(frame[offset:offset+2], "little", signed=True)
    offset += 2
    
    # Tempo reportado de sono
    sleep_reported_sec = int.from_bytes(frame[offset:offset+2], "little")
    
    return src, cmd, valores, bus_raw, shunt_raw, sleep_reported_sec

def load_min_max_config():
    try: return json.load(open(MIN_MAX_FILE, 'r'))
    except: return {}

def bits_to_real(bits, cfg_sensor):
    v_min = float(cfg_sensor.get("min", 0.0))
    v_max = float(cfg_sensor.get("max", 100.0))
    if bits < BITS_MIN_4MA: bits = BITS_MIN_4MA
    ratio = (bits - BITS_MIN_4MA) / BITS_RANGE
    return round((ratio * (v_max - v_min)) + v_min, 2)

def save_endpoint_data(valores_bits, voltage_v, current_ma, accumulated_mah, battery_pct, bat_days, avg_eff_ma):
    min_max_cfg = load_min_max_config()
    data_sensors = {}
    
    for i, bits in enumerate(valores_bits):
        if i < len(SENSOR_KEYS):
            key = SENSOR_KEYS[i]
            val = bits_to_real(bits, min_max_cfg.get(key, {}))
            data_sensors[key] = val
    
    data_sensors["battery_voltage"] = voltage_v
    data_sensors["battery_avg_current"] = round(avg_eff_ma, 2) 
    data_sensors["battery_instant_current"] = current_ma 
    data_sensors["bat_percent"] = battery_pct      
    data_sensors["bat_days"] = bat_days            
    data_sensors["consumo_mah"] = round(accumulated_mah, 4)
    data_sensors["comm_loss_counter"] = 0

    try:
        with open(SENSOR_DATA_FILE, 'w') as f: 
            json.dump(data_sensors, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except: pass
    
    return data_sensors

def enviar_configuracao_sleep(ser, target_id, sleep_val, window_val):
    print(f"   [CFG] Sleep -> Wake:{sleep_val}s Window:{window_val}s")
    frame = bytearray([target_id & 0xFF, (target_id >> 8) & 0xFF, CMD_CONFIG_SLEEP, sleep_val & 0xFF, window_val & 0xFF])
    crc = calcular_crc(frame)
    frame.extend(crc.to_bytes(2, "little"))
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(0.5)
    if ser.in_waiting: 
        ser.read(ser.in_waiting)
        return True
    return False

def enviar_configuracao_radio(ser, target_id, cfg, retries=3):
    print(f"   [CFG] Radio -> Pwr:{cfg['power']} BW:{cfg['bw']} SF:{cfg['sf']}")
    payload = bytearray([0x01, cfg["power"], cfg["bw"], cfg["sf"], cfg["cr"]])
    frame = bytearray([target_id & 0xFF, (target_id >> 8) & 0xFF, CMD_CONFIG_RADIO])
    frame.extend(payload)
    crc = calcular_crc(frame)
    frame.extend(crc.to_bytes(2, "little"))
    for i in range(retries):
        ser.reset_input_buffer()
        ser.write(frame)
        time.sleep(1.5)
        if ser.in_waiting: 
            ser.read(ser.in_waiting)
            return True
    return True

def enviar_configuracao_modo(ser, target_id, cfg, forcar_classe_c=False):
    classe = cfg["classe"]
    if forcar_classe_c: classe = 0x02 
    print(f"   [CFG] Modo -> Classe:{'C' if classe==2 else 'A'} Janela:{cfg['janela']}")
    payload = bytearray([0x00, classe, cfg["janela"]])
    frame = bytearray([target_id & 0xFF, (target_id >> 8) & 0xFF, CMD_CONFIG_MODE])
    frame.extend(payload)
    crc = calcular_crc(frame)
    frame.extend(crc.to_bytes(2, "little"))
    ser.reset_input_buffer()
    ser.write(frame)
    time.sleep(0.5)
    if ser.in_waiting: ser.read(ser.in_waiting)

# ==================== MAIN LOOP ====================
def main():
    ser = abrir_serial()
    if not ser: return

    try:
        bat_monitor = BatteryMonitor(BATTERY_FILE)
    except Exception as e:
        print(f"[ERRO] BatteryMonitor: {e}")
        return

    last_success_time = time.time()
    pending_config = None
    
    logic_total_cycle_time = 30 
    
    # Variável dinâmica para janela (inicializada com o padrão)
    active_window_sec = DEFAULT_ACTIVE_WINDOW_SEC

    serial_buffer = bytearray()
    last_packet_arrival = None 

    while True:
        try:
            # 1. RECONFIGURAÇÃO
            if os.path.exists(RECONFIG_FLAG):
                print("\n" + "="*50)
                print(" 🚩 RECONFIGURAÇÃO SOLICITADA")
                print("="*50)
                cfg_json = load_lora_config()
                if cfg_json: pending_config = map_config_to_bytes(cfg_json)
                try: os.remove(RECONFIG_FLAG)
                except: pass

            # 2. ATUALIZA PARÂMETROS
            cfg_temp = load_lora_config()
            if cfg_temp:
                # Atualiza ciclo
                logic_total_cycle_time = int(cfg_temp.get("wake_interval", 30))
                if cfg_temp.get("classe") in ["C", 0x02]: 
                    logic_total_cycle_time = 2
                
                # --- NOVO: Atualiza Janela Dinâmica ---
                # Lê "janela" do JSON (ex: "10s"), remove o 's' e converte para float
                raw_win = str(cfg_temp.get("janela", str(DEFAULT_ACTIVE_WINDOW_SEC)))
                try:
                    active_window_sec = float(raw_win.lower().replace('s', '').strip())
                except:
                    pass # Mantém o valor anterior se falhar

            if time.time() - last_success_time < logic_total_cycle_time:
                time.sleep(1)
                continue

            # 3. LEITURA
            ser.reset_input_buffer()
            ser.write(make_cmd_frame(SLAVE_ID, CMD_ADC))
            t0 = time.time()
            
            while time.time() - t0 < RETRY_TIMEOUT:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    serial_buffer.extend(chunk)
                    
                    header_seq = bytes([SLAVE_ID & 0xFF, (SLAVE_ID >> 8) & 0xFF, CMD_ADC])
                    start_idx = serial_buffer.find(header_seq)
                    
                    if start_idx != -1 and (len(serial_buffer) - start_idx) >= FRAME_FULL_SIZE:
                        valid_frame = serial_buffer[start_idx : start_idx + FRAME_FULL_SIZE]
                        try:
                            # Parse
                            src, cmd, sensores, bus_raw, shunt_raw, sleep_reported_s = parse_adc_frame(valid_frame[:CMD_READ_RESP_SIZE])
                            serial_buffer = serial_buffer[start_idx + FRAME_FULL_SIZE:]

                            current_arrival = time.time()
                            multiplier = 1.0
                            if last_packet_arrival is not None:
                                real_interval = current_arrival - last_packet_arrival
                                if logic_total_cycle_time > 0 and real_interval < 3600:
                                    multiplier = round(real_interval / logic_total_cycle_time)
                                    if multiplier < 1: multiplier = 1
                            last_packet_arrival = current_arrival

                            # Processa Bateria
                            try:
                                ret = bat_monitor.process_data(bus_raw, shunt_raw, cycle_multiplier=multiplier)
                            except TypeError:
                                ret = bat_monitor.process_data(bus_raw, shunt_raw)
                            
                            if len(ret) >= 4:
                                vv, curr_orig, mah, pct = ret[0], ret[1], ret[2], ret[3]
                                days = ret[4] if len(ret) > 4 else 0
                            else:
                                vv, curr_orig, mah, pct, days = 0,0,0,0,0

                            # --- CÁLCULO DE CORRENTE MÉDIA (EXATA / DETERMINÍSTICA) ---
                            curr = curr_orig * RESISTOR_CORRECTION_FACTOR
                            
                            # Dados reais
                            t_sleep_effective = float(sleep_reported_s)
                            
                            # AJUSTE FINO:
                            # O Ciclo Real é o configurado (30s) pois o Slave ajusta o sleep para cumprir isso.
                            # O tempo que não é Sleep, assumimos como Ativo (Janela + Overhead + Boot).
                            # Isso corrige o "buraco" de 4s que faltava na conta.
                            if logic_total_cycle_time > t_sleep_effective:
                                t_cycle_calc = float(logic_total_cycle_time)
                                t_active_calc = t_cycle_calc - t_sleep_effective
                            else:
                                # Fallback se algo estranho ocorrer
                                t_active_calc = active_window_sec
                                t_cycle_calc = t_sleep_effective + t_active_calc

                            if t_cycle_calc > 0:
                                # Média Ponderada Real
                                avg_logic_ma = ((curr * t_active_calc) + (CONST_SLEEP_CURRENT_MA * t_sleep_effective)) / t_cycle_calc
                            else:
                                avg_logic_ma = curr 

                            # Salva
                            dados_finais = save_endpoint_data(sensores, vv, curr, mah, pct, days, avg_logic_ma)
                            
                            # Prints
                            ts = datetime.now().strftime("%H:%M:%S")
                            sens_str = ", ".join([f"{dados_finais[k]:.1f}" for k in SENSOR_KEYS if k in dados_finais])
                            
                            print(f"\n[{ts}] 📡 PACOTE RECEBIDO (ID: {src})")
                            print("=" * 50)
                            print(f" ⚙️  TELEMETRIA DE TEMPO")
                            print(f"    • Tempo Dormido (Reportado): {t_sleep_effective:.0f} s")
                            print(f"    • Tempo Ativo Total (Calc) : {t_active_calc:.1f} s (Inclui Overhead)")
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

                            last_success_time = time.time()

                            if pending_config:
                                print("\n⚙️ APLICANDO NOVA CONFIGURAÇÃO...")
                                time.sleep(0.2)
                                enviar_configuracao_sleep(ser, SLAVE_ID, pending_config["wake"], pending_config["window_sec"])
                                enviar_configuracao_modo(ser, SLAVE_ID, pending_config)
                                if enviar_configuracao_radio(ser, SLAVE_ID, pending_config, retries=3):
                                    print("✅ Sucesso!")
                                    pending_config = None
                                else:
                                    print("❌ Falha.")
                            break

                        except Exception as e:
                            print(f"[ERRO PARSE] {e}")
                            serial_buffer = serial_buffer[start_idx + 1:]
                time.sleep(0.05)
            time.sleep(1)

        except KeyboardInterrupt: break
        except Exception as e:
            print(f"[ERRO MAIN] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()