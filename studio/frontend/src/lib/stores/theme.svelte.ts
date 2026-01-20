/**
 * Theme Store - Manages dark/light mode and editor theme with localStorage persistence
 */

const STORAGE_KEY = 'sygra-studio-theme';
const EDITOR_THEME_STORAGE_KEY = 'sygra-studio-editor-theme';

type Theme = 'light' | 'dark' | 'system';

// Monaco Editor themes - includes built-in and custom themes
export type EditorTheme =
	| 'vs' | 'vs-dark' | 'hc-black' | 'hc-light'  // Built-in
	| 'monokai' | 'dracula' | 'github-dark' | 'github-light'  // Popular dark/light
	| 'solarized-dark' | 'solarized-light'  // Solarized
	| 'nord' | 'one-dark-pro' | 'tokyo-night';  // Modern favorites

export interface EditorThemeConfig {
	id: EditorTheme;
	name: string;
	description: string;
	category: 'light' | 'dark' | 'high-contrast';
	base: 'vs' | 'vs-dark' | 'hc-black' | 'hc-light';  // Monaco base theme
	preview: {
		bg: string;
		border: string;
		gutter: string;
		text: string;
		keyword: string;
		string: string;
		comment: string;
		function: string;
		lineNumber: string;
	};
	// Monaco theme definition for custom themes
	themeData?: {
		base: 'vs' | 'vs-dark' | 'hc-black' | 'hc-light';
		inherit: boolean;
		rules: Array<{ token: string; foreground?: string; fontStyle?: string }>;
		colors: Record<string, string>;
	};
}

export const EDITOR_THEMES: EditorThemeConfig[] = [
	// ===== LIGHT THEMES =====
	{
		id: 'vs',
		name: 'Light',
		description: 'Clean and minimal',
		category: 'light',
		base: 'vs',
		preview: {
			bg: '#ffffff',
			border: '#e4e4e4',
			gutter: '#f5f5f5',
			text: '#000000',
			keyword: '#0000ff',
			string: '#a31515',
			comment: '#008000',
			function: '#795e26',
			lineNumber: '#237893'
		}
	},
	{
		id: 'github-light',
		name: 'GitHub Light',
		description: 'Clean GitHub style',
		category: 'light',
		base: 'vs',
		preview: {
			bg: '#ffffff',
			border: '#e1e4e8',
			gutter: '#fafbfc',
			text: '#24292e',
			keyword: '#d73a49',
			string: '#032f62',
			comment: '#6a737d',
			function: '#6f42c1',
			lineNumber: '#959da5'
		},
		themeData: {
			base: 'vs',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'd73a49' },
				{ token: 'string', foreground: '032f62' },
				{ token: 'comment', foreground: '6a737d', fontStyle: 'italic' },
				{ token: 'function', foreground: '6f42c1' },
				{ token: 'variable', foreground: '005cc5' },
				{ token: 'number', foreground: '005cc5' },
				{ token: 'type', foreground: '22863a' },
			],
			colors: {
				'editor.background': '#ffffff',
				'editor.foreground': '#24292e',
				'editor.lineHighlightBackground': '#f6f8fa',
				'editorLineNumber.foreground': '#959da5',
				'editorGutter.background': '#fafbfc',
			}
		}
	},
	{
		id: 'solarized-light',
		name: 'Solarized Light',
		description: 'Warm and easy',
		category: 'light',
		base: 'vs',
		preview: {
			bg: '#fdf6e3',
			border: '#eee8d5',
			gutter: '#eee8d5',
			text: '#657b83',
			keyword: '#859900',
			string: '#2aa198',
			comment: '#93a1a1',
			function: '#268bd2',
			lineNumber: '#93a1a1'
		},
		themeData: {
			base: 'vs',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: '859900' },
				{ token: 'string', foreground: '2aa198' },
				{ token: 'comment', foreground: '93a1a1', fontStyle: 'italic' },
				{ token: 'function', foreground: '268bd2' },
				{ token: 'variable', foreground: 'b58900' },
				{ token: 'number', foreground: 'd33682' },
				{ token: 'type', foreground: 'cb4b16' },
			],
			colors: {
				'editor.background': '#fdf6e3',
				'editor.foreground': '#657b83',
				'editor.lineHighlightBackground': '#eee8d5',
				'editorLineNumber.foreground': '#93a1a1',
				'editorGutter.background': '#eee8d5',
			}
		}
	},

	// ===== DARK THEMES =====
	{
		id: 'vs-dark',
		name: 'Dark',
		description: 'Classic VS Code dark',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#1e1e1e',
			border: '#3c3c3c',
			gutter: '#252526',
			text: '#d4d4d4',
			keyword: '#569cd6',
			string: '#ce9178',
			comment: '#6a9955',
			function: '#dcdcaa',
			lineNumber: '#858585'
		}
	},
	{
		id: 'monokai',
		name: 'Monokai',
		description: 'Vibrant classic',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#272822',
			border: '#3e3d32',
			gutter: '#272822',
			text: '#f8f8f2',
			keyword: '#f92672',
			string: '#e6db74',
			comment: '#75715e',
			function: '#a6e22e',
			lineNumber: '#90908a'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'f92672' },
				{ token: 'string', foreground: 'e6db74' },
				{ token: 'comment', foreground: '75715e', fontStyle: 'italic' },
				{ token: 'function', foreground: 'a6e22e' },
				{ token: 'variable', foreground: 'f8f8f2' },
				{ token: 'number', foreground: 'ae81ff' },
				{ token: 'type', foreground: '66d9ef', fontStyle: 'italic' },
			],
			colors: {
				'editor.background': '#272822',
				'editor.foreground': '#f8f8f2',
				'editor.lineHighlightBackground': '#3e3d32',
				'editorLineNumber.foreground': '#90908a',
				'editorGutter.background': '#272822',
			}
		}
	},
	{
		id: 'dracula',
		name: 'Dracula',
		description: 'Dark and colorful',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#282a36',
			border: '#44475a',
			gutter: '#282a36',
			text: '#f8f8f2',
			keyword: '#ff79c6',
			string: '#f1fa8c',
			comment: '#6272a4',
			function: '#50fa7b',
			lineNumber: '#6272a4'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'ff79c6' },
				{ token: 'string', foreground: 'f1fa8c' },
				{ token: 'comment', foreground: '6272a4', fontStyle: 'italic' },
				{ token: 'function', foreground: '50fa7b' },
				{ token: 'variable', foreground: 'f8f8f2' },
				{ token: 'number', foreground: 'bd93f9' },
				{ token: 'type', foreground: '8be9fd', fontStyle: 'italic' },
			],
			colors: {
				'editor.background': '#282a36',
				'editor.foreground': '#f8f8f2',
				'editor.lineHighlightBackground': '#44475a',
				'editorLineNumber.foreground': '#6272a4',
				'editorGutter.background': '#282a36',
			}
		}
	},
	{
		id: 'github-dark',
		name: 'GitHub Dark',
		description: 'GitHub\'s dark mode',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#0d1117',
			border: '#30363d',
			gutter: '#0d1117',
			text: '#c9d1d9',
			keyword: '#ff7b72',
			string: '#a5d6ff',
			comment: '#8b949e',
			function: '#d2a8ff',
			lineNumber: '#484f58'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'ff7b72' },
				{ token: 'string', foreground: 'a5d6ff' },
				{ token: 'comment', foreground: '8b949e', fontStyle: 'italic' },
				{ token: 'function', foreground: 'd2a8ff' },
				{ token: 'variable', foreground: 'ffa657' },
				{ token: 'number', foreground: '79c0ff' },
				{ token: 'type', foreground: '7ee787' },
			],
			colors: {
				'editor.background': '#0d1117',
				'editor.foreground': '#c9d1d9',
				'editor.lineHighlightBackground': '#161b22',
				'editorLineNumber.foreground': '#484f58',
				'editorGutter.background': '#0d1117',
			}
		}
	},
	{
		id: 'solarized-dark',
		name: 'Solarized Dark',
		description: 'Precision colors',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#002b36',
			border: '#073642',
			gutter: '#073642',
			text: '#839496',
			keyword: '#859900',
			string: '#2aa198',
			comment: '#586e75',
			function: '#268bd2',
			lineNumber: '#586e75'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: '859900' },
				{ token: 'string', foreground: '2aa198' },
				{ token: 'comment', foreground: '586e75', fontStyle: 'italic' },
				{ token: 'function', foreground: '268bd2' },
				{ token: 'variable', foreground: 'b58900' },
				{ token: 'number', foreground: 'd33682' },
				{ token: 'type', foreground: 'cb4b16' },
			],
			colors: {
				'editor.background': '#002b36',
				'editor.foreground': '#839496',
				'editor.lineHighlightBackground': '#073642',
				'editorLineNumber.foreground': '#586e75',
				'editorGutter.background': '#073642',
			}
		}
	},
	{
		id: 'nord',
		name: 'Nord',
		description: 'Arctic, north-bluish',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#2e3440',
			border: '#3b4252',
			gutter: '#2e3440',
			text: '#d8dee9',
			keyword: '#81a1c1',
			string: '#a3be8c',
			comment: '#616e88',
			function: '#88c0d0',
			lineNumber: '#4c566a'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: '81a1c1' },
				{ token: 'string', foreground: 'a3be8c' },
				{ token: 'comment', foreground: '616e88', fontStyle: 'italic' },
				{ token: 'function', foreground: '88c0d0' },
				{ token: 'variable', foreground: 'd8dee9' },
				{ token: 'number', foreground: 'b48ead' },
				{ token: 'type', foreground: '8fbcbb' },
			],
			colors: {
				'editor.background': '#2e3440',
				'editor.foreground': '#d8dee9',
				'editor.lineHighlightBackground': '#3b4252',
				'editorLineNumber.foreground': '#4c566a',
				'editorGutter.background': '#2e3440',
			}
		}
	},
	{
		id: 'one-dark-pro',
		name: 'One Dark Pro',
		description: 'Atom\'s iconic theme',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#282c34',
			border: '#3e4451',
			gutter: '#282c34',
			text: '#abb2bf',
			keyword: '#c678dd',
			string: '#98c379',
			comment: '#5c6370',
			function: '#61afef',
			lineNumber: '#4b5263'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'c678dd' },
				{ token: 'string', foreground: '98c379' },
				{ token: 'comment', foreground: '5c6370', fontStyle: 'italic' },
				{ token: 'function', foreground: '61afef' },
				{ token: 'variable', foreground: 'e06c75' },
				{ token: 'number', foreground: 'd19a66' },
				{ token: 'type', foreground: 'e5c07b' },
			],
			colors: {
				'editor.background': '#282c34',
				'editor.foreground': '#abb2bf',
				'editor.lineHighlightBackground': '#2c313c',
				'editorLineNumber.foreground': '#4b5263',
				'editorGutter.background': '#282c34',
			}
		}
	},
	{
		id: 'tokyo-night',
		name: 'Tokyo Night',
		description: 'Clean, dark Tokyo',
		category: 'dark',
		base: 'vs-dark',
		preview: {
			bg: '#1a1b26',
			border: '#292e42',
			gutter: '#1a1b26',
			text: '#a9b1d6',
			keyword: '#bb9af7',
			string: '#9ece6a',
			comment: '#565f89',
			function: '#7aa2f7',
			lineNumber: '#3b4261'
		},
		themeData: {
			base: 'vs-dark',
			inherit: true,
			rules: [
				{ token: 'keyword', foreground: 'bb9af7' },
				{ token: 'string', foreground: '9ece6a' },
				{ token: 'comment', foreground: '565f89', fontStyle: 'italic' },
				{ token: 'function', foreground: '7aa2f7' },
				{ token: 'variable', foreground: 'c0caf5' },
				{ token: 'number', foreground: 'ff9e64' },
				{ token: 'type', foreground: '2ac3de' },
			],
			colors: {
				'editor.background': '#1a1b26',
				'editor.foreground': '#a9b1d6',
				'editor.lineHighlightBackground': '#292e42',
				'editorLineNumber.foreground': '#3b4261',
				'editorGutter.background': '#1a1b26',
			}
		}
	},

	// ===== HIGH CONTRAST THEMES =====
	{
		id: 'hc-black',
		name: 'High Contrast Dark',
		description: 'Maximum visibility',
		category: 'high-contrast',
		base: 'hc-black',
		preview: {
			bg: '#000000',
			border: '#6fc3df',
			gutter: '#000000',
			text: '#ffffff',
			keyword: '#569cd6',
			string: '#ce9178',
			comment: '#7ca668',
			function: '#dcdcaa',
			lineNumber: '#ffffff'
		}
	},
	{
		id: 'hc-light',
		name: 'High Contrast Light',
		description: 'Bright and clear',
		category: 'high-contrast',
		base: 'hc-light',
		preview: {
			bg: '#ffffff',
			border: '#0000cd',
			gutter: '#ffffff',
			text: '#292929',
			keyword: '#0000ff',
			string: '#a31515',
			comment: '#008000',
			function: '#5c2d91',
			lineNumber: '#292929'
		}
	}
];

interface ThemeState {
	theme: Theme;
	isDark: boolean;
}

// Reactive state
let _theme = $state<Theme>('system');
let _isDark = $state(false);
let _editorTheme = $state<EditorTheme>('vs-dark');

// Subscribers for editor theme changes
type EditorThemeSubscriber = (theme: EditorTheme) => void;
const editorThemeSubscribers = new Set<EditorThemeSubscriber>();

// Subscribe to editor theme changes - returns unsubscribe function
export function subscribeToEditorTheme(callback: EditorThemeSubscriber): () => void {
	editorThemeSubscribers.add(callback);
	// Immediately call with current value
	callback(_editorTheme);
	// Return unsubscribe function
	return () => {
		editorThemeSubscribers.delete(callback);
	};
}

// Notify all subscribers of theme change
function notifyEditorThemeSubscribers() {
	editorThemeSubscribers.forEach(callback => callback(_editorTheme));
}

function createThemeStore() {

	// Initialize from localStorage or system preference
	function init() {
		if (typeof window === 'undefined') return;

		const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
		if (stored && ['light', 'dark', 'system'].includes(stored)) {
			_theme = stored;
		}

		// Initialize editor theme
		const storedEditorTheme = localStorage.getItem(EDITOR_THEME_STORAGE_KEY) as EditorTheme | null;
		if (storedEditorTheme && EDITOR_THEMES.some(t => t.id === storedEditorTheme)) {
			_editorTheme = storedEditorTheme;
		}

		updateDarkMode();

		// Listen for system theme changes
		if (window.matchMedia) {
			window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
				if (_theme === 'system') {
					updateDarkMode();
				}
			});
		}
	}

	function updateDarkMode() {
		if (typeof window === 'undefined') return;

		if (_theme === 'system') {
			_isDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
		} else {
			_isDark = _theme === 'dark';
		}

		// Apply to document
		if (_isDark) {
			document.documentElement.classList.add('dark');
		} else {
			document.documentElement.classList.remove('dark');
		}
	}

	function setTheme(newTheme: Theme) {
		_theme = newTheme;
		if (typeof window !== 'undefined') {
			localStorage.setItem(STORAGE_KEY, newTheme);
		}
		updateDarkMode();
	}

	function toggle() {
		// Simple toggle between light and dark
		setTheme(_isDark ? 'light' : 'dark');
	}

	function setEditorTheme(newTheme: EditorTheme) {
		_editorTheme = newTheme;
		if (typeof window !== 'undefined') {
			localStorage.setItem(EDITOR_THEME_STORAGE_KEY, newTheme);
		}
		// Notify all subscribers of the change
		notifyEditorThemeSubscribers();
	}

	return {
		get theme() { return _theme; },
		get isDark() { return _isDark; },
		get editorTheme() { return _editorTheme; },
		init,
		setTheme,
		setEditorTheme,
		toggle
	};
}

export const themeStore = createThemeStore();
