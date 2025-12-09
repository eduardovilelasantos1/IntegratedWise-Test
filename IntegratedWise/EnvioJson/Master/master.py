import serial
import time
from datetime import datetime

# --- Configurações ---
PORT = '/dev/serial0'
BAUD = 9600
SLAVE_ID = 1         # O ID do escravo que queremos contatar
CMD_ADC = 0xB0       # Comando customizado para "Ler ADC"
INTERVAL_SECONDS = 5 # Intervalo entre medições
FRAME_SIZE = 7       # Tamanho esperado da RESPOSTA (ID(2) + CMD(1) + PAYLOAD(2) + CRC(2))
READ_TIMEOUT = 2     # Segundos para esperar pela resposta

def compute_crc(data: bytes) -> int:
    """
    Calcula o CRC-16 (Radioenge)
    Polinômio: 0xA001, Valor Inicial: 0xC181
    """
    crc = 0xC181
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc >> 1) ^ 0xA001) if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF

def make_cmd_frame(dest_id: int, cmd: int) -> bytes:
    """
    Cria o pacote de COMANDO (5 bytes)
    Formato: [ID_LSB, ID_MSB, CMD, CRC_LSB, CRC_MSB]
    """
    # O CRC é calculado sobre ID (2 bytes) + CMD (1 byte)
    frame = dest_id.to_bytes(2, 'little') + bytes([cmd])
    crc = compute_crc(frame)
    return frame + crc.to_bytes(2, 'little')

def parse_adc_frame(frame: bytes):
    """
    Valida e extrai dados do pacote de RESPOSTA (7 bytes)
    Formato: [ID_LSB, ID_MSB, CMD, PL_LSB, PL_MSB, CRC_LSB, CRC_MSB]
    """
    if len(frame) != FRAME_SIZE:
        raise ValueError(f"Tamanho inválido: {len(frame)} bytes (esperado {FRAME_SIZE})")
    
    # Valida o CRC (calculado sobre ID + CMD + PAYLOAD)
    crc_rx = int.from_bytes(frame[5:7], 'little')
    crc_calc = compute_crc(frame[:5])
    
    if crc_rx != crc_calc:
        raise ValueError(f"CRC inválido: RX {crc_rx:04X} != Calc {crc_calc:04X}")
    
    # Extrai os dados
    src = int.from_bytes(frame[0:2], 'little')
    cmd = frame[2]
    valor = int.from_bytes(frame[3:5], 'little')
    return src, cmd, valor

def abrir_serial():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=READ_TIMEOUT)
        time.sleep(2)  # Aguarda estabilização
        print(f"[RPI] Porta {PORT} aberta a {BAUD} bps")
        return ser
    except serial.SerialException as e:
        print(f"[ERRO] Não foi possível abrir a porta serial: {e}")
        exit(1)

def main():
    ser = abrir_serial()
    print(f"[RPI] Iniciando Modo de Comando (Mestre-Escravo)")
    print(f"[RPI] Solicitando dados do Escravo ID {SLAVE_ID} a cada {INTERVAL_SECONDS} segundos\n")

    try:
        while True:
            start_time = time.time()
            ser.reset_input_buffer() # Limpa lixo antigo

            # 1. Monta e Envia o Comando
            frame = make_cmd_frame(SLAVE_ID, CMD_ADC)
            ser.write(frame)

            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] TX -> Enviando {CMD_ADC:02X} para ID {SLAVE_ID} ({frame.hex().upper()})")

            # 2. Espera e Lê a Resposta
            resp = ser.read(FRAME_SIZE)

            # 3. Processa a Resposta
            if len(resp) < FRAME_SIZE:
                print(f"[RPI] FALHA: Timeout ou resposta incompleta (Recebido: {resp.hex().upper() if resp else 'vazio'})\n")
            else:
                try:
                    src, cmd, val = parse_adc_frame(resp)
                    volts = (val / 4095.0) * 3.3 # Assumindo ADC de 12 bits e VRef 3.3V
                    timestamp_rx = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp_rx}] RX <- Resposta de ID {src} ({resp.hex().upper()})")
                    print(f"[RPI] SUCESSO: Leitura: {val:4d} -> {volts:.2f} V\n")
                
                except ValueError as e:
                    print(f"[RPI] FALHA: Erro ao processar resposta: {e}")
                    print(f"    (Recebido: {resp.hex().upper()})\n")

            # 4. Aguarda o próximo ciclo
            elapsed = time.time() - start_time
            time.sleep(max(0, INTERVAL_SECONDS - elapsed))

    except KeyboardInterrupt:
        print("\n[RPI] Encerrado pelo usuário.")
    finally:
        ser.close()

# Corrigido: __name__ (com dois underscores)
if __name__ == "__main__":
    main()