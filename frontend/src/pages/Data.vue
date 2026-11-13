<script setup lang="ts">
import {ref,onMounted,watch,computed} from 'vue';
import {useResearch} from '../stores/research';
import {useDays} from '../stores/days';
import {useAuth} from '../stores/auth';
import {createDataset} from '../api/datasets';
import {useTask} from '../hooks/useTask';
import {number} from '../utils/format';
import PageHeading from '../components/common/PageHeading.vue';
import ErrorNotice from '../components/common/ErrorNotice.vue';
import DatasetSelect from '../components/DatasetSelect.vue';
import EmptyState from '../components/common/EmptyState.vue';
const lab=useResearch(),days=useDays(),auth=useAuth(),selected=ref(0),building=ref(''),offset=ref(0),show=ref(false),name=ref(''),source=ref('ls-energy-days.csv'),csv=ref('building_code,day,temperature_c,operating_hours,area_m2,visitors,humidity_pct,equipment_kw,holiday_flag,energy_kwh\n'),{busy,error,perform}=useTask();
const dataset=computed(()=>lab.datasets.find(d=>d.id===selected.value)),buildings=computed(()=>[...(dataset.value?.train_buildings||[]),...(dataset.value?.test_buildings||[])].sort());
const samples=computed(()=>{const counts=dataset.value?.building_samples||{};const values=buildings.value.map(code=>counts[code]??0);return {total:values.reduce((a,b)=>a+b,0),min:values.length?Math.min(...values):0,max:values.length?Math.max(...values):0};});
async function load(){if(selected.value)await days.load(selected.value,building.value,offset.value);}
onMounted(()=>perform(async()=>{await lab.load();selected.value=lab.datasets[0]?.id||0;await load();}));
watch(selected,()=>{offset.value=0;building.value='';perform(load);});
watch(building,()=>{offset.value=0;perform(load);});
function submit(){perform(async()=>{const result=await createDataset({name:name.value,source_file:source.value,csv_text:csv.value,note:'团队导入的机构级楼宇日能耗记录'});await lab.load();selected.value=result.id;show.value=false;});}
</script>
<template>
  <PageHeading index="02" title="把同一栋楼，留在同一侧" text="训练与封存按楼宇分开；每条记录仍保留日期、特征与原始能耗单位。">
    <button v-if="auth.canEdit" class="outline" @click="show=!show">{{show?'收起导入':'导入新楼宇数据 +'}}</button>
  </PageHeading>
  <ErrorNotice :message="error" @retry="perform(load)"/>
  <form v-if="show" class="entry-form" @submit.prevent="submit">
    <h2>导入尚未评估的新楼宇研究数据</h2>
    <div class="form-grid"><label>数据集名称<input v-model="name" required minlength="2"></label><label>来源文件<input v-model="source" required></label></div>
    <label>CSV内容<textarea v-model="csv" rows="7" required></textarea></label>
    <p class="input-note">8栋及以上、每栋至少6天，48–5000行；同一楼宇同一天唯一。新方案应使用新采集的未见楼宇，不用重导旧数据规避封存。</p>
    <button class="primary" :disabled="busy">校验并建立数据集 →</button>
  </form>
  <div class="data-toolbar">
    <DatasetSelect v-model="selected" :datasets="lab.datasets"/>
    <label>观察楼宇<select v-model="building"><option value="">全部楼宇</option><option v-for="code in buildings" :key="code" :value="code">{{code}} / {{dataset?.test_buildings.includes(code)?'封存':'训练'}}</option></select></label>
  </div>
  <div class="source-caption"><b>{{dataset?.source_file}}</b><span>{{dataset?.row_count}}行 / {{dataset?.building_count}}栋</span><p>{{dataset?.note}}</p></div>
  <div v-if="buildings.length" class="sample-audit">
    <div class="section-heading"><h2>各楼记录天数</h2><span>样本量不等时，按日汇总会让长记录楼宇主导成绩</span></div>
    <div class="building-sample-list"><span v-for="code in buildings" :key="code" :class="{sealed:dataset?.test_buildings.includes(code)}"><b>{{code}}</b><em>{{dataset?.building_samples?.[code]??0}}天</em><small>{{dataset?.test_buildings.includes(code)?'封存':'训练'}}</small></span></div>
    <p class="plot-note">共{{samples.total}}个楼宇日；单栋最少{{samples.min}}天、最多{{samples.max}}天。研究页可选择“按楼宇等权”，让每栋楼先算误差再等权汇总。</p>
  </div>
  <p class="sealed-notice">{{dataset?.evaluation_released?'封存评估已公开；原始能耗可见，选模配置与统计方式保持锁定。':'封存楼宇的目标能耗暂不显示，首次方案锁定并完成选模后才公开最终评估。'}}</p>
  <div class="table-wrap"><table><thead><tr><th>楼宇 / 日期</th><th>分组</th><th>温度 °C</th><th>运行 h</th><th>面积 m²</th><th>到访</th><th>湿度 %</th><th>装机 kW</th><th>休息日</th><th>能耗 kWh</th></tr></thead><tbody><tr v-for="d in days.rows" :key="d.id" :class="{sealed:d.sealed}"><td><b>{{d.building_code}}</b><small>{{d.day}}</small></td><td>{{d.sealed?'封存':'训练'}}</td><td>{{number(d.temperature_c,2)}}</td><td>{{number(d.operating_hours,2)}}</td><td>{{number(d.area_m2,1)}}</td><td>{{number(d.visitors)}}</td><td>{{number(d.humidity_pct,2)}}</td><td>{{number(d.equipment_kw,2)}}</td><td>{{d.holiday_flag}}</td><td>{{d.energy_kwh===null?'封存目标':number(d.energy_kwh,2)}}</td></tr></tbody></table></div>
  <EmptyState v-if="!days.rows.length&&!busy" title="尚无匹配记录" text="选择一个楼宇数据集，或先导入有完整表头的CSV。"/>
  <div class="pagination"><span>共{{days.total}}行 / {{offset+1}}—{{Math.min(offset+20,days.total)}}</span><div><button :disabled="offset===0" @click="offset-=20;perform(load)">← 前20行</button><button :disabled="offset+20>=days.total" @click="offset+=20;perform(load)">后20行 →</button></div></div>
</template>
