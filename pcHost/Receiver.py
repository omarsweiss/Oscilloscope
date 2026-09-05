from PyQt6.QtWidgets import *
import pyqtgraph as pg
import sys
import serial
import struct

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("title")
        button = QPushButton("button")
        
        self.setFixedSize(400,400)
        self.plot_graph = pg.PlotWidget()
        self.setCentralWidget(self.plot_graph)
        minutes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        temperature = [30, 32, 34, 32, 33, 31, 29, 32, 35, 30]
        self.plot_graph.plot(minutes,temperature)
ser = serial.Serial('/dev/ttyACM0',timeout=1)
i=0
readings = [0]*200
while True:
    while i!=200:
        readings[i] = ser.readline(2)
        i=i+1
    i=0
    
    unpacked_list = [struct.unpack('<H', chunk)[0] for chunk in readings] 
    print(unpacked_list)
app = QApplication(sys.argv) #argv could be which serial port
window = MainWindow()
window.show()
app.exec()
