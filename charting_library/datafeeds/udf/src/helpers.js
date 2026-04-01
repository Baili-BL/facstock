/**
 * helpers.js — 供 custom datafeed.js 使用的 HTTP 请求和工具函数
 */

/**
 * 获取后端 datafeed URL
 * 由 mobile_white.html 在模块加载前写入 window.__tvDatafeedUrl__
 * 开发环境: Vite 代理 /tv_udf → Flask
 * 生产环境: Flask 直接提供 /tv_udf/*
 */
export function getDatafeedUrl() {
	if (typeof window !== 'undefined' && window.__tvDatafeedUrl__) {
		return window.__tvDatafeedUrl__;
	}
	// 降级：同源
	if (typeof window !== 'undefined' && window.location) {
		return window.location.origin + '/tv_udf';
	}
	return '/tv_udf';
}

/**
 * 发起 HTTP GET 请求
 * @param {string} url - 请求 URL
 * @param {object} params - 查询参数
 * @param {string} responseType - 'json' | 'text'
 * @returns {Promise<any>}
 */
export function makeRequest(url, params = {}, responseType = 'json') {
	const paramKeys = Object.keys(params);
	if (paramKeys.length !== 0) {
		const queryString = paramKeys
			.map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
			.join('&');
		url += (url.includes('?') ? '&' : '?') + queryString;
	}

	return fetch(url, { credentials: 'same-origin' })
		.then((response) => {
			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}
			if (responseType === 'text') {
				return response.text();
			}
			return response.json();
		});
}

/**
 * 判断是否为 A 股交易时间
 * 仅工作日 09:15-11:30 / 13:00-15:05（北京时间）
 */
export function isTradingSession() {
	const now = new Date();
	// 北京时间
	const hour = now.getUTCHours() + 8;
	const day = now.getUTCDay();
	const minute = now.getUTCMinutes();

	// 周末休市
	if (day === 0 || day === 6) return false;

	const totalMinutes = hour * 60 + minute;

	// 上午: 09:15-11:30
	const morningStart = 9 * 60 + 15;
	const morningEnd = 11 * 60 + 30;

	// 下午: 13:00-15:05
	const afternoonStart = 13 * 60;
	const afternoonEnd = 15 * 60 + 5;

	return (
		(totalMinutes >= morningStart && totalMinutes <= morningEnd) ||
		(totalMinutes >= afternoonStart && totalMinutes <= afternoonEnd)
	);
}

/**
 * 根据 resolution 计算下一根 K 线的时间戳（毫秒）
 * @param {number} barTime - 当前 K 线时间戳（毫秒）
 * @param {string} resolution - 分辨率字符串，如 '1', '5', '15', '60', '1D', '1W'
 */
export function getNextBarTime(barTime, resolution) {
	const date = new Date(barTime);

	if (resolution === '1D' || resolution === 'D') {
		date.setUTCDate(date.getUTCDate() + 1);
		date.setUTCHours(0, 0, 0, 0);
	} else if (resolution === '1W' || resolution === 'W') {
		date.setUTCDate(date.getUTCDate() + 7);
		date.setUTCHours(0, 0, 0, 0);
	} else if (resolution === '1M' || resolution === 'M') {
		date.setUTCMonth(date.getUTCMonth() + 1);
		date.setUTCDate(1);
		date.setUTCHours(0, 0, 0, 0);
	} else if (resolution === '4H') {
		date.setUTCHours(date.getUTCHours() + 4);
		date.setUTCMinutes(0, 0, 0);
	} else {
		// 分钟线: '1', '5', '15', '30', '60'
		const interval = parseInt(resolution);
		if (!isNaN(interval)) {
			date.setUTCMinutes(date.getUTCMinutes() + interval);
		}
	}

	return date.getTime();
}
