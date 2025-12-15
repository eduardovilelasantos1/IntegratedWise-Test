import json
import os

CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'configs')

def load_opcua_config():
    with open(os.path.join(CONFIG_DIR, 'config_opcua.json'), 'r') as f:
        return json.load(f)
