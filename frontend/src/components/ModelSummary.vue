<script setup lang="ts">
import type {Run} from '../types/domain';
import {number} from '../utils/format';
import {weightings} from '../constants/enums';
defineProps<{run:Run}>();
</script>
<template>
  <section class="model-summary">
    <p class="eyebrow">UNSEEN BUILDING EVALUATION</p>
    <h2>{{number(run.result.metrics?.mae,2)}} <small>kWh</small></h2>
    <p class="metric-caption">封存楼宇 MAE / {{run.result.metrics?.n}}个楼宇日 / {{weightings[run.result.metrics?.weighting||run.result.weighting||'day']}}</p>
    <dl>
      <div><dt>分组CV MAE</dt><dd>{{number(run.result.best?.mean_mae,2)}}</dd></div>
      <div><dt>封存 RMSE</dt><dd>{{number(run.result.metrics?.rmse,2)}}</dd></div>
      <div><dt>封存 R²</dt><dd>{{number(run.result.metrics?.r2??undefined,3)}}</dd></div>
      <div><dt>选定 α / l1_ratio</dt><dd>{{run.result.best?.alpha}} / {{run.result.best?.l1_ratio}}</dd></div>
    </dl>
    <small>封存结果在模型选择完成后读取；只用于最终评估与解释。{{run.result.metrics?.weighting==='building'?'成绩为各封存楼宇误差等权平均。':''}}</small>
  </section>
</template>
