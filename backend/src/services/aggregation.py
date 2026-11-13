import numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from src.constants.enums import WEIGHTING_DAY,WEIGHTING_BUILDING,WEIGHTINGS
def normalize_config(config):
    if not config:return config
    normalized=dict(config);weighting=normalized.get('weighting') or WEIGHTING_DAY
    if weighting not in WEIGHTINGS:raise ValueError('统计汇总方式非法，只能为day或building')
    normalized['weighting']=weighting
    return normalized
def fingerprint_config(config):
    # Legacy configurations had no weighting key and always aggregated by day.
    # Omitting the default here keeps old selection fingerprints reproducible.
    normalized=normalize_config(config)
    if normalized['weighting']==WEIGHTING_DAY:normalized.pop('weighting')
    return normalized
def building_indices(buildings):
    groups={}
    for i,code in enumerate(buildings):groups.setdefault(str(code),[]).append(i)
    return [(code,np.asarray(indices,dtype=int)) for code,indices in sorted(groups.items())]
def per_building_errors(y_true,y_pred,buildings):
    y_true=np.asarray(y_true,float);y_pred=np.asarray(y_pred,float);rows=[]
    for code,indices in building_indices(buildings):
        residual=y_true[indices]-y_pred[indices]
        rows.append({'building_code':code,'n':int(len(indices)),'mae':float(np.mean(np.abs(residual))),'rmse':float(np.sqrt(np.mean(residual**2)))})
    return rows
def grouped_mae(y_true,y_pred,buildings,weighting):
    if weighting==WEIGHTING_BUILDING:
        return float(np.mean([row['mae'] for row in per_building_errors(y_true,y_pred,buildings)]))
    return float(mean_absolute_error(y_true,y_pred))
def evaluation_metrics(y_true,y_pred,buildings,weighting):
    y_true=np.asarray(y_true,float);y_pred=np.asarray(y_pred,float);rows=per_building_errors(y_true,y_pred,buildings)
    if weighting==WEIGHTING_BUILDING:
        per_building_mse=[float(np.mean((y_true[indices]-y_pred[indices])**2)) for _,indices in building_indices(buildings)]
        per_building_var=[float(np.mean((y_true[indices]-np.mean(y_true[indices]))**2)) for _,indices in building_indices(buildings)]
        mse=float(np.mean(per_building_mse));variance=float(np.mean(per_building_var))
        return ({'mae':float(np.mean([row['mae'] for row in rows])),'rmse':float(np.sqrt(mse)),'r2':None if variance<1e-10 else float(1-mse/variance)},rows)
    metrics={'mae':float(mean_absolute_error(y_true,y_pred)),'rmse':float(np.sqrt(mean_squared_error(y_true,y_pred))),'r2':None if np.std(y_true)<1e-10 else float(r2_score(y_true,y_pred))}
    return metrics,rows
