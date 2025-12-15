# LEDs
LED1 = 21
LED2 = 20
LED3 = 16
LED4 = 12
LED5 = 7
LED6 = 26
LED7 = 19
LED8 = 13
LED9 = 6

LEDS = [LED1, LED2, LED3, LED4, LED5, LED6, LED7, LED8, LED9]

# Botões
BTN1 = 10
BTN2 = 11

I2C_BUS = 1

MCP4728_DEVICES = [
    {"address": 0x60, "busy_pin": 17},   # DAC1
]

VREF = 5.0  # tensão de referência do DAC mudar depois para 3.3V