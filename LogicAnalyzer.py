"""UART Logic Analyzer - mỗi byte nhận được = 1 mẫu của 8 kênh (D0..D7).

Cài đặt:  pip install pyserial pyqtgraph numpy PyQt5
Chạy:     python uart_logic_analyzer.py
"""
import sys, re
import numpy as np
import serial, serial.tools.list_ports
import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore, QtGui

W = QtWidgets
COLORS = ['#e6194b', '#f58231', '#ffe119', '#3cb44b', '#42d4f4', '#4363d8', '#911eb4', '#f032e6']


class App(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('UART Logic Analyzer')
        self.resize(1250, 780)
        self.ser = None
        self.buf = bytearray()
        self.data = np.zeros(0, np.uint8)
        self.armed = False
        self.t0 = 0
        self.dirty = False

        root = W.QWidget(); self.setCentralWidget(root)
        lay = W.QVBoxLayout(root)

        # ---- hàng 1: kết nối + lấy mẫu
        r1 = W.QHBoxLayout(); lay.addLayout(r1)
        self.port = W.QComboBox(); self.port.setMinimumWidth(130)
        b_ref = W.QPushButton('Làm mới'); b_ref.clicked.connect(self.refresh_ports)
        self.baud = W.QComboBox(); self.baud.setEditable(True)
        self.baud.addItems(['115200', '230400', '460800', '921600', '1000000', '2000000', '3000000'])
        self.baud.setCurrentText('921600')
        self.b_conn = W.QPushButton('Kết nối'); self.b_conn.clicked.connect(self.toggle_conn)
        self.rate = W.QDoubleSpinBox(); self.rate.setRange(1, 1e9); self.rate.setDecimals(0)
        self.rate.setValue(1_000_000); self.rate.setSuffix(' Hz'); self.rate.valueChanged.connect(self.redraw)
        self.nsamp = W.QSpinBox(); self.nsamp.setRange(1, 5_000_000); self.nsamp.setValue(16384)
        self.mode = W.QComboBox(); self.mode.addItems(['Capture (N mẫu)', 'Stream (cuộn)'])
        self.b_arm = W.QPushButton('Arm / Chạy'); self.b_arm.clicked.connect(self.arm)
        for w_, t in [(self.port, 'Cổng'), (b_ref, None), (self.baud, 'Baud'), (self.b_conn, None),
                      (self.rate, 'Tần số mẫu'), (self.nsamp, 'N mẫu'), (self.mode, None), (self.b_arm, None)]:
            if t: r1.addWidget(W.QLabel(t))
            r1.addWidget(w_)
        r1.addStretch()

        # ---- hàng 2: trigger + file
        r2 = W.QHBoxLayout(); lay.addLayout(r2)
        self.tch = W.QComboBox(); self.tch.addItems(['Không'] + [f'D{i}' for i in range(8)])
        self.tedge = W.QComboBox(); self.tedge.addItems(['Cạnh lên', 'Cạnh xuống'])
        self.tch.currentIndexChanged.connect(self.apply_trigger)
        self.tedge.currentIndexChanged.connect(self.apply_trigger)
        b_fit = W.QPushButton('Vừa khung'); b_fit.clicked.connect(lambda: self.plot.autoRange())
        b_clr = W.QPushButton('Xoá'); b_clr.clicked.connect(self.clear)
        b_save = W.QPushButton('Lưu CSV'); b_save.clicked.connect(self.save_csv)
        b_load = W.QPushButton('Mở file hex'); b_load.clicked.connect(self.load_file)
        b_paste = W.QPushButton('Dán chuỗi hex'); b_paste.clicked.connect(self.paste_hex)
        self.spb = W.QDoubleSpinBox(); self.spb.setRange(0, 1e6); self.spb.setDecimals(2)
        self.spb.setToolTip('Số mẫu trên 1 bit (vd 8.68 cho 115200 baud @ 1 MHz). 0 = tắt dịch chuỗi')
        self.spb.valueChanged.connect(self.measure)
        self.lsb = W.QCheckBox('LSB trước'); self.lsb.setChecked(True); self.lsb.stateChanged.connect(self.measure)
        for w_, t in [(self.tch, 'Trigger'), (self.tedge, None), (b_fit, None), (b_clr, None),
                      (b_save, None), (b_load, None), (b_paste, None), (self.spb, 'Mẫu/bit'), (self.lsb, None)]:
            if t: r2.addWidget(W.QLabel(t))
            r2.addWidget(w_)
        r2.addStretch()

        # ---- đồ thị
        pg.setConfigOptions(antialias=False)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=False, alpha=0.25)
        self.plot.setLabel('bottom', 'Thời gian', units='µs')
        self.plot.setYRange(-0.1, 7.95, padding=0)
        self.plot.setLimits(yMin=-0.5, yMax=8.5)
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.getAxis('left').setTicks([[(7 - i + 0.6, f'D{i}') for i in range(8)]])
        self.plot.setClipToView(True)
        self.plot.setDownsampling(mode='peak', auto=True)
        self.curves = [self.plot.plot(pen=pg.mkPen(COLORS[i], width=1.5)) for i in range(8)]
        self.labels = []; self.runs = None
        self.plot.getViewBox().sigXRangeChanged.connect(self.update_labels)
        lay.addWidget(self.plot, 1)

        # cursor A, B
        self.ca = pg.InfiniteLine(0, movable=True, pen=pg.mkPen('#00ff88', width=2), label='A',
                                  labelOpts={'position': 0.96, 'color': '#00ff88'})
        self.cb = pg.InfiniteLine(100, movable=True, pen=pg.mkPen('#ff5577', width=2), label='B',
                                  labelOpts={'position': 0.96, 'color': '#ff5577'})
        self.plot.addItem(self.ca); self.plot.addItem(self.cb)
        self.ca.sigPositionChanged.connect(self.measure)
        self.cb.sigPositionChanged.connect(self.measure)

        # ---- đo đạc
        self.info = W.QLabel(); self.info.setStyleSheet('font-family:Consolas,monospace;')
        self.info.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.info)
        self.dec = W.QPlainTextEdit(); self.dec.setReadOnly(True); self.dec.setMaximumHeight(150)
        self.dec.setStyleSheet('font-family:Consolas,monospace;')
        lay.addWidget(self.dec)
        self.statusBar().showMessage('Chưa kết nối')

        self.refresh_ports()
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self.poll); self.timer.start(30)

    # ---------- serial ----------
    def refresh_ports(self):
        self.port.clear()
        self.port.addItems([p.device for p in serial.tools.list_ports.comports()])

    def toggle_conn(self):
        if self.ser:
            self.ser.close(); self.ser = None
            self.b_conn.setText('Kết nối'); self.statusBar().showMessage('Đã ngắt'); return
        try:
            self.ser = serial.Serial(self.port.currentText(), int(self.baud.currentText()), timeout=0)
        except Exception as e:
            W.QMessageBox.warning(self, 'Lỗi', str(e)); return
        self.b_conn.setText('Ngắt'); self.statusBar().showMessage('Đã kết nối')
        if self.mode.currentIndex() == 1: self.arm()

    def arm(self):
        if not self.ser:
            W.QMessageBox.information(self, 'Chưa kết nối', 'Hãy kết nối cổng COM trước.'); return
        self.ser.reset_input_buffer(); self.buf.clear(); self.armed = True
        self.statusBar().showMessage('Đang chờ dữ liệu... (hãy cho MCU gửi buffer)')

    def poll(self):
        if self.ser and self.armed:
            try:
                chunk = self.ser.read(self.ser.in_waiting or 0)
            except Exception as e:
                self.statusBar().showMessage(f'Lỗi serial: {e}'); return
            if chunk:
                self.buf.extend(chunk); n = self.nsamp.value()
                if self.mode.currentIndex() == 0:
                    self.statusBar().showMessage(f'Đã nhận {min(len(self.buf), n)}/{n} mẫu')
                    if len(self.buf) >= n:
                        self.data = np.frombuffer(bytes(self.buf[:n]), np.uint8).copy()
                        self.buf.clear(); self.armed = False
                        self.apply_trigger(); self.plot.autoRange()
                        self.statusBar().showMessage(f'Xong: {n} mẫu')
                else:
                    if len(self.buf) > n: del self.buf[:-n]
                    self.data = np.frombuffer(bytes(self.buf), np.uint8).copy(); self.t0 = 0
                    self.dirty = True
        if self.dirty:
            self.dirty = False; self.redraw()

    # ---------- trigger + vẽ ----------
    def apply_trigger(self):
        self.t0 = 0; c = self.tch.currentIndex() - 1
        if c >= 0 and len(self.data) > 1:
            bits = ((self.data >> c) & 1).astype(np.int8)
            idx = np.flatnonzero(np.diff(bits) == (1 if self.tedge.currentIndex() == 0 else -1))
            if idx.size: self.t0 = int(idx[0]) + 1
            else: self.statusBar().showMessage('Không tìm thấy cạnh trigger trong dữ liệu')
        self.redraw()

    def redraw(self):
        n = len(self.data)
        if n == 0:
            for c in self.curves: c.setData([], [])
            self.info.setText(''); self.dec.clear(); self.runs = None; self.update_labels(); return
        dt = 1e6 / self.rate.value()
        t = (np.arange(n + 1) - self.t0) * dt
        x = np.repeat(t, 2)[1:-1]
        self.runs = []
        for ch in range(8):
            bits = (self.data >> ch) & 1
            y = np.repeat(bits * 0.5 + (7 - ch) + 0.35, 2)
            self.curves[ch].setData(x, y)
            e = np.flatnonzero(np.diff(bits)) + 1          # các điểm đổi mức
            st = np.concatenate(([0], e)); en = np.concatenate((e, [n]))
            self.runs.append((st, en, bits[st]))           # mỗi 'xung' = 1 đoạn liên tiếp cùng mức
        self.update_labels()
        if not (t[0] <= self.ca.value() <= t[-1]): self.ca.setValue(t[0] + (t[-1] - t[0]) * 0.25)
        if not (t[0] <= self.cb.value() <= t[-1]): self.cb.setValue(t[0] + (t[-1] - t[0]) * 0.50)
        self.measure()

    def measure(self):
        n = len(self.data)
        if n == 0: return
        dt = 1e6 / self.rate.value()
        a, b = sorted((self.ca.value(), self.cb.value()))
        ia = int(np.clip(round(a / dt) + self.t0, 0, n - 1)); ib = int(np.clip(round(b / dt) + self.t0, 0, n - 1))
        span = (ib - ia) * dt
        lines = [f'A = {a:.2f} µs   B = {b:.2f} µs   ΔT = {span:.2f} µs   1/ΔT = '
                 f'{(1e6 / span if span > 0 else 0):.1f} Hz   ({ib - ia} mẫu)',
                 'Kênh  Cạnh lên  Cạnh xuống  Tần số (Hz)   Duty %   Chu kỳ TB (µs)']
        seg = self.data[ia:ib + 1]
        for ch in range(8):
            bits = ((seg >> ch) & 1).astype(np.int8)
            d = np.diff(bits); r = int((d == 1).sum()); f = int((d == -1).sum())
            if r >= 2 and span > 0:
                per = np.diff(np.flatnonzero(d == 1)).mean() * dt; freq = 1e6 / per
                fs, ps = f'{freq:12.1f}', f'{per:12.2f}'
            else: fs = ps = f'{"-":>12}'
            duty = bits.mean() * 100 if len(bits) else 0
            lines.append(f'D{ch}    {r:8d}  {f:10d}  {fs}  {duty:6.1f}  {ps}')
        self.info.setText('\n'.join(lines))
        self.decode(ia, ib)

    def update_labels(self, *args):
        """Ghi bit 0/1 (và độ rộng) ngay dưới từng xung đang nhìn thấy."""
        for it in self.labels: self.plot.removeItem(it)
        self.labels = []
        if not self.runs or not len(self.data): return
        vb = self.plot.getViewBox(); x0, x1 = vb.viewRange()[0]
        if x1 <= x0: return
        dt = 1e6 / self.rate.value(); pxu = vb.width() / (x1 - x0)   # pixel trên mỗi µs
        font = QtGui.QFont('Consolas', 8)
        for ch in range(8):
            st, en, v = self.runs[ch]
            xs = (st - self.t0) * dt; xe = (en - self.t0) * dt
            vis = np.flatnonzero((xe > x0) & (xs < x1) & ((xe - xs) * pxu >= 14))
            for k in vis[:60]:
                a, b = max(xs[k], x0), min(xe[k], x1)
                wpx = (xe[k] - xs[k]) * pxu
                txt = f'{v[k]}\n{xe[k] - xs[k]:.1f}µs' if wpx >= 60 else str(v[k])
                it = pg.TextItem(txt, color=COLORS[ch], anchor=(0.5, 0)); it.setFont(font)
                it.setPos((a + b) / 2, (7 - ch) + 0.32)
                self.plot.addItem(it, ignoreBounds=True); self.labels.append(it)

    def decode(self, ia, ib):
        """Lấy mẫu giữa mỗi bit (theo Mẫu/bit) trong đoạn A..B, ghép thành chuỗi bit và giá trị hex."""
        spb = self.spb.value()
        if spb <= 0:
            self.dec.setPlainText('Đặt "Mẫu/bit" > 0 (vd 8.68 cho 115200 baud @ 1 MHz) để dịch chuỗi bit giữa A và B.')
            return
        k = int((ib - ia) / spb)
        if k < 1: self.dec.setPlainText(''); return
        pos = np.minimum((ia + (np.arange(k) + 0.5) * spb).astype(int), len(self.data) - 1)
        out = [f'Chuỗi bit giữa A và B ({k} bit, nhóm 8 bit, {"LSB" if self.lsb.isChecked() else "MSB"} trước):']
        for ch in range(8):
            bits = ((self.data[pos] >> ch) & 1).tolist()
            s = ' '.join(''.join(map(str, bits[i:i + 8])) for i in range(0, k, 8))
            hx = []
            for i in range(0, k - 7, 8):
                g = bits[i:i + 8]
                if not self.lsb.isChecked(): g = g[::-1]
                val = sum(b << j for j, b in enumerate(g))
                hx.append(f'{val:02X}' + (f"'{chr(val)}'" if 32 <= val < 127 else ''))
            out.append(f'D{ch}: {s}   ->   {" ".join(hx)}')
        self.dec.setPlainText('\n'.join(out))

    # ---------- file ----------
    def clear(self):
        self.data = np.zeros(0, np.uint8); self.buf.clear(); self.redraw()

    def save_csv(self):
        if not len(self.data): return
        fn, _ = W.QFileDialog.getSaveFileName(self, 'Lưu CSV', 'capture.csv', 'CSV (*.csv)')
        if not fn: return
        dt = 1e6 / self.rate.value()
        with open(fn, 'w') as f:
            f.write('time_us,byte,' + ','.join(f'D{i}' for i in range(8)) + '\n')
            for i, v in enumerate(self.data):
                f.write(f'{(i - self.t0) * dt:.3f},{v:02X},' + ','.join(str((v >> k) & 1) for k in range(8)) + '\n')

    def load_file(self):
        fn, _ = W.QFileDialog.getOpenFileName(self, 'Mở file', '', 'Text (*.txt *.csv *.hex);;All (*)')
        if not fn: return
        self.set_hex(open(fn, errors='ignore').read())

    @staticmethod
    def parse_hex(txt):
        txt = re.sub(r'0x', '', txt, flags=re.I)
        return [int(t, 16) for t in re.split(r'[\s,;]+', txt) if re.fullmatch(r'[0-9a-fA-F]{1,2}', t)]

    def set_hex(self, txt):
        vals = self.parse_hex(txt)
        if not vals:
            W.QMessageBox.warning(self, 'Lỗi', 'Không đọc được giá trị hex nào.'); return False
        self.data = np.array(vals, np.uint8); self.apply_trigger(); self.plot.autoRange()
        self.statusBar().showMessage(f'Đã nạp {len(vals)} mẫu (mô phỏng)')
        return True

    def paste_hex(self):
        dlg = W.QDialog(self); dlg.setWindowTitle('Dán chuỗi hex để mô phỏng'); dlg.resize(650, 380)
        v = W.QVBoxLayout(dlg)
        v.addWidget(W.QLabel('Dán các byte hex, cách nhau bằng dấu cách, xuống dòng hoặc dấu phẩy '
                             '(ví dụ: 11 11 10 13 93 D3 hoặc 0x11, 0x13):'))
        te = W.QPlainTextEdit(); te.setStyleSheet('font-family:Consolas,monospace;')
        cb = QtWidgets.QApplication.clipboard().text()
        if self.parse_hex(cb): te.setPlainText(cb)  # tự điền nếu clipboard đang có chuỗi hex
        v.addWidget(te)
        cnt = W.QLabel(); v.addWidget(cnt)
        te.textChanged.connect(lambda: cnt.setText(f'{len(self.parse_hex(te.toPlainText()))} byte hợp lệ'))
        te.textChanged.emit()
        row = W.QHBoxLayout(); v.addLayout(row); row.addStretch()
        ok = W.QPushButton('Vẽ'); cancel = W.QPushButton('Huỷ')
        row.addWidget(ok); row.addWidget(cancel)
        cancel.clicked.connect(dlg.reject)
        ok.clicked.connect(lambda: dlg.accept() if self.set_hex(te.toPlainText()) else None)
        dlg.exec_() if hasattr(dlg, 'exec_') else dlg.exec()


if __name__ == '__main__':
    app = W.QApplication(sys.argv)
    w = App(); w.show()
    sys.exit(app.exec_() if hasattr(app, 'exec_') else app.exec())