# Computación con OpenFOAM

Casos de estudio resueltos con **OpenFOAM 13**, en orden creciente de complejidad:
de la difusión pura de calor a la convección natural tridimensional.

## Casos

| Caso | Físico | Solver | Descripción |
|------|--------|--------|-------------|
| [`HeatEquation`](HeatEquation/) | Difusión pura | `laplacianFoam` | Ecuación del calor $\partial_t T = \alpha\,\nabla^2 T$ en un dominio simple. |
| [`SphereConvection`](SphereConvection/) | Difusión con fuente | `laplacianFoam` | Difusión térmica alrededor de una esfera caliente ($\tau = R^2/\alpha \approx 500$ s). |
| [`RoomSphere`](RoomSphere/) | Convección natural | `fluid` (Boussinesq) | Pluma térmica de una esfera caliente en una habitación (régimen laminar, $t_f = 30$ s). |

## Estructura de cada caso

```
<caso>/
├── 0/           # condiciones iniciales y de contorno
├── constant/    # propiedades físicas (malla polyMesh se regenera)
├── system/      # blockMeshDict, controlDict, fvSchemes, fvSolution
└── Scripts/     # post-proceso y visualización (Python + vispy/matplotlib)
```

## Reproducir un caso

```bash
cd <caso>
blockMesh                 # genera la malla base
# snappyHexMesh -overwrite  (solo RoomSphere)
foamRun                   # o el solver indicado en controlDict
```

Los directorios de tiempo (`1/`, `2/`, ...), las mallas generadas y el entorno
virtual de Python quedan fuera del control de versiones (ver `.gitignore`).
