<template>
  <div class="wls">
    <header class="wls-bar">
      <button type="button" class="wls-ico-btn" aria-label="返回" @click="$router.back()">
        <svg class="wls-ico wls-ico--pri" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z"/>
        </svg>
      </button>
      <h1 class="wls-bar__title">策略全域配置</h1>
      <div class="wls-bar__actions">
        <button type="button" class="wls-ico-btn" aria-label="设置总览" @click="$router.push('/settings')">
          <svg class="wls-ico" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 0 0 .12-.61l-1.92-3.32a.488.488 0 0 0-.59-.22l-2.39.96c-.52-.4-1.08-.73-1.69-.98l-.36-2.54A.484.484 0 0 0 14.26 2h-3.84c-.24 0-.43.17-.47.4l-.36 2.54c-.61.25-1.17.59-1.69.98l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.07.64-.07.94s.02.63.06.94l-2.03 1.58a.49.49 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.52.4 1.08.73 1.69.98l.36 2.54c.05.23.24.4.47.4h3.84c.24 0 .44-.17.47-.4l.36-2.54c.61-.25 1.17-.59 1.69-.98l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"
            />
          </svg>
        </button>
        <button type="button" class="wls-ico-btn" aria-label="更多" @click="showHelp">
          <svg class="wls-ico" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="currentColor" d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/>
          </svg>
        </button>
      </div>
    </header>

    <main class="wls-main">
      <!-- 适用范围 -->
      <section class="wls-sec">
        <div class="wls-sec__head">
          <h2 class="wls-sec__t">适用范围</h2>
          <span class="wls-sec__en">Applicable Scope</span>
        </div>
        <button type="button" class="wls-scope" @click="goWatchlist">
          <div class="wls-scope__l">
            <div class="wls-scope__ico" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z"/></svg>
            </div>
            <div class="wls-scope__txt">
              <p class="wls-scope__t">我的自选股</p>
              <p class="wls-scope__s">{{ scopeSubtitle }}</p>
            </div>
          </div>
          <svg class="wls-scope__chev" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path fill="currentColor" d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
          </svg>
        </button>
      </section>

      <!-- 执行与安全 -->
      <section class="wls-sec">
        <div class="wls-sec__head">
          <h2 class="wls-sec__t">执行与安全</h2>
          <span class="wls-sec__en">Execution &amp; Safety</span>
        </div>
        <div class="wls-shell">
          <div class="wls-exec">
            <div class="wls-exec__field">
              <label class="wls-exec__lbl">执行频率</label>
              <div class="wls-seg wls-seg--pill" role="tablist" aria-label="执行频率">
                <button
                  type="button"
                  role="tab"
                  class="wls-seg__pill"
                  :class="{ on: form.execFrequency === 'once' }"
                  @click="form.execFrequency = 'once'"
                >
                  单次
                </button>
                <button
                  type="button"
                  role="tab"
                  class="wls-seg__pill"
                  :class="{ on: form.execFrequency === 'per_bar' }"
                  @click="form.execFrequency = 'per_bar'"
                >
                  每根K线 (1m)
                </button>
                <button
                  type="button"
                  role="tab"
                  class="wls-seg__pill"
                  :class="{ on: form.execFrequency === 'loop' }"
                  @click="form.execFrequency = 'loop'"
                >
                  循环
                </button>
              </div>
            </div>
            <div class="wls-exec__row">
              <label class="wls-exec__lbl">最大执行限制</label>
              <input
                v-model.number="form.maxExecCount"
                class="wls-exec__num"
                type="number"
                min="1"
                max="9999"
                step="1"
              />
            </div>
            <div class="wls-fuse">
              <svg class="wls-fuse__ico" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path fill="currentColor" d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/>
              </svg>
              <p class="wls-fuse__txt">
                安全熔断机制已启用：当单日亏损超过 <strong>{{ fusePctStr }}</strong> 时，系统将自动挂起所有执行引擎。
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- 风控边界 -->
      <section class="wls-sec">
        <div class="wls-sec__head wls-sec__head--risk">
          <div class="wls-sec__risk-l">
            <h2 class="wls-sec__t">风控边界</h2>
            <span class="wls-host-pill">智能托管</span>
          </div>
          <span class="wls-sec__en">Risk Control</span>
        </div>
        <div class="wls-risk-card">
          <div class="wls-risk-block">
            <div class="wls-risk-head">
              <span class="wls-risk-head__lbl">止盈设置</span>
              <div class="wls-risk-head__meta">
                <span class="wls-risk-head__pct tabular wls-risk-head__pct--tp">{{ tpStr }}</span>
                <span class="wls-risk-chip wls-risk-chip--tp tabular">{{ tpEstStr }}</span>
              </div>
            </div>
            <input
              v-model.number="form.takeProfitPct"
              class="wls-range wls-range--tv"
              type="range"
              min="1"
              max="50"
              step="0.5"
            />
          </div>
          <div class="wls-risk-block">
            <div class="wls-risk-head">
              <span class="wls-risk-head__lbl">止损设置</span>
              <div class="wls-risk-head__meta">
                <span class="wls-risk-head__pct tabular wls-risk-head__pct--sl">{{ slStr }}</span>
                <span class="wls-risk-chip wls-risk-chip--sl tabular">{{ slEstStr }}</span>
              </div>
            </div>
            <input
              v-model.number="form.stopLossSliderPct"
              class="wls-range wls-range--tv"
              type="range"
              min="1"
              max="20"
              step="0.5"
            />
          </div>
        </div>
      </section>

      <!-- 策略触发逻辑 -->
      <section class="wls-sec">
        <div class="wls-sec__head">
          <h2 class="wls-sec__t">策略触发逻辑</h2>
          <span class="wls-sec__en">Strategy Logic</span>
        </div>

        <div class="wls-engine">
          <div class="wls-engine__inner">
            <svg class="wls-engine__ico" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
              <path fill="currentColor" d="M15 9H9v6h6V9zm-2 4h-2v-2h2v2zM4 11c0 .55.45 1 1 1h2v2H5c-1.66 0-3-1.34-3-3s1.34-3 3-3h2v2H5c-.55 0-1 .45-1 1zm16 0c0-.55-.45-1-1-1h-2V8h2c1.66 0 3 1.34 3 3s-1.34 3-3 3h-2v-2h2c.55 0 1-.45 1-1zM11 5H9V3c0-1.66 1.34-3 3-3s3 1.34 3 3v2h-2V5c0-.55-.45-1-1-1s-1 .45-1 1v2h2v2zm6 10h2v2c0 1.66-1.34 3-3 3s-3-1.34-3-3v-2h2v2c0 .55.45 1 1 1s1-.45 1-1v-2z"/>
            </svg>
            <div>
              <p class="wls-engine__k">核心引擎</p>
              <p class="wls-engine__v">
                {{ engineEngineLine }}
              </p>
            </div>
          </div>
        </div>

        <div class="wls-scanner">
          <div class="wls-scanner__head">
            <h3 class="wls-scanner__ttl">
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14zM9 11H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z"/></svg>
              扫描参数配置
            </h3>
          </div>
          <div class="wls-scanner__body">
            <div class="wls-cond-panel">
              <div class="wls-cond-section">
                <div class="wls-cond-type-row">
                  <div class="wls-cond-type-lbl">条件</div>
                  <div class="wls-cond-type-opts">
                    <button
                      v-for="t in condTypes"
                      :key="t.value"
                      type="button"
                      class="wls-cond-type-btn"
                      :class="{ on: form.scanCondIndicator === t.value }"
                      @click="switchCondType(t.value)"
                    >{{ t.label }}</button>
                  </div>
                </div>

                <!-- RSI -->
                <div v-if="form.scanCondIndicator === 'rsi'" class="wls-cond-body">
                  <div class="wls-cond-row">
                    <select v-model.number="form.scanCondPeriod" class="wls-tv-select">
                      <option :value="6">6 周期</option>
                      <option :value="14">14 周期</option>
                      <option :value="21">21 周期</option>
                    </select>
                    <select v-model="form.scanCondOp" class="wls-tv-select">
                      <option value="gt">大于</option>
                      <option value="lt">小于</option>
                      <option value="cross_above">上穿</option>
                      <option value="cross_below">下穿</option>
                    </select>
                  </div>
                  <div class="wls-cond-row">
                    <select class="wls-tv-select wls-tv-select--narrow" disabled><option>值</option></select>
                    <input v-model.number="form.scanCondValue" class="wls-tv-input" type="number" min="0" max="100" step="1" />
                  </div>
                  <div class="wls-cond-preview">
                    <span class="wls-cond-preview__a">{{ condPreviewLeft }}</span>
                    <span class="wls-cond-preview__op">{{ condPreviewOp }}</span>
                    <span class="wls-cond-preview__b">{{ condPreviewRight }}</span>
                    <span v-if="condRegionTag" class="wls-cond-preview__tag">{{ condRegionTag }}</span>
                  </div>
                </div>

                <!-- 均线 MA -->
                <div v-else-if="form.scanCondIndicator === 'ma'" class="wls-cond-body">
                  <div class="wls-cond-row wls-cond-row--3">
                    <select v-model.number="form.scanMaFast" class="wls-tv-select">
                      <option :value="5">MA5</option>
                      <option :value="10">MA10</option>
                      <option :value="20">MA20</option>
                      <option :value="60">MA60</option>
                    </select>
                    <select v-model="form.scanMaMode" class="wls-tv-select">
                      <option value="golden_cross">金叉上穿</option>
                      <option value="death_cross">死叉下穿</option>
                      <option value="above">快线在慢线上</option>
                      <option value="below">快线在慢线下</option>
                    </select>
                    <select v-model.number="form.scanMaSlow" class="wls-tv-select">
                      <option :value="20">MA20</option>
                      <option :value="10">MA10</option>
                      <option :value="60">MA60</option>
                      <option :value="120">MA120</option>
                    </select>
                  </div>
                  <div class="wls-cond-preview">
                    <span class="wls-cond-preview__a">{{ condMaPreview }}</span>
                    <span class="wls-cond-preview__op">{{ maModeLabel }}</span>
                    <span class="wls-cond-preview__tag">{{ condMaTag }}</span>
                  </div>
                </div>

                <!-- MACD -->
                <div v-else-if="form.scanCondIndicator === 'macd'" class="wls-cond-body">
                  <div class="wls-cond-row">
                    <select v-model="form.scanMacdMode" class="wls-tv-select wls-tv-select--full">
                      <option value="hist_turn">柱状图由负转正</option>
                      <option value="hist_bear">柱状图由正转负</option>
                      <option value="dif_cross_above">DIF 上穿 DEA</option>
                      <option value="dif_cross_below">DIF 下穿 DEA</option>
                    </select>
                  </div>
                  <div class="wls-cond-preview">
                    <span class="wls-cond-preview__a">{{ condMacdPreview }}</span>
                    <span class="wls-cond-preview__tag">{{ condMacdTag }}</span>
                  </div>
                </div>

                <!-- 布林带 BB -->
                <div v-else-if="form.scanCondIndicator === 'bb'" class="wls-cond-body">
                  <div class="wls-cond-row">
                    <select v-model.number="form.scanBbPeriod" class="wls-tv-select">
                      <option :value="20">20 日周期</option>
                      <option :value="10">10 日周期</option>
                      <option :value="30">30 日周期</option>
                    </select>
                    <select v-model.number="form.scanBbStd" class="wls-tv-select">
                      <option :value="2">标准差 2</option>
                      <option :value="1">标准差 1</option>
                      <option :value="3">标准差 3</option>
                    </select>
                  </div>
                  <div class="wls-cond-row">
                    <select v-model="form.scanBbMode" class="wls-tv-select wls-tv-select--full">
                      <option value="near_upper">贴近上轨</option>
                      <option value="near_lower">贴近下轨</option>
                      <option value="break_upper">突破上轨</option>
                      <option value="break_lower">跌破下轨</option>
                      <option value="squeeze">布林收口</option>
                    </select>
                  </div>
                  <div class="wls-cond-preview">
                    <span class="wls-cond-preview__a">{{ condBbPreview }}</span>
                    <span class="wls-cond-preview__tag">{{ condBbTag }}</span>
                  </div>
                </div>

                <!-- 成交量 / 价格（保留） -->
                <div v-else-if="form.scanCondIndicator === 'vol' || form.scanCondIndicator === 'price'" class="wls-cond-body">
                  <div class="wls-cond-row">
                    <select v-model="form.scanCondOp" class="wls-tv-select">
                      <option value="gt">大于</option>
                      <option value="lt">小于</option>
                      <option value="cross_above">上穿</option>
                      <option value="cross_below">下穿</option>
                    </select>
                    <input v-model.number="form.scanCondValue" class="wls-tv-input" type="number" min="0" step="1" />
                  </div>
                  <div class="wls-cond-preview">
                    <span class="wls-cond-preview__a">{{ condPreviewLeft }}</span>
                    <span class="wls-cond-preview__op">{{ condPreviewOp }}</span>
                    <span class="wls-cond-preview__b">{{ condPreviewRight }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="wls-cond-grid wls-cond-grid--period">
              <span class="wls-cond-grid__lbl">周期</span>
              <div class="wls-cond-grid__cell">
                <select v-model="form.scanBarTf" class="wls-tv-select wls-tv-select--full">
                  <option value="1d">1天</option>
                  <option value="1w">1周</option>
                  <option value="60m">60 分钟</option>
                </select>
              </div>
            </div>

            <div class="wls-cond-grid wls-cond-grid--trigger">
              <span class="wls-cond-grid__lbl">触发</span>
              <div class="wls-cond-grid__cell wls-cond-triggers">
                <button
                  type="button"
                  class="wls-trig"
                  :class="{ on: form.execFrequency === 'per_bar' }"
                  :disabled="form.execFrequency === 'loop'"
                  @click="form.execFrequency = 'per_bar'"
                >
                  <div class="wls-trig__l">
                    <div class="wls-trig__ico" aria-hidden="true">
                      <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.56 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.12.69 4.2 1.78L13 11h7V4l-2.35 2.35z"/></svg>
                    </div>
                    <div>
                      <p class="wls-trig__t">每根K线一次</p>
                      <p class="wls-trig__d">当满足条件时，每分钟触发一次</p>
                    </div>
                  </div>
                  <svg v-if="form.execFrequency === 'per_bar'" class="wls-trig__chk" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                    <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                  </svg>
                </button>
                <button
                  type="button"
                  class="wls-trig"
                  :class="{ on: form.execFrequency === 'once' }"
                  :disabled="form.execFrequency === 'loop'"
                  @click="form.execFrequency = 'once'"
                >
                  <div class="wls-trig__l">
                    <div class="wls-trig__ico wls-trig__ico--muted" aria-hidden="true">
                      <svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                    </div>
                    <div>
                      <p class="wls-trig__t">仅一次</p>
                      <p class="wls-trig__d">满足条件时仅触发一次</p>
                    </div>
                  </div>
                  <svg v-if="form.execFrequency === 'once'" class="wls-trig__chk" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
                    <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
                  </svg>
                </button>
                <p v-if="form.execFrequency === 'loop'" class="wls-trig-loop-hint">当前为「循环」模式，触发细分以上方执行频率为准。</p>
              </div>
            </div>

            <div class="wls-cond-grid">
              <span class="wls-cond-grid__lbl">到期时间</span>
              <div class="wls-cond-grid__cell">
                <div class="wls-dt-wrap">
                  <input v-model="form.scanExpiresAt" class="wls-tv-input wls-tv-input--dt" type="datetime-local" />
                </div>
              </div>
            </div>

            <div class="wls-strat-summary">
              <span class="wls-strat-summary__sel">已选 {{ form.watchlistStrategyIds.length }} 项策略</span>
              <button type="button" class="wls-strat-summary__clear" @click="clearAllStrategies">清空</button>
            </div>
            <div class="wls-ta-strat-grid" role="group" aria-label="自选扫描策略">
              <label v-for="s in strategyOptions" :key="s.id" class="wls-ta-strat-row">
                <input
                  type="checkbox"
                  class="wls-ta-strat-cb"
                  :checked="strategyIdsSet.has(s.id)"
                  @change="onStrategyToggle(s.id, $event.target.checked)"
                />
                <span class="wls-ta-strat-row__txt">{{ s.name }}</span>
              </label>
            </div>
            <p v-if="selectedStrategyDesc" class="wls-ta-desc">{{ selectedStrategyDesc }}</p>
          </div>
        </div>

        <button
          type="button"
          class="wls-scan-outline"
          :disabled="scanLoading || !strategyOptions.length || !form.watchlistStrategyIds.length"
          @click="runStrategyScan"
        >
          <span v-if="scanLoading" class="wls-scan-outline__spin" aria-hidden="true" />
          <svg v-else viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
          {{ scanLoading ? '扫描中…' : '立即扫描自选股标的' }}
        </button>
        <p v-if="scanError" class="wls-ta-err">{{ scanError }}</p>
        <ul v-if="scanItems.length" class="wls-ta-ul">
          <li v-for="it in scanItems" :key="it.code" class="wls-ta-item">
            <div class="wls-ta-item__sym">
              <span class="tabular">{{ it.code }}</span>
              <span class="wls-ta-item__nm">{{ it.name }}</span>
            </div>
            <div v-if="it.hits && it.hits.length" class="wls-ta-hits">
              <div v-for="h in it.hits" :key="h.strategy_id" class="wls-ta-hit">
                <span class="wls-ta-hit__tag">{{ h.strategy_name || h.strategy_id }}</span>
                <div class="wls-ta-item__sig" :class="signalToneClass(h.signal)">
                  <span class="wls-ta-item__lbl">{{ h.label_zh || '—' }}</span>
                  <span class="wls-ta-item__det">{{ h.detail || h.error || '' }}</span>
                </div>
              </div>
            </div>
            <div v-else class="wls-ta-item__sig" :class="signalToneClass(it.signal)">
              <span class="wls-ta-item__lbl">{{ it.label_zh || '—' }}</span>
              <span class="wls-ta-item__det">{{ it.detail || it.error || '' }}</span>
            </div>
          </li>
        </ul>
      </section>

      <p v-if="savedHint" class="wls-toast" role="status">{{ savedHint }}</p>
    </main>

    <nav class="wls-dock wls-dock--save">
      <div class="wls-dock__inner wls-dock__inner--single">
        <button type="button" class="wls-btn wls-btn--save-full" @click="save">
          <svg class="wls-btn__ico" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/></svg>
          保存配置
        </button>
      </div>
    </nav>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { watchlist, watchlistStrategy, WATCHLIST_STRATEGY_FALLBACK } from '@/api/strategy.js'
import {
  loadWatchlistRiskSettings,
  saveWatchlistRiskSettings,
  defaultWatchlistRiskSettings,
} from '@/config/watchlistSettingsStorage.js'

const router = useRouter()
const form = reactive(defaultWatchlistRiskSettings())
const savedHint = ref('')

/** 与稿面示例一致：用于展示预估盈亏的虚拟本金（非真实账户） */
const NOTIONAL_BASE = 4520

const watchlistCount = ref(0)
const scopeLoading = ref(false)

const strategyOptions = ref([])
const engineInfo = ref(null)
const scanLoading = ref(false)
const scanError = ref('')
const scanItems = ref([])

const tpStr = computed(() => `${Number(form.takeProfitPct).toFixed(1)}%`)
const slStr = computed(() => `${Number(form.stopLossSliderPct).toFixed(1)}%`)

const tpEstStr = computed(() => {
  const v = (NOTIONAL_BASE * Number(form.takeProfitPct)) / 100
  return `+$${v.toFixed(2)}`
})
const slEstStr = computed(() => {
  const v = (NOTIONAL_BASE * Number(form.stopLossSliderPct)) / 100
  return `-$${v.toFixed(2)}`
})

const fusePctStr = computed(() => `${Number(form.dayDropPct).toFixed(1)}%`)

const scopeSubtitle = computed(() => {
  if (scopeLoading.value) return '加载自选数量…'
  const n = watchlistCount.value
  return `${n} 只标的 · 已同步`
})

const engineEngineLine = computed(() => {
  const talibOn = engineInfo.value?.available
  const core = 'pandas / numpy 计算管线'
  const ext = talibOn ? '，已集成 TA-Lib 高性能库' : '；可选安装 TA-Lib 原生库提升性能'
  return `${core}${ext}`
})

/** 条件类型切换按钮 */
const condTypes = [
  { value: 'rsi', label: 'RSI' },
  { value: 'ma', label: '均线' },
  { value: 'macd', label: 'MACD' },
  { value: 'bb', label: '布林带' },
  { value: 'vol', label: '成交量' },
  { value: 'price', label: '价格' },
]

function switchCondType(type) {
  form.scanCondIndicator = type
}

const COND_OP_SYM = { gt: '>', lt: '<', cross_above: '上穿', cross_below: '下穿' }
const COND_IND_LABEL = { rsi: 'RSI', vol: '成交量', price: '价格', ma: '均线', macd: 'MACD', bb: '布林带' }
const MA_MODE_LABEL = { golden_cross: '金叉', death_cross: '死叉', above: '快线 > 慢线', below: '快线 < 慢线' }
const MACD_TAG = {
  hist_turn: 'MACD 柱由负转正（多头）',
  hist_bear: 'MACD 柱由正转负（空头）',
  dif_cross_above: 'DIF 上穿 DEA（金叉）',
  dif_cross_below: 'DIF 下穿 DEA（死叉）',
}
const BB_TAG = {
  near_upper: '贴近上轨（超买）',
  near_lower: '贴近下轨（超卖）',
  break_upper: '突破上轨',
  break_lower: '跌破下轨',
  squeeze: '布林收口（蓄力）',
}

/** RSI 预览 */
const condPreviewLeft = computed(() => {
  const ind = COND_IND_LABEL[form.scanCondIndicator] || form.scanCondIndicator
  return `${ind} (${form.scanCondPeriod})`
})
const condPreviewOp = computed(() => COND_OP_SYM[form.scanCondOp] || form.scanCondOp)
const condPreviewRight = computed(() => String(form.scanCondValue ?? ''))
const condRegionTag = computed(() => {
  if (form.scanCondIndicator !== 'rsi') return ''
  const v = Number(form.scanCondValue)
  const op = form.scanCondOp
  if (op === 'gt' && v >= 70) return '超买区域 (Overbought)'
  if (op === 'lt' && v <= 30) return '超卖区域 (Oversold)'
  return ''
})

/** 均线预览 */
const condMaPreview = computed(() => `MA${form.scanMaFast} vs MA${form.scanMaSlow}`)
const maModeLabel = computed(() => MA_MODE_LABEL[form.scanMaMode] || form.scanMaMode)
const condMaTag = computed(() => {
  const map = { golden_cross: '金叉触发', death_cross: '死叉触发', above: '多头排列', below: '空头排列' }
  return map[form.scanMaMode] || ''
})
const condMacdPreview = computed(() => 'MACD (12,26,9)')
const condMacdTag = computed(() => MACD_TAG[form.scanMacdMode] || '')

/** 布林带预览 */
const condBbPreview = computed(() => `BB(${form.scanBbPeriod},${form.scanBbStd})`)
const condBbTag = computed(() => BB_TAG[form.scanBbMode] || '')

const strategyIdsSet = computed(() => new Set(form.watchlistStrategyIds))

const selectedStrategyDesc = computed(() => {
  const sel = strategyIdsSet.value
  const parts = strategyOptions.value
    .filter((x) => sel.has(x.id))
    .map((x) => `【${x.name}】${x.description || ''}`)
  return parts.join(' ')
})

/** 后端 catalog 失败时为 true，使用本地 FALLBACK */
const catalogOffline = ref(false)

/** 与上方「立即扫描」及下方告警一一对应 */
const STRATEGY_ALERT_ROWS = [
  ['rsi_extreme', 'alertRSI'],
  ['ma_cross', 'alertMA'],
  ['breakout_20', 'alertBreakRange'],
  ['macd_turn', 'alertMACD'],
  ['bollinger_position', 'alertBollinger'],
]

function sortStrategyIdsByCatalog() {
  const order = strategyOptions.value.map((s) => s.id)
  const set = new Set(form.watchlistStrategyIds)
  form.watchlistStrategyIds = order.filter((id) => set.has(id))
}

/** 上方勾选与下方开关：以 watchlistStrategyIds 为准同步告警布尔值 */
function syncAlertsFromStrategies() {
  const set = strategyIdsSet.value
  for (const [sid, key] of STRATEGY_ALERT_ROWS) {
    form[key] = set.has(sid)
  }
}

function clearAllStrategies() {
  form.watchlistStrategyIds = []
  syncAlertsFromStrategies()
}

function onStrategyToggle(sid, checked) {
  if (checked) {
    if (!form.watchlistStrategyIds.includes(sid)) {
      form.watchlistStrategyIds.push(sid)
    }
  } else {
    const i = form.watchlistStrategyIds.indexOf(sid)
    if (i >= 0) form.watchlistStrategyIds.splice(i, 1)
  }
  sortStrategyIdsByCatalog()
  syncAlertsFromStrategies()
}

function toggleStrategyAlert(sid) {
  const row = STRATEGY_ALERT_ROWS.find(([s]) => s === sid)
  if (!row) return
  const key = row[1]
  form[key] = !form[key]
  if (form[key]) {
    if (!form.watchlistStrategyIds.includes(sid)) {
      form.watchlistStrategyIds.push(sid)
      sortStrategyIdsByCatalog()
    }
  } else {
    const i = form.watchlistStrategyIds.indexOf(sid)
    if (i >= 0) form.watchlistStrategyIds.splice(i, 1)
  }
}

function signalToneClass(sig) {
  const s = String(sig || '')
  if (/oversold|golden|break_high|macd_bull|near_lower|bull_align/.test(s)) return 'is-bull'
  if (/overbought|death|break_low|macd_bear|near_upper|bear_align/.test(s)) return 'is-bear'
  if (s === 'neutral' || s === 'inside' || s === 'mid_band') return 'is-mid'
  return ''
}

async function loadStrategyCatalog() {
  catalogOffline.value = false
  try {
    const d = await watchlistStrategy.catalog()
    strategyOptions.value = Array.isArray(d.strategies) ? d.strategies : []
    engineInfo.value = d.engine || null
    if (!strategyOptions.value.length) {
      strategyOptions.value = [...WATCHLIST_STRATEGY_FALLBACK]
      catalogOffline.value = true
    }
  } catch (e) {
    watchlistStrategy.invalidateCatalog()
    strategyOptions.value = [...WATCHLIST_STRATEGY_FALLBACK]
    engineInfo.value = { available: false, library: 'offline' }
    catalogOffline.value = true
    const msg = e?.message || '策略列表加载失败'
    savedHint.value = `${msg} 已使用本地列表；扫描自选仍需后端运行。`
    setTimeout(() => { savedHint.value = '' }, 5000)
  }
  ensureValidStrategyIds()
}

async function runStrategyScan() {
  scanError.value = ''
  scanItems.value = []
  scanLoading.value = true
  try {
    const ids = [...form.watchlistStrategyIds]
    if (!ids.length) {
      scanError.value = '请至少选择一项策略'
      return
    }
    const d = await watchlistStrategy.run(ids)
    scanItems.value = Array.isArray(d.items) ? d.items : []
    if (d.count === 0 && d.hint) {
      savedHint.value = d.hint
      setTimeout(() => { savedHint.value = '' }, 2600)
    }
  } catch (e) {
    scanError.value = e?.message || '扫描失败'
  } finally {
    scanLoading.value = false
  }
}

function clamp(n, lo, hi) {
  const x = Number(n)
  if (!Number.isFinite(x)) return lo
  return Math.min(hi, Math.max(lo, x))
}

function ensureValidStrategyIds() {
  const valid = new Set(strategyOptions.value.map((s) => s.id))
  let next = form.watchlistStrategyIds.filter((id) => valid.has(id))
  if (!next.length) {
    next = [strategyOptions.value[0]?.id || 'rsi_extreme']
  }
  form.watchlistStrategyIds = next
  sortStrategyIdsByCatalog()
  syncAlertsFromStrategies()
}

function load() {
  Object.assign(form, loadWatchlistRiskSettings())
  if (!Array.isArray(form.watchlistStrategyIds)) {
    form.watchlistStrategyIds = form.watchlistStrategyId
      ? [form.watchlistStrategyId]
      : ['rsi_extreme']
  }
  if (form.alertMACD === undefined) form.alertMACD = false
  if (form.alertBollinger === undefined) form.alertBollinger = false
  const d = defaultWatchlistRiskSettings()
  if (!form.scanCondIndicator) form.scanCondIndicator = d.scanCondIndicator
  if (form.scanCondPeriod == null) form.scanCondPeriod = d.scanCondPeriod
  if (!form.scanCondOp) form.scanCondOp = d.scanCondOp
  if (form.scanCondValue == null) form.scanCondValue = d.scanCondValue
  if (form.scanMaFast == null) form.scanMaFast = d.scanMaFast
  if (form.scanMaSlow == null) form.scanMaSlow = d.scanMaSlow
  if (!form.scanMaMode) form.scanMaMode = d.scanMaMode
  if (!form.scanMacdMode) form.scanMacdMode = d.scanMacdMode
  if (form.scanBbPeriod == null) form.scanBbPeriod = d.scanBbPeriod
  if (form.scanBbStd == null) form.scanBbStd = d.scanBbStd
  if (!form.scanBbMode) form.scanBbMode = d.scanBbMode
  if (!form.scanBarTf) form.scanBarTf = d.scanBarTf
  if (form.scanExpiresAt == null) form.scanExpiresAt = d.scanExpiresAt
}

function normalize() {
  form.maxExecCount = Math.round(clamp(form.maxExecCount, 1, 9999))
  form.takeProfitPct = clamp(form.takeProfitPct, 1, 50)
  form.stopLossSliderPct = clamp(form.stopLossSliderPct, 1, 20)
  form.stopLossPct = form.stopLossSliderPct
  form.dayDropPct = clamp(form.dayDropPct, 0.5, 25)
  form.scanCondPeriod = Math.round(clamp(form.scanCondPeriod, 2, 99))
  form.scanCondValue = clamp(form.scanCondValue, 0, 10000)
  form.scanMaFast = Math.round(clamp(form.scanMaFast, 1, 500))
  form.scanMaSlow = Math.round(clamp(form.scanMaSlow, 1, 500))
  form.scanBbPeriod = Math.round(clamp(form.scanBbPeriod, 2, 200))
  form.scanBbStd = Math.max(0.5, Math.min(5, Number(form.scanBbStd) || 2))
}

function save() {
  normalize()
  try {
    saveWatchlistRiskSettings({ ...form })
    savedHint.value = '已保存到本机'
    setTimeout(() => { savedHint.value = '' }, 2200)
  } catch {
    savedHint.value = '保存失败'
  }
}

function showHelp() {
  savedHint.value = '参数保存在浏览器本地；实际下单与推送需后续接入交易与通知服务。'
  setTimeout(() => { savedHint.value = '' }, 3200)
}

function goWatchlist() {
  router.push('/watchlist')
}

async function loadWatchlistCount() {
  scopeLoading.value = true
  try {
    const list = await watchlist.list()
    watchlistCount.value = Array.isArray(list) ? list.length : 0
  } catch {
    watchlistCount.value = 0
  } finally {
    scopeLoading.value = false
  }
}

onMounted(() => {
  load()
  strategyOptions.value = [...WATCHLIST_STRATEGY_FALLBACK]
  ensureValidStrategyIds()
  loadStrategyCatalog()
  loadWatchlistCount()
})
</script>

<style scoped>
/* stitch + DESIGN.md: light surfaces, primary gradient CTA, ambient shadow */
.wls {
  --w-surface: #f9f9fe;
  --w-surface-low: #f3f3f8;
  --w-surface-lowest: #ffffff;
  --w-surface-container: #ededf2;
  --w-surface-high: #e8e8ed;
  --w-surface-highest: #e2e2e7;
  --w-on-surface: #1a1c1f;
  --w-on-variant: #414755;
  --w-outline-variant: rgba(193, 198, 215, 0.45);
  --w-primary: #007aff;
  --w-primary-ctr: #0052ff;
  --w-primary-fixed: #d8e2ff;
  --w-error: #ba1a1a;
  --w-tertiary: #bc000a;
  --w-secondary: #006c4a;
  --w-secondary-container: #63f9bb;
  --w-up: #006c4a;
  --w-shadow: 0 8px 24px rgba(26, 28, 31, 0.06);
  --w-shadow-soft: 0 8px 24px rgba(26, 28, 31, 0.04);

  min-height: 100vh;
  min-height: 100dvh;
  background: var(--w-surface);
  color: var(--w-on-surface);
  padding-bottom: calc(env(safe-area-inset-bottom) + 112px);
  font-family: Inter, var(--font, system-ui), sans-serif;
}

.wls-bar {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: calc(56px + env(safe-area-inset-top, 0));
  padding: env(safe-area-inset-top, 0) 16px 0;
  background: rgba(249, 249, 254, 0.82);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: var(--w-shadow);
}
.wls-bar__title {
  flex: 1;
  text-align: center;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 1.0625rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin: 0;
  color: var(--w-on-surface);
}
.wls-bar__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}
.wls-ico-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 12px;
  background: transparent;
  color: var(--w-on-surface);
  cursor: pointer;
}
.wls-ico-btn:active {
  background: var(--w-surface-low);
}
.wls-ico {
  width: 22px;
  height: 22px;
  display: block;
  opacity: 0.9;
}
.wls-ico--pri {
  color: var(--w-primary-ctr);
  opacity: 1;
}

.wls-main {
  max-width: 560px;
  margin: 0 auto;
  padding: 8px 20px 24px;
}
.wls-hero {
  margin-bottom: 28px;
  margin-top: 8px;
}
.wls-hero__t {
  font-family: Manrope, var(--font), sans-serif;
  font-size: clamp(1.75rem, 6vw, 2.25rem);
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin: 0 0 8px;
  color: var(--w-on-surface);
}
.wls-hero__s {
  margin: 0;
  font-size: 14px;
  color: var(--w-on-variant);
  line-height: 1.45;
}

.wls-card {
  background: var(--w-surface-lowest);
  border-radius: 16px;
  padding: 22px 20px;
  margin-bottom: 20px;
  box-shadow: var(--w-shadow-soft);
}
.wls-card__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 20px;
}
.wls-card__head--simple {
  gap: 10px;
  margin-bottom: 18px;
}
.wls-card__h-l {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wls-card__h {
  font-family: Manrope, var(--font), sans-serif;
  font-size: 1.125rem;
  font-weight: 800;
  margin: 0;
  letter-spacing: -0.02em;
}
.wls-badge-ico {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--w-primary);
}
.wls-badge-ico--fill {
  color: var(--w-primary-ctr);
}

.wls-seg {
  display: flex;
  padding: 4px;
  border-radius: 999px;
  background: var(--w-surface-container);
  gap: 2px;
}
.wls-seg__btn {
  border: none;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--w-on-variant);
  background: transparent;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}
.wls-seg__btn.on {
  background: var(--w-surface-lowest);
  color: var(--w-on-surface);
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.08);
}

.wls-grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 380px) {
  .wls-grid2 {
    grid-template-columns: 1fr;
  }
}
.wls-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wls-field--full {
  margin-top: 18px;
}
.wls-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--w-on-variant);
  padding-left: 2px;
}
.wls-input-wrap {
  position: relative;
}
.wls-input {
  width: 100%;
  padding: 12px 36px 12px 14px;
  font-size: 15px;
  font-weight: 600;
  color: var(--w-on-surface);
  background: var(--w-surface-low);
  border: 1px solid transparent;
  border-radius: 12px;
  outline: none;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.wls-input:focus {
  background: var(--w-surface-lowest);
  border-color: rgba(195, 197, 217, 0.45);
}
.wls-input--block {
  padding-right: 14px;
}
.wls-input-suf {
  position: absolute;
  right: 14px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 14px;
  font-weight: 800;
  color: var(--w-on-variant);
  pointer-events: none;
}
.wls-input::-webkit-outer-spin-button,
.wls-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.wls-input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}

.wls-select {
  width: 100%;
  padding: 12px 14px;
  font-size: 14px;
  font-weight: 600;
  color: var(--w-on-surface);
  background: var(--w-surface-low);
  border: 1px solid transparent;
  border-radius: 12px;
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}
.wls-select:focus {
  background: var(--w-surface-lowest);
  border-color: rgba(195, 197, 217, 0.45);
}
.wls-select--block {
  width: 100%;
}
.wls-field--tight {
  margin-bottom: 4px;
}
.wls-ta-lead {
  font-size: 12px;
  line-height: 1.55;
  color: var(--w-on-variant);
  margin: 0 0 10px;
}
.wls-ta-link-hint {
  font-size: 11px;
  line-height: 1.45;
  color: var(--w-on-variant);
  opacity: 0.9;
  margin: 0 0 14px;
}
.wls-ta-lead code {
  font-size: 11px;
  background: var(--w-surface-container);
  padding: 1px 6px;
  border-radius: 6px;
}
.wls-ta-tip {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  opacity: 0.9;
}
.wls-ta-desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--w-on-variant);
  line-height: 1.45;
}
.wls-strat-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--w-surface-low);
  border-radius: 10px;
  margin-bottom: 8px;
}
.wls-strat-summary__sel {
  font-size: 13px;
  font-weight: 700;
  color: var(--w-primary-ctr);
}
.wls-strat-summary__clear {
  border: none;
  background: none;
  font-size: 12px;
  font-weight: 600;
  color: var(--w-on-variant);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
}
.wls-strat-summary__clear:active {
  background: var(--w-surface-container);
}
.wls-ta-strat-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}
.wls-ta-strat-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--w-surface-low);
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: var(--w-on-surface);
}
.wls-ta-strat-row:active {
  background: var(--w-surface-container);
}
.wls-ta-strat-cb {
  margin-top: 2px;
  width: 18px;
  height: 18px;
  accent-color: var(--w-primary-ctr);
  flex-shrink: 0;
}
.wls-ta-strat-row__txt {
  flex: 1;
  line-height: 1.35;
}
.wls-ta-hits {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 6px;
}
.wls-ta-hit {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.wls-ta-hit__tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--w-primary);
  background: var(--w-primary-fixed);
  padding: 3px 8px;
  border-radius: 6px;
  align-self: flex-start;
}
.wls-ta-scan {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  width: 100%;
  margin-top: 12px;
  padding: 14px 16px;
  border: none;
  border-radius: 14px;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 14px;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, var(--w-primary) 0%, var(--w-primary-ctr) 100%);
  box-shadow: 0 8px 20px rgba(0, 82, 255, 0.22);
  cursor: pointer;
}
.wls-ta-scan:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.wls-ta-scan:active:not(:disabled) {
  transform: scale(0.99);
}
.wls-ta-scan__spin {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: wls-spin 0.7s linear infinite;
}
@keyframes wls-spin {
  to {
    transform: rotate(360deg);
  }
}
.wls-ta-err {
  margin: 12px 0 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--w-error);
}
.wls-ta-ul {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wls-ta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--w-surface-low);
}
.wls-ta-item__sym {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 13px;
  font-weight: 800;
  font-family: Manrope, var(--font), sans-serif;
}
.wls-ta-item__nm {
  font-size: 12px;
  font-weight: 600;
  color: var(--w-on-variant);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wls-ta-item__sig {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.wls-ta-item__lbl {
  font-size: 13px;
  font-weight: 800;
}
.wls-ta-item__det {
  font-size: 11px;
  color: var(--w-on-variant);
  line-height: 1.35;
}
.wls-ta-item__sig.is-bull .wls-ta-item__lbl {
  color: var(--w-up);
}
.wls-ta-item__sig.is-bear .wls-ta-item__lbl {
  color: var(--w-error);
}
.wls-ta-item__sig.is-mid .wls-ta-item__lbl {
  color: var(--w-on-variant);
}

.wls-freq {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 8px;
}
.wls-freq__btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 88px;
  padding: 12px 8px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: var(--w-surface-low);
  color: var(--w-on-surface);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}
.wls-freq__btn:active {
  transform: scale(0.98);
}
.wls-freq__btn.on {
  background: linear-gradient(135deg, var(--w-primary) 0%, var(--w-primary-ctr) 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(0, 82, 255, 0.22);
}
.wls-freq__sym {
  font-size: 22px;
  font-weight: 800;
  font-family: Manrope, var(--font), sans-serif;
  color: var(--w-on-variant);
  line-height: 1;
}
.wls-freq__btn.on .wls-freq__sym {
  color: #fff;
}
.wls-freq__ico {
  width: 26px;
  height: 26px;
  opacity: 0.65;
}
.wls-freq__btn.on .wls-freq__ico {
  opacity: 1;
  color: #fff;
}
.wls-freq__lbl {
  font-size: 12px;
  font-weight: 700;
  text-align: center;
  line-height: 1.25;
}

.wls-tpsl {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.wls-tpsl__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.wls-tpsl__ttl {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
}
.wls-pill {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--w-primary);
  background: var(--w-primary-fixed);
  padding: 4px 8px;
  border-radius: 6px;
}
.wls-slider-block {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wls-slider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.wls-slider-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
}
.wls-slider-ico {
  width: 22px;
  height: 22px;
}
.wls-slider-ico--up {
  color: var(--w-up);
}
.wls-slider-ico--down {
  color: var(--w-error);
}
.wls-slider-val {
  font-size: 14px;
  font-weight: 800;
}
.wls-slider-val--up {
  color: var(--w-up);
}
.wls-slider-val--down {
  color: var(--w-error);
}

.wls-range {
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: var(--w-surface-highest);
  appearance: none;
  cursor: pointer;
}
.wls-range::-webkit-slider-thumb {
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--w-primary);
  box-shadow: var(--w-shadow);
  cursor: pointer;
}
.wls-range::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: var(--w-primary);
  box-shadow: var(--w-shadow);
  cursor: pointer;
}

.wls-divider {
  height: 8px;
  margin: 8px 0 20px;
  background: var(--w-surface-container);
  border-radius: 4px;
  opacity: 0.65;
}

.wls-alerts__ttl {
  margin: 0 0 14px;
  font-size: 14px;
  font-weight: 800;
}
.wls-alert-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border-radius: 12px;
  background: var(--w-surface-low);
  margin-bottom: 10px;
}
.wls-alert-row:last-child {
  margin-bottom: 0;
}
.wls-alert-row__ico {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--w-surface-container);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--w-on-variant);
  flex-shrink: 0;
}
.wls-alert-row__txt {
  flex: 1;
  min-width: 0;
}
.wls-alert-row__t {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
}
.wls-alert-row__d {
  margin: 4px 0 0;
  font-size: 11px;
  font-weight: 600;
  color: var(--w-on-variant);
  line-height: 1.35;
}

.wls-switch {
  position: relative;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 12px;
  border: none;
  background: var(--w-surface-highest);
  cursor: pointer;
  transition: background 0.15s ease;
}
.wls-switch.on {
  background: var(--w-primary);
}
.wls-switch__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.15s ease;
}
.wls-switch.on .wls-switch__knob {
  transform: translateX(20px);
}

.wls-toast {
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--w-on-variant);
  margin: 16px 0 0;
}

.wls-dock {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom, 0));
  background: rgba(249, 249, 254, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  box-shadow: 0 -8px 24px rgba(26, 28, 31, 0.06);
  border-radius: 28px 28px 0 0;
}
.wls-dock__inner {
  max-width: 560px;
  margin: 0 auto;
  display: flex;
  gap: 12px;
}
.wls-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 999px;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 13px;
  font-weight: 800;
  border: none;
  cursor: pointer;
  transition: filter 0.15s ease, transform 0.12s ease;
}
.wls-btn:active {
  transform: scale(0.98);
}
.wls-btn__ico {
  width: 20px;
  height: 20px;
}
.wls-btn--ghost {
  background: transparent;
  color: var(--w-on-surface);
}
.wls-btn--ghost:active {
  background: var(--w-surface-low);
}
.wls-btn--pri {
  background: linear-gradient(135deg, var(--w-primary) 0%, var(--w-primary-ctr) 100%);
  color: #fff;
  box-shadow: 0 8px 20px rgba(0, 82, 255, 0.25);
}
.wls-btn--pri:active {
  filter: brightness(1.05);
}

.wls-dock--save {
  background: linear-gradient(to top, var(--w-surface) 55%, rgba(249, 249, 254, 0));
  border-radius: 0;
  box-shadow: none;
}
.wls-dock__inner--single {
  max-width: 560px;
}
.wls-btn--save-full {
  flex: none;
  width: 100%;
  border-radius: 16px;
  padding: 16px 20px;
  font-size: 15px;
  background: linear-gradient(135deg, var(--w-primary) 0%, var(--w-primary-ctr) 100%);
  color: #fff;
  box-shadow: 0 12px 32px rgba(0, 122, 255, 0.22);
}

/* —— stitch: 适用范围 / 执行与安全 / 风控 / 引擎 —— */
.wls-sec {
  margin-bottom: 28px;
}
.wls-sec__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.wls-sec__head--risk {
  align-items: flex-start;
}
.wls-sec__risk-l {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.wls-sec__t {
  margin: 0;
  font-family: Manrope, var(--font), sans-serif;
  font-size: 1.125rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--w-on-surface);
}
.wls-sec__en {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #717786;
  flex-shrink: 0;
}
.wls-host-pill {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--w-secondary-container);
  color: var(--w-secondary);
}

.wls-scope {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px;
  border: none;
  border-radius: 16px;
  background: var(--w-surface-lowest);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease;
}
.wls-scope:active {
  background: var(--w-surface-low);
}
.wls-scope__l {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.wls-scope__ico {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: rgba(0, 122, 255, 0.1);
  color: var(--w-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.wls-scope__t {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
}
.wls-scope__s {
  margin: 2px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--w-on-variant);
}
.wls-scope__chev {
  flex-shrink: 0;
  opacity: 0.45;
}

.wls-shell {
  background: var(--w-surface-low);
  border-radius: 16px;
  padding: 4px;
}
.wls-exec {
  padding: 18px 16px 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.wls-exec__field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wls-exec__lbl {
  font-size: 14px;
  font-weight: 700;
  color: var(--w-on-surface);
}
.wls-exec__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 4px;
}
.wls-exec__num {
  width: 72px;
  padding: 10px 12px;
  border: none;
  border-radius: 10px;
  background: var(--w-surface-lowest);
  font-family: ui-monospace, monospace;
  font-size: 15px;
  font-weight: 800;
  color: var(--w-primary);
  text-align: right;
  outline: none;
}
.wls-exec__num:focus {
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.2);
}

.wls-seg--pill {
  display: flex;
  padding: 4px;
  border-radius: 10px;
  background: var(--w-surface-high);
  gap: 2px;
}
.wls-seg__pill {
  flex: 1;
  border: none;
  padding: 10px 8px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #717786;
  background: transparent;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}
.wls-seg__pill.on {
  background: var(--w-surface-lowest);
  color: var(--w-primary);
  box-shadow: 0 2px 8px rgba(26, 28, 31, 0.08);
}

.wls-fuse {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(0, 122, 255, 0.08);
}
.wls-fuse__ico {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--w-primary);
}
.wls-fuse__txt {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--w-on-variant);
}
.wls-fuse__txt strong {
  color: var(--w-on-surface);
  font-weight: 800;
}

.wls-risk-card {
  background: var(--w-surface-lowest);
  border-radius: 20px;
  padding: 22px 20px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.03);
}
.wls-risk-block + .wls-risk-block {
  margin-top: 28px;
}
.wls-risk-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.wls-risk-head__lbl {
  font-size: 14px;
  font-weight: 700;
}
.wls-risk-head__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.wls-risk-head__pct {
  font-size: 18px;
  font-weight: 800;
  font-family: ui-monospace, monospace;
}
.wls-risk-head__pct--tp {
  color: var(--w-secondary);
}
.wls-risk-head__pct--sl {
  color: var(--w-tertiary);
}
.wls-risk-chip {
  font-size: 10px;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 6px;
  font-family: ui-monospace, monospace;
}
.wls-risk-chip--tp {
  background: var(--w-secondary-container);
  color: var(--w-secondary);
}
.wls-risk-chip--sl {
  background: var(--w-tertiary);
  color: #fff;
}

.wls-range--tv::-webkit-slider-runnable-track {
  background: var(--w-surface-container);
}
.wls-range--tv::-webkit-slider-thumb {
  background: var(--w-primary);
  box-shadow: 0 2px 10px rgba(0, 122, 255, 0.25);
}
.wls-range--tv::-moz-range-thumb {
  background: var(--w-primary);
  box-shadow: 0 2px 10px rgba(0, 122, 255, 0.25);
}

.wls-engine {
  position: relative;
  overflow: hidden;
  border-radius: 14px;
  padding: 16px 18px;
  background: #1a1c1f;
  color: #fff;
  margin-bottom: 14px;
}
.wls-engine::after {
  content: '';
  position: absolute;
  right: -16px;
  bottom: -16px;
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: rgba(0, 122, 255, 0.2);
  filter: blur(24px);
  pointer-events: none;
}
.wls-engine__inner {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.wls-engine__ico {
  flex-shrink: 0;
  margin-top: 2px;
  color: #67fcbe;
}
.wls-engine__k {
  margin: 0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #94a3b8;
}
.wls-engine__v {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.45;
  color: #e2e8f0;
}

.wls-scanner {
  background: var(--w-surface-low);
  border-radius: 20px;
  overflow: hidden;
  margin-bottom: 14px;
  box-shadow: 0 1px 0 rgba(193, 198, 215, 0.35);
}
.wls-scanner__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: var(--w-surface-container);
}
.wls-scanner__ttl {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 800;
}
.wls-scanner__body {
  padding: 16px;
}
.wls-scanner__hint {
  margin-top: 0;
  margin-bottom: 16px;
}

.wls-cond-grid {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px 12px;
  align-items: start;
  margin-bottom: 18px;
}
.wls-cond-grid__lbl {
  font-size: 11px;
  font-weight: 800;
  color: #717786;
  padding-top: 10px;
}
.wls-cond-grid__cell {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wls-cond-row {
  display: flex;
  gap: 8px;
}
.wls-tv-select {
  flex: 1;
  min-width: 0;
  height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--w-outline-variant);
  background: var(--w-surface-lowest);
  font-size: 13px;
  font-weight: 600;
  color: var(--w-on-surface);
  outline: none;
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%23717786' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 10px center;
  background-size: 1.25em;
  padding-right: 36px;
}
.wls-tv-select:focus {
  border-color: rgba(0, 122, 255, 0.35);
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.12);
}
.wls-tv-select--full {
  width: 100%;
}
.wls-tv-select--narrow {
  flex: 0 0 88px;
  min-width: 88px;
}
.wls-tv-input {
  flex: 1;
  height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid var(--w-outline-variant);
  background: var(--w-surface-lowest);
  font-size: 14px;
  font-weight: 800;
  font-family: ui-monospace, monospace;
  color: var(--w-primary);
  outline: none;
}
.wls-tv-input:focus {
  border-color: rgba(0, 122, 255, 0.35);
}
.wls-tv-input--dt {
  width: 100%;
  font-family: inherit;
  font-weight: 600;
  font-size: 13px;
  color: var(--w-on-surface);
}
.wls-dt-wrap {
  width: 100%;
}

.wls-cond-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--w-surface-lowest);
  border: 1px solid rgba(193, 198, 215, 0.25);
  font-size: 11px;
  font-weight: 700;
}
.wls-cond-preview__a {
  color: var(--w-secondary);
}
.wls-cond-preview__op {
  color: #717786;
}
.wls-cond-preview__b {
  color: var(--w-primary);
}
.wls-cond-preview__tag {
  margin-left: auto;
  font-size: 9px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(188, 0, 10, 0.06);
  color: var(--w-tertiary);
}

.wls-trig {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--w-outline-variant);
  background: var(--w-surface-lowest);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, opacity 0.15s ease;
}
.wls-trig.on {
  border-color: rgba(0, 122, 255, 0.45);
  box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.08);
}
.wls-trig:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.wls-trig__l {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.wls-trig__ico {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0, 122, 255, 0.1);
  color: var(--w-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.wls-trig__ico--muted {
  background: var(--w-surface-container);
  color: #717786;
}
.wls-trig__t {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
}
.wls-trig__d {
  margin: 2px 0 0;
  font-size: 10px;
  font-weight: 600;
  color: #717786;
  line-height: 1.35;
}
.wls-trig__chk {
  flex-shrink: 0;
  color: var(--w-primary);
}
.wls-trig-loop-hint {
  margin: 0;
  font-size: 11px;
  color: var(--w-on-variant);
  line-height: 1.4;
}

.wls-scan-outline {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  border: 2px solid rgba(0, 122, 255, 0.22);
  background: transparent;
  font-size: 14px;
  font-weight: 800;
  color: var(--w-primary);
  cursor: pointer;
  transition: background 0.15s ease;
}
.wls-scan-outline:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.wls-scan-outline:active:not(:disabled) {
  background: rgba(0, 122, 255, 0.06);
}
.wls-scan-outline__spin {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(0, 122, 255, 0.25);
  border-top-color: var(--w-primary);
  border-radius: 50%;
  animation: wls-spin 0.7s linear infinite;
}

.wls-cond-panel {
  margin-bottom: 16px;
}
.wls-cond-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wls-cond-type-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.wls-cond-type-lbl {
  font-size: 11px;
  font-weight: 800;
  color: #717786;
  flex-shrink: 0;
}
.wls-cond-type-opts {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.wls-cond-type-btn {
  border: none;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--w-surface-high);
  color: var(--w-on-variant);
  cursor: pointer;
  transition: background 0.15s, color 0.15s, box-shadow 0.15s;
}
.wls-cond-type-btn.on {
  background: var(--w-primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(0, 122, 255, 0.25);
}
.wls-cond-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 14px;
  background: var(--w-surface-lowest);
  border-radius: 12px;
  border: 1px solid rgba(193, 198, 215, 0.3);
}
.wls-cond-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.wls-cond-row--3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
}

.wls-card--alerts {
  margin-bottom: 24px;
}
.wls-alerts--flat .wls-alert-row:first-child {
  margin-top: 0;
}

.tabular {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
}
</style>
