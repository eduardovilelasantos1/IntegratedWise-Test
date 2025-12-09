# -*- coding: utf-8 -*-
# web_server/defaults.py

"""
Este arquivo contém as configurações padrão de fábrica para todos os
arquivos .json do sistema. A função de reset utilizará estes dicionários
para restaurar o estado original dos arquivos de configuração.
"""

# Configuração padrão para LoRa
DEFAULT_LORA_CONFIG = {
    "classe": "C",
    "janela": "15s",
    "power": 20,
    "bandwidth": "500kHz",
    "spreading_factor": 7,
    "coding_rate": "4/5"
}

# Configuração padrão para Modbus
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

# Configuração padrão para OPC UA
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

# Configuração padrão para Alarmes (todos desativados)
DEFAULT_ALARMES_CONFIG = {
    "OUTPUT1": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT2": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT3": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT4": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT5": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT6": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT7": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT8": {"COD ALARME": 0, "MAX VALUE": 0},
    "OUTPUT9": {"COD ALARME": 0, "MAX VALUE": 0}
}

# Configuração padrão para Calibração 4-20mA
DEFAULT_4_20MA_CONFIG = {
    "CHANNEL1": {"TRIM_ZERO_BIT1": 900, "TRIM_SPAN_BIT1": 1200},
    "CHANNEL2": {"TRIM_ZERO_BIT2": 900, "TRIM_SPAN_BIT2": 1200},
    "CHANNEL3": {"TRIM_ZERO_BIT3": 900, "TRIM_SPAN_BIT3": 1200},
    "CHANNEL4": {"TRIM_ZERO_BIT4": 900, "TRIM_SPAN_BIT4": 1200}
}