import serial
import time

PORT = '/dev/serial0'
BAUD = 9600
SLAVE_ID = 1
TIMEOUT = 2

def open_serial():
    ser = serial.Serial(PORT, BAUD, timeout=TIMEOUT)
    time.sleep(1)
    print(f"[READ] Porta {PORT} aberta")
    return ser

def send_at_local(ser, cmd):
    ser.reset_input_buffer()
    ser.write((cmd + "\r\n").encode())
    time.sleep(0.2)
    resp = ser.read(200).decode(errors="ignore").strip()
    print(f"[LOCAL] {cmd} -> {resp}")
    return resp

def send_at_remote(ser, cmd):
    full = f"AT+REMOTE={SLAVE_ID},{cmd}"
    ser.reset_input_buffer()
    ser.write((full + "\r\n").encode())
    time.sleep(0.7)
    resp = ser.read(200).decode(errors="ignore").strip()
    print(f"[SLAVE] {full} -> {resp}")
    return resp

def main():
    ser = open_serial()

    print("\n=== LENDO CONFIGURAÇÕES DO MASTER ===")
    send_at_local(ser, "AT+BW?")
    send_at_local(ser, "AT+SF?")
    send_at_local(ser, "AT+CR?")
    send_at_local(ser, "AT+CLASS?")

    print("\n=== LENDO CONFIGURAÇÕES DO SLAVE ===")
    send_at_remote(ser, "AT+BW?")
    send_at_remote(ser, "AT+SF?")
    send_at_remote(ser, "AT+CR?")
    send_at_remote(ser, "AT+CLASS?")
    send_at_remote(ser, "AT+RXWN?")

    print("\n[FINAL] Leitura concluída!")

    ser.close()

if __name__ == "__main__":
    main()
