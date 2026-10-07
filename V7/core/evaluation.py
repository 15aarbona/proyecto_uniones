import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from .config import REGRESSION_ALWAYS, MASKED_COLUMNS, P_COLUMNS, N_Y

def preparar_para_evaluar(test_df, full_design):
    cols = REGRESSION_ALWAYS + MASKED_COLUMNS
    real = test_df[cols].apply(pd.to_numeric, errors="coerce").fillna(0).reset_index(drop=True)
    pred = full_design[cols].apply(pd.to_numeric, errors="coerce").fillna(0).reset_index(drop=True)
    return real, pred

def evaluar_predicciones(df_real, df_pred, tol_taller=(5.0, 10.0)):
    rows=[]
    for col in [c for c in df_real.columns if c in df_pred.columns]:
        y=df_real[col].to_numpy(); p=df_pred[col].to_numpy()
        if col in MASKED_COLUMNS:
            active=y>0
            if active.sum()==0: continue
            y,p=y[active],p[active]
        err=np.abs(y-p)
        r2=r2_score(y,p) if len(y)>1 and np.std(y)>0 else np.nan
        rows.append({"Variable":col,"N":len(y),"MAE_mm":mean_absolute_error(y,p),
                     "RMSE_mm":np.sqrt(mean_squared_error(y,p)),"R2":r2,
                     "pct_5mm":100*np.mean(err<=tol_taller[0]),
                     "pct_10mm":100*np.mean(err<=tol_taller[1])})
    result=pd.DataFrame(rows)
    print(result.round(3).to_string(index=False))
    return result

def evaluar_estructura(test_df, design):
    real_na=test_df["n_alma"].astype(int).to_numpy(); pred_na=design["n_alma"].astype(int).to_numpy()
    real_nc=test_df["n_cantonera"].astype(int).to_numpy(); pred_nc=design["n_cantonera"].astype(int).to_numpy()
    result={"n_alma_exacto":np.mean(real_na==pred_na),
            "n_cantonera_exacto":np.mean(real_nc==pred_nc),
            "ambos_exactos":np.mean((real_na==pred_na)&(real_nc==pred_nc))}
    print(pd.Series(result).to_string())
    return result

def evaluar_sesgo_p(test_df, design):
    rows=[]
    for col in P_COLUMNS:
        y=test_df[col].fillna(0).to_numpy(float); p=design[col].fillna(0).to_numpy(float)
        active=y>0
        if active.sum()==0: continue
        e=p[active]-y[active]
        rows.append({"Variable":col,"N":active.sum(),"MAE_mm":np.abs(e).mean(),
                     "sesgo_mm":e.mean(),"subestimadas_pct":100*np.mean(e<0),
                     "subestimadas_mas_10_pct":100*np.mean(e<-10)})
    return pd.DataFrame(rows)

def evaluar_acumulado_y(test_df, design):
    real=test_df[P_COLUMNS].fillna(0).to_numpy(float)
    pred=design[P_COLUMNS].fillna(0).to_numpy(float)
    active=real>0
    real_y=np.cumsum(real,axis=1); pred_y=np.cumsum(pred,axis=1)
    err=np.abs(pred_y-real_y)
    rows=[]
    for j,col in enumerate(P_COLUMNS):
        m=active[:,j]
        if m.sum():
            rows.append({"Y_hasta":col,"N":m.sum(),"MAE_acumulado_mm":err[m,j].mean(),
                         "pct_10mm":100*np.mean(err[m,j]<=10),"pct_20mm":100*np.mean(err[m,j]<=20)})
    return pd.DataFrame(rows)

def evaluar_por_transicion(test_df, design):
    records=[]
    for i,col in enumerate(P_COLUMNS,1):
        y=test_df[col].fillna(0).to_numpy(float); p=design[col].fillna(0).to_numpy(float)
        tcol=f"p{i}_transition"
        trans=(test_df[tcol] if tcol in test_df.columns else design[tcol]).astype(str).to_numpy()
        for row in np.where(y>0)[0]:
            e=p[row]-y[row]
            records.append({"transicion":trans[row],"error_mm":e,"abs_error_mm":abs(e)})
    detail=pd.DataFrame(records)
    summary=(detail.groupby("transicion").agg(
        N=("error_mm","size"),MAE_mm=("abs_error_mm","mean"),sesgo_mm=("error_mm","mean"),
        dentro_10_pct=("abs_error_mm",lambda x:100*np.mean(x<=10)),
        subestimadas_mas_10_pct=("error_mm",lambda x:100*np.mean(x<-10))).reset_index())
    return summary.sort_values("dentro_10_pct"),detail
