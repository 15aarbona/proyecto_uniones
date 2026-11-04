"""geometria.py

Módulo de corrección geométrica iterativa, reestructuración estricta del patrón de tornillos
y validación cruzada resistencia-geometría para uniones atornilladas con chapa frontal (AISC 360-10).
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple
from externos import tablapernos, tablaplaca


def _round5(x: float) -> float:
    return round(x / 5.0) * 5.0


def _ceil5(x: float) -> float:
    return math.ceil(round(x, 6) / 5.0) * 5.0


def _floor5(x: float) -> float:
    return math.floor(round(x, 6) / 5.0) * 5.0


_ORDEN_PERNOS = ["M16", "M20", "M22", "M24", "M27", "M30", "M36"]
_ORDEN_CLASES = ["8.8", "10.9"]
_ESPESORES_PLACA = ["10mm", "12mm", "15mm", "20mm", "25mm", "30mm", "35mm", "40mm", "45mm", "50mm"]


def reorganizar_patron_tornillos_estricto(
    inp, min_spacing: float, min_edge: float, clearance_herramienta: float
) -> Tuple[Any, bool]:
    """
    Garantiza el cumplimiento estricto del patrón vertical de tornillos:
      1. Exactamente 1 fila exterior superior (pfo).
      2. Al menos 1 fila interior dentro del canto libre de la viga (pfi/pb).
      3. Al menos 1 fila interior dentro del canto de la cantonera (si existe).
      4. Exactamente 1 fila exterior inferior (bajo el ala de la cantonera o viga).
    """
    viga = inp.viga
    if not viga:
        return inp, False

    h_v = viga.h
    tf_v = viga.tf
    has_haunch = (inp.AnguloCantonera or 0.0) > 0.0 and (inp.Lh or 0.0) > 0.0

    # Altura vertical de la cantonera
    h_h = 0.0
    if has_haunch:
        rad = math.radians(inp.AnguloCantonera)
        h_h = inp.FactorCantoCantonera * h_v / math.sin(rad) if rad > 0 else 0.0

    wf_val = inp.wf if hasattr(inp, "wf") and inp.wf else 6.0
    db_val = float("".join(filter(str.isdigit, str(inp.BoltName_ep))) or 24.0)

    pfo_min = _ceil5(db_val + wf_val + 10.0)
    pfi_min = _ceil5(db_val + 15.0)

    # 1. Resetear explícitamente todos los pasos sobrantes
    campos_todos = ["pb", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12"]
    for campo in campos_todos:
        setattr(inp, campo, 0.0)

    # 2. FILA 1: Exterior Superior (Única)
    inp.pfo = max(_round5(inp.pfo), pfo_min)

    # 3. FILAS INTERIORES VIGA
    canto_libre_viga = h_v - 2.0 * tf_v
    inp.pfi = max(_ceil5(inp.pfi or pfi_min), pfi_min)
    filas_viga = [inp.pfi]

    espacio_disp_viga = canto_libre_viga - inp.pfi - pfi_min
    if espacio_disp_viga >= min_spacing:
        pb_val = _ceil5(max(inp.pb or min_spacing, min_spacing))
        if pb_val <= espacio_disp_viga:
            filas_viga.append(pb_val)

    # 4. FILA INTERIOR CANTONERA (Si existe cantonera)
    dist_cantonera = 0.0
    if has_haunch and h_h > 0:
        # Colocar la fila centrada en la cantonera respetando holguras
        dist_cantonera = _ceil5(max(h_h / 2.0, pfi_min))
        if dist_cantonera > (h_h - pfi_min):
            dist_cantonera = max(pfi_min, h_h - pfi_min)

    # 5. FILA EXTERIOR INFERIOR (Única)
    p_ext_inf = max(pfo_min, _ceil5(min_spacing))

    # 6. CÁLCULO DE PASOS CONSECUTIVOS
    separaciones = []
    if len(filas_viga) > 1:
        separaciones.append(filas_viga[1])  # pb

    cota_ult_viga = inp.pfo + sum(filas_viga)

    if has_haunch and h_h > 0:
        # Fila dentro de la cantonera
        cota_fila_cant = inp.pfo + h_v + dist_cantonera
        p_paso_cant = _ceil5(cota_fila_cant - cota_ult_viga)
        separaciones.append(p_paso_cant)

        # Fila exterior inferior bajo la cantonera
        cota_ext_inf = inp.pfo + h_v + h_h + p_ext_inf
        p_paso_ext = _ceil5(cota_ext_inf - cota_fila_cant)
        separaciones.append(p_paso_ext)
    else:
        # Fila exterior inferior bajo la viga
        cota_ext_inf = inp.pfo + h_v + p_ext_inf
        p_paso_ext = _ceil5(cota_ext_inf - cota_ult_viga)
        separaciones.append(p_paso_ext)

    # 7. Asignar a inp (pb, p3, p4...)
    if len(separaciones) > 0:
        inp.pb = separaciones[0]
    for idx, sep in enumerate(separaciones[1:], start=3):
        setattr(inp, f"p{idx}", sep)

    # Actualizar contador de filas y pernos
    total_filas = 1 + len(filas_viga) + (1 if (has_haunch and h_h > 0) else 0) + 1
    inp.NumeTotalFilasTornillos = total_filas
    inp.nbol = 2.0 * total_filas

    return inp, True


def recalcular_geometria_fallos(
    inp, pfo_pred: float, pfi_pred: float, pb_pred: float, dev_pred: float
) -> dict:
    """Ajuste incremental básico sobre las predicciones del modelo."""
    tbl_pernos = tablapernos()
    tbl_pernos.nombretornillo = inp.BoltName_ep

    tbl_placa = tablaplaca()
    tbl_placa.nombreplaca = inp.ThicknessName_t_ep

    db = tbl_pernos.dmetrico
    min_edge = tbl_pernos.disborminmet
    min_spacing = tbl_pernos.pitchminmet
    max_spacing = tbl_placa.pitchmaxmet if tbl_placa.pitchmaxmet > 0 else 305.0

    wf_val = inp.wf if hasattr(inp, "wf") and inp.wf else 6.0

    pfo_min = _ceil5(db + wf_val + 10.0)
    pfi_min = _ceil5(db + 15.0)

    pfo_calc = max(_round5(pfo_pred), pfo_min)
    pfi_calc = max(_round5(pfi_pred), pfi_min)

    pb_calc = max(_ceil5(pb_pred), _ceil5(min_spacing))
    if max_spacing > 0 and pb_calc > max_spacing:
        pb_calc = math.floor(max_spacing / 5.0) * 5.0

    dev_calc = max(_ceil5(dev_pred), _ceil5(min_edge))

    arr = [0.0] * 12
    arr[0] = pfo_calc
    arr[1] = pfi_calc
    arr[2] = pb_calc

    return {
        "pfo": pfo_calc,
        "pfi": pfi_calc,
        "pb": pb_calc,
        "dev": dev_calc,
        "p_separations": arr,
        "bolt_used": inp.BoltName_ep,
    }


def resolver_geometria_y_ratios_automatico(
    inp, max_iter_geom: int = 25, ratio_objetivo: float = 0.85
) -> Dict[str, Any]:
    """
    Ejecuta el bucle de auto-corrección geométrica obligatoria y validación cruzada con ratios mecánicos.
    """
    from calculador import CalculadorAISC36010

    motivo_fallo: Optional[str] = None
    exito_global = False

    idx_perno = _ORDEN_PERNOS.index(inp.BoltName_ep) if inp.BoltName_ep in _ORDEN_PERNOS else 1
    idx_clase = _ORDEN_CLASES.index(inp.BoltGrade) if inp.BoltGrade in _ORDEN_CLASES else 0
    idx_tp = _ESPESORES_PLACA.index(inp.ThicknessName_t_ep) if inp.ThicknessName_t_ep in _ESPESORES_PLACA else 2

    for _ in range(40):
        tbl_pernos = tablapernos()
        tbl_pernos.nombretornillo = inp.BoltName_ep
        db = tbl_pernos.dmetrico or float("".join(filter(str.isdigit, str(inp.BoltName_ep))) or 24)
        min_edge = tbl_pernos.disborminmet or 35.0
        min_spacing = tbl_pernos.pitchminmet or 60.0

        db_val = float("".join(filter(str.isdigit, str(inp.BoltName_ep))) or 24.0)
        clearance_herramienta = tablapernos.DATOS_PERNOS.get(int(round(db_val)), {}).get("clearance", db_val + 15.0)

        geom_ok = False

        # BUCLE DE CORRECCIÓN GEOMÉTRICA OBLIGATORIA
        for _ in range(max_iter_geom):
            inp, _ = reorganizar_patron_tornillos_estricto(
                inp,
                min_spacing=min_spacing,
                min_edge=min_edge,
                clearance_herramienta=clearance_herramienta,
            )

            calc = CalculadorAISC36010(inp)
            fallos_geom = calc.calcular_geometria()

            if not fallos_geom:
                geom_ok = True
                break

            if "bc&bb" in fallos_geom:
                motivo_fallo = (
                    f"Incompatibilidad de perfiles: El ancho del pilar ({inp.pilar.b} mm) "
                    f"es inferior al de la viga ({inp.viga.b} mm)."
                )
                break

            if "PRMIN" in fallos_geom:
                m = re.search(r"prmin:\s*([\d\.]+)", fallos_geom["PRMIN"])
                if m:
                    inp.p2_ep = _ceil5(float(m.group(1)))
                else:
                    inp.p2_ep += 5.0

            if "PRMAX" in fallos_geom:
                m = re.search(r"prmax:\s*([\d\.]+)", fallos_geom["PRMAX"])
                if m:
                    inp.p2_ep = _floor5(float(m.group(1)))

            bep_min_req = _ceil5(inp.p2_ep + 2.0 * min_edge)
            if inp.viga:
                bep_min_req = max(bep_min_req, _ceil5(inp.viga.b + 10.0))

            if inp.pilar and bep_min_req > inp.pilar.b:
                motivo_fallo = (
                    f"Geometría inviable: El gramil p2 ({inp.p2_ep} mm) más distancias al borde (2x{min_edge} mm) "
                    f"requiere un ancho de chapa ({bep_min_req} mm) mayor que el ala del pilar ({inp.pilar.b} mm)."
                )
                break

            if "bep&bepmin" in fallos_geom or "DEH_MIN" in fallos_geom:
                inp.b_ep = _ceil5(max(inp.b_ep, bep_min_req))

            if "bep&bb" in fallos_geom and inp.viga:
                inp.b_ep = _ceil5(max(inp.b_ep, inp.viga.b + 10.0))

            if "bep&bc" in fallos_geom and inp.pilar:
                if inp.b_ep > inp.pilar.b:
                    inp.b_ep = _floor5(inp.pilar.b)

            if "DEV_MIN" in fallos_geom:
                inp.dev = _ceil5(max(inp.dev, min_edge))

            if "SPACING_MIN" in fallos_geom:
                inp.pb = _ceil5(max(inp.pb, min_spacing))
                if inp.pfi is not None and inp.pfi < min_spacing:
                    inp.pfi = _ceil5(min_spacing)

            interferencias = [k for k in fallos_geom.keys() if k.startswith("ENTER_")]
            if interferencias:
                wf_val = inp.wf if hasattr(inp, "wf") and inp.wf else 6.0
                pfo_min = _ceil5(db + wf_val + 10.0)
                pfi_min = _ceil5(db + 15.0)

                if inp.pfo < pfo_min:
                    inp.pfo = pfo_min
                else:
                    inp.pfo += 5.0

                if inp.pfi is not None:
                    if inp.pfi < pfi_min:
                        inp.pfi = pfi_min
                    else:
                        inp.pfi += 5.0

        if motivo_fallo:
            break

        if not geom_ok:
            motivo_fallo = "No se logró estabilizar la geometría tras agotar las iteraciones de ajuste espacial."
            break

        # VALIDACIÓN DE RATIOS MECÁNICOS
        calc = CalculadorAISC36010(inp)
        resul = calc.calcular_conexion()

        if resul.cumple and resul.ratio_pesimo <= ratio_objetivo:
            exito_global = True
            break

        desc = resul.descripcion_ratio_pesimo

        if "yield" in desc.lower() or "prying" in desc.lower() or "plate" in desc.lower():
            if idx_tp < len(_ESPESORES_PLACA) - 1:
                idx_tp += 1
                inp.ThicknessName_t_ep = _ESPESORES_PLACA[idx_tp]
                continue

        if "bolts" in desc.lower() or "shear" in desc.lower() or "tension" in desc.lower():
            if idx_clase < len(_ORDEN_CLASES) - 1:
                idx_clase += 1
                inp.BoltGrade = _ORDEN_CLASES[idx_clase]
                continue
            elif idx_perno < len(_ORDEN_PERNOS) - 1:
                idx_perno += 1
                inp.BoltName_ep = _ORDEN_PERNOS[idx_perno]
                inp.BoltGrade = _ORDEN_CLASES[0]
                idx_clase = 0
                continue

        if idx_tp < len(_ESPESORES_PLACA) - 1:
            idx_tp += 1
            inp.ThicknessName_t_ep = _ESPESORES_PLACA[idx_tp]
            continue

        motivo_fallo = (
            f"Resistencia insuficiente: Ratio pésimo {resul.ratio_pesimo:.3f} en '{desc}' "
            f"usando pernos máximos {inp.BoltName_ep} {inp.BoltGrade} y chapa {inp.ThicknessName_t_ep}. "
            f"Se requiere redimensionar los perfiles de la estructura."
        )
        break

    calc_final = CalculadorAISC36010(inp)
    resul_final = calc_final.calcular_conexion()
    fallos_geom_final = calc_final.calcular_geometria()

    cumple_final = exito_global and (len(fallos_geom_final) == 0)

    return {
        "conexion_input": inp,
        "resultado": resul_final,
        "fallos_geometria": fallos_geom_final,
        "cumple_todo": cumple_final,
        "motivo_fallo": None if cumple_final else (motivo_fallo or "Geometría o resistencia no conformes."),
    }