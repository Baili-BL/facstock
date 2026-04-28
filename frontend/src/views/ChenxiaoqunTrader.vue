<template>
  <div class="cxq-page">
    <!-- 顶栏 -->
    <header class="cxq-header">
      <button type="button" class="cxq-back" aria-label="返回" @click="goBack">
        <svg class="icon" viewBox="0 0 24 24"><path d="M11.67 3.87L9.9 2.1 0 12l9.9 9.9 1.77-1.77L3.54 12z"/></svg>
      </button>
      <div class="cxq-header__brand">
        <img
          src="https://pic.imgdb.cn/item/5f7b3c6e160a81a4a535c2a2.jpg"
          alt="陈小群"
          class="cxq-header__avatar"
          loading="lazy"
        />
        <div>
          <h1 class="cxq-header__title">陈小群</h1>
          <span class="cxq-header__sub">情绪驱动 · 结构确认</span>
        </div>
      </div>
      <div class="cxq-header__right">
        <span
          class="cxq-status-badge"
          :class="{
            'cxq-status-badge--running': isRunning,
            'cxq-status-badge--done': isDone,
          }"
        >
          <span v-if="isRunning" class="cxq-status-badge__dot cxq-status-badge__dot--spin" />
          <span v-else-if="isDone" class="cxq-status-badge__dot" />
          {{ isRunning ? '扫描中' : isDone ? '已完成' : '待启动' }}
        </span>
      </div>
    </header>

    <main class="cxq-main">
      <!-- 进度总览 -->
      <section class="cxq-progress-card">
        <div class="cxq-progress__meta">
          <span class="cxq-kicker">扫描进度</span>
          <span class="cxq-progress__pct">{{ progressPct }}%</span>
        </div>
        <div class="cxq-progress__bar">
          <div
            class="cxq-progress__fill"
            :style="{ width: progressPct + '%' }"
            :class="{ 'cxq-progress__fill--done': isDone }"
          />
        </div>
        <p class="cxq-progress__hint">
          {{ isRunning ? currentStepMsg : isDone ? '扫描完成，以下是结果' : '点击下方按钮启动每日扫描' }}
        </p>
      </section>

      <!-- 步骤日志 -->
      <section class="cxq-log-card">
        <div class="cxq-log__head">
          <svg class="icon cxq-log__ico" aria-hidden="true"><use href="#icon-ai" /></svg>
          <h2 class="cxq-log__title">扫描日志</h2>
          <span class="cxq-log__count">{{ steps.length }} 步</span>
        </div>
        <div class="cxq-log__body" ref="logEl">
          <div
            v-for="(s, i) in steps"
            :key="i"
            class="cxq-log-entry"
            :class="{
              'cxq-log-entry--done': s.status === 'done',
              'cxq-log-entry--active': s.status === 'active',
              'cxq-log-entry--error': s.status === 'error',
            }"
          >
            <span class="cxq-log-entry__dot" />
            <span class="cxq-log-entry__time">{{ s.time }}</span>
            <span class="cxq-log-entry__msg">{{ s.message }}</span>
          </div>
          <div v-if="!steps.length" class="cxq-log-empty">
            尚未开始扫描，等待启动…
          </div>
        </div>
      </section>

      <!-- 扫描结果（完成后展示） -->
      <template v-if="isDone && scanData">
        <!-- 趋势环境 -->
        <section class="cxq-trend-env-card">
          <div class="cxq-trend-env__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="cxq-trend-env__title">趋势环境</h2>
            <span class="cxq-trend-env__phase" :class="'phase-' + trendEnvStage">
              {{ trendEnvName }}
            </span>
          </div>
          <div class="cxq-trend-env__content">
            <div class="cxq-trend-env__gauge">
              <div class="cxq-trend-env__gauge-ring" :class="'phase-' + trendEnvStage">
                <span class="cxq-trend-env__gauge-score">{{ trendEnvConfidence }}</span>
              </div>
            </div>
            <div class="cxq-trend-env__info">
              <div class="cxq-trend-env__item">
                <span class="cxq-trend-env__label">市场阶段</span>
                <span class="cxq-trend-env__value">{{ trendEnvName }}（{{ trendEnvDesc }}）</span>
              </div>
              <div class="cxq-trend-env__item">
                <span class="cxq-trend-env__label">仓位建议</span>
                <span class="cxq-trend-env__value" :class="'position-' + trendEnvPosition">
                  {{ trendEnvPosition }}
                </span>
              </div>
              <div class="cxq-trend-env__item">
                <span class="cxq-trend-env__label">操作建议</span>
                <span class="cxq-trend-env__value">{{ trendEnvAction }}</span>
              </div>
            </div>
          </div>
          <div v-if="trendEnvReasons.length" class="cxq-trend-env__reasons">
            <div v-for="(reason, i) in trendEnvReasons" :key="i" class="cxq-trend-env__reason-item">
              {{ reason }}
            </div>
          </div>
        </section>

        <!-- 大盘指数 -->
        <section class="cxq-market-card">
          <div class="cxq-market__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="cxq-market__title">大盘指数</h2>
          </div>
          <div class="cxq-market__indices">
            <div
              v-for="(info, name) in indexData"
              :key="name"
              class="cxq-index-item"
            >
              <span class="cxq-index-item__name">{{ name }}</span>
              <span
                class="cxq-index-item__chg"
                :class="info.change >= 0 ? 'up' : 'down'"
              >
                {{ info.change >= 0 ? '+' : '' }}{{ info.change.toFixed(2) }}%
              </span>
            </div>
          </div>
        </section>

        <!-- 热点板块 -->
        <section v-if="hotSectors.length" class="cxq-sectors-card">
          <div class="cxq-sectors__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="cxq-sectors__title">热点板块</h2>
            <span class="cxq-sectors__count">{{ hotSectors.length }} 个</span>
          </div>
          <div class="cxq-sectors__chips">
            <span
              v-for="s in hotSectors"
              :key="s.name"
              class="cxq-sector-chip"
              :class="s.change >= 0 ? 'up' : 'down'"
            >
              {{ s.name }}
              <span class="cxq-sector-chip__chg">{{ s.change >= 0 ? '+' : '' }}{{ s.change }}%</span>
            </span>
          </div>
        </section>

        <!-- 趋势股票统计 -->
        <section class="cxq-stats-card">
          <div class="cxq-stats__head">
            <svg class="icon" aria-hidden="true"><use href="#icon-ai" /></svg>
            <h2 class="cxq-stats__title">趋势扫描</h2>
          </div>
          <div class="cxq-stats__grid">
            <div class="cxq-stat-item">
              <span class="cxq-stat-item__val">{{ stats.totalStocks }}</span>
              <span class="cxq-stat-item__lbl">趋势股票</span>
            </div>
            <div class="cxq-stat-item cxq-stat-item--main-up">
              <span class="cxq-stat-item__val">{{ stats.mainUpCount || 0 }}</span>
              <span class="cxq-stat-item__lbl">主升趋势</span>
            </div>
            <div class="cxq-stat-item cxq-stat-item--pullback">
              <span class="cxq-stat-item__val">{{ stats.pullbackCount || 0 }}</span>
              <span class="cxq-stat-item__lbl">回调机会</span>
            </div>
            <div class="cxq-stat-item cxq-stat-item--leader">
              <span class="cxq-stat-item__val">{{ stats.capitalCore || 0 }}</span>
              <span class="cxq-stat-item__lbl">容量中军</span>
            </div>
          </div>
          <div class="cxq-stats__elapsed">
            扫描耗时 {{ scanData.elapsedSeconds || 0 }}s
          </div>
        </section>

        <!-- 精选趋势股 -->
        <section v-if="recommendations.length" class="cxq-recs-card">
          <h2 class="cxq-recs__title">
            <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            精选趋势股
          </h2>
          <div class="cxq-recs__list">
            <div
              v-for="(s, i) in recommendations"
              :key="s.code"
              class="cxq-rec-item"
            >
              <div class="cxq-rec-item__left">
                <span class="cxq-rec-item__rank">{{ i + 1 }}</span>
                <div>
                  <p class="cxq-rec-item__name">{{ s.name }}</p>
                  <p class="cxq-rec-item__code">{{ s.code }}</p>
                </div>
              </div>
              <div class="cxq-rec-item__mid">
                <span
                  class="cxq-structure-badge"
                  :class="'structure-' + s.structure?.type"
                >
                  {{ s.structure?.name || '趋势' }}
                </span>
                <span class="cxq-rec-item__sector">{{ s.sector || s.tags?.[0] }}</span>
              </div>
              <div class="cxq-rec-item__right">
                <div class="cxq-rec-item__entry-type">{{ s.entryPlan?.type }}</div>
                <div class="cxq-rec-item__range">
                  <span v-if="s.entryPlan?.entryZone">买：{{ s.entryPlan.entryZone }}</span>
                  <span class="cxq-rec-item__stop" v-if="s.exitPlan?.stopLoss">止：{{ s.exitPlan.stopLoss }}</span>
                </div>
              </div>
              <span
                class="cxq-rec-item__chg"
                :class="s.changePct >= 0 ? 'up' : 'down'"
              >
                {{ s.changePct >= 0 ? '+' : '' }}{{ s.changePct }}%
              </span>
            </div>
          </div>
        </section>

        <!-- AI 增强分析 -->
        <template v-if="agentResult && agentResult.success">
          <!-- 共识标尺 -->
          <section class="cxq-consensus-card">
            <div class="cxq-consensus__left">
              <div class="cxq-consensus__gauge">
                <svg viewBox="0 0 96 96" class="cxq-consensus__svg">
                  <circle cx="48" cy="48" r="40" fill="none" stroke-width="8" stroke="var(--track)" />
                  <circle
                    cx="48" cy="48" r="40"
                    fill="none"
                    stroke-width="8"
                    stroke-linecap="round"
                    :stroke="stanceColor"
                    :stroke-dasharray="gaugeCirc"
                    :stroke-dashoffset="gaugeOffset"
                    transform="rotate(-90 48 48)"
                    class="cxq-consensus__arc"
                  />
                  <text x="48" y="44" text-anchor="middle" class="cxq-consensus__num">{{ confidence }}</text>
                  <text x="48" y="58" text-anchor="middle" class="cxq-consensus__unit">%</text>
                </svg>
              </div>
            </div>
            <div class="cxq-consensus__right">
              <div class="cxq-consensus__stance-row">
                <span
                  class="cxq-stance-tag"
                  :class="'cxq-stance-tag--' + (structured?.stance || 'neutral')"
                >
                  {{ stanceLabel }}
                </span>
                <span class="cxq-consensus__conf-label">AI 信心 {{ confidence }}%</span>
              </div>
              <p class="cxq-consensus__comm">
                {{ structured?.marketCommentary || '' }}
              </p>
              <div class="cxq-consensus__advice">
                <strong>策略建议：</strong>{{ structured?.positionAdvice || '' }}
              </div>
              <div v-if="structured?.riskWarning" class="cxq-consensus__warning">
                <span class="cxq-warn-ico" aria-hidden="true">⚠</span>
                {{ structured.riskWarning }}
              </div>
            </div>
          </section>

          <!-- AI 推荐趋势股 -->
          <section v-if="aiRecommendedStocks.length" class="cxq-recs-card">
            <h2 class="cxq-recs__title">
              <svg class="icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
              AI 精选趋势股
            </h2>
            <div class="cxq-recs__list">
              <div
                v-for="(s, i) in aiRecommendedStocks"
                :key="s.code || i"
                class="cxq-rec-item"
              >
                <div class="cxq-rec-item__left">
                  <span class="cxq-rec-item__rank">{{ i + 1 }}</span>
                  <div>
                    <p class="cxq-rec-item__name">{{ s.name }}</p>
                    <p class="cxq-rec-item__code">{{ s.code }}</p>
                  </div>
                </div>
                <div class="cxq-rec-item__mid">
                  <span
                    class="cxq-structure-badge"
                    :class="'structure-' + (s.structure?.type || 'unknown')"
                  >
                    {{ s.structure?.name || '趋势' }}
                  </span>
                  <span class="cxq-rec-item__advise">{{ s.adviseType || '趋势持有' }}</span>
                </div>
                <div class="cxq-rec-item__right">
                  <div class="cxq-rec-item__entry-type">{{ s.entryPlan?.type || '趋势持有' }}</div>
                  <div class="cxq-rec-item__range">
                    <span v-if="s.entryPlan?.entryZone">买：{{ s.entryPlan.entryZone }}</span>
                    <span class="cxq-rec-item__stop" v-if="s.exitPlan?.stopLoss">止：{{ s.exitPlan.stopLoss }}</span>
                  </div>
                </div>
                <span
                  class="cxq-rec-item__chg"
                  :class="s.changePct >= 0 ? 'up' : 'down'"
                >
                  {{ s.changePct >= 0 ? '+' : '' }}{{ s.changePct }}%
                </span>
              </div>
            </div>
          </section>

          <!-- 标签命中 -->
          <section v-if="structured?.tags && structured.tags.length" class="cxq-tags-card">
            <div class="cxq-tags__head">
              <svg class="icon" aria-hidden="true"><use href="#icon-tag" /></svg>
              <h2 class="cxq-tags__title">策略标签</h2>
            </div>
            <div class="cxq-tags__list">
              <span v-for="tag in structured.tags" :key="tag" class="cxq-tag">{{ tag }}</span>
            </div>
          </section>
        </template>
      </template>
    </main>

    <!-- 底部启动按钮 -->
    <footer class="cxq-footer">
      <button
        class="cxq-start-btn"
        :class="{ 'cxq-start-btn--loading': isRunning }"
        :disabled="isRunning"
        @click="startScan"
      >
        <svg v-if="!isRunning" class="icon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        <span v-if="isRunning" class="cxq-spinner" />
        {{ isRunning ? '扫描中...' : '启动趋势扫描' }}
      </button>
    </footer>
  </div>
</template>

<script>
import { defineComponent, ref, computed, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { chenxiaoqunScan } from '@/api/agents';

export default defineComponent({
  name: 'ChenxiaoqunTrader',
  setup() {
    const router = useRouter();
    const logEl = ref(null);
    const isRunning = ref(false);
    const isDone = ref(false);
    const progressPct = ref(0);
    const currentStepMsg = ref('');
    const steps = ref([]);
    const scanData = ref(null);
    const agentResult = ref(null);

    // ─── 计算属性 ───────────────────────────────────────────────
    const indexData = computed(() => scanData.value?.marketIndices || {});
    const hotSectors = computed(() => scanData.value?.hotSectors || []);
    const recommendations = computed(() => scanData.value?.recommendations || []);

    const trendEnv = computed(() => scanData.value?.trendEnvironment || {});
    const trendEnvStage = computed(() => trendEnv.value.stage || 'unknown');
    const trendEnvName = computed(() => trendEnv.value.name || '未知');
    const trendEnvDesc = computed(() => trendEnv.value.description || '');
    const trendEnvAction = computed(() => trendEnv.value.action || '');
    const trendEnvPosition = computed(() => trendEnv.value.positionAdvice || '');
    const trendEnvConfidence = computed(() => trendEnv.value.confidence || 0);
    const trendEnvReasons = computed(() => trendEnv.value.reasons || []);

    const stats = computed(() => {
      const stocks = scanData.value?.trendStocks || [];
      return {
        totalStocks: stocks.length,
        mainUpCount: stocks.filter(s => s.structure?.type === 'main_up').length,
        pullbackCount: stocks.filter(s => s.structure?.type === 'pullback').length,
        capitalCore: stocks.filter(s => s.tags?.includes('容量中军')).length,
      };
    });

    // AI 分析结果
    const structured = computed(() => agentResult.value?.structured || null);
    const aiRecommendedStocks = computed(() => agentResult.value?.recommendedStocks || []);

    // 立场颜色
    const stanceColor = computed(() => {
      const st = structured.value?.stance || 'neutral';
      const colorMap = {
        bullish: '#f23645',
        bear: '#089981',
        neutral: '#6462d2',
      };
      return colorMap[st] || '#6462d2';
    });

    // 立场标签
    const stanceLabel = computed(() => {
      const st = structured.value?.stance || 'neutral';
      const labelMap = {
        bullish: '看多',
        bear: '看空',
        neutral: '中性',
      };
      return labelMap[st] || '中性';
    });

    // 信心指数
    const confidence = computed(() => agentResult.value?.confidence || 50);

    // 仪表盘
    const gaugeCirc = 2 * Math.PI * 40;
    const gaugeOffset = computed(() => {
      return gaugeCirc * (1 - (confidence.value / 100));
    });

    // ─── 方法 ─────────────────────────────────────────────────
    function goBack() {
      router.back();
    }

    function pushStep(message, status = 'active') {
      const now = new Date();
      const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
      // 标记前一个为完成
      if (steps.value.length > 0 && steps.value[steps.value.length - 1].status === 'active') {
        steps.value[steps.value.length - 1].status = 'done';
      }
      steps.value.push({ time: timeStr, message, status });
      nextTick(() => {
        if (logEl.value) {
          logEl.value.scrollTop = logEl.value.scrollHeight;
        }
      });
    }

    function updateStep(index, message, status) {
      if (steps.value[index]) {
        steps.value[index].message = message;
        steps.value[index].status = status;
      }
    }

    async function startScan() {
      if (isRunning.value) return;

      isRunning.value = true;
      isDone.value = false;
      progressPct.value = 0;
      currentStepMsg.value = '准备启动...';
      steps.value = [];
      scanData.value = null;
      agentResult.value = null;

      const startTime = Date.now();

      try {
        // 步骤1：启动扫描
        pushStep('正在连接服务器...', 'active');
        progressPct.value = 10;
        currentStepMsg.value = '正在连接服务器...';
        await sleep(500);

        // 步骤2：获取数据
        updateStep(0, '连接成功，正在获取市场数据...', 'done');
        pushStep('正在获取大盘指数...', 'active');
        progressPct.value = 20;
        currentStepMsg.value = '正在获取大盘指数...';
        await sleep(600);

        // 步骤3：分析趋势环境
        updateStep(1, '获取指数完成，正在分析趋势环境...', 'done');
        pushStep('正在分析趋势环境...', 'active');
        progressPct.value = 35;
        currentStepMsg.value = '正在分析趋势环境...';
        await sleep(500);

        // 步骤4：获取热点板块
        updateStep(2, '趋势环境分析完成，正在获取热点板块...', 'done');
        pushStep('正在扫描热点板块...', 'active');
        progressPct.value = 50;
        currentStepMsg.value = '正在扫描热点板块...';
        await sleep(800);

        // 步骤5：获取趋势股票
        updateStep(3, '热点板块扫描完成，正在筛选趋势股票...', 'done');
        pushStep('正在筛选趋势股票...', 'active');
        progressPct.value = 65;
        currentStepMsg.value = '正在筛选趋势股票...';
        await sleep(1000);

        // 步骤6：分析趋势结构
        updateStep(4, '趋势股票筛选完成，正在分析趋势结构...', 'done');
        pushStep('正在分析趋势结构...', 'active');
        progressPct.value = 80;
        currentStepMsg.value = '正在分析趋势结构...';
        await sleep(800);

        // 步骤7：AI 增强分析
        updateStep(5, '趋势结构分析完成，正在进行 AI 增强分析...', 'done');
        pushStep('正在进行 AI 增强分析...', 'active');
        progressPct.value = 90;
        currentStepMsg.value = '正在进行 AI 增强分析...';

        // 调用 API
        const response = await chenxiaoqunScan();

        updateStep(6, 'AI 分析完成，正在整理结果...', 'done');
        pushStep('扫描完成！', 'done');
        progressPct.value = 100;
        currentStepMsg.value = '扫描完成';

        // 解析结果
        scanData.value = response.data?.scanResult || response.data || response;
        agentResult.value = response.data?.aiResult || null;

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        scanData.value.elapsedSeconds = parseFloat(elapsed);

        await sleep(300);
        isDone.value = true;

      } catch (err) {
        console.error('扫描失败:', err);
        pushStep(`扫描失败: ${err.message || '未知错误'}`, 'error');
        updateStep(steps.value.length - 1, `扫描失败: ${err.message || '未知错误'}`, 'error');
      } finally {
        isRunning.value = false;
      }
    }

    function sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    return {
      router,
      logEl,
      isRunning,
      isDone,
      progressPct,
      currentStepMsg,
      steps,
      scanData,
      agentResult,
      // computed
      indexData,
      hotSectors,
      recommendations,
      trendEnv,
      trendEnvStage,
      trendEnvName,
      trendEnvDesc,
      trendEnvAction,
      trendEnvPosition,
      trendEnvConfidence,
      trendEnvReasons,
      stats,
      structured,
      aiRecommendedStocks,
      stanceColor,
      stanceLabel,
      confidence,
      gaugeCirc,
      gaugeOffset,
      // methods
      goBack,
      startScan,
    };
  },
});
</script>

<style scoped>
/* ─── 基础变量 ─── */
.cxq-page {
  --up: #f23645;
  --down: #089981;
  --accent: #f23645;
  --bg: #f5f6fa;
  --surface: #ffffff;
  --surface-variant: #f0f1f5;
  --on-surface: #1a1a2e;
  --on-surface-variant: #6b6b8a;
  --track: #e8e8f0;

  min-height: 100vh;
  background: var(--bg);
  padding-bottom: 80px;
}

/* ─── 顶栏 ─── */
.cxq-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--surface);
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.08);
}

.cxq-back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  background: var(--surface-variant);
  border-radius: 50%;
  cursor: pointer;
  color: var(--on-surface);
}

.cxq-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.cxq-header__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--accent);
}

.cxq-header__title {
  font-size: 17px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0;
}

.cxq-header__sub {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.cxq-header__right {
  display: flex;
  align-items: center;
}

.cxq-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  background: var(--surface-variant);
  color: var(--on-surface-variant);
}

.cxq-status-badge--running {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}

.cxq-status-badge--done {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}

.cxq-status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.cxq-status-badge__dot--spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ─── 主内容 ─── */
.cxq-main {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ─── 进度卡片 ─── */
.cxq-progress-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-progress__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.cxq-kicker {
  font-size: 13px;
  color: var(--on-surface-variant);
}

.cxq-progress__pct {
  font-size: 15px;
  font-weight: 700;
  color: var(--accent);
}

.cxq-progress__bar {
  height: 6px;
  background: var(--track);
  border-radius: 3px;
  overflow: hidden;
}

.cxq-progress__fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.cxq-progress__fill--done {
  background: var(--down);
}

.cxq-progress__hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--on-surface-variant);
}

/* ─── 日志卡片 ─── */
.cxq-log-card {
  background: var(--surface);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-log__head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--track);
}

.cxq-log__ico {
  color: var(--accent);
}

.cxq-log__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
  flex: 1;
}

.cxq-log__count {
  font-size: 12px;
  color: var(--on-surface-variant);
  background: var(--surface-variant);
  padding: 2px 8px;
  border-radius: 10px;
}

.cxq-log__body {
  max-height: 180px;
  overflow-y: auto;
  padding: 12px 16px;
}

.cxq-log-entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
  color: var(--on-surface-variant);
}

.cxq-log-entry__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--track);
  flex-shrink: 0;
  margin-top: 5px;
}

.cxq-log-entry--active .cxq-log-entry__dot {
  background: var(--accent);
  animation: pulse 1.5s ease infinite;
}

.cxq-log-entry--done .cxq-log-entry__dot {
  background: var(--down);
}

.cxq-log-entry--error .cxq-log-entry__dot {
  background: #e74c3c;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

.cxq-log-entry__time {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
  opacity: 0.7;
  flex-shrink: 0;
}

.cxq-log-entry__msg {
  flex: 1;
  line-height: 1.4;
}

.cxq-log-entry--active .cxq-log-entry__msg {
  color: var(--on-surface);
  font-weight: 500;
}

.cxq-log-entry--error .cxq-log-entry__msg {
  color: #e74c3c;
}

.cxq-log-empty {
  text-align: center;
  padding: 20px;
  color: var(--on-surface-variant);
  font-size: 13px;
}

/* ─── 趋势环境卡片 ─── */
.cxq-trend-env-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-trend-env__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.cxq-trend-env__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
  flex: 1;
}

.cxq-trend-env__phase {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.phase-main_up {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}

.phase-shock {
  background: rgba(100, 98, 210, 0.1);
  color: #6462d2;
}

.phase-weak {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}

.cxq-trend-env__content {
  display: flex;
  gap: 16px;
  align-items: center;
}

.cxq-trend-env__gauge {
  flex-shrink: 0;
}

.cxq-trend-env__gauge-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-variant);
}

.phase-main_up .cxq-trend-env__gauge-ring {
  background: rgba(242, 54, 69, 0.1);
}

.phase-shock .cxq-trend-env__gauge-ring {
  background: rgba(100, 98, 210, 0.1);
}

.phase-weak .cxq-trend-env__gauge-ring {
  background: rgba(8, 153, 129, 0.1);
}

.cxq-trend-env__gauge-score {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
}

.cxq-trend-env__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cxq-trend-env__item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.cxq-trend-env__label {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.cxq-trend-env__value {
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
}

.position-重仓持有 {
  color: var(--up);
}

.position-轻仓试探 {
  color: #6462d2;
}

.position-空仓 {
  color: var(--down);
}

.cxq-trend-env__reasons {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--track);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cxq-trend-env__reason-item {
  font-size: 12px;
  color: var(--on-surface-variant);
  line-height: 1.4;
}

/* ─── 市场指数 ─── */
.cxq-market-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-market__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.cxq-market__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
}

.cxq-market__indices {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.cxq-index-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-variant);
  border-radius: 10px;
  flex: 1;
  min-width: 120px;
}

.cxq-index-item__name {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.cxq-index-item__chg {
  font-size: 13px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.cxq-index-item__chg.up { color: var(--up); }
.cxq-index-item__chg.down { color: var(--down); }

/* ─── 热点板块 ─── */
.cxq-sectors-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-sectors__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.cxq-sectors__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
  flex: 1;
}

.cxq-sectors__count {
  font-size: 12px;
  color: var(--on-surface-variant);
  background: var(--surface-variant);
  padding: 2px 8px;
  border-radius: 10px;
}

.cxq-sectors__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cxq-sector-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 500;
  background: var(--surface-variant);
  color: var(--on-surface);
}

.cxq-sector-chip.up {
  background: rgba(242, 54, 69, 0.08);
  color: var(--up);
}

.cxq-sector-chip.down {
  background: rgba(8, 153, 129, 0.08);
  color: var(--down);
}

.cxq-sector-chip__chg {
  font-family: var(--font-mono);
  font-size: 11px;
}

/* ─── 统计卡片 ─── */
.cxq-stats-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-stats__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.cxq-stats__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
}

.cxq-stats__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
}

.cxq-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 8px;
  background: var(--surface-variant);
  border-radius: 12px;
}

.cxq-stat-item__val {
  font-size: 20px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--on-surface);
}

.cxq-stat-item__lbl {
  font-size: 10px;
  color: var(--on-surface-variant);
  margin-top: 2px;
}

.cxq-stat-item--main-up .cxq-stat-item__val { color: var(--up); }
.cxq-stat-item--pullback .cxq-stat-item__val { color: #6462d2; }
.cxq-stat-item--leader .cxq-stat-item__val { color: var(--down); }

.cxq-stats__elapsed {
  text-align: center;
  margin-top: 12px;
  font-size: 12px;
  color: var(--on-surface-variant);
}

/* ─── 推荐列表 ─── */
.cxq-recs-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-recs__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 14px;
}

.cxq-recs__title .icon {
  color: #f7c948;
  font-size: 18px;
}

.cxq-recs__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cxq-rec-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--surface-variant);
  border-radius: 12px;
}

.cxq-rec-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 80px;
}

.cxq-rec-item__rank {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cxq-rec-item__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
  white-space: nowrap;
}

.cxq-rec-item__code {
  font-size: 11px;
  color: var(--on-surface-variant);
  font-family: var(--font-mono);
  margin: 0;
}

.cxq-rec-item__mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cxq-structure-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.structure-main_up {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}

.structure-pullback {
  background: rgba(100, 98, 210, 0.1);
  color: #6462d2;
}

.structure-breakdown {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}

.structure-unknown {
  background: var(--surface);
  color: var(--on-surface-variant);
}

.cxq-rec-item__sector,
.cxq-rec-item__advise {
  font-size: 11px;
  color: var(--on-surface-variant);
}

.cxq-rec-item__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  min-width: 90px;
}

.cxq-rec-item__entry-type {
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
}

.cxq-rec-item__range {
  font-size: 10px;
  color: var(--on-surface-variant);
  display: flex;
  gap: 6px;
}

.cxq-rec-item__stop {
  color: var(--down);
}

.cxq-rec-item__chg {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono);
  padding: 4px 8px;
  border-radius: 6px;
  flex-shrink: 0;
}

.cxq-rec-item__chg.up {
  color: var(--up);
  background: rgba(242, 54, 69, 0.1);
}

.cxq-rec-item__chg.down {
  color: var(--down);
  background: rgba(8, 153, 129, 0.1);
}

/* ─── 共识/AI分析 ─── */
.cxq-consensus-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-consensus__left {
  flex-shrink: 0;
}

.cxq-consensus__gauge {
  width: 96px;
  height: 96px;
}

.cxq-consensus__svg {
  width: 100%;
  height: 100%;
}

.cxq-consensus__num {
  font-size: 22px;
  font-weight: 700;
  font-family: var(--font-mono);
  fill: var(--on-surface);
}

.cxq-consensus__unit {
  font-size: 12px;
  fill: var(--on-surface-variant);
}

.cxq-consensus__right {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cxq-consensus__stance-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.cxq-stance-tag {
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  font-weight: 700;
}

.cxq-stance-tag--bullish {
  background: rgba(242, 54, 69, 0.1);
  color: var(--up);
}

.cxq-stance-tag--bear {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}

.cxq-stance-tag--neutral {
  background: rgba(100, 98, 210, 0.1);
  color: #6462d2;
}

.cxq-consensus__conf-label {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.cxq-consensus__comm {
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
  margin: 0;
}

.cxq-consensus__advice {
  font-size: 13px;
  color: var(--on-surface);
  line-height: 1.5;
}

.cxq-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(242, 54, 69, 0.06);
  border-radius: 8px;
  font-size: 12px;
  color: var(--up);
  line-height: 1.4;
}

.cxq-warn-ico {
  flex-shrink: 0;
}

/* ─── 标签卡片 ─── */
.cxq-tags-card {
  background: var(--surface);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(46, 36, 73, 0.06);
}

.cxq-tags__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.cxq-tags__title {
  font-size: 15px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0;
}

.cxq-tags__list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.cxq-tag {
  padding: 4px 12px;
  background: var(--surface-variant);
  border-radius: 12px;
  font-size: 12px;
  color: var(--on-surface);
}

/* ─── 底部按钮 ─── */
.cxq-footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: var(--surface);
  box-shadow: 0 -4px 20px rgba(46, 36, 73, 0.08);
}

.cxq-start-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  border: none;
  border-radius: 14px;
  background: var(--accent);
  color: white;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
}

.cxq-start-btn:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.cxq-start-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.cxq-start-btn--loading {
  background: var(--on-surface-variant);
}

.cxq-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ─── 通用 ─── */
.icon {
  width: 20px;
  height: 20px;
  fill: currentColor;
}

.cxq-page :deep(.icon) {
  width: 20px;
  height: 20px;
  fill: currentColor;
}
</style>
