/**
 * Theme Store - Manages dark/light mode with localStorage persistence
 */

const STORAGE_KEY = 'sygra-studio-theme';

type Theme = 'light' | 'dark' | 'system';

interface ThemeState {
	theme: Theme;
	isDark: boolean;
}

function createThemeStore() {
	let theme = $state<Theme>('system');
	let isDark = $state(false);

	// Initialize from localStorage or system preference
	function init() {
		if (typeof window === 'undefined') return;

		const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
		if (stored && ['light', 'dark', 'system'].includes(stored)) {
			theme = stored;
		}

		updateDarkMode();

		// Listen for system theme changes
		if (window.matchMedia) {
			window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
				if (theme === 'system') {
					updateDarkMode();
				}
			});
		}
	}

	function updateDarkMode() {
		if (typeof window === 'undefined') return;

		if (theme === 'system') {
			isDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
		} else {
			isDark = theme === 'dark';
		}

		// Apply to document
		if (isDark) {
			document.documentElement.classList.add('dark');
		} else {
			document.documentElement.classList.remove('dark');
		}
	}

	function setTheme(newTheme: Theme) {
		theme = newTheme;
		if (typeof window !== 'undefined') {
			localStorage.setItem(STORAGE_KEY, newTheme);
		}
		updateDarkMode();
	}

	function toggle() {
		// Simple toggle between light and dark
		setTheme(isDark ? 'light' : 'dark');
	}

	return {
		get theme() { return theme; },
		get isDark() { return isDark; },
		init,
		setTheme,
		toggle
	};
}

export const themeStore = createThemeStore();
