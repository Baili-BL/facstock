/**
 * streaming.js — 实时行情 WebSocket 订阅
 *
 * 支持两种模式（按优先级尝试）：
 * 1. SocketIO (flask-socketio)  — 低延迟实时行情
 * 2. Polling fallback           — 无 WebSocket 时每 10s 轮询 /tv_udf/stream 接口
 *
 * 协议格式（SocketIO event: 'kline_update'）:
 * {
 *   symbol: "SSE:600519",
 *   resolution: "1D",
 *   time: 1743350400000,   // UTC ms (日线 = 当天 00:00 UTC = 前一交易日 08:00 北京时间)
 *   open:  1600.00,
 *   high:  1625.00,
 *   low:   1595.00,
 *   close: 1618.50,
 *   volume: 12345678,
 * }
 */

import { getNextBarTime } from './helpers.js';

const SOIConnectionState = {
	DISCONNECTED: 0,
	CONNECTING: 1,
	CONNECTED: 2,
	ERROR: 3,
};

// ── SocketIO 连接 ──────────────────────────────────────────────────────────
let socketIO = null;
let connectionState = SOIConnectionState.DISCONNECTED;

// 订阅者 Map: channelString → { resolution, lastBar, handlers[] }
const channelToSubscription = new Map();

// ── Polling fallback ──────────────────────────────────────────────────────
const pollTimers = new Map(); // subscriberUID → timerId
let pollInterval = null; // 全局轮询定时器（每 10s）
const pollPending = new Set(); // 待轮询的 subscriberUID
const pollCache = new Map();   // subscriberUID → lastBar
const POLL_INTERVAL_MS = 10 * 1000;

// ──────────────────────────────────────────────────────────────────────────
function parseSymbolFromChannel(channelString) {
	// 格式: "SSE:600519"
	const parts = channelString.split(':');
	return parts.length === 2 ? { exchange: parts[0], code: parts[1] } : null;
}

function getChannelString(symbolInfo) {
	return symbolInfo.ticker || '';
}

// ── SocketIO 连接 ──────────────────────────────────────────────────────────
function ensureSocketIO(datafeedUrl) {
	if (socketIO !== null) return socketIO;

	connectionState = SOIConnectionState.CONNECTING;

	// 动态加载 socket.io 客户端
	const script = document.createElement('script');
	script.src = 'https://cdn.socket.io/4.7.5/socket.io.min.js';
	script.onload = () => {
		console.log('[Streaming] SocketIO script loaded');
		connectSocketIO(datafeedUrl);
	};
	script.onerror = () => {
		console.warn('[Streaming] SocketIO CDN failed, falling back to polling');
		connectionState = SOIConnectionState.ERROR;
		startPolling();
	};
	document.head.appendChild(script);

	return null;
}

function connectSocketIO(datafeedUrl) {
	// 将 http://host/tv_udf 转成 ws://host/socket.io
	// 去掉末尾斜杠，统一处理
	const base = datafeedUrl.replace(/\/$/, '').replace(/^http/, 'ws');
	const ns = '/tv';

	try {
		socketIO = io(base, {
			path: '/socket.io',
			namespace: ns,
			transports: ['websocket', 'polling'],
			reconnection: true,
			reconnectionDelay: 3000,
			reconnectionAttempts: 5,
			timeout: 10000,
		});
	} catch (e) {
		console.warn('[Streaming] SocketIO init failed:', e);
		connectionState = SOIConnectionState.ERROR;
		startPolling();
		return;
	}

	socketIO.on('connect', () => {
		console.log('[Streaming] SocketIO connected, sid:', socketIO.id);
		connectionState = SOIConnectionState.CONNECTED;

		// 重连后重新订阅所有活跃频道
		for (const [channel, sub] of channelToSubscription.entries()) {
			socketIO.emit('subscribe', { channel, resolution: sub.resolution });
		}
	});

	socketIO.on('disconnect', (reason) => {
		console.log('[Streaming] SocketIO disconnected:', reason);
		connectionState = SOIConnectionState.DISCONNECTED;
	});

	socketIO.on('connect_error', (err) => {
		console.warn('[Streaming] SocketIO connect_error:', err.message);
		connectionState = SOIConnectionState.ERROR;
		startPolling();
	});

	// ── K 线实时更新事件 ──────────────────────────────────────────────────
	// 后端推送格式: { symbol, resolution, time, open, high, low, close, volume }
	socketIO.on('kline_update', (payload) => {
		if (!payload || !payload.symbol) return;
		handleUpdate(payload);
	});

	socketIO.on('tick_update', (payload) => {
		// 独立 tick（如分时数据），格式: { symbol, price, volume, time }
		if (!payload || !payload.symbol) return;
		// 转换为 bar 更新格式
		handleUpdate({
			symbol: payload.symbol,
			resolution: '1',
			time: payload.time,
			open: payload.price,
			high: payload.price,
			low: payload.price,
			close: payload.price,
			volume: payload.volume || 0,
		});
	});
}

// ── 统一更新处理 ──────────────────────────────────────────────────────────
function handleUpdate(payload) {
	const { symbol, resolution } = payload;
	const channelString = symbol;
	const subscription = channelToSubscription.get(channelString);
	if (!subscription) return;

	// 检查 resolution 是否匹配
	if (subscription.resolution !== resolution) return;

	let bar = {
		time: payload.time,
		open: parseFloat(payload.open),
		high: parseFloat(payload.high),
		low: parseFloat(payload.low),
		close: parseFloat(payload.close),
		volume: parseFloat(payload.volume || 0),
	};

	// 修正时间：若 resolution 是分钟，time 可能传的是秒，转换为毫秒
	if (bar.time < 1e12) {
		bar.time = bar.time * 1000;
	}

	const lastBar = subscription.lastBar;
	if (lastBar && bar.time === lastBar.time) {
		// 同根 K 线：合并
		bar = {
			...lastBar,
			high: Math.max(lastBar.high, bar.high),
			low: Math.min(lastBar.low, bar.low),
			close: bar.close,
			volume: (lastBar.volume || 0) + (bar.volume || 0),
		};
	} else if (lastBar && bar.time < lastBar.time) {
		// 时间倒流，忽略
		return;
	}

	subscription.lastBar = bar;

	// 通知所有订阅者
	for (const handler of subscription.handlers) {
		handler.callback(bar);
	}
}

// ── 订阅 / 取消订阅（Datafeed API 调用的入口）─────────────────────────────
export function subscribeRealTime(symbolInfo, resolution, onRealtimeCallback, subscriberUID, lastBarsCache) {
	const channelString = getChannelString(symbolInfo);
	if (!channelString) return;

	const handler = { id: subscriberUID, callback: onRealtimeCallback };

	let subscriptionItem = channelToSubscription.get(channelString);

	if (subscriptionItem) {
		// 已有订阅：追加 handler，更新 resolution 和 lastBar
		subscriptionItem.resolution = resolution;
		subscriptionItem.handlers.push(handler);
		if (lastBarsCache && lastBarsCache.has(symbolInfo.ticker)) {
			subscriptionItem.lastBar = lastBarsCache.get(symbolInfo.ticker);
		}
	} else {
		// 新订阅
		subscriptionItem = {
			resolution,
			lastBar: null,
			handlers: [handler],
		};
		channelToSubscription.set(channelString, subscriptionItem);

		// 初始化 SocketIO（如果尚未初始化）
		if (connectionState === SOIConnectionState.DISCONNECTED) {
			// datafeedUrl 存储在全局或从 window 对象获取
			const datafeedUrl = window.__tvDatafeedUrl__ || (window.location ? window.location.origin + '/tv_udf' : '/tv_udf');
			ensureSocketIO(datafeedUrl);
		}

		// SocketIO 已连接：直接订阅
		if (connectionState === SOIConnectionState.CONNECTED && socketIO) {
			socketIO.emit('subscribe', { channel: channelString, resolution });
		}
	}

	console.log('[Streaming] subscribeBars:', channelString, resolution, subscriberUID);
}

export function unsubscribeRealTime(subscriberUID) {
	for (const [channelString, subscriptionItem] of channelToSubscription.entries()) {
		const handlerIndex = subscriptionItem.handlers.findIndex((h) => h.id === subscriberUID);
		if (handlerIndex !== -1) {
			subscriptionItem.handlers.splice(handlerIndex, 1);
			if (subscriptionItem.handlers.length === 0) {
				// 无订阅者：退订频道
				console.log('[Streaming] unsubscribe:', channelString);
				channelToSubscription.delete(channelString);

				// 通知后端退订
				if (connectionState === SOIConnectionState.CONNECTED && socketIO) {
					socketIO.emit('unsubscribe', { channel: channelString });
				}

				// 清理轮询
				if (pollTimers.has(subscriberUID)) {
					clearInterval(pollTimers.get(subscriberUID));
					pollTimers.delete(subscriberUID);
				}
				pollCache.delete(subscriberUID);
				pollPending.delete(subscriberUID);
			}
			break;
		}
	}
}

// ── Polling Fallback ──────────────────────────────────────────────────────
function startPolling() {
	if (pollInterval !== null) return; // 已在运行

	console.log('[Streaming] Starting polling fallback');

	// 全局轮询：每 10s 获取所有活跃频道的最新 K 线
	pollInterval = setInterval(() => {
		if (pollPending.size === 0) return;

		// 批量请求
		const channels = Array.from(pollPending);
		pollPending.clear();

		for (const subscriberUID of channels) {
			let targetSub = null;
			for (const sub of channelToSubscription.values()) {
				if (sub.handlers.some((h) => h.id === subscriberUID)) {
					targetSub = sub;
					break;
				}
			}
			if (!targetSub) continue;

			const channel = sub => {
				for (const [ch, s] of channelToSubscription.entries()) {
					if (s === targetSub) return ch;
				}
				return null;
			};
			const ch = channel(targetSub);
			if (!ch) continue;

			const datafeedUrl = window.__tvDatafeedUrl__ || (window.location ? window.location.origin + '/tv_udf' : '/tv_udf');
			const url = `${datafeedUrl}/stream?symbol=${encodeURIComponent(ch)}&resolution=${targetSub.resolution}`;

			fetch(url, { credentials: 'same-origin' })
				.then((r) => r.json())
				.then((data) => {
					if (data && data.time && data.close !== undefined) {
						handleUpdate({
							symbol: ch,
							resolution: targetSub.resolution,
							time: data.time,
							open: data.open,
							high: data.high,
							low: data.low,
							close: data.close,
							volume: data.volume || 0,
						});
					}
				})
				.catch((err) => {
					console.warn('[Streaming] poll fetch error:', err);
				});
		}
	}, POLL_INTERVAL_MS);
}

// ── 主动拉取（首次订阅时立即拉一次）─────────────────────────────────────
export function fetchLatestBar(symbolInfo, resolution, callback) {
	const channelString = getChannelString(symbolInfo);
	const datafeedUrl = window.__tvDatafeedUrl__ || (window.location ? window.location.origin + '/tv_udf' : '/tv_udf');
	const url = `${datafeedUrl}/stream?symbol=${encodeURIComponent(channelString)}&resolution=${resolution}`;

	fetch(url, { credentials: 'same-origin' })
		.then((r) => r.json())
		.then((data) => {
			if (data && data.time && data.close !== undefined) {
				callback({
					time: data.time < 1e12 ? data.time * 1000 : data.time,
					open: parseFloat(data.open),
					high: parseFloat(data.high),
					low: parseFloat(data.low),
					close: parseFloat(data.close),
					volume: parseFloat(data.volume || 0),
				});
			}
		})
		.catch(() => {
			// ignore
		});
}
