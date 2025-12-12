import json
import time
import os
import sys
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIGURAÇÃO DE CAMINHOS (PATHS) ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from logger import log

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

SENSOR_DATA_FILE = os.path.join(PROJECT_ROOT, "read", "dados_endpoint.json")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "configs")
MIN_MAX_FILE = os.path.join(CONFIG_DIR, "config_min_max.json")
CALIBRATION_FILE = os.path.join(CONFIG_DIR, "config_4_20ma.json")
OUTPUT_DAC_COMMAND_FILE = os.path.join(PROJECT_ROOT, "AnalogOutputs", "dac_commands.json")

# --- VARIÁVEIS GLOBAIS SEGURAS ---
config_lock = threading.Lock()
calibration_config = {}
min_max_config = {}

sensor_data = {}
sensor_data_lock = threading.Lock()

# O "Sinalizador" (Flag) de Recálculo
g_config_changed = threading.Event()

# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---

def load_all_configs():
    """Carrega ambos os arquivos da pasta /configs."""
    global calibration_config, min_max_config
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            new_calib_config = json.load(f)
        with open(MIN_MAX_FILE, 'r') as f:
            new_min_max_config = json.load(f)

        with config_lock:
            calibration_config = new_calib_config
            min_max_config = new_min_max_config
        log(f"[Converter] Configurações de Calibração e Range recarregadas.")
    except Exception as e:
        log(f"[Converter] ERRO: Falha ao carregar arquivos de configuração: {e}")

def load_sensor_data():
    """Lê o JSON dos sensores (read/dados_endpoint.json)."""
    global sensor_data
    try:
        with open(SENSOR_DATA_FILE, 'r') as f:
            new_data = json.load(f)
        with sensor_data_lock:
            sensor_data = new_data
    except Exception:
        with sensor_data_lock:
            sensor_data = {}

def save_json_file(file_path, data):
    """Função genérica para salvar um arquivo JSON e forçar a escrita no disco."""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno()) 
        return True
    except Exception as e:
        log(f"[Converter] ERRO: Falha ao salvar o JSON {file_path}: {e}")
        return False

# --- CLASSE DO WATCHDOG (MONITOR DE CONFIGS) ---

class ConfigChangeHandler(FileSystemEventHandler):
    def _check_and_reload(self, event_path):
        global g_config_changed
        if event_path == CALIBRATION_FILE or event_path == MIN_MAX_FILE:
            log(f"[WATCHDOG] Detectada mudança em {event_path}!")
            time.sleep(0.1) 
            load_all_configs() 
            g_config_changed.set() 

    def on_modified(self, event): self._check_and_reload(event.src_path)
    def on_created(self, event): self._check_and_reload(event.src_path)
    def on_moved(self, event): self._check_and_reload(event.dest_path)

def start_config_monitor():
    event_handler = ConfigChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=CONFIG_DIR, recursive=False)
    observer.start()
    log(f"Monitorando o diretório {CONFIG_DIR} por mudanças...")
    return observer

# --- FUNÇÃO DE MAPEAMENTO (INTERPOLAÇÃO) ---

def map_value(x, in_min, in_max, out_min, out_max):
    if (in_max - in_min) == 0:
        return out_min
    x = max(min(x, in_max), in_min)
    value = (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    return max(min(value, out_max), out_min)

# --- FUNÇÃO PRINCIPAL ---

def main():
    global g_config_changed 
    log("[Converter] Iniciando serviço 'converter.py'...")
    previous_sensor_data = {}

    load_all_configs()
    config_monitor_observer = start_config_monitor()
    g_config_changed.set() 

    try: 
        while True:
            try:
                load_sensor_data()

                with config_lock:
                    curr_calib = calibration_config.copy()
                    curr_min_max = min_max_config.copy()
                
                with sensor_data_lock:
                    curr_sensors = sensor_data.copy()

                if not curr_sensors or not curr_calib:
                    time.sleep(1)
                    continue

                # Verifica mudanças
                if (curr_sensors == previous_sensor_data) and (not g_config_changed.is_set()):
                    time.sleep(1)
                    continue
                    
                log("\n[Converter] Recalculando Tensões do DAC...")
                output_voltages = {}

                # --- LOOP PARA OS 4 CANAIS DO DAC ---
                for i in range(1, 5):
                    sensor_key = f"channel_{i}"  # Ex: channel_1 (Entrada)
                    dac_key = f"channel_{i}"     # Ex: channel_1 (Calibração)

                    if sensor_key in curr_sensors and dac_key in curr_calib:
                        
                        # 1. Valor Real (já convertido pelo LoraMaster)
                        val_real = float(curr_sensors.get(sensor_key, 0.0))
                        
                        # 2. Range do Usuário
                        user_cfg = curr_min_max.get(sensor_key, {})
                        user_min = float(user_cfg.get("min", 0.0))
                        user_max = float(user_cfg.get("max", 100.0))
                        
                        # 3. Calibração Elétrica (Bits do DAC)
                        # (Usa as chaves genéricas SEM o número)
                        dac_min_bits = int(curr_calib[dac_key].get("TRIM_ZERO_BIT", 0))
                        dac_max_bits = int(curr_calib[dac_key].get("TRIM_SPAN_BIT", 4095))
                        
                        v_dac_min = (dac_min_bits / 4095.0) * 5.0
                        v_dac_max = (dac_max_bits / 4095.0) * 5.0
                        
                        # 4. Cálculo
                        voltage = map_value(val_real, user_min, user_max, v_dac_min, v_dac_max)
                        
                        output_voltages[f"channel_{i-1}"] = voltage
                        
                        log(f"  CH{i}: Entrada={val_real:.2f} -> DAC: {voltage:.3f}V")

                save_json_file(OUTPUT_DAC_COMMAND_FILE, output_voltages)
                
                previous_sensor_data = curr_sensors
                g_config_changed.clear()
                
                time.sleep(0.5) 
            
            except Exception as e:
                log(f"[Converter] Erro no loop principal: {e}")
                time.sleep(5) 

    except KeyboardInterrupt:
        log("[Converter] Interrompido.")
    
    finally:
        config_monitor_observer.stop()
        config_monitor_observer.join()

if __name__ == "__main__":
    main()