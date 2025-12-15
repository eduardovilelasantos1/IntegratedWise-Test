# web_server/routes_config.py

import os
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash
)

from web_server.decorators import login_required
from web_server.services.json_store import load_json, save_json
from web_server.logging_config import setup_logger
from web_server.defaults import (
    DEFAULT_LORA_CONFIG,
    DEFAULT_MODBUS_CONFIG,
    DEFAULT_OPCUA_CONFIG
)

logger = setup_logger(__name__)

routes_config_bp = Blueprint("routes_config", __name__)


@routes_config_bp.route("/configuracao", methods=["GET"])
@login_required
def configuracao():
    logger.debug("Acessando tela de configuração")

    try:
        modbus = load_json("config_modbus.json")
        opcua = load_json("config_opcua.json")
        lora = load_json("config_lora.json")
        battery = load_json("config_battery.json")

        logger.info("Configurações carregadas com sucesso")

        return render_template(
            "settings.html",
            modbus_host=modbus.get("MODBUS_HOST", ""),
            modbus_port=modbus.get("MODBUS_PORT", 502),
            unit_id=modbus.get("UNIT_ID", 1),
            server_identity=modbus.get("SERVER_IDENTITY", {}),
            opcua_server_name=opcua.get("SERVER_NAME", ""),
            opcua_server_url=opcua.get("SERVER_URL", ""),
            opcua_main_node=opcua.get("MAIN_NODE_NAME", ""),
            opcua_users=opcua.get("AUTHORIZED_USERS", {}),
            lora_config=lora,
            battery_config=battery
        )

    except Exception as e:
        logger.exception("Erro ao carregar configurações")
        flash("Erro ao carregar configurações.", "alert-danger")
        return redirect(url_for("routes_config.configuracao"))


@routes_config_bp.route("/salvar_configuracao", methods=["POST"])
@login_required
def salvar_configuracao():
    logger.info("Solicitação para salvar configurações")

    try:
        current_lora = load_json("config_lora.json") or {}

        lora_config = {
            "classe": request.form.get(
                "lora_classe", current_lora.get("classe", "C")
            ),
            "janela": request.form.get(
                "lora_janela", current_lora.get("janela", "15s")
            ),
            "bandwidth": request.form.get(
                "lora_bandwidth", current_lora.get("bandwidth", "125kHz")
            ),
            "spreading_factor": int(
                request.form.get(
                    "lora_spreading_factor",
                    current_lora.get("spreading_factor", 7)
                )
            ),
            "coding_rate": request.form.get(
                "lora_coding_rate", current_lora.get("coding_rate", "4/5")
            ),
            "wake_interval": int(
                request.form.get(
                    "lora_wake_interval",
                    current_lora.get("wake_interval", 30)
                )
            ),
            "power": int(current_lora.get("power", 20))
        }

        save_json("config_lora.json", lora_config)
        logger.info("Configuração LoRa salva")

        # Flag para reconfiguração do LoRa
        reconfig_flag = os.path.join(
            os.path.dirname(__file__), "..", "configs", "reconfig.flag"
        )
        with open(reconfig_flag, "w"):
            pass

        logger.debug("reconfig.flag criado")

        # Bateria
        capacity = int(request.form.get("battery_capacity", 54000))
        save_json("config_battery.json", {"capacity_mah": capacity})
        logger.info("Configuração de bateria salva")

        # Modbus
        modbus_config = {
            "MODBUS_HOST": request.form.get("modbus_host", "0.0.0.0"),
            "MODBUS_PORT": int(request.form.get("modbus_port", 502)),
            "UNIT_ID": int(request.form.get("unit_id", 1)),
            "SERVER_IDENTITY": {
                "VendorName": request.form.get("vendor_name", ""),
                "ProductCode": request.form.get("product_code", ""),
                "VendorUrl": request.form.get("vendor_url", ""),
                "ProductName": request.form.get("product_name", ""),
                "ModelName": request.form.get("model_name", ""),
                "MajorMinorRevision": request.form.get("revision", "")
            }
        }
        save_json("config_modbus.json", modbus_config)
        logger.info("Configuração Modbus salva")

        # OPC UA
        users_raw = request.form.get("opcua_users", "")
        users = {}

        if users_raw:
            for pair in users_raw.split(","):
                if ":" in pair:
                    user, pwd = pair.strip().split(":")
                    users[user.strip()] = pwd.strip()

        opcua_config = {
            "SERVER_NAME": request.form.get("opcua_server_name", "LoRaServer"),
            "SERVER_URL": request.form.get(
                "opcua_server_url", "opc.tcp://0.0.0.0:4840"
            ),
            "MAIN_NODE_NAME": request.form.get(
                "opcua_main_node", "Sensores"
            ),
            "AUTHORIZED_USERS": users,
            "CERT_PATH": "server-cert.pem",
            "KEY_PATH": "server-key.pem"
        }
        save_json("config_opcua.json", opcua_config)
        logger.info("Configuração OPC UA salva")

        flash("Configurações salvas!", "alert-success")

    except Exception as e:
        logger.exception("Erro ao salvar configurações")
        flash("Erro ao salvar configurações.", "alert-danger")

    return redirect(url_for("routes_config.configuracao"))
