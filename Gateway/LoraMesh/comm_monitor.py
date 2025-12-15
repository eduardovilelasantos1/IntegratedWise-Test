import os
import json
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMM_FILE = os.path.join(BASE_DIR, "communication_time.json")


# ======================================================
#  Inicialização do JSON, caso não exista
# ======================================================
def _init_file():
    if not os.path.exists(COMM_FILE):
        data = {
            "last_success": time.time(),
            "elapsed_sec": 0.0
        }
        with open(COMM_FILE, "w") as f:
            json.dump(data, f, indent=4)


# ======================================================
#  Carregar JSON
# ======================================================
def _load():
    try:
        with open(COMM_FILE, "r") as f:
            return json.load(f)
    except:
        _init_file()
        return _load()


# ======================================================
#  Salvar JSON
# ======================================================
def _save(data):
    try:
        with open(COMM_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except:
        pass


# ======================================================
#  Atualiza o timestamp do último sucesso de comunicação
# ======================================================
def update_success_timestamp():
    _init_file()
    data = _load()

    data["last_success"] = time.time()
    data["elapsed_sec"] = 0.0  # zera o contador

    _save(data)


# ======================================================
#  Atualiza elapsed_sec baseado no último sucesso
# ======================================================
def update_elapsed_time():
    _init_file()
    data = _load()

    last = data.get("last_success", time.time())
    elapsed = time.time() - last

    data["elapsed_sec"] = round(elapsed, 1)

    _save(data)


# ======================================================
#  Retorna informações completas
# ======================================================
def get_comm_info():
    _init_file()
    return _load()
