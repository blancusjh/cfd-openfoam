#!/usr/bin/env python
"""
Anima en 3D el enfriamiento de la esfera (VisPy).

Dibuja los centros de celda como nube de puntos coloreada por T, recortada a
un hemisferio (y>=0) para ver el nucleo caliente. Recorre los instantes.

Requiere el campo de centros de celda:  postProcess -func writeCellCentres -time 0
Uso: python Scripts/visualize_sphere.py [caso] [intervalo_seg]
"""
import re
import sys
from pathlib import Path

import numpy as np
from vispy import scene, app
from vispy.color import get_colormap


def _field_block(path):
    txt = path.read_text()
    return txt.split("internalField", 1)[1].split("boundaryField", 1)[0]


def read_scalar(path, ncells):
    seg = _field_block(path)
    if "nonuniform" in seg[:40]:
        o = seg.index("("); c = seg.index(")", o)
        return np.array([float(x) for x in seg[o + 1:c].split()])
    val = float(re.search(r"uniform\s+([-\d.eE+]+)", seg).group(1))
    return np.full(ncells, val)


def read_vectors(path):
    seg = _field_block(path)
    trip = re.findall(r"\(([^()]*)\)", seg)
    return np.array([[float(a) for a in t.split()] for t in trip])


def main(case, interval):
    C = read_vectors(case / "0" / "C")
    ncells = len(C)
    mask = C[:, 1] >= 0            # medio hemisferio: revela el nucleo
    pos = C[mask]

    times = sorted((d.name for d in case.iterdir()
                    if d.is_dir() and re.fullmatch(r"\d+(\.\d+)?", d.name)
                    and (d / "T").exists()), key=float)
    fields = [read_scalar(case / t / "T", ncells)[mask] for t in times]
    # escala de color robusta por percentiles: ignora sobre/subimpulsos numericos
    # (p.ej. el transitorio de t=2 s) que si no lavarian toda la animacion
    allv = np.concatenate(fields)
    vmin, vmax = np.percentile(allv, 1), np.percentile(allv, 99)
    print(f"Instantes: {len(times)}   escala color T: {vmin:.0f}..{vmax:.0f} K "
          f"(datos reales: {allv.min():.0f}..{allv.max():.0f})")

    cmap = get_colormap("hot")

    def colors_for(f):
        norm = (f - vmin) / (vmax - vmin + 1e-30)
        return cmap.map(norm[:, np.newaxis])   # (N,1) por 'hot'

    canvas = scene.SceneCanvas(keys="interactive", bgcolor="black",
                               size=(900, 820), show=True)
    view = canvas.central_widget.add_view()
    view.camera = scene.cameras.TurntableCamera(fov=30, distance=0.5)

    markers = scene.visuals.Markers(parent=view.scene)
    markers.set_data(pos, face_color=colors_for(fields[0]), size=10, edge_width=0)
    label = scene.visuals.Text(f"t = {times[0]} s", color="white", font_size=12,
                               pos=(0, 0, 0.13), parent=view.scene)
    view.camera.set_range()

    state = {"i": 0}

    def on_timer(event):
        state["i"] = (state["i"] + 1) % len(times)
        i = state["i"]
        markers.set_data(pos, face_color=colors_for(fields[i]), size=10, edge_width=0)
        label.text = f"t = {times[i]} s"
        canvas.update()

    timer = app.Timer(interval=interval, connect=on_timer, start=True)
    app.run()


if __name__ == "__main__":
    args = sys.argv[1:]
    case = Path(args[0]) if args else Path.cwd()
    interval = float(args[1]) if len(args) > 1 else 0.1
    main(case, interval)
