/** @type {import('tailwindcss').Config} */
export default {
	content: ['./src/**/*.{html,js,svelte,ts}'],
	darkMode: 'class',
	theme: {
		extend: {
			colors: {
				// =================================================================
				// BRAND PRIMARY COLORS (Use most frequently)
				// =================================================================
				brand: {
					// Primary: Infinite Blue - Main brand color
					'primary': '#032D42',
					'primary-light': '#0a4560',
					'primary-dark': '#021e2d',
					// Accent: Wasabi Green - Use sparingly for highlights
					'accent': '#63DF4E',
					'accent-hover': '#52c840',
					'accent-dark': '#4bb93d',
					// Neutrals
					'white': '#FFFFFF',
					'black': '#000000',
				},

				// =================================================================
				// SUPPLEMENTARY COLORS (Limited use - gradients only)
				// =================================================================
				supplementary: {
					'bright-blue': '#52B8FF',
					'bright-indigo': '#7661FF',
					'bright-purple': '#BF71F2',
				},

				// =================================================================
				// SURFACE COLORS (CSS Variables for light/dark mode)
				// =================================================================
				surface: {
					DEFAULT: 'var(--surface)',
					primary: 'var(--surface)',
					secondary: 'var(--surface-secondary)',
					tertiary: 'var(--surface-tertiary)',
					hover: 'var(--surface-hover)',
					selected: 'var(--surface-selected)',
					inverse: 'var(--surface-inverse)',
					elevated: 'var(--surface-elevated)',
					glass: 'var(--surface-glass)',
					border: 'var(--border)',
				},

				// =================================================================
				// TEXT COLORS
				// =================================================================
				text: {
					primary: 'var(--text-primary)',
					secondary: 'var(--text-secondary)',
					muted: 'var(--text-muted)',
					inverse: 'var(--text-inverse)',
				},

				// =================================================================
				// NODE TYPE COLORS
				// =================================================================
				node: {
					llm: '#7661FF',
					'llm-bg': 'rgba(118, 97, 255, 0.1)',
					lambda: '#f97316',
					'lambda-bg': 'rgba(249, 115, 22, 0.1)',
					connector: '#52B8FF',
					data: '#52B8FF',
					'data-bg': 'rgba(82, 184, 255, 0.1)',
					start: '#63DF4E',
					'start-bg': 'rgba(99, 223, 78, 0.1)',
					end: '#f43f5e',
					'end-bg': 'rgba(244, 63, 94, 0.1)',
					output: '#10b981',
					'output-bg': 'rgba(16, 185, 129, 0.1)',
					subgraph: '#032D42',
					'subgraph-bg': 'rgba(3, 45, 66, 0.08)',
					agent: '#BF71F2',
					'agent-bg': 'rgba(191, 113, 242, 0.1)',
					webagent: '#BF71F2',
					'multi-llm': '#BF71F2',
					'weighted-sampler': '#7661FF',
				},

				// =================================================================
				// STATUS COLORS
				// =================================================================
				status: {
					pending: '#94a3b8',
					running: '#52B8FF',
					completed: '#63DF4E',
					failed: '#ef4444',
					cancelled: '#f59e0b',
					skipped: '#64748b',
				},

				// =================================================================
				// SEMANTIC COLORS
				// =================================================================
				success: {
					DEFAULT: '#63DF4E',
					light: 'rgba(99, 223, 78, 0.1)',
					dark: '#52c840',
					border: 'rgba(99, 223, 78, 0.25)',
				},
				info: {
					DEFAULT: '#52B8FF',
					light: 'rgba(82, 184, 255, 0.1)',
					dark: '#3da8f5',
					border: 'rgba(82, 184, 255, 0.25)',
				},
				warning: {
					DEFAULT: '#f59e0b',
					light: 'rgba(245, 158, 11, 0.1)',
					dark: '#d97706',
					border: 'rgba(245, 158, 11, 0.25)',
				},
				error: {
					DEFAULT: '#ef4444',
					light: 'rgba(239, 68, 68, 0.1)',
					dark: '#dc2626',
					border: 'rgba(239, 68, 68, 0.25)',
				},

				// Extended palette (for backwards compatibility)
				cyan: {
					DEFAULT: '#52B8FF',
					50: '#eef9ff',
					100: '#d9f1ff',
					200: '#bce8ff',
					300: '#8edaff',
					400: '#52B8FF',
					500: '#3da8f5',
					600: '#2493e6',
					700: '#1a7bcc',
					800: '#1a65a6',
					900: '#1b5583',
					950: '#123550',
				},
				indigo: {
					DEFAULT: '#7661FF',
					50: '#f0eeff',
					100: '#e4e0ff',
					200: '#cdc5ff',
					300: '#aea0ff',
					400: '#9183ff',
					500: '#7661FF',
					600: '#6a4ff5',
					700: '#5a3de0',
					800: '#4a32ba',
					900: '#3d2c96',
					950: '#251a5e',
				},
				violet: {
					DEFAULT: '#BF71F2',
					50: '#faf5ff',
					100: '#f4e8ff',
					200: '#ebd5ff',
					300: '#dcb4ff',
					400: '#c785ff',
					500: '#BF71F2',
					600: '#a24de6',
					700: '#8a39ca',
					800: '#7331a5',
					900: '#5e2b86',
					950: '#3f1261',
				},
			},

			// =================================================================
			// TYPOGRAPHY
			// =================================================================
			fontFamily: {
				sans: ['Plus Jakarta Sans', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
				mono: ['JetBrains Mono', 'Fira Code', 'SF Mono', 'Monaco', 'Consolas', 'monospace'],
				display: ['Plus Jakarta Sans', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
			},

			fontSize: {
				'2xs': ['0.6875rem', { lineHeight: '1rem' }],
				'xs': ['0.75rem', { lineHeight: '1rem' }],
				'sm': ['0.8125rem', { lineHeight: '1.25rem' }],
				'base': ['0.875rem', { lineHeight: '1.5rem' }],
				'lg': ['1rem', { lineHeight: '1.5rem' }],
				'xl': ['1.125rem', { lineHeight: '1.75rem' }],
				'2xl': ['1.25rem', { lineHeight: '1.75rem' }],
				'3xl': ['1.5rem', { lineHeight: '2rem' }],
				'4xl': ['1.875rem', { lineHeight: '2.25rem' }],
				'5xl': ['2.25rem', { lineHeight: '2.5rem' }],
			},

			letterSpacing: {
				tighter: '-0.025em',
				tight: '-0.015em',
				normal: '-0.011em',
				wide: '0.015em',
			},

			// =================================================================
			// SHADOWS - Elevation system
			// =================================================================
			boxShadow: {
				'xs': '0 1px 2px rgba(0, 0, 0, 0.04)',
				'sm': '0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04)',
				'DEFAULT': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
				'md': '0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04)',
				'lg': '0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04)',
				'xl': '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.03)',
				'2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
				'inner': 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.04)',
				// Brand glows (use sparingly)
				'glow-accent': '0 0 20px rgba(99, 223, 78, 0.35)',
				'glow-info': '0 0 20px rgba(82, 184, 255, 0.25)',
				'glow-indigo': '0 0 20px rgba(118, 97, 255, 0.25)',
				// Elevation system
				'elevation-1': '0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
				'elevation-2': '0 4px 12px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.04)',
				'elevation-3': '0 10px 24px rgba(0, 0, 0, 0.12), 0 4px 8px rgba(0, 0, 0, 0.06)',
				'card': '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02)',
				'card-hover': '0 8px 16px -4px rgba(0, 0, 0, 0.1), 0 4px 8px -4px rgba(0, 0, 0, 0.04)',
				'dropdown': '0 10px 40px -10px rgba(0, 0, 0, 0.2), 0 4px 12px rgba(0, 0, 0, 0.08)',
			},

			// =================================================================
			// ANIMATIONS
			// =================================================================
			animation: {
				'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
				'glow': 'glow 2s ease-in-out infinite',
				'shimmer': 'shimmer 1.5s infinite',
				'float': 'float 3s ease-in-out infinite',
				'slide-up': 'slide-up 0.3s ease-out forwards',
				'slide-down': 'slide-down 0.3s ease-out forwards',
				'scale-in': 'scale-in 0.2s ease-out forwards',
				'fade-in': 'fade-in 0.2s ease-out forwards',
				'spin-slow': 'spin 2s linear infinite',
			},
			keyframes: {
				glow: {
					'0%, 100%': { boxShadow: '0 0 5px rgba(99, 223, 78, 0.3)' },
					'50%': { boxShadow: '0 0 20px rgba(99, 223, 78, 0.5)' },
				},
				shimmer: {
					'0%': { backgroundPosition: '-200% 0' },
					'100%': { backgroundPosition: '200% 0' },
				},
				float: {
					'0%, 100%': { transform: 'translateY(0)' },
					'50%': { transform: 'translateY(-6px)' },
				},
				'slide-up': {
					from: { opacity: '0', transform: 'translateY(10px)' },
					to: { opacity: '1', transform: 'translateY(0)' },
				},
				'slide-down': {
					from: { opacity: '0', transform: 'translateY(-10px)' },
					to: { opacity: '1', transform: 'translateY(0)' },
				},
				'scale-in': {
					from: { opacity: '0', transform: 'scale(0.95)' },
					to: { opacity: '1', transform: 'scale(1)' },
				},
				'fade-in': {
					from: { opacity: '0' },
					to: { opacity: '1' },
				},
			},

			// =================================================================
			// BORDER RADIUS
			// =================================================================
			borderRadius: {
				'sm': '6px',
				'DEFAULT': '8px',
				'md': '8px',
				'lg': '12px',
				'xl': '16px',
				'2xl': '24px',
				'3xl': '32px',
			},

			// =================================================================
			// TRANSITIONS
			// =================================================================
			transitionDuration: {
				'fast': '120ms',
				'base': '200ms',
				'slow': '300ms',
			},
			transitionTimingFunction: {
				'bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
				'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
			},

			// =================================================================
			// BACKDROP BLUR
			// =================================================================
			backdropBlur: {
				'xs': '2px',
				'sm': '4px',
				'DEFAULT': '8px',
				'md': '12px',
				'lg': '16px',
				'xl': '24px',
				'2xl': '40px',
				'3xl': '64px',
			},

			// =================================================================
			// Z-INDEX
			// =================================================================
			zIndex: {
				'dropdown': '50',
				'sticky': '100',
				'fixed': '200',
				'overlay': '300',
				'modal': '400',
				'popover': '500',
				'tooltip': '600',
			},

			// =================================================================
			// SPACING
			// =================================================================
			spacing: {
				'4.5': '1.125rem',
				'5.5': '1.375rem',
				'13': '3.25rem',
				'15': '3.75rem',
				'17': '4.25rem',
				'18': '4.5rem',
				'19': '4.75rem',
				'21': '5.25rem',
				'22': '5.5rem',
			},
		}
	},
	plugins: []
};
