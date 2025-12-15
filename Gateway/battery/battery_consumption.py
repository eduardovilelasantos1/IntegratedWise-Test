import time
import json
import os
import traceback
from datetime import datetime

class BatteryMonitor:
    def __init__(self, battery_file_path):
        print(f"[BAT] Inicializando Monitor (Modo Detalhado)...")
        self.battery_file = battery_file_path
        
        # Caminhos
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.abspath(os.path.join(self.base_dir, ".."))
        self.config_bat_file = os.path.join(self.project_root, "configs", "config_battery.json")
        self.config_lora_file = os.path.join(self.project_root, "configs", "config_lora.json")
        self.reset_flag = os.path.join(self.project_root, "configs", "reset_battery.flag")
        
        # Hardware Constants
        self.INA226_BUS_LSB = 0.00125 
        self.INA226_SHUNT_LSB = 0.0000025
        self.R_SHUNT = 0.02
        
        # Corrente fixa Deep Sleep
        self.SLEEP_CURRENT_MA = 13.0
        
        # Inicializa capacidade (será atualizada no loop)
        self.total_capacity_mah = 3000.0 
        
        self.accumulated_mah = self._load_accumulated_mah()
        self.last_calc_time = time.time()

    def _load_json(self, filepath):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f: return json.load(f)
        except: pass
        return {}

    def _load_accumulated_mah(self):
        try:
            if os.path.exists(self.battery_file):
                with open(self.battery_file, 'r') as f:
                    val = float(json.load(f).get("consumo_acumulado_mah", 0.0))
                    return val
        except: pass
        return 0.0

    def _get_active_window_seconds(self):
        """Lê config do LoRa para saber tempo acordado (Janela + 4s)"""
        lora_cfg = self._load_json(self.config_lora_file)
        classe = lora_cfg.get("classe", "A")
        if classe == "C" or classe == 0x02: return 999999.0 
        
        try:
            val_str = str(lora_cfg.get("janela", "5s")).lower().replace("s", "")
            window_sec = int(val_str)
        except: window_sec = 5 
        return float(window_sec + 4.0)

    def process_data(self, bus_raw, shunt_raw):
        try:
            # 1. Config Dinâmica
            bat_config = self._load_json(self.config_bat_file)
            new_capacity = float(bat_config.get("capacity_mah", 3000.0))
            if new_capacity != self.total_capacity_mah:
                self.total_capacity_mah = new_capacity

            # 2. Reset Manual
            if os.path.exists(self.reset_flag):
                print("[BAT] 🚩 Reset solicitado! Zerando consumo.")
                self.accumulated_mah = 0.0
                try: os.remove(self.reset_flag)
                except: pass

            # 3. Conversão (Valores Reais Medidos)
            voltage_v = round(bus_raw * self.INA226_BUS_LSB, 2)
            shunt_v = shunt_raw * self.INA226_SHUNT_LSB
            current_active_ma = round((shunt_v / self.R_SHUNT) * 1000, 1)

            # 4. Definição dos Tempos
            curr_time = time.time()
            dt_total = curr_time - self.last_calc_time
            if dt_total > 3600 or dt_total < 0: dt_total = 0 
            
            time_on_limit = self._get_active_window_seconds()
            
            if time_on_limit > 900000: # Classe C
                dt_active = dt_total
                dt_sleep = 0.0
            else:
                dt_active = min(dt_total, time_on_limit)
                dt_sleep = max(0.0, dt_total - dt_active)

            # 5. Cálculo Consumo (O que o usuário quer ver)
            mah_active = current_active_ma * (dt_active / 3600.0)
            mah_sleep = self.SLEEP_CURRENT_MA * (dt_sleep / 3600.0)
            total_inc = mah_active + mah_sleep
            
            self.accumulated_mah += total_inc
            self.last_calc_time = curr_time

            # 6. Média Efetiva (Weighted Average)
            # É essa corrente que define a duração da bateria no longo prazo
            avg_current_effective = 0.0
            if dt_total > 0:
                avg_current_effective = ((current_active_ma * dt_active) + (self.SLEEP_CURRENT_MA * dt_sleep)) / dt_total
            else:
                avg_current_effective = self.SLEEP_CURRENT_MA

            # 7. Porcentagem e Dias
            remaining_mah = self.total_capacity_mah - self.accumulated_mah
            percentage = (remaining_mah / self.total_capacity_mah) * 100.0
            percentage = max(0.0, min(100.0, percentage))

            days_left = 0.0
            if avg_current_effective > 0 and remaining_mah > 0:
                hours_left = remaining_mah / avg_current_effective
                days_left = hours_left / 24.0
            elif remaining_mah <= 0: days_left = 0.0
            else: days_left = 999.0

            # 8. Salva e RETORNA DETALHES EXTRAS
            self._save_battery_file(voltage_v, current_active_ma, percentage, days_left)

            # Retorna 8 valores para o LoraMaster printar tudo
            return (voltage_v, current_active_ma, self.accumulated_mah, 
                    round(percentage, 1), round(days_left, 1), 
                    dt_active, dt_sleep, avg_current_effective)

        except Exception as e:
            print(f"[BAT-ERRO] {e}")
            traceback.print_exc()
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    def _save_battery_file(self, voltage, current, percentage, days_left):
        data_bat = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "consumo_acumulado_mah": round(self.accumulated_mah, 6),
            "capacidade_total_mah": self.total_capacity_mah,
            "voltage": voltage,
            "current": current,
            "bat_percent": round(percentage, 1),
            "bat_days": round(days_left, 1)
        }
        try:
            with open(self.battery_file, 'w') as f:
                json.dump(data_bat, f, indent=4)
                os.fsync(f.fileno())
        except: pass