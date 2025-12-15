import os
from flask import Blueprint, render_template, jsonify
from web_server.decorators import login_required
from web_server.services.json_store import load_json_safe
from threading import Lock

view_bp = Blueprint('view', __name__)

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SENSOR_FILE = os.path.join(BASE, 'read', 'dados_endpoint.json')
COMM_FILE = os.path.join(BASE, 'LoraMesh', 'communication_time.json')

lock = Lock()

@view_bp.route('/visualizacao')
@login_required
def visualizacao():
    sensor_config = load_json_safe(os.path.join(BASE, 'configs', 'config_min_max.json'))
    return render_template('data_visualization.html', sensor_config=sensor_config)

@view_bp.route('/api/sensor_data')
def api_sensor_data():
    with lock:
        data = load_json_safe(SENSOR_FILE)
        comm = load_json_safe(COMM_FILE)
        if 'elapsed_sec' in comm:
            data['comm_time'] = comm['elapsed_sec']
        return jsonify(data)
