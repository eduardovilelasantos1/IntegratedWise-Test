from config_loader import calcular_crc

def parse_adc_frame(frame: bytes):
    if len(frame) != 23:
        raise ValueError("Tamanho inválido")

    crc_calc = calcular_crc(frame[:-2])
    crc_recv = int.from_bytes(frame[-2:], "little")

    if crc_calc != crc_recv:
        raise ValueError("CRC inválido")

    src = int.from_bytes(frame[0:2], "little")
    valores = []
    offset = 3

    for _ in range(6):
        valores.append(int.from_bytes(frame[offset:offset+2], "little"))
        offset += 2

    bus_raw = int.from_bytes(frame[offset:offset+2], "little"); offset += 2
    shunt_raw = int.from_bytes(frame[offset:offset+2], "little", signed=True); offset += 2
    sleep_sec = int.from_bytes(frame[offset:offset+2], "little")

    return src, valores, bus_raw, shunt_raw, sleep_sec
