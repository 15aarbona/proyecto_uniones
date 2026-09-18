import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import OrdinalEncoder

DATA_PATH = Path().cwd() / "data"

class DataProcessor:
    def __init__(self, data_path: Path=DATA_PATH):
        self.df = pd.read_csv(data_path / "data.csv", low_memory=False) # global data
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
        if "Unicode" in self.df.columns:
            self.df.set_index("Unicode", inplace=True)

        # type changes
        self.df.replace("-", 0, inplace=True)
        self.df[["w3", "w4", "w5", "w6"]] = self.df[["w3", "w4", "w5", "w6"]].astype(np.int64)

        # bracing existence
        self.df["arriostramiento"] = (self.df["Lh"] != 0).astype(int)

        # normative code
        self.df["National_Annex"] = self.df["National_Annex"].replace(0, "")
        self.df["standard"] = (
            self.df["Normativas"].fillna("").astype(str)
            + self.df["National_Annex"].map(lambda x: f" - {x}" if x else "")
        )

        # Bolt distances
        cols_p = [c for c in ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12"]]
        df_abs = self.df[cols_p].cumsum(axis=1).add(self.df['e'], axis=0)
        df_abs.columns = [f'pos_{c}' for c in cols_p]
        self.df = pd.concat([self.df, df_abs], axis=1)

        # drop unuseful columns
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
            "Designation"
        ] + cols_p, inplace=True)

        
        self.df[["DrawingCode", "Bolt", "Hole", "SlipCritical"]] = self.encoder.fit_transform(self.df[["DrawingCode", "Bolt", "Hole", "SlipCritical"]])

        if verbose:
            self.print()

        if save:
            self.df.to_csv(DATA_PATH / "processed_data.csv", index=True)



if __name__ == "__main__":
    P = DataProcessor()

    P.process_data(1, 1)

    P.print()


