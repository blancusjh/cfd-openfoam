#!/usr/bin/env python
"""
Visualiza la conveccion natural de la esfera caliente en la habitacion.

Corte vertical z~0: temperatura (color) + campo de velocidad (flechas),
mostrando la pluma termica y la recirculacion del aire.

Requiere:  postProcess -func writeCellCentres -time 0
Uso: python Scripts/plot_plume.py [tiempo] [salida.png]   (tiempo por defecto: ultimo)
"""
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri


def _block(path):
    t = path.read_text()
    return t.split("internalField", 1)[1].split("boundaryField", 1)[0]


def read_scalar(path, n):
    s = _block(path)
    if "nonuniform" in s[:40]:
        o = s.index("("); c = s.index(")", o)
        return np.array([float(x) for x in s[o + 1:c].split()])
    return np.full(n, float(re.search(r"uniform\s+([-\d.eE+]+)", s).group(1)))


def read_vectors(path):
    s = _block(path)
    trip = re.findall(r"\(([^()]*)\)", s)
    return np.array([[float(a) for a in t.split()] for t in trip])


def main(case, time, out):
    C = read_vectors(case / "0" / "C")
    n = len(C)
    T = read_scalar(case / time / "T", n)
    U = read_vectors(case / time / "U")

    # corte vertical z ~ 0
    m = np.abs(C[:, 2]) < 0.02
    x, y = C[m, 0], C[m, 1]
    Tm = T[m]
    Ux, Uy = U[m, 0], U[m, 1]
    speed = np.hypot(Ux, Uy)
    print(f"t={time}s  T:{Tm.min():.1f}..{Tm.max():.1f} K  |U|max={speed.max():.3f} m/s")

    # triangulacion enmascarando el agujero de la esfera (circulo r=0.1 en (0,0.3))
    tri = mtri.Triangulation(x, y)
    cx = x[tri.triangles].mean(axis=1)
    cy = y[tri.triangles].mean(axis=1)
    inside = (cx**2 + (cy - 0.3)**2) < 0.105**2
    # tambien enmascara triangulos muy alargados (bordes del dominio/agujero)
    d = lambda i, j: np.hypot(x[tri.triangles[:, i]] - x[tri.triangles[:, j]],
                              y[tri.triangles[:, i]] - y[tri.triangles[:, j]])
    big = np.maximum.reduce([d(0, 1), d(1, 2), d(2, 0)]) > 0.06
    tri.set_mask(inside | big)

    fig, ax = plt.subplots(figsize=(6.2, 9))
    cf = ax.tricontourf(tri, Tm, levels=np.linspace(300, 350, 26), cmap="inferno",
                        extend="both")
    # velocidad: flechas submuestreadas
    s = slice(None, None, 3)
    ax.quiver(x[s], y[s], Ux[s], Uy[s], color="white", scale=6, width=0.003,
              alpha=0.7)
    # dibuja la esfera
    ax.add_patch(plt.Circle((0, 0.3), 0.1, color="gray", zorder=5))
    ax.set_xlim(-0.3, 0.3); ax.set_ylim(0, 1.0); ax.set_aspect("equal")
    ax.set_title(f"Convección natural — esfera caliente\nt = {time} s")
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m] (altura)")
    fig.colorbar(cf, ax=ax, label="T [K]", shrink=0.7)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"figura -> {out}")


if __name__ == "__main__":
    case = Path(".")
    args = sys.argv[1:]
    if args and args[0] not in ("", "."):
        time = args[0]
    else:
        times = sorted((d.name for d in case.iterdir()
                        if d.is_dir() and re.fullmatch(r"\d+(\.\d+)?", d.name)
                        and (d / "T").exists()), key=float)
        time = times[-1]
    out = args[1] if len(args) > 1 else "plume.png"
    main(case, time, out)
