"""Reconstrucción 3D estéreo cámara-proyector a partir de la fase absoluta.

Adapta los códigos de MATLAB:
- `StereoCalibCodes/StereoReconstruction.m`
- `StereoCalibCodes/comp_distortion_oulu.m`
- `3DReconstructionCodes/Plane_fitting.m`
- `3DReconstructionCodes/XYZtoPC.m`
- `3DReconstructionCodes/R3D_ComplexShape.m`
- `3DReconstructionCodes/R3D_mirrorPositions.m`

Flujo:
1. Carga las fases absolutas (`resultados/fases/<categoria>/pose_XX.npz`) y la calibración estéreo.
2. Triangula cada píxel válido intersecando su rayo de cámara con el plano del proyector definido
   por u_p (fase `Fx`), por v_p (fase `Fy`), o con ambos por mínimos cuadrados ponderados por la
   modulación de cada fase (`ambas`). `auto` elige la fase alineada con la línea base.
   Las distorsiones se compensan con el modelo de Oulu.
3. Para `plano` ajusta un plano a cada pose (`Plane_fitting.m`) y reporta el error RMS de planitud.
4. Exporta por pose la nube `.ply` con textura, los mapas X, Y, Z (`<categoria>_pose_XX.npz`) y una
   figura, más `<categoria>_resumen.json`. Las poses sin cambios se reutilizan (caché).

Ejemplo de uso:
    python reconstruccion_3d.py --categorias objeto plano --fase auto
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

import configuracion as cfg
import mascara
import fase
import rutas
import sesiones
from calibracion_estereo import normalizar_mapa_color


# ==============================================================================
# 1. COMPENSACIÓN DE DISTORSIÓN Y TRIANGULACIÓN ESTÉREO (StereoReconstruction.m)
# ==============================================================================


def comp_distortion_oulu(xd: np.ndarray, k: np.ndarray, iteraciones: int = 20) -> np.ndarray:
    """Compensa iterativamente la distorsión radial y tangencial (`comp_distortion_oulu.m`).

    - xd: coordenadas normalizadas distorsionadas (2, N).
    - k: coeficientes `[k1, k2, p1, p2, k3]` (formato OpenCV).
    """
    k_flat = np.zeros(5, dtype=np.float64)
    k_in = np.asarray(k, dtype=np.float64).ravel()[:5]
    k_flat[: k_in.size] = k_in
    if np.allclose(k_flat, 0.0):
        return xd.copy()

    k1, k2, p1, p2, k3 = k_flat
    x = xd.copy()
    for _ in range(iteraciones):
        r_2 = np.sum(x * x, axis=0)
        k_radial = 1.0 + k1 * r_2 + k2 * r_2**2 + k3 * r_2**3
        delta_x = np.vstack(
            [
                2.0 * p1 * x[0] * x[1] + p2 * (r_2 + 2.0 * x[0] ** 2),
                p1 * (r_2 + 2.0 * x[1] ** 2) + 2.0 * p2 * x[0] * x[1],
            ]
        )
        x = (xd - delta_x) / k_radial[np.newaxis, :]
    return x


def _distorsion(params: dict, prefijo: str) -> np.ndarray:
    clave = f"dist_{prefijo}"
    if clave in params:
        return np.asarray(params[clave], dtype=np.float64).ravel()
    idx = "1" if prefijo == "cam" else "2"
    kr = np.asarray(params[f"Kr{idx}"], dtype=np.float64).ravel()
    kt = np.asarray(params[f"Kt{idx}"], dtype=np.float64).ravel()
    return np.array([kr[0], kr[1], kt[0], kt[1], kr[2] if kr.size > 2 else 0.0])


def elegir_fase(fd: str, stereo_params: dict | None = None) -> str:
    """Resuelve `fd='auto'`: la coordenada del proyector alineada con la línea base.

    La sensibilidad de u_p a la profundidad es proporcional a la componente T_x de la línea base
    (expresada en el sistema del proyector) y la de v_p a T_y. Un error de fase se traduce en un
    error de Z inversamente proporcional a esa sensibilidad, así que se usa la fase cuyo eje tiene
    mayor |T|. En este montaje T ~ (25, -89, -4) mm: v_p (Fy) es ~3.5 veces más sensible que u_p.
    Es lo mismo que hacían los scripts de MATLAB (`Fd = 'Fy'` en `R3D_ComplexShape.m`).
    """
    if fd.lower() != "auto":
        return fd
    if stereo_params is None:
        return "Fy"
    t_vec = np.asarray(stereo_params["T"], dtype=np.float64).ravel()
    return "Fx" if abs(t_vec[0]) > abs(t_vec[1]) else "Fy"


def fuera_de_cobertura(
    up: np.ndarray, vp: np.ndarray, mascara: np.ndarray, stereo_params: dict, fd: str
) -> float:
    """Fracción de puntos cuya coordenada del proyector cae fuera del rango que cubrieron los
    círculos del tablero durante la calibración (ahí el modelo de distorsión se extrapola)."""
    claves = {"fx": [("cobertura_up", up)], "fy": [("cobertura_vp", vp)]}
    claves["ambas"] = claves["fx"] + claves["fy"]
    fuera = np.zeros(int(np.count_nonzero(mascara)), dtype=bool)
    for clave, mapa in claves[fd.lower()]:
        if clave not in stereo_params:
            return float("nan")
        lo, hi = np.asarray(stereo_params[clave], dtype=np.float64).ravel()[:2]
        valores = mapa[mascara]
        fuera |= (valores < lo) | (valores > hi)
    return float(fuera.mean()) if fuera.size else 0.0


def triangular(
    up: np.ndarray,
    vp: np.ndarray,
    mascara_x: np.ndarray,
    mascara_y: np.ndarray,
    stereo_params: dict,
    fd: str = "ambas",
    peso_x: np.ndarray | None = None,
    peso_y: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Triangulación cámara-proyector por píxel (`StereoReconstruction.m`).

    Cada píxel de cámara define un rayo X = Z * r (r normalizado y sin distorsión). Cada coordenada
    del proyector impone una ecuación lineal en Z:
        (R_1 . r - x_p R_3 . r) Z = x_p T_3 - T_1     (con u_p; análogo con v_p y la fila 2)
    `Fx` usa la ecuación de u_p, `Fy` la de v_p y `ambas` las combina por mínimos cuadrados con
    pesos (f_p * B)^2, inversos a la varianza de cada coordenada del proyector.

    Retorna X, Y, Z (mm, sistema de la cámara; NaN fuera de la máscara) y la máscara usada.
    """
    ac = np.asarray(stereo_params["Ac"], dtype=np.float64)
    ap = np.asarray(stereo_params["Ap"], dtype=np.float64)
    r_mat = np.asarray(stereo_params["R"], dtype=np.float64)
    t_vec = np.asarray(stereo_params["T"], dtype=np.float64).ravel()
    k_cam = _distorsion(stereo_params, "cam")
    k_proj = _distorsion(stereo_params, "proj")

    fd = elegir_fase(fd, stereo_params).lower()
    usar_x = fd in ("fx", "ambas")
    usar_y = fd in ("fy", "ambas")
    if not (usar_x or usar_y):
        raise ValueError("fd debe ser 'Fx', 'Fy', 'ambas' o 'auto'")
    mx = (mascara_x > 0) & np.isfinite(up) if usar_x else np.zeros(up.shape, bool)
    my = (mascara_y > 0) & np.isfinite(vp) if usar_y else np.zeros(up.shape, bool)
    mascara = mx | my

    vc, uc = np.nonzero(mascara)
    rc = np.linalg.solve(ac, np.vstack([uc, vc, np.ones_like(uc)]).astype(np.float64))
    ray = np.vstack([comp_distortion_oulu(rc[:2], k_cam), np.ones(len(uc))])

    # Coordenadas del proyector -> normalizadas sin distorsión. La corrección necesita u_p y v_p a la
    # vez; si una tiene poca modulación se usa igualmente, pues solo entra en el término de distorsión.
    u_px = np.nan_to_num(up[vc, uc])
    v_px = np.nan_to_num(vp[vc, uc])
    xp = np.linalg.solve(ap, np.vstack([u_px, v_px, np.ones_like(u_px)]))
    xp = comp_distortion_oulu(xp[:2], k_proj)

    num = np.zeros(len(uc))
    den = np.zeros(len(uc))
    for fila, coord, usar, valido, peso, focal in (
        (0, xp[0], usar_x, mx[vc, uc], peso_x, ap[0, 0]),
        (1, xp[1], usar_y, my[vc, uc], peso_y, ap[1, 1]),
    ):
        if not usar:
            continue
        a = r_mat[fila] @ ray - coord * (r_mat[2] @ ray)
        b = coord * t_vec[2] - t_vec[fila]
        w = np.ones(len(uc)) if peso is None else (focal * peso[vc, uc]) ** 2
        w = np.where(valido, w, 0.0)
        num += w * a * b
        den += w * a * a

    zc = np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)
    x_cm = np.full(up.shape, np.nan)
    y_cm = np.full(up.shape, np.nan)
    z_cm = np.full(up.shape, np.nan)
    x_cm[vc, uc] = zc * ray[0]
    y_cm[vc, uc] = zc * ray[1]
    z_cm[vc, uc] = zc
    return x_cm, y_cm, z_cm, mascara & np.isfinite(z_cm)


# ==============================================================================
# 2. AJUSTE DE PLANOS, FILTRADO Y EXPORTACIÓN (Plane_fitting.m / XYZtoPC.m)
# ==============================================================================


def plane_fitting(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    mask: np.ndarray,
    umbral_mm: float = 3.0,
    iteraciones: int = 300,
    semilla: int = 0,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Ajusta el plano dominante Z = A X + B Y + C a una pose (`Plane_fitting.m`).

    Se usa RANSAC para que otras superficies de la escena (p. ej. la placa de soporte) no sesguen el
    ajuste, y luego mínimos cuadrados sobre los inliers. Retorna el mapa de distancia perpendicular
    al plano (mm, NaN fuera del plano dominante), el error RMS (mm) y los coeficientes [A, B, C].
    """
    valido = (mask > 0) & np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    pts = np.column_stack([x[valido], y[valido], z[valido]])
    rng = np.random.default_rng(semilla)
    muestra = pts[rng.choice(len(pts), size=min(len(pts), 20000), replace=False)]

    mejor, mejor_n = None, -1
    for _ in range(iteraciones):
        p0, p1, p2 = muestra[rng.choice(len(muestra), 3, replace=False)]
        normal = np.cross(p1 - p0, p2 - p0)
        norma = np.linalg.norm(normal)
        if norma < 1e-9:
            continue
        normal /= norma
        n_in = np.count_nonzero(np.abs((muestra - p0) @ normal) < umbral_mm)
        if n_in > mejor_n:
            mejor, mejor_n = (normal, p0), n_in

    normal, p0 = mejor
    en_plano = valido.copy()
    en_plano[valido] = np.abs((pts - p0) @ normal) < umbral_mm
    a_mat = np.column_stack([x[en_plano], y[en_plano], np.ones(np.count_nonzero(en_plano))])
    tt, *_ = np.linalg.lstsq(a_mat, z[en_plano], rcond=None)
    dist = (tt[0] * x + tt[1] * y - z + tt[2]) / np.sqrt(tt[0] ** 2 + tt[1] ** 2 + 1.0)
    en_plano = valido & (np.abs(dist) < umbral_mm)
    e_map = np.where(en_plano, dist, np.nan)
    err = e_map[en_plano]
    return e_map, float(np.sqrt(np.mean((err - err.mean()) ** 2))), tt


def filtrar_outliers_3d(
    z: np.ndarray, mask: np.ndarray, salto_max: float, z_min: float, z_max: float
) -> np.ndarray:
    """Descarta saltos locales en Z respecto a la mediana 5x5 y puntos fuera del rango físico (`pcdenoise`)."""
    valido = (mask > 0) & np.isfinite(z)
    if not np.any(valido):
        return valido
    z_rel = np.where(valido, z, np.nanmedian(z[valido])).astype(np.float32)
    z_med = cv2.medianBlur(z_rel, 5).astype(np.float64)
    return valido & (np.abs(z - z_med) < salto_max) & (z > z_min) & (z < z_max)


def escribir_ply_binario(ruta_ply: Path, puntos_xyz: np.ndarray, colores_rgb: np.ndarray) -> None:
    """Escribe una nube de puntos con color en formato PLY binario little-endian (`pcwrite`)."""
    n_pts = puntos_xyz.shape[0]
    encabezado = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {n_pts}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    ).encode("ascii")
    datos = np.empty(
        n_pts, dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")]
    )
    datos["x"], datos["y"], datos["z"] = puntos_xyz[:, 0], puntos_xyz[:, 1], puntos_xyz[:, 2]
    datos["r"], datos["g"], datos["b"] = colores_rgb[:, 0], colores_rgb[:, 1], colores_rgb[:, 2]
    with ruta_ply.open("wb") as f:
        f.write(encabezado)
        f.write(datos.tobytes())


def _guardar_figura(
    ruta: Path, titulo: str, itex: np.ndarray, z: np.ndarray, mask: np.ndarray,
    e_map: np.ndarray | None = None, erms: float | None = None,
) -> None:
    tex = cv2.cvtColor(itex, cv2.COLOR_GRAY2BGR)
    cv2.putText(tex, f"{titulo}: textura", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
    vmin, vmax = np.nanpercentile(z[mask], [2, 98]) if np.any(mask) else (0.0, 1.0)
    z_bgr = normalizar_mapa_color(z, mask.astype(np.uint8), float(vmin), float(vmax), cv2.COLORMAP_VIRIDIS)
    cv2.putText(z_bgr, f"Z [{vmin:.1f}, {vmax:.1f}] mm", (25, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
    paneles = [tex, z_bgr]
    if e_map is not None:
        lim = max(3.0 * (erms or 0.2), 0.05)
        e_bgr = normalizar_mapa_color(e_map, None, -lim, lim, cv2.COLORMAP_TURBO)
        cv2.putText(e_bgr, f"Error plano RMS = {erms:.4f} mm [+-{lim:.2f}]", (25, 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        paneles.append(e_bgr)
    cv2.imwrite(str(ruta), cv2.resize(np.hstack(paneles), (0, 0), fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA))


# ==============================================================================
# 3. ETAPA COMPLETA
# ==============================================================================


def _id_reconstruccion(ruta_calibracion: Path, fd: str, z_min: float, z_max: float, salto_max: float,
                       plano_umbral: float = cfg.PLANO_UMBRAL_MM, vecinos: float = 0.0) -> str:
    """Identifica todo lo que, además de la fase de la pose, determina su reconstrucción."""
    st = ruta_calibracion.resolve().stat()
    extra = "" if plano_umbral == 3.0 else f"|{plano_umbral}"  # sin cambiar el id de lo ya calculado
    extra += f"|vecinos={vecinos}" if vecinos else ""
    return f"{ruta_calibracion.resolve()}|{st.st_mtime_ns}|{fd}|{z_min}|{z_max}|{salto_max}{extra}"


def cargar_reconstruccion_pose(ruta: Path) -> dict[str, np.ndarray]:
    """Lee `<cat>_pose_XX.npz`: X, Y, Z (mm, float32, NaN fuera), Mask, y E (error al plano) si existe."""
    with np.load(ruta) as datos:
        return {k: datos[k] for k in datos.files}


def procesar_reconstruccion(
    dir_fases: Path = cfg.DIR_RESULTADOS / "fases",
    ruta_calibracion: Path = cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz",
    dir_salida: Path = cfg.DIR_RESULTADOS / "reconstruccion",
    categorias: Sequence[str] = ("objeto", "plano"),
    fd: str = cfg.FASE_TRIANGULACION,
    z_min: float = cfg.Z_MIN_MM,
    z_max: float = cfg.Z_MAX_MM,
    salto_max: float = cfg.SALTO_MAX_MM,
    rehacer: bool = False,
    plano_umbral: float = cfg.PLANO_UMBRAL_MM,
) -> dict[str, list[Path]]:
    """Reconstruye todas las poses de las categorías indicadas.

    Por pose escribe `<cat>_pose_XX.ply` (nube), `<cat>_pose_XX.npz` (mapas X, Y, Z, Mask) y una
    figura; por categoría, `<cat>_resumen.json` con las estadísticas de cada pose.

    Caché: una pose se omite si su `.npz` es más reciente que su fase absoluta y fue calculado con
    la misma calibración (ruta y fecha), el mismo modo de triangulación y los mismos filtros.
    Así, al medir un objeto nuevo solo se triangula ese objeto. `rehacer=True` lo ignora.
    """
    if not ruta_calibracion.exists():
        raise FileNotFoundError(
            f"No existe la calibración '{ruta_calibracion}'. Ejecuta antes la etapa 'calibracion'."
        )
    stereo_params = dict(np.load(ruta_calibracion))
    fd_usada = elegir_fase(fd, stereo_params)
    ident = _id_reconstruccion(ruta_calibracion, fd_usada, z_min, z_max, salto_max, plano_umbral, cfg.FILTRO_VECINOS_SIGMA)
    print(f"[INFO] Calibración: '{ruta_calibracion}' | triangulación con: {fd_usada}"
          f"{' (auto)' if fd.lower() == 'auto' else ''}")
    for clave in ("cobertura_up", "cobertura_vp"):
        if clave in stereo_params:
            lo, hi = np.asarray(stereo_params[clave]).ravel()[:2]
            print(f"[INFO] Rango calibrado de {clave[-2:]}: [{lo:.0f}, {hi:.0f}] px del proyector")

    salidas: dict[str, list[Path]] = {}
    for categoria in categorias:
        vigentes = sesiones.poses_vigentes(categoria)  # solo el montaje actual (sesiones.py)
        # Cada pose en la carpeta de su proceso (rutas.py); `dir_fases`/`dir_salida` quedan por compatibilidad
        rutas_fase = [rutas.fase_absoluta(categoria, p) for p in rutas.poses(categoria)
                      if vigentes is None or p in vigentes]
        rutas_fase = [r for r in rutas_fase if r.exists()]
        if not rutas_fase:
            print(f"[AVISO] No hay fases absolutas de '{categoria}'. Ejecuta antes 'fase_absoluta'.")
            continue
        dir_resumen = rutas.dir_resumen(categoria)  # resumen de todas las poses de la categoría
        dir_resumen.mkdir(parents=True, exist_ok=True)
        ruta_resumen = dir_resumen / f"{categoria}_resumen.json"
        resumen = json.loads(ruta_resumen.read_text(encoding="utf-8")) if ruta_resumen.exists() else {}
        print(f"\n================ RECONSTRUCCIÓN 3D: '{categoria.upper()}' ({len(rutas_fase)} poses) ================")

        for ruta_fase in rutas_fase:
            nombre = ruta_fase.stem
            dir_cat = rutas.dir_reconstruccion(categoria, nombre)
            dir_cat.mkdir(parents=True, exist_ok=True)
            ruta_ply = dir_cat / f"{categoria}_{nombre}.ply"
            ruta_xyz = dir_cat / f"{categoria}_{nombre}.npz"
            salidas.setdefault(categoria, []).append(ruta_ply)
            previo = resumen.get(nombre, {})
            firma_mascara = mascara.firma(categoria, nombre)  # máscara de la pestaña «Máscara», si hay
            if (
                not rehacer and previo.get("id") == ident and previo.get("mascara") == firma_mascara
                and ruta_ply.exists() and ruta_xyz.exists()
                and ruta_xyz.stat().st_mtime > ruta_fase.stat().st_mtime
            ):
                print(f"  [{nombre}] sin cambios, se reutiliza '{ruta_ply.name}'"
                      + (f" | error RMS plano = {previo['erms_mm']:.4f} mm" if previo.get("erms_mm") else ""))
                continue

            t0 = time.perf_counter()
            d = fase.cargar_fases_pose(ruta_fase)
            x, y, z, m = triangular(
                d["up"], d["vp"], d["MaskX"], d["MaskY"], stereo_params, fd_usada,
                peso_x=d.get("BX"), peso_y=d.get("BY"),
            )
            m = filtrar_outliers_3d(z, m, salto_max, z_min, z_max)
            n_antes = int(np.count_nonzero(m))
            mask_usuario = mascara.cargar(categoria, nombre, m.shape)
            if mask_usuario is not None:
                m &= mask_usuario
            m = mascara.filtrar_vecinos(x, y, z, m, cfg.FILTRO_VECINOS_SIGMA)
            itex = d["Itex"]
            fuera = fuera_de_cobertura(d["up"], d["vp"], m, stereo_params, fd_usada)

            pts = np.column_stack([x[m], y[m], z[m]])
            gris = itex[m]
            escribir_ply_binario(ruta_ply, pts, np.column_stack([gris, gris, gris]))

            e_map, erms = None, None
            texto = ""
            info = {"id": ident, "puntos": int(len(pts)), "fuera_de_cobertura": round(fuera, 4),
                    "mascara": firma_mascara, "quitados_mascara": n_antes - int(len(pts))}
            if firma_mascara or cfg.FILTRO_VECINOS_SIGMA:
                texto = f" | máscara/filtro: -{n_antes - len(pts):,} puntos"
            if categoria == "plano" and np.count_nonzero(m) > 100:
                e_map, erms, coef = plane_fitting(x, y, z, m, umbral_mm=plano_umbral)
                cobertura = 100.0 * np.count_nonzero(np.isfinite(e_map)) / np.count_nonzero(m)
                texto += f" | error RMS plano = {erms:.4f} mm ({cobertura:.0f}% de los puntos)"
                info.update(erms_mm=erms, plano_ABC=[float(c) for c in coef], fraccion_en_plano=cobertura / 100)
            if np.any(m):
                z1, z99 = np.percentile(z[m], [1, 99])
                texto = f" | Z=[{z1:.1f}, {z99:.1f}] mm" + texto
                info.update(z_p1_mm=float(z1), z_p99_mm=float(z99))
            print(
                f"  [{nombre}] {len(pts):,} puntos ({time.perf_counter() - t0:.1f} s){texto} -> '{ruta_ply.name}'"
            )
            if fuera > 0.05:
                print(f"      [AVISO] {100 * fuera:.0f}% de los puntos usan zonas del proyector fuera del "
                      f"rango calibrado: ahí el error crece. Captura poses del tablero que cubran esa zona.")
            _guardar_figura(dir_cat / f"reconstruccion_{categoria}_{nombre}.png", f"{categoria} {nombre}",
                            itex, z, m, e_map, erms)
            extra = {"E": e_map.astype(np.float32)} if e_map is not None else {}
            fase.guardar_npz_atomico(
                ruta_xyz, X=x.astype(np.float32), Y=y.astype(np.float32), Z=z.astype(np.float32),
                Mask=m, fase=fd_usada, **extra,
            )
            resumen[nombre] = info
            ruta_resumen.write_text(json.dumps(resumen, indent=2), encoding="utf-8")

        # Se olvidan solo las poses que ya no existen (no las de otra configuración: al volver a ellas
        # su resumen sigue sirviendo y la caché evita recalcularlas)
        existentes = set(rutas.poses(categoria))
        resumen = {k: v for k, v in resumen.items() if k in existentes}
        ruta_resumen.write_text(json.dumps(resumen, indent=2), encoding="utf-8")
        errores = [v["erms_mm"] for v in resumen.values() if v.get("erms_mm") is not None]
        if errores:
            print(f"  -> Error RMS promedio en planos: {float(np.mean(errores)):.4f} mm")
        print(f"[OK] Resultados 3D de '{categoria}' en la carpeta de cada proceso dentro de '{cfg.DIR_RESULTADOS}'")
    return salidas


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconstrucción 3D estéreo cámara-proyector.")
    parser.add_argument("--fases", type=Path, default=cfg.DIR_RESULTADOS / "fases")
    parser.add_argument("--calibracion", type=Path,
                        default=cfg.DIR_CALIBRACION / "Estereo_TSC_0_2.npz",
                        help="Archivo .npz de calibración estéreo")
    parser.add_argument("--salida", type=Path, default=cfg.DIR_RESULTADOS / "reconstruccion")
    parser.add_argument("--categorias", nargs="+", default=["objeto", "plano"])
    parser.add_argument("--fase", default=cfg.FASE_TRIANGULACION, choices=["auto", "ambas", "Fx", "Fy"],
                        help="Fase usada para triangular (por defecto: %(default)s)")
    parser.add_argument("--rehacer", action="store_true", help="Ignora la caché y reconstruye todo")
    args = parser.parse_args()
    procesar_reconstruccion(args.fases, args.calibracion, args.salida, args.categorias, args.fase,
                            rehacer=args.rehacer)  # z, salto y plano: los de configuracion.py


if __name__ == "__main__":
    main()
