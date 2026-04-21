<template>
  <div class="fac-root">
    <!-- TopAppBar -->
    <header class="fac-header">
      <div class="fac-header__left">
        <button type="button" class="fac-header__icon-btn" aria-label="返回" @click="goBack">
          <span class="mso">arrow_back</span>
      </button>
        <div class="fac-header__brand">
          <div class="fac-header__avatar" :aria-label="agentName">{{ agentInitial }}</div>
          <div class="fac-header__title-group">
            <h1 class="fac-header__title">{{ agentName }}</h1>
            <span class="fac-header__subtitle">{{ roleSubtitle }}</span>
        </div>
        </div>
      </div>
      <div class="fac-header__right">
        <span v-if="isFromHistory" class="fac-badge fac-badge--history">
          <span class="mso" style="font-size:12px">history</span>
          今日记录
        </span>
        <span class="fac-badge" :class="isRunning ? 'fac-badge--running' : isDone ? 'fac-badge--done' : 'fac-badge--pending'">
          <span v-if="isRunning" class="fac-badge__dot fac-badge__dot--spin" />
          <span v-else-if="isDone" class="fac-badge__dot" />
          {{ isRunning ? '分析中' : isDone ? '已完成' : '待分析' }}
        </span>
      </div>
    </header>

    <!-- Content Canvas -->
    <main class="fac-main">

      <!-- ── 策略提示词卡片 ───────────────────────────────────── -->
      <section class="fac-prompt-card">
        <div class="fac-prompt-card__glow" />
        <div class="fac-prompt-card__head">
          <h2 class="fac-prompt-card__title">
            <span class="mso">terminal</span>
            策略核心理念
          </h2>
          <button type="button" class="fac-prompt-card__expand" @click="showPromptModal = true">
            查看全部 <span class="mso">chevron_right</span>
          </button>
        </div>
        <pre class="fac-prompt-card__code">{{ agentInfo.tagline || '加载中...' }}</pre>
      </section>

      <!-- ── 任务执行过程（横向步骤条）────────────────────────── -->
      <TaskProcessCard
        v-if="isRunning || isDone"
        :steps="cotSteps"
        :current-step="currentCotStep"
        :total-steps="totalCotSteps"
        :current-step-title="currentCotTitle"
        :current-step-detail="currentStepDetail"
        :is-running="isRunning"
        :is-done="isDone"
        :confidence="result?.cot_steps_confidence ?? confidence"
        :stance="result?.cot_steps_stance ?? structured?.stance"
        :market-commentary="result?.cot_steps_marketCommentary ?? structured?.marketCommentary"
      />

      <!-- ── AI 思考过程 ─────────────────────────────────── -->
      <section class="fac-thinking-card">
        <!-- 折叠头 -->
        <div
          class="fac-thinking-card__head"
          role="button"
          tabindex="0"
          @click="thinkingExpanded = !thinkingExpanded"
          @keydown.enter.prevent="thinkingExpanded = !thinkingExpanded"
          @keydown.space.prevent="thinkingExpanded = !thinkingExpanded"
        >
          <span class="mso">memory</span>
          <h2 class="fac-thinking-card__title">AI 分析过程</h2>
          <span class="fac-thinking-card__count">{{ thinkingLines.length }} 步</span>
          <span class="fac-thinking-card__toggle" :class="{ 'fac-thinking-card__toggle--open': thinkingExpanded }">
            <span class="mso">expand_more</span>
          </span>
        </div>

        <!-- 时间线 -->
        <div v-show="thinkingExpanded" class="fac-timeline">
          <div
            v-for="(line, i) in thinkingLines"
            :key="'tl-' + i"
            class="fac-timeline__item"
          >
            <div class="fac-timeline__dot" :class="{ 'fac-timeline__dot--active': (line.startsWith('[步骤') || line.startsWith('[阶段')) && i === thinkingLines.length - 1 }">
              <span class="mso">{{ line.startsWith('[步骤') ? 'task_alt' : line.startsWith('[调用') ? 'cloud_download' : line.startsWith('[结果') ? 'database' : line.startsWith('[阶段]') ? 'auto_awesome' : 'smart_toy' }}</span>
          </div>
            <div class="fac-timeline__content" :class="{ 'fac-timeline__content--active': (line.startsWith('[步骤') || line.startsWith('[阶段')) && i === thinkingLines.length - 1 }">
              <div class="fac-timeline__title">
                {{ line.startsWith('[步骤') ? '任务步骤' : line.startsWith('[调用') ? '数据获取' : line.startsWith('[结果') ? '返回数据' : line.startsWith('[阶段]') ? '推理阶段' : '思考中' }}
                <span v-if="line.startsWith('[阶段]') && i === thinkingLines.length - 1" class="fac-timeline__dots">
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                </span>
        </div>
              <p class="fac-timeline__desc">{{ line.replace(/^\[[^\]]+\]\s*/, '') }}</p>
            </div>
          </div>
        </div>

        <!-- 分析中时间线占位（实时滚动用） -->
        <div v-if="isRunning && !thinkingLines.length" class="fac-timeline">
          <div class="fac-timeline__item">
            <div class="fac-timeline__dot fac-timeline__dot--active">
              <span class="mso">model_training</span>
            </div>
            <div class="fac-timeline__content fac-timeline__content--active">
              <div class="fac-timeline__title">
                正在分析
                <span class="fac-timeline__dots">
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                  <span class="fac-timeline__dot-anim" />
                </span>
              </div>
              <p class="fac-timeline__desc">等待 AI 智能体返回分析结果...</p>
            </div>
          </div>
        </div>

        <!-- 启动按钮 -->
        <div class="fac-thinking-card__run-btn-wrap">
        <button
          type="button"
            class="fac-btn-run"
            :class="{ 'fac-btn-run--running': isRunning }"
          :disabled="isRunning"
          @click="runAnalysis"
        >
            <span v-if="isRunning" class="fac-btn-run__spinner" />
            <span v-else class="mso">play_arrow</span>
            {{ isRunning ? '分析中...' : isFromHistory ? '再次分析' : '启动 AI 分析' }}
          </button>
        </div>
      </section>

      <!-- ── 实时分析报告 ─────────────────────────────────── -->
      <section v-if="liveReportLines.length" class="fac-report-card">
        <div class="fac-report-card__head">
          <span class="mso">description</span>
          <h2 class="fac-report-card__title">{{ isRunning ? '实时分析报告' : '分析报告' }}</h2>
          <span v-if="isRunning" class="fac-report-card__live">
            <span class="fac-report-card__live-dot" />
            实时输出
          </span>
        </div>
        <div class="fac-report-card__body" ref="liveEl">
          <div
            v-for="(line, i) in liveReportLines"
            :key="i"
            class="fac-report-line"
            :class="'fac-report-line--' + line.type"
          >{{ line.text }}</div>
        </div>
      </section>

      <!-- ── 分析结果（完成后展示）──────────────────────── -->
      <template v-if="isDone && result">

        <!-- 共识标尺 -->
        <section v-if="structured" class="fac-consensus-card">
          <div class="fac-consensus__gauge">
            <svg viewBox="0 0 96 96" class="fac-consensus__svg">
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
                class="fac-consensus__arc"
                />
              <text x="48" y="44" text-anchor="middle" class="fac-consensus__num">{{ confidence }}</text>
              <text x="48" y="58" text-anchor="middle" class="fac-consensus__unit">%</text>
              </svg>
            </div>
          <div class="fac-consensus__right">
            <div class="fac-consensus__stance-row">
              <span class="fac-stance-tag" :class="'fac-stance-tag--' + (structured?.stance || 'neutral')">
                {{ stanceLabel }}
              </span>
              <span class="fac-consensus__conf-label">信心指数 {{ confidence }}%</span>
            </div>
            <p class="fac-consensus__comm">{{ structured?.marketCommentary || '' }}</p>
            <p class="fac-consensus__advice"><strong>策略建议：</strong>{{ structured?.positionAdvice || '' }}</p>
            <div v-if="structured?.riskWarning" class="fac-consensus__warning">
              <span class="mso">warning</span>
              {{ structured.riskWarning }}
            </div>
          </div>
        </section>

        <!-- 推荐股票（对齐设计图） -->
        <section v-if="recommendedStocks.length" class="fac-recs-card">
          <h2 class="fac-recs__title">
            <span class="mso">star</span>
            推荐结果
          </h2>
          <div>
            <div
              v-for="(s, i) in recommendedStocks"
              :key="i + '-' + (s.routeCode || s.code)"
              class="fac-rec-item"
            >
              <!-- 顶部：名称 + 评级 + 趋势标签 -->
              <div class="fac-rec-item__top">
                <div class="fac-rec-item__name-group">
                  <div class="fac-rec-item__name">
                    {{ s.name }}
                    <span class="fac-rec-item__code-badge">{{ s.displayCode }}</span>
                    <span v-if="s.grade" class="fac-rec-item__grade-badge" :class="'fac-rec-item__grade-badge--' + s.grade.toLowerCase()">
                      {{ s.grade }}
                    </span>
                    </div>
                  <!-- 现价 + 涨跌幅 -->
                  <div v-if="s.price || s.chg_pct !== 0" class="fac-rec-item__price-row">
                    <span v-if="s.price" class="fac-rec-item__price">{{ s.price }}</span>
                    <span v-if="s.chg_pct !== 0" class="fac-rec-item__chg" :class="s.chg_pct >= 0 ? 'fac-rec-item__chg--up' : 'fac-rec-item__chg--down'">
                      {{ s.chg_pct >= 0 ? '+' : '' }}{{ s.chg_pct }}%
                    </span>
                    <span v-if="s.score > 0" class="fac-rec-item__score-chip">
                      <span class="mso">star</span>
                      {{ s.score }}分
                    </span>
                  </div>
                </div>
                <div class="fac-rec-item__badges">
                  <span v-if="s.trendTag || s.adviseType" class="fac-rec-item__trend-chip">
                    <span class="mso">{{ s.trendTag.includes('高动能') || s.adviseType.includes('打板') ? 'bolt' : s.trendTag.includes('强势') || s.trendTag.includes('突破') ? 'trending_up' : 'favorite' }}</span>
                    {{ s.trendTag || s.adviseType }}
                  </span>
                  <span v-if="s.sector" class="fac-rec-item__sector-chip">{{ s.sector }}</span>
                  <span v-if="s.riskLevel" class="fac-rec-item__risk-chip" :class="'fac-rec-item__risk-chip--' + s.riskLevel">
                    {{ s.riskLevel }}风险
                  </span>
                </div>
              </div>

              <!-- 信号标签行 -->
              <div v-if="s.signal" class="fac-rec-item__signals">
                <span
                  v-for="(sig, si) in s.signal.split('/').filter(Boolean)"
                  :key="si"
                  class="fac-rec-item__signal-chip"
                >{{ sig.trim() }}</span>
              </div>

              <!-- 核心指标网格 -->
              <div class="fac-rec-item__metrics">
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">目标盈利</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--up">
                    {{ s.targetProfit || '--' }}
                  </p>
                </div>
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">硬性防守</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--down">
                    {{ s.hardStop || '--' }}
                  </p>
                </div>
                <div class="fac-rec-item__metric">
                  <p class="fac-rec-item__metric-label">合理建仓区间</p>
                  <p class="fac-rec-item__metric-value fac-rec-item__metric-value--range">
                    {{ s.priceRange || '--' }}
                  </p>
                </div>
              </div>

              <!-- 操作信息：仓位 + 持股周期 -->
              <div v-if="s.positionRatio || s.holdPeriod" class="fac-rec-item__ops">
                <span v-if="s.positionRatio" class="fac-rec-item__op-chip">
                  <span class="mso">account_balance_wallet</span>
                  {{ s.positionRatio }}
                </span>
                <span v-if="s.holdPeriod" class="fac-rec-item__op-chip">
                  <span class="mso">schedule</span>
                  {{ s.holdPeriod }}
                </span>
              </div>

              <!-- 推荐逻辑 -->
              <div class="fac-rec-item__reason">
                <p class="fac-rec-item__reason-label">
                  <span class="mso">lightbulb</span>
                  推荐逻辑
                </p>
                <p class="fac-rec-item__reason-text">{{ s.reason || '暂无详细逻辑说明' }}</p>
              </div>

              <!-- 底部：收藏按钮 -->
              <div class="fac-rec-item__footer">
                <button
                  type="button"
                  class="fac-btn-fav"
                  :class="{ 'fac-btn-fav--on': favAdded[s.routeCode] }"
                  :disabled="favBusy[s.routeCode]"
                  @click="favoriteStock(s)"
                >
                  <span class="mso">{{ favAdded[s.routeCode] ? 'favorite' : 'favorite_border' }}</span>
                  {{ favAdded[s.routeCode] ? '已自选' : '加入自选' }}
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- 任务拆解 -->
        <section v-if="hasTaskDecomposition" class="fac-decomp-card">
          <div class="fac-decomp-card__head">
            <span class="mso">assignment</span>
            <h2 class="fac-decomp-card__title">任务拆解</h2>
          </div>
          <div class="fac-decomp-card__body">
            <div
              v-for="(step, idx) in taskDecomposition"
              :key="idx"
              class="fac-decomp-step"
            >
              <div class="fac-decomp-step__header">
                <span class="fac-decomp-step__num">{{ idx + 1 }}</span>
                <span class="fac-decomp-step__title">{{ step.title || step.name || `步骤 ${idx + 1}` }}</span>
              </div>
              <p class="fac-decomp-step__desc">{{ step.description || step.desc || step.content || '' }}</p>
            </div>
          </div>
        </section>
      </template>

    </main>

    <!-- 底部分享栏 -->
    <div v-if="isDone" class="fac-bottom-bar">
      <button type="button" class="fac-btn-share" @click="printReport">
        <span class="mso">share</span>
        分享此深度报告
      </button>
    </div>

    <!-- Footer: Risk Disclosure -->
    <footer class="fac-footer">
      <div class="fac-footer__inner">
        <div class="fac-footer__warn">
          <span class="mso">warning</span>
          Risk Disclosure
      </div>
        <p class="fac-footer__text">
          免责声明：本智能体所提供的所有分析仅供参考，不构成任何形式的投资建议。市场有风险，投资需谨慎。AI 智能分析可能存在延迟或算法误差，用户应根据自身风险承受能力独立做出决策。
        </p>
      </div>
    </footer>

    <!-- Prompt Modal -->
    <div v-if="showPromptModal" class="fac-modal-overlay" @click.self="showPromptModal = false">
      <div class="fac-modal">
        <div class="fac-modal__header">
          <h3 class="fac-modal__title">{{ agentName }} - 提示词模板</h3>
          <button type="button" class="fac-modal__close" @click="showPromptModal = false" aria-label="关闭">
            <span class="mso">close</span>
          </button>
        </div>
        <div class="fac-modal__body">
          <div class="fac-modal__section">
            <h4 class="fac-modal__label">System Prompt</h4>
            <pre class="fac-modal__code">{{ realPrompts.systemPrompt || '加载中...' }}</pre>
          </div>
          <div class="fac-modal__section">
            <h4 class="fac-modal__label">User Prompt 模板</h4>
            <pre class="fac-modal__code">{{ realPrompts.userPrompt || '加载中...' }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>

</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { analyzeWithAgent, fetchTodayAnalysis, fetchAgentInfo } from '@/api/agents.js'
import { watchlist } from '@/api/strategy.js'
import TaskProcessCard from './components/TaskProcessCard.vue'

const route = useRoute()
const router = useRouter()

const agentId = computed(() => route.params.id || 'jun')
const agentName = computed(() => _nameMap[agentId.value] || agentId.value)
const roleSubtitle = computed(() => _roleMap[agentId.value] || '')
const agentInitial = computed(() => {
  const n = (result.value?.name_brand || result.value?.agent_name || agentName.value || '').trim()
  for (const ch of n) {
    if (ch && !/\s/.test(ch)) return ch
  }
  return '?'
})

const _nameMap = {
  jun: '钧哥天下无双', qiao: '乔帮主', jia: '炒股养家',
  speed: '极速先锋', trend: '趋势追随者', quant: '量化之翼',
  deepseek: '深度思考者', beijing: '北京炒家',
}
const _roleMap = {
  jun: '龙头战法', qiao: '板块轮动', jia: '低位潜伏',
  speed: '打板专家', trend: '中线波段', quant: '算法回测',
  deepseek: '深度推理', beijing: '游资打板',
}

const agentDescMap = {
  jun: '专注挖掘市场领涨龙头，捕捉短线爆发动能，并针对高频情绪波动进行深度解析与即时反馈。',
  qiao: '擅长识别板块轮动节奏，在热点切换中精准定位下一个接力方向，灵活调整配置策略。',
  jia: '注重安全边际与价值回归，在市场恐慌时逆向布局低位优质筹码，追求稳健收益。',
  speed: '专注于打板策略，识别最强封板意愿，结合量价关系寻找最优介入时机。',
  trend: '追踪中期趋势方向，结合均线系统与动能指标，把握波段性机会。',
  quant: '运用量化模型与回测数据，从统计学角度验证交易逻辑的可靠性。',
  deepseek: '宏观+行业+个股三维共振；布林带+资金流+催化剂三角验证。',
  beijing: '三有量化选板，六大板型机械执行，1/8仓铁律护本。',
}

// 任务标签配置（beijing 五步为核心）
const agentTaskTags = {
  beijing: [
    { label: '联网搜索', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54' },
    { label: '三有筛选', icon: 'M3 5v14h18V5H3zm16 12H5V7h14v10z' },
    { label: '板型分类', icon: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z' },
    { label: '仓位分配', icon: 'M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z' },
    { label: '离场预案', icon: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z' },
  ],
  deepseek: [
    { label: '宏观研判', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z' },
    { label: '行业验证', icon: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z' },
    { label: '个股筛选', icon: 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z' },
    { label: '风险评估', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z' },
  ],
}

const taskTags = computed(() => agentTaskTags[agentId.value] || [])

// ── 生命周期 & 请求取消 ─────────────────────────────────────────────────
let abortCtrl = null

onBeforeUnmount(() => {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  isRunning.value = false
})

onMounted(async () => {
  try {
    const today = await fetchTodayAnalysis(agentId.value)
    if (today) {
      const ar = today.analysis_result || {}
      const st = ar.structured || {}
      result.value = {
        agent_id: today.agent_id || agentId.value,
        agent_name: st.agentName || agentName.value,
        name_brand: st.agentName || agentName.value,
        structured: st,
        analysis: ar.raw_text || today.raw_response_text || ar.analysis || '',
        thinking: ar.thinking || today.thinking_text || '',
        report_date: today.report_date,
        report_time: today.report_time,
        tokens_used: today.tokens_used || 0,
      }
      if (result.value.thinking) {
        const lines = result.value.thinking.trim().split('\n').filter(Boolean)
          .map(line => {
            let t = line.trim()
            while (t.startsWith('思考中:') || t.startsWith('思考中 ')) {
              t = t.replace(/^思考中[:：]\s*/, '')
            }
            return t
          })
          .filter(Boolean)
        thinkingLines.value = lines
        // 历史记录：把 thinking 内容填充到 liveReportLines 用于展示
        liveReportLines.value = lines.map(text => ({
          text,
          type: text.startsWith('【') ? 'section' : 'normal',
        }))
      }
        isDone.value = true
        isFromHistory.value = true
        return
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载今日记录失败:', e)
  }

  // 加载 Agent 信息（tagline 等）
  try {
    const info = await fetchAgentInfo(agentId.value)
    if (info) {
      agentInfo.value = info
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载 Agent 信息失败:', e)
  }

})
const isRunning = ref(false)
const isDone = ref(false)
const isFromHistory = ref(false)
const result = ref(null)
const favBusy = ref({})
const favAdded = ref({})
const showPromptModal = ref(false)
const thinkingLines = ref([])
const liveReportLines = ref([])
const normalBuffer = []
const liveEl = ref(null)
let thinkingBuffer = ''
const realPrompts = ref({ systemPrompt: '', userPrompt: '' })
const agentInfo = ref({ tagline: '' })

// 思考过程展开/折叠状态（分析中可折叠以减少干扰）
const thinkingExpanded = ref(true)

// COT 任务拆解状态
const cotSteps = ref([])        // [{step, title, desc, done}]
const currentCotStep = ref(0)
const totalCotSteps = ref(5)
const currentCotTitle = ref('')
const currentStepDetail = ref('')   // 当前步骤详细描述（用于 TaskProcessCard）
const cotDataLines = ref([])    // 数据获取过程的输出

// ── 加载真实 prompt（弹窗打开时）─────────────────────────────────────
watch(showPromptModal, async (open) => {
  if (!open || realPrompts.value.systemPrompt) return
  try {
    const data = await fetchAgentInfo(agentId.value)
    if (data) {
      realPrompts.value.systemPrompt = data.system_prompt || ''
      realPrompts.value.userPrompt = data.user_prompt_template || ''
    }
  } catch (e) {
    console.warn('[AgentAnalysis] 加载 prompt 失败:', e)
  }
})

// ── 计算属性 ────────────────────────────────────────────────────────────────
const structured = computed(() => result.value?.structured)
const confidence = computed(() => structured.value?.confidence ?? 0)
const recommendedStocks = computed(() => {
  const raw = structured.value?.recommendedStocks ?? []
  if (!Array.isArray(raw)) return []
  return raw.map(s => normalizeRecRow(s)).filter(Boolean)
})

const stanceLabel = computed(() => {
  const m = { bull: '看多', bear: '看空', neutral: '中性' }
  return m[structured.value?.stance] || '中性'
})

const stanceColor = computed(() => {
  const m = { bull: '#f23645', bear: '#089981', neutral: '#717786' }
  return m[structured.value?.stance] || '#717786'
})

const gaugeR = 40
const gaugeCirc = computed(() => 2 * Math.PI * gaugeR)
const gaugeOffset = computed(() => gaugeCirc.value * (1 - confidence.value / 100))

const analysisText = computed(() => result.value?.analysis || result.value?.thinking || '')

// 是否有真实思考内容（非占位符）
const hasThinkingContent = computed(() => {
  return thinkingLines.value.some(l =>
    l && !l.startsWith('[阶段]') &&
    l !== 'Waiting to start...' &&
    !l.startsWith('[调用工具]') &&
    !l.startsWith('[数据]')
  )
})

// ── 任务拆解（层次化模式特有）────────────────────────────────────────────
const hasTaskDecomposition = computed(() => {
  const decomp = result.value?.task_decomposition
  return Array.isArray(decomp) && decomp.length > 0
})

const taskDecomposition = computed(() => {
  const decomp = result.value?.task_decomposition
  return Array.isArray(decomp) ? decomp : []
})

const systemPromptPreview = computed(() => {
  return `你是一位专业的A股短线交易策略分析师，代号「${agentName.value}」，使用${roleSubtitle.value}风格。
你拥有丰富的题材炒作、龙头战法、板块轮动实战经验，熟悉游资操盘手法与量化指标。
请始终以专业、严谨、客观的态度输出分析，禁止提供具体买卖价格建议。`
})

const userPromptPreview = computed(() => {
  const m = {
    'jun': '请根据以下今日市场数据，从龙头视角给出你的策略分析...',
    'qiao': '请根据以下今日市场数据，分析板块轮动节奏与配置方向...',
    'jia': '请根据以下市场数据，从价值与安全边际角度给出分析...',
    'speed': '请根据以下市场数据，分析打板机会与风险...',
    'trend': '请根据以下市场数据，分析中期趋势方向与波段机会...',
    'quant': '请根据以下市场数据，给出量化视角的分析...',
    'deepseek': '请从宏观+行业+个股三维深度推理，结合扫描数据给出分析...',
    'beijing': '请根据三有量化标准和六大板型，识别今日最强涨停板机会...',
  }
  return m[agentId.value] || '正在加载 Prompt...'
})

// ── 工具函数 ────────────────────────────────────────────────────────────────
function scrollLive() {
  nextTick(() => {
    if (liveEl.value) {
      liveEl.value.scrollTop = liveEl.value.scrollHeight
    }
  })
}

function roleColor(role) {
  if (!role) return 'neutral'
  if (role.includes('龙头') || role.includes('中军')) return 'primary'
  if (role.includes('跟风') || role.includes('补涨')) return 'muted'
  return 'neutral'
}

function stockRouteCode6(code) {
  const s = String(code || '').trim()
  const m = s.match(/^(\d{6})/)
  if (m) return m[1]
  const digits = s.replace(/\D/g, '')
  return digits.length >= 6 ? digits.slice(0, 6) : digits
}

function normalizeRecRow(s) {
  if (!s || typeof s !== 'object') return null
  const codeRaw = String(s.code || '').trim()
  const routeCode = stockRouteCode6(codeRaw)

  // 涨跌幅：changePct / chg_pct / change_pct
  const chgRaw = s.changePct ?? s.chg_pct ?? s.change_pct
  const chg = Number(chgRaw)
  const chg_pct = Number.isFinite(chg) ? Math.round(chg * 100) / 100 : 0

  // 现价（后端已补调，不应为 0）
  const price = s.price !== undefined && s.price !== null && s.price !== ''
    ? String(s.price) : ''

  const name = String(s.name || '').trim()
  const displayCode = codeRaw || routeCode || '--'

  // 趋势标签：从 grade / adviseType 综合判断
  const gradeRaw = String(s.grade || '').trim()
  const adviseType = String(s.adviseType || '').trim()
  const signal = String(s.signal || '').trim()
  let trendTag = String(s.trendTag || '').trim()
  if (!trendTag) {
    const gradeMap = { 'S': '顶级标的', 'A': '重点关注', 'B': '普通关注', 'C': '观察标的' }
    if (gradeRaw && gradeMap[gradeRaw]) trendTag = gradeMap[gradeRaw]
    else if (adviseType) trendTag = adviseType
  }

  // 目标盈利
  let targetProfit = String(s.targetProfit || s.profit_target || '').trim()
  if (!targetProfit && s.targetPrice) targetProfit = String(s.targetPrice)
  if (!targetProfit && s.target) targetProfit = String(s.target)

  // 硬性止损
  const hardStop = String(s.hardStop || s.stopLoss || s.stop_loss || '').trim()

  // 建仓区间
  const priceRange = String(s.priceRange || s.price_range || s.entry_range || s.buyRange || '').trim()

  // 推荐逻辑
  const reason = String(s.meta || s.reason || signal || '').trim()

  return {
    ...s,
    name,
    routeCode,
    displayCode,
    chg_pct,
    price,
    trendTag,
    targetProfit,
    hardStop,
    priceRange,
    reason,
    grade: gradeRaw,
    adviseType,
    signal,
  }
}

function goStockDetail(s) {
  const c = s.routeCode
  if (!c || !/^\d{6}$/.test(c)) return
  router.push({ name: 'StockDetail', params: { code: c } })
}

async function favoriteStock(s) {
  const code = s.routeCode
  if (!code || !/^\d{6}$/.test(code)) return
  if (favAdded.value[code]) return
  favBusy.value = { ...favBusy.value, [code]: true }
  try {
    await watchlist.add(code, s.name || '', s.sector || '')
    favAdded.value = { ...favAdded.value, [code]: true }
  } catch (e) {
    console.warn('[AgentAnalysis] 加自选失败', e)
  } finally {
    const next = { ...favBusy.value }
    delete next[code]
    favBusy.value = next
  }
}

// 合并普通内容缓冲区：积累的短句合并成一段输出
function flushNormalBuffer() {
  if (!normalBuffer.length) return
  const text = normalBuffer.join(' ')
  thinkingLines.value.push(text)
  liveReportLines.value.push({ text, type: 'normal' })
  normalBuffer.length = 0
}

// ── 分析执行 ────────────────────────────────────────────────────────────────
async function runAnalysis() {
  if (isRunning.value) return
  isRunning.value = true
  isDone.value = false
  isFromHistory.value = false
  result.value = null
  thinkingLines.value = []
  liveReportLines.value = []
  thinkingBuffer = ''
  normalBuffer.length = 0
  cotSteps.value = []
  currentCotStep.value = 0

  abortCtrl = new AbortController()

  try {
    // 使用流式接口
    await runAnalysisStream(agentId.value, abortCtrl.signal)
  } catch (err) {
    console.warn('[AgentAnalysis] 分析中断:', err.message)
    if (err.message !== '分析已取消') {
      console.error('[AgentAnalysis] 分析失败:', err)
    }
  } finally {
    isRunning.value = false
    abortCtrl = null
  }
}

async function runAnalysisStream(agentId, signal) {
  console.log('[AgentAnalysisStream] 开始请求流式接口:', agentId)
  const response = await fetch(`/api/agents/analyze/${agentId}/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal,
  })

  console.log('[AgentAnalysisStream] 响应状态:', response.status, response.statusText)
  console.log('[AgentAnalysisStream] Response headers:', Object.fromEntries(response.headers.entries()))

  if (!response.ok) {
    // 尝试读取错误响应
    let text
    try {
      text = await response.text()
      console.error('[AgentAnalysisStream] 错误响应体:', text)
    } catch (e) {
      text = ''
    }
    // 尝试从 SSE 格式解析错误信息
    try {
      const lines = text.split('\n\n')
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          if (data.type === 'error') {
            throw new Error(data.error || '请求失败')
          }
        }
      }
    } catch (e) {
      if (e.message !== '请求失败') throw e
    }
    throw new Error(text || `请求失败 (HTTP ${response.status})`)
  }

  // 检查 Content-Type
  const contentType = response.headers.get('content-type') || ''
  console.log('[AgentAnalysisStream] Content-Type:', contentType)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      console.log('[AgentAnalysisStream] 流读取完成')
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    console.log('[AgentAnalysisStream] 收到数据块, 行数:', lines.length, 'buffer长度:', buffer.length)

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue
      if (!trimmed.startsWith('data: ')) continue
      const payload = trimmed.slice(6).trim()
      if (payload === '[DONE]') {
        continue
      }

      try {
        const data = JSON.parse(payload)
        handleStreamEvent(data)
      } catch (e) {
        console.warn('[Stream] 解析失败:', payload, e)
      }
    }
  }
}

function handleStreamEvent(data) {
  switch (data.type) {
    case 'task_step': {
      // 任务执行过程：前端展示步骤进度
      const step = data.step || 1
      const total = data.total || 5
      const title = data.title || ''
      const desc = data.desc || ''

      currentCotStep.value = step
      totalCotSteps.value = total
      currentCotTitle.value = title
      currentStepDetail.value = desc

      // 更新或追加步骤
      const existing = cotSteps.value.find(s => s.step === step)
      if (existing) {
        existing.title = title
        existing.desc = desc
      } else {
        cotSteps.value.push({ step, title, desc, done: false })
        cotSteps.value.sort((a, b) => a.step - b.step)
      }
      break
    }

    case 'cot': {
      currentCotStep.value = data.step || 0
      totalCotSteps.value = data.total || 5
      currentCotTitle.value = data.title || ''
      thinkingLines.value.push(`[阶段] ${data.title} → ${data.message}`)
      break
    }

    case 'cot_step': {
      flushNormalBuffer()
      cotSteps.value.push({
        step: data.step,
        title: data.title,
        desc: data.desc,
        done: data.step < (currentCotStep.value || 0),
      })
      thinkingLines.value.push(`[步骤${data.step}] ${data.title}：${data.desc}`)
      break
    }

    case 'cot_data': {
      flushNormalBuffer()
      const lines = data.lines || []
      for (const line of lines) {
        cotDataLines.value.push({ step: data.step, text: line })
        thinkingLines.value.push(`[数据] ${line}`)
        // 检测错误标记，停止等待状态
        if (line.includes('[警告]') || line.includes('[错误]') || line.includes('[失败]')) {
          isRunning.value = false
        }
      }
      break
    }

    case 'thinking': {
      // 整块接收 thinking 内容，按章节分隔符（【）分批推送
      const raw = data.content || ''
      let i = 0

      while (i < raw.length) {
        // 找到下一个【标题的位置
        const nextSection = raw.indexOf('【', i)
        if (nextSection === -1) {
          // 没有更多【，积累剩余内容
          thinkingBuffer += raw.slice(i)
          break
        }

        // 先把【之前的内容（如果有）作为普通段落 flush
        if (thinkingBuffer) {
          const beforeText = thinkingBuffer.trim()
          if (beforeText) {
            thinkingLines.value.push(beforeText)
            liveReportLines.value.push({ text: beforeText, type: 'normal' })
          }
          thinkingBuffer = ''
        }

        // 收集完整的【章节块（到下一个【之前或字符串末尾）
        const sectionStart = nextSection
        const sectionEnd = raw.indexOf('【', nextSection + 1)
        const sectionText = sectionEnd === -1
          ? raw.slice(sectionStart)
          : raw.slice(sectionStart, sectionEnd)

        // 去掉"思考中: "前缀
        let cleanSection = sectionText.replace(/^思考中[:：]\s*/, '')
        cleanSection = cleanSection.trim()
        if (cleanSection) {
          thinkingLines.value.push(cleanSection)
          liveReportLines.value.push({ text: cleanSection, type: 'section' })
        }

        i = sectionEnd === -1 ? raw.length : sectionEnd
        scrollLive()
      }
      break
    }

    case 'content': {
      // 正文内容：push 到实时报告区
      break
    }

    case 'analysis': {
      // 同步分析模式下的最终报告分段（联网思考已完成，最终报告分段输出）
      const text = (data.content || '').trim()
      if (text) {
        const type = text.startsWith('【') ? 'section' : 'normal'
        liveReportLines.value.push({ text, type })
        scrollLive()
      }
      break
    }

    case 'status':
      // 更新进度提示
      break

    case 'tool_call':
      // 展示正在调用的工具及参数
      flushNormalBuffer()
      const args = data.args || {}
      thinkingLines.value.push(`[调用] ${data.tool} → 参数: ${JSON.stringify(args)}`)
      break

    case 'tool_result': {
      // 展示 qwen 返回的数据内容
      const raw = data.result || ''
      // 尝试解析为可读格式
      let display = raw
      try {
        const parsed = JSON.parse(raw)
        display = JSON.stringify(parsed, null, 2)
      } catch {}
      // 截断过长数据
      const lines = display.split('\n')
      const truncated = lines.length > 30 ? lines.slice(0, 30).join('\n') + '\n... (共' + lines.length + '行)' : display
      thinkingLines.value.push(`[结果] ${truncated}`)
      break
    }

    case 'done':
      // flush 剩余 thinking
      if (thinkingBuffer.trim()) {
        const text = thinkingBuffer.trim()
        liveReportLines.value.push({ text, type: 'normal' })
        thinkingLines.value.push(text)
        thinkingBuffer = ''
      }
      // 如果没有实时内容但有分析文本，转成报告
      if (!liveReportLines.value.length && data.analysis) {
        const lines = data.analysis.split('\n').filter(l => l.trim())
        for (const l of lines) {
          const text = l.trim()
          const type = text.startsWith('【') ? 'section' : 'normal'
          liveReportLines.value.push({ text, type })
        }
      }
      const st = data.structured || {}
      result.value = {
        agent_id: data.agent_id,
        agent_name: data.agent_name,
        structured: st,
        analysis: data.analysis,
        thinking: data.thinking,
        tokens_used: data.tokens_used,
        // 同步 stance / confidence 到 cotSteps 用于 TaskProcessCard 的共识仪表
        cot_steps_confidence: st.confidence || 0,
        cot_steps_stance: st.stance || 'neutral',
        cot_steps_marketCommentary: st.marketCommentary || '',
        // 任务拆解数据
        task_decomposition: data.task_decomposition || [],
      }
      isDone.value = true
      // 分析完成：将所有 COT 步骤标记为已完成，flush 剩余缓冲区
      flushNormalBuffer()
      cotSteps.value = cotSteps.value.map(s => ({ ...s, done: true }))
      break

    case 'error':
      throw new Error(data.error || '流式分析错误')
  }
}

function resetAnalysis() {
  isRunning.value = false
  isDone.value = false
  result.value = null
  isFromHistory.value = false
  favAdded.value = {}
  favBusy.value = {}
  thinkingLines.value = []
  liveReportLines.value = []
  thinkingBuffer = ''
  normalBuffer.length = 0
  cotSteps.value = []
  currentCotStep.value = 0
  totalCotSteps.value = 5
  currentCotTitle.value = ''
  currentStepDetail.value = ''
  currentStepDetail.value = ''
  cotDataLines.value = []
  thinkingExpanded.value = true
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/strategy/agents')
}

function printReport() {
  window.print()
}
</script>

<style scoped>
/* ── Precision Ledger Design System ────────────────────────────────────── */

/* Color Palette — root vars */
.fac-root {
  /* Primary: Deep Ocean Navy */
  --primary: #3b1f8c;
  --primary-container: #5a34a8;
  --on-primary: #ffffff;
  --on-primary-container: #e8deff;
  --primary-fixed: #e8deff;
  --primary-fixed-dim: #c9b8ff;
  --on-primary-fixed: #26005a;
  --on-primary-fixed-variant: #4600b3;

  /* Surface Tiers (No-line tonal hierarchy) */
  --surface: #f5f2ff;
  --surface-bright: #f5f2ff;
  --surface-container-lowest: #ffffff;
  --surface-container-low: #ede8ff;
  --surface-container: #e5e0ff;
  --surface-container-high: #ddd8ff;
  --surface-container-highest: #d5d0ff;
  --surface-dim: #c7c2eb;
  --surface-variant: #ddd8ff;

  /* Semantic — A股红涨绿跌 */
  --secondary: #6b3fa0;
  --secondary-container: #e5d0ff;
  --secondary-fixed: #eed9ff;
  --secondary-fixed-dim: #dab8ff;
  --on-secondary: #ffffff;
  --on-secondary-container: #4a0080;
  --on-secondary-fixed: #380066;
  --on-secondary-fixed-variant: #5600b3;

  --tertiary: #390002;
  --tertiary-container: #600007;
  --tertiary-fixed: #ffdad6;
  --tertiary-fixed-dim: #ffb3ac;
  --on-tertiary: #ffffff;
  --on-tertiary-container: #ff5a53;
  --on-tertiary-fixed: #410003;
  --on-tertiary-fixed-variant: #930010;

  --error: #ba1a1a;
  --error-container: #ffdad6;
  --on-error: #ffffff;
  --on-error-container: #93000a;

  /* Neutrals */
  --background: #f5f2ff;
  --on-background: #1e1633;
  --on-surface: #1e1633;
  --on-surface-variant: #464455;
  --inverse-surface: #2d2449;
  --inverse-on-surface: #f0ecff;
  --inverse-primary: #c9b8ff;

  --outline: #747780;
  --outline-variant: rgba(196, 198, 208, 0.3);

  /* A股涨跌语义 */
  --up: #f23645;
  --up-alpha: rgba(242, 54, 69, 0.1);
  --down: #089981;
  --down-alpha: rgba(8, 153, 129, 0.1);

  /* Elevation */
  --shadow-card: 0 8px 24px rgba(46, 36, 73, 0.06);
  --shadow-nav: 0 -4px 20px rgba(46, 36, 73, 0.08);
  --shadow-header: 0 8px 24px rgba(46, 36, 73, 0.06);
  --track: #c7c2eb;

  /* Typography */
  --font-headline: 'Manrope', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-body: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'Roboto Mono', 'SF Mono', Menlo, monospace;
}

.fac-root {
  font-family: var(--font-body);
  min-height: 100dvh;
  background: var(--surface);
  color: var(--on-surface);
  -webkit-font-smoothing: antialiased;
}

/* ── TopAppBar ─────────────────────────────────────────────────────────── */
.fac-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 64px;
  padding: 0 24px;
  background: rgba(245, 242, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--shadow-header);
  transition: background 0.2s;
}

.fac-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.fac-header__icon-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--on-surface);
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
  flex-shrink: 0;
}
.fac-header__icon-btn:active { transform: scale(0.92); }
.fac-header__icon-btn:hover { background: rgba(221, 216, 255, 0.6); }
.fac-header__icon-btn .mso { font-size: 24px; }

.fac-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.fac-header__avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--on-primary);
  font-family: var(--font-headline);
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.03em;
  flex-shrink: 0;
}

.fac-header__title-group {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.fac-header__title {
  font-family: var(--font-headline);
  font-size: 1.05rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.fac-header__subtitle {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--on-surface-variant);
}

.fac-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fac-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.fac-badge--history {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-badge--running {
  background: rgba(0, 22, 55, 0.1);
  color: var(--primary);
}
.fac-badge--done {
  background: rgba(8, 153, 129, 0.1);
  color: var(--down);
}
.fac-badge--pending {
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
.fac-badge__dot--spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Main Canvas ─────────────────────────────────────────────────────── */
.fac-main {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 16px 100px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Prompt Card ─────────────────────────────────────────────────────── */
.fac-prompt-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
  position: relative;
  overflow: hidden;
}
.fac-prompt-card__glow {
  position: absolute;
  top: -20px;
  right: -20px;
  width: 120px;
  height: 120px;
  background: var(--primary-container);
  opacity: 0.06;
  border-radius: 0 0 0 100%;
  pointer-events: none;
}
.fac-prompt-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  position: relative;
  z-index: 1;
}
.fac-prompt-card__title {
  font-family: var(--font-headline);
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--on-surface);
  display: flex;
  align-items: center;
  gap: 8px;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-prompt-card__title .mso {
  color: var(--primary-container);
  font-size: 20px;
}
.fac-prompt-card__expand {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 500;
  color: var(--on-surface-variant);
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: color 0.15s, background 0.15s;
}
.fac-prompt-card__expand:hover { color: var(--primary); background: rgba(0, 22, 55, 0.05); }
.fac-prompt-card__expand .mso { font-size: 16px; }
.fac-prompt-card__code {
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 16px;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.8;
  color: var(--on-surface-variant);
  overflow-x: auto;
  position: relative;
  z-index: 1;
  border: 1px solid rgba(196, 198, 208, 0.15);
  white-space: pre-wrap;
  word-break: break-all;
}
.fac-prompt-card__code .kw { color: var(--primary-container); font-weight: 600; }

/* ── Thinking Timeline ──────────────────────────────────────────────── */
.fac-thinking-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
}
.fac-thinking-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  cursor: pointer;
  border-radius: 12px;
  padding: 4px;
  margin: -4px -4px 20px;
  transition: background 0.15s;
}
.fac-thinking-card__head:hover { background: rgba(207, 230, 242, 0.4); }
.fac-thinking-card__head:active { background: rgba(207, 230, 242, 0.7); }
.fac-thinking-card__head .mso {
  color: var(--primary-container);
  font-size: 20px;
}
.fac-thinking-card__title {
  font-family: var(--font-headline);
  font-size: 1.1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-thinking-card__count {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
  padding: 2px 8px;
  border-radius: 999px;
}
.fac-thinking-card__toggle {
  color: var(--on-surface-variant);
  transition: transform 0.2s;
  display: flex;
  align-items: center;
}
.fac-thinking-card__toggle--open { transform: rotate(180deg); }
.fac-thinking-card__toggle .mso { font-size: 20px; }

.fac-timeline {
  position: relative;
  padding-left: 36px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.fac-timeline::before {
  content: '';
  position: absolute;
  left: 14px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--surface-dim);
  border-radius: 1px;
}

.fac-timeline__item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  position: relative;
}
.fac-timeline__dot {
  position: absolute;
  left: -30px;
  top: 2px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--surface-container-highest);
  border: 2px solid var(--surface-container-lowest);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s;
}
.fac-timeline__dot .mso {
  font-size: 14px;
  color: var(--primary-container);
}
.fac-timeline__dot--active {
  background: var(--primary);
  border-color: var(--surface-container-lowest);
  box-shadow: 0 0 16px rgba(0, 22, 55, 0.35);
}
.fac-timeline__dot--active .mso {
  color: var(--on-primary);
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.fac-timeline__content {
  flex: 1;
  min-width: 0;
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 14px 16px;
  transition: all 0.3s;
}
.fac-timeline__content--active {
  background: rgba(0, 42, 93, 0.06);
  border: 1px solid rgba(0, 42, 93, 0.15);
}
.fac-timeline__content--done { opacity: 0.7; }

.fac-timeline__title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fac-timeline__dots {
  display: flex;
  gap: 3px;
  align-items: center;
}
.fac-timeline__dot-anim {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-container);
  animation: bounce 1s infinite;
}
.fac-timeline__dot-anim:nth-child(2) { animation-delay: 0.2s; }
.fac-timeline__dot-anim:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 100% { transform: translateY(0); opacity: 1; }
  50% { transform: translateY(-3px); opacity: 0.4; }
}

.fac-timeline__desc {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.6;
}

.fac-thinking-card__run-btn-wrap {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
.fac-btn-run {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 32px;
  border-radius: 999px;
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(7, 30, 39, 0.12);
  transition: background 0.15s, transform 0.1s, box-shadow 0.15s;
}
.fac-btn-run:hover {
  background: var(--primary-container);
  box-shadow: 0 12px 32px rgba(7, 30, 39, 0.18);
}
.fac-btn-run:active { transform: scale(0.97); }
.fac-btn-run:disabled { opacity: 0.5; cursor: not-allowed; }
.fac-btn-run--running {
  background: var(--on-surface-variant);
  box-shadow: none;
}
.fac-btn-run .mso { font-size: 20px; }
.fac-btn-run__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── Report Card ────────────────────────────────────────────────────── */
.fac-report-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  padding: 24px;
  box-shadow: var(--shadow-card);
}
.fac-report-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.fac-report-card__head .mso {
  color: var(--primary-container);
  font-size: 18px;
}
.fac-report-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-report-card__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--primary-container);
  background: rgba(0, 42, 93, 0.08);
  padding: 3px 10px;
  border-radius: 999px;
}
.fac-report-card__live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary-container);
  animation: pulse-dot 1.2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
}

.fac-report-card__body {
  background: var(--surface-container-low);
  border-radius: 16px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  scrollbar-width: thin;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.fac-report-line {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.75;
  color: var(--on-surface);
  animation: fadein 0.3s ease;
}
.fac-report-line--section {
  font-family: var(--font-headline);
  font-size: 14px;
  font-weight: 800;
  color: var(--primary-container);
  padding: 8px 0 4px;
  border-bottom: 1px solid rgba(196, 198, 208, 0.2);
  margin-top: 8px;
}
.fac-report-line--section:first-child { margin-top: 0; border-top: none; padding-top: 0; }
@keyframes fadein {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Consensus Gauge ────────────────────────────────────────────────── */
.fac-consensus-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  padding: 24px;
  background: var(--surface-container-lowest);
  border-radius: 24px;
  box-shadow: var(--shadow-card);
}
@media (max-width: 380px) { .fac-consensus-card { grid-template-columns: 1fr; } }

.fac-consensus__gauge {
  display: flex;
  align-items: center;
}
.fac-consensus__svg { width: 96px; height: 96px; }
.fac-consensus__arc { transition: stroke-dashoffset 1s ease; }
.fac-consensus__num {
  font-family: var(--font-headline);
  font-size: 20px;
  font-weight: 800;
  fill: var(--on-surface);
  font-variant-numeric: tabular-nums;
}
.fac-consensus__unit {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 600;
  fill: var(--on-surface-variant);
}

.fac-consensus__right { display: flex; flex-direction: column; gap: 8px; }
.fac-consensus__stance-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.fac-stance-tag {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  padding: 4px 14px;
  border-radius: 999px;
}
.fac-stance-tag--bull { background: var(--up-alpha); color: var(--up); }
.fac-stance-tag--bear { background: var(--down-alpha); color: var(--down); }
.fac-stance-tag--neutral { background: var(--surface-dim); color: var(--on-surface-variant); }

.fac-consensus__conf-label {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface-variant);
}
.fac-consensus__comm {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.65;
  color: var(--on-surface);
  margin: 0;
}
.fac-consensus__advice {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.65;
  color: var(--on-surface-variant);
  margin: 0;
}
.fac-consensus__advice strong { font-weight: 800; color: var(--on-surface); }
.fac-consensus__warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--error);
  background: rgba(186, 26, 26, 0.06);
  padding: 8px 12px;
  border-radius: 10px;
  line-height: 1.5;
}
.fac-consensus__warning .mso { font-size: 14px; flex-shrink: 0; }

/* ── Recommendations ────────────────────────────────────────────────── */
.fac-recs-card {
  padding: 0;
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.fac-recs__title {
  font-family: var(--font-headline);
  font-size: 1.2rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.02em;
  padding: 24px 24px 0;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.fac-recs__title .mso { color: var(--primary-container); font-size: 22px; }

.fac-rec-item {
  display: flex;
  flex-direction: column;
  padding: 20px 24px;
  border-top: 1px solid rgba(196, 198, 208, 0.15);
  position: relative;
  overflow: hidden;
  transition: background 0.15s;
}
.fac-rec-item:last-child { border-bottom: none; }
.fac-rec-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, transparent 0%, rgba(0, 42, 93, 0.025) 100%);
  opacity: 0;
  transition: opacity 0.3s;
  pointer-events: none;
}
.fac-rec-item:hover::before { opacity: 1; }

/* 顶部行：名称代码 | 标签 */
.fac-rec-item__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
  gap: 12px;
}
.fac-rec-item__name-group { display: flex; flex-direction: column; gap: 4px; }
.fac-rec-item__name {
  font-family: var(--font-headline);
  font-size: 1.3rem;
  font-weight: 800;
  color: var(--on-surface);
  letter-spacing: -0.03em;
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 8px;
}
.fac-rec-item__code-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--on-surface-variant);
  background: var(--surface-dim);
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.04em;
}
.fac-rec-item__grade-badge {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 800;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.03em;
}
.fac-rec-item__grade-badge--s { background: rgba(242, 54, 69, 0.12); color: var(--up); border: 1px solid rgba(242, 54, 69, 0.25); }
.fac-rec-item__grade-badge--a { background: rgba(0, 42, 93, 0.1); color: var(--primary-container); border: 1px solid rgba(0, 42, 93, 0.2); }
.fac-rec-item__grade-badge--b, .fac-rec-item__grade-badge--c { background: var(--surface-dim); color: var(--on-surface-variant); }

.fac-rec-item__badges { display: flex; gap: 6px; align-items: flex-start; flex-wrap: wrap; justify-content: flex-end; flex-shrink: 0; }
.fac-rec-item__trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 700;
  background: var(--up-alpha);
  color: var(--up);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.fac-rec-item__trend-chip .mso { font-size: 12px; }
.fac-rec-item__sector-chip {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  background: var(--surface-dim);
  color: var(--on-surface-variant);
}
.fac-rec-item__risk-chip {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.fac-rec-item__risk-chip--高 { background: var(--up-alpha); color: var(--up); }
.fac-rec-item__risk-chip--中 { background: rgba(0, 42, 93, 0.08); color: var(--primary-container); }
.fac-rec-item__risk-chip--低 { background: var(--down-alpha); color: var(--down); }

/* 信号行 */
.fac-rec-item__signals {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}
.fac-rec-item__signal-chip {
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(0, 42, 93, 0.07);
  color: var(--primary-container);
}

/* 指标网格 */
.fac-rec-item__metrics {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 10px;
  margin-bottom: 14px;
}
.fac-rec-item__metric {
  background: var(--surface-container-low);
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  text-align: center;
}
.fac-rec-item__metric-label {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--on-surface-variant);
  margin: 0;
}
.fac-rec-item__metric-value {
  font-family: var(--font-headline);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}
.fac-rec-item__metric-value--up { color: var(--up); }
.fac-rec-item__metric-value--down { color: var(--down); }
.fac-rec-item__metric-value--range {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--on-surface);
}

/* 现价+涨跌行 */
.fac-rec-item__price-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fac-rec-item__price {
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  color: var(--on-surface);
}
.fac-rec-item__chg {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.fac-rec-item__chg--up { color: var(--up); }
.fac-rec-item__chg--down { color: var(--down); }
.fac-rec-item__score-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
  color: var(--primary-container);
}
.fac-rec-item__score-chip .mso { font-size: 12px; }

/* 操作行 */
.fac-rec-item__ops {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.fac-rec-item__op-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--on-surface);
  background: var(--surface-container-low);
  padding: 4px 10px;
  border-radius: 8px;
}
.fac-rec-item__op-chip .mso { font-size: 14px; color: var(--on-surface-variant); }

/* 推荐逻辑 */
.fac-rec-item__reason {
  border-top: 1px solid rgba(196, 198, 208, 0.15);
  padding-top: 14px;
  margin-bottom: 14px;
}
.fac-rec-item__reason-label {
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 700;
  color: var(--on-surface-variant);
  margin: 0 0 6px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.fac-rec-item__reason-label .mso { font-size: 14px; color: var(--primary-container); }
.fac-rec-item__reason-text {
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.7;
  color: var(--on-surface);
  margin: 0;
}

/* 底部按钮 */
.fac-rec-item__footer {
  display: flex;
  justify-content: flex-end;
}
.fac-btn-fav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 999px;
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  background: var(--surface-dim);
  color: var(--on-surface);
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}
.fac-btn-fav:active { transform: scale(0.97); }
.fac-btn-fav:disabled { opacity: 0.5; }
.fac-btn-fav--on {
  background: var(--primary);
  color: var(--on-primary);
  box-shadow: 0 4px 16px rgba(7, 30, 39, 0.15);
}
.fac-btn-fav .mso { font-size: 16px; }

/* ── Task Decomposition ─────────────────────────────────────────────── */
.fac-decomp-card {
  background: var(--surface-container-lowest);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}
.fac-decomp-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-decomp-card__head .mso { color: var(--primary-container); font-size: 18px; }
.fac-decomp-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  letter-spacing: -0.02em;
  margin: 0;
}
.fac-decomp-card__body { padding: 16px 20px; display: flex; flex-direction: column; gap: 12px; }
.fac-decomp-step {
  padding: 14px 16px;
  background: var(--surface-container-low);
  border-radius: 12px;
  border-left: 4px solid var(--primary-container);
}
.fac-decomp-step__header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.fac-decomp-step__num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--primary-container);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.fac-decomp-step__title {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  color: var(--on-surface);
}
.fac-decomp-step__desc {
  font-family: var(--font-body);
  font-size: 12px;
  line-height: 1.6;
  color: var(--on-surface-variant);
  margin: 0;
  padding-left: 34px;
}

/* ── JSON Block ────────────────────────────────────────────────────── */
.fac-analysis-card { background: var(--surface-container-lowest); border-radius: 24px; overflow: hidden; box-shadow: var(--shadow-card); }
.fac-analysis-card__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-analysis-card__head .mso { color: var(--primary-container); font-size: 18px; }
.fac-analysis-card__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  flex: 1;
  margin: 0;
  letter-spacing: -0.02em;
}
.fac-json-block {
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: var(--on-surface);
  background: var(--surface-container-low);
  padding: 16px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Prompt Modal ───────────────────────────────────────────────────── */
.fac-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.fac-modal {
  background: var(--surface-container-lowest);
  border-radius: 20px;
  width: 100%;
  max-width: 680px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.2);
}
.fac-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  background: var(--surface-container-low);
  border-bottom: 1px solid rgba(196, 198, 208, 0.15);
  flex-shrink: 0;
}
.fac-modal__title {
  font-family: var(--font-headline);
  font-size: 1rem;
  font-weight: 800;
  color: var(--on-surface);
  margin: 0;
  letter-spacing: -0.02em;
}
.fac-modal__close {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--surface-dim);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--on-surface-variant);
  transition: background 0.15s;
}
.fac-modal__close:hover { background: var(--surface-container-highest); }
.fac-modal__close .mso { font-size: 18px; }
.fac-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 32px;
  display: flex;
  flex-direction: column;
  scrollbar-width: thin;
}
.fac-modal__section { padding: 20px 0; border-bottom: 1px solid rgba(196, 198, 208, 0.15); }
.fac-modal__section:last-child { border-bottom: none; }
.fac-modal__label {
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--primary-container);
  margin: 0 0 12px;
}
.fac-modal__code {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.75;
  color: var(--on-surface);
  background: var(--surface-container-low);
  border-radius: 12px;
  padding: 16px;
  margin: 0;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
  scrollbar-width: thin;
  border: 1px solid rgba(196, 198, 208, 0.15);
}

/* ── Bottom Bar ──────────────────────────────────────────────────────── */
.fac-bottom-bar {
  display: flex;
  justify-content: center;
  padding: 16px 20px;
  background: var(--surface);
}
.fac-btn-share {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 36px;
  border-radius: 16px;
  background: var(--primary);
  color: var(--on-primary);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(7, 30, 39, 0.15);
  transition: all 0.15s;
}
.fac-btn-share:hover {
  background: var(--primary-container);
  box-shadow: 0 12px 32px rgba(7, 30, 39, 0.2);
}
.fac-btn-share:active { transform: scale(0.97); }
.fac-btn-share .mso { font-size: 20px; }

/* 主内容区底部间距 */
.fac-main { padding-bottom: 24px; }

/* ── Footer ─────────────────────────────────────────────────────────── */
.fac-footer {
  margin-top: auto;
  padding: 24px 16px 40px;
  border-top: 1px solid rgba(196, 198, 208, 0.15);
}
.fac-footer__inner { max-width: 640px; margin: 0 auto; text-align: center; }
.fac-footer__warn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-body);
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--error);
  margin-bottom: 8px;
}
.fac-footer__warn .mso { font-size: 14px; }
.fac-footer__text {
  font-family: var(--font-body);
  font-size: 11px;
  line-height: 1.65;
  color: var(--on-surface-variant);
  margin: 0;
}

/* ── Material Symbols Outlined ───────────────────────────────────────── */
.mso {
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  font-family: 'Material Symbols Outlined';
  user-select: none;
}
.mso-fill { font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24; }

/* ── Print ────────────────────────────────────────────────────────────── */
@media print {
  .fac-header, .fac-footer, .fac-btn-run, .fac-btn-share, .fac-modal-overlay, .fac-bottom-bar { display: none !important; }
  .fac-main { padding: 0 !important; max-width: 100% !important; }
  .fac-report-card { box-shadow: none !important; }
  .fac-report-card__body { max-height: none !important; overflow: visible !important; }
  @page { margin: 16mm; size: A4; }
}
</style>