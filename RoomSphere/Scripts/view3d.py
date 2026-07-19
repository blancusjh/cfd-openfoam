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

Representacion de la velocidad (--velocity-representation, en animaciones):
    eulerian   (default) flechas en puntos fijos del corte
    lagrangian           flechas "arrastradas" por el flujo, como trazadores:
                         se siembran en una banda en torno al plano z=0, se
                         advectan con U y se reciclan al salir del dominio o
                         agotar su vida util

Apariencia:
    --background dark|light   fondo oscuro o claro (default: light)
    --cmap NAME               mapa de color de la temperatura (default: inferno);
                              acepta cualquier colormap de matplotlib

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
SPHERE_C = np.array([0.0, 0.3, 0.0])                # centro de la esfera
SPHERE_R = 0.1                                      # radio de la esfera
SEED_LO = np.array([-0.28, 0.02, -0.06])            # banda de siembra en torno a z=0
SEED_HI = np.array([0.28, 0.98, 0.06])
THEMES = {"light": ("white", "black"), "dark": ("#1a1a1a", "white")}
BG, FG = THEMES["light"]                            # tema activo (--background)
CMAP = "inferno"                                    # mapa de color de T (--cmap)


def reader_for(case):
    foam = case / f"{case.name}.foam"
    if not foam.exists():
        foam.touch()
    r = pv.OpenFOAMReader(str(foam))
    r.cell_to_point_creation = True
    return r


def _strip(pd, keep):
    """Deja solo los campos 'keep': cada cuadro precalculado vive en RAM."""
    for name in list(pd.point_data.keys()):
        if name not in keep:
            del pd.point_data[name]
    pd.cell_data.clear()
    return pd


def geometry(mesh):
    """Extrae mallado interno + corte + isosuperficies de un instante."""
    internal = mesh["internalMesh"]
    internal["Umag"] = np.linalg.norm(internal["U"], axis=1)
    internal.set_active_vectors("U")
    sl = _strip(internal.slice(normal="z", origin=(0, 0.3, 0)), ("T", "U", "Umag"))
    iso = _strip(internal.contour(isosurfaces=[304, 309, 315], scalars="T"), ("T",))
    return internal, sl, iso


def _glyph(P, U):
    pts = pv.PolyData(P)
    pts["U"] = U
    pts["Umag"] = np.linalg.norm(U, axis=1)
    pts.set_active_vectors("U")
    return pts.glyph(orient="U", scale="U", factor=0.12)


def glyphs_eulerian(sl):
    # glifos de velocidad: submuestreo por INDICE (~400 flechas).
    # NB: 'tolerance' de glyph fusiona puntos y es ~500x mas lento (2.9 s vs 6 ms).
    P = sl.points
    Up = sl.point_data["U"]                     # datos de PUNTO (longitud = n_points)
    step = max(1, len(P) // 400)
    idx = np.arange(0, len(P), step)
    return _glyph(P[idx], Up[idx])


class LagrangianArrows:
    """Flechas advectadas por el flujo (trazadores) con reciclado de particulas."""

    def __init__(self, n=400, rng_seed=7):
        self.rng = np.random.default_rng(rng_seed)
        self.pts = self._spawn(n)
        self.life = self.rng.integers(20, 45, n)   # cuadros hasta reciclar
        self.age = self.rng.integers(0, 20, n)     # desfase: no reciclar en bloque

    def _spawn(self, n):
        pts = np.empty((0, 3))
        while len(pts) < n:
            cand = self.rng.uniform(SEED_LO, SEED_HI, size=(n, 3))
            cand = cand[np.linalg.norm(cand - SPHERE_C, axis=1) > SPHERE_R + 0.02]
            pts = np.vstack([pts, cand])
        return pts[:n]

    @staticmethod
    def _sample(internal, pts):
        pd = pv.PolyData(pts).sample(internal)
        return np.asarray(pd["U"]), np.asarray(pd["vtkValidPointMask"]).astype(bool)

    def glyphs(self, internal):
        U, _ = self._sample(internal, self.pts)
        return _glyph(self.pts.copy(), U)

    def advect(self, internal, dt):
        """Avanza las particulas x += U dt (Euler con subpasos <= 0.05 s)."""
        nsub = max(1, int(np.ceil(dt / 0.05)))
        for _ in range(nsub):
            U, ok = self._sample(internal, self.pts)
            self.pts += U * (dt / nsub)
            self._recycle(~ok | (np.linalg.norm(self.pts - SPHERE_C, axis=1) < SPHERE_R))
        self.age += 1
        self._recycle(self.age > self.life)

    def _recycle(self, dead):
        if dead.any():
            n = int(dead.sum())
            self.pts[dead] = self._spawn(n)
            self.age[dead] = 0
            self.life[dead] = self.rng.integers(20, 45, n)


def add_frame(p, sl, iso, gl, sphere, outline, t, cam):
    """Redibuja la escena para el instante t, respetando la camara 'cam'."""
    p.clear()
    p.add_mesh(sl, scalars="T", opacity=0.9, clim=CLIM, cmap=CMAP,
               scalar_bar_args=dict(title="T [K]", vertical=True, color=FG))
    if iso.n_points:
        p.add_mesh(iso, scalars="T", clim=CLIM, cmap=CMAP, opacity=0.35,
                   show_scalar_bar=False)
    p.add_mesh(gl, scalars="Umag", cmap="cool", clim=[0, 0.6],
               scalar_bar_args=dict(title="|U| [m/s]", vertical=True, position_x=0.05,
                                    color=FG))
    if sphere is not None:
        p.add_mesh(sphere, color="firebrick", smooth_shading=True)
    p.add_mesh(outline, color=FG)
    p.add_text(f"t = {t:.2f} s", font_size=12, color=FG)
    p.camera_position = cam


def precompute(case, stride, rep="eulerian"):
    """Precalcula la geometria de todos los instantes (para animar fluido)."""
    r = reader_for(case)
    times = list(np.array(r.time_values)[::stride])
    print(f"Precalculando {len(times)} instantes ({rep})...")
    arrows = LagrangianArrows() if rep == "lagrangian" else None
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
        internal, sl, iso = geometry(m)
        if arrows is None:
            gl = glyphs_eulerian(sl)
        else:
            gl = arrows.glyphs(internal)
            if k + 1 < len(times):
                arrows.advect(internal, float(times[k + 1]) - float(t))
        frames.append((float(t), sl, iso, gl))
        if k % 10 == 0:
            print(f"  {k}/{len(times)}")
    return frames, sphere, outline


def live(case, fps, stride, rep="eulerian"):
    frames, sphere, outline = precompute(case, stride, rep)
    p = pv.Plotter(window_size=(1100, 1000))
    p.set_background(BG)

    # actores ESTATICOS (una vez)
    if sphere is not None:
        p.add_mesh(sphere, color="firebrick", smooth_shading=True)
    p.add_mesh(outline, color=FG)

    # actores DINAMICOS: se crean una vez (con el ultimo cuadro, que tiene
    # isosuperficies) y luego solo se les intercambia el dataset -> sin parpadeo
    _, slL, isoL, glL = frames[-1]
    slL.set_active_scalars("T")
    a_sl = p.add_mesh(slL, scalars="T", opacity=0.9, clim=CLIM, cmap=CMAP,
                      scalar_bar_args=dict(title="T [K]", vertical=True, color=FG))
    isoL.set_active_scalars("T")
    a_iso = p.add_mesh(isoL, scalars="T", clim=CLIM, cmap=CMAP, opacity=0.35,
                       show_scalar_bar=False)
    glL.set_active_scalars("Umag")
    a_gl = p.add_mesh(glL, scalars="Umag", cmap="cool", clim=[0, 0.6],
                      scalar_bar_args=dict(title="|U| [m/s]", vertical=True,
                                           position_x=0.05, color=FG))
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
                           color=FG, render=False)
                p.render()                       # fuerza el redibujo tras el swap
                p.update()                       # procesa eventos (rotacion del raton)
                _time.sleep(1.0 / fps)
    except (RuntimeError, KeyboardInterrupt):
        pass


def save(case, out, fps, stride, rep="eulerian"):
    frames, sphere, outline = precompute(case, stride, rep)
    p = pv.Plotter(off_screen=True, window_size=(880, 820))
    p.set_background(BG)
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
    p.set_background(BG)
    m = r.read()
    sphere = m["boundary"]["hotSphere"] if "hotSphere" in m["boundary"].keys() else None
    internal, sl, iso = geometry(m)
    add_frame(p, sl, iso, glyphs_eulerian(sl), sphere, internal.outline(), tt, CAM)
    (p.screenshot(out), print(f"captura -> {out}")) if out else p.show()


def _pop_flag(a, flag, default, valid=None):
    v = default
    if flag in a:
        i = a.index(flag)
        if i + 1 >= len(a):
            sys.exit(f"{flag} requiere un valor"
                     + (f": {' | '.join(valid)}" if valid else ""))
        v = a[i + 1]
        del a[i:i + 2]
    if valid is not None and v not in valid:
        sys.exit(f"{flag} invalida: '{v}' ({' | '.join(valid)})")
    return v


if __name__ == "__main__":
    case = Path(".").resolve()
    a = sys.argv[1:]
    rep = _pop_flag(a, "--velocity-representation", "eulerian",
                    ("eulerian", "lagrangian"))
    BG, FG = THEMES[_pop_flag(a, "--background", "light", tuple(THEMES))]
    CMAP = _pop_flag(a, "--cmap", "inferno")
    from matplotlib import colormaps
    if CMAP not in colormaps:
        sys.exit(f"--cmap invalido: '{CMAP}' no es un colormap de matplotlib "
                 "(prueba: inferno, viridis, plasma, magma, coolwarm, turbo)")
    if "--still" in a:
        i = a.index("--still")
        still(case, a[i + 1], a[i + 2] if len(a) > i + 2 else "view3d.png")
    elif "--save" in a:
        rest = [x for x in a if x != "--save"]
        out = rest[0] if rest else "plume3d.gif"
        fps = float(rest[1]) if len(rest) > 1 else 15
        stride = int(rest[2]) if len(rest) > 2 else 3
        save(case, out, fps, stride, rep)
    else:                                    # por defecto: interactiva animada
        fps = float(a[0]) if a else 12
        stride = int(a[1]) if len(a) > 1 else 3
        live(case, fps, stride, rep)
