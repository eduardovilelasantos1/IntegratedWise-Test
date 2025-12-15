import json
import os

# Caminho absoluto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "config_lora.json")

# Tabelas de conversão Radioenge
BW_MAP = { "125kHz": 0x00, "250kHz": 0x01, "500kHz": 0x02 }
SF_MAP = { 7: 0x07, 8: 0x08, 9: 0x09, 10: 0x0A, 11: 0x0B, 12: 0x0C }
CR_MAP = { "4/5": 0x01, "4/6": 0x02, "4/7": 0x03, "4/8": 0x04 }
CLASS_MAP = { "A": 0x00, "C": 0x02 }
WINDOW_MAP = { "5s": 0x00, "10s": 0x01, "15s": 0x02 }
WINDOW_SEC_MAP = { "5s": 5, "10s": 10, "15s": 15 }

def load_lora_config():
    """Lê o JSON e retorna o dicionário."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def map_config_to_bytes(config):
    """Converte o dicionário JSON para valores brutos do rádio."""
    if not config:
        # Padrão de segurança se o arquivo falhar
        return {
            "power": 20, "bw": 0x00, "sf": 0x07, "cr": 0x01,
            "classe": 0x02, "janela": 0x00, "window_sec": 5,
            "wake": 30 
        }

    # Extrai valores com defaults seguros
    power = int(config.get("power", 20))
    bw = BW_MAP.get(config.get("bandwidth", "125kHz"), 0x00)
    sf = SF_MAP.get(int(config.get("spreading_factor", 7)), 0x07)
    cr = CR_MAP.get(config.get("coding_rate", "4/5"), 0x01)

    classe = CLASS_MAP.get(config.get("classe", "C"), 0x02)
    
    janela_str = config.get("janela", "5s")
    janela_byte = WINDOW_MAP.get(janela_str, 0x00)
    janela_sec = WINDOW_SEC_MAP.get(janela_str, 5)

    # Lógica de Sleep
    wake_val = int(config.get("wake_interval", 30))
    
    # Se for Classe C, força tempo acordado infinito (0)
    # Se for Classe A, mantém o tempo configurado
    if classe == 0x02:
        wake_val = 0
    else:
        if wake_val < 5: wake_val = 5
        if wake_val > 255: wake_val = 255

    return {
        "power": power & 0xFF, 
        "bw": bw & 0xFF, 
        "sf": sf & 0xFF, 
        "cr": cr & 0xFF,
        "classe": classe & 0xFF,
        "janela": janela_byte & 0xFF,
        "window_sec": janela_sec,
        "wake": wake_val & 0xFF 
    }

def calcular_crc(buffer):
    """Calcula CRC-16 (Modbus) para os pacotes."""
    crc = 0xC181
    poly = 0xA001
    for byte in buffer:
        crc ^= byte & 0x00FF
        for _ in range(8):
            if (crc & 1): crc = (crc >> 1) ^ poly
            else:         crc >>= 1
    return crc & 0xFFFF