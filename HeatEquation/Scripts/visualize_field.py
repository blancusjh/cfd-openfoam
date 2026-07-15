#!/usr/bin/env python
"""
Anima el campo de temperatura T de OpenFOAM en el tiempo.

Lee constant/polyMesh + todas las carpetas <tiempo>/T y colorea la placa
(patch 'frontAndBack') recorriendo los instantes con un temporizador.

Uso:
    python Scripts/visualize_field.py [caso] [intervalo_seg]
    (sin argumentos: caso = directorio actual, intervalo = 0.4 s por fotograma)
"""
import re
import sys
from pathlib import Path

import numpy as np
from vispy import scene, app
from vispy.color import get_colormap


# ----------------------------------------------------------------------
# Parsers del formato OpenFOAM
# ----------------------------------------------------------------------
def _strip_header(text):
    return text.split("}", 1)[1]


def read_points(path):
    body = _strip_header(path.read_text())
    trips = re.findall(r"\(([^()]*)\)", body)
    n = int(re.search(r"(\d+)\s*\(", body).group(1))
    return np.array([[float(v) for v in t.split()] for t in trips[:n]])


def read_faces(path):
    body = _strip_header(path.read_text())
    inner = re.findall(r"\(([^()]*)\)", body)
    return [[int(i) for i in grp.split()] for grp in inner if grp.strip()]


def read_boundary(path):
    patches = {}
    for name, block in re.findall(r"(\w+)\s*\{([^}]*)\}", path.read_text()):
        ms, mn = re.search(r"startFace\s+(\d+)", block), re.search(r"nFaces\s+(\d+)", block)
        if ms and mn:
            patches[name] = (int(ms.group(1)), int(mn.group(1)))
    return patches


def read_labels(path):
    body = _strip_header(path.read_text())
    o, c = body.index("("), body.rindex(")")
    return np.array([int(x) for x in body[o + 1:c].split()])


def read_internal_scalar(path, ncells):
    seg = path.read_text().split("internalField", 1)[1]
    if "nonuniform" in seg[:40]:
        o, c = seg.index("("), seg.index(")")
        return np.array([float(v) for v in seg[o + 1:c].split()])
    val = float(re.search(r"uniform\s+([-\d.eE+]+)", seg).group(1))
    return np.full(ncells, val)


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main(case, interval):
    mesh = case / "constant" / "polyMesh"
    points = read_points(mesh / "points")
    faces = read_faces(mesh / "faces")
    boundary = read_boundary(mesh / "boundary")
    owner = read_labels(mesh / "owner")
    ncells = owner.max() + 1

    # instantes de tiempo ordenados
    times = sorted((d.name for d in case.iterdir()
                    if d.is_dir() and re.fullmatch(r"\d+(\.\d+)?", d.name)
                    and (d / "T").exists()), key=float)
    print(f"Instantes: {times}")

    # carga T de cada instante
    fields = [read_internal_scalar(case / t / "T", ncells) for t in times]
    vmin = min(f.min() for f in fields)      # escala de color fija (comparable
    vmax = max(f.max() for f in fields)      # entre fotogramas)
    print(f"Rango T global: {vmin:.1f} .. {vmax:.1f} K")

    # triangula el patch frontal una sola vez; guarda la celda de cada triangulo
    start, n = boundary["frontAndBack"]
    tris, tri_cell = [], []
    for f, c in zip(faces[start:start + n], owner[start:start + n]):
        for k in range(1, len(f) - 1):
            tris.append([f[0], f[k], f[k + 1]])
            tri_cell.append(c)
    tris = np.array(tris)
    tri_cell = np.array(tri_cell)
    cmap = get_colormap("hot")

    def colors_for(field):
        norm = (field[tri_cell] - vmin) / (vmax - vmin + 1e-30)
        # forma (N,1): los colormaps 'hot'/'fire' no aceptan el vector plano (N,)
        return cmap.map(norm[:, np.newaxis])

    # --- escena ---
    canvas = scene.SceneCanvas(keys="interactive", bgcolor="white",
                               size=(900, 820), show=True)
    view = canvas.central_widget.add_view()
    view.camera = scene.cameras.PanZoomCamera(aspect=1)

    mesh_vis = scene.visuals.Mesh(vertices=points, faces=tris,
                                  face_colors=colors_for(fields[0]),
                                  parent=view.scene)
    label = scene.visuals.Text(f"t = {times[0]} s", color="black", font_size=14,
                               pos=(0.5, 1.05), parent=view.scene)
    view.camera.set_range()

    # --- animacion ---
    state = {"i": 0}

    def on_timer(event):
        state["i"] = (state["i"] + 1) % len(times)
        i = state["i"]
        mesh_vis.set_data(vertices=points, faces=tris,
                          face_colors=colors_for(fields[i]))
        label.text = f"t = {times[i]} s"
        canvas.update()

    timer = app.Timer(interval=interval, connect=on_timer, start=True)
    app.run()


if __name__ == "__main__":
    args = sys.argv[1:]
    case = Path(args[0]) if args else Path.cwd()
    interval = float(args[1]) if len(args) > 1 else 0.4
    main(case, interval)
