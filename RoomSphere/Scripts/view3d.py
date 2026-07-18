#!/usr/bin/env python
"""
Visualizacion 3D ANIMADA de la conveccion natural con PyVista.

Escena: esfera caliente + corte de TEMPERATURA (mapa escalar) + isosuperficies
3D de la pluma + glifos de VELOCIDAD (vectores de flujo) coloreados por rapidez.

Uso:
    python Scripts/view3d.py                 -> ventana 3D interactiva ANIMADA (rotable)
    python Scripts/view3d.py 12 2            -> interactiva, fps=12, 1 de cada 2 instantes
    python Scripts/view3d.py --save          -> guarda GIF (plume3d.gif)
    python Scripts/view3d.py --save out.gif 15 3
    python Scripts/view3d.py --still 20 img.png   -> una sola imagen en t=20 s

La generacion del GIF es OPCIONAL (flag --save); por defecto se anima en pantalla.
"""
import sys
import time as _time
from pathlib import Path

import numpy as np
import pyvista as pv
from PIL import Image

CLIM = [300, 322]                                   # rango util de T
CAM = [(1.4, 1.1, 1.4), (0, 0.45, 0), (0, 1, 0)]    # camara inicial


def reader_for(case):
    foam = case / f"{case.name}.foam"
    if not foam.exists():
        foam.touch()
    r = pv.OpenFOAMReader(str(foam))
    r.cell_to_point_creation = True
    return r


def geometry(mesh):
    """Extrae corte + isosuperficies + glifos para un instante (polydata autonomo)."""
    internal = mesh["internalMesh"]
    internal["Umag"] = np.linalg.norm(internal["U"], axis=1)
    internal.set_active_vectors("U")
    sl = internal.slice(normal="z", origin=(0, 0.3, 0))
    iso = internal.contour(isosurfaces=[304, 309, 315], scalars="T")

    # glifos de velocidad: submuestreo por INDICE (~400 flechas).
    # NB: 'tolerance' de glyph fusiona puntos y es ~500x mas lento (2.9 s vs 6 ms).
    P = sl.points
    Up = sl.point_data["U"]                     # datos de PUNTO (longitud = n_points)
    Umag = sl.point_data.get("Umag", np.linalg.norm(Up, axis=1))
    step = max(1, len(P) // 400)
    idx = np.arange(0, len(P), step)
    pts = pv.PolyData(P[idx])
    pts["U"] = Up[idx]
    pts["Umag"] = Umag[idx]
    pts.set_active_vectors("U")
    gl = pts.glyph(orient="U", scale="U", factor=0.12)
    return sl, iso, gl


def add_frame(p, sl, iso, gl, sphere, outline, t, cam):
    """Redibuja la escena para el instante t, respetando la camara 'cam'."""
    p.clear()
    p.add_mesh(sl, scalars="T", opacity=0.9, clim=CLIM, cmap="inferno",
               scalar_bar_args=dict(title="T [K]", vertical=True))
    if iso.n_points:
        p.add_mesh(iso, scalars="T", clim=CLIM, cmap="inferno", opacity=0.35,
                   show_scalar_bar=False)
    p.add_mesh(gl, scalars="Umag", cmap="cool", clim=[0, 0.6],
               scalar_bar_args=dict(title="|U| [m/s]", vertical=True, position_x=0.05))
    if sphere is not None:
        p.add_mesh(sphere, color="firebrick", smooth_shading=True)
    p.add_mesh(outline, color="black")
    p.add_text(f"t = {t:.2f} s", font_size=12, color="black")
    p.camera_position = cam


def precompute(case, stride):
    """Precalcula la geometria de todos los instantes (para animar fluido)."""
    r = reader_for(case)
    times = list(np.array(r.time_values)[::stride])
    print(f"Precalculando {len(times)} instantes...")
    frames, sphere, outline = [], None, None
    for k, t in enumerate(times):
        r.set_active_time_value(float(t))
        m = r.read()
        if sphere is None:
            try:
                sphere = m["boundary"]["hotSphere"]
            except Exception:
                sphere = None
            outline = m["internalMesh"].outline()
        frames.append((float(t), *geometry(m)))
        if k % 10 == 0:
            print(f"  {k}/{len(times)}")
    return frames, sphere, outline


def live(case, fps, stride):
    frames, sphere, outline = precompute(case, stride)
    p = pv.Plotter(window_size=(1100, 1000))
    p.set_background("white")

    # actores ESTATICOS (una vez)
    if sphere is not None:
        p.add_mesh(sphere, color="firebrick", smooth_shading=True)
    p.add_mesh(outline, color="black")

    # actores DINAMICOS: se crean una vez (con el ultimo cuadro, que tiene
    # isosuperficies) y luego solo se les intercambia el dataset -> sin parpadeo
    _, slL, isoL, glL = frames[-1]
    slL.set_active_scalars("T")
    a_sl = p.add_mesh(slL, scalars="T", opacity=0.9, clim=CLIM, cmap="inferno",
                      scalar_bar_args=dict(title="T [K]", vertical=True))
    isoL.set_active_scalars("T")
    a_iso = p.add_mesh(isoL, scalars="T", clim=CLIM, cmap="inferno", opacity=0.35,
                       show_scalar_bar=False)
    glL.set_active_scalars("Umag")
    a_gl = p.add_mesh(glL, scalars="Umag", cmap="cool", clim=[0, 0.6],
                      scalar_bar_args=dict(title="|U| [m/s]", vertical=True,
                                           position_x=0.05))
    p.camera_position = CAM
    empty = pv.PolyData()

    print("Ventana interactiva: arrastra para rotar; se anima en bucle. Cierra para salir.")
    p.show(interactive_update=True, auto_close=False)
    try:
        while not getattr(p, "_closed", False):
            for t, sl, iso, gl in frames:
                if getattr(p, "_closed", False):
                    break
                sl.set_active_scalars("T")
                a_sl.mapper.dataset = sl
                if iso.n_points:
                    iso.set_active_scalars("T")
                a_iso.mapper.dataset = iso if iso.n_points else empty
                gl.set_active_scalars("Umag")
                a_gl.mapper.dataset = gl
                p.add_text(f"t = {t:.2f} s", name="tt", font_size=12,
                           color="black", render=False)
                p.render()                       # fuerza el redibujo tras el swap
                p.update()                       # procesa eventos (rotacion del raton)
                _time.sleep(1.0 / fps)
    except (RuntimeError, KeyboardInterrupt):
        pass


def save(case, out, fps, stride):
    frames, sphere, outline = precompute(case, stride)
    p = pv.Plotter(off_screen=True, window_size=(880, 820))
    p.set_background("white")
    imgs = []
    for t, sl, iso, gl in frames:
        add_frame(p, sl, iso, gl, sphere, outline, t, CAM)
        imgs.append(Image.fromarray(p.screenshot(return_img=True)))
    p.close()
    imgs[0].save(out, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / fps), loop=0)
    print(f"listo: {out} ({len(imgs)} cuadros)")


def still(case, t, out):
    r = reader_for(case)
    tv = np.array(r.time_values)
    tt = float(tv[np.argmin(np.abs(tv - float(t)))])
    r.set_active_time_value(tt)
    p = pv.Plotter(off_screen=bool(out), window_size=(1100, 1000))
    p.set_background("white")
    m = r.read()
    sphere = m["boundary"]["hotSphere"] if "hotSphere" in m["boundary"].keys() else None
    add_frame(p, *geometry(m), sphere, m["internalMesh"].outline(), tt, CAM)
    (p.screenshot(out), print(f"captura -> {out}")) if out else p.show()


if __name__ == "__main__":
    case = Path(".").resolve()
    a = sys.argv[1:]
    if "--still" in a:
        i = a.index("--still")
        still(case, a[i + 1], a[i + 2] if len(a) > i + 2 else "view3d.png")
    elif "--save" in a:
        rest = [x for x in a if x != "--save"]
        out = rest[0] if rest else "plume3d.gif"
        fps = float(rest[1]) if len(rest) > 1 else 15
        stride = int(rest[2]) if len(rest) > 2 else 3
        save(case, out, fps, stride)
    else:                                    # por defecto: interactiva animada
        fps = float(a[0]) if a else 12
        stride = int(a[1]) if len(a) > 1 else 3
        live(case, fps, stride)
