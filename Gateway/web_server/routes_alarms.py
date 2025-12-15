# web_server/routes_alarms.py

import os
import json
from flask import (
    Blueprint, render_template,
    request, redirect, url_for, flash, jsonify
)

from web_server.decorators import login_required
from web_server.services.json_store import load_json, save_json
from web_server.logging_config import setup_logger

logger = setup_logger(__name__)

routes_alarms_bp = Blueprint("routes_alarms", __name__)

CONFIG_ALARMES_FILE = "config_alarmes.json"
STATUS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "Alarms", "alarmes_status.json")
)


@routes_alarms_bp.route("/alarmes", methods=["GET", "POST"])
@login_required
def alarmes():
    logger.debug("Acessando tela de configuração de alarmes")

    sensor_config = load_json("config_min_max.json")

    if request.method == "POST":
        logger.info("Salvando configuração de alarmes")

        try:
            updated_alarms = {}

            for i in range(1, 10):
                relay_key = f"relay_{i}"

                source = request.form.get(f"{relay_key}_source", "")
                alarm_name = request.form.get(f"{relay_key}_name", "")
                limit_real_str = request.form.get(f"{relay_key}_limit", "")
                alarm_type = request.form.get(f"{relay_key}_type", "high")

                limit_real = 0.0
                limit_bits = 0

                if source and limit_real_str and source in sensor_config:
                    limit_real = float(limit_real_str)
                    s_min = sensor_config[source]["min"]
                    s_max = sensor_config[source]["max"]

                    if (s_max - s_min) != 0:
                        ratio = (limit_real - s_min) / (s_max - s_min)
                        limit_bits = int(max(0, min(4095, ratio * 4095)))

                updated_alarms[relay_key] = {
                    "source": source,
                    "alarm_name": alarm_name,
                    "type": alarm_type,
                    "limit_real": limit_real,
                    "limit_bits": limit_bits
                }

                logger.debug(
                    "Alarme %s configurado: source=%s type=%s limit=%.2f",
                    relay_key, source, alarm_type, limit_real
                )

            save_json(CONFIG_ALARMES_FILE, updated_alarms)
            logger.info("Configuração de alarmes salva com sucesso")

            flash("Relés salvos!", "alert-success")

        except Exception as e:
            logger.exception("Erro ao salvar alarmes")
            flash("Erro ao salvar alarmes.", "alert-danger")

        return redirect(url_for("routes_alarms.alarmes"))

    # -------- GET --------
    try:
        current_alarms = load_json(CONFIG_ALARMES_FILE)
        if not current_alarms:
            current_alarms = {
                f"relay_{i}": {
                    "source": "",
                    "limit_real": 0,
                    "type": "high"
                }
                for i in range(1, 10)
            }

        logger.debug("Alarmes carregados com sucesso")

    except Exception:
        logger.exception("Erro ao carregar alarmes")
        current_alarms = {}

    try:
        with open(STATUS_FILE, "r") as f:
            alarm_status = json.load(f)
        logger.debug("Status dos alarmes carregado")

    except Exception:
        logger.warning("Arquivo de status dos alarmes não encontrado")
        alarm_status = {f"relay_{i}": False for i in range(1, 10)}

    return render_template(
        "alarms.html",
        sensor_config=sensor_config,
        current_alarms=current_alarms,
        alarm_status=alarm_status
    )


@routes_alarms_bp.route("/api/alarm_status")
def api_alarm_status():
    try:
        with open(STATUS_FILE, "r") as f:
            data = json.load(f)

        return jsonify(data)

    except Exception:
        logger.warning("Falha ao ler alarmes_status.json")
        return jsonify({})
