import sys
import os
import json
import time
from opcua import Server, ua

# Adiciona o diretório raiz ao sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from opcua_server.config_loader import load_opcua_config

# --- CAMINHOS ---
DATA_ENDPOINT_PATH = os.path.join(PROJECT_ROOT, "read", "dados_endpoint.json")
CONFIG_SENSORS_PATH = os.path.join(PROJECT_ROOT, "configs", "config_min_max.json")
OPCUA_DATA_FILE = os.path.join(os.path.dirname(__file__), "opcua_data.json")

# Carrega configurações
config = load_opcua_config()

if not os.path.exists(DATA_ENDPOINT_PATH):
    # Apenas aviso, não crasha, pois o arquivo pode ser criado depois
    print(f"Aviso: Ficheiro de dados não encontrado em: {DATA_ENDPOINT_PATH}")

# --- INICIALIZAÇÃO DO SERVIDOR ---
server = Server()
server.set_endpoint(config["SERVER_URL"])
server.set_server_name(config["SERVER_NAME"])

# --- SEGURANÇA ---
cert_path = os.path.join(PROJECT_ROOT, config["CERT_PATH"])
key_path = os.path.join(PROJECT_ROOT, config["KEY_PATH"])

if os.path.exists(cert_path) and os.path.exists(key_path):
    server.load_certificate(cert_path)
    server.load_private_key(key_path)
    server.set_security_policy([
        ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt,
        ua.SecurityPolicyType.Basic256Sha256_Sign,
        ua.SecurityPolicyType.NoSecurity,
    ])
else:
    print("Aviso: Certificados não encontrados. Rodando sem segurança completa.")

def user_manager(isession, username, password):
    return config["AUTHORIZED_USERS"].get(username) == password

server.user_manager.set_user_manager(user_manager)

# --- ESPAÇO DE NOMES E VARIÁVEIS DINÂMICAS ---
uri = config["SERVER_NAME"]
idx = server.register_namespace(uri)
node = server.get_objects_node()
Param = node.add_object(idx, config["MAIN_NODE_NAME"])

# Dicionário para guardar as referências das variáveis OPC UA
# Chave = ID do sensor (ex: "nivel_acucar"), Valor = Objeto Variável OPC UA
opcua_vars = {}

# 1. Carrega a lista de sensores da configuração
try:
    with open(CONFIG_SENSORS_PATH, 'r') as f:
        sensors_config = json.load(f)
except Exception as e:
    print(f"Erro ao ler configuração de sensores: {e}")
    sensors_config = {}

# 2. Cria as variáveis no servidor OPC UA
for sensor_key, sensor_data in sensors_config.items():
    # Usa o "label" como nome de exibição, ou a chave se não houver label
    display_name = sensor_data.get("label", sensor_key)
    initial_value = 0.0
    
    # Cria a variável
    my_var = Param.add_variable(idx, display_name, initial_value)
    my_var.set_writable() # Permite escrita se necessário (mas aqui só vamos ler)
    
    # Guarda a referência para atualizar depois
    opcua_vars[sensor_key] = my_var
    print(f"Variável OPC UA criada: {display_name} ({sensor_key})")

server.start()
print(f"Servidor OPC UA iniciado em {config['SERVER_URL']}")

try:
    while True:
        try:
            # --- LEITURA DOS DADOS ---
            if os.path.exists(DATA_ENDPOINT_PATH):
                with open(DATA_ENDPOINT_PATH, 'r') as f:
                    sensor_values = json.load(f)
            else:
                sensor_values = {}

            dados_para_web_legado = {} # Apenas para compatibilidade se necessário

            # --- ATUALIZAÇÃO DAS VARIÁVEIS ---
            for sensor_key, opcua_var in opcua_vars.items():
                
                # Pega o valor do JSON de dados (ou 0.0)
                valor_raw = sensor_values.get(sensor_key, 0.0)
                
                try:
                    valor_float = float(valor_raw)
                except:
                    valor_float = 0.0

                # Atualiza no servidor OPC UA
                opcua_var.set_value(valor_float)
                
                # Guarda para o log/arquivo legado
                dados_para_web_legado[sensor_key] = valor_float

            # Salva arquivo legado (opcional, para debug)
            with open(OPCUA_DATA_FILE, "w") as json_file:
                json.dump(dados_para_web_legado, json_file, indent=4)

            # Log simplificado
            # print(f"OPC UA Atualizado: {dados_para_web_legado}")

        except (json.JSONDecodeError, FileNotFoundError):
            pass # Ignora erros de leitura momentâneos
        except Exception as e:
            print(f"Erro no loop OPC UA: {e}")

        time.sleep(2)

except KeyboardInterrupt:
    print("\nEncerrando servidor OPC UA...")
finally:
    server.stop()
    print("Servidor OPC UA finalizado.")