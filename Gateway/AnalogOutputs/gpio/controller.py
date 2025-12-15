import RPi.GPIO as GPIO
from utils.logger import log

class GPIOController:
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        self.pins = {}

    # Configura saída
    def setup_output(self, pin):
        GPIO.setup(pin, GPIO.OUT)
        self.pins[pin] = 'OUT'

    # Liga saída
    def turn_on(self, pin):
        if self.pins.get(pin) == 'OUT':
            GPIO.output(pin, GPIO.HIGH)

    # Desliga saída
    def turn_off(self, pin):
        if self.pins.get(pin) == 'OUT':
            GPIO.output(pin, GPIO.LOW)

    # Configura entrada com pull-up/pull-down opcional
    def setup_input(self, pin, pull_up_down=None):
        if pull_up_down is not None:
            GPIO.setup(pin, GPIO.IN, pull_up_down=pull_up_down)
        else:
            GPIO.setup(pin, GPIO.IN)
        self.pins[pin] = 'IN'

    # Lê estado de entrada e retorna True se “acionado”
    def is_pressed(self, pin, active_state=GPIO.LOW):
        """
        Retorna True se o pino estiver no estado considerado 'acionado'.
        active_state: GPIO.LOW (botão ligado ao GND) ou GPIO.HIGH
        """
        if self.pins.get(pin) != 'IN':
            log(f"GPIO {pin} não configurado como entrada")
        return GPIO.input(pin) == active_state

    # Libera os pinos
    def cleanup(self):
        GPIO.cleanup()
