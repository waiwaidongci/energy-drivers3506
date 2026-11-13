import numpy as np
from src.constants.enums import SPLIT_SEED
from src.services.aggregation import normalize_config,building_indices,grouped_mae,per_building_errors,evaluation_metrics
def inspect_holdout(model,report,rows,config):
    config=normalize_config(config);buildings_equal=config['weighting']=='building'
    test=[r for r in rows if r['building_code'] in report['split']['test_buildings']]
    x=np.array([[r[f] for f in config['features']] for r in test],float);y=np.array([r['energy_kwh'] for r in test],float);codes=[str(r['building_code']) for r in test]
    if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('封存特征或目标含非有限值，不能公开评估')
    prediction=model.predict(x);metrics,per_building=evaluation_metrics(y,prediction,codes,config['weighting'])
    baseline=grouped_mae(y,prediction,codes,config['weighting']);base_by_building=[row['mae'] for row in per_building] if buildings_equal else []
    groups=building_indices(codes);findings=[]
    for j,feature in enumerate(config['features']):
        rng=np.random.default_rng(SPLIT_SEED+j);deltas=[];building_deltas=[]
        for _ in range(config['permutation_repeats']):
            corrupted=x.copy()
            if buildings_equal:
                # Permute inside each sealed building so the equal-weight score stays a
                # genuine per-building contrast; cross-building row mixing is avoided.
                for _,indices in groups:corrupted[indices,j]=x[rng.permutation(indices),j]
            else:
                corrupted[:,j]=x[rng.permutation(len(x)),j]
            permuted=model.predict(corrupted);deltas.append(float(grouped_mae(y,permuted,codes,config['weighting'])-baseline))
            if buildings_equal:building_deltas.append([float(row['mae']-base) for row,base in zip(per_building_errors(y,permuted,codes),base_by_building)])
        low,high=np.quantile(deltas,[.025,.975]).tolist()
        findings.append({'feature':feature,'coefficient':report['coefficient'][feature],'standardized_coefficient':report['standardized_coefficient'][feature],'importance_mean':float(np.mean(deltas)),'importance_low':low,'importance_high':high,'repeats':deltas,'building_importance_mean':{code:float(np.mean([repeat[i] for repeat in building_deltas])) for i,(code,_) in enumerate(groups)} if building_deltas else {}})
    metrics['n']=len(test);metrics['buildings']=report['split']['test_buildings'];metrics['per_building']=per_building;metrics['weighting']=config['weighting']
    points=[{'id':r['id'],'building_code':r['building_code'],'day':r['day'],'actual':float(actual),'prediction':float(pred),'residual':float(actual-pred)} for r,actual,pred in zip(test,y,prediction)]
    return metrics,findings,points
