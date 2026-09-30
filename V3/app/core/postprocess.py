import numpy as np
import pandas as pd
from .config import CATALOGO_BOLT, CATALOGS, REGRESSION_ALWAYS, P_COLUMNS, P_LABEL_COLUMNS, STIFFENER_COLUMNS, MASKED_VALUE_COLUMNS
def snap(x,cat):
    if cat is None:return x
    a=np.asarray(cat,float); return a[np.abs(x[:,None]-a).argmin(1)]
def decode(outputs,pre):
    reg=pre.inverse_reg(outputs['reg']); vals=pre.inverse_masked(outputs['masked_value']); out={}
    for j,c in enumerate(REGRESSION_ALWAYS):out[c]=snap(reg[:,j],CATALOGS.get(c))
    label_idx=outputs['p_label_logits'].argmax(2); labels=pre.p_label_encoder.inverse_transform(label_idx.ravel()).reshape(label_idx.shape)
    # La secuencia física es contigua: después del primer UNUSED no puede reaparecer una fila.
    for i in range(len(labels)):
        unused = np.flatnonzero(labels[i] == 'UNUSED')
        if len(unused): labels[i, unused[0]:] = 'UNUSED'
    for j,(pc,lc) in enumerate(zip(P_COLUMNS,P_LABEL_COLUMNS)):
        out[lc]=labels[:,j]; out[pc]=np.where(labels[:,j]=='UNUSED',0,np.round(vals[:,j]/5)*5)
    for k,c in enumerate(STIFFENER_COLUMNS,start=len(P_COLUMNS)):
        # Los rigidizadores no tienen etiqueta; presencia se deduce de valor positivo y catálogo.
        out[c]=snap(np.maximum(vals[:,k],0),CATALOGS[c])
    out['DrawingCode']=pre.drawing_encoder.classes_[outputs['drawing_logits'].argmax(1)]
    b=np.asarray(CATALOGO_BOLT)[outputs['bolt_logits'].argmax(1)]; out['Bolt']=[f'M{x}' for x in b]
    out['SlipCritical']=np.where(outputs['slip_logit']>=0,'YES','NO'); out['Hole']=b+2
    out['num_filas_tornillos']=(labels!='UNUSED').sum(1)+1
    out['tiene_cantonera']=np.any(np.char.startswith(labels.astype(str),'HAUNCH'),axis=1)
    return pd.DataFrame(out)