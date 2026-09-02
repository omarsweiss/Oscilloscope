from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg
import sys
import serial
ser = serial.Serial('/dev/ttyACM1',timeout=1)
while True:
   data = ser.readline(400)
   print(data)

