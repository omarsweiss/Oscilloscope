#!/usr/bin/env python3


import os
import struct
import sys
import time
import threading
import queue

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")
# VS Code's snap terminal puts its own outdated GSettings schemas first on
# XDG_DATA_DIRS, which makes Qt's GTK theme abort on GNOME 50. Use the system ones.
os.environ.setdefault("GSETTINGS_SCHEMA_DIR", "/usr/share/glib-2.0/schemas")

import numpy as np
import serial
import serial.tools.list_ports
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg


ADC_BUF_LEN = 16000               # must match ADC_BUF_LEN in myapp.c (DMA words)
SAMPLES_PER_FRAME = 2 * ADC_BUF_LEN   # uint16 count of adcBuf[]
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2

ADC_CLK_HZ = 48_000_000
PAIR_CYCLES = 19                 # t_sample(6.5) + t_convert(12.5)
DELAY_CYCLES = 9                 # TwoSamplingDelay: ADC2 offset from ADC1

VREF = 3.3
ADC_FULL_SCALE = 4095            # 12-bit

STM32_VID, STM32_CDC_PID = 0x0483, 0x5740

# Commands to the board: must match Cmd in myapp.h (packed, 7 bytes).
CMD = struct.Struct("<BIH")      # id, freq_hz, dutyx100
CMD_PWM, CMD_DAC = 1, 2
TIMER_CLK_HZ = 48_000_000        # TIM1 / TIM6 clock
DAC_TABLE_LEN = 64               # points in sinewave[]
PWM_MAX_HZ = 24_000_000          # limits enforced by pwm_set / dac_set
DAC_MAX_HZ = 15_000


def timer_actual_hz(hz: int) -> float:
    """Frequency the timer really produces for a request, using the firmware's PSC/ARR maths."""
    ticks = TIMER_CLK_HZ // hz
    psc = ticks // 65536
    arr = ticks // (psc + 1) - 1
    return TIMER_CLK_HZ / ((psc + 1) * (arr + 1))


def build_time_axis(n: int) -> np.ndarray:
    """True sample timestamps in microseconds, accounting for non-uniform interleave."""
    idx = np.arange(n)
    pair = idx // 2                                  # which conversion pair
    offset = np.where(idx % 2, DELAY_CYCLES, 0)      # ADC2 lags ADC1 by DELAY_CYCLES
    cycles = pair * PAIR_CYCLES + offset
    return cycles / ADC_CLK_HZ * 1e6



def find_port() -> str:
    """Pick the STM32 CDC port, skipping the ST-LINK VCP."""
    for p in serial.tools.list_ports.comports():
        if p.vid == STM32_VID and p.pid == STM32_CDC_PID:
            return p.device
    candidates = [p.device for p in serial.tools.list_ports.comports()]
    raise SystemExit(
        f"No STM32 CDC device ({STM32_VID:04x}:{STM32_CDC_PID:04x}) found.\n"
        f"Ports seen: {candidates or 'none'}\n"
        f"Note /dev/ttyACM0 is usually the ST-LINK VCP, not the target."
    )


class Reader(threading.Thread):
    """Reads fixed-size frames off the CDC port into a queue."""

    daemon = True

    def __init__(self, port: str, out: queue.Queue):
        super().__init__()
        self.out = out
        self.stop_flag = threading.Event()
        # xonxoff MUST stay off: 0x11/0x13 occur constantly in binary ADC data
        # and the tty layer would silently eat them as flow control.
        self.ser = serial.Serial(
            port, baudrate=115200, timeout=1.0,
            xonxoff=False, rtscts=False, dsrdtr=False,
        )
        self.ser.reset_input_buffer()

    def run(self):
        while not self.stop_flag.is_set():
            try:
                buf = self.ser.read(BYTES_PER_FRAME)
            except (serial.SerialException, OSError, TypeError) as exc:
                # TypeError/OSError happen when the port is closed from the GUI
                # thread while this read is still blocked on it.
                if not self.stop_flag.is_set():
                    print(f"serial error: {exc}", file=sys.stderr)
                return
            if len(buf) != BYTES_PER_FRAME:
                continue  # timeout or short read; drop the partial frame
            frame = np.frombuffer(buf, dtype="<u2").astype(np.float32)
            if self.out.full():
                try:
                    self.out.get_nowait()   # drop oldest, keep the display current
                except queue.Empty:
                    pass
            self.out.put(frame)

    def close(self):
        self.stop_flag.set()
        try:
            self.ser.close()
        except Exception:
            pass


class Scope(QtWidgets.QMainWindow):
    def __init__(self, port: str):
        super().__init__()
        self.setWindowTitle(f"STM32G474 Scope — {port}")
        self.resize(1050, 600)

        self.frames = queue.Queue(maxsize=4)
        self.reader = Reader(port, self.frames)
        self.reader.start()

        self.t = build_time_axis(SAMPLES_PER_FRAME)
        self.paused = False
        self.frame_count = 0
        self.t0 = time.monotonic()

        # Antialiasing makes a 4096-point square wave take ~350 ms to draw.
        pg.setConfigOptions(antialias=False)

        # One frame, on the true (non-uniform) microsecond axis
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", "Time", units="µs")
        self.plot.setLabel("left", "Voltage", units="V")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setYRange(0, VREF)
        self.plot.setXRange(self.t[0], self.t[-1])
        # Mouse wheel / drag act on time only; voltage stays fixed at 0..VREF.
        # Limits stop you from panning off the ends of the frame.
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.setLimits(xMin=self.t[0], xMax=self.t[-1], minXRange=1.0,
                            yMin=-0.1, yMax=VREF + 0.1)
        # clipToView only draws the visible points, so zooming in is cheap.
        self.curve = self.plot.plot(pen=pg.mkPen("#4ea1ff", width=1), clipToView=True)
        # Zoomed out, 32k points are more than the screen has pixels. Peak downsampling
        # keeps each pixel column's min and max, so square-wave edges stay sharp.
        self.curve.setDownsampling(auto=True, method="peak")
        self.plot.sigXRangeChanged.connect(self.on_zoom)

        self.readout = QtWidgets.QLabel("waiting for data…")
        self.readout.setStyleSheet("font-family: monospace; padding: 4px;")

        # Preset time windows, like a scope's time/div knob.
        self.window_box = QtWidgets.QComboBox()
        self.window_box.addItem("Full frame", None)
        for us in (5000, 2000, 1000, 500, 200, 100, 50, 20, 10, 5, 2):
            self.window_box.addItem(f"{us} µs", us)
        self.window_box.activated.connect(self.on_window)

        self.reset_btn = QtWidgets.QPushButton("Reset zoom")
        self.reset_btn.clicked.connect(lambda: self.set_window(None))

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self.on_pause)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Window:"))
        controls.addWidget(self.window_box)
        controls.addWidget(self.reset_btn)
        controls.addStretch(1)
        controls.addWidget(self.pause_btn)

        # Signal generator: PWM on PC0, DAC sine on PA4.
        self.pwm_freq = QtWidgets.QSpinBox()
        self.pwm_freq.setRange(1, PWM_MAX_HZ)
        self.pwm_freq.setValue(100_000)
        self.pwm_freq.setSuffix(" Hz")
        self.pwm_freq.setGroupSeparatorShown(True)
        self.pwm_duty = QtWidgets.QDoubleSpinBox()
        self.pwm_duty.setRange(0, 100)
        self.pwm_duty.setDecimals(2)
        self.pwm_duty.setValue(50)
        self.pwm_duty.setSuffix(" %")
        pwm_btn = QtWidgets.QPushButton("Set PWM")
        pwm_btn.clicked.connect(self.send_pwm)

        self.dac_freq = QtWidgets.QSpinBox()
        self.dac_freq.setRange(1, DAC_MAX_HZ)
        self.dac_freq.setValue(10_000)
        self.dac_freq.setSuffix(" Hz")
        self.dac_freq.setGroupSeparatorShown(True)
        dac_btn = QtWidgets.QPushButton("Set DAC")
        dac_btn.clicked.connect(self.send_dac)

        self.gen_status = QtWidgets.QLabel("")
        self.gen_status.setStyleSheet("font-family: monospace;")

        generator = QtWidgets.QHBoxLayout()
        for w in (QtWidgets.QLabel("PWM (PC0):"), self.pwm_freq, self.pwm_duty, pwm_btn,
                  QtWidgets.QLabel("   DAC sine (PA4):"), self.dac_freq, dac_btn):
            generator.addWidget(w)
        generator.addWidget(self.gen_status, 1)

        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.addWidget(self.plot)
        layout.addLayout(controls)
        layout.addLayout(generator)
        layout.addWidget(self.readout)
        self.setCentralWidget(root)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30)   # ~33 Hz redraw; the link, not the GUI, is the limit

    def on_pause(self, checked: bool):
        self.paused = checked
        self.pause_btn.setText("Resume" if checked else "Pause")

    # ------------------------------------------------------------ generator
    def send_cmd(self, cmd_id: int, freq_hz: int, duty_x100: int = 0) -> bool:
        try:
            self.reader.ser.write(CMD.pack(cmd_id, freq_hz, duty_x100))
            return True
        except (serial.SerialException, OSError) as exc:
            self.gen_status.setText(f"send failed: {exc}")
            return False

    def send_pwm(self):
        hz = self.pwm_freq.value()
        duty_x100 = round(self.pwm_duty.value() * 100)
        if self.send_cmd(CMD_PWM, hz, duty_x100):
            self.gen_status.setText(f"PWM sent: actual {timer_actual_hz(hz):,.1f} Hz")

    def send_dac(self):
        hz = self.dac_freq.value()
        if self.send_cmd(CMD_DAC, hz):
            # TIM6 steps through the table, so the sine is the tick rate / table length.
            actual = timer_actual_hz(hz * DAC_TABLE_LEN) / DAC_TABLE_LEN
            self.gen_status.setText(f"DAC sent: actual {actual:,.1f} Hz")

    def on_window(self, index: int):
        self.set_window(self.window_box.itemData(index))

    def set_window(self, width_us):
        """Show width_us of the frame starting at the current left edge, or the whole frame."""
        if width_us is None:
            self.window_box.setCurrentIndex(0)
            self.plot.setXRange(self.t[0], self.t[-1], padding=0)
            return
        left = self.plot.viewRange()[0][0]
        left = min(max(left, self.t[0]), self.t[-1] - width_us)
        self.plot.setXRange(left, left + width_us, padding=0)

    def on_zoom(self, _view, x_range):
        # Once only a few hundred samples are visible, mark each one with a dot
        # so you can see where the real samples are vs. the lines between them.
        visible = (x_range[1] - x_range[0]) / self.t[-1] * SAMPLES_PER_FRAME
        if visible < 300:
            self.curve.setSymbol("o")
            self.curve.setSymbolSize(4)
            self.curve.setSymbolBrush("#4ea1ff")
            self.curve.setSymbolPen(None)
        else:
            self.curve.setSymbol(None)

    def refresh(self):
        if self.paused:
            return
        # Draw only the newest frame; anything older is already stale.
        raw = None
        while True:
            try:
                raw = self.frames.get_nowait()
            except queue.Empty:
                break
        if raw is None:
            return

        self.frame_count += 1
        volts = raw * (VREF / ADC_FULL_SCALE)
        self.curve.setData(self.t, volts)

        span = self.t[-1]
        fps = self.frame_count / max(time.monotonic() - self.t0, 1e-6)
        self.readout.setText(
            f"frames {self.frame_count:6d} │ "
            f"min {volts.min():5.3f} V  max {volts.max():5.3f} V  "
            f"pk-pk {np.ptp(volts):5.3f} V  mean {volts.mean():5.3f} V │ "
            f"{SAMPLES_PER_FRAME} samples / {span:.2f} µs "
            f"({SAMPLES_PER_FRAME / span:.2f} MSPS) │ {fps:.0f} fps"
        )

    def closeEvent(self, event):
        self.timer.stop()
        self.reader.close()
        super().closeEvent(event)


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    app = QtWidgets.QApplication(sys.argv)
    win = Scope(port)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
