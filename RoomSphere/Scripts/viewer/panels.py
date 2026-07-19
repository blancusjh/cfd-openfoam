"""Panel de control del visor (solo construccion de widgets; el cableado de
senales vive en main.py)."""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                            QGroupBox, QHBoxLayout, QLabel, QPushButton,
                            QSlider, QSpinBox, QVBoxLayout, QWidget)

CMAPS = ["inferno", "viridis", "plasma", "magma", "cividis", "turbo",
         "coolwarm", "jet"]
VEC_CMAPS = ["cool", "turbo", "viridis", "plasma", "spring"]
VOL_PRESETS = ["sigmoid", "sigmoid_5", "sigmoid_10", "linear", "geom"]


def _dspin(lo, hi, val, step=0.01, dec=3):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(val)
    return s


def _ispin(lo, hi, val, step=1):
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setValue(val)
    return s


class ControlPanel(QWidget):
    def __init__(self, scalars, vectors, n_times, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # --- tiempo ---
        g = QGroupBox("Tiempo")
        f = QVBoxLayout(g)
        self.time_label = QLabel("t = 0.00 s")
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(0, n_times - 1)
        self.btn_play = QPushButton("Reproducir")
        self.btn_play.setCheckable(True)
        self.fps = _dspin(1, 60, 12, 1, 0)
        self.stride = _ispin(1, 200, 10)
        row = QHBoxLayout()
        row.addWidget(self.btn_play)
        row.addWidget(QLabel("fps"))
        row.addWidget(self.fps)
        row.addWidget(QLabel("paso"))
        row.addWidget(self.stride)
        f.addWidget(self.time_label)
        f.addWidget(self.time_slider)
        f.addLayout(row)
        lay.addWidget(g)

        # --- campos y rangos ---
        g = QGroupBox("Campos")
        f = QFormLayout(g)
        self.scalar_combo = QComboBox()
        self.scalar_combo.addItems(scalars)
        self.vector_combo = QComboBox()
        self.vector_combo.addItems(vectors)
        self.smin = _dspin(-1e9, 1e9, 300)
        self.smax = _dspin(-1e9, 1e9, 322)
        self.btn_sauto = QPushButton("auto")
        self.vmax = _dspin(1e-6, 1e9, 0.6)
        self.btn_vauto = QPushButton("auto")
        f.addRow("escalar", self.scalar_combo)
        row = QHBoxLayout()
        row.addWidget(self.smin)
        row.addWidget(self.smax)
        row.addWidget(self.btn_sauto)
        f.addRow("rango", row)
        f.addRow("vectorial", self.vector_combo)
        row = QHBoxLayout()
        row.addWidget(self.vmax)
        row.addWidget(self.btn_vauto)
        f.addRow("|max|", row)
        lay.addWidget(g)

        # --- plano de corte ---
        g = QGroupBox("Plano (corte / clip / glifos)")
        f = QFormLayout(g)
        self.theta = _dspin(0, 180, 90, 5, 1)
        self.phi = _dspin(0, 360, 90, 5, 1)
        self.dist = _dspin(-1, 1, 0.0, 0.01, 3)
        self.chk_widget = QCheckBox("widget arrastrable en escena")
        f.addRow("θ [°] desde +y", self.theta)
        f.addRow("φ [°] de +x a +z", self.phi)
        f.addRow("d a lo largo de n", self.dist)
        f.addRow(self.chk_widget)
        lay.addWidget(g)

        # --- representaciones del campo escalar ---
        g = QGroupBox("Escalar: representaciones")
        f = QFormLayout(g)
        self.chk_slice = QCheckBox("corte en el plano")
        self.slice_op = _dspin(0, 1, 0.9, 0.05, 2)
        self.chk_volume = QCheckBox("volume rendering")
        self.vol_preset = QComboBox()
        self.vol_preset.addItems(VOL_PRESETS)
        self.vol_unit = _dspin(0.01, 2, 0.3, 0.05, 2)
        self.chk_iso = QCheckBox("isosuperficies")
        self.iso_value = _dspin(-1e9, 1e9, 311)
        self.iso_n = _ispin(1, 8, 3)
        self.iso_op = _dspin(0, 1, 0.35, 0.05, 2)
        self.chk_clip = QCheckBox("clip (media caja)")
        f.addRow(self.chk_slice)
        f.addRow("  opacidad corte", self.slice_op)
        f.addRow(self.chk_volume)
        f.addRow("  transferencia", self.vol_preset)
        f.addRow("  dist. opacidad", self.vol_unit)
        f.addRow(self.chk_iso)
        f.addRow("  isovalor", self.iso_value)
        f.addRow("  n superficies", self.iso_n)
        f.addRow("  opacidad iso", self.iso_op)
        f.addRow(self.chk_clip)
        lay.addWidget(g)

        # --- representaciones del campo vectorial ---
        g = QGroupBox("Vector: representaciones")
        f = QFormLayout(g)
        self.chk_glyph = QCheckBox("glifos eulerianos (en el plano)")
        self.glyph_n = _ispin(50, 3000, 400, 50)
        self.glyph_factor = _dspin(0.005, 1, 0.12, 0.01, 3)
        self.chk_tracer = QCheckBox("trazadores lagrangianos (3D)")
        self.tracer_n = _ispin(50, 3000, 600, 50)
        self.chk_stream = QCheckBox("streamlines desde la esfera")
        self.stream_n = _ispin(10, 500, 100, 10)
        self.stream_tube = _dspin(0.001, 0.02, 0.004, 0.001, 3)
        f.addRow(self.chk_glyph)
        f.addRow("  n flechas", self.glyph_n)
        f.addRow("  escala flecha", self.glyph_factor)
        f.addRow(self.chk_tracer)
        f.addRow("  n trazadores", self.tracer_n)
        f.addRow(self.chk_stream)
        f.addRow("  semillas", self.stream_n)
        f.addRow("  radio tubo", self.stream_tube)
        lay.addWidget(g)

        # --- apariencia y salida ---
        g = QGroupBox("Apariencia y salida")
        f = QFormLayout(g)
        self.bg_combo = QComboBox()
        self.bg_combo.addItems(["light", "dark"])
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(CMAPS)
        self.vec_cmap_combo = QComboBox()
        self.vec_cmap_combo.addItems(VEC_CMAPS)
        self.btn_shot = QPushButton("Captura PNG")
        self.btn_gif = QPushButton("Exportar GIF")
        f.addRow("fondo", self.bg_combo)
        f.addRow("cmap escalar", self.cmap_combo)
        f.addRow("cmap vector", self.vec_cmap_combo)
        row = QHBoxLayout()
        row.addWidget(self.btn_shot)
        row.addWidget(self.btn_gif)
        f.addRow(row)
        lay.addWidget(g)

        lay.addStretch(1)
