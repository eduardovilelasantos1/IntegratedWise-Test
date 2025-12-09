# --- Importações de Bibliotecas ---
import time
import json
import os
import sys
from smbus2 import SMBus

# Ajuste de path para importar utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.logger import log
from utils.config import I2C_BUS, MCP4728_DEVICES
from utils.dac_controller import MCP4728

# --- CAMINHO DO FICHEIRO DE COMANDO ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMAND_FILE_PATH = os.path.join(SCRIPT_DIR, "dac_commands.json")

# --- TAXA DE ATUALIZAÇÃO ---
POLL_RATE = 0.1  # 10 vezes por segundo

# --- FUNÇÃO DE LER JSON ---
def load_command_file():
    """
    Carrega os comandos de tensão mais recentes.
    Retorna None se falhar ou se o arquivo estiver vazio/incompleto.
    """
    try:
        if not os.path.exists(COMMAND_FILE_PATH):
            return None
            
        with open(COMMAND_FILE_PATH, 'r') as f:
            data = json.load(f)
            return data
    except Exception:
        # Não loga erro aqui para não poluir o terminal (leitura concorrente)
        return None

# --- Função Principal ---
def main():
    log("[DAC Control] Iniciando Barramento I2C...")
    try:
        bus = SMBus(I2C_BUS)
    except Exception as e:
        log(f"[DAC Control] ERRO FATAL I2C: {e}")
        return

    log("[DAC Control] Iniciando DACs MCP4728...")
    try:
        dacs = [MCP4728(dev["address"], dev["busy_pin"], bus) for dev in MCP4728_DEVICES]
    except Exception as e:
        log(f"[DAC Control] ERRO ao iniciar DACs: {e}")
        return

    # Guarda os comandos anteriores para evitar escritas desnecessárias
    previous_commands = {}

    log("[DAC Control] DACs configurados. Entrando em loop (Músculo)...")

    try:
        while True:
            # 1. Lê o ficheiro de comandos
            commands = load_command_file()

            # 2. Se falhou a leitura, espera e tenta de novo
            if not commands:
                time.sleep(0.5)
                continue

            # 3. Se os comandos não mudaram, não faz nada (eficiência)
            if commands == previous_commands:
                time.sleep(POLL_RATE)
                continue

            # 4. COMANDOS MUDARAM! Atualiza o Hardware
            
            # Pega a tensão para cada canal (com 0.0V como padrão)
            v0 = float(commands.get("channel_0", 0.0))
            v1 = float(commands.get("channel_1", 0.0))
            v2 = float(commands.get("channel_2", 0.0))
            v3 = float(commands.get("channel_3", 0.0))

            # --- LOG LIMPO E ORGANIZADO ---
            log(f"[DAC Update] CH0: {v0:.3f}V | CH1: {v1:.3f}V | CH2: {v2:.3f}V | CH3: {v3:.3f}V")

            # --- Envia para o Hardware ---
            # (use_eeprom=False para não desgastar a memória do chip)
            dacs[0].set_voltage_and_config(0, v0, use_eeprom=False)
            dacs[0].set_voltage_and_config(1, v1, use_eeprom=False)
            dacs[0].set_voltage_and_config(2, v2, use_eeprom=False)
            dacs[0].set_voltage_and_config(3, v3, use_eeprom=False)

            # 5. Atualiza o estado anterior
            previous_commands = commands
            
            # 6. Pausa
            time.sleep(POLL_RATE)

    except KeyboardInterrupt:
        log("\n[DAC Control] Interrompido pelo usuário.")
        
    except Exception as e:
        log(f"[DAC Control] Erro inesperado: {e}")

    finally:
        log("[DAC Control] Zerando saídas do DAC por segurança...")
        try:
            dacs[0].set_voltage_and_config(0, 0.0, use_eeprom=False)
            dacs[0].set_voltage_and_config(1, 0.0, use_eeprom=False)
            dacs[0].set_voltage_and_config(2, 0.0, use_eeprom=False)
            dacs[0].set_voltage_and_config(3, 0.0, use_eeprom=False)
        except:
            pass
        log("[DAC Control] Programa encerrado.")

if __name__ == "__main__":
    main()