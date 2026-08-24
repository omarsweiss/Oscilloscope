import serial
print('test', flush=True)
ser = serial.Serial('COM3', 115200, timeout=1)

while True:
    if ser.in_waiting > 0:
        line = ser.readline().decode('utf-8').strip()
        print(line, flush=True)

