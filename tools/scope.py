#!/usr/bin/env python3


import os
import sys
import time
import threading
import queue
from collections import deque

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

import numpy as np
import serial
import serial.tools.list_ports
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg


SAMPLES_PER_FRAME = 100          # uint16 count of snapshot[]
BYTES_PER_FRAME = SAMPLES_PER_FRAME * 2

ADC_CLK_HZ = 48_000_000
PAIR_CYCLES = 19                 # t_sample(6.5) + t_convert(12.5)
DELAY_CYCLES = 9                 # TwoSamplingDelay: ADC2 offset from ADC1

VREF = 3.3
ADC_FULL_SCALE = 4095            # 12-bit

HISTORY_SECONDS = 10.0           # rolling wall-clock window kept for scrubback

STM32_VID, STM32_CDC_PID = 0x0483, 0x5740


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
        self.resize(1050, 760)

        self.frames = queue.Queue(maxsize=4)
        self.reader = Reader(port, self.frames)
        self.reader.start()

        self.t = build_time_axis(SAMPLES_PER_FRAME)
        self.paused = False
        self.frame_count = 0
        self.t0 = time.monotonic()

        # Rolling history, trimmed to HISTORY_SECONDS of wall-clock time.
        # Per-frame stats are precomputed on arrival so redraws stay cheap.
        self.h_t = deque()
        self.h_min = deque()
        self.h_max = deque()
        self.h_mean = deque()
        self.h_frames = deque()

        pg.setConfigOptions(antialias=True)

        # --- top: one frame, on the true (non-uniform) microsecond axis -------
        self.plot = pg.PlotWidget(title="Current frame")
        self.plot.setLabel("bottom", "Time", units="µs")
        self.plot.setLabel("left", "Voltage", units="V")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setYRange(0, VREF)
        self.plot.setXRange(self.t[0], self.t[-1])
        self.curve = self.plot.plot(pen=pg.mkPen("#4ea1ff", width=1.5))

        # --- bottom: rolling history, min/max envelope + mean -----------------
        self.hist_plot = pg.PlotWidget(title=f"Last {HISTORY_SECONDS:g} s")
        self.hist_plot.setLabel("bottom", "Elapsed", units="s")
        self.hist_plot.setLabel("left", "Voltage", units="V")
        self.hist_plot.showGrid(x=True, y=True, alpha=0.3)
        self.hist_plot.setYRange(0, VREF)
        self.hist_min = self.hist_plot.plot(pen=pg.mkPen("#2d6a9f", width=1))
        self.hist_max = self.hist_plot.plot(pen=pg.mkPen("#2d6a9f", width=1))
        self.hist_plot.addItem(
            pg.FillBetweenItem(self.hist_min, self.hist_max, brush=pg.mkBrush(45, 106, 159, 70))
        )
        self.hist_mean = self.hist_plot.plot(pen=pg.mkPen("#ffb454", width=1.5))

        # Draggable cursor, only while paused: picks which past frame to show.
        self.cursor = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen("#e05c5c", width=1))
        self.hist_plot.addItem(self.cursor)
        self.cursor.hide()
        self.cursor.sigPositionChanged.connect(self.on_cursor)

        self.readout = QtWidgets.QLabel("waiting for data…")
        self.readout.setStyleSheet("font-family: monospace; padding: 4px;")

        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self.on_pause)

        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(self.readout, 1)
        bar.addWidget(self.pause_btn)

        root = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(root)
        layout.addWidget(self.plot, 3)
        layout.addWidget(self.hist_plot, 2)
        layout.addLayout(bar)
        self.setCentralWidget(root)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(30)   # ~33 Hz redraw; the link, not the GUI, is the limit

    # ------------------------------------------------------------------ pause
    def on_pause(self, checked: bool):
        self.paused = checked
        self.pause_btn.setText("Resume" if checked else "Pause")
        if checked and self.h_t:
            # Freeze: show the whole retained window and expose the cursor.
            self.hist_plot.setXRange(self.h_t[0], self.h_t[-1])
            self.cursor.setValue(self.h_t[-1])
            self.cursor.show()
            self.plot.setTitle("Paused — drag the red cursor to scrub frames")
        else:
            self.cursor.hide()
            self.plot.setTitle("Current frame")

    def on_cursor(self):
        """Show whichever retained frame is nearest the cursor."""
        if not self.paused or not self.h_t:
            return
        times = np.fromiter(self.h_t, dtype=float, count=len(self.h_t))
        i = int(np.argmin(np.abs(times - self.cursor.value())))
        self.show_frame(self.h_frames[i])
        self.plot.setTitle(f"Paused — frame {i + 1}/{len(self.h_t)} at t = {times[i]:.3f} s")

    # ----------------------------------------------------------------- drawing
    def show_frame(self, raw: np.ndarray):
        self.curve.setData(self.t, raw * (VREF / ADC_FULL_SCALE))

    def refresh(self):
        if self.paused:
            return                      # freeze the display and keep history intact
        try:
            raw = self.frames.get_nowait()
        except queue.Empty:
            return

        self.frame_count += 1
        now = time.monotonic() - self.t0
        volts = raw * (VREF / ADC_FULL_SCALE)

        self.h_t.append(now)
        self.h_frames.append(raw)
        self.h_min.append(float(volts.min()))
        self.h_max.append(float(volts.max()))
        self.h_mean.append(float(volts.mean()))
        while self.h_t and now - self.h_t[0] > HISTORY_SECONDS:
            for d in (self.h_t, self.h_frames, self.h_min, self.h_max, self.h_mean):
                d.popleft()

        self.show_frame(raw)

        n = len(self.h_t)
        ts = np.fromiter(self.h_t, dtype=float, count=n)
        self.hist_min.setData(ts, np.fromiter(self.h_min, dtype=float, count=n))
        self.hist_max.setData(ts, np.fromiter(self.h_max, dtype=float, count=n))
        self.hist_mean.setData(ts, np.fromiter(self.h_mean, dtype=float, count=n))
        self.hist_plot.setXRange(max(0.0, now - HISTORY_SECONDS), max(now, HISTORY_SECONDS))

        span = self.t[-1]
        rate = n / max(now - self.h_t[0], 1e-6)
        self.readout.setText(
            f"frames {self.frame_count:6d} │ "
            f"min {volts.min():5.3f} V  max {volts.max():5.3f} V  "
            f"pk-pk {np.ptp(volts):5.3f} V  mean {volts.mean():5.3f} V │ "
            f"{SAMPLES_PER_FRAME} samples / {span:.2f} µs "
            f"({SAMPLES_PER_FRAME / span:.2f} MSPS) │ "
            f"history {n} frames @ {rate:.0f} fps"
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
