"""Representaciones del visor: una estrategia por forma de visualizar un campo.

Cada representacion crea sus actores en build(), rehace la geometria del
instante/parametros actuales en update() (intercambiando el dataset del mapper,
sin parpadeo) y se quita en remove(). El objeto `viewer` provee el estado
compartido: plotter, model, internal (malla del instante actual), campo
escalar/vectorial activos, clims, cmap, params y el plano (theta, phi, d).
"""
import numpy as np
import pyvista as pv


def plane_normal(theta, phi):
    """Normal del plano: theta desde la vertical +y, phi azimutal de +x a +z."""
    th, ph = np.radians(theta), np.radians(phi)
    return np.array([np.sin(th) * np.cos(ph), np.cos(th), np.sin(th) * np.sin(ph)])


def normal_to_angles(n):
    n = np.asarray(n, dtype=float)
    n = n / np.linalg.norm(n)
    theta = np.degrees(np.arccos(np.clip(n[1], -1, 1)))
    phi = np.degrees(np.arctan2(n[2], n[0])) % 360
    return theta, phi


def _glyph(P, U, factor):
    pts = pv.PolyData(np.asarray(P))
    pts["vec"] = np.asarray(U)
    pts["mag"] = np.linalg.norm(U, axis=1)
    pts.set_active_vectors("vec")
    return pts.glyph(orient="vec", scale="vec", factor=factor)


class Representation:
    def __init__(self, viewer):
        self.v = viewer
        self.actor = None
        self.enabled = False

    def set_enabled(self, on):
        self.enabled = bool(on)
        if on:
            self.build()
        else:
            self.remove()
        self.v.plotter.render()

    def remove(self):
        if self.actor is not None:
            self.v.plotter.remove_actor(self.actor)
            self.actor = None

    def rebuild(self):
        if self.enabled:
            self.remove()
            self.build()

    def refresh(self):
        """Al cambiar el tiempo o la geometria (no las propiedades del actor)."""
        if not self.enabled:
            return
        if self.actor is None:
            self.build()
        else:
            self.update()

    def _swap(self, dataset, scalars):
        if dataset.n_points and scalars in dataset.point_data:
            dataset.set_active_scalars(scalars)
            self.actor.mapper.dataset = dataset
        else:
            self.actor.mapper.dataset = pv.PolyData()


# ---------- representaciones de campos ESCALARES ----------

class SliceRep(Representation):
    def dataset(self):
        v = self.v
        return v.internal.slice(normal=v.plane_n(), origin=v.plane_o())

    def build(self):
        v = self.v
        ds = self.dataset()
        if ds.n_points == 0:
            return
        self.actor = v.plotter.add_mesh(
            ds, scalars=v.scalar_field, cmap=v.cmap, clim=v.scalar_clim,
            opacity=v.params["slice_opacity"],
            scalar_bar_args=v.sbar(v.scalar_field))

    def update(self):
        self._swap(self.dataset(), self.v.scalar_field)


class IsoRep(Representation):
    def values(self):
        v = self.v
        n, val = v.params["iso_n"], v.params["iso_value"]
        hi = v.scalar_clim[1]
        return [val] if n == 1 else list(np.linspace(val, hi, n + 1)[:-1])

    def dataset(self):
        v = self.v
        return v.internal.contour(isosurfaces=self.values(), scalars=v.scalar_field)

    def build(self):
        v = self.v
        ds = self.dataset()
        if ds.n_points == 0:
            return
        self.actor = v.plotter.add_mesh(
            ds, scalars=v.scalar_field, cmap=v.cmap, clim=v.scalar_clim,
            opacity=v.params["iso_opacity"], scalar_bar_args=v.sbar(v.scalar_field))

    def update(self):
        self._swap(self.dataset(), self.v.scalar_field)


class ClipRep(Representation):
    def dataset(self):
        v = self.v
        return v.internal.clip(normal=v.plane_n(), origin=v.plane_o())

    def build(self):
        v = self.v
        ds = self.dataset()
        if ds.n_points == 0:
            return
        self.actor = v.plotter.add_mesh(
            ds, scalars=v.scalar_field, cmap=v.cmap, clim=v.scalar_clim,
            scalar_bar_args=v.sbar(v.scalar_field))

    def update(self):
        self._swap(self.dataset(), self.v.scalar_field)


class VolumeRep(Representation):
    """Volume rendering sobre una grilla uniforme resampleada del caso.

    El actor conserva SIEMPRE la misma grilla; en cada instante solo se
    reasigna el arreglo escalar (dispara Modified y el mapper se actualiza).
    """

    def build(self):
        v = self.v
        self.field = v.scalar_field
        self.grid = v.model.image_template()
        self.grid[self.field] = v.model.volume_values(v.t, self.field)
        self.grid.set_active_scalars(self.field)
        self.actor = v.plotter.add_volume(
            self.grid, scalars=self.field, cmap=v.cmap, clim=v.scalar_clim,
            opacity=v.params["vol_preset"],
            opacity_unit_distance=v.params["vol_unit"],
            shade=False, scalar_bar_args=v.sbar(self.field))

    def update(self):
        v = self.v
        if v.scalar_field != self.field:
            self.rebuild()
            return
        self.grid[self.field] = v.model.volume_values(v.t, self.field)


# ---------- representaciones de campos VECTORIALES ----------

class GlyphRep(Representation):
    """Flechas eulerianas: puntos fijos sobre el plano de corte."""

    def dataset(self):
        v = self.v
        sl = v.internal.slice(normal=v.plane_n(), origin=v.plane_o())
        if sl.n_points == 0:
            return pv.PolyData()
        P = sl.points
        U = np.asarray(sl.point_data[v.vector_field])
        step = max(1, len(P) // v.params["glyph_n"])
        idx = np.arange(0, len(P), step)
        return _glyph(P[idx], U[idx], v.params["glyph_factor"])

    def build(self):
        v = self.v
        ds = self.dataset()
        if ds.n_points == 0:
            return
        self.actor = v.plotter.add_mesh(
            ds, scalars="mag", cmap=v.params["vec_cmap"], clim=v.vector_clim,
            scalar_bar_args=v.sbar(f"|{v.vector_field}|", left=True))

    def update(self):
        self._swap(self.dataset(), "mag")


class TracerRep(GlyphRep):
    """Flechas lagrangianas: trazadores advectados por el flujo con reciclado.

    En playback secuencial el visor llama a advect(dt); al saltar en el tiempo
    (scrub) solo se re-muestrea la velocidad en las posiciones actuales.
    """

    def __init__(self, viewer):
        super().__init__(viewer)
        self.rng = np.random.default_rng(7)
        self.pts = self.life = self.age = None

    def _seed_box(self):
        b = self.v.model.bounds
        ext = b[1::2] - b[::2]
        return b[::2] + 0.03 * ext, b[1::2] - 0.03 * ext

    def _spawn(self, n):
        lo, hi = self._seed_box()
        m = self.v.model
        pts = np.empty((0, 3))
        while len(pts) < n:
            cand = self.rng.uniform(lo, hi, size=(max(n, 8), 3))
            if m.sphere_r:
                cand = cand[np.linalg.norm(cand - m.sphere_c, axis=1)
                            > m.sphere_r + 0.02]
            pts = np.vstack([pts, cand])
        return pts[:n]

    def _ensure(self):
        n = self.v.params["tracer_n"]
        if self.pts is None or len(self.pts) != n:
            self.pts = self._spawn(n)
            self.life = self.rng.integers(20, 45, n)
            self.age = self.rng.integers(0, 20, n)

    def _sample(self):
        pd = pv.PolyData(self.pts).sample(self.v.internal)
        return (np.asarray(pd[self.v.vector_field]),
                np.asarray(pd["vtkValidPointMask"]).astype(bool))

    def dataset(self):
        self._ensure()
        U, _ = self._sample()
        return _glyph(self.pts.copy(), U, self.v.params["glyph_factor"])

    def advect(self, dt):
        if not self.enabled:
            return
        self._ensure()
        m = self.v.model
        nsub = max(1, int(np.ceil(dt / 0.05)))
        for _ in range(nsub):
            U, ok = self._sample()
            self.pts += U * (dt / nsub)
            dead = ~ok
            if m.sphere_r:
                dead |= np.linalg.norm(self.pts - m.sphere_c, axis=1) < m.sphere_r
            self._recycle(dead)
        self.age += 1
        self._recycle(self.age > self.life)

    def _recycle(self, dead):
        if dead.any():
            n = int(dead.sum())
            self.pts[dead] = self._spawn(n)
            self.age[dead] = 0
            self.life[dead] = self.rng.integers(20, 45, n)


class StreamRep(Representation):
    """Streamlines integradas desde una fuente esferica alrededor de la esfera."""

    def dataset(self):
        v, m = self.v, self.v.model
        s = v.internal.streamlines(
            vectors=v.vector_field, n_points=v.params["stream_n"],
            source_center=tuple(m.sphere_c),
            source_radius=(m.sphere_r or 0.05) + 0.05,
            integration_direction="both", max_length=3.0)
        if s.n_points == 0:
            return pv.PolyData()
        s["mag"] = np.linalg.norm(np.asarray(s[v.vector_field]), axis=1)
        return s.tube(radius=v.params["stream_tube"])

    def build(self):
        v = self.v
        ds = self.dataset()
        if ds.n_points == 0:
            return
        self.actor = v.plotter.add_mesh(
            ds, scalars="mag", cmap=v.params["vec_cmap"], clim=v.vector_clim,
            scalar_bar_args=v.sbar(f"|{v.vector_field}|", left=True))

    def update(self):
        self._swap(self.dataset(), "mag")
