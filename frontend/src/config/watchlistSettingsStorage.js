/** 自选风控 / 告警偏好（localStorage），供设置页与其它模块共用 */
export const WATCHLIST_SETTINGS_STORAGE_KEY = 'facSstock_watchlist_settings_v1'

export function defaultWatchlistRiskSettings() {
  return {
    positionMode: 'fixed_ratio',
    singlePositionMaxPct: 20,
    totalPositionMaxPct: 80,
    singlePositionMaxWan: 10,
    totalPositionMaxWan: 100,
    execFrequency: 'per_bar',
    maxExecCount: 10,
    takeProfitPct: 10,
    stopLossSliderPct: 5,
    tpSlAutoManage: true,
    alertRSI: true,
    alertMA: false,
    alertBreakRange: false,
    alertMACD: false,
    alertBollinger: false,
    alertMaster: true,
    alertPctMove: true,
    alertPctMoveThreshold: 5,
    alertVolumeRatio: false,
    alertVolumeRatioMin: 2.5,
    stopLossMode: 'pct_from_cost',
    stopLossPct: 8,
    trailingPct: 8,
    dayDropPct: 3.5,
    /** 自选扫描所用技术指标策略 id（与 watchlistStrategyIds[0] 同步，供旧逻辑读取） */
    watchlistStrategyId: 'rsi_extreme',
    /** 多选策略 id 列表，与下方告警开关一一对应 */
    watchlistStrategyIds: ['rsi_extreme'],
    /** 扫描条件面板（UI / 预留，与后端预设策略并行保存） */
    scanCondIndicator: 'rsi',
    scanCondPeriod: 14,
    scanCondOp: 'gt',
    scanCondValue: 70,
    /** 均线：快慢线与模式 */
    scanMaFast: 5,
    scanMaSlow: 20,
    scanMaMode: 'golden_cross',
    /** MACD：信号类型（参数 12/26/9 与后端一致） */
    scanMacdMode: 'hist_turn',
    /** 布林带：周期、标准差、信号 */
    scanBbPeriod: 20,
    scanBbStd: 2,
    scanBbMode: 'near_upper',
    scanBarTf: '1d',
    /** datetime-local 字符串，空表示未设置 */
    scanExpiresAt: '',
  }
}

export function loadWatchlistRiskSettings() {
  try {
    const raw = localStorage.getItem(WATCHLIST_SETTINGS_STORAGE_KEY)
    if (!raw) return defaultWatchlistRiskSettings()
    const o = JSON.parse(raw)
    if (!o || typeof o !== 'object') return defaultWatchlistRiskSettings()
    const merged = { ...defaultWatchlistRiskSettings(), ...o }
    if (!Array.isArray(merged.watchlistStrategyIds) || merged.watchlistStrategyIds.length === 0) {
      const legacy = merged.watchlistStrategyId
      merged.watchlistStrategyIds =
        typeof legacy === 'string' && legacy.trim()
          ? [legacy.trim()]
          : [...defaultWatchlistRiskSettings().watchlistStrategyIds]
    }
    return merged
  } catch {
    return defaultWatchlistRiskSettings()
  }
}

export function saveWatchlistRiskSettings(data) {
  const payload = { ...data }
  if (Array.isArray(payload.watchlistStrategyIds) && payload.watchlistStrategyIds.length) {
    payload.watchlistStrategyId = payload.watchlistStrategyIds[0]
  }
  localStorage.setItem(WATCHLIST_SETTINGS_STORAGE_KEY, JSON.stringify(payload))
}
