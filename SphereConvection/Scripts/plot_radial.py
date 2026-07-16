#!/usr/bin/env python
"""
Verifica y visualiza el enfriamiento de la esfera (laplacianFoam + BC convectiva).

Genera una figura con:
  (izq)  perfiles radiales T(r) en varios instantes
  (der)  corte z~0 de la esfera coloreado por T en un instante

Uso: python Scripts/plot_radial.py [caso] [salida.png]
"""
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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


def main(case, out):
    C = read_vectors(case / "0" / "C")          # centros de celda (Ncells,3)
    r = np.linalg.norm(C, axis=1)               # radio de cada celda
    ncells = len(r)
    R = r.max()

    times = sorted((d.name for d in case.iterdir()
                    if d.is_dir() and re.fullmatch(r"\d+(\.\d+)?", d.name)
                    and (d / "T").exists()), key=float)

    Tinf, T0, Kc = 293.0, 573.0, 50.0
    print(f"Ncells={ncells}  R={R:.4f} m  Bi = Kc*R = {Kc*R:.1f}")

    # --- verificacion numerica: centro vs superficie en el tiempo ---
    icenter = np.argmin(r)
    surf = r > 0.95 * R
    print(f"{'t[s]':>6} {'T_centro':>9} {'T_superf':>9} {'T_media':>8}")
    for t in times[::10]:
        T = read_scalar(case / t / "T", ncells)
        print(f"{float(t):6.0f} {T[icenter]:9.1f} {T[surf].mean():9.1f} {T.mean():8.1f}")

    # --- figura ---
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))

    # (izq) perfiles radiales, promediados en cascarones
    bins = np.linspace(0, R, 25)
    rc = 0.5 * (bins[:-1] + bins[1:])
    # 5 instantes repartidos por toda la simulacion (0 .. tmax)
    tmax = float(times[-1])
    sel = [min(times, key=lambda t: abs(float(t) - frac * tmax))
           for frac in (0.0, 0.1, 0.3, 0.6, 1.0)]
    cmap = plt.cm.inferno
    for t in sel:
        T = read_scalar(case / t / "T", ncells)
        prof = [T[m].mean() if (m := (r >= bins[i]) & (r < bins[i + 1])).any() else np.nan
                for i in range(len(bins) - 1)]
        axL.plot(rc / R, prof, "-o", ms=3, color=cmap(float(t) / tmax),
                 label=f"t = {float(t):.0f} s")
    axL.axhline(Tinf, ls="--", c="gray", lw=1, label=r"$T_\infty$")
    axL.set_xlabel("r / R  (0 = centro, 1 = superficie)")
    axL.set_ylabel("T [K]")
    axL.set_title(f"Perfil radial de T  (Bi = {Kc*R:.0f})")
    axL.legend(fontsize=8); axL.grid(alpha=0.3)

    # (der) corte z ~ 0 en el instante de MAYOR gradiente interno (mas ilustrativo)
    icenter2 = np.argmin(r)
    surf2 = r > 0.95 * R
    grad = {t: read_scalar(case / t / "T", ncells)[icenter2]
               - read_scalar(case / t / "T", ncells)[surf2].mean() for t in times}
    t_slice = max(grad, key=grad.get)
    T = read_scalar(case / t_slice / "T", ncells)
    zmask = np.abs(C[:, 2]) < 0.012
    sc = axR.scatter(C[zmask, 0], C[zmask, 1], c=T[zmask], cmap="inferno",
                     s=60, vmin=Tinf, vmax=T0)
    axR.set_aspect("equal"); axR.set_title(f"Corte z~0,  t = {t_slice} s")
    axR.set_xlabel("x [m]"); axR.set_ylabel("y [m]")
    fig.colorbar(sc, ax=axR, label="T [K]")

    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(f"figura -> {out}")


if __name__ == "__main__":
    case = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    out = sys.argv[2] if len(sys.argv) > 2 else "radial.png"
    main(case, out)
