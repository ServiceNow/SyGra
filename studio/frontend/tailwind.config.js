/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				// SyGra brand colors (purple theme)
				surface: {
					DEFAULT: 'var(--surface)',
					secondary: 'var(--surface-secondary)',
					tertiary: 'var(--surface-tertiary)',
					hover: 'var(--surface-hover)',
					selected: 'var(--surface-selected)',
					inverse: 'var(--surface-inverse)'
				},
				frost: {
					DEFAULT: 'var(--frost)',
					secondary: 'var(--frost-secondary)'
				},
				// Node type colors
				node: {
					llm: '#8b5cf6',      // violet-500
					lambda: '#f97316',    // orange-500
					connector: '#06b6d4', // cyan-500
					start: '#22c55e',     // green-500
					end: '#ef4444',       // red-500
					subgraph: '#3b82f6',  // blue-500
					webagent: '#ec4899'   // pink-500
				},
				// Status colors
				status: {
					pending: '#9ca3af',   // gray-400
					running: '#3b82f6',   // blue-500
					completed: '#22c55e', // green-500
					failed: '#ef4444',    // red-500
					cancelled: '#eab308'  // yellow-500
				}
			},
			fontFamily: {
				mono: ['JetBrains Mono', 'Fira Code', 'monospace']
			},
			animation: {
				'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite'
			}
		}
	},
	plugins: []
};
