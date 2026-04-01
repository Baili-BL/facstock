/**
 * A-Share Custom Datafeed for TradingView Advanced Charts
 * 实现 Datafeed API，支持 A 股日线 + 分钟线 + 实时行情
 *
 * 参考: https://www.tradingview.com/charting-library-docs/latest/connecting_data/datafeed-api/
 */

import { makeRequest, getDatafeedUrl } from './helpers.js';
import { subscribeRealTime, unsubscribeRealTime } from './streaming.js';

// 缓存最后一根 K 线（用于实时更新）
const lastBarsCache = new Map();

// Datafeed 配置：支持日线 + 分钟线
const configurationData = {
	supports_search: false,
	supports_group_request: false,
	supports_marks: false,
	supports_timescale_marks: false,
	supports_time: true,
	supports_realtime: true,

	// 支持 A 股常用时间周期
	supported_resolutions: [
		'1',  '5',  '15',  '30',  '60',   // 分钟
		'4H', '1D', '1W', '1M',           // 日线及以上
	],
	exchanges: [
		{ value: 'SSE', name: '上海证券交易所', desc: 'SSE A-Share' },
		{ value: 'SZSE', name: '深圳证券交易所', desc: 'SZSE A-Share' },
	],
	symbols_types: [
		{ name: '股票', value: 'stock' },
	],
};

// ── 辅助：解析 TradingView symbol → A 股代码 ──────────────────────────────
function parseSymbol(symbolName) {
	// 格式: "SSE:600519" 或 "SZSE:000001" 或纯代码 "600519"
	const s = String(symbolName || '').trim().toUpperCase();
	if (s.includes(':')) {
		const parts = s.split(':');
		return { exchange: parts[0], code: parts[1] };
	}
	// 纯代码
	const code = s;
	if (code.startsWith('6')) return { exchange: 'SSE', code };
	if (code.startsWith('0') || code.startsWith('3')) return { exchange: 'SZSE', code };
	return { exchange: 'SSE', code };
}

// ── 辅助：获取 A 股交易时段 ────────────────────────────────────────────────
function getSession(resolution) {
	if (resolution === '1D' || resolution === '1W' || resolution === '1M' || resolution === '4H') {
		return '0930-1130,1300-1500';
	}
	// 分钟线也用 A 股时段
	return '0930-1130,1300-1500';
}

// ── Datafeed API 实现 ─────────────────────────────────────────────────────
const Datafeed = {
	// 1. onReady — 返回配置
	onReady(callback) {
		console.log('[Datafeed] onReady');
		setTimeout(() => callback(configurationData), 0);
	},

	// 2. searchSymbols — 搜索股票（简化：后端暂无搜索 API，返回空）
	searchSymbols(userInput, exchange, symbolType, onResultReadyCallback) {
		console.log('[Datafeed] searchSymbols:', userInput, exchange, symbolType);
		// 当前后端未实现搜索，返回空结果
		setTimeout(() => onResultReadyCallback([]), 0);
	},

	// 3. resolveSymbol — 解析股票信息
	resolveSymbol(symbolName, onSymbolResolvedCallback, onResolveErrorCallback) {
		console.log('[Datafeed] resolveSymbol:', symbolName);
		const { exchange, code } = parseSymbol(symbolName);

		makeRequest(`${getDatafeedUrl()}/symbols`, {
			symbol: `${exchange}:${code}`,
		})
			.then((response) => {
				if (response.s === 'error') {
					onResolveErrorCallback(response.errmsg || 'unknown_symbol');
					return;
				}
				onSymbolResolvedCallback(response);
			})
			.catch((err) => {
				console.error('[Datafeed] resolveSymbol error:', err);
				onResolveErrorCallback('unknown_symbol');
			});
	},

	// 4. getBars — 获取历史 K 线
	getBars(symbolInfo, resolution, periodParams, onHistoryCallback, onErrorCallback) {
		const { from, to, firstDataRequest } = periodParams;
		console.log('[Datafeed] getBars:', symbolInfo.ticker, resolution, from, to, 'first:', firstDataRequest);

		makeRequest(`${getDatafeedUrl()}/history`, {
			symbol: symbolInfo.ticker,
			resolution: resolution,
			from: from || 0,
			to: to || 0,
		})
			.then((response) => {
				if (response.s === 'no_data') {
					onHistoryCallback([], { noData: true, nextTime: response.nextTime });
					return;
				}
				if (response.s === 'error') {
					onErrorCallback(response.errmsg || 'server_error');
					return;
				}

				const bars = [];
				const { t, o, h, l, c, v } = response;
				for (let i = 0; i < t.length; i++) {
					const close = parseFloat(c[i]);
					bars.push({
						time: t[i] * 1000,
						open: o && o[i] !== undefined ? parseFloat(o[i]) : close,
						high: h && h[i] !== undefined ? parseFloat(h[i]) : close,
						low: l && l[i] !== undefined ? parseFloat(l[i]) : close,
						close: close,
						volume: v && v[i] !== undefined ? parseFloat(v[i]) : 0,
					});
				}

				// 缓存最后一根 K 线
				if (firstDataRequest && bars.length > 0) {
					lastBarsCache.set(symbolInfo.ticker, { ...bars[bars.length - 1] });
				}

				onHistoryCallback(bars, { noData: false });
			})
			.catch((err) => {
				console.error('[Datafeed] getBars error:', err);
				onErrorCallback(String(err));
			});
	},

	// 5. subscribeBars — 订阅实时 K 线更新
	subscribeBars(symbolInfo, resolution, onRealtimeCallback, subscriberUID) {
		console.log('[Datafeed] subscribeBars:', symbolInfo.ticker, resolution, subscriberUID);
		subscribeRealTime(symbolInfo, resolution, onRealtimeCallback, subscriberUID, lastBarsCache);
	},

	// 6. unsubscribeBars — 取消订阅
	unsubscribeBars(subscriberUID) {
		console.log('[Datafeed] unsubscribeBars:', subscriberUID);
		unsubscribeRealTime(subscriberUID);
	},

	// 7. getServerTime — 服务器时间
	getServerTime(callback) {
		makeRequest(`${getDatafeedUrl()}/time`, {}, 'text')
			.then((timeStr) => {
				const t = parseInt(timeStr);
				if (!isNaN(t)) callback(t);
			})
			.catch(() => {
				// 降级：用本地时间（北京时间）
				callback(Math.floor(Date.now() / 1000) - 8 * 3600);
			});
	},
};

export default Datafeed;
