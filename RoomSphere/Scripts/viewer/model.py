"""Modelo de datos del visor: lectura del caso OpenFOAM bajo demanda con caches."""
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pyvista as pv

EXCLUDE = {"C", "Ccx", "Ccy", "Ccz", "vtkValidPointMask", "vtkGhostType"}


class CaseModel:
    """Envuelve el OpenFOAMReader: tiempos, campos por naturaleza y caches LRU.

    Nada se precalcula: cada instante se lee al pedirlo y se retienen los
    ultimos `cache_size` (leccion aprendida: precalcular 1001 cuadros agota
    la RAM). El resampleo a grilla uniforme para volume rendering se cachea
    aparte porque sus arreglos son pequenos.
    """

    def __init__(self, case, cache_size=6, vol_cache_size=150, volume_res=96):
        self.case = Path(case).resolve()
        foam = self.case / f"{self.case.name}.foam"
        if not foam.exists():
            foam.touch()
        self.reader = pv.OpenFOAMReader(str(foam))
        self.reader.cell_to_point_creation = True
        self.times = [float(t) for t in self.reader.time_values]
        self.cache_size = cache_size
        self.vol_cache_size = vol_cache_size
        self.volume_res = volume_res
        self._mesh_cache = OrderedDict()   # t -> internalMesh (+ |vec| derivados)
        self._vol_cache = OrderedDict()    # (t, campo) -> np.ndarray limpio
        self.sphere = None
        self.outline = None

        first = self.load(self.times[0])
        self.bounds = np.array(first.bounds)
        self.center = np.array(first.center)
        self.scalars = [n for n in first.point_data
                        if n not in EXCLUDE and first.point_data[n].ndim == 1]
        self.vectors = [n for n in first.point_data
                        if n not in EXCLUDE and first.point_data[n].ndim == 2]
        if self.sphere is not None:
            b = np.array(self.sphere.bounds)
            self.sphere_c = np.array(self.sphere.center)
            self.sphere_r = float(b[1] - b[0]) / 2
        else:
            self.sphere_c, self.sphere_r = self.center.copy(), 0.0

    def snap(self, t):
        tv = np.asarray(self.times)
        return float(tv[np.argmin(np.abs(tv - float(t)))])

    def load(self, t):
        t = self.snap(t)
        if t in self._mesh_cache:
            self._mesh_cache.move_to_end(t)
            return self._mesh_cache[t]
        self.reader.set_active_time_value(t)
        m = self.reader.read()
        internal = m["internalMesh"]
        internal.cell_data.clear()
        for name in list(internal.point_data.keys()):
            arr = internal.point_data[name]
            if name not in EXCLUDE and arr.ndim == 2 and arr.shape[1] == 3:
                internal[f"|{name}|"] = np.linalg.norm(arr, axis=1)
        if self.outline is None:
            try:
                self.sphere = m["boundary"]["hotSphere"]
            except (KeyError, TypeError):
                self.sphere = None
            self.outline = internal.outline()
        self._mesh_cache[t] = internal
        while len(self._mesh_cache) > self.cache_size:
            self._mesh_cache.popitem(last=False)
        return internal

    def field_range(self, field, t):
        arr = np.asarray(self.load(t)[field])
        if arr.ndim == 2:
            arr = np.linalg.norm(arr, axis=1)
        return float(arr.min()), float(arr.max())

    # ---- volume rendering: resampleo a grilla uniforme ----
    def image_template(self):
        b = self.bounds
        ext = np.array([b[1] - b[0], b[3] - b[2], b[5] - b[4]])
        dims = np.maximum(2, np.round(ext / ext.max() * self.volume_res)).astype(int)
        return pv.ImageData(dimensions=dims, spacing=ext / (dims - 1),
                            origin=(b[0], b[2], b[4]))

    def volume_values(self, t, field):
        """Campo resampleado a la grilla uniforme; puntos fuera del dominio
        (p. ej. el interior de la esfera) toman el minimo valido para que la
        funcion de transferencia los deje transparentes."""
        t = self.snap(t)
        key = (t, field)
        if key in self._vol_cache:
            self._vol_cache.move_to_end(key)
            return self._vol_cache[key]
        sampled = self.image_template().sample(self.load(t))
        ok = np.asarray(sampled["vtkValidPointMask"]).astype(bool)
        vals = np.array(sampled[field], dtype=float)
        vals[~ok] = vals[ok].min() if ok.any() else 0.0
        self._vol_cache[key] = vals
        while len(self._vol_cache) > self.vol_cache_size:
            self._vol_cache.popitem(last=False)
        return vals
