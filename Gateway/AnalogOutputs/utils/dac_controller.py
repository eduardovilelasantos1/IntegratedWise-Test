import time
from smbus2 import i2c_msg
import RPi.GPIO as GPIO

# Importa VREF do config
try:
    from utils.config import VREF
except ImportError:
    VREF = 5.0

# Tenta importar logger
try:
    from utils.logger import log
except ImportError:
    log = print

class MCP4728:
    def __init__(self, address, busy_pin, bus):
        self.address = address
        self.busy_pin = busy_pin
        self.bus = bus

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.busy_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            log(f"Aviso GPIO: {e}")

    def _wait_ready(self, timeout_s=0.1):
        """Espera a EEPROM terminar de escrever (apenas se necessário)."""
        start = time.time()
        while GPIO.input(self.busy_pin) == GPIO.LOW:
            if time.time() - start > timeout_s:
                log("Aviso: Timeout esperando DAC (BSY).")
                return
            time.sleep(0.001)

    def set_voltage_and_config(self, channel, voltage, use_eeprom=False, vref_mode=0, pd_mode=0):
        """
        Converte tensão para bits e envia para o DAC.
        """
        if channel < 0 or channel > 3:
            return

        # 1. Conversão Tensão -> Bits
        voltage_clamped = max(0.0, min(voltage, VREF))
        value = int((voltage_clamped / VREF) * 4095)

        # 2. Configuração dos Bits de Dados
        # MSB: [VREF(1)][PD1(1)][PD0(1)][Gain(1)] [D11][D10][D9][D8]
        # LSB: [D7]...[D0]
        
        # Gain=0 (x1) para VREF=5V
        vref_bit = (vref_mode & 1) << 7
        pd_bits = (pd_mode & 3) << 5
        gain_bit = 0 
        
        upper_nibble = (value >> 8) & 0x0F
        msb = vref_bit | pd_bits | gain_bit | upper_nibble
        lsb = value & 0xFF

        # 3. Seleção do Comando (A CORREÇÃO CRÍTICA)
        if use_eeprom:
            # 0x58: Single Write (Input Register + EEPROM)
            # Este comando é LENTO (~50ms) e bloqueia o chip.
            cmd_byte = 0x58 | (channel << 1)
        else:
            # 0x40: Multi-Write (Input Register Only - Volatile)
            # Este comando é RÁPIDO e não bloqueia.
            # (Bits: 0 1 0 0 0 [DAC1] [DAC0] [UDAC])
            cmd_byte = 0x40 | (channel << 1)

        # 4. Envio I2C
        msg = i2c_msg.write(self.address, [cmd_byte, msb, lsb])
        
        try:
            self.bus.i2c_rdwr(msg)
            
            if use_eeprom:
                # Se escrever na EEPROM, TEMOS de esperar o chip liberar
                self._wait_ready()
                
            # Log opcional para debug
            # log(f"DAC Ch{channel}: {voltage:.2f}V (Val: {value}) CMD: {cmd_byte:x}")

        except Exception as e:
            log(f"ERRO I2C no DAC: {e}")