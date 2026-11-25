"""Visualización de una pose: cuadrícula con cada paso del proceso y ventana 3D de la reconstrucción.

Ventana 1 (cuadrícula):
    franja V (paso 0) | franja H (paso 0) | bit Gray V | textura (blanco)
    fase relativa X   | fase relativa Y   | orden de franja k X | modulación X
    fase absoluta Fx  | fase absoluta Fy  | máscara válida      | profundidad Z
Ventana 2: nube de puntos 3D (submuestreada) coloreada por profundidad o por textura.

Usa los resultados de las etapas organizar, fase_relativa, fase_absoluta y reconstruccion.

Ejemplo:
    .env/bin/python visualizacion.py          # usa los valores de la sección de abajo
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import configuracion as cfg
import fase

# ==============================================================================
# --- PARÁMETROS (EDITA AQUÍ) ---
# ==============================================================================
CATEGORIA = "objeto"         # "patron", "plano" u "objeto"
POSE = "ultima"              # "ultima" (la pose más reciente) o un nombre como "pose_00"
PUNTOS_MAX_3D = 80_000       # submuestreo para que la ventana 3D sea fluida
COLOR_3D = "profundidad"     # "profundidad" o "textura"
GUARDAR_FIGURAS = True       # guarda también los .png en resultados/visualizacion/
# ==============================================================================


def _leer_franja(dir_pose: Path, orientacion: str, indice: int) -> np.ndarray:
    return fase.leer_gris(fase.buscar_imagen_patron(dir_pose / orientacion / cfg.PREFIJO_ORDENADAS, indice))


def _panel(ax, imagen, titulo, cmap="gray", mascara=None, barra=True, rango=None):
    datos = np.asarray(imagen, dtype=np.float64)
    if mascara is not None:
        datos = np.where(mascara, datos, np.nan)
    vmin, vmax = rango if rango else (None, None)
    if rango is None and np.any(np.isfinite(datos)) and cmap != "gray":
        vmin, vmax = np.nanpercentile(datos, [1, 99])
    im = ax.imshow(datos, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_title(titulo, fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    if barra:
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.02)


def visualizar_pose(
    categoria: str = CATEGORIA,
    pose: str = POSE,
    puntos_max: int = PUNTOS_MAX_3D,
    color_3d: str = COLOR_3D,
    guardar: bool = GUARDAR_FIGURAS,
    mostrar: bool = True,
) -> None:
    """Abre la cuadrícula del proceso y la ventana 3D de la pose indicada (o la última)."""
    if pose == "ultima":
        poses = fase.listar_poses(categoria)
        if not poses:
            raise FileNotFoundError(f"No hay poses organizadas de '{categoria}'.")
        pose = poses[-1].name
        print(f"[INFO] Visualizando la última pose: {categoria}/{pose}")
    import rutas

    dir_pose = rutas.dir_pose_ordenada(categoria, pose)  # en la carpeta de su proceso
    dir_fases = rutas.dir_fases(categoria, pose)
    ruta_rel = dir_fases / f"{pose}_relativa.npz"
    ruta_abs = dir_fases / f"{pose}.npz"
    ruta_xyz = rutas.reconstruccion(categoria, pose)
    for ruta, etapa in ((dir_pose, "organizar"), (ruta_rel, "fase_relativa"), (ruta_abs, "fase_absoluta")):
        if not ruta.exists():
            raise FileNotFoundError(f"No existe '{ruta}'. Ejecuta antes la etapa '{etapa}'.")

    rel = fase.cargar_fases_pose(ruta_rel)
    absl = fase.cargar_fases_pose(ruta_abs)

    xs = ys = zs = m3d = None
    if ruta_xyz.exists():
        with np.load(ruta_xyz) as r3d:
            xs, ys, zs = (r3d[k].astype(np.float64) for k in ("X", "Y", "Z"))
            m3d = r3d["Mask"].astype(bool)
    if zs is None:
        print(f"[AVISO] No hay reconstrucción 3D de {categoria}/{pose}: ejecuta la etapa 'reconstruccion'.")

    # ---------------- Ventana 1: cuadrícula del proceso ----------------
    fig, ejes = plt.subplots(3, 4, figsize=(17, 11))
    fig.suptitle(f"{categoria} / {pose}: proceso de phase shifting", fontsize=14)
    mx, my = absl["MaskX"].astype(bool), absl["MaskY"].astype(bool)

    _panel(ejes[0, 0], _leer_franja(dir_pose, "V", 0), "Franjas verticales (V, paso 0)", barra=False)
    _panel(ejes[0, 1], _leer_franja(dir_pose, "H", 0), "Franjas horizontales (H, paso 0)", barra=False)
    _panel(ejes[0, 2], _leer_franja(dir_pose, "V", cfg.N_PASOS), "Código Gray V (primer bit)", barra=False)
    _panel(ejes[0, 3], absl["Itex"], "Textura (patrón blanco)", barra=False)

    _panel(ejes[1, 0], rel["phiX"], "Fase relativa X  [rad]", "twilight", rango=(-np.pi, np.pi))
    _panel(ejes[1, 1], rel["phiY"], "Fase relativa Y  [rad]", "twilight", rango=(-np.pi, np.pi))
    _panel(ejes[1, 2], absl["kX"], "Orden de franja k (Gray V)", "nipy_spectral")
    _panel(ejes[1, 3], rel["qX"], "Modulación γ = B/A (X)", "viridis", rango=(0, 1))

    _panel(ejes[2, 0], absl["Fx"], "Fase absoluta Fx  [rad]", "jet", mascara=mx)
    _panel(ejes[2, 1], absl["Fy"], "Fase absoluta Fy  [rad]", "jet", mascara=my)
    _panel(ejes[2, 2], absl["MaskC"].astype(float) + mx + my, "Máscara: 0 nada · 1 una fase · 3 ambas",
           "magma", rango=(0, 3))
    if zs is not None:
        _panel(ejes[2, 3], zs, "Profundidad Z  [mm]", "viridis_r", mascara=m3d)
    else:
        ejes[2, 3].axis("off")
        ejes[2, 3].text(0.5, 0.5, "Sin reconstrucción 3D", ha="center", va="center")
    fig.tight_layout()

    # ---------------- Ventana 2: nube de puntos 3D ----------------
    fig3d = None
    if zs is not None and np.any(m3d):
        # Se ocultan los atípicos extremos para que no deformen la escala de la vista
        z_lo, z_hi = np.percentile(zs[m3d], [0.5, 99.5])
        idx = np.flatnonzero(m3d & (zs >= z_lo) & (zs <= z_hi))
        if len(idx) > puntos_max:
            idx = np.random.default_rng(0).choice(idx, puntos_max, replace=False)
        x, y, z = xs.ravel()[idx], ys.ravel()[idx], zs.ravel()[idx]
        fig3d = plt.figure(figsize=(10, 8))
        ax = fig3d.add_subplot(projection="3d")
        if color_3d == "textura":
            col = absl["Itex"].ravel()[idx] / 255.0
            sc = ax.scatter(x, y, z, c=col, cmap="gray", s=0.5, vmin=0, vmax=1)
        else:
            sc = ax.scatter(x, y, z, c=z, cmap="viridis_r", s=0.5)
            fig3d.colorbar(sc, ax=ax, shrink=0.6, label="Z [mm]")
        ax.set_xlabel("X [mm]")
        ax.set_ylabel("Y [mm]")
        ax.set_zlabel("Z [mm]")
        ax.set_title(f"{categoria} / {pose}: {np.count_nonzero(m3d):,} puntos ({len(idx):,} mostrados)")
        # Escala igual en los tres ejes y vista desde la cámara (Z hacia la escena, Y hacia abajo)
        rangos = np.array([np.ptp(x), np.ptp(y), np.ptp(z)])
        ax.set_box_aspect(np.maximum(rangos, 1e-3))
        ax.zaxis.set_major_locator(plt.MaxNLocator(3))
        ax.view_init(elev=-60, azim=-70)
        ax.invert_zaxis()

    if guardar:
        dir_vis = cfg.DIR_RESULTADOS / "visualizacion"
        dir_vis.mkdir(parents=True, exist_ok=True)
        fig.savefig(dir_vis / f"{categoria}_{pose}_proceso.png", dpi=110)
        if fig3d is not None:
            fig3d.savefig(dir_vis / f"{categoria}_{pose}_3d.png", dpi=110)
        print(f"[OK] Figuras guardadas en '{dir_vis}'")
    if mostrar:
        plt.show()
    else:
        plt.close("all")


if __name__ == "__main__":
    visualizar_pose()
