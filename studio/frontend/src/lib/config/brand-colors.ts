/**
 * Brand Color Palette
 *
 * A bold, optimistic, and empathetic color system.
 * Combining colors in gradients adds visual interest, depth, and dimension.
 */

// =============================================================================
// PRIMARY COLORS
// =============================================================================
// Main colors used most frequently. Infinite Blue is the dominant brand color.
// Wasabi Green is an accent - use sparingly for special highlights.

export const PRIMARY = {
	infiniteBlue: '#032D42',    // RGB: 3 45 66 - Main brand color, use most
	wasabiGreen: '#63DF4E',     // RGB: 99 223 78 - Accent, sparingly
	white: '#FFFFFF',
	black: '#000000',
} as const;

// =============================================================================
// SUPPLEMENTARY COLORS
// =============================================================================
// Complement primary colors, adding variety without overshadowing.
// For limited use, like in gradients.

export const SUPPLEMENTARY = {
	brightBlue: '#52B8FF',      // RGB: 82 184 255 - Info, data nodes
	brightIndigo: '#7661FF',    // RGB: 118 97 255 - LLM, AI nodes
	brightPurple: '#BF71F2',    // RGB: 191 113 242 - Special features
} as const;

// =============================================================================
// DERIVED COLORS
// =============================================================================
// Variations for UI states, derived from primary colors

export const DERIVED = {
	// Infinite Blue variations
	infiniteBlueDark: '#021E2D',      // Darker for hover states
	infiniteBlueLight: '#0A4D6E',     // Lighter variation
	infiniteBlueMuted: '#064565',     // Muted for backgrounds
	infiniteBlueSubtle: '#E8F4F8',    // Very light for light mode backgrounds

	// Wasabi Green variations (use sparingly)
	wasabiGreenDark: '#4BC93A',       // Darker for hover
	wasabiGreenLight: '#8AEB7D',      // Lighter variation
	wasabiGreenMuted: 'rgba(99, 223, 78, 0.15)', // Subtle background

	// Supplementary variations
	brightBlueMuted: 'rgba(82, 184, 255, 0.15)',
	brightIndigoMuted: 'rgba(118, 97, 255, 0.15)',
	brightPurpleMuted: 'rgba(191, 113, 242, 0.15)',
} as const;

// =============================================================================
// SEMANTIC COLORS
// =============================================================================
// Purpose-driven color assignments

export const SEMANTIC = {
	// Status colors - mapped from brand palette
	success: PRIMARY.wasabiGreen,
	successBg: DERIVED.wasabiGreenMuted,

	info: SUPPLEMENTARY.brightBlue,
	infoBg: DERIVED.brightBlueMuted,

	warning: '#F59E0B',               // Amber for warnings (accessible)
	warningBg: 'rgba(245, 158, 11, 0.15)',

	error: '#EF4444',                 // Red for errors (standard)
	errorBg: 'rgba(239, 68, 68, 0.15)',

	// Interactive states
	primary: PRIMARY.infiniteBlue,
	primaryHover: DERIVED.infiniteBlueDark,
	primaryActive: DERIVED.infiniteBlueLight,

	accent: PRIMARY.wasabiGreen,
	accentHover: DERIVED.wasabiGreenDark,

	// Text colors
	textPrimary: PRIMARY.infiniteBlue,
	textSecondary: '#4B5563',         // Gray-600
	textMuted: '#9CA3AF',             // Gray-400
	textInverse: PRIMARY.white,

	// Border colors
	border: '#E5E7EB',                // Gray-200
	borderDark: '#374151',            // Gray-700
} as const;

// =============================================================================
// NODE COLORS
// =============================================================================
// Graph node type colors - using brand-aligned palette

export const NODE_COLORS = {
	// Core nodes
	start: PRIMARY.wasabiGreen,       // Green - entry point
	end: '#EF4444',                   // Red - exit (standard recognition)

	// AI/LLM nodes - use supplementary colors
	llm: SUPPLEMENTARY.brightIndigo,  // Indigo - AI/intelligence
	multi_llm: SUPPLEMENTARY.brightPurple, // Purple - multi-model
	agent: SUPPLEMENTARY.brightPurple, // Purple - autonomous agents

	// Data nodes
	data: SUPPLEMENTARY.brightBlue,   // Bright blue - data/information
	output: PRIMARY.wasabiGreen,      // Green - successful output

	// Processing nodes
	lambda: '#F97316',                // Orange - custom functions
	subgraph: PRIMARY.infiniteBlue,   // Infinite Blue - nested workflows
	weighted_sampler: SUPPLEMENTARY.brightIndigo,

	// Special nodes
	webagent: SUPPLEMENTARY.brightPurple,
} as const;

// =============================================================================
// STATUS COLORS
// =============================================================================
// Execution status indicators

export const STATUS_COLORS = {
	pending: {
		color: '#9CA3AF',              // Gray
		bg: 'rgba(156, 163, 175, 0.15)',
		border: 'rgba(156, 163, 175, 0.3)',
	},
	running: {
		color: SUPPLEMENTARY.brightBlue,
		bg: DERIVED.brightBlueMuted,
		border: 'rgba(82, 184, 255, 0.4)',
	},
	completed: {
		color: PRIMARY.wasabiGreen,
		bg: DERIVED.wasabiGreenMuted,
		border: 'rgba(99, 223, 78, 0.4)',
	},
	failed: {
		color: '#EF4444',
		bg: 'rgba(239, 68, 68, 0.15)',
		border: 'rgba(239, 68, 68, 0.4)',
	},
	cancelled: {
		color: '#F59E0B',
		bg: 'rgba(245, 158, 11, 0.15)',
		border: 'rgba(245, 158, 11, 0.4)',
	},
	skipped: {
		color: '#6B7280',
		bg: 'rgba(107, 114, 128, 0.15)',
		border: 'rgba(107, 114, 128, 0.3)',
	},
} as const;

// =============================================================================
// SURFACE COLORS
// =============================================================================
// Background and surface colors for light/dark modes

export const SURFACES = {
	light: {
		surface: PRIMARY.white,
		surfaceSecondary: '#F9FAFB',   // Gray-50
		surfaceTertiary: '#F3F4F6',    // Gray-100
		surfaceHover: '#F3F4F6',
		surfaceSelected: DERIVED.infiniteBlueSubtle,
		surfaceInverse: PRIMARY.infiniteBlue,
		frost: 'rgba(255, 255, 255, 0.85)',
		frostSecondary: 'rgba(255, 255, 255, 0.6)',
	},
	dark: {
		surface: PRIMARY.infiniteBlue,
		surfaceSecondary: DERIVED.infiniteBlueMuted,
		surfaceTertiary: DERIVED.infiniteBlueLight,
		surfaceHover: DERIVED.infiniteBlueLight,
		surfaceSelected: SUPPLEMENTARY.brightIndigo,
		surfaceInverse: '#F9FAFB',
		frost: 'rgba(3, 45, 66, 0.85)',
		frostSecondary: 'rgba(3, 45, 66, 0.6)',
	},
} as const;

// =============================================================================
// GRADIENTS
// =============================================================================
// Brand gradients for visual interest

export const GRADIENTS = {
	// Primary gradient - Infinite Blue to Bright Blue
	primary: 'linear-gradient(135deg, #032D42 0%, #52B8FF 100%)',

	// Accent gradient - for highlights
	accent: 'linear-gradient(135deg, #63DF4E 0%, #52B8FF 100%)',

	// AI/LLM gradient
	ai: 'linear-gradient(135deg, #7661FF 0%, #BF71F2 100%)',

	// Success gradient
	success: 'linear-gradient(135deg, #63DF4E 0%, #4BC93A 100%)',

	// Dark background gradient
	darkBg: 'linear-gradient(180deg, #032D42 0%, #021E2D 100%)',

	// Subtle overlay
	overlay: 'linear-gradient(180deg, rgba(3, 45, 66, 0) 0%, rgba(3, 45, 66, 0.8) 100%)',
} as const;

// =============================================================================
// CSS VARIABLE NAMES
// =============================================================================
// For easy reference when using in CSS

export const CSS_VARS = {
	// Surface
	'--surface': 'surface',
	'--surface-secondary': 'surface-secondary',
	'--surface-tertiary': 'surface-tertiary',
	'--surface-hover': 'surface-hover',
	'--surface-selected': 'surface-selected',
	'--surface-inverse': 'surface-inverse',
	'--frost': 'frost',
	'--frost-secondary': 'frost-secondary',

	// Brand
	'--primary': 'primary',
	'--primary-hover': 'primary-hover',
	'--primary-light': 'primary-light',
	'--accent': 'accent',
	'--accent-hover': 'accent-hover',
} as const;

// =============================================================================
// TYPE EXPORTS
// =============================================================================

export type NodeColorKey = keyof typeof NODE_COLORS;
export type StatusKey = keyof typeof STATUS_COLORS;
export type SurfaceMode = 'light' | 'dark';
