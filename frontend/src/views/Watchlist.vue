<template>
  <div class="wl">
    <header class="wl-topbar">
      <button type="button" class="wl-topbar__icon" aria-label="搜索添加" @click="openAddModal">
        <svg class="wl-svg" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
      </button>
      <h1 class="wl-brand">{{ listTitle }}</h1>
      <button type="button" class="wl-topbar__icon" aria-label="自选设置" @click="goWatchlistSettings">
        <svg class="wl-svg" viewBox="0 0 24 24" aria-hidden="true">
          <path
            fill="currentColor"
            d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.52-.4-1.08-.73-1.69-.98l-.36-2.54A.484.484 0 0 0 14.26 2h-3.84c-.24 0-.43.17-.47.4l-.36 2.54c-.61.25-1.17.59-1.69.98l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.07.64-.07.94s.02.63.06.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.52.4 1.08.73 1.69.98l.36 2.54c.05.23.24.4.47.4h3.84c.24 0 .44-.17.47-.4l.36-2.54c.61-.25 1.17-.59 1.69-.98l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"
          />
        </svg>
      </button>
    </header>

    <main class="wl-main">
      <div v-if="loading && stocks.length === 0" class="wl-state">
        <div class="wl-spinner" />
        <p>加载自选…</p>
      </div>

      <div v-else-if="error" class="wl-state wl-state--err">
        <p>{{ error }}</p>
        <button type="button" class="wl-btn wl-btn--primary wl-btn--grad" @click="loadList">重试</button>
      </div>

      <template v-else-if="stocks.length === 0">
        <div class="wl-empty-hero">
          <p class="wl-empty-hero__t">暂无自选</p>
          <p class="wl-empty-hero__h">搜索 A 股代码或名称，加入主自选列表</p>
          <button type="button" class="wl-btn wl-btn--primary wl-btn--grad" @click="openAddModal">添加品种</button>
        </div>
        <button type="button" class="wl-dropzone" @click="openAddModal">
          <span class="wl-dropzone__plus" aria-hidden="true">+</span>
          <span class="wl-dropzone__txt">点击添加自选</span>
        </button>
      </template>

      <template v-else>
        <section v-if="watchlistStats" class="wl-summary">
          <div class="wl-portfolio">
            <div class="wl-portfolio__inner">
              <p class="wl-kicker">自选概览</p>
              <div class="wl-portfolio__hero tabular">
                <span class="wl-portfolio__avg">{{ fmtSignedPct(watchlistStats.avgPct) }}</span>
                <span class="wl-portfolio__unit">平均涨跌</span>
              </div>
              <div class="wl-portfolio__foot">
                <div>
                  <span class="wl-portfolio__foot-l">标的数量</span>
                  <span class="wl-portfolio__foot-v tabular">{{ watchlistStats.n }} 只</span>
                </div>
                <div>
                  <span class="wl-portfolio__foot-l">总市值约</span>
                  <span class="wl-portfolio__foot-v tabular">{{ fmtCapSum(watchlistStats.capSum) }}</span>
                </div>
              </div>
            </div>
            <div class="wl-portfolio__glow" aria-hidden="true" />
          </div>

          <div class="wl-health">
            <h3 class="wl-kicker">市场情绪</h3>
            <div class="wl-health__row">
              <span class="wl-health__tag tabular" :class="sentimentTone">{{ sentimentWord }}</span>
              <div class="wl-health__bar">
                <div class="wl-health__fill" :style="{ width: watchlistStats.sentimentPct + '%' }" />
              </div>
              <span class="wl-health__pct tabular">{{ watchlistStats.sentimentPct }}%</span>
            </div>
            <p class="wl-health__hint">{{ sentimentHint }}</p>
            <button type="button" class="wl-health__cta" @click="goSectors">
              查看板块热力
              <svg class="wl-svg wl-svg--sm" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
              </svg>
            </button>
          </div>
        </section>

        <section v-if="watchlistStats && advanceBar" class="wl-adstats">
          <div class="wl-adcard">
            <div class="wl-adcard__head">
              <span class="wl-adcard__title">今日 自选股涨跌比</span>
              <span class="wl-adcard__meta tabular">
                {{ watchlistStats.up }} 涨 / {{ watchlistStats.down }} 跌 / {{ watchlistStats.flat }} 平
              </span>
            </div>
            <div class="wl-triple-bar" role="img" :aria-label="`涨${advanceBar.upP}%平${advanceBar.flatP}%跌${advanceBar.downP}%`">
              <div
                v-if="watchlistStats.up > 0"
                class="wl-triple-bar__seg wl-triple-bar__up"
                :style="{ flexGrow: watchlistStats.up }"
              >
                <span v-if="advanceBar.upP >= 10" class="tabular">{{ advanceBar.upP }}%</span>
              </div>
              <div
                v-if="watchlistStats.flat > 0"
                class="wl-triple-bar__seg wl-triple-bar__flat"
                :style="{ flexGrow: watchlistStats.flat }"
              >
                <span v-if="advanceBar.flatP >= 10" class="tabular">{{ advanceBar.flatP }}%</span>
              </div>
              <div
                v-if="watchlistStats.down > 0"
                class="wl-triple-bar__seg wl-triple-bar__down"
                :style="{ flexGrow: watchlistStats.down }"
              >
                <span v-if="advanceBar.downP >= 10" class="tabular">{{ advanceBar.downP }}%</span>
              </div>
            </div>
          </div>

          <div class="wl-adcard">
            <div class="wl-adcard__head">
              <span class="wl-adcard__title">累计收益涨跌比（自选后）</span>
              <span class="wl-adcard__meta tabular">{{ cumPerf.positiveRate }}% 正收益率</span>
            </div>
            <p class="wl-adcard__note">说明：正收益率与强弱条按「今日涨跌幅」统计；未记录加入时成本，非持仓真实累计收益。</p>
            <div
              v-if="cumPerf.hasQuote"
              class="wl-winlos-bar"
              role="img"
              :aria-label="`上涨占比${cumPerf.positiveRate}%`"
            >
              <div
                v-if="cumPerf.up > 0"
                class="wl-winlos-bar__win"
                :style="{ flexGrow: cumPerf.up }"
              >
                <span>WINNERS</span>
              </div>
              <div
                v-if="cumPerf.nonUp > 0"
                class="wl-winlos-bar__lose"
                :style="{ flexGrow: cumPerf.nonUp }"
              >
                <span>LOSERS</span>
              </div>
            </div>
            <div v-else class="wl-winlos-empty tabular">暂无今日涨跌幅数据</div>
            <div class="wl-adcard__foot">
              <div class="wl-adcard__ext">
                <span class="wl-adcard__ext-l">最大涨幅</span>
                <span v-if="cumPerf.maxGain" class="wl-adcard__ext-v wl-adcard__ext-v--gain tabular">
                  {{ cumPerf.maxGain.code }} {{ fmtSignedPct(cumPerf.maxGain.p) }}
                </span>
                <span v-else class="wl-adcard__ext-v tabular">—</span>
              </div>
              <div class="wl-adcard__ext wl-adcard__ext--right">
                <span class="wl-adcard__ext-l">最大跌幅</span>
                <span v-if="cumPerf.maxLoss" class="wl-adcard__ext-v wl-adcard__ext-v--loss tabular">
                  {{ cumPerf.maxLoss.code }} {{ fmtSignedPct(cumPerf.maxLoss.p) }}
                </span>
                <span v-else class="wl-adcard__ext-v tabular">—</span>
              </div>
            </div>
          </div>
        </section>

        <div class="wl-toolbar">
          <h2 class="wl-section-title">主自选列表</h2>
          <div class="wl-toolbar__btns">
            <button type="button" class="wl-toolbtn" @click="sortMenuOpen = true">
              <svg class="wl-svg wl-svg--sm" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="currentColor" d="M3 18h6v-2H3v2zM3 6v2h18V6H3zm0 7h12v-2H3v2z"/>
              </svg>
              {{ sortLabel }}
            </button>
            <button type="button" class="wl-toolbtn" @click="editMode = !editMode">
              <svg class="wl-svg wl-svg--sm" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="currentColor" d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1.003 1.003 0 0 0 0-1.41l-2.34-2.34a1.003 1.003 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
              </svg>
              {{ editMode ? '完成' : '编辑' }}
            </button>
          </div>
        </div>

        <div class="wl-table-card">
          <div class="wl-thead">
            <span>代码 / 名称</span>
            <span class="wl-thead__r">现价</span>
            <span class="wl-thead__r">涨跌</span>
            <span class="wl-thead__r">量 · 高低</span>
          </div>
          <div
            v-for="stock in displayStocks"
            :key="stock.code"
            class="wl-block"
          >
            <div
              class="wl-trow"
              :class="{ 'wl-trow--edit': editMode }"
              @click="editMode ? null : showDetail(stock)"
            >
              <button
                v-if="editMode"
                type="button"
                class="wl-trow__remove"
                :disabled="unstarLoading === stock.code"
                aria-label="移除"
                @click.stop="unstar(stock.code)"
              >
                −
              </button>
              <div class="wl-trow__sym">
                <div class="wl-badge tabular" :style="{ background: badgeBg(stock.code) }">{{ stock.code }}</div>
                <div class="wl-trow__meta">
                  <div class="wl-name">{{ stock.name || '—' }}</div>
                  <div class="wl-ex">{{ exchangeLabel(stock.code) }}</div>
                </div>
              </div>
              <div class="wl-trow__price">
                <span class="wl-price tabular">{{ fmtPrice(stock) }}</span>
                <svg class="wl-spark" viewBox="0 0 52 28" preserveAspectRatio="none" aria-hidden="true">
                  <polyline
                    fill="none"
                    :stroke="sparkStroke(stock)"
                    stroke-width="1.4"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    :points="sparkPoints(stock)"
                  />
                </svg>
              </div>
              <div class="wl-trow__chg tabular">
                <span class="wl-pct" :class="tvDir(stock)">{{ fmtPctOnly(stock) }}</span>
              </div>
              <div class="wl-trow__vol tabular">
                <div class="wl-vol-main">{{ fmtVolume(stock.volume) }}</div>
                <div class="wl-vol-sub">
                  高 {{ fmtNum(stock.high) }} · 低 {{ fmtNum(stock.low) }}
                </div>
              </div>
            </div>
            <div class="wl-subrow">
              <div class="wl-subrow__ohl">
                <span>开 <em class="tabular">{{ fmtNum(stock.open) }}</em></span>
                <span>高 <em class="tabular">{{ fmtNum(stock.high) }}</em></span>
                <span>低 <em class="tabular">{{ fmtNum(stock.low) }}</em></span>
              </div>
              <div v-if="isActiveStock(stock)" class="wl-subrow__live">
                <span class="wl-dot" aria-hidden="true" />
                量比活跃
              </div>
            </div>
          </div>
        </div>

        <button type="button" class="wl-dropzone wl-dropzone--tight" @click="openAddModal">
          <span class="wl-dropzone__plus" aria-hidden="true">+</span>
          <span class="wl-dropzone__txt">继续添加自选</span>
        </button>
      </template>
    </main>

    <div class="wl-sheet" :class="{ active: sortMenuOpen }" @click.self="sortMenuOpen = false">
      <div class="wl-sheet__panel" @click.stop>
        <p class="wl-sheet__title">排序方式</p>
        <button
          v-for="opt in sortOptions"
          :key="opt.id"
          type="button"
          class="wl-sheet__opt"
          :class="{ on: sortKey === opt.id }"
          @click="pickSort(opt.id)"
        >
          {{ opt.label }}
        </button>
        <button type="button" class="wl-sheet__cancel" @click="sortMenuOpen = false">取消</button>
      </div>
    </div>

    <!-- 全屏搜索添加 -->
    <div class="wl-add" :class="{ active: showAddModal }">
      <div class="wl-add__head">
        <div class="wl-add__search">
          <svg class="wl-add__glass" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
          </svg>
            <input
              ref="searchInputRef"
              v-model="searchKeyword"
            type="search"
            class="wl-add__input"
            placeholder="搜索代码、名称"
            enterkeyhint="search"
              @input="onSearchInput"
            />
          <button v-if="searchKeyword" type="button" class="wl-add__clear" @click="clearSearch">
            <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
            </button>
        </div>
        <button type="button" class="wl-add__close" @click="closeAddModal">关闭</button>
          </div>

      <div class="wl-add__body">
        <div v-if="stockCount === 0" class="wl-sync">
          <p>本地股票库为空，请先同步后再搜索。</p>
          <button type="button" class="wl-btn wl-btn--primary" :disabled="syncing" @click="syncStocks">
            {{ syncing ? '同步中…' : '同步股票库' }}
          </button>
          </div>

        <div v-if="searching" class="wl-add__loading">
          <div class="wl-spinner wl-spinner--sm" />
          <span>搜索中…</span>
        </div>

        <ul v-else-if="searchResults.length" class="wl-find">
          <li
              v-for="item in searchResults"
              :key="item.code"
            class="wl-find__row"
          >
            <div class="wl-find__left">
              <span class="wl-find__code">{{ item.code }}</span>
              <span class="wl-find__name">{{ item.name }}</span>
              <span class="wl-find__ex">{{ marketLabel(item.market_type) }}</span>
              </div>
            <button
              type="button"
              class="wl-find__plus"
              :disabled="isInList(item.code)"
              :aria-label="isInList(item.code) ? '已在自选' : '添加'"
              @click="selectStock(item)"
            >
              <svg v-if="isInList(item.code)" viewBox="0 0 24 24" width="20" height="20">
                <path fill="var(--up)" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" width="22" height="22">
                <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
              </svg>
            </button>
          </li>
        </ul>

        <div v-else-if="searchKeyword && !searching" class="wl-add__empty">
          <template v-if="needsStockSync">请先同步股票库。</template>
          <template v-else>未找到「{{ searchKeyword }}」</template>
          </div>

        <p v-else-if="!searchKeyword && stockCount !== 0" class="wl-add__tip">输入代码或名称查找 A 股</p>
      </div>
    </div>

    <!-- 详情（深色） -->
    <div class="wl-detail" :class="{ active: detailVisible }" @click.self="closeDetail">
      <div class="wl-detail__panel">
        <header class="wl-detail__bar">
          <button type="button" class="wl-detail__iconbtn" aria-label="返回" @click="closeDetail">
            <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/></svg>
          </button>
          <span class="wl-detail__headline">{{ detailStock?.name || '' }}</span>
          <button
            type="button"
            class="wl-detail__star"
            :class="{ on: inWatchlist }"
            :title="inWatchlist ? '取消自选' : '加自选'"
            @click="toggleWatchlist"
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path
                :fill="inWatchlist ? 'var(--wl-primary)' : 'none'"
                :stroke="inWatchlist ? 'var(--wl-primary)' : 'currentColor'"
                stroke-width="1.5"
                d="M12 17.3l5.2 3.1-1.4-5.9L20 9.8l-6-.5L12 3.7 9.9 9.3l-6 .5 4.2 4.7-1.4 5.9 5.3-3.1z"
              />
            </svg>
          </button>
        </header>
        <div v-if="detailStock" class="wl-detail__scroll">
          <!-- 价格区 -->
          <div class="wl-detail__priceblk">
            <div class="wl-detail__row1">
              <span class="wl-detail__px">{{ fmtPrice(detailStock) }}</span>
              <span class="wl-detail__pct" :class="tvDir(detailStock)">{{ fmtDeltaLine(detailStock) }}</span>
        </div>
            <div class="wl-detail__meta">
              <span class="wl-detail__tag">{{ detailStock.code }}</span>
              <span v-if="detailStock.sector" class="wl-detail__tag">{{ detailStock.sector }}</span>
            </div>
          </div>

          <!-- 行情数据网格 -->
          <div v-if="detailQuote" class="wl-detail__stats">
            <div class="wl-detail__stat-row">
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">今开</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.open) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">最高</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.high) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">最低</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.low) }}</span>
              </div>
            </div>
            <div class="wl-detail__stat-row">
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">成交量</span>
                <span class="wl-detail__stat-v">{{ fmtAmt(detailQuote.volume) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">成交额</span>
                <span class="wl-detail__stat-v">{{ fmtAmt(detailQuote.amount) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">换手率</span>
                <span class="wl-detail__stat-v">{{ fmtPct(detailQuote.turnover) }}</span>
              </div>
            </div>
            <div class="wl-detail__stat-row">
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">量比</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.qtyRatio) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">振幅</span>
                <span class="wl-detail__stat-v">{{ fmtPct(detailQuote.amplitude) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">市盈率</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.pe) }}</span>
              </div>
            </div>
            <div class="wl-detail__stat-row">
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">总市值</span>
                <span class="wl-detail__stat-v">{{ fmtCap(detailQuote.mktCap) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">流通市值</span>
                <span class="wl-detail__stat-v">{{ fmtCap(detailQuote.floatMktCap) }}</span>
              </div>
              <div class="wl-detail__stat">
                <span class="wl-detail__stat-l">市净率</span>
                <span class="wl-detail__stat-v">{{ fmtVal(detailQuote.pb) }}</span>
              </div>
            </div>
          </div>

          <!-- K线图 -->
          <div class="wl-detail__chart">
            <KlineChart v-if="detailStock.code" :code="detailStock.code" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { watchlist } from '@/api/strategy.js'
import { stock } from '@/api/strategy.js'
import { stocks as stocksApi } from '@/api/strategy.js'
import KlineChart from '@/components/KlineChart.vue'

const router = useRouter()

const FLAG_PALETTE = ['var(--wl-rise)', 'var(--wl-fall)', 'var(--wl-primary)', 'var(--wl-primary-mid)', 'var(--wl-rise)']

const loading = ref(true)
const error = ref('')
const stocks = ref([])
const unstarLoading = ref(null)

const detailStock = ref(null)
const detailQuote = ref(null)
const detailVisible = ref(false)
const inWatchlist = ref(true)

const showAddModal = ref(false)
const editMode = ref(false)
const sortKey = ref('order')
const sortMenuOpen = ref(false)

const searchKeyword = ref('')
const searchResults = ref([])
const searching = ref(false)
const searchInputRef = ref(null)
const syncing = ref(false)
const stockCount = ref(-1)
const needsStockSync = ref(false)

const listTitle = ref('自选')

let searchTimer = null

const sortOptions = [
  { id: 'order', label: '顺序' },
  { id: 'pct_desc', label: '涨幅' },
  { id: 'pct_asc', label: '跌幅' },
  { id: 'name', label: '名称' },
]

const sortLabel = computed(() => sortOptions.find((o) => o.id === sortKey.value)?.label ?? '排序')

const watchlistStats = computed(() => {
  const arr = stocks.value
  if (!arr.length) return null
  let up = 0
  let down = 0
  let flat = 0
  const pcts = []
  let capSum = 0
  for (const s of arr) {
    const p = Number(s.pct_change)
    if (Number.isFinite(p)) {
      pcts.push(p)
      if (p > 0) up++
      else if (p < 0) down++
      else flat++
    } else {
      flat++
    }
    const c = Number(s.mkt_cap)
    if (Number.isFinite(c) && c > 0) capSum += c
  }
  const n = arr.length
  const avgPct = pcts.length ? pcts.reduce((a, b) => a + b, 0) / pcts.length : 0
  const sentimentPct = n ? Math.round((up / n) * 100) : 0
  return { up, down, flat, n, avgPct, sentimentPct, capSum }
})

/** 三色条用整数百分比，保证合计 100 */
const advanceBar = computed(() => {
  const s = watchlistStats.value
  if (!s || !s.n) return null
  const n = s.n
  const upP = Math.floor((100 * s.up) / n)
  const flatP = Math.floor((100 * s.flat) / n)
  const downP = 100 - upP - flatP
  return { upP, flatP, downP }
})

/** 第二卡：今日涨跌幅下的强弱与极值（无加入价则非真实累计收益） */
const cumPerf = computed(() => {
  const arr = stocks.value
  if (!arr.length) {
    return {
      up: 0,
      nonUp: 0,
      positiveRate: 0,
      maxGain: null,
      maxLoss: null,
      hasQuote: false,
    }
  }
  let up = 0
  let maxGain = null
  let maxLoss = null
  let hasQuote = false
  for (const s of arr) {
    const p = Number(s.pct_change)
    if (!Number.isFinite(p)) continue
    hasQuote = true
    if (p > 0) up++
    if (maxGain === null || p > maxGain.p) maxGain = { code: s.code, p }
    if (maxLoss === null || p < maxLoss.p) maxLoss = { code: s.code, p }
  }
  const n = arr.length
  const positiveRate = n ? Math.round((100 * up) / n) : 0
  const nonUp = Math.max(0, n - up)
  return {
    up,
    nonUp,
    positiveRate,
    maxGain,
    maxLoss,
    hasQuote,
  }
})

const sentimentWord = computed(() => {
  const s = watchlistStats.value
  if (!s) return '—'
  if (s.avgPct > 0.2) return '偏强'
  if (s.avgPct < -0.2) return '偏弱'
  return '盘整'
})

const sentimentTone = computed(() => {
  const s = watchlistStats.value
  if (!s) return ''
  if (s.avgPct > 0.2) return 'is-up'
  if (s.avgPct < -0.2) return 'is-down'
  return 'is-mid'
})

const sentimentHint = computed(() => {
  const s = watchlistStats.value
  if (!s) return ''
  return `共 ${s.n} 只：${s.up} 只上涨、${s.down} 只下跌（按最新涨跌幅）。`
})

const displayStocks = computed(() => {
  const arr = [...stocks.value]
  if (sortKey.value === 'name') {
    arr.sort((a, b) => (a.name || a.code).localeCompare(b.name || b.code, 'zh-CN'))
  } else if (sortKey.value === 'pct_desc') {
    arr.sort((a, b) => (Number(b.pct_change) || -1e9) - (Number(a.pct_change) || -1e9))
  } else if (sortKey.value === 'pct_asc') {
    arr.sort((a, b) => (Number(a.pct_change) || 1e9) - (Number(b.pct_change) || 1e9))
  }
  return arr
})

function flagColor(code) {
  let h = 0
  const s = String(code || '')
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return FLAG_PALETTE[h % FLAG_PALETTE.length]
}

function badgeBg(code) {
  return flagColor(code)
}

function goSectors() {
  router.push('/sectors')
}

function goWatchlistSettings() {
  router.push('/watchlist/settings')
}

function pickSort(id) {
  sortKey.value = id
  sortMenuOpen.value = false
}

function exchangeLabel(code) {
  const c = String(code || '')
  if (c.startsWith('6') || c.startsWith('9')) return '沪市'
  if (c.startsWith('0') || c.startsWith('3')) return '深市'
  if (c.startsWith('8') || c.startsWith('4')) return '北交所'
  return 'A股'
}

function fmtSignedPct(p) {
  if (!Number.isFinite(p)) return '--'
  return (p >= 0 ? '+' : '') + p.toFixed(2) + '%'
}

function fmtPctOnly(s) {
  const p = Number(s.pct_change)
  if (!Number.isFinite(p)) return '--'
  return (p >= 0 ? '+' : '') + p.toFixed(2) + '%'
}

function fmtNum(v) {
  if (v == null || v === '-' || Number.isNaN(Number(v))) return '—'
  return Number(v).toFixed(2)
}

function fmtVolume(v) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万'
  return String(Math.round(n))
}

function fmtCapSum(sum) {
  if (!sum || !Number.isFinite(sum) || sum <= 0) return '—'
  if (sum >= 1e12) return (sum / 1e12).toFixed(2) + '万亿'
  if (sum >= 1e8) return (sum / 1e8).toFixed(2) + '亿'
  return (sum / 1e4).toFixed(0) + '万'
}

function isActiveStock(s) {
  const q = Number(s.qty_ratio)
  return Number.isFinite(q) && q > 1.15
}

function sparkStroke(stock) {
  const mk = stock?.mini_kline
  if (mk?.closes?.length >= 2) {
    const first = Number(mk.closes[0])
    const last = Number(mk.closes[mk.closes.length - 1])
    return last >= first ? 'var(--wl-rise)' : 'var(--wl-fall)'
  }
  return tvDir(stock) === 'is-up' ? 'var(--wl-rise)' : 'var(--wl-fall)'
}

function sparkPoints(stock) {
  const mk = stock?.mini_kline
  const closes = mk?.closes
  const dates = mk?.dates
  if (!closes?.length) {
    // 兜底：生成假的确定性曲线（用于没有数据时保持UI美观）
    const code = stock?.code || ''
    let seed = 2166136261
    for (let i = 0; i < code.length; i++) {
      seed ^= code.charCodeAt(i)
      seed = Math.imul(seed, 16777619)
    }
    const isUp = Number(stock?.pct_change || 0) >= 0
    const w = 52
    const h = 28
    const pts = []
    for (let i = 0; i <= 16; i++) {
      const t = i / 16
      const x = (t * w).toFixed(1)
      const wave =
        Math.sin(seed * 1e-6 + t * 5) * 0.45 +
        Math.sin(t * 11 + (seed >>> 4)) * 0.25
      const drift = isUp ? -t * 4 : t * 4
      let y = h / 2 + wave * (h * 0.38) + drift
      y = Math.max(2, Math.min(h - 2, y))
      pts.push(`${x},${y.toFixed(1)}`)
    }
    return pts.join(' ')
  }

  // 真实数据：从真实收盘价生成缩略图
  const valid = closes.map((c, i) => ({ c: Number(c), t: i / (closes.length - 1) }))
  if (valid.length < 2) return ''
  const minC = Math.min(...valid.map(v => v.c))
  const maxC = Math.max(...valid.map(v => v.c))
  const range = maxC - minC || 1
  const w = 52
  const h = 28
  const pad = 3
  const pts = valid.map(v => {
    const x = (v.t * w).toFixed(1)
    const y = (h - pad - ((v.c - minC) / range) * (h - pad * 2)).toFixed(1)
    return `${x},${y}`
  })
  return pts.join(' ')
}

async function loadList() {
  loading.value = true
  error.value = ''
  try {
    const data = await watchlist.enriched()
    const raw = Array.isArray(data) ? data : []
    stocks.value = raw
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function unstar(code) {
  if (unstarLoading.value === code) return
  unstarLoading.value = code
  try {
    await watchlist.remove(code)
    stocks.value = stocks.value.filter((s) => s.code !== code)
    if (detailStock.value?.code === code) closeDetail()
  } catch (e) {
    alert(e.message || '移除失败')
  } finally {
    unstarLoading.value = null
  }
}

function closeAddModal() {
  showAddModal.value = false
  searchKeyword.value = ''
  searchResults.value = []
  clearTimeout(searchTimer)
}

function onSearchInput() {
  clearTimeout(searchTimer)
  const kw = searchKeyword.value.trim()
  if (!kw) {
    searchResults.value = []
    searching.value = false
    return
  }
  searching.value = true
  searchTimer = setTimeout(() => doSearch(kw), 280)
}

async function doSearch(kw) {
  try {
    const { list, stockCount: sc, needsSync } = await stocksApi.search(kw, 30)
    searchResults.value = list || []
    stockCount.value = sc
    needsStockSync.value = needsSync
  } catch {
    searchResults.value = []
    needsStockSync.value = stockCount.value === 0
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  searchKeyword.value = ''
  searchResults.value = []
  nextTick(() => searchInputRef.value?.focus())
}

async function syncStocks() {
  syncing.value = true
  try {
    const ret = await stocksApi.sync()
    const total = ret?.total ?? ret?.count
    if (typeof total === 'number') stockCount.value = total
    else {
      const s = await stocksApi.status()
      stockCount.value = s.count
    }
    needsStockSync.value = stockCount.value === 0
    if (searchKeyword.value.trim()) {
      await doSearch(searchKeyword.value.trim())
    }
  } catch (e) {
    alert(e.message || '同步失败')
  } finally {
    syncing.value = false
  }
}

function isInList(code) {
  return stocks.value.some((s) => s.code === code)
}

function marketLabel(market) {
  return { sh: '沪市', sz: '深市', bj: '北交所' }[market] || 'A股'
}

async function selectStock(item) {
  if (isInList(item.code)) return
  try {
    await watchlist.add(item.code, item.name, item.sector || '')
    const placeholder = { code: item.code, name: item.name, sector: item.sector || '' }
    stocks.value.unshift(placeholder)
    try {
      const q = await stock.quote(item.code)
      const idx = stocks.value.findIndex((s) => s.code === item.code)
      if (idx !== -1) {
        stocks.value[idx] = {
          ...stocks.value[idx],
          close:      q?.close,
          pct_change: q?.pct_change,
          change_amt: q?.change,
        }
      }
    } catch {}
    closeAddModal()
  } catch (e) {
    alert(e.message || '添加失败')
  }
}

async function openAddModal() {
  showAddModal.value = true
  try {
    const s = await stocksApi.status()
    stockCount.value = s.count
    needsStockSync.value = s.needsSync
  } catch {
    stockCount.value = 0
    needsStockSync.value = true
  }
  nextTick(() => {
    searchInputRef.value?.focus()
  })
}

async function showDetail(s) {
  detailStock.value = { ...s }
  // 优先复用已加载的行情数据（来自 enriched 接口）
  const cached = stocks.value.find(x => x.code === s.code)
  detailQuote.value = cached
    ? {
        open:      cached.open,
        high:      cached.high,
        low:       cached.low,
        volume:    cached.volume,
        amount:    cached.amount,
        turnover:  cached.turnover,
        qtyRatio:  cached.qty_ratio,
        amplitude: null,
        pe:        null,
        pb:        null,
        mktCap:    cached.mkt_cap,
        floatMktCap: null,
      }
    : null
  inWatchlist.value = true
  detailVisible.value = true
  // 如果列表中没有详细数据，再请求一次
  if (!detailQuote.value?.open) {
    try {
      const q = await stock.quote(s.code)
      detailQuote.value = q
    } catch {}
  }
}

function closeDetail() {
  detailVisible.value = false
}

async function toggleWatchlist() {
  if (!detailStock.value) return
  const code = detailStock.value.code
  const name = detailStock.value.name
  const sector = detailStock.value.sector
  if (inWatchlist.value) {
    try {
      await watchlist.remove(code)
      inWatchlist.value = false
      stocks.value = stocks.value.filter((s) => s.code !== code)
    } catch (e) {
      alert(e.message || '移除失败')
    }
  } else {
    try {
      await watchlist.add(code, name, sector)
      inWatchlist.value = true
      if (!stocks.value.find((s) => s.code === code)) {
        stocks.value.unshift({ ...detailStock.value })
      }
    } catch (e) {
      alert(e.message || '添加失败')
    }
  }
}

/** A 股配色：涨红跌绿（与全局 .up/.down 区分，避免 !important 冲突） */
function tvDir(s) {
  const n = Number(s?.pct_change)
  if (!Number.isFinite(n)) return ''
  return n >= 0 ? 'is-up' : 'is-down'
}

function fmtPrice(s) {
  const n = Number(s.close)
  return Number.isFinite(n) ? n.toFixed(2) : '--'
}

function fmtDeltaLine(s) {
  const pct = Number(s.pct_change)
  // 优先用后端返回的真实涨跌额
  if (Number.isFinite(s.change_amt) && s.change_amt !== null) {
    const sd = s.change_amt >= 0 ? '+' : ''
    const sp = pct >= 0 ? '+' : ''
    return `${sd}${Number(s.change_amt).toFixed(2)} ${sp}${pct.toFixed(2)}%`
  }
  // 兜底：用手数和涨跌幅反推
  const close = Number(s.close)
  if (!Number.isFinite(pct) || !Number.isFinite(close)) return '--'
  const prev = close / (1 + pct / 100)
  const delta = close - prev
  const sd = delta >= 0 ? '+' : ''
  const sp = pct >= 0 ? '+' : ''
  return `${sd}${delta.toFixed(2)} ${sp}${pct.toFixed(2)}%`
}

function fmtVal(v) {
  if (v == null || v === '-' || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

function fmtPct(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'
}

function fmtAmt(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}

function fmtCap(v) {
  if (v == null || Number.isNaN(Number(v))) return '--'
  const n = Number(v)
  if (n >= 1e12) return (n / 1e12).toFixed(2) + '万亿'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  return (n / 1e4).toFixed(0) + '万'
}

watch([showAddModal, detailVisible, sortMenuOpen], ([add, det, sort]) => {
  document.body.style.overflow = add || det || sort ? 'hidden' : ''
})

onMounted(() => loadList())
onUnmounted(() => {
  document.body.style.overflow = ''
  sortMenuOpen.value = false
})
</script>

<style scoped>
/* Architectural Ledger — DESIGN.md + stitch Terminal watchlist */
.wl {
  --wl-primary: #003ec7;
  --wl-primary-mid: #0052ff;
  --wl-rise: #f23645;
  --wl-fall: #089981;
  --wl-surface: #f8f9fa;
  --wl-surface-low: #f3f4f5;
  --wl-surface-high: #e7e8e9;
  --wl-surface-lowest: #ffffff;
  --wl-on-surface: #191c1d;
  --wl-on-variant: #434656;
  --wl-outline: #737688;
  --wl-ghost: rgba(195, 197, 217, 0.15);
  --wl-ambient: 0 4px 24px rgba(25, 28, 29, 0.06);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--wl-surface);
  color: var(--wl-on-surface);
  padding-bottom: calc(env(safe-area-inset-bottom) + 72px);
  font-family: 'Inter', var(--font);
}

.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}

.wl-topbar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: calc(48px + env(safe-area-inset-top, 0));
  padding: env(safe-area-inset-top, 0) 12px 0;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 1px 0 var(--wl-ghost);
}
.wl-topbar__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--wl-primary-mid);
  background: transparent;
  cursor: pointer;
}
.wl-topbar__icon:active {
  background: var(--wl-surface-low);
}
.wl-brand {
  flex: 1;
  text-align: center;
  font-family: 'Manrope', var(--font);
  font-size: 1.125rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--wl-primary);
  margin: 0;
}

.wl-svg {
  width: 22px;
  height: 22px;
  display: block;
}
.wl-svg--sm {
  width: 18px;
  height: 18px;
}

.wl-main {
  padding: 12px 14px 24px;
}

.wl-state {
  text-align: center;
  padding: 72px 20px 40px;
  color: var(--wl-on-variant);
  font-size: 14px;
}
.wl-state--err .wl-btn {
  margin-top: 16px;
}
.wl-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--wl-surface-high);
  border-top-color: var(--wl-primary);
  border-radius: 50%;
  animation: wl-spin 0.75s linear infinite;
  margin: 0 auto 12px;
}
.wl-spinner--sm {
  width: 18px;
  height: 18px;
  border-width: 2px;
  margin: 0;
}
@keyframes wl-spin {
  to { transform: rotate(360deg); }
}

.wl-empty-hero {
  text-align: center;
  padding: 36px 16px 28px;
}
.wl-empty-hero__t {
  font-family: 'Manrope', var(--font);
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--wl-on-surface);
  margin-bottom: 8px;
}
.wl-empty-hero__h {
  font-size: 13px;
  color: var(--wl-on-variant);
  line-height: 1.45;
  margin-bottom: 20px;
}

.wl-summary {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}
@media (min-width: 520px) {
  .wl-summary {
    grid-template-columns: 1.55fr 1fr;
  }
}

.wl-portfolio {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: linear-gradient(135deg, var(--wl-primary) 0%, #1a4a9e 50%, var(--wl-primary-mid) 100%);
  color: #fff;
  box-shadow: var(--wl-ambient);
}
.wl-portfolio__inner {
  position: relative;
  z-index: 1;
  padding: 18px 16px;
}
.wl-portfolio__glow {
  position: absolute;
  right: -20px;
  top: -20px;
  width: 100px;
  height: 100px;
  background: rgba(255, 255, 255, 0.14);
  border-radius: 50%;
  filter: blur(20px);
}
.wl-kicker {
  font-family: 'Manrope', var(--font);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.88;
  margin: 0 0 10px;
}
.wl-portfolio__hero {
  min-width: 0;
}
.wl-portfolio__avg {
  display: block;
  font-family: 'Manrope', var(--font);
  font-size: 27px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.1;
}
.wl-portfolio__unit {
  display: block;
  font-size: 11px;
  opacity: 0.85;
  margin-top: 4px;
}
.wl-portfolio__foot {
  display: flex;
  gap: 22px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.22);
  font-size: 10px;
}
.wl-portfolio__foot-l {
  display: block;
  opacity: 0.75;
  margin-bottom: 2px;
}
.wl-portfolio__foot-v {
  font-weight: 700;
  font-size: 12px;
}

.wl-health {
  border-radius: 8px;
  background: var(--wl-surface-lowest);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  padding: 14px 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wl-health .wl-kicker {
  color: var(--wl-outline);
}
.wl-health__row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wl-health__tag {
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}
.wl-health__tag.is-up {
  color: var(--wl-rise);
}
.wl-health__tag.is-down {
  color: var(--wl-fall);
}
.wl-health__tag.is-mid {
  color: var(--wl-on-variant);
}
.wl-health__bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--wl-surface-high);
  overflow: hidden;
}
.wl-health__fill {
  height: 100%;
  background: var(--wl-rise);
  border-radius: 3px;
  transition: width 0.25s ease;
}
.wl-health__pct {
  font-size: 10px;
  font-weight: 700;
  color: var(--wl-outline);
  flex-shrink: 0;
  min-width: 30px;
  text-align: right;
}
.wl-health__hint {
  font-size: 10px;
  line-height: 1.45;
  color: var(--wl-on-variant);
  margin: 0;
}
.wl-health__cta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  padding: 0;
  background: none;
  border: none;
  font-size: 11px;
  font-weight: 700;
  color: var(--wl-primary);
  cursor: pointer;
}

/* 今日涨跌比 + 强弱分布（概览与列表之间） */
.wl-adstats {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 18px;
}
.wl-adcard {
  background: var(--wl-surface-lowest);
  border-radius: 8px;
  padding: 14px 14px 16px;
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
}
.wl-adcard__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.wl-adcard__title {
  font-size: 14px;
  font-weight: 800;
  color: var(--wl-on-surface);
  letter-spacing: -0.02em;
}
.wl-adcard__meta {
  font-size: 12px;
  font-weight: 600;
  color: var(--wl-on-variant);
  white-space: nowrap;
}
.wl-adcard__note {
  font-size: 10px;
  line-height: 1.45;
  color: var(--wl-outline);
  margin: -6px 0 12px;
}
.wl-triple-bar {
  display: flex;
  height: 38px;
  border-radius: 4px;
  overflow: hidden;
  font-size: 12px;
  font-weight: 800;
}
.wl-triple-bar__seg {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  flex-shrink: 0;
}
.wl-triple-bar__up {
  background: var(--wl-rise);
  color: #fff;
}
.wl-triple-bar__flat {
  background: #d1d4dc;
  color: #434656;
}
.wl-triple-bar__down {
  background: var(--wl-fall);
  color: #fff;
}

.wl-winlos-bar {
  display: flex;
  height: 40px;
  border-radius: 4px;
  overflow: hidden;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  margin-bottom: 14px;
}
.wl-winlos-bar__win {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  background: var(--wl-rise);
  color: #fff;
}
.wl-winlos-bar__lose {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  background: var(--wl-fall);
  color: #fff;
}
.wl-winlos-empty {
  height: 40px;
  margin-bottom: 14px;
  border-radius: 4px;
  background: var(--wl-surface-low);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--wl-outline);
}
.wl-adcard__foot {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.wl-adcard__ext {
  flex: 1;
  min-width: 0;
}
.wl-adcard__ext--right {
  text-align: right;
}
.wl-adcard__ext-l {
  display: block;
  font-size: 10px;
  font-weight: 600;
  color: var(--wl-outline);
  margin-bottom: 4px;
}
.wl-adcard__ext-v {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.wl-adcard__ext-v--gain {
  color: var(--wl-rise);
}
.wl-adcard__ext-v--loss {
  color: var(--wl-fall);
}

.wl-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  padding: 0 2px;
}
.wl-section-title {
  font-family: 'Manrope', var(--font);
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
}
.wl-toolbar__btns {
  display: flex;
  gap: 8px;
}
.wl-toolbtn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--wl-on-variant);
  background: var(--wl-surface-low);
  cursor: pointer;
  border: none;
}
.wl-toolbtn:active {
  background: var(--wl-surface-high);
}

.wl-table-card {
  border-radius: 8px;
  background: var(--wl-surface-lowest);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  overflow: hidden;
  margin-bottom: 14px;
}
.wl-thead {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(64px, 0.78fr) minmax(48px, 0.42fr) minmax(82px, 0.92fr);
  gap: 6px;
  align-items: center;
  padding: 8px 10px;
  background: var(--wl-surface-low);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--wl-outline);
}
.wl-thead__r {
  text-align: right;
}

.wl-block + .wl-block {
  box-shadow: 0 -1px 0 var(--wl-ghost);
}
.wl-trow {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(64px, 0.78fr) minmax(48px, 0.42fr) minmax(82px, 0.92fr);
  gap: 6px;
  align-items: center;
  padding: 10px 10px 6px;
  cursor: pointer;
  position: relative;
}
.wl-trow:active {
  background: var(--wl-surface-low);
}

.wl-trow__remove {
  position: absolute;
  left: 6px;
  top: 50%;
  transform: translateY(-50%);
  width: 26px;
  height: 26px;
  border-radius: 4px;
  background: var(--wl-rise);
  color: #fff;
  border: none;
  font-size: 16px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}
.wl-trow__remove:disabled {
  opacity: 0.45;
}
.wl-trow--edit .wl-trow__sym {
  padding-left: 34px;
}

.wl-trow__sym {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.wl-badge {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  color: #fff;
  letter-spacing: -0.02em;
  line-height: 1.05;
  text-align: center;
  word-break: break-all;
  padding: 2px;
}
.wl-trow__meta {
  min-width: 0;
}
.wl-name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wl-ex {
  font-size: 11px;
  font-weight: 600;
  color: var(--wl-outline);
  text-transform: uppercase;
  margin-top: 2px;
}

.wl-trow__price {
  text-align: right;
}
.wl-price {
  display: block;
  font-size: 14px;
  font-weight: 700;
}
.wl-spark {
  width: 56px;
  height: 22px;
  margin-left: auto;
  margin-top: 2px;
  opacity: 0.9;
  display: block;
}

.wl-trow__chg {
  text-align: right;
}
.wl-pct {
  font-size: 14px;
  font-weight: 700;
}
.wl-pct.is-up {
  color: var(--wl-rise);
}
.wl-pct.is-down {
  color: var(--wl-fall);
}

.wl-trow__vol {
  text-align: right;
  font-size: 12px;
  font-weight: 600;
  color: var(--wl-on-variant);
}
.wl-vol-main {
  font-weight: 700;
  color: var(--wl-on-surface);
}
.wl-vol-sub {
  font-size: 9px;
  margin-top: 3px;
  line-height: 1.2;
  opacity: 0.92;
}

.wl-subrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 10px 10px;
  font-size: 10px;
  font-weight: 600;
  color: var(--wl-outline);
}
.wl-subrow__ohl {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.wl-subrow__ohl em {
  font-style: normal;
  color: var(--wl-on-surface);
}
.wl-subrow__live {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 10px;
  color: var(--wl-fall);
}
.wl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--wl-fall);
}

.wl-dropzone {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 36px 16px;
  border-radius: 8px;
  border: 2px dashed var(--wl-ghost);
  background: transparent;
  cursor: pointer;
  color: var(--wl-outline);
}
.wl-dropzone--tight {
  padding: 22px 16px;
}
.wl-dropzone__plus {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--wl-surface-low);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: 300;
  line-height: 1;
  color: var(--wl-outline);
}
.wl-dropzone__txt {
  font-size: 11px;
  font-weight: 700;
}

.wl-sheet {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 190;
  background: rgba(0, 0, 0, 0.35);
  align-items: flex-end;
  justify-content: center;
}
.wl-sheet.active {
  display: flex;
}
.wl-sheet__panel {
  width: 100%;
  max-width: 520px;
  background: var(--wl-surface-lowest);
  border-radius: 12px 12px 0 0;
  padding: 14px 14px calc(18px + env(safe-area-inset-bottom));
  box-shadow: var(--wl-ambient);
}
.wl-sheet__title {
  font-family: 'Manrope', var(--font);
  font-size: 13px;
  font-weight: 800;
  color: var(--wl-on-variant);
  margin: 0 0 10px;
  text-align: center;
}
.wl-sheet__opt {
  display: block;
  width: 100%;
  text-align: left;
  padding: 12px 14px;
  border-radius: 4px;
  border: none;
  background: var(--wl-surface-low);
  font-size: 15px;
  font-weight: 600;
  color: var(--wl-on-surface);
  margin-bottom: 6px;
  cursor: pointer;
}
.wl-sheet__opt.on {
  box-shadow: inset 0 0 0 2px var(--wl-primary);
}
.wl-sheet__cancel {
  display: block;
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  border: none;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: var(--wl-outline);
  cursor: pointer;
}

.wl-btn {
  padding: 11px 22px;
  border-radius: 4px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  border: none;
}
.wl-btn--primary {
  background: var(--wl-primary);
  color: #fff;
}
.wl-btn--grad {
  background: linear-gradient(135deg, var(--wl-primary) 0%, var(--wl-primary-mid) 100%);
  box-shadow: var(--wl-ambient);
}

/* Fullscreen add */
.wl-add {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 200;
  flex-direction: column;
  background: var(--wl-surface);
}
.wl-add.active { display: flex; }
.wl-add__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  padding-top: calc(10px + env(safe-area-inset-top));
  box-shadow: 0 1px 0 var(--wl-ghost);
}
.wl-add__search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--wl-surface-low);
  border-radius: 4px;
  padding: 10px 12px;
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
}
.wl-add__glass {
  width: 20px;
  height: 20px;
  fill: var(--wl-outline);
  flex-shrink: 0;
}
.wl-add__input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--wl-on-surface);
  font-size: 16px;
  outline: none;
  min-width: 0;
}
.wl-add__input::placeholder { color: var(--wl-outline); opacity: 0.75; }
.wl-add__clear {
  padding: 0;
  color: var(--wl-outline);
  cursor: pointer;
  display: flex;
}
.wl-add__close {
  font-size: 16px;
  font-weight: 600;
  color: var(--wl-primary);
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px 4px;
  flex-shrink: 0;
}
.wl-add__body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0;
}
.wl-sync {
  padding: 20px 16px;
  font-size: 14px;
  color: var(--wl-on-variant);
  line-height: 1.5;
}
.wl-sync p { margin-bottom: 12px; }
.wl-add__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px;
  color: var(--wl-on-variant);
}
.wl-find {
  list-style: none;
  margin: 0;
  padding: 0;
}
.wl-find__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 0 var(--wl-ghost);
}
.wl-find__row:active {
  background: var(--wl-surface-low);
}
.wl-find__left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wl-find__code {
  font-size: 15px;
  font-weight: 700;
  color: var(--wl-primary);
}
.wl-find__name { font-size: 13px; color: var(--wl-on-surface); }
.wl-find__ex { font-size: 11px; color: var(--wl-outline); }
.wl-find__plus {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  border: none;
  background: var(--wl-surface-low);
  color: var(--wl-outline);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.wl-find__plus:disabled {
  cursor: default;
  opacity: 0.85;
}
.wl-add__empty,
.wl-add__tip {
  text-align: center;
  padding: 40px 20px;
  color: var(--wl-on-variant);
  font-size: 14px;
}

/* Detail drawer */
.wl-detail {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 210;
  background: rgba(0, 0, 0, 0.45);
}
.wl-detail.active { display: block; }
.wl-detail__panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  background: var(--wl-surface-lowest);
  display: flex;
  flex-direction: column;
  animation: wl-slide 0.3s ease;
}
@keyframes wl-slide {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}
.wl-detail__bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  padding-top: calc(10px + env(safe-area-inset-top));
  box-shadow: 0 1px 0 var(--wl-ghost);
  flex-shrink: 0;
}
.wl-detail__iconbtn {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  background: var(--wl-surface-low);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  color: var(--wl-outline);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.wl-detail__headline {
  flex: 1;
  font-size: 16px;
  font-weight: 700;
  color: var(--wl-on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wl-detail__star {
  width: 40px;
  height: 40px;
  border-radius: 4px;
  background: var(--wl-surface-low);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  color: var(--wl-outline);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.wl-detail__star.on { box-shadow: inset 0 0 0 2px var(--wl-primary); }
.wl-detail__scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: calc(24px + env(safe-area-inset-bottom));
}
.wl-detail__priceblk { margin-bottom: 16px; }
.wl-detail__row1 {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 12px;
}
.wl-detail__px {
  font-size: 34px;
  font-weight: 800;
  color: var(--wl-on-surface);
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}
.wl-detail__pct {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}
.wl-detail__pct.is-up { color: var(--wl-rise); }
.wl-detail__pct.is-down { color: var(--wl-fall); }
.wl-detail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  font-size: 13px;
  color: var(--wl-on-variant);
}
.wl-detail__tag {
  background: var(--wl-surface-low);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
}

/* 行情统计网格 */
.wl-detail__stats {
  margin-bottom: 16px;
  background: var(--wl-surface-low);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
  border-radius: 8px;
  overflow: hidden;
}
.wl-detail__stat-row {
  display: flex;
  box-shadow: 0 1px 0 var(--wl-ghost);
}
.wl-detail__stat-row:last-child { box-shadow: none; }
.wl-detail__stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  box-shadow: 1px 0 0 var(--wl-ghost);
}
.wl-detail__stat:last-child { box-shadow: none; }
.wl-detail__stat-l {
  font-size: 11px;
  color: var(--wl-outline);
  font-weight: 500;
}
.wl-detail__stat-v {
  font-size: 13px;
  color: var(--wl-on-surface);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}
.wl-detail__chart {
  border-radius: 8px;
  overflow: hidden;
}

/* K 线卡片适配浅色详情页 */
.wl-detail__chart :deep(.kline-wrap) {
  background: var(--wl-surface-lowest);
  box-shadow: inset 0 0 0 1px var(--wl-ghost);
}
</style>
