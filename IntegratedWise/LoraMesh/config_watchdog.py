import hashlib
import time
import subprocess
import os
import sys

# Caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "configs", "config_lora.json")
HASH_FILE = os.path.join(BASE_DIR, "config_lora_applied.hash")
RECONFIG_FLAG = os.path.join(PROJECT_ROOT, "configs", "reconfig.flag")

def file_hash(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()
    except FileNotFoundError:
        return None

def load_last_hash():
    if not os.path.exists(HASH_FILE):
        return None
    with open(HASH_FILE, "r") as f:
        return f.read().strip()

def save_hash(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)

def run_configurator():
    print("🔧 [WATCHDOG] Rodando configurador auxiliar...")
    # Se lora_configurator.py estiver na mesma pasta, use:
    subprocess.run(["python3", os.path.join(BASE_DIR, "lora_configurator.py")])

def create_reconfig_flag():
    # Cria o arquivo vazio para avisar o Master
    with open(RECONFIG_FLAG, 'w') as f:
        pass
    print("🚩 [WATCHDOG] Flag de reconfiguração criada.")

def main():
    print("[WATCHDOG] Iniciando Monitoramento + Master...")

    # 1. Verifica estado inicial
    last_hash = load_last_hash()
    current_hash = file_hash(CONFIG_FILE)

    if current_hash != last_hash:
        print("🟡 Configuração inicial diferente. Sincronizando...")
        save_hash(current_hash)
        run_configurator()
    
    # 2. Inicia o Master em PROCESSO SEPARADO (Não bloqueante)
    # Usa Popen para que o watchdog continue rodando
    master_process = subprocess.Popen(["python3", os.path.join(BASE_DIR, "LoraMaster.py")])
    print(f"🚀 [WATCHDOG] LoraMaster iniciado (PID: {master_process.pid})")

    # 3. Loop de Monitoramento
    try:
        while True:
            time.sleep(3) # Verifica a cada 3 segundos

            # Verifica se o Master ainda está vivo
            if master_process.poll() is not None:
                print("❌ [WATCHDOG] O LoraMaster fechou inesperadamente! Reiniciando...")
                master_process = subprocess.Popen(["python3", os.path.join(BASE_DIR, "LoraMaster.py")])

            # Verifica alteração no arquivo
            current_hash = file_hash(CONFIG_FILE)
            if current_hash != last_hash:
                print("\n============================")
                print("change Detectada no JSON!")
                print("============================")
                
                # Atualiza o hash para não disparar de novo
                save_hash(current_hash)
                last_hash = current_hash
                
                # Opcional: Rodar scripts auxiliares
                run_configurator()
                
                # CRUCIAL: Avisa o Master através da Flag
                create_reconfig_flag()
                
    except KeyboardInterrupt:
        print("\n[WATCHDOG] Parando Master e encerrando...")
        master_process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()