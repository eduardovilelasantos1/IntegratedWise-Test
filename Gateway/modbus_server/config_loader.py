import json
import os

# Caminho da pasta configs
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'configs')

def load_modbus_config():
    """Carrega o arquivo config_modbus.json"""
    with open(os.path.join(CONFIG_DIR, 'config_modbus.json'), 'r') as f:
        return json.load(f)

def save_modbus_config(data):
    """Salva os dados no arquivo config_modbus.json"""
    with open(os.path.join(CONFIG_DIR, 'config_modbus.json'), 'w') as f:
        json.dump(data, f, indent=4)
