import sys
import os
import json
from threading import Thread, Lock
from time import sleep

from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock

# Adiciona o diretório raiz ao sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from modbus_server.config_loader import load_modbus_config

# --- CAMINHOS ---
DATA_ENDPOINT_PATH = os.path.join(PROJECT_ROOT, "read", "dados_endpoint.json")
CONFIG_SENSORS_PATH = os.path.join(PROJECT_ROOT, "configs", "config_min_max.json")
MODBUS_DATA_FILE = os.path.join(os.path.dirname(__file__), 'modbus_data.json')

file_lock = Lock()

def salvar_modbus_data_json(data):
    """Salva os dados para debug."""
    with file_lock:
        try:
            with open(MODBUS_DATA_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Erro ao salvar modbus_data.json: {e}")

class ServidorMODBUS:
    def __init__(self, host_ip, port, unit_id=1, identity_data=None):
        self.unit_id = unit_id
        self.host_ip = host_ip
        self.port = port

        # Inicializa blocos de dados (Holding Registers Inteiros de 16-bit)
        self.store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0]*100),
            co=ModbusSequentialDataBlock(0, [0]*100),
            hr=ModbusSequentialDataBlock(0, [0]*100), 
            ir=ModbusSequentialDataBlock(0, [0]*100)
        )

        self.context = ModbusServerContext(slaves={unit_id: self.store}, single=False)

        self.identity = ModbusDeviceIdentification()
        if identity_data:
            for key, value in identity_data.items():
                setattr(self.identity, key, value)

    def atualizar_dados(self):
        print(f"Servidor Modbus a ler sensores (Modo Inteiro Arredondado)...")

        while True:
            try:
                # 1. Lê configs e dados
                if os.path.exists(CONFIG_SENSORS_PATH):
                    with open(CONFIG_SENSORS_PATH, 'r') as f:
                        config_sensors = json.load(f)
                else:
                    config_sensors = {}

                if os.path.exists(DATA_ENDPOINT_PATH):
                    with open(DATA_ENDPOINT_PATH, 'r') as f:
                        sensor_data = json.load(f)
                else:
                    sensor_data = {}

                valores_registradores = []
                dados_web = {}
                
                # 2. Processa cada sensor na ordem correta
                for i, (sensor_key, sensor_info) in enumerate(config_sensors.items()):
                    valor_bruto = sensor_data.get(sensor_key, 0.0)
                    try:
                        valor_float = float(valor_bruto)
                    except:
                        valor_float = 0.0
                    
                    # --- LÓGICA DE ARREDONDAMENTO ---
                    # Arredonda para o inteiro mais próximo (ex: 33.56 -> 34)
                    valor_int = int(round(valor_float))
                    
                    valores_registradores.append(valor_int)
                    
                    # Log para debug (R40001, R40002...)
                    reg_addr = 40001 + i
                    dados_web[f"R{reg_addr}"] = valor_int

                # 3. Escreve na memória do Modbus
                if valores_registradores:
                    # Escreve a partir do endereço 0 (que corresponde ao 40001 lógico)
                    self.store.setValues(3, 0, valores_registradores)
                
                # 4. Salva log
                salvar_modbus_data_json(dados_web)

            except Exception as e:
                print(f"[Modbus] Erro no loop: {e}")

            sleep(2)

    def run(self):
        print(f"Iniciando Servidor Modbus em {self.host_ip}:{self.port} (ID={self.unit_id})...")
        
        # Inicia a thread de atualização
        t = Thread(target=self.atualizar_dados, daemon=True)
        t.start()
        
        try:
            StartTcpServer(
                context=self.context,
                identity=self.identity,
                address=(self.host_ip, self.port)
            )
        except Exception as e:
            print(f"ERRO CRÍTICO ao iniciar servidor Modbus: {e}")
            print("DICA: Verifique se a porta já está em uso (sudo fuser -k 1502/tcp)")

if __name__ == "__main__":
    try:
        config = load_modbus_config()
        s = ServidorMODBUS(
            host_ip=config['MODBUS_HOST'],
            port=config['MODBUS_PORT'],
            unit_id=config['UNIT_ID'],
            identity_data=config['SERVER_IDENTITY']
        )
        s.run()
    except Exception as e:
        print(f"Erro na inicialização: {e}")