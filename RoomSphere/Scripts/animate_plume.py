#!/usr/bin/env python
"""
Anima (GIF) la conveccion natural: corte z~0 con T (color) + velocidad (flechas).

Requiere:  postProcess -func writeCellCentres -time 0
Uso: python Scripts/animate_plume.py [salida.gif] [fps]
"""
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from PIL import Image


def _block(path):
    return path.read_text().split("internalField", 1)[1].split("boundaryField", 1)[0]


def read_scalar(path, n):
    s = _block(path)
    if "nonuniform" in s[:40]:
        o = s.index("("); c = s.index(")", o)
        return np.array([float(x) for x in s[o + 1:c].split()])
    return np.full(n, float(re.search(r"uniform\s+([-\d.eE+]+)", s).group(1)))


def read_vectors(path, n=None):
    s = _block(path)
    trip = re.findall(r"\(([^()]*)\)", s)
    arr = np.array([[float(a) for a in t.split()] for t in trip])
    if n is not None and "nonuniform" not in s[:40]:   # campo uniforme -> expandir
        return np.tile(arr[0], (n, 1))
    return arr


def main(out, fps):
    case = Path(".")
    C = read_vectors(case / "0" / "C")
    n = len(C)
    m = np.abs(C[:, 2]) < 0.02
    x, y = C[m, 0], C[m, 1]

    times = sorted((d.name for d in case.iterdir()
                    if d.is_dir() and re.fullmatch(r"\d+(\.\d+)?", d.name)
                    and (d / "T").exists()), key=float)
    print(f"{len(times)} instantes -> {out}")

    # triangulacion + mascara (una sola vez: la malla no cambia)
    tri = mtri.Triangulation(x, y)
    cx = x[tri.triangles].mean(axis=1); cy = y[tri.triangles].mean(axis=1)
    inside = (cx**2 + (cy - 0.3)**2) < 0.105**2
    d = lambda i, j: np.hypot(x[tri.triangles[:, i]] - x[tri.triangles[:, j]],
                              y[tri.triangles[:, i]] - y[tri.triangles[:, j]])
    big = np.maximum.reduce([d(0, 1), d(1, 2), d(2, 0)]) > 0.06
    tri.set_mask(inside | big)

    levels = np.linspace(300, 350, 26)
    s = slice(None, None, 3)
    fig, ax = plt.subplots(figsize=(6.2, 9))
    T0 = read_scalar(case / times[0] / "T", n)[m]
    cf = ax.tricontourf(tri, T0, levels=levels, cmap="inferno", extend="both")
    fig.colorbar(cf, ax=ax, label="T [K]", shrink=0.7)

    # renderiza cada cuadro y lo acumula como imagen PIL
    frames = []
    for k, t in enumerate(times):
        ax.clear()
        T = read_scalar(case / t / "T", n)[m]
        U = read_vectors(case / t / "U", n)[m]
        ax.tricontourf(tri, T, levels=levels, cmap="inferno", extend="both")
        ax.quiver(x[s], y[s], U[s, 0], U[s, 1], color="white",
                  scale=8, width=0.003, alpha=0.7)
        ax.add_patch(plt.Circle((0, 0.3), 0.1, color="gray", zorder=5))
        ax.set_xlim(-0.3, 0.3); ax.set_ylim(0, 1.0); ax.set_aspect("equal")
        ax.set_title(f"Convección natural — esfera caliente\nt = {float(t):.2f} s")
        ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]")
        fig.canvas.draw()
        frames.append(Image.fromarray(
            np.asarray(fig.canvas.buffer_rgba())).convert("RGB"))
        if k % 20 == 0:
            print(f"  cuadro {k}/{len(times)}")

    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=int(1000 / fps), loop=0)
    print(f"listo: {out} ({len(frames)} cuadros)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "plume.gif"
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 12
    main(out, fps)
