#!/usr/bin/env python
"""Visor 3D dedicado del caso (PyVista embebido en Qt via pyvistaqt).

Uso (desde la raiz del caso, con el .venv activo):
    python Scripts/viewer/main.py [ruta_al_caso]

Cada campo se visualiza segun su naturaleza:
    escalares (T, p, p_rgh, |U|): corte en plano, volume rendering,
                                  isosuperficies, clip
    vectoriales (U): glifos eulerianos, trazadores lagrangianos, streamlines

El plano de corte se define por los angulos θ (desde la vertical +y) y
φ (azimut de +x a +z) de su normal, mas una traslacion d a lo largo de ella;
tambien puede arrastrarse directamente en escena (checkbox del widget).
"""
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image
from pyvistaqt import QtInteractor
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (QApplication, QFileDialog, QMainWindow,
                            QProgressDialog, QScrollArea, QSplitter)

from viewer.model import CaseModel
from viewer.panels import ControlPanel
from viewer import representations as vrep

THEMES = {"light": ("white", "black"), "dark": ("#1a1a1a", "white")}


class Viewer(QMainWindow):
    def __init__(self, case):
        super().__init__()
        self.setWindowTitle(f"Visor OpenFOAM — {Path(case).resolve().name}")
        self.model = CaseModel(case)
        m = self.model

        # ---- estado compartido que leen las representaciones ----
        self.idx = len(m.times) - 1                  # arrancar en el ultimo t
        self.internal = m.load(self.t)
        self._internal_t = self.t
        self._baked = None                           # precómputo de animación
        self.scalar_field = "T" if "T" in m.scalars else m.scalars[0]
        self.vector_field = m.vectors[0] if m.vectors else None
        self.cmap = "inferno"
        self.bg, self.fg = THEMES["light"]
        lo, hi = m.field_range(self.scalar_field, self.t)
        self.scalar_clim = [lo, hi]
        vhi = m.field_range(self.vector_field, self.t)[1] if self.vector_field else 1
        self.vector_clim = [0.0, max(round(vhi, 2), 1e-6)]
        self.params = dict(slice_opacity=0.9, vol_preset="uniforme",
                           vol_opacity=0.5, vol_unit=0.3,
                           iso_value=0.5 * (lo + hi), iso_n=3, iso_opacity=0.35,
                           glyph_n=400, glyph_factor=0.12, tracer_n=600,
                           stream_n=100, stream_tube=0.004, vec_cmap="cool")

        # ---- UI: panel a la izquierda, escena a la derecha ----
        self.panel = ControlPanel(m.scalars, m.vectors, len(m.times))
        scroll = QScrollArea()
        scroll.setWidget(self.panel)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(330)
        scroll.setMaximumWidth(400)
        split = QSplitter()
        split.addWidget(scroll)
        self.plotter = QtInteractor(self)
        split.addWidget(self.plotter)
        split.setStretchFactor(1, 1)
        self.setCentralWidget(split)

        # ---- escena estatica ----
        self.plotter.set_background(self.bg)
        if m.sphere is not None:
            self.plotter.add_mesh(m.sphere, color="firebrick", smooth_shading=True)
        self.outline_actor = self.plotter.add_mesh(m.outline, color=self.fg)
        c = m.center
        self.plotter.camera_position = [tuple(c + np.array([1.4, 0.6, 1.4])),
                                        tuple(c), (0, 1, 0)]

        # ---- representaciones ----
        self.reps = dict(slice=vrep.SliceRep(self), volume=vrep.VolumeRep(self),
                         iso=vrep.IsoRep(self), clip=vrep.ClipRep(self),
                         glyph=vrep.GlyphRep(self), tracer=vrep.TracerRep(self),
                         stream=vrep.StreamRep(self))
        self.scalar_reps = ("slice", "volume", "iso", "clip")
        self.vector_reps = ("glyph", "tracer", "stream")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self._sync_panel_state()
        self._wire()

        # vista inicial: corte + glifos (la escena clasica del caso)
        self.panel.chk_slice.setChecked(True)
        if self.vector_field:
            self.panel.chk_glyph.setChecked(True)
        self._set_time(self.idx)

    # ---- estado derivado (lo consumen las representaciones) ----
    @property
    def t(self):
        return self.model.times[self.idx]

    def plane_n(self):
        return vrep.plane_normal(self.panel.theta.value(), self.panel.phi.value())

    def plane_o(self):
        return self.model.center + self.panel.dist.value() * self.plane_n()

    def sbar(self, title, left=False):
        d = dict(title=title, vertical=True, color=self.fg)
        if left:
            d["position_x"] = 0.05
        return d

    # ---- cableado de senales ----
    def _sync_panel_state(self):
        P = self.panel
        for w, val in ((P.smin, self.scalar_clim[0]), (P.smax, self.scalar_clim[1]),
                       (P.vmax, self.vector_clim[1]),
                       (P.iso_value, self.params["iso_value"])):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)
        P.iso_value.setRange(*self.scalar_clim)
        P.time_slider.blockSignals(True)
        P.time_slider.setValue(self.idx)
        P.time_slider.blockSignals(False)

    def _wire(self):
        P = self.panel
        P.time_slider.valueChanged.connect(lambda i: self._set_time(i))
        P.btn_play.toggled.connect(self._toggle_play)
        P.fps.valueChanged.connect(
            lambda v: self.timer.setInterval(int(1000 / v))
            if self.timer.isActive() else None)
        P.scalar_combo.currentTextChanged.connect(self._on_scalar_field)
        P.vector_combo.currentTextChanged.connect(self._on_vector_field)
        P.smin.valueChanged.connect(self._on_scalar_clim)
        P.smax.valueChanged.connect(self._on_scalar_clim)
        P.btn_sauto.clicked.connect(self._auto_scalar_clim)
        P.vmax.valueChanged.connect(self._on_vector_clim)
        P.btn_vauto.clicked.connect(self._auto_vector_clim)
        for w in (P.theta, P.phi, P.dist):
            w.valueChanged.connect(self._on_plane)
        P.chk_widget.toggled.connect(self._toggle_plane_widget)
        for name, chk in (("slice", P.chk_slice), ("volume", P.chk_volume),
                          ("iso", P.chk_iso), ("clip", P.chk_clip),
                          ("glyph", P.chk_glyph), ("tracer", P.chk_tracer),
                          ("stream", P.chk_stream)):
            chk.toggled.connect(lambda on, n=name: self._toggle_rep(n, on))
        for w, key, names in ((P.slice_op, "slice_opacity", ("slice",)),
                              (P.vol_opacity, "vol_opacity", ("volume",)),
                              (P.vol_unit, "vol_unit", ("volume",)),
                              (P.iso_value, "iso_value", ("iso",)),
                              (P.iso_n, "iso_n", ("iso",)),
                              (P.iso_op, "iso_opacity", ("iso",)),
                              (P.glyph_n, "glyph_n", ("glyph",)),
                              (P.glyph_factor, "glyph_factor", ("glyph", "tracer")),
                              (P.tracer_n, "tracer_n", ("tracer",)),
                              (P.stream_n, "stream_n", ("stream",)),
                              (P.stream_tube, "stream_tube", ("stream",))):
            w.valueChanged.connect(
                lambda v, k=key, ns=names: self._set_param(k, v, ns))
        P.vol_preset.currentTextChanged.connect(
            lambda v: self._set_param("vol_preset", v, ("volume",)))
        P.vec_cmap_combo.currentTextChanged.connect(
            lambda v: self._set_param("vec_cmap", v, self.vector_reps))
        P.bg_combo.currentTextChanged.connect(self._on_background)
        P.cmap_combo.currentTextChanged.connect(self._on_cmap)
        P.btn_bake.clicked.connect(self._bake)
        P.btn_shot.clicked.connect(self._screenshot)
        P.btn_gif.clicked.connect(self._export_gif)

    def _toggle_rep(self, name, on):
        if on:
            self._ensure_internal()
        self.reps[name].set_enabled(on)

    # ---- tiempo ----
    def _ensure_internal(self):
        """Recarga la malla del instante actual si quedo desfasada (tras
        playback precalculado, que no toca el lector)."""
        if self._internal_t != self.t:
            self.internal = self.model.load(self.t)
            self._internal_t = self.t

    def _set_time(self, idx, dt=None):
        self.idx = int(np.clip(idx, 0, len(self.model.times) - 1))
        enabled = [n for n, r in self.reps.items() if r.enabled]
        frames = self._baked_frames(enabled)
        if frames is not None:                       # via rapida: sin lector
            for n in enabled:
                self.reps[n].apply_frame(frames[n])
        else:
            self.internal = self.model.load(self.t)
            self._internal_t = self.t
            if dt is not None and dt > 0:
                self.reps["tracer"].advect(dt)
            for r in self.reps.values():
                r.refresh()
        self.plotter.add_text(f"t = {self.t:.2f} s", name="tt", font_size=12,
                              color=self.fg)
        self.panel.time_label.setText(f"t = {self.t:.2f} s")
        if self.panel.time_slider.value() != self.idx:
            self.panel.time_slider.blockSignals(True)
            self.panel.time_slider.setValue(self.idx)
            self.panel.time_slider.blockSignals(False)
        self.plotter.render()

    # ---- precómputo de animación ----
    def _bake_sig(self):
        """Firma de los parametros que afectan la geometria precalculada."""
        p, P = self.params, self.panel
        return (tuple(sorted(n for n, r in self.reps.items() if r.enabled)),
                self.scalar_field, self.vector_field, tuple(self.scalar_clim),
                P.theta.value(), P.phi.value(), P.dist.value(),
                p["iso_value"], p["iso_n"], p["glyph_n"], p["glyph_factor"],
                p["tracer_n"], p["stream_n"], p["stream_tube"],
                P.stride.value())

    def _baked_frames(self, enabled):
        b = self._baked
        if not b or not enabled or b["sig"] != self._bake_sig():
            return None
        try:
            return {n: b["frames"][(n, self.idx)] for n in enabled}
        except KeyError:
            return None                              # instante no precalculado

    def _bake(self):
        enabled = [n for n, r in self.reps.items() if r.enabled]
        if not enabled:
            self.panel.bake_status.setText("precálculo: no hay nada activado")
            return
        was_playing = self.timer.isActive()
        if was_playing:
            self.panel.btn_play.setChecked(False)
        times, stride = self.model.times, self.panel.stride.value()
        idxs = list(range(0, len(times), stride))
        prog = QProgressDialog("Precalculando animación...", "Cancelar",
                               0, len(idxs), self)
        prog.setWindowModality(Qt.WindowModal)
        sig, frames, prev = self._bake_sig(), {}, None
        for k, i in enumerate(idxs):
            prog.setValue(k)
            QApplication.processEvents()
            if prog.wasCanceled():
                self.panel.bake_status.setText("precálculo: cancelado")
                self._set_time(self.idx)             # resincronizar la escena
                return
            self.idx = i
            self.internal = self.model.load(self.t)
            self._internal_t = self.t
            if "tracer" in enabled and prev is not None:
                self.reps["tracer"].advect(times[i] - times[prev])
            for n in enabled:
                frames[(n, i)] = self.reps[n].bake_frame()
            prev = i
        prog.setValue(len(idxs))
        self._baked = dict(sig=sig, frames=frames)
        self.panel.bake_status.setText(
            f"precálculo: {len(idxs)} frames listos ({', '.join(enabled)})")
        self._set_time(0)

    def _tick(self):
        new = self.idx + self.panel.stride.value()
        if new >= len(self.model.times):
            self._set_time(0)                       # reinicio del bucle
        else:
            self._set_time(new, dt=self.model.times[new] - self.t)

    def _toggle_play(self, on):
        self.panel.btn_play.setText("Pausa" if on else "Reproducir")
        if on:
            self.timer.start(int(1000 / self.panel.fps.value()))
        else:
            self.timer.stop()

    # ---- campos y rangos ----
    def _rebuild(self, names):
        self._ensure_internal()
        for n in names:
            self.reps[n].rebuild()
        self.plotter.render()

    def _on_scalar_field(self, name):
        self.scalar_field = name
        self._auto_scalar_clim()

    def _on_vector_field(self, name):
        self.vector_field = name
        self._auto_vector_clim()

    def _auto_scalar_clim(self):
        lo, hi = self.model.field_range(self.scalar_field, self.t)
        if hi <= lo:
            hi = lo + 1
        self.scalar_clim = [lo, hi]
        self.params["iso_value"] = 0.5 * (lo + hi)
        self._sync_panel_state()
        self._rebuild(self.scalar_reps)

    def _on_scalar_clim(self):
        self.scalar_clim = [self.panel.smin.value(), self.panel.smax.value()]
        self.panel.iso_value.setRange(*self.scalar_clim)
        self._rebuild(self.scalar_reps)

    def _auto_vector_clim(self):
        vhi = self.model.field_range(self.vector_field, self.t)[1]
        self.vector_clim = [0.0, max(vhi, 1e-6)]
        self._sync_panel_state()
        self._rebuild(self.vector_reps)

    def _on_vector_clim(self):
        self.vector_clim = [0.0, self.panel.vmax.value()]
        self._rebuild(self.vector_reps)

    def _set_param(self, key, val, names):
        self.params[key] = val
        self._rebuild(names)

    # ---- plano de corte ----
    def _plane_reps_refresh(self):
        self._ensure_internal()
        for n in ("slice", "clip", "glyph"):
            self.reps[n].refresh()
        self.plotter.render()

    def _on_plane(self):
        self._plane_reps_refresh()
        if self.panel.chk_widget.isChecked():
            self._make_plane_widget()               # reposicionar el widget

    def _toggle_plane_widget(self, on):
        if on:
            self._make_plane_widget()
        else:
            self.plotter.clear_plane_widgets()
        self.plotter.render()

    def _make_plane_widget(self):
        self.plotter.clear_plane_widgets()
        self.plotter.add_plane_widget(self._on_widget_moved,
                                      normal=tuple(self.plane_n()),
                                      origin=tuple(self.plane_o()),
                                      test_callback=False)

    def _on_widget_moved(self, normal, origin):
        th, ph = vrep.normal_to_angles(normal)
        n = vrep.plane_normal(th, ph)
        d = float(np.dot(np.asarray(origin) - self.model.center, n))
        P = self.panel
        for w, val in ((P.theta, th), (P.phi, ph), (P.dist, d)):
            w.blockSignals(True)
            w.setValue(val)
            w.blockSignals(False)
        self._plane_reps_refresh()

    # ---- apariencia y salida ----
    def _on_background(self, name):
        self.bg, self.fg = THEMES[name]
        self.plotter.set_background(self.bg)
        self.outline_actor.prop.color = self.fg
        self.plotter.add_text(f"t = {self.t:.2f} s", name="tt", font_size=12,
                              color=self.fg)
        self._rebuild(self.reps.keys())             # refresca barras de color

    def _on_cmap(self, name):
        self.cmap = name
        self._rebuild(self.scalar_reps)

    def _screenshot(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar captura",
                                              "captura.png", "PNG (*.png)")
        if path:
            self.plotter.render_window.Render()     # render sincrono pre-captura
            self.plotter.screenshot(path)

    def _export_gif(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar GIF",
                                              "plume.gif", "GIF (*.gif)")
        if not path:
            return
        times, stride = self.model.times, self.panel.stride.value()
        idxs = list(range(0, len(times), stride))
        prog = QProgressDialog("Generando GIF...", "Cancelar", 0, len(idxs), self)
        prog.setWindowModality(Qt.WindowModal)
        imgs, prev = [], None
        for k, i in enumerate(idxs):
            prog.setValue(k)
            QApplication.processEvents()
            if prog.wasCanceled():
                return
            self._set_time(i, dt=None if prev is None else times[i] - times[prev])
            prev = i
            self.plotter.render_window.Render()     # render sincrono pre-captura
            imgs.append(Image.fromarray(self.plotter.screenshot(return_img=True)))
        prog.setValue(len(idxs))
        imgs[0].save(path, save_all=True, append_images=imgs[1:],
                     duration=int(1000 / self.panel.fps.value()), loop=0)

    def _shutdown(self):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        self.timer.stop()
        self.plotter.close()

    def closeEvent(self, ev):
        self._shutdown()
        super().closeEvent(ev)


def main():
    case = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    app = QApplication(sys.argv)
    w = Viewer(case)
    w.resize(1500, 1000)
    w.show()
    app.aboutToQuit.connect(w._shutdown)
    ret = app.exec()
    w._shutdown()
    # el teardown de VTK/Cocoa al final del interprete puede colgar el proceso
    # en macOS; con todo ya cerrado limpiamente, salir de forma inmediata.
    os._exit(ret)


if __name__ == "__main__":
    main()
