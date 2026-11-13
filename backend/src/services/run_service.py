import json,hashlib
from sqlalchemy import select
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL
from src.constants.enums import RunStatus
from src.models import BuildingDataset,ModelRun,DriverFinding
from src.services.day_service import raw_days
from src.services.splitting import training_arrays
from src.services.learning import fit_grouped
from src.services.aggregation import normalize_config,fingerprint_config
from src.services.inspection import inspect_holdout
queue=Redis.from_url(REDIS_URL)
def run_payload(run):
    # Runs created before the equal-weight scheme have no weighting key; they remain day-based.
    # The stored config/result stay untouched so legacy values and fingerprints are preserved.
    result=dict(run.result or {})
    if result:result['weighting']=normalize_config(result)['weighting']
    payload_config=dict(run.config or {})
    payload_config['weighting']=normalize_config(payload_config)['weighting']
    return {'id':run.id,'name':run.name,'dataset_id':run.dataset_id,'config':payload_config,'status':run.status,'error':run.error,'created_at':run.created_at,'result':result}
def list_runs(db):return [run_payload(run) for run in db.scalars(select(ModelRun).order_by(ModelRun.id.desc())).all()]
def get_run(db,id):
    run=db.get(ModelRun,id)
    if not run:raise HTTPException(404,'模型研究不存在')
    return run_payload(run)
def create_run(db,data):
    dataset=db.scalar(select(BuildingDataset).where(BuildingDataset.id==data.dataset_id).with_for_update())
    if not dataset:raise HTTPException(404,'数据集不存在')
    config=normalize_config(data.config())
    if dataset.locked_config is not None and normalize_config(dataset.locked_config)!=config:raise HTTPException(409,'数据集选模配置已锁定；统计汇总方式、特征与超参在首次研究后均不可更改，只能同配置复算')
    if db.scalar(select(ModelRun).where(ModelRun.name==data.name)):raise HTTPException(409,'研究名称已存在')
    try:training_arrays(raw_days(db,dataset.id),config)
    except ValueError as exc:raise HTTPException(422,str(exc))
    dataset.locked_config=config;run=ModelRun(name=data.name,dataset_id=dataset.id,config=config,status=RunStatus.QUEUED);db.add(run);db.commit();queue.lpush('energy:runs',str(run.id));return run_payload(run)
def execute_run(db,id):
    run=db.get(ModelRun,id)
    if not run or run.status not in (RunStatus.QUEUED,RunStatus.RUNNING):return
    run.status=RunStatus.RUNNING;db.commit()
    try:
        dataset=db.get(BuildingDataset,run.dataset_id);rows=raw_days(db,dataset.id);config=normalize_config(run.config)
        model,report=fit_grouped(rows,config)
        # The winning configuration and training-only report exist before test targets are inspected.
        metrics,findings,points=inspect_holdout(model,report,rows,config)
        # Test targets and sealed rows participate only in the final evaluation and explanation.
        snapshot={'algorithm':'elasticnet-building-v1','dataset_id':dataset.id,'rows':rows,'config':fingerprint_config(config),'split':report['split']}
        fingerprint=hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        # Recovery can rerun an interrupted job; findings are written in the same final transaction.
        existing={f.feature:f for f in db.scalars(select(DriverFinding).where(DriverFinding.run_id==run.id)).all()}
        permutation_by_building={}
        for values in findings:
            permutation_by_building[values['feature']]={'mean':values.pop('building_importance_mean')}
            if values['feature'] not in existing:db.add(DriverFinding(run_id=run.id,**values))
        run.config=config;run.result={**report,'metrics':metrics,'points':points,'permutation_by_building':permutation_by_building,'input_fingerprint':fingerprint,'config':config};run.status=RunStatus.COMPLETED;run.error='';dataset.evaluation_released=True;db.commit()
    except Exception as exc:
        db.rollback();run=db.get(ModelRun,id);run.status=RunStatus.FAILED;run.error=str(exc)[:600];db.commit()
