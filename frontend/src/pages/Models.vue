<script setup lang="ts">
import {ref,onMounted,watch,computed} from 'vue';
import {useResearch} from '../stores/research';
import {useAuth} from '../stores/auth';
import {createRun} from '../api/runs';
import {useTask} from '../hooks/useTask';
import {usePolling} from '../hooks/usePolling';
import {features,weightings} from '../constants/enums';
import {number} from '../utils/format';
import PageHeading from '../components/common/PageHeading.vue';
import ErrorNotice from '../components/common/ErrorNotice.vue';
import DatasetSelect from '../components/DatasetSelect.vue';
import RunTable from '../components/RunTable.vue';
const lab=useResearch(),auth=useAuth(),data=ref({name:'未见楼宇 · 能耗驱动复核',dataset_id:0,weighting:'day',features:Object.keys(features),alphas:[.05,.5,5,25],l1_ratios:[.2,.6,.9],permutation_repeats:20}),message=ref(''),{busy,error,perform}=useTask();
const dataset=computed(()=>lab.datasets.find(d=>d.id===data.value.dataset_id)),locked=computed(()=>!!dataset.value?.locked_config),latest=computed(()=>lab.runs.find(r=>r.dataset_id===data.value.dataset_id&&r.status==='completed'));
const byBuilding=computed(()=>{
  const run=latest.value;const split=run?.result.split;if(!run||!split)return [];
  const cv=new Map((run.result.cv_per_building||[]).map(r=>[r.building_code,r]));
  const testRows=run.result.metrics?.per_building||[];const test=new Map(testRows.map(r=>[r.building_code,r]));
  // Old studies lack building_samples and audited per-building training counts are unknown, so only
  // sealed sample sizes are filled in from the holdout evaluation.
  const samples=run.result.building_samples||{};
  const codes=[...new Set([...Object.keys(samples),...(split.train_buildings||[]),...(split.test_buildings||[])])].sort();
  return codes.map(code=>{const sealed=(split.test_buildings||[]).includes(code);return {code,split:sealed?'test':'train',n:samples[code]?.n??(sealed?test.get(code)?.n:undefined),cv:cv.get(code),test:test.get(code)};});
});
function applyLock(){const config=dataset.value?.locked_config;if(config){Object.assign(data.value,config);data.value.weighting=config.weighting||'day';}}
onMounted(()=>perform(async()=>{await lab.load();data.value.dataset_id=lab.datasets[0]?.id||0;applyLock();}));
watch(()=>data.value.dataset_id,applyLock);
watch(locked,value=>{if(!value)data.value.weighting='day';});
usePolling(async()=>{if(lab.runs.some(r=>['queued','running'].includes(r.status)))await lab.load();});
function submit(){perform(async()=>{const run=await createRun(data.value);message.value=`研究 #${run.id} 已锁定配置并进入分组验证队列。`;await lab.load();applyLock();});}
</script>
<template>
  <PageHeading index="03" title="先在训练楼宇里比较，再揭开封存成绩" text="每一折独立学习均值与尺度；封存楼宇不参与特征或超参数选择。"/>
  <ErrorNotice :message="error" @retry="perform(lab.load)"/>
  <div class="model-config-layout">
    <form v-if="auth.canEdit" class="research-form" @submit.prevent="submit">
      <h2>{{locked?'复算已锁定方案':'建立分组模型研究'}}</h2>
      <label>研究名称<input v-model="data.name" required minlength="2"></label>
      <DatasetSelect v-model="data.dataset_id" :datasets="lab.datasets"/>
      <label>统计汇总方式
        <select v-model="data.weighting" :disabled="locked">
          <option v-for="(label,key) in weightings" :key="key" :value="key">{{label}}</option>
        </select>
      </label>
      <p class="input-note">{{data.weighting==='building'?'每栋楼先算自身MAE，再对楼宇取等权平均；选模、封存评估和置换ΔMAE都按此汇总，长记录楼宇不会主导成绩。':'每行楼宇日等权；这是兼容旧数据的原方案，长记录楼宇会获得更大权重。'}}</p>
      <p class="lock-message">{{locked?'本数据集配置与统计汇总方式已锁定，后续研究仅复算同一特征与候选范围。':'首次提交会锁定本数据集的特征、候选范围与统计汇总方式，再进行封存评估。'}}</p>
      <fieldset :disabled="locked">
        <legend>特征范围 <small>至少2项</small></legend>
        <div class="feature-options"><label v-for="(label,key) in features" :key="key" class="checkbox"><input v-model="data.features" type="checkbox" :value="key">{{label}}</label></div>
      </fieldset>
      <fieldset :disabled="locked">
        <legend>α 候选 <small>正则强度</small></legend>
        <div class="inline-options"><label v-for="a in [.05,.5,5,25]" :key="a" class="checkbox"><input v-model="data.alphas" type="checkbox" :value="a">{{a}}</label></div>
      </fieldset>
      <fieldset :disabled="locked">
        <legend>l1_ratio 候选</legend>
        <div class="inline-options"><label v-for="r in [.2,.6,.9]" :key="r" class="checkbox"><input v-model="data.l1_ratios" type="checkbox" :value="r">{{r}}</label></div>
      </fieldset>
      <label>封存置换重复次数
        <select v-model="data.permutation_repeats" :disabled="locked"><option :value="10">10次</option><option :value="20">20次</option><option :value="40">40次</option></select>
      </label>
      <button class="primary" :disabled="busy||data.features.length<2||!data.alphas.length||!data.l1_ratios.length">{{busy?'正在提交…':'锁定并提交分组训练 →'}}</button>
      <p v-if="message" class="success" role="status">{{message}}</p>
    </form>
    <section v-else class="research-form"><h2>联络员阅读工作区</h2><p>可以读取模型比较与驱动解释，并下载已审阅的改造假设。</p></section>
    <aside class="model-notes">
      <p class="eyebrow">MODEL BASIS / GROUPED VALIDATION</p>
      <h2>一栋楼的90天，<br>不会散进两边。</h2>
      <div class="model-stages">
        <span>01 <b>先分楼宇</b><small>固定seed97，约25%楼宇封存</small></span>
        <span>02 <b>训练内3折比较</b><small>每折Pipeline独立fit StandardScaler</small></span>
        <span>03 <b>锁定模型后评估</b><small>仅最终模型读取封存目标与置换解释</small></span>
      </div>
      <p>候选按三折平均MAE选优，同分依次选更小α与更小l1_ratio。未收敛的候选保留记录，不进入选优。</p>
      <p>{{data.weighting==='building'?'按楼宇等权时，每折先在各验证楼宇内算MAE，再对楼宇取平均；封存MAE与置换ΔMAE同样等权汇总。':'按日汇总时，每行封存楼宇日等权；这是旧数据的原口径。'}}各楼样本量和误差在下方逐栋列出。</p>
      <p>公开封存成绩后，不再用本数据集改统计方式、特征或候选范围。新方案需要新采集、尚未评估的楼宇。</p>
    </aside>
  </div>
  <section v-if="latest" class="candidate-comparison">
    <div class="section-heading"><h2>训练楼宇内的候选比较</h2><span>{{latest.name}} / {{weightings[latest.result.weighting||'day']}}</span></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>α</th><th>l1_ratio</th><th>折1 MAE</th><th>折2 MAE</th><th>折3 MAE</th><th>平均MAE</th><th>收敛 / 选择</th></tr></thead>
        <tbody><tr v-for="c in latest.result.candidates" :key="c.alpha+'-'+c.l1_ratio" :class="{chosen:c.alpha===latest.result.best?.alpha&&c.l1_ratio===latest.result.best?.l1_ratio}"><td>{{c.alpha}}</td><td>{{c.l1_ratio}}</td><td v-for="(score,i) in c.fold_maes" :key="i">{{score.toFixed(3)}}</td><td>{{c.mean_mae.toFixed(3)}}</td><td>{{!c.converged?'未收敛':c.alpha===latest.result.best?.alpha&&c.l1_ratio===latest.result.best?.l1_ratio?'已选定':'收敛'}}</td></tr></tbody>
      </table>
    </div>
    <p class="plot-note">各折MAE与平均MAE均按{{weightings[latest.result.weighting||'day']}}汇总；未收敛候选只留档，不参与选优。</p>
  </section>
  <section v-if="latest&&byBuilding.length" class="building-errors">
    <div class="section-heading"><h2>各楼样本量与误差</h2><span>训练楼宇为胜出配置的折外误差；封存楼宇为最终评估</span></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>楼宇</th><th>分组</th><th>样本量 / 楼宇日</th><th>CV MAE / kWh</th><th>封存 MAE / kWh</th><th>封存 RMSE / kWh</th></tr></thead>
        <tbody><tr v-for="b in byBuilding" :key="b.code" :class="{sealed:b.split==='test'}"><td><b>{{b.code}}</b></td><td>{{b.split==='test'?'封存':'训练'}}</td><td>{{b.n}}</td><td>{{number(b.cv?.mae,2)}}</td><td>{{number(b.test?.mae,2)}}</td><td>{{number(b.test?.rmse,2)}}</td></tr></tbody>
      </table>
    </div>
    <p class="plot-note">{{latest.result.weighting==='building'?'页面成绩为各楼误差的等权平均，样本量仅说明每栋楼的记录天数，不改变其权重。':'页面成绩为全部楼宇日等权平均；记录天数越多的楼宇权重越大。'}}</p>
  </section>
  <section class="run-directory"><div class="section-heading"><h2>研究运行记录</h2><span>运行中自动刷新</span></div><RunTable :runs="lab.runs"/></section>
</template>
