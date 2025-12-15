# -*- coding: utf-8 -*-
# web_server/defaults.py

"""
Configurações padrão de fábrica usadas pelo botão de reset.
"""

import bcrypt

# ==========================================================
#  DEFAULT DE USUÁRIOS (senha admin/admin)
# ==========================================================
DEFAULT_USERS = {
    "admin": {
        "password": bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode('utf-8')
    }
}

# ==========================================================
#  DEFAULT LORA
# ==========================================================
DEFAULT_LORA_CONFIG = {
    "classe": "C",
    "janela": "15s",
    "power": 20,
    "bandwidth": "500kHz",
    "spreading_factor": 7,
    "coding_rate": "4/5",
    "wake_interval": 30
}

# ==========================================================
#  DEFAULT MODBUS
# ==========================================================
DEFAULT_MODBUS_CONFIG = {
    "MODBUS_HOST": "0.0.0.0",
    "MODBUS_PORT": 502,
    "UNIT_ID": 1,
    "SERVER_IDENTITY": {
        "VendorName": "WK Solucoes",
        "ProductCode": "WK-GW-01",
        "VendorUrl": "www.wksolucoes.com.br",
        "ProductName": "Gateway IoT",
        "ModelName": "Modelo-Base",
        "MajorMinorRevision": "1.0"
    }
}

# ==========================================================
#  DEFAULT OPC UA
# ==========================================================
DEFAULT_OPCUA_CONFIG = {
    "SERVER_NAME": "ServidorOPCUA-WK",
    "SERVER_URL": "opc.tcp://0.0.0.0:4840",
    "MAIN_NODE_NAME": "Sensores",
    "AUTHORIZED_USERS": {
        "admin": "12345"
    },
    "CERT_PATH": "server-cert.pem",
    "KEY_PATH": "server-key.pem"
}

# ==========================================================
#  DEFAULT ALARMES
# ==========================================================
DEFAULT_ALARMES_CONFIG = {
    f"relay_{i}": {"source": "", "alarm_name": "", "type": "high", "limit_real": 0, "limit_bits": 0}
    for i in range(1, 10)
}

# ==========================================================
#  DEFAULT CALIBRAÇÃO 4-20mA
# ==========================================================
DEFAULT_4_20MA_CONFIG = {
    "CHANNEL1": {"TRIM_ZERO_BIT": 900, "TRIM_SPAN_BIT": 1200},
    "CHANNEL2": {"TRIM_ZERO_BIT": 900, "TRIM_SPAN_BIT": 1200},
    "CHANNEL3": {"TRIM_ZERO_BIT": 900, "TRIM_SPAN_BIT": 1200},
    "CHANNEL4": {"TRIM_ZERO_BIT": 900, "TRIM_SPAN_BIT": 1200}
}

# ==========================================================
#  ⭐ DEFAULT MIN/MAX (RESET DE NOMES E CALIBRAÇÃO)
# ==========================================================
DEFAULT_MIN_MAX_CONFIG = {
    "channel_1": {"label": "Sensor 1", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 1},
    "channel_2": {"label": "Sensor 2", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 2},
    "channel_3": {"label": "Sensor 3", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 3},
    "channel_4": {"label": "Sensor 4", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 4},
    "channel_5": {"label": "Sensor 5", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 5},
    "channel_6": {"label": "Sensor 6", "unit": "-", "min": 0.0, "max": 4095.0, "channel": 6},

    # ⭐ Estes NÃO devem ser resetados
    "battery_voltage": {"label": "Tensão da Bateria", "unit": "V", "min": 0.0, "max": 15.0},
    "battery_avg_current": {"label": "Corrente Média", "unit": "mA", "min": 0.0, "max": 500.0},
    "consumo_mah": {"label": "Consumo Acumulado", "unit": "mAh", "min": 0.0, "max": 54000.0},
    "comm_time": {"label": "Tempo sem Comunicação", "unit": "s", "min": 0.0, "max": 86400.0}
}
