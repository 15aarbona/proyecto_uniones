import torch
import torch.nn as nn
class ConnectionDesignLoss(nn.Module):
    def __init__(self,w_cls=1.,w_reg=1.,w_p_label=1.5,w_masked=2.): super().__init__(); self.ws=(w_cls,w_reg,w_p_label,w_masked); self.ce=nn.CrossEntropyLoss(); self.bce=nn.BCEWithLogitsLoss(); self.huber=nn.SmoothL1Loss(reduction='none')
    def forward(self,p,t):
        cls=self.ce(p['drawing_logits'],t['drawing_idx'])+self.ce(p['bolt_logits'],t['bolt_idx'])+self.bce(p['slip_logit'],t['slip'])
        reg=self.huber(p['reg'],t['reg']).mean(); pl=self.ce(p['p_label_logits'].flatten(0,1),t['p_label_idx'].flatten())
        mask=t['masked_mask']; mv=(self.huber(p['masked_value'],t['masked_value'])*mask).sum()/mask.sum().clamp_min(1)
        total=self.ws[0]*cls+self.ws[1]*reg+self.ws[2]*pl+self.ws[3]*mv
        return total,{"classification":cls.item(),"regression":reg.item(),"p_labels":pl.item(),"masked_values":mv.item()}