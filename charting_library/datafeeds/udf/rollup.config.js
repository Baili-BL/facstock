/* globals process */

import { terser } from 'rollup-plugin-terser';
import { nodeResolve } from '@rollup/plugin-node-resolve';

const environment = process.env.ENV || 'development';
const isDevelopmentEnv = (environment === 'development');

export default [
	// ── A-Share Custom Datafeed（新版图表用 Datafeed API）─────────────────
	{
		input: 'lib/udf-compatible-datafeed.js',
		output: {
			name: 'Datafeeds',
			format: 'umd',
			file: 'dist/bundle.js',
			sourcemap: isDevelopmentEnv,
		},
		plugins: [
			nodeResolve({
				browser: true,
			}),
			!isDevelopmentEnv && terser({
				ecma: 2018,
				output: { inline_script: true },
			}),
		],
	},
];
