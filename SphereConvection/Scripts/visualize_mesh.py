#!/usr/bin/env python
"""
Visualiza una malla de OpenFOAM (constant/polyMesh) con VisPy.

Dibuja:
  - el mallado completo como wireframe gris  (geometria + volumen + celdas)
  - cada patch de frontera relleno con un color  (las 'caras' con nombre)

Uso:
    python visualize_mesh.py [ruta_del_caso]
    (por defecto usa el directorio actual; ejecutalo desde la carpeta del caso)
"""
import re
import sys
from pathlib import Path

import numpy as np
from vispy import scene, app


# ----------------------------------------------------------------------
# 1) PARSERS del formato de texto de OpenFOAM
# ----------------------------------------------------------------------
def _strip_header(text: str) -> str:
    """Quita el bloque FoamFile { ... } inicial y devuelve solo los datos."""
    return text.split("}", 1)[1]


def read_points(path: Path) -> np.ndarray:
    """points -> array (Npuntos, 3)."""
    body = _strip_header(path.read_text())
    # cada punto es '(x y z)'; [^()]* captura el interior sin parentesis
    trips = re.findall(r"\(([^()]*)\)", body)
    n = int(re.search(r"(\d+)\s*\(", body).group(1))
    trips = trips[:n]
    return np.array([[float(v) for v in t.split()] for t in trips])


def read_faces(path: Path) -> list[list[int]]:
    """faces -> lista de caras, cada una es una lista de indices de puntos."""
    body = _strip_header(path.read_text())
    # cada cara es 'n(i0 i1 i2 ...)'; capturamos el interior de cada parentesis
    inner = re.findall(r"\(([^()]*)\)", body)
    return [[int(i) for i in grp.split()] for grp in inner if grp.strip()]


def read_boundary(path: Path) -> dict:
    """boundary -> {nombre: (startFace, nFaces)}."""
    text = path.read_text()
    patches = {}
    for name, block in re.findall(r"(\w+)\s*\{([^}]*)\}", text):
        m_start = re.search(r"startFace\s+(\d+)", block)
        m_n = re.search(r"nFaces\s+(\d+)", block)
        if m_start and m_n:
            patches[name] = (int(m_start.group(1)), int(m_n.group(1)))
    return patches


# ----------------------------------------------------------------------
# 2) GEOMETRIA -> primitivas para VisPy
# ----------------------------------------------------------------------
def face_edges(points, faces):
    """Segmentos de linea (2*Nedges, 3) con las aristas de TODAS las caras."""
    segs = []
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):     # cierra el poligono
            segs.append(points[a])
            segs.append(points[b])
    return np.array(segs)


def triangulate(points, faces_subset):
    """Triangula un abanico cada cara (quad -> 2 triangulos) para rellenar."""
    tris = []
    for f in faces_subset:
        for k in range(1, len(f) - 1):
            tris.append([f[0], f[k], f[k + 1]])
    return np.array(tris)


# ----------------------------------------------------------------------
# 3) MAIN
# ----------------------------------------------------------------------
def main(case_dir: Path):
    mesh_dir = case_dir / "constant" / "polyMesh"
    points = read_points(mesh_dir / "points")
    faces = read_faces(mesh_dir / "faces")
    boundary = read_boundary(mesh_dir / "boundary")

    print(f"Puntos : {len(points)}")
    print(f"Caras  : {len(faces)}")
    print(f"Patches: {', '.join(boundary)}")

    # --- escena VisPy ---
    canvas = scene.SceneCanvas(keys="interactive", bgcolor="white",
                               size=(1000, 800), show=True)
    view = canvas.central_widget.add_view()
    view.camera = scene.cameras.TurntableCamera(fov=30, azimuth=-60, elevation=25)

    # wireframe de toda la malla (gris)
    scene.visuals.Line(pos=face_edges(points, faces), connect="segments",
                       color=(0.4, 0.4, 0.4, 0.6), width=1, parent=view.scene)

    # cada patch relleno de un color
    colors = {"left": (0.85, 0.2, 0.2, 0.9),        # rojo  (sera el borde caliente)
              "right": (0.2, 0.4, 0.9, 0.9),        # azul  (sera el borde frio)
              "topAndBottom": (0.2, 0.7, 0.3, 0.7), # verde (aislados)
              "frontAndBack": (0.8, 0.8, 0.8, 0.15)}# gris casi transparente (caras 2D)
    for name, (start, n) in boundary.items():
        sub = faces[start:start + n]
        tris = triangulate(points, sub)
        col = colors.get(name, (0.6, 0.6, 0.6, 0.5))
        scene.visuals.Mesh(vertices=points, faces=tris, color=col,
                           parent=view.scene)
        print(f"  patch '{name}': {n} caras -> color {col[:3]}")

    view.camera.set_range()
    app.run()


if __name__ == "__main__":
    case = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    main(case)
