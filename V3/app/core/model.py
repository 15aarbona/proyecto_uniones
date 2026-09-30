import torch
import torch.nn as nn
from .config import CATALOGO_BOLT, REGRESSION_ALWAYS, MASKED_VALUE_COLUMNS, P_COLUMNS
class Block(nn.Module):
    def __init__(self,d,drop=.1):
        super().__init__(); self.net=nn.Sequential(nn.Linear(d,d),nn.BatchNorm1d(d),nn.ReLU(),nn.Dropout(drop),nn.Linear(d,d),nn.BatchNorm1d(d))
    def forward(self,x): return torch.relu(x+self.net(x))
class ConnectionDesignNet(nn.Module):
    def __init__(self,cat_cardinalities,num_continuous,n_drawing_codes,n_p_labels,hidden_dim=192,num_blocks=3,dropout=.1):
        super().__init__(); dims=[min(16,(c+1)//2) for c in cat_cardinalities]
        self.emb=nn.ModuleList([nn.Embedding(c,d) for c,d in zip(cat_cardinalities,dims)])
        self.input=nn.Sequential(nn.Linear(sum(dims)+num_continuous,hidden_dim),nn.BatchNorm1d(hidden_dim),nn.ReLU())
        self.blocks=nn.ModuleList([Block(hidden_dim,dropout) for _ in range(num_blocks)])
        self.drawing=nn.Linear(hidden_dim,n_drawing_codes); self.bolt=nn.Linear(hidden_dim,len(CATALOGO_BOLT)); self.slip=nn.Linear(hidden_dim,1)
        self.reg=nn.Linear(hidden_dim,len(REGRESSION_ALWAYS)); self.p_labels=nn.Linear(hidden_dim,len(P_COLUMNS)*n_p_labels)
        self.masked=nn.Linear(hidden_dim,len(MASKED_VALUE_COLUMNS)); self.n_p_labels=n_p_labels
    def forward(self,x_cat,x_num):
        x=self.input(torch.cat([e(x_cat[:,i]) for i,e in enumerate(self.emb)]+[x_num],1))
        for b in self.blocks:x=b(x)
        return {"drawing_logits":self.drawing(x),"bolt_logits":self.bolt(x),"slip_logit":self.slip(x).squeeze(-1),"reg":self.reg(x),"p_label_logits":self.p_labels(x).view(-1,len(P_COLUMNS),self.n_p_labels),"masked_value":self.masked(x)}