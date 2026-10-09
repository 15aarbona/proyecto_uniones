"""
Módulo de comprobación estructural.
Convierte las filas dict recibidas del cliente a ConexionInput y ejecuta CalculadorAISC36010.
"""
from __future__ import annotations

import pandas as pd
from typing import Dict, Any, List

from modelos import ConexionInput, Perfil
from calculador import CalculadorAISC36010
from models.V11.core.adapter import (
    _profile_lookup,
    ACERO_TABLE,
    TORNILLO_TABLE,
    DEFAULT_GRADO_ACERO,
    DEFAULT_CLASE_TORNILLO,
)


def _get_perfil(nombre: str, is_column: bool = False) -> Perfil:
    lookup = _profile_lookup()
    key = str(nombre).strip().upper()
    if key not in lookup.index:
        raise ValueError(f"Perfil '{nombre}' no encontrado en los catálogos Tekla.")

    geom = lookup.loc[key]
    h = float(geom["d_mm"])
    b = float(geom["bf_mm"])
    tw = float(geom["tw_mm"])
    tf = float(geom["tf_mm"])

    r_val = geom.get("r1_mm", geom.get("r_mm", 0.0))
    r = float(r_val) if pd.notna(r_val) else 0.0

    area_raw = float(geom.get("area_cm2", geom.get("area", 0.0)))
    A = area_raw * 100.0 if area_raw < 1000.0 else area_raw

    z_raw = float(geom.get("zx_cm3", geom.get("wx_cm3", geom.get("Z", 0.0))))
    Z = z_raw * 1000.0 if z_raw < 100000.0 else z_raw

    prmin = float(geom.get("prmin", 0.0)) if is_column and "prmin" in geom else 0.0
    prmax = float(geom.get("prmax", 0.0)) if is_column and "prmax" in geom else 0.0

    return Perfil(
        nombre=str(nombre),
        h=h, b=b, tf=tf, tw=tw, r=r, A=A, Z=Z,
        Prmin=prmin, Prmax=prmax
    )


def row_to_conexion_input(row: Dict[str, Any]) -> ConexionInput:
    beam_name = row.get("BEAM", "IPE300")
    col_name = row.get("COLUMN", "HEA200")

    viga = _get_perfil(beam_name, is_column=False)
    pilar = _get_perfil(col_name, is_column=True)

    grado = str(row.get("grado_acero") or DEFAULT_GRADO_ACERO).strip()
    acero_info = ACERO_TABLE.get(grado, ACERO_TABLE[DEFAULT_GRADO_ACERO])
    fy = float(acero_info["fy_acero_mpa"])
    fu = float(acero_info["fu_acero_mpa"])

    clase = str(row.get("clase_tornillo") or DEFAULT_CLASE_TORNILLO).strip()

    bolt_raw = str(row.get("Bolt", "M24")).strip().upper()
    bolt_name = bolt_raw if bolt_raw.startswith("M") else f"M{bolt_raw}"

    r_m = float(row.get("ratio_moment", 0.8))
    r_v = float(row.get("ratio_shear", 0.5))
    r_n = float(row.get("ratio_axial", 0.0))

    b_ep = float(row.get("Bp", 200.0))
    p2_ep = float(row.get("g", 100.0))
    pfo = float(row.get("d", 50.0))
    dev = float(row.get("e", 50.0))

    p1 = float(row.get("p1", 0.0))
    p2 = float(row.get("p2", row.get("pb", 80.0)))
    pb = p2

    if p1 > 0:
        pfi = max(0.0, p1 - pfo - viga.tf)
    else:
        pfi = float(row.get("pfi", 30.0))

    p3 = float(row.get("p3", 0.0))
    p4 = float(row.get("p4", 0.0))
    p5 = float(row.get("p5", 0.0))
    p6 = float(row.get("p6", 0.0))
    p7 = float(row.get("p7", 0.0))
    p8 = float(row.get("p8", 0.0))
    p9 = float(row.get("p9", 0.0))
    p10 = float(row.get("p10", 0.0))
    p11 = float(row.get("p11", 0.0))
    p12 = float(row.get("p12", 0.0))

    n_alma = int(row.get("n_alma", 2))
    n_cantonera = int(row.get("n_cantonera", 0))
    nbrtension_ep = n_alma + 2 if "n_alma" in row else 2
    n_total_filas = int(row.get("num_filas_tornillos", n_alma + n_cantonera + 2))

    tp_val = str(row.get("tp", 20))
    ts_val = str(row.get("ts", 0))
    tws_val = str(row.get("tws", 0))
    tbs_val = str(row.get("tbs", 0))

    return ConexionInput(
        viga=viga,
        pilar=pilar,
        fy=fy,
        fu=fu,
        fyp=fy,
        fup=fu,
        BoltName_ep=bolt_name,
        BoltGrade=clase,
        BoltsInTensionFactor=2.0,
        nbrtension_ep_AME=nbrtension_ep,
        NumeTotalFilasTornillos=n_total_filas,
        b_ep=b_ep,
        p2_ep=p2_ep,
        pfo=pfo,
        pfi=pfi,
        dev=dev,
        pb=pb,
        p1=p1,
        p3=p3, p4=p4, p5=p5, p6=p6, p7=p7, p8=p8, p9=p9, p10=p10, p11=p11, p12=p12,
        ThicknessName_t_ep=tp_val,
        ThicknessName_t_tenstiff=ts_val if ts_val != "0" else None,
        ThicknessName_t_webstiff=tws_val if tws_val != "0" else None,
        ThicknessName_t_BeamHcompstiff=tbs_val if tbs_val != "0" else None,
        MzEd_Porcen=r_m * 100.0,
        FyEd_Porcen=r_v * 100.0,
        FxEd_Porcen=r_n * 100.0,
        TipoCombiEnve="LRFD",
        yieldmethod=True,
        Traccion=False,
        SisUniPerMetri=True,
        SisUniPlaMetri=True,
    )


def check_single_row(row: Dict[str, Any]) -> Dict[str, Any]:
    conexion_input = row_to_conexion_input(row)
    calculador = CalculadorAISC36010(inp=conexion_input)
    resultado = calculador.calcular_conexion()

    res_dict = row.copy()

    if "Bolt" in res_dict:
        b_val = str(res_dict["Bolt"]).strip().upper()
        res_dict["Bolt"] = b_val if b_val.startswith("M") else f"M{b_val}"

    res_dict["cumple"] = resultado.cumple
    res_dict["ratio_pesimo"] = round(resultado.ratio_pesimo, 4)
    res_dict["descripcion_ratio_pesimo"] = resultado.descripcion_ratio_pesimo
    res_dict["ratios"] = [f.model_dump() for f in resultado.ratios]
    res_dict["complementarios"] = [c.model_dump() for c in resultado.complementarios]

    return res_dict


def check_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [check_single_row(r) for r in rows]