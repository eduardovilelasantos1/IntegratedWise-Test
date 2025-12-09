import sys
import os
import json
import bcrypt
from threading import Lock
from flask import Flask, render_template, url_for, request, flash, redirect, session, jsonify

# Ajusta o path para imports absolutos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs'))

from web_server.forms import FormLogin, FormAlterarSenha
from web_server.defaults import (
    DEFAULT_LORA_CONFIG,
    DEFAULT_MODBUS_CONFIG,
    DEFAULT_OPCUA_CONFIG,
    DEFAULT_ALARMES_CONFIG,
    DEFAULT_4_20MA_CONFIG
)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
SENSOR_DATA_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'read', 'dados_endpoint.json'))
sensor_data_lock = Lock()

def load_users():
    if not os.path.exists(USERS_FILE):
        hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode('utf-8')
        default_users = {"admin": {"password": hashed}}
        save_users(default_users)
    with open(USERS_FILE, 'r') as f: return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f: json.dump(users, f, indent=4)

def load_json(file):
    try:
        with open(os.path.join(CONFIG_DIR, file), 'r') as f: return json.load(f)
    except FileNotFoundError: return {}

def save_json(file, data):
    try:
        with open(os.path.join(CONFIG_DIR, file), 'w') as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Erro ao salvar {file}: {e}")

def real_to_bits(valor_real, min_real, max_real):
    try:
        valor_real = float(valor_real)
        min_real = float(min_real)
        max_real = float(max_real)
        if (max_real - min_real) == 0: return 0
        ratio = (valor_real - min_real) / (max_real - min_real)
        bits = int(ratio * 4095)
        return max(0, min(4095, bits))
    except: return 0

@app.route('/')
def home(): return render_template('homepage.html')

@app.route('/configuracao', methods=['GET'])
def configuracao():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    modbus = load_json('config_modbus.json')
    opcua = load_json('config_opcua.json')
    lora = load_json('config_lora.json')
    battery = load_json('config_battery.json')

    return render_template('settings.html',
                           modbus_host=modbus.get("MODBUS_HOST", ""),
                           modbus_port=modbus.get("MODBUS_PORT", 502),
                           unit_id=modbus.get("UNIT_ID", 1),
                           server_identity=modbus.get("SERVER_IDENTITY", {}),
                           opcua_server_name=opcua.get("SERVER_NAME", ""),
                           opcua_server_url=opcua.get("SERVER_URL", ""),
                           opcua_main_node=opcua.get("MAIN_NODE_NAME", ""),
                           opcua_users=opcua.get("AUTHORIZED_USERS", {}),
                           lora_config=lora,
                           battery_config=battery)

@app.route('/salvar_configuracao', methods=['POST'])
def salvar_configuracao():
    if not session.get('logged_in'): return redirect(url_for('login'))
    try:
        # 1. LoRa
        current_lora = load_json('config_lora.json')
        if not current_lora: current_lora = {}
        
        lora_config = {
            "classe": request.form.get('lora_classe', current_lora.get('classe', 'C')),
            "janela": request.form.get('lora_janela', current_lora.get('janela', '15s')),
            "bandwidth": request.form.get('lora_bandwidth', current_lora.get('bandwidth', '125kHz')),
            "spreading_factor": int(request.form.get('lora_spreading_factor', current_lora.get('spreading_factor', 7))),
            "coding_rate": request.form.get('lora_coding_rate', current_lora.get('coding_rate', '4/5')),
            "wake_interval": int(request.form.get('lora_wake_interval', current_lora.get('wake_interval', 30))),
            "power": int(current_lora.get('power', 20))
        }
        save_json('config_lora.json', lora_config)

        # Flag Reconfiguração
        with open(os.path.join(CONFIG_DIR, 'reconfig.flag'), 'w') as f: pass 

        # 2. Bateria (VERSÃO LIMPA)
        capacity = int(request.form.get('battery_capacity', 54000))
        
        # Salva APENAS a capacidade, sem inventar voltagens
        bat_config = {"capacity_mah": capacity}
        save_json('config_battery.json', bat_config)
        
        # Atualiza Min/Max visualização se necessário (para gráficos)
        min_max = load_json('config_min_max.json')
        if "consumo_mah" in min_max:
            min_max["consumo_mah"]["max"] = float(capacity)
            save_json('config_min_max.json', min_max)

        # ... (continua para Modbus) ...
        
        # Atualiza Min/Max visualização se necessário
        min_max = load_json('config_min_max.json')
        if "consumo_mah" in min_max:
            min_max["consumo_mah"]["max"] = float(capacity)
            save_json('config_min_max.json', min_max)

        # 3. Modbus
        modbus_config = {
            "MODBUS_HOST": request.form.get('modbus_host', '0.0.0.0'),
            "MODBUS_PORT": int(request.form.get('modbus_port', 502)),
            "UNIT_ID": int(request.form.get('unit_id', 1)),
            "SERVER_IDENTITY": {
                "VendorName": request.form.get('vendor_name', ''),
                "ProductCode": request.form.get('product_code', ''),
                "VendorUrl": request.form.get('vendor_url', ''),
                "ProductName": request.form.get('product_name', ''),
                "ModelName": request.form.get('model_name', ''),
                "MajorMinorRevision": request.form.get('revision', '')
            }
        }
        save_json('config_modbus.json', modbus_config)

        # 4. OPC UA
        users_raw = request.form.get('opcua_users', '')
        users = {}
        if users_raw:
            for pair in users_raw.split(","):
                if ":" in pair:
                    user, pwd = pair.strip().split(":")
                    users[user.strip()] = pwd.strip()
        opcua_config = {
            "SERVER_NAME": request.form.get('opcua_server_name', 'LoRaServer'),
            "SERVER_URL": request.form.get('opcua_server_url', 'opc.tcp://0.0.0.0:4840'),
            "MAIN_NODE_NAME": request.form.get('opcua_main_node', 'Sensores'),
            "AUTHORIZED_USERS": users,
            "CERT_PATH": "server-cert.pem",
            "KEY_PATH": "server-key.pem"
        }
        save_json('config_opcua.json', opcua_config)
        flash('Configurações salvas!', 'alert-success')

    except Exception as e:
        flash(f'Erro ao salvar: {e}', 'alert-danger')

    return redirect(url_for('configuracao'))

@app.route('/reset_bateria', methods=['POST'])
def reset_bateria():
    if not session.get('logged_in'): return redirect(url_for('login'))
    try:
        with open(os.path.join(CONFIG_DIR, 'reset_battery.flag'), 'w') as f: pass
        flash('Reset de Bateria Solicitado!', 'alert-warning')
    except Exception as e:
        flash(f'Erro: {e}', 'alert-danger')
    return redirect(url_for('configuracao'))

# ... (início do código igual) ...

@app.route('/visualizacao')
def visualizacao():
    if not session.get('logged_in'): return redirect(url_for('login'))
    
    # 1. Carrega canais normais
    sensor_config = load_json('config_min_max.json')

    # 2. INJETA MANUALMENTE AS CHAVES DA BATERIA
    sensor_config['battery_voltage'] = {"label": "Tensão", "unit": "V"}
    
    # AQUI: Mudamos para mostrar a média efetiva
    sensor_config['battery_avg_current'] = {"label": "Corrente Média", "unit": "mA"}
    
    sensor_config['consumo_mah'] =     {"label": "Consumido", "unit": "mAh"}
    sensor_config['bat_percent'] =     {"label": "Nível Bateria", "unit": "%"}
    sensor_config['bat_days'] =        {"label": "Estimativa", "unit": "Dias"}
    
    return render_template('data_visualization.html', sensor_config=sensor_config)

# ... (resto do código igual) ...

@app.route('/api/sensor_data')
def get_sensor_data():
    try:
        with sensor_data_lock:
            if os.path.exists(SENSOR_DATA_FILE):
                with open(SENSOR_DATA_FILE, 'r') as f: return jsonify(json.load(f))
            else: return jsonify({})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/calibracao', methods=['GET'])
def calibracao():
    if not session.get('logged_in'): return redirect(url_for('login'))
    calibracao_config = load_json('config_4_20ma.json')
    sensor_config = load_json('config_min_max.json')
    return render_template('calibration.html', config=calibracao_config, sensor_config=sensor_config)

@app.route('/salvar_calibracao', methods=['POST'])
def salvar_calibracao():
    if not session.get('logged_in'): return redirect(url_for('login'))
    try:
        sensor_config = load_json('config_min_max.json')
        for key in sensor_config.keys():
            if f'sensor_{key}_label' in request.form:
                sensor_config[key]['label'] = request.form[f'sensor_{key}_label']
                sensor_config[key]['unit'] = request.form[f'sensor_{key}_unit']
                sensor_config[key]['min'] = float(request.form[f'sensor_{key}_min'])
                sensor_config[key]['max'] = float(request.form[f'sensor_{key}_max'])
        save_json('config_min_max.json', sensor_config)

        selected_channel = request.form.get("selected_channel")
        if selected_channel:
            config_420 = load_json('config_4_20ma.json')
            trim_zero = request.form.get(f"TRIM_ZERO_BIT_{selected_channel}")
            trim_span = request.form.get(f"TRIM_SPAN_BIT_{selected_channel}")
            if trim_zero and trim_span:
                config_420[selected_channel] = {"TRIM_ZERO_BIT": int(trim_zero), "TRIM_SPAN_BIT": int(trim_span)}
                save_json('config_4_20ma.json', config_420)
        flash('Salvo com sucesso!', 'alert-success')
    except Exception as e: flash(f'Erro: {e}', 'alert-danger')
    return redirect(url_for('calibracao'))

@app.route('/alarmes', methods=['GET', 'POST'])
def alarmes():
    if not session.get('logged_in'): return redirect(url_for('login'))
    alarm_file = 'config_alarmes.json'
    sensor_config = load_json('config_min_max.json')

    if request.method == 'POST':
        try:
            updated_alarms = {}
            for i in range(1, 10):
                relay_key = f"relay_{i}"
                source = request.form.get(f'{relay_key}_source', '')
                alarm_name = request.form.get(f'{relay_key}_name', '')
                limit_real_str = request.form.get(f'{relay_key}_limit', '')
                alarm_type = request.form.get(f'{relay_key}_type', 'high')
                limit_real = 0.0
                limit_bits = 0
                if source and limit_real_str and source in sensor_config:
                    limit_real = float(limit_real_str)
                    s_min = sensor_config[source]['min']
                    s_max = sensor_config[source]['max']
                    limit_bits = real_to_bits(limit_real, s_min, s_max)
                updated_alarms[relay_key] = {
                    "source": source, "alarm_name": alarm_name, "type": alarm_type,
                    "limit_real": limit_real, "limit_bits": limit_bits
                }
            save_json(alarm_file, updated_alarms)
            flash('Relés salvos!', 'alert-success')
        except Exception as e: flash(f'Erro: {e}', 'alert-danger')
        return redirect(url_for('alarmes'))

    current_alarms = load_json(alarm_file)
    if not current_alarms:
        current_alarms = {f"relay_{i}": {"source": "", "limit_real": 0, "type": "high"} for i in range(1, 10)}
    return render_template('alarms.html', sensor_config=sensor_config, current_alarms=current_alarms)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = FormLogin()
    form_pw = FormAlterarSenha()
    users = load_users()
    if form.validate_on_submit() and 'botao_submit_login' in request.form:
        if bcrypt.checkpw(form.password.data.encode('utf-8'), users['admin']['password'].encode('utf-8')):
            session['logged_in'] = True
            flash('Login ok!', 'alert-success')
            return redirect(url_for('configuracao'))
        else: flash('Senha incorreta.', 'alert-danger')
    if form_pw.validate_on_submit() and 'botao_submit_alterar_senha' in request.form:
        if not bcrypt.checkpw(form_pw.senha_atual.data.encode('utf-8'), users['admin']['password'].encode('utf-8')):
            flash('Senha atual errada.', 'alert-danger')
        elif form_pw.nova_senha.data != form_pw.confirmar_senha.data:
            flash('Senhas não conferem.', 'alert-danger')
        else:
            users['admin']['password'] = bcrypt.hashpw(form_pw.nova_senha.data.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            save_users(users)
            flash('Senha alterada!', 'alert-success')
            return redirect(url_for('login'))
    return render_template('login.html', form_login=form, form_alterar_senha=form_pw)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/reset', methods=['GET', 'POST'])
def reset():
    if not session.get('logged_in'): return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            save_json('config_lora.json', DEFAULT_LORA_CONFIG)
            save_json('config_modbus.json', DEFAULT_MODBUS_CONFIG)
            save_json('config_opcua.json', DEFAULT_OPCUA_CONFIG)
            save_json('config_alarmes.json', DEFAULT_ALARMES_CONFIG)
            save_json('config_4_20ma.json', DEFAULT_4_20MA_CONFIG)
            flash('Reset OK!', 'alert-success')
        except Exception as e: flash(f'Erro: {e}', 'alert-danger')
        return redirect(url_for('configuracao'))
    return render_template('reset.html')

if __name__ == '__main__':
    users = load_users()
    if users.get('admin', {}).get('password') == 'admin':
        hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt())
        users['admin']['password'] = hashed.decode('utf-8')
        save_users(users)
    app.run(host='0.0.0.0', port=5001, debug=True)