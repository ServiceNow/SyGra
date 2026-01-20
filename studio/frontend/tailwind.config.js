/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				// =================================================================
				// BRAND PRIMARY COLORS
				// =================================================================
				// Infinite Blue: Main brand color, use most frequently
				// Wasabi Green: Accent color, use sparingly for special highlights
				brand: {
					'infinite-blue': '#032D42',
					'wasabi-green': '#63DF4E',
					'bright-blue': '#52B8FF',
					'bright-indigo': '#7661FF',
					'bright-purple': '#BF71F2',
				},

				// =================================================================
				// SURFACE COLORS (CSS Variables for light/dark mode)
				// =================================================================
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

				// =================================================================
				// NODE TYPE COLORS
				// =================================================================
				// Using brand-aligned palette for graph nodes
				node: {
					llm: '#7661FF',           // Bright Indigo - AI/intelligence
					lambda: '#F97316',        // Orange - custom functions
					connector: '#52B8FF',     // Bright Blue - data flow
					data: '#52B8FF',          // Bright Blue - data nodes
					start: '#63DF4E',         // Wasabi Green - entry point
					end: '#EF4444',           // Red - exit point
					output: '#63DF4E',        // Wasabi Green - successful output
					subgraph: '#032D42',      // Infinite Blue - nested workflows
					agent: '#BF71F2',         // Bright Purple - autonomous agents
					webagent: '#BF71F2',      // Bright Purple - web agents
					'multi-llm': '#BF71F2',   // Bright Purple - multi-model
					'weighted-sampler': '#7661FF', // Bright Indigo
				},

				// =================================================================
				// STATUS COLORS
				// =================================================================
				status: {
					pending: '#9CA3AF',       // Gray - waiting
					running: '#52B8FF',       // Bright Blue - in progress
					completed: '#63DF4E',     // Wasabi Green - success
					failed: '#EF4444',        // Red - error
					cancelled: '#F59E0B',     // Amber - cancelled
					skipped: '#6B7280',       // Gray - skipped
				},

				// =================================================================
				// SEMANTIC COLORS
				// =================================================================
				success: {
					DEFAULT: '#63DF4E',
					light: 'rgba(99, 223, 78, 0.15)',
					dark: '#4BC93A',
				},
				info: {
					DEFAULT: '#52B8FF',
					light: 'rgba(82, 184, 255, 0.15)',
					dark: '#3AA3E8',
				},
				warning: {
					DEFAULT: '#F59E0B',
					light: 'rgba(245, 158, 11, 0.15)',
					dark: '#D97706',
				},
				error: {
					DEFAULT: '#EF4444',
					light: 'rgba(239, 68, 68, 0.15)',
					dark: '#DC2626',
				},
			},

			// =================================================================
			// TYPOGRAPHY
			// =================================================================
			fontFamily: {
				sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
				mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'Consolas', 'monospace'],
			},

			// =================================================================
			// SHADOWS - Brand styled
			// =================================================================
			boxShadow: {
				'brand-sm': '0 1px 2px 0 rgba(3, 45, 66, 0.05)',
				'brand': '0 1px 3px 0 rgba(3, 45, 66, 0.1), 0 1px 2px -1px rgba(3, 45, 66, 0.1)',
				'brand-md': '0 4px 6px -1px rgba(3, 45, 66, 0.1), 0 2px 4px -2px rgba(3, 45, 66, 0.1)',
				'brand-lg': '0 10px 15px -3px rgba(3, 45, 66, 0.1), 0 4px 6px -4px rgba(3, 45, 66, 0.1)',
				'brand-xl': '0 20px 25px -5px rgba(3, 45, 66, 0.1), 0 8px 10px -6px rgba(3, 45, 66, 0.1)',
				'glow-accent': '0 0 20px rgba(99, 223, 78, 0.3)',
				'glow-primary': '0 0 20px rgba(82, 184, 255, 0.3)',
			},

			// =================================================================
			// ANIMATIONS
			// =================================================================
			animation: {
				'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
				'glow': 'glow 2s ease-in-out infinite',
			},
			keyframes: {
				glow: {
					'0%, 100%': { boxShadow: '0 0 5px rgba(99, 223, 78, 0.3)' },
					'50%': { boxShadow: '0 0 20px rgba(99, 223, 78, 0.5)' },
				},
			},

			// =================================================================
			// BORDER RADIUS
			// =================================================================
			borderRadius: {
				'brand': '0.5rem',
				'brand-lg': '0.75rem',
				'brand-xl': '1rem',
			},

			// =================================================================
			// TRANSITIONS
			// =================================================================
			transitionDuration: {
				'brand': '150ms',
			},
			transitionTimingFunction: {
				'brand': 'cubic-bezier(0.4, 0, 0.2, 1)',
			},
		}
	},
	plugins: []
};
