import copy, numpy as np, torch
def _epoch(model,loader,loss_fn,device,opt=None):
    model.train(opt is not None); sums={}; total=0
    for b in loader:
        x1=b.pop('x_cat').to(device); x2=b.pop('x_num').to(device); y={k:v.to(device) for k,v in b.items()}
        with torch.set_grad_enabled(opt is not None):
            loss,parts=loss_fn(model(x1,x2),y)
            if opt: opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),5); opt.step()
        total+=loss.item()
        for k,v in parts.items():sums[k]=sums.get(k,0)+v
    n=len(loader); return total/n,{k:v/n for k,v in sums.items()}
def fit(model,tr,va,loss_fn,device,epochs=150,lr=2e-3):
    opt=torch.optim.AdamW(model.parameters(),lr=lr,weight_decay=1e-4); hist={'train_loss':[],'val_loss':[],'train_parts':[],'val_parts':[],'best_epoch':0}; best=(float('inf'),None)
    for ep in range(epochs):
        a,ap=_epoch(model,tr,loss_fn,device,opt); b,bp=_epoch(model,va,loss_fn,device); hist['train_loss'].append(a);hist['val_loss'].append(b);hist['train_parts'].append(ap);hist['val_parts'].append(bp)
        if b<best[0]:best=(b,copy.deepcopy(model.state_dict()));hist['best_epoch']=ep+1
        if ep==0 or (ep+1)%max(1,epochs//10)==0:print(f'{ep+1:03}/{epochs} train={a:.4f} val={b:.4f}')
    model.load_state_dict(best[1]); return hist
@torch.no_grad()
def predict(model,loader,device):
    model.eval(); all=[]
    for b in loader:all.append({k:v.cpu().numpy() for k,v in model(b['x_cat'].to(device),b['x_num'].to(device)).items()})
    return {k:np.concatenate([x[k] for x in all]) for k in all[0]}
