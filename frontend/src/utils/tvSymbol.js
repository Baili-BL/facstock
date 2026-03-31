/**
 * 6 位 A 股代码 → TradingView / UDF 常用交易所前缀（与后端 tv_udf_routes 规则一致）
 */
export function tvSymbolFromChinaCode6(code6) {
  const c = String(code6 || '').trim()
  if (!/^\d{6}$/.test(c)) return c
  if (c.startsWith('6')) return `SSE:${c}`
  if (c.startsWith('0') || c.startsWith('3')) return `SZSE:${c}`
  return c
}
