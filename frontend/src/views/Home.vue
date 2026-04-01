<template>
  <div class="market-home">
    <div class="hm-status">
      <span class="hm-status__dot" :class="marketStatus.dot" aria-hidden="true" />
      <span>{{ marketStatus.label }}</span>
      <span class="hm-status__sep">·</span>
      <span class="hm-status__date">{{ dateStrFull }}</span>
      <span class="hm-status__grow" />
      <span class="hm-status__flow-label">北向净流入</span>
      <span class="hm-status__flow tabular" :class="northNet >= 0 ? 'is-up' : 'is-down'">{{ formatSignedCompact(northNet) }}</span>
    </div>

    <main class="hm-main">
      <!-- 三大指数网格 + 迷你走势 -->
      <section class="hm-card hm-idx-wrap">
        <div v-if="loadingIndex" class="hm-idx-skel">
          <div v-for="i in 3" :key="i" class="hm-idx-skel__cell" />
        </div>
        <div v-else class="hm-idx-grid">
          <button
            v-for="item in indexCarousel"
            :key="item.name"
            type="button"
            class="hm-idx-cell"
            :class="Number(item.change) >= 0 ? 'is-up' : 'is-down'"
            @click="toggleIndexDetail(item.name)"
          >
            <div class="hm-idx-cell__hd">
              <span class="hm-idx-cell__name">{{ item.short }}</span>
              <span class="hm-idx-cell__code tabular">{{ indexTicker(item.name) }}</span>
            </div>
            <div class="hm-idx-cell__nums">
              <span class="hm-idx-cell__px tabular">{{ formatPrice(item.price) }}</span>
              <span class="hm-idx-cell__pct tabular">{{ formatPct(item.change) }}%</span>
            </div>
            <svg class="hm-idx-spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true">
              <path
                fill="none"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                :stroke="Number(item.change) >= 0 ? 'var(--hm-up)' : 'var(--hm-down)'"
                :d="indexSparkPath(item)"
              />
            </svg>
          </button>
        </div>
      </section>

      <transition name="fade">
        <div v-if="detailIndexName && !loadingIndex" class="hm-card hm-idx-expand">
          <div v-for="row in indexDetailRows" :key="row.k" class="hm-idx-expand__row">
            <span>{{ row.k }}</span><span class="tabular">{{ row.v }}</span>
          </div>
        </div>
      </transition>

      <!-- 市场情绪 -->
      <section class="hm-card hm-sentiment">
        <div class="hm-sentiment__hd">
          <h2 class="hm-sentiment__title">市场情绪 <span class="hm-sentiment__en">(MARKET SENTIMENT)</span></h2>
          <div v-if="loadingOverview" class="hm-sentiment__tag-skel" aria-busy="true">
            <div class="sk-dot" />
            <div class="sk-short" />
          </div>
          <div v-else class="hm-sentiment__tag">
            <span class="hm-sentiment__dot" :class="sentimentMood.moodClass" aria-hidden="true" />
            <span class="hm-sentiment__mood">{{ sentimentMood.label }}</span>
          </div>
        </div>
        <div v-if="loadingOverview" class="hm-sentiment__bar-skel" aria-busy="true">
          <div class="sk-barlabels">
            <div class="sk-barlabel" />
            <div class="sk-barlabel" />
            <div class="sk-barlabel" />
          </div>
          <div class="sk-bar" />
        </div>
        <template v-else>
          <div class="hm-sentiment__bar-wrap">
            <div class="hm-sentiment__bar-labels">
              <span class="is-up tabular">上涨 {{ breadth.up }}</span>
              <span class="is-flat tabular">平盘 {{ breadth.flat }}</span>
              <span class="is-down tabular">下跌 {{ breadth.down }}</span>
            </div>
            <div class="hm-sentiment__bar" role="img" :aria-label="`上涨${breadthPct.up}%`">
              <div class="hm-sentiment__seg is-up" :style="{ width: breadthPct.up + '%' }" />
              <div class="hm-sentiment__seg is-flat" :style="{ width: breadthPct.flat + '%' }" />
              <div class="hm-sentiment__seg is-down" :style="{ width: breadthPct.down + '%' }" />
            </div>
          </div>
        </template>
        <div class="hm-sentiment__grid">
          <div class="hm-subcard hm-subcard--limit" @click="$router.push('/sectors')">
            <p class="hm-subcard__k">涨跌停对比</p>
            <div v-if="loadingLimit" class="skeleton-num" aria-busy="true" />
            <div v-else class="hm-subcard__limit-row">
              <span class="hm-subcard__num tabular">{{ limit.limit_up_count || 0 }} <small>家</small></span>
              <span class="hm-subcard__num is-down tabular">{{ limit.limit_down_count || 0 }} <small>家</small></span>
            </div>
          </div>
          <div class="hm-subcard hm-subcard--cap">
            <p class="hm-subcard__k">大小盘对比</p>
            <div v-if="loadingOverview" class="skeleton-num" aria-busy="true" />
            <template v-else>
              <div class="hm-subcard__line">
                <span>{{ capPair.largeLabel }}</span>
                <span class="tabular" :class="capPair.large >= 0 ? 'is-up' : 'is-down'">{{ formatPct(capPair.large) }}%</span>
              </div>
              <div class="hm-subcard__line">
                <span>{{ capPair.smallLabel }}</span>
                <span class="tabular" :class="capPair.small >= 0 ? 'is-up' : 'is-down'">{{ formatPct(capPair.small) }}%</span>
              </div>
            </template>
          </div>
        </div>
        <div v-if="!loadingTurnover" class="hm-turnover">
          今日成交额总计 <strong class="tabular">{{ formatTotalYi(snapshot.total_amount) }}</strong>
          <span v-if="snapshot.delta_hint" class="hm-turnover__hint">{{ snapshot.delta_hint }}</span>
        </div>
        <div v-else class="hm-turnover hm-turnover--skel"><div class="skeleton-line" /></div>
      </section>

      <!-- 股票排行：与板块页一致的胶囊 Tab，涨跌幅仅文字着色 -->
      <section class="hm-card hm-rank">
        <div class="hm-rank__hd">
          <span class="hm-rank__title">股票排行</span>
          <button type="button" class="hm-rank__toggle" @click="rankCollapsed = !rankCollapsed">
            {{ rankCollapsed ? '展开' : '收起' }}
          </button>
        </div>
        <div v-show="!rankCollapsed">
          <div class="hm-rank-tabs" role="tablist">
            <button
              v-for="t in rankTabDefs"
              :key="t.id"
              type="button"
              class="hm-rank-tab"
              :class="{ active: rankTab === t.id }"
              role="tab"
              @click="rankTab = t.id"
            >
              {{ t.label }}
            </button>
          </div>
          <div class="hm-rank-thead">
            <span class="col-name">名称 / 代码</span>
            <span class="col-price">最新价</span>
            <span class="col-pct">{{ rankPctLabel }}</span>
            <span class="col-ind">所属板块</span>
          </div>
          <div v-if="loadingRank" class="hm-rank-skel" aria-busy="true">
            <div v-for="i in 6" :key="i" class="hm-rank-skel__row">
              <div class="hm-rank-skel__name">
                <div class="sk-bar-sk" style="width:60%;height:13px;border-radius:4px" />
                <div class="sk-bar-sk" style="width:40%;height:10px;border-radius:4px;margin-top:3px" />
              </div>
              <div class="sk-bar-sk hm-rank-skel__px" style="width:52px;height:13px;border-radius:4px" />
              <div class="sk-bar-sk hm-rank-skel__pct" style="width:48px;height:13px;border-radius:4px" />
              <div class="sk-bar-sk" style="width:64px;height:10px;border-radius:4px" />
            </div>
          </div>
          <div v-else-if="!currentRankList.length" class="hm-rank-empty">暂无排行数据</div>
          <template v-else>
            <div
              v-for="(s, i) in currentRankList"
              :key="s.code + '-' + i"
              class="hm-rank-row"
              @click="goStock(s.code)"
            >
              <div class="col-name">
                <span class="hm-stock-name">{{ s.name }}</span>
                <span class="hm-stock-code tabular">{{ s.code }}</span>
              </div>
              <span class="col-price tabular" :class="s.change >= 0 ? 'is-up' : 'is-down'">{{ formatPrice(s.price) }}</span>
              <span class="col-pct tabular hm-pct-text" :class="s.change >= 0 ? 'is-up' : 'is-down'">{{ formatPct(s.change) }}%</span>
              <span class="col-ind">{{ s.industry || '—' }}</span>
            </div>
          </template>
        </div>
      </section>

      <!-- 每日宏观视角：真实数据 -->
      <section class="hm-card hm-macro">
        <div class="hm-macro__hd">
          <svg class="hm-macro__ico" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/>
          </svg>
          <h3 class="hm-macro__title">每日宏观视角 <span class="hm-macro__en">(DAILY MACRO)</span></h3>
        </div>
        <p class="hm-macro__body">
          <span v-if="loadingMacro" class="sk-body-text" aria-busy="true">
            <span class="skeleton-line" style="width:100%;height:12px;border-radius:4px;display:block;margin-bottom:5px" />
            <span class="skeleton-line" style="width:85%;height:12px;border-radius:4px;display:block;margin-bottom:5px" />
            <span class="skeleton-line" style="width:70%;height:12px;border-radius:4px;display:block" />
          </span>
          <span v-else>{{ macroSummaryText }}</span>
        </p>
        <div v-if="loadingMacro" class="hm-macro__foot-skel" aria-busy="true">
          <div class="hm-macro__stat-skel" />
          <div class="hm-macro__divider-skel" />
          <div class="hm-macro__stat-skel" />
        </div>
        <div v-else class="hm-macro__foot">
          <div class="hm-macro__stat-col">
            <span class="hm-macro__stat-l">SENTIMENT SCORE</span>
            <span class="hm-macro__stat-v" :class="macroScoreColor">{{ macroScore }} / 100</span>
          </div>
          <div class="hm-macro__divider" aria-hidden="true" />
          <div class="hm-macro__stat-col">
            <span class="hm-macro__stat-l">RISK LEVEL</span>
            <span class="hm-macro__stat-v" :class="macroScoreColor">{{ macroRiskLevel }}</span>
          </div>
        </div>
      </section>

      <!-- 热门板块 -->
      <section class="hm-card hm-hot">
        <div class="hm-hot__hd">
          <span>热门板块</span>
          <button type="button" class="hm-link" @click="$router.push('/sectors')">更多 ›</button>
        </div>
        <div v-if="loadingSectors" class="hm-hot-treemap-sk" aria-busy="true">
          <div class="hm-hot-treemap-sk__row hm-hot-treemap-sk__row--4">
            <div v-for="i in 4" :key="'a' + i" class="hm-hot-treemap-sk__blk" />
          </div>
          <div class="hm-hot-treemap-sk__row hm-hot-treemap-sk__row--2">
            <div v-for="i in 2" :key="'b' + i" class="hm-hot-treemap-sk__blk" />
          </div>
        </div>
        <div v-else-if="!sectors.length" class="hm-hot-empty">暂无板块数据</div>
        <div v-else class="hm-hot-treemap-wrap">
          <svg
            class="hm-hot-treemap"
            :viewBox="`0 0 ${hotSectorTreemap.vw} ${hotSectorTreemap.vh}`"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            :aria-label="hotSectorTreemapAria"
          >
            <g v-for="(r, idx) in hotSectorTreemap.rects" :key="r.data.name + idx">
              <rect
                class="hm-hot-treemap__cell"
                :x="r.x + 0.5"
                :y="r.y + 0.5"
                :width="Math.max(0, r.w - 1)"
                :height="Math.max(0, r.h - 1)"
                :fill="r.fill"
                rx="4"
                stroke="rgba(255,255,255,0.65)"
                stroke-width="1"
                @click="$router.push('/sectors')"
              />
              <text
                v-if="r.showName"
                class="hm-hot-treemap__lbl hm-hot-treemap__lbl--name"
                :x="r.x + r.w / 2"
                :y="r.y + r.h / 2 - (r.showPct ? 5 : 0)"
                text-anchor="middle"
                dominant-baseline="middle"
                :fill="r.tc"
                :font-size="r.fontName"
              >{{ ellipsisSectorName(r.name, r.w) }}</text>
              <text
                v-if="r.showPct"
                class="hm-hot-treemap__lbl hm-hot-treemap__lbl--pct"
                :x="r.x + r.w / 2"
                :y="r.y + r.h / 2 + (r.showName ? 9 : 0)"
                text-anchor="middle"
                dominant-baseline="middle"
                :fill="r.tc"
                :font-size="r.fontPct"
              >{{ r.pctStr }}</text>
            </g>
          </svg>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { market, macroSummary } from '@/api/market.js'
import { layoutBinaryTreemap, fillForSectorChange, textColorForChange } from '@/utils/sectorTreemap.js'

const router = useRouter()

// 各区块独立 loading 状态
const loadingIndex   = ref(true)
const loadingTurnover = ref(true)
const loadingLimit   = ref(true)
const loadingOverview = ref(true)
const loadingRank     = ref(true)
const loadingSectors  = ref(true)
const loadingMacro    = ref(true)

// 宏观摘要数据
const macroRaw = ref(null)

// 全部骨架展示后隐藏全页 loading
const allSkeletonsShown = computed(() =>
  loadingIndex.value || loadingTurnover.value || loadingLimit.value ||
  loadingOverview.value || loadingRank.value || loadingSectors.value
)

const overview = ref([])
const flow = ref({ north_money: {} })
const limit = ref({})
const sectors = ref([])
const snapshot = ref({
  up_count: 0,
  down_count: 0,
  flat_count: 0,
  total_amount: 0,
  top_gainers: [],
  top_losers: [],
  top_by_amount: [],
  fast_gainers: [],
})

const rankTab = ref('gain')
const rankCollapsed = ref(false)
const detailIndexName = ref('')

const rankTabDefs = [
  { id: 'gain', label: '涨幅榜', key: 'top_gainers' },
  { id: 'loss', label: '跌幅榜', key: 'top_losers' },
  { id: 'fast', label: '快速涨幅', key: 'fast_gainers' },
  { id: 'amount', label: '成交额', key: 'top_by_amount' },
]

// 交易时段：优先 /api/market/session（服务端北京时间）；失败时用浏览器按上海时区推算
const sessionFromApi = ref(null)
/** 驱动日期与本地兜底状态刷新（SPA 长时间停留时仍更新） */
const clockTick = ref(0)

const MARKET_OPEN_MORNING = 9 * 60 + 30
const MARKET_CLOSE_MORNING = 11 * 60 + 30
const MARKET_OPEN_AFTERNOON = 13 * 60
const MARKET_CLOSE_AFTERNOON = 15 * 60

function shanghaiMinuteOfDay() {
  const d = new Date()
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const h = Number(parts.find(p => p.type === 'hour').value)
  const m = Number(parts.find(p => p.type === 'minute').value)
  return h * 60 + m
}

function isShanghaiWeekend() {
  const wd = new Intl.DateTimeFormat('en-US', { timeZone: 'Asia/Shanghai', weekday: 'short' }).format(new Date())
  return wd === 'Sat' || wd === 'Sun'
}

function localFallbackMarketStatus() {
  void clockTick.value
  if (isShanghaiWeekend()) return { label: '非交易日', dot: 'is-off' }
  const t = shanghaiMinuteOfDay()
  if (t >= MARKET_OPEN_MORNING && t < MARKET_CLOSE_MORNING) return { label: '交易中', dot: 'is-up' }
  if (t >= MARKET_OPEN_AFTERNOON && t < MARKET_CLOSE_AFTERNOON) return { label: '交易中', dot: 'is-up' }
  if (t >= MARKET_CLOSE_MORNING && t < MARKET_OPEN_AFTERNOON) return { label: '午间休市', dot: 'is-off' }
  return { label: '已收盘', dot: 'is-off' }
}

const marketStatus = computed(() => {
  const s = sessionFromApi.value
  if (s && s.label && s.dot) return { label: s.label, dot: s.dot }
  return localFallbackMarketStatus()
})

const dateStrFull = computed(() => {
  void clockTick.value
  const d = new Date()
  const w = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${mo}-${day} 星期${w}`
})

const northNet = computed(() => flow.value?.north_money?.north_net_inflow ?? 0)

const indexCarousel = computed(() => {
  const pick = (n, short) => {
    const x = overview.value.find(i => i.name === n) || {}
    return { name: n, short, ...x }
  }
  return [
    pick('上证指数', '上证指数'),
    pick('深证成指', '深证成指'),
    pick('创业板指', '创业板指'),
  ]
})

const indexDetailRows = computed(() => {
  const x = overview.value.find(i => i.name === detailIndexName.value) || {}
  return [
    { k: '今开', v: formatPrice(x.open) },
    { k: '最高', v: formatPrice(x.high) },
    { k: '昨收', v: formatPrice(x.prev_close) },
    { k: '最低', v: formatPrice(x.low) },
  ]
})

function toggleIndexDetail(name) {
  detailIndexName.value = detailIndexName.value === name ? '' : name
}

const breadth = computed(() => {
  const snap = snapshot.value
  const sh = overview.value.find(i => i.name === '上证指数') || {}
  const up = Number(snap.up_count || sh.up_count || 0)
  const down = Number(snap.down_count || sh.down_count || 0)
  const flat = Number(snap.flat_count || sh.flat_count || 0)
  const total = Math.max(1, up + down + flat)
  return {
    up,
    down,
    flat,
    pctUp: Math.round((up / total) * 100),
    pctDown: Math.round((down / total) * 100),
  }
})

const breadthPct = computed(() => {
  const { up, down, flat } = breadth.value
  const n = Math.max(1, up + down + flat)
  const u = Math.floor((100 * up) / n)
  const f = Math.floor((100 * flat) / n)
  const d = 100 - u - f
  return { up: u, flat: f, down: d }
})

const sentimentMood = computed(() => {
  const { up, down } = breadth.value
  if (up > down * 1.08) return { label: 'BULLISH', moodClass: 'is-up' }
  if (down > up * 1.08) return { label: 'BEARISH', moodClass: 'is-down' }
  return { label: 'NEUTRAL', moodClass: 'is-flat' }
})

const INDEX_TICKERS = {
  上证指数: '000001.SH',
  深证成指: '399001.SZ',
  创业板指: '399006.SZ',
}

function indexTicker(name) {
  return INDEX_TICKERS[name] || ''
}

function indexSparkPath(item) {
  const isUp = Number(item.change) >= 0
  const w = 100
  const h = 30
  const pad = 2
  let seed = 2166136261
  const s = String(item.name || '')
  for (let i = 0; i < s.length; i++) {
    seed ^= s.charCodeAt(i)
    seed = Math.imul(seed, 16777619)
  }
  const parts = []
  for (let i = 0; i <= 12; i++) {
    const t = i / 12
    const x = (t * w).toFixed(1)
    const wave = Math.sin(seed * 1e-6 + t * 5) * 6
    const drift = isUp ? (1 - t) * 12 : t * 12
    let y = h / 2 + wave + drift * 0.35
    y = Math.max(pad, Math.min(h - pad, y))
    parts.push(i === 0 ? `M${x} ${y.toFixed(1)}` : `L${x} ${y.toFixed(1)}`)
  }
  return parts.join(' ')
}

const capPair = computed(() => {
  const hs300 = overview.value.find(i => i.name === '沪深300') || {}
  const sz50 = overview.value.find(i => i.name === '上证50') || {}
  const zz1000 = overview.value.find(i => i.name === '中证1000') || {}
  const zz500 = overview.value.find(i => i.name === '中证500') || {}
  const largeSource = hs300.change != null && hs300.change !== '' ? hs300 : sz50
  const large = largeSource.change ?? 0
  const largeLabel = hs300.change != null && hs300.change !== '' ? '大盘 (沪深300)' : '大盘 (上证50)'
  const small = (zz1000.change != null ? zz1000.change : zz500.change) ?? 0
  const smallLabel = '小盘 (中证1000)'
  let hint = '风格均衡'
  if (small > large + 0.05) hint = '小盘股更强'
  else if (large > small + 0.05) hint = '大盘股更强'
  return { large, small, hint, largeLabel, smallLabel }
})

const macroScore = computed(() => macroRaw.value?.sentiment_score ?? 50)
const macroRiskLevel = computed(() => macroRaw.value?.risk_level ?? 'MEDIUM')
const macroSummaryText = computed(() => {
  const t = macroRaw.value?.summary_text
  if (t != null && String(t).trim()) return String(t).trim()
  return '摘要暂不可用，请稍后重试'
})
const macroScoreColor = computed(() => {
  const s = macroScore.value
  if (s >= 62) return 'is-up'     // 红涨 → 多头
  if (s >= 48) return 'is-flat'
  return 'is-down'                  // 绿跌 → 空头
})

const hotSectorTreemap = computed(() => {
  const list = sectors.value.slice(0, 6)
  const vw = 320
  const vh = 150
  if (!list.length) return { rects: [], vw, vh, maxAbs: 1 }
  const weights = list.map((s) => {
    const a = Number(s.amount)
    if (Number.isFinite(a) && a > 0) return a
    return Math.abs(Number(s.change)) + 0.35
  })
  const items = list.map((s, i) => ({ weight: weights[i], data: s }))
  const rects = layoutBinaryTreemap(items, 0, 0, vw, vh)
  const changes = list.map((s) => Number(s.change) || 0)
  const maxAbs = Math.max(...changes.map((c) => Math.abs(c)), 0.01)
  const enriched = rects.map((r) => {
    const ch = Number(r.data.change) || 0
    const area = r.w * r.h
    const tiny = area < 2000 || r.w < 36 || r.h < 24
    const compact = area < 4200 || r.w < 52 || r.h < 34
    const showPct = r.w >= 30 && r.h >= 20
    const showName = showPct && !tiny && r.w >= 44
    return {
      ...r,
      fill: fillForSectorChange(ch, maxAbs),
      tc: textColorForChange(ch),
      name: r.data.name,
      pctStr: `${formatPct(ch)}%`,
      showName,
      showPct,
      fontName: compact ? 10 : 11,
      fontPct: compact ? 10.5 : 12.5,
    }
  })
  return { rects: enriched, vw, vh, maxAbs }
})

const hotSectorTreemapAria = computed(() => {
  const parts = hotSectorTreemap.value.rects.map((r) => `${r.data.name} ${r.pctStr}`)
  return `热门板块热力图 ${parts.join('，')}`
})

function ellipsisSectorName(name, w) {
  if (!name) return ''
  const maxChars = w < 48 ? 5 : w < 70 ? 7 : w < 100 ? 10 : 12
  return name.length > maxChars ? `${name.slice(0, maxChars - 1)}…` : name
}

const rankPctLabel = computed(() =>
  rankTab.value === 'amount' ? '涨跌' : '涨幅'
)

const currentRankList = computed(() => {
  const def = rankTabDefs.find(t => t.id === rankTab.value)
  const key = def?.key || 'top_gainers'
  let list = snapshot.value[key] || []
  if (key === 'fast_gainers' && (!list || !list.length)) {
    list = snapshot.value.top_gainers || []
  }
  if (key === 'top_by_amount') {
    return (list || []).map(s => ({ ...s, change: s.change }))
  }
  return list || []
})

function formatPrice(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}
function formatChange(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}
function formatPct(v) {
  if (v == null || v === '' || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}
function formatSignedCompact(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  const abs = Math.abs(n)
  let s = abs >= 1e8 ? (abs / 1e8).toFixed(2) + '亿'
    : abs >= 1e4 ? (abs / 1e4).toFixed(0) + '万'
    : abs.toFixed(0)
  return (n >= 0 ? '+' : '-') + s
}
function formatTotalYi(amount) {
  if (!amount) return '--'
  const yi = Number(amount) / 1e8
  if (yi >= 10000) return (yi / 10000).toFixed(2) + '万亿'
  return yi.toFixed(0) + '亿'
}
function goStock(code) {
  const c = String(code || '').trim()
  if (/^\d{6}$/.test(c)) router.push({ name: 'StockDetail', params: { code: c } })
}

// 各区块独立加载，互不阻塞
async function loadOverview() {
  try {
    const ov = await market.overview()
    overview.value = Array.isArray(ov) ? ov : []
  } catch (e) {
    console.error('overview error', e)
  } finally {
    loadingOverview.value = false
  }
}

async function loadFlow() {
  try {
    const fl = await market.flow()
    flow.value = fl || {}
  } catch (e) {
    console.error('flow error', e)
  }
}

async function loadLimit() {
  try {
    const lm = await market.limit()
    limit.value = lm || {}
  } catch (e) {
    console.error('limit error', e)
  } finally {
    loadingLimit.value = false
  }
}

async function loadSnapshot() {
  try {
    const sn = await market.snapshot()
    if (sn && typeof sn === 'object') {
      snapshot.value = { ...snapshot.value, ...sn }
    }
  } catch (e) {
    console.error('snapshot error', e)
  } finally {
    loadingRank.value = false
  }
}

async function loadSectors() {
  try {
    const sc = await market.sectors()
    sectors.value = Array.isArray(sc) ? sc : []
  } catch (e) {
    console.error('sectors error', e)
  } finally {
    loadingSectors.value = false
  }
}

async function loadTurnover() {
  try {
    const sn = await market.snapshot()
    if (sn && typeof sn === 'object') {
      snapshot.value = { ...snapshot.value, ...sn }
    }
  } catch (e) {
    console.error('turnover error', e)
  } finally {
    loadingTurnover.value = false
  }
}

async function loadMacro() {
  try {
    const data = await macroSummary()
    if (data && typeof data === 'object') {
      macroRaw.value = data
    }
  } catch (e) {
    console.error('macro error', e)
  } finally {
    loadingMacro.value = false
  }
}

// 指数数据在 overview 加载完成后显示
function setupIndexReady() {
  loadingIndex.value = false
}

async function loadSession() {
  try {
    const data = await market.session()
    if (data && typeof data === 'object' && data.label && data.dot) {
      sessionFromApi.value = data
    }
  } catch (e) {
    console.error('session error', e)
    sessionFromApi.value = null
  }
}

let timer = null
let sessionPollTimer = null
onMounted(() => {
  loadFlow()
  loadOverview()
  loadLimit()
  loadSnapshot()
  loadSectors()
  loadTurnover()
  loadMacro()
  loadSession()

  // 指数在 overview 返回后即 ready
  const unwatch = setInterval(() => {
    if (overview.value.length) {
      setupIndexReady()
      clearInterval(unwatch)
    }
  }, 100)

  sessionPollTimer = setInterval(() => {
    clockTick.value += 1
    loadSession()
  }, 30_000)

  timer = setInterval(() => {
    // 不清缓存，让前端 TTL 缓存自动管理，静静静后台刷新
    loadOverview()
    loadFlow()
    loadLimit()
    loadSnapshot()
    loadSectors()
    loadTurnover()
    loadMacro()
    loadSession()
  }, 120_000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (sessionPollTimer) clearInterval(sessionPollTimer)
})
</script>

<style scoped>
/* Architectural Ledger — DESIGN.md + stitch Market Overview（红涨绿跌 · TV #f23645 / #089981） */
.market-home {
  --hm-primary: #003ec7;
  --hm-primary-mid: #0052ff;
  --hm-up: #f23645;
  --hm-down: #089981;
  --hm-surface: #f8f9fa;
  --hm-low: #f3f4f5;
  --hm-high: #e7e8e9;
  --hm-white: #ffffff;
  --hm-text: #191c1d;
  --hm-muted: #434656;
  --hm-outline: #737688;
  --hm-ghost: rgba(195, 197, 217, 0.15);
  --hm-ambient: 0 4px 24px rgba(25, 28, 29, 0.06);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--hm-surface);
  color: var(--hm-text);
  padding-top: env(safe-area-inset-top, 0);
  padding-bottom: calc(env(safe-area-inset-bottom) + 72px);
  font-family: 'Inter', var(--font);
}

.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}

.hm-status {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px 8px;
  padding: 8px 16px 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--hm-muted);
}
.hm-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--hm-up);
  flex-shrink: 0;
}
.hm-status__dot.is-up { background: var(--hm-up); }
.hm-status__dot.is-off { background: var(--hm-outline); }
.hm-status__sep {
  opacity: 0.5;
}
.hm-status__date {
  font-weight: 500;
}
.hm-status__grow {
  flex: 1;
  min-width: 8px;
}
.hm-status__flow-label {
  color: var(--hm-outline);
  font-weight: 600;
}
.hm-status__flow.is-up {
  color: var(--hm-up);
  font-weight: 800;
}
.hm-status__flow.is-down {
  color: var(--hm-down);
  font-weight: 800;
}

.hm-main {
  padding: 0 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hm-card {
  background: var(--hm-white);
  border-radius: 8px;
  box-shadow: inset 0 0 0 1px var(--hm-ghost), var(--hm-ambient);
  overflow: hidden;
}

/* 三大指数 */
.hm-idx-wrap {
  padding: 0;
}
.hm-idx-skel {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--hm-ghost);
  padding: 0;
}
.hm-idx-skel__cell {
  min-height: 100px;
  background: var(--hm-white);
  animation: sk-shine 1.1s ease-in-out infinite;
}
.hm-idx-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--hm-ghost);
}
.hm-idx-cell {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
  padding: 10px 8px 8px;
  background: var(--hm-white);
  border: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
  min-width: 0;
}
.hm-idx-cell:active {
  background: var(--hm-low);
}
.hm-idx-cell__hd {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 4px;
}
.hm-idx-cell__name {
  font-family: 'Manrope', var(--font);
  font-size: 11px;
  font-weight: 800;
  color: var(--hm-muted);
  line-height: 1.2;
}
.hm-idx-cell__code {
  font-size: 9px;
  color: var(--hm-outline);
  opacity: 0.75;
  white-space: nowrap;
}
.hm-idx-cell__nums {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
}
.hm-idx-cell__px {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hm-idx-cell__pct {
  font-size: 11px;
  font-weight: 700;
}
.hm-idx-cell.is-up .hm-idx-cell__px,
.hm-idx-cell.is-up .hm-idx-cell__pct {
  color: var(--hm-up);
}
.hm-idx-cell.is-down .hm-idx-cell__px,
.hm-idx-cell.is-down .hm-idx-cell__pct {
  color: var(--hm-down);
}
.hm-idx-spark {
  width: 100%;
  height: 28px;
  margin-top: 2px;
}

.hm-idx-expand {
  padding: 12px 14px;
}
.hm-idx-expand__row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--hm-muted);
  padding: 5px 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 市场情绪 */
.hm-sentiment {
  padding: 14px 14px 12px;
}
.hm-sentiment__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.hm-sentiment__title {
  margin: 0;
  font-family: 'Manrope', var(--font);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hm-sentiment__en {
  font-size: 10px;
  font-weight: 800;
  color: var(--hm-outline);
  letter-spacing: 0.04em;
}
.hm-sentiment__tag {
  display: flex;
  align-items: center;
  gap: 5px;
}
.hm-sentiment__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.hm-sentiment__dot.is-up {
  background: var(--hm-up);
}
.hm-sentiment__dot.is-down {
  background: var(--hm-down);
}
.hm-sentiment__dot.is-flat {
  background: var(--hm-outline);
}
.hm-sentiment__mood {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: var(--hm-muted);
}

/* Skeleton: sentiment mood tag */
.hm-sentiment__tag-skel {
  display: flex;
  align-items: center;
  gap: 5px;
}
.sk-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
  flex-shrink: 0;
}
.sk-short {
  height: 10px;
  width: 52px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}

/* Skeleton: sentiment bar */
.hm-sentiment__bar-skel {
  margin-bottom: 14px;
}
.sk-barlabels {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.sk-barlabel {
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.sk-barlabel:nth-child(1) { width: 28px; }
.sk-barlabel:nth-child(2) { width: 28px; }
.sk-barlabel:nth-child(3) { width: 28px; }
.sk-bar {
  height: 6px;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.hm-sentiment__bar-wrap {
  margin-bottom: 14px;
}
.hm-sentiment__bar-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-weight: 800;
  margin-bottom: 6px;
  letter-spacing: 0.02em;
}
.hm-sentiment__bar-labels .is-up {
  color: var(--hm-up);
}
.hm-sentiment__bar-labels .is-flat {
  color: var(--hm-outline);
}
.hm-sentiment__bar-labels .is-down {
  color: var(--hm-down);
}
.hm-sentiment__bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--hm-high);
}
.hm-sentiment__seg {
  height: 100%;
  min-width: 0;
  transition: width 0.25s ease;
}
.hm-sentiment__seg.is-up {
  background: var(--hm-up);
}
.hm-sentiment__seg.is-flat {
  background: #c3c5d9;
}
.hm-sentiment__seg.is-down {
  background: var(--hm-down);
}

.hm-sentiment__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.hm-subcard {
  background: var(--hm-low);
  border-radius: 6px;
  padding: 10px 10px 8px;
  box-shadow: inset 0 0 0 1px var(--hm-ghost);
}
.hm-subcard--limit {
  cursor: pointer;
}
.hm-subcard--limit:active {
  opacity: 0.92;
}
.hm-subcard__k {
  margin: 0 0 8px;
  font-size: 10px;
  font-weight: 800;
  color: var(--hm-outline);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.hm-subcard__limit-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
}
.hm-subcard__num {
  font-family: 'Manrope', var(--font);
  font-size: 20px;
  font-weight: 800;
  color: var(--hm-text);
}
.hm-subcard__num small {
  font-size: 10px;
  font-weight: 600;
  color: var(--hm-outline);
}
.hm-subcard__num.is-down {
  color: var(--hm-down);
}
.hm-subcard__line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  margin-bottom: 4px;
}
.hm-subcard__line:last-child {
  margin-bottom: 0;
}
.is-up {
  color: var(--hm-up);
  font-weight: 800;
}
.is-down {
  color: var(--hm-down);
  font-weight: 800;
}
.is-flat {
  color: var(--hm-outline);
}

.hm-turnover {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--hm-ghost);
  font-size: 12px;
  color: var(--hm-muted);
  line-height: 1.45;
}
.hm-turnover strong {
  color: var(--hm-text);
  font-weight: 800;
}
.hm-turnover__hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--hm-outline);
}
.hm-turnover--skel .skeleton-line {
  margin: 0;
}

/* 排行：与 Sectors 页 sec-hot-pill / sec-flow-pill 一致的胶囊 Tab；涨跌幅纯文字色 */
.hm-rank {
  padding: 0;
}
.hm-rank__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px 8px;
}
.hm-rank__title {
  font-family: 'Manrope', var(--font);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hm-rank__toggle {
  font-size: 12px;
  font-weight: 700;
  color: var(--hm-primary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.hm-rank-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  overflow-x: auto;
  padding: 0 14px 10px;
  scrollbar-width: none;
}
.hm-rank-tabs::-webkit-scrollbar {
  display: none;
}
.hm-rank-tab {
  flex: 0 0 auto;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  border: 1px solid var(--hm-ghost);
  background: var(--hm-white);
  color: var(--hm-muted);
  cursor: pointer;
  font-family: inherit;
}
.hm-rank-tab.active {
  background: rgba(0, 62, 199, 0.08);
  border-color: rgba(0, 62, 199, 0.32);
  color: var(--hm-primary);
}

.hm-rank-thead {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 0.72fr 0.62fr minmax(0, 1fr);
  gap: 6px;
  align-items: center;
  padding: 8px 12px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--hm-outline);
  opacity: 0.85;
  background: var(--hm-low);
}
.hm-rank-thead .col-price,
.hm-rank-thead .col-pct {
  text-align: right;
}
.hm-rank-thead .col-ind {
  text-align: right;
}

/* Skeleton: rank rows */
.hm-rank-skel {
  display: flex;
  flex-direction: column;
}
.hm-rank-skel__row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 0.72fr 0.62fr minmax(0, 1fr);
  gap: 6px;
  align-items: center;
  padding: 10px 12px;
  box-shadow: 0 1px 0 var(--hm-ghost);
  background: var(--hm-white);
}
.hm-rank-skel__name {
  display: flex;
  flex-direction: column;
}
.sk-bar-sk {
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}

.hm-rank-row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) 0.72fr 0.62fr minmax(0, 1fr);
  gap: 6px;
  align-items: center;
  padding: 10px 12px;
  cursor: pointer;
  box-shadow: 0 1px 0 var(--hm-ghost);
  background: var(--hm-white);
}
.hm-rank-row:active {
  background: var(--hm-low);
}
.hm-rank-row .col-name {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.hm-stock-name {
  font-family: 'Manrope', var(--font);
  font-size: 13px;
  font-weight: 800;
  line-height: 1.2;
  color: var(--hm-text);
}
.hm-stock-code {
  font-size: 10px;
  color: var(--hm-outline);
}
.hm-rank-row .col-price,
.hm-rank-row .col-pct {
  text-align: right;
  font-size: 13px;
  font-weight: 800;
}
.hm-rank-row .col-ind {
  text-align: right;
  font-size: 10px;
  color: var(--hm-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hm-pct-text {
  background: none !important;
  padding: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}

.hm-rank-empty,
.hm-rank-loading {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: var(--hm-outline);
}

/* 宏观 */
.hm-macro {
  padding: 16px 14px 14px;
  position: relative;
  overflow: hidden;
}
.hm-macro::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -40px;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: var(--hm-primary);
  opacity: 0.05;
  pointer-events: none;
}
.hm-macro__hd {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  position: relative;
  z-index: 1;
}
.hm-macro__ico {
  width: 18px;
  height: 18px;
  color: var(--hm-primary);
  flex-shrink: 0;
}
.hm-macro__title {
  margin: 0;
  font-family: 'Manrope', var(--font);
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--hm-primary);
}
.hm-macro__en {
  font-weight: 800;
  opacity: 0.85;
}
.hm-macro__body {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--hm-text);
  font-weight: 500;
  position: relative;
  z-index: 1;
}
.hm-macro__foot {
  display: flex;
  align-items: center;
  gap: 14px;
  position: relative;
  z-index: 1;
}
.hm-macro__stat-col {
  flex: 1;
  min-width: 0;
}
.hm-macro__stat-l {
  display: block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--hm-outline);
  opacity: 0.65;
  margin-bottom: 2px;
}
.hm-macro__stat-v {
  font-family: 'Manrope', var(--font);
  font-size: 14px;
  font-weight: 800;
  color: var(--hm-text);
}
.hm-macro__stat-v.is-up {
  color: var(--hm-up);
}
.hm-macro__divider {
  width: 1px;
  height: 28px;
  background: var(--hm-ghost);
  flex-shrink: 0;
}

/* Skeleton: macro foot */
.hm-macro__foot-skel {
  display: flex;
  align-items: center;
  gap: 14px;
  position: relative;
  z-index: 1;
}
.hm-macro__stat-skel {
  flex: 1;
  min-width: 0;
}
.hm-macro__stat-skel::before {
  content: '';
  display: block;
  height: 9px;
  width: 60%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
  margin-bottom: 4px;
}
.hm-macro__stat-skel::after {
  content: '';
  display: block;
  height: 14px;
  width: 80%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.hm-macro__divider-skel {
  width: 1px;
  height: 28px;
  background: var(--hm-ghost);
  flex-shrink: 0;
}
.sk-body-text {
  display: block;
}

/* 热门板块 */
.hm-hot {
  padding: 12px 14px 14px;
}
.hm-hot__hd {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: 'Manrope', var(--font);
  font-size: 15px;
  font-weight: 800;
  margin-bottom: 10px;
  letter-spacing: -0.02em;
}
.hm-link {
  font-size: 12px;
  font-weight: 700;
  color: var(--hm-primary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}
.hm-hot-treemap-wrap {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px var(--hm-ghost);
  background: rgba(255, 255, 255, 0.35);
}
.hm-hot-treemap {
  width: 100%;
  height: auto;
  display: block;
  vertical-align: top;
  min-height: 132px;
}
.hm-hot-treemap__cell {
  cursor: pointer;
  transition: filter 0.12s ease;
}
.hm-hot-treemap__cell:hover {
  filter: brightness(1.05);
}
.hm-hot-treemap__cell:active {
  filter: brightness(0.96);
}
.hm-hot-treemap__lbl {
  pointer-events: none;
  font-family: 'Manrope', var(--font);
  font-weight: 800;
  letter-spacing: -0.02em;
  user-select: none;
}
.hm-hot-treemap__lbl--name {
  font-weight: 700;
  opacity: 0.96;
}
.hm-hot-treemap__lbl--pct {
  font-weight: 800;
}
.hm-hot-empty {
  font-size: 12px;
  color: var(--hm-outline);
  padding: 20px 8px;
  text-align: center;
}
.hm-hot-treemap-sk {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 132px;
}
.hm-hot-treemap-sk__row {
  display: flex;
  gap: 6px;
  flex: 1;
  min-height: 0;
}
.hm-hot-treemap-sk__row--4 .hm-hot-treemap-sk__blk {
  flex: 1;
}
.hm-hot-treemap-sk__row--2 .hm-hot-treemap-sk__blk {
  flex: 1;
}
.hm-hot-treemap-sk__blk {
  border-radius: 8px;
  min-height: 56px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}

.page-loading {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 200;
}
.page-loading__skeleton {
  width: 100%;
  max-width: 360px;
  padding: 0 24px;
}
.sk {
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
  border-radius: 12px;
}
.sk-title {
  height: 32px;
  width: 40%;
  margin-bottom: 16px;
  border-radius: 8px;
}
.sk-row {
  height: 72px;
  margin-bottom: 12px;
}
.sk-grid {
  display: flex;
  gap: 10px;
}
.sk-card {
  flex: 1;
  height: 88px;
  border-radius: 14px;
}
/* 各区块骨架屏 */
.skeleton-row {
  display: flex;
  gap: 10px;
  padding: 12px 14px 14px;
}
.sk-card {
  flex: 0 0 42%;
  min-width: 140px;
  height: 80px;
  border-radius: 14px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.skeleton-line {
  height: 20px;
  width: 60%;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.skeleton-num {
  height: 20px;
  width: 80px;
  border-radius: 8px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
  margin-bottom: 4px;
}
.skeleton-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.sk-chip {
  height: 56px;
  width: 80px;
  border-radius: 12px;
  background: linear-gradient(90deg, var(--surface-2) 0%, var(--divider) 50%, var(--surface-2) 100%);
  background-size: 200% 100%;
  animation: sk-shine 1.1s ease-in-out infinite;
}
.rank-loading-hint {
  text-align: center;
  padding: 16px;
  color: var(--text-3);
  font-size: var(--text-sm);
}

@keyframes sk-shine {
  0% { background-position: 100% 0; }
  100% { background-position: -100% 0; }
}
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--divider);
  border-top-color: var(--text-1);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
