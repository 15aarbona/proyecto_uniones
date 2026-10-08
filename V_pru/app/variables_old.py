# Generated from: variables_old.ipynb
# Converted at: 2026-10-02T09:56:47.085Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# # PATHS


dir = Path.cwd().parent / "data"
data_excel_path = dir / "CONEXIONES_MOMENTO_ATORNILLADAS_CHAPA_FRONTAL.xlsx"
tekla_excel_path = dir / "Prontuario Tekla19.xlsx"

# # CARGA DE DATOS


data = pd.read_excel(data_excel_path, sheet_name="Sheet1")

data.head(20)

# # DESCRIPCIÓN DE VARIABLES


# - UNICODE: Identificador global de la unión
# - BEAM: Estandar de viga
# - COLUMN: Estandar de columna
# - Capacity_Moment_Percentage: Porcentaje de momento
# - Capacity_Moment: Momento
# - Capacity_Shear_Percentage: Porcentaje de capacidad de fractura
# - Capacity_Shear: Capacidad de fractura
# - Capacity_Axial_Percentage: porcentaje de capacidad axial
# - Capacity_Axial: Capacidad axial
# - Pr_Porcen: 
# - DrawingCode: 
# - g: Distancia entre los centros de los tornillos
# - tws: Grosor chapa columna
# - Lws: Alto chapa columna
# - Bws: Ancho chapa columna
# - Bp: Ancho chapa tornillos
# - Lp: Alto chapa tornillos
# - tp: Grosor chapa tornillos
# - Lh: Altura viga-
# - e: Distancia borde chapa-primer tornillo
# - d: Distancia tornillo-ala viga
# - pfo: Todo nulls (descarte directo)
# - pX: Distancia entre tornillo x y x+1
# - ts: Grosor rigidizdor columna
# - tbs: Grosor rigidizador viga
# - tst: Grosor rigidizador columna-viga (union viga-columna)
# - thw: 
# - thf:
# - wX:
# - Bolt: Estandar grosor tornillos
# - Hole: Agujero tornillos
# - SlipCritical: Necesidad de 
# - Normativas: Normativa
# - AceroEstructural: Tipo de acero utilizado
# - ElectrodoSoldadura: Tipo de soldadura
# - EstandarTornillos: Estandar Tornillos
# - Ordinary_Moment_Frames: 
# - Calculation_Tool: Herramienta de cálculo utilizado
# - Source: Región
# - Designation: Designación
# - rib_thk:
# - Representation_Angle:
# - BoltConnectionTypeSelection:
# - National_Annex: Anexo nacional (excepciones en designaciones)
# - p0:
# - tso:
# - Lst:
# - SpecialMomentFrames:
# - MzEd_PanelZone:
# - Vgra: 
# - Havg:
# - Yieldmethod:
# - Acero_Estructural_Perfil: 


# Veamos los tipos de las clases y sus valores:


for index, row in data.dtypes.items():
    print(f"{index}: {row}")

# Vemos que algunas wX son de tipo Object, debido a que los 0 son -.


data.replace("-", 0, inplace=True)
data[["w3", "w4", "w5", "w6"]] = data[["w3", "w4", "w5", "w6"]].astype(np.int64)

for index, row in data.dtypes.items():
    print(f"{index}: {row}")

# Separamos por tipo de columna


numerical_columns = data.select_dtypes(include=[np.number]).columns.tolist()
categorical_columns = data.select_dtypes(include=['object', "str", "bool"]).columns.tolist()

numerical_df = data[numerical_columns]
categorical_df = data[categorical_columns]

# Vamos a analizar las columnas por su tipo de dato.


# ## COLUMNAS NUMÉRICAS


numerical_df.head()

numerical_df.columns

# ## CAPACIDADES Y PORCENTAJES


# Estas variables indican las cargas, pero son datos redundantes entre sí, por lo que nos quedamos solo con no porcentajes.


# numerical_df.drop(columns=['Capacity_Moment', 'Capacity_Shear', 'Capacity_Axial'], inplace=True)

# ## VALORES NULOS, IGUALES O A 0


# Vemos que la columna "Pr_Porcen" tiene siempre el valor 50, por lo que podemos eliminarla


describe = numerical_df.describe().transpose()

# Veamos si alguna fila tiene todos los valores a 0:


for row in describe.iterrows():
    if row[1]["mean"] == 0:
        print(f"Row {row[0]} values are 0")

numerical_df.Representation_Angle.value_counts()

numerical_df.BoltConnectionTypeSelection.value_counts()

numerical_df.rib_thk.value_counts()

# Vemos que "Representation_Angle", "rib_thk" y "BoltConnectionTypeSelection" tienen todos los valores a 0, por lo que no serán relevantes para el modelo.


numerical_df.isna().sum()

# Vemos que pfo tiene todos sus valores a Na, por lo que la descartaremos.


numerical_df.drop(columns=["Pr_Porcen", "Representation_Angle", "rib_thk", "BoltConnectionTypeSelection", "pfo"], inplace=True)
numerical_df.head()

# ## CHAPA DE LA COLUMNA


# Siguiendo indicaciones, podemos eliminar ancho y largo de la plancha que se pone en la columna (si aplica), ya que solo nos interesa su grosor


numerical_df.drop(columns=["Lws", "Bws"], inplace=True)

# Comentar que si no tiene esta chapa, el valor será 0. Se determinará un mínimo para el grosor.


# ## CANTONERA y SOLDADURA


# Se deduce de las filas de tornillos.


# Sabemos que las variables wX y thw se refieren a propiedades de soldado, que no vamos a utilizar, por lo que podemos eliminarlas


# Hecho esto, eliminamos las medidas:


numerical_df.drop(columns=["thw", "thf", "w1", "w2", "w3", "w4", "w5", "w6"], inplace=True)

# ## RIGIDIZADORES


# Los rigidizadores tienen medidas en función de la columna y viga y, en principio, siempre aparecene, por lo que lo relacionado con ello se elimina


numerical_df.drop(columns=["tso", "Lst"], inplace=True)

numerical_df.columns

# # QUITAR SPECIAL


# ## COLUMNAS CATEGÓRICAS


categorical_df.columns

# Veamos un poco las categorías


# ## NORMATIVA (PARA LAS MEDIDAS)


# Quien va a identificar el estandar va a ser la combinación Normativas-National_Annex


categorical_df["National_Annex"] = categorical_df["National_Annex"].replace(0, "", inplace=True)

categorical_df["National_Annex"].value_counts()

categorical_df["standard"] = (
    categorical_df["Normativas"].fillna("").astype(str)
    + categorical_df["National_Annex"].map(lambda x: f" - {x}" if x else "")
)

categorical_df[categorical_df["National_Annex"] != ""].head()

#categorical_df.drop(columns=["Normativas", "National_Annex"], inplace=True)

categorical_df.head()

# Con esto, junto a al código de columna o viga sabremos las medidas de estas.


# ## SOLDADURAS


# Como hemos hecho en las variables numéricas, eliminamos todas las columnas relacionadas con las soldaduras


categorical_df.drop(columns=["ElectrodoSoldadura"], inplace=True)

# ## OTRAS VARIABLES A ELIMINAR


# La herramienta de cálculo es irrelevante, por lo que la eliminamos.
# 
# Todas las designaciones son "Tekla19", por lo que la eliminamos.


categorical_df.drop(columns=["Calculation_Tool", "Designation", 
'MzEd_PanelZone', 'Vgra', 'Havg', 'Ordinary_Moment_Frames', 'Acero_Estructural_Perfil'], inplace=True)

categorical_df.columns

numerical_df.drop(columns=["Yieldmethod"], inplace=True)

# # DATAFRAME FINAL


df_final = pd.concat([numerical_df, categorical_df], axis=1)

df_final.head()

# Vamos a poner el unicode como identificador de las filas, que son únicas dentro de nuestro sistema.


df_final.set_index("Unicode", inplace=True)

df_final.head()

df_final.columns

# # QUITAR FILAS SPECIALMOMENTFRAMES VERDADERO


df_final.shape

df_final_c = df_final[df_final["SpecialMomentFrames"] != 1]

df_final_c.shape

(df_final_c["p0"] > 0).sum()

df_final = df_final_c.drop(columns=["p0", "SpecialMomentFrames"])

# # AÑADIR DATOS DE TEKLA


xls = pd.ExcelFile(dir / "Prontuario Tekla19.xlsx")
eu = pd.read_excel(xls, 'Tekla19 europeo')
cad = pd.read_excel(xls, 'Tekla19 canadiense')
resto = pd.read_csv(dir / "tekla_faltante.csv")

df_union = pd.concat([eu, cad, resto])
df_union = df_union[["tekla_nomenclature_1", "type", "d_mm", 
        "bf_mm", "tw_mm", "tf_mm", "r1_mm", "wely_mm", "w_kgm"
        ]]

df_union.dtypes

faltan_BEAM = set(df_final["BEAM"].unique()) - set(df_union["tekla_nomenclature_1"].unique())
faltan_COLUMN = set(df_final["COLUMN"].unique()) - set(df_union["tekla_nomenclature_1"].unique())

faltan_BEAM | faltan_COLUMN

union_BEAM = (df_union.set_index('tekla_nomenclature_1')
    .add_prefix('BEAM_')
    .reset_index()
)

union_COLUMN = (df_union.set_index('tekla_nomenclature_1')
    .add_prefix('COLUMN_')
    .reset_index()
)
union_BEAM

df_final.shape

df_merge1 = pd.merge(df_final, union_BEAM, left_on="BEAM", right_on="tekla_nomenclature_1").drop(columns=["tekla_nomenclature_1"])
df_merge2 = pd.merge(df_merge1, union_COLUMN, left_on="COLUMN", right_on="tekla_nomenclature_1").drop(columns=["tekla_nomenclature_1"])
df_merge2

df_merge2.drop(columns=["BEAM_r1_mm", "BEAM_wely_mm", "BEAM_w_kgm","COLUMN_r1_mm", "COLUMN_wely_mm", "COLUMN_w_kgm"],
                inplace=True)

# # AÑADIR RESISTENCIAS ACERO Y TORNILLOS


df_aceros = pd.DataFrame([
    {
        "grado_acero": "S275JR",
        "fy_acero_mpa": 275.0,  # Límite elástico (MPa)
        "fu_acero_mpa": 430.0   # Resistencia a tracción (MPa)
    },
    {
        "grado_acero": "S355JR",
        "fy_acero_mpa": 355.0,
        "fu_acero_mpa": 490.0
    }
])

df_tornillos = pd.DataFrame([
    {
        "clase_tornillo": "8.8",
        "fy_tornillo_mpa": 640.0,  # Límite elástico (MPa) - Corregido
        "fu_tornillo_mpa": 800.0,  # Resistencia a tracción (MPa)
        "fv_tornillo_mpa": 480.0   # Resistencia a cortante (MPa)
    },
    {
        "clase_tornillo": "10.9",
        "fy_tornillo_mpa": 900.0,
        "fu_tornillo_mpa": 1000.0,
        "fv_tornillo_mpa": 500.0
    },
    {
        "clase_tornillo": "A325M",
        "fy_tornillo_mpa": 660.0,
        "fu_tornillo_mpa": 830.0,
        "fv_tornillo_mpa": 372.0
    }
])

df_merge2.shape

df_final2 = pd.merge(df_merge2, df_aceros, left_on="AceroEstructural", right_on="grado_acero")
df_final2.shape

df_final2['EstandarTornillos'] = df_final2['EstandarTornillos'].replace({ 'ASTM A325': "A325M"}).astype(str)

df_final3 = pd.merge(df_final2, df_tornillos, left_on="EstandarTornillos", right_on="clase_tornillo")
df_final3.shape

df_final3.drop(columns=["grado_acero", "clase_tornillo"], inplace=True)

df_final3.columns

# ## DISTANCIAS


# de int a float
int_a_float = ['p6',
"p7",
'p8',
'p9',
'p10',
'p11',
'p12']

for col in int_a_float:
    df_final3[col] = df_final3[col].astype(float)

import numpy as np
import pandas as pd


def transformar_topologia_y_cotas(df):
    """Transforma pasos relativos (p_i) en cotas absolutas desde el borde

    superior de la chapa (Y_i = e + sum(p_k)) y clasifica filas por zona
    viga.
    """
    p_cols = [f'p{i}' for i in range(1, 13)]

    def procesar_fila(row):
        pasos = [
            row[col] for col in p_cols if pd.notna(row[col]) and row[col] > 0
        ]
        n_filas = len(pasos) + 1 if pd.notna(row.get('e')) else 0

        res = {
            'n_sup': 0,
            'n_alma': 0,
            'n_cantonera': 0,
            'n_inf': 0,
            'num_filas': n_filas,
        }

        # Inicializamos 12 cotas Y1..Y12 (correspondientes al tornillo final de cada paso p1..p12)
        for i in range(1, 13):
            res[f'Y{i}'] = 0.0

        if n_filas < 2:
            return pd.Series(res)

        # 1. Cotas Absolutas (Origen Y=0 en Borde Superior de la Chapa)
        e = row['e']
        Y_coords = [e]  # Fila 1 está en cota 'e'

        # Y1 = e + p1, Y2 = e + p1 + p2...
        y_acum = e
        for p in pasos:
            y_acum += p
            Y_coords.append(y_acum)

        # Guardar en Y1..Y12 (Y_coords tiene len = n_filas)
        for idx, y_val in enumerate(Y_coords[1:], start=1):
            res[f'Y{idx}'] = y_val

        # 2. Fronteras físicas de la viga
        d = row.get('d', 0)
        h_beam = row['BEAM_d_mm']

        y_ala_sup = e + d
        y_ala_inf = e + d + h_beam

        # 3. Clasificación topológica por zonas
        n_debajo = 0
        for y_val in Y_coords:
            if y_val < y_ala_sup:
                res['n_sup'] += 1  # Tornillos por encima de la viga
            elif y_val <= y_ala_inf:
                res['n_alma'] += 1  # Tornillos entre las alas
            else:
                n_debajo += 1  # Tornillos por debajo de la viga

        # 4. Desglose cantonera / fuera
        if n_debajo > 0:
            res['n_inf'] = 1
            res['n_cantonera'] = n_debajo - 1
        else:
            res['n_inf'] = 0
            res['n_cantonera'] = 0

        return pd.Series(res)

    df_transformado = df.apply(procesar_fila, axis=1)
    return pd.concat([df, df_transformado], axis=1)


# ==============================================================================
# FUNCIÓN INVERSA PARA RECUPERAR LOS PASOS p_i DE TALLER
# ==============================================================================
def convertir_cotas_a_pasos(df_prediccion):
    """Convierte cotas absolutas Y1..Y12 y borde 'e' de vuelta a pasos relativos

    p1..p12.
    """
    df_res = df_prediccion.copy()

    # p1 = Y1 - e
    if 'Y1' in df_res.columns and 'e' in df_res.columns:
        mask_y1 = df_res['Y1'] > 0
        df_res.loc[mask_y1, 'p1'] = (
            df_res.loc[mask_y1, 'Y1'] - df_res.loc[mask_y1, 'e']
        )
        df_res.loc[~mask_y1, 'p1'] = 0.0

    # p_i = Y_i - Y_{i-1} para i >= 2
    for i in range(2, 13):
        col_actual = f'Y{i}'
        col_anterior = f'Y{i-1}'
        col_paso = f'p{i}'

        if col_actual in df_res.columns and col_anterior in df_res.columns:
            mask_existe = df_res[col_actual] > 0
            df_res.loc[mask_existe, col_paso] = (
                df_res.loc[mask_existe, col_actual]
                - df_res.loc[mask_existe, col_anterior]
            )
            df_res.loc[~mask_existe, col_paso] = 0.0

    return df_res

df_resultado = transformar_topologia_y_cotas(df_final3)

df_resultado.columns

df_resultado.drop(columns=['n_sup', 'n_inf', 'num_filas', 'Y1', 'Y2', 'Y3', 'Y4', 'Y5', 'Y6', 'Y7', 'Y8',
       'Y9', 'Y10', 'Y11', 'Y12'], inplace=True)

cols_drop = [
    'BEAM_type', 'COLUMN_type'
]

df_resultado.drop(columns=cols_drop, inplace=True)

# # REVISAR TIPOS


for index, row in df_resultado.dtypes.items():
    print(f"{index}: {row}")

df_final3 = df_resultado

df_final3["Bolt"] = df_final3["Bolt"].str.strip().str.replace("M", "").astype(int)

df_final3["SlipCritical"] = (df_final3["SlipCritical"] == 'YES')

for index, row in df_final3.dtypes.items():
    print(f"{index}: {row}")

df_final3.isna().sum().sum()

# # TRAIN, TEST SPLIT


df_resultado.loc[df_resultado["Lh"]<0,"Lh"] = 0

df_resultado.columns

df_resultado.to_csv(dir / "data_final.csv", sep=";")

df_train, df_test = train_test_split(df_resultado, test_size=0.2, random_state=2)

df_train.shape, df_test.shape

df_train.columns

df_train.to_parquet(dir / "train_final.parquet")
df_test.to_parquet(dir / "test_final.parquet")

import pyarrow
print(pyarrow.__version__)   



df = pd.read_parquet("data" / "train.parquet")