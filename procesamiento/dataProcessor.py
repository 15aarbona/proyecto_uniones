import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import OrdinalEncoder

DATA_PATH = Path().cwd() / "data"

class DataProcessor:
    def __init__(self, data_path: Path=DATA_PATH):
        self.df = pd.read_csv(data_path / "data.csv", low_memory=False) # global data

        eu = pd.read_csv(data_path / "tekla_eu.csv")
        cad = pd.read_csv(data_path / "tekla_cad.csv")
        resto = pd.read_csv(data_path / "tekla_faltante.csv")

        self.tekla = pd.concat([eu, cad, resto])

        self.aceros = pd.DataFrame([
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

        self.tornillos = pd.DataFrame([
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

        self.encoder = OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1)

    def print(self, lines: str=10):
        self.df.head(lines)

    def add_new_data(self, names: str | list[str], verbose: int=0, lines: int=0):
        names_list: list[str] = [names] if isinstance(names, str) else names

        dfs = [self.df]

        for name in names_list:
            new_df = pd.read_csv(DATA_PATH / name, low_memory=False)
            dfs.append(new_df)

        self.df = pd.concat(dfs, ignore_index=True)

        if verbose:
            self.print(lines=lines)

        self.df.to_csv(DATA_PATH / 'data.csv', index=False)


    def process_data(self, verbose: int=0, save: int=0):
        def include_tekla_data():
            self.tekla = self.tekla[["tekla_nomenclature_1", "type", "d_mm", 
                    "bf_mm", "tw_mm", "tf_mm", "r1_mm", "wely_mm", "w_kgm"
                    ]]

            union_BEAM = (self.tekla.set_index('tekla_nomenclature_1')
                .add_prefix('BEAM_')
                .reset_index()
            )

            union_COLUMN = (self.tekla.set_index('tekla_nomenclature_1')
                .add_prefix('COLUMN_')
                .reset_index()
            )

            self.df = pd.merge(self.df, union_BEAM, left_on="BEAM", right_on="tekla_nomenclature_1").drop(columns=["tekla_nomenclature_1"])
            self.df = pd.merge(self.df, union_COLUMN, left_on="COLUMN", right_on="tekla_nomenclature_1").drop(columns=["tekla_nomenclature_1"])

        def include_screw_info():
            self.df = pd.merge(self.df, self.aceros, left_on="AceroEstructural", right_on="grado_acero")
            self.df['EstandarTornillos'] = self.df['EstandarTornillos'].replace({ 'ASTM A325': "A325M"}).astype(str)
            self.df = pd.merge(self.df, self.tornillos, left_on="EstandarTornillos", right_on="clase_tornillo")


        if "Unicode" in self.df.columns:
            self.df.set_index("Unicode", inplace=True)

        # type changes
        if verbose: print("Type changes\n")
        self.df.replace("-", 0, inplace=True)
        self.df[["w3", "w4", "w5", "w6"]] = self.df[["w3", "w4", "w5", "w6"]].astype(np.int64)

        self.df["SlipCritical"] = (self.df["SlipCritical"] == "TRUE").astype(int)

        # normative code
        if verbose: print("Normative\n")
        self.df["National_Annex"] = self.df["National_Annex"].replace(0, "")
        self.df["standard"] = (
            self.df["Normativas"].fillna("").astype(str)
            + self.df["National_Annex"].map(lambda x: f" - {x}" if x else "")
        )

        # Bolt distances
        if verbose: print("Bolt distances\n")
        cols_p = [c for c in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12"]]

        df_abs = self.df[cols_p].cumsum(axis=1).add(self.df['e'], axis=0)
        df_abs.columns = [f'pos_{c}' for c in cols_p]
        self.df = pd.concat([self.df, df_abs], axis=1)

        self.df[cols_p] = self.df[cols_p].astype(float)

        self.df["Bolt"] = self.df["Bolt"].str.strip().str.replace("M", "").astype(int)

        # drop specialmomentframes=true
        self.df = self.df[self.df["SpecialMomentFrames"] != 1]

        # include tekla
        include_tekla_data()

        # include screw
        include_screw_info()

         # drop unuseful columns
        if verbose: print("Drop columns\n")
        self.df.drop(columns=[
            'Capacity_Moment', 'Capacity_Shear', 
            'Capacity_Axial', 'Pr_Porcen', 
            'Representation_Angle', 'rib_thk', 
            'BoltConnectionTypeSelection', 'pfo',
            "Lws", "Bws",
            "Lh", "thw", 
            "thf", "w1", 
            "w2", "w3", 
            "w4", "w5", 
            "w6", "tst", 
            "ts", "tbs",
            "Normativas", "National_Annex",
            "ElectrodoSoldadura", "Calculation_Tool", 
            "Designation", "p0",
            "SpecialMomentFrames", "grado_acero",
            "clase_tornillo"
        ] + cols_p, inplace=True)

        if verbose: print("Encoding")
        self.df[["DrawingCode", "Hole", "SlipCritical"]] = self.encoder.fit_transform(self.df[["DrawingCode", "Hole", "SlipCritical"]])

        if verbose:
            self.print()

        if save:
            self.df.reset_index().to_csv(DATA_PATH / "processed_data.csv", index=False)



if __name__ == "__main__":
    P = DataProcessor()

    P.process_data(1, 1)

    P.print()


