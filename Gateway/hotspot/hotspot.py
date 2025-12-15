import subprocess
import time
import RPi.GPIO as GPIO
import os
import sys  # <-- IMPORTANTE: Precisamos disso

print("Iniciando script do hotspot...")

# Configuração
HOTSPOT_NAME = "PiHotspot"
WIFI_INTERFACE = "wlan0"
HOTSPOT_TIMEOUT = 3
BOTAO_GPIO = 10

# --- Controle do LED Interno (ACT/led0) ---
LED_TRIGGER_PATH = "/sys/class/leds/ACT/trigger"
LED_BRIGHTNESS_PATH = "/sys/class/leds/ACT/brightness"
original_trigger = "mmc0" # Padrão do Pi

# Estados
hotspot_ativo = False
wifi_anterior = None
webserver_process = None  # <-- ADICIONADO: Para rastrear o webserver

def setup_led():
    """Toma controle do LED de atividade (ACT) do Pi."""
    global original_trigger
    try:
        with open(LED_TRIGGER_PATH, 'r') as f:
            original_trigger = f.read().strip()
        with open(LED_TRIGGER_PATH, 'w') as f:
            f.write("none")
        with open(LED_BRIGHTNESS_PATH, 'w') as f:
            f.write("0")
    except Exception as e:
        print(f"Erro ao configurar o LED: {e}. (Rodando como root?)")

def set_led(ligado):
    """Acende (1) ou apaga (0) o LED."""
    try:
        with open(LED_BRIGHTNESS_PATH, 'w') as f:
            f.write("1" if ligado else "0")
    except Exception as e:
        print(f"Erro ao alterar o brilho do LED: {e}")

def restore_led():
    """Devolve o controle do LED ao sistema."""
    try:
        with open(LED_TRIGGER_PATH, 'w') as f:
            f.write(original_trigger)
    except Exception as e:
        print(f"Erro ao restaurar o gatilho do LED: {e}")
# -----------------------------------------------

# --- Lógica do Botão (Pull-Up) ---
GPIO.setmode(GPIO.BCM)
GPIO.setup(BOTAO_GPIO, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def get_current_wifi():
    """Verifica qual rede Wi-Fi está ativa no momento."""
    result = subprocess.run(['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active'],
                            capture_output=True, text=True)
    for line in result.stdout.splitlines():
        try:
            name, ctype, device = line.split(":")
            if ctype == '802-11-wireless' and device == WIFI_INTERFACE:
                return name
        except ValueError:
            continue
    return None

# --- FUNÇÕES DO WEBSERVER (READICIONADAS) ---
def iniciar_servidor_web():
    """Inicia o webserver.py como um processo separado."""
    global webserver_process
    if webserver_process: # Se já estiver rodando, não faz nada
        return
        
    print("Iniciando servidor web via webserver.py...")
    # O caminho para o webserver
    webserver_path = '/home/suporte/IntegratedWise/web_server/webserver.py'
    
    # sys.executable é o caminho para o Python do VENV (ex: /home/suporte/.../venv/bin/python3)
    # Isso garante que o webserver rode no mesmo venv!
    webserver_process = subprocess.Popen([sys.executable, webserver_path])
    
def parar_servidor_web():
    """Para o processo do webserver se ele estiver rodando."""
    global webserver_process
    if webserver_process and webserver_process.poll() is None:
        print("Parando servidor web...")
        webserver_process.terminate()
        webserver_process.wait()
        webserver_process = None
# ----------------------------------------------------

def activate_hotspot():
    """Ativa o perfil de hotspot e acende o LED."""
    global hotspot_ativo
    print(f"Ativando hotspot '{HOTSPOT_NAME}'...")
    subprocess.run(['nmcli', 'connection', 'up', HOTSPOT_NAME])
    hotspot_ativo = True
    set_led(True) # Acende o LED
    iniciar_servidor_web() # <-- ADICIONADO: Liga o webserver
    print("Hotspot ATIVADO.")

def deactivate_hotspot():
    """Desativa o perfil de hotspot e apaga o LED."""
    global hotspot_ativo
    parar_servidor_web() # <-- ADICIONADO: Desliga o webserver
    print(f"Desativando hotspot '{HOTSPOT_NAME}'...")
    subprocess.run(['nmcli', 'connection', 'down', HOTSPOT_NAME])
    hotspot_ativo = False
    set_led(False) # Apaga o LED
    print("Hotspot DESATIVADO.")

def connect_wifi(ssid):
    """Tenta se reconectar a uma rede Wi-Fi anterior."""
    if not ssid:
        print("Nenhuma rede anterior para reconectar.")
        return
    print(f"Reconectando à rede Wi-Fi '{ssid}'...")
    subprocess.run(['nmcli', 'connection', 'up', ssid])

def monitorar_botao():
    """Loop principal que monitora o botão por uma pressão longa."""
    global wifi_anterior, hotspot_ativo
    
    setup_led() # Toma controle do LED
    print(f"Monitorando o botão GPIO {BOTAO_GPIO}... (pressione por {HOTSPOT_TIMEOUT}s para alternar)")
    
    try:
        while True:
            if GPIO.input(BOTAO_GPIO) == GPIO.LOW: # Botão pressionado
                start_time = time.time()
                while GPIO.input(BOTAO_GPIO) == GPIO.LOW:
                    time.sleep(0.1)
                    if time.time() - start_time >= HOTSPOT_TIMEOUT:
                        print("Pressão longa detectada. Alternando o estado do hotspot.")
                        
                        if not hotspot_ativo:
                            wifi_anterior = get_current_wifi()
                            print(f"Rede Wi-Fi anterior salva: {wifi_anterior}")
                            activate_hotspot() # (Agora também inicia o webserver)
                        else:
                            deactivate_hotspot() # (Agora também para o webserver)
                            if wifi_anterior:
                                connect_wifi(wifi_anterior)
                        
                        print("Aguardando soltar o botão...")
                        while GPIO.input(BOTAO_GPIO) == GPIO.LOW:
                            time.sleep(0.1)
                        print("Botão solto.")
                        break 
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nEncerrando programa (Ctrl+C).")
    finally:
        print("Limpando na saída...")
        parar_servidor_web() # <-- ADICIONADO: Garante que o webserver pare
        if hotspot_ativo:
            deactivate_hotspot()
            if wifi_anterior:
                connect_wifi(wifi_anterior)
        restore_led() # Devolve o LED ao sistema
        GPIO.cleanup()
        print("GPIO limpo. Script encerrado.")

if __name__ == "__main__":
    monitorar_botao()