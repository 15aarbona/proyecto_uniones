import numpy as np
import torch
from torch.utils.data import Dataset
from sklearn.preprocessing import StandardScaler, OrdinalEncoder, LabelEncoder
from config import CATEGORICAL_FEATURES, NUMERIC_FEATURES, REGRESSION_ALWAYS, MASKED_VALUE_COLUMNS, P_LABEL_COLUMNS, CATALOGO_BOLT

class Preprocessor:
    def fit(self, df):
        # unknown_value permite inferir con categorías nuevas sin abortar.
        self.cat_encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        self.cat_encoder.fit(df[CATEGORICAL_FEATURES].fillna("UNKNOWN").astype(str))
        self.num_scaler = StandardScaler().fit(df[NUMERIC_FEATURES].astype(float))
        self.reg_scaler = StandardScaler().fit(df[REGRESSION_ALWAYS].astype(float))
        self.drawing_encoder = LabelEncoder().fit(df["DrawingCode"].astype(str))
        labels = df[P_LABEL_COLUMNS].fillna("UNUSED").astype(str).to_numpy().ravel()
        self.p_label_encoder = LabelEncoder().fit(np.append(labels, "UNUSED"))
        m = df[MASKED_VALUE_COLUMNS].fillna(0).astype(float).to_numpy()
        self.masked_mean=np.zeros(m.shape[1]); self.masked_std=np.ones(m.shape[1])
        active = self._value_mask(df)
        for j in range(m.shape[1]):
            x=m[active[:,j],j]
            if len(x)>1: self.masked_mean[j],self.masked_std[j]=x.mean(),max(x.std(),1e-6)
        return self
    @property
    def cat_cardinalities(self): return [len(x)+1 for x in self.cat_encoder.categories_]
    @property
    def n_drawing_codes(self): return len(self.drawing_encoder.classes_)
    @property
    def n_p_labels(self): return len(self.p_label_encoder.classes_)
    def transform_features(self,df):
        cat=self.cat_encoder.transform(df[CATEGORICAL_FEATURES].fillna("UNKNOWN").astype(str)).astype(np.int64)+1
        num=self.num_scaler.transform(df[NUMERIC_FEATURES].astype(float)).astype(np.float32)
        return cat,num
    def _value_mask(self,df):
        p=(df[P_LABEL_COLUMNS].fillna("UNUSED").astype(str).to_numpy()!="UNUSED")
        s=(df[["tws","ts","tbs","tst"]].fillna(0).astype(float).to_numpy()>0)
        return np.concatenate([p,s],axis=1)
    def transform_targets(self,df):
        bolt=df["Bolt"].astype(str).str.replace("M","",regex=False).astype(int)
        bolt_map={v:i for i,v in enumerate(CATALOGO_BOLT)}
        labels=df[P_LABEL_COLUMNS].fillna("UNUSED").astype(str).to_numpy()
        p_idx=self.p_label_encoder.transform(labels.ravel()).reshape(labels.shape)
        vals=df[MASKED_VALUE_COLUMNS].fillna(0).astype(float).to_numpy()
        mask=self._value_mask(df).astype(np.float32)
        return {
          "drawing_idx":self.drawing_encoder.transform(df["DrawingCode"].astype(str)).astype(np.int64),
          "bolt_idx":bolt.map(bolt_map).to_numpy(dtype=np.int64),
          "slip":(df["SlipCritical"].astype(str).str.upper()=="YES").to_numpy(dtype=np.float32),
          "reg":self.reg_scaler.transform(df[REGRESSION_ALWAYS].astype(float)).astype(np.float32),
          "p_label_idx":p_idx.astype(np.int64),
          "masked_value":((vals-self.masked_mean)/self.masked_std).astype(np.float32),
          "masked_mask":mask,
        }
    def inverse_reg(self,x): return self.reg_scaler.inverse_transform(x)
    def inverse_masked(self,x): return x*self.masked_std+self.masked_mean

class ConnectionDataset(Dataset):
    def __init__(self,df,pre): self.x_cat,self.x_num=pre.transform_features(df); self.y=pre.transform_targets(df)
    def __len__(self): return len(self.x_cat)
    def __getitem__(self,i):
        out={"x_cat":torch.tensor(self.x_cat[i],dtype=torch.long),"x_num":torch.tensor(self.x_num[i],dtype=torch.float32)}
        for k,v in self.y.items(): out[k]=torch.tensor(v[i])
        return out
