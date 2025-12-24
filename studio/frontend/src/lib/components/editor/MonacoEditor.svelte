<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import loader from '@monaco-editor/loader';
	import type * as Monaco from 'monaco-editor';

	interface Props {
		value?: string;
		language?: string;
		theme?: 'vs' | 'vs-dark' | 'hc-black';
		height?: string;
		readonly?: boolean;
		minimap?: boolean;
		lineNumbers?: boolean;
		wordWrap?: boolean;
		fontSize?: number;
		placeholder?: string;
		breakpointsEnabled?: boolean;
		breakpoints?: number[];
		currentLine?: number | null;  // Line where execution is paused
	}

	let {
		value = $bindable(''),
		language = 'python',
		theme = 'vs-dark',
		height = '200px',
		readonly = false,
		minimap = false,
		lineNumbers = true,
		wordWrap = true,
		fontSize = 13,
		placeholder = '',
		breakpointsEnabled = false,
		breakpoints = $bindable([]),
		currentLine = null
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		change: string;
		save: void;
		breakpointsChange: number[];
	}>();

	let container: HTMLDivElement;
	let editor: Monaco.editor.IStandaloneCodeEditor | null = null;
	let monaco: typeof Monaco | null = null;
	let isInitialized = $state(false);
	let breakpointDecorations: string[] = [];
	let currentLineDecorations: string[] = [];

	onMount(async () => {
		monaco = await loader.init();

		if (!container) return;

		editor = monaco.editor.create(container, {
			value: value || '',
			language,
			theme,
			readOnly: readonly,
			minimap: { enabled: minimap },
			lineNumbers: lineNumbers ? 'on' : 'off',
			wordWrap: wordWrap ? 'on' : 'off',
			fontSize,
			automaticLayout: true,
			scrollBeyondLastLine: false,
			renderLineHighlight: 'line',
			folding: true,
			lineDecorationsWidth: breakpointsEnabled ? 15 : 5,
			lineNumbersMinChars: 3,
			padding: { top: 8, bottom: 8 },
			scrollbar: {
				verticalScrollbarSize: 8,
				horizontalScrollbarSize: 8,
			},
			overviewRulerBorder: false,
			hideCursorInOverviewRuler: true,
			tabSize: 4,
			insertSpaces: true,
			glyphMargin: breakpointsEnabled,
		});

		editor.onDidChangeModelContent(() => {
			if (editor) {
				const newValue = editor.getValue();
				if (newValue !== value) {
					value = newValue;
					dispatch('change', newValue);
				}
			}
		});

		// Ctrl+S / Cmd+S to save
		editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
			dispatch('save');
		});

		// Handle gutter clicks for breakpoints
		if (breakpointsEnabled) {
			editor.onMouseDown((e) => {
				if (!editor || !monaco) return;

				// Check if click is in the gutter margin area
				const target = e.target;
				if (
					target.type === monaco.editor.MouseTargetType.GUTTER_GLYPH_MARGIN ||
					target.type === monaco.editor.MouseTargetType.GUTTER_LINE_NUMBERS ||
					target.type === monaco.editor.MouseTargetType.GUTTER_LINE_DECORATIONS
				) {
					const lineNumber = target.position?.lineNumber;
					if (lineNumber) {
						toggleBreakpoint(lineNumber);
					}
				}
			});
		}

		isInitialized = true;

		// Apply initial breakpoints if any
		if (breakpoints.length > 0) {
			updateBreakpointDecorations();
		}
	});

	function toggleBreakpoint(lineNumber: number) {
		const index = breakpoints.indexOf(lineNumber);
		if (index === -1) {
			breakpoints = [...breakpoints, lineNumber].sort((a, b) => a - b);
		} else {
			breakpoints = breakpoints.filter(l => l !== lineNumber);
		}
		updateBreakpointDecorations();
		dispatch('breakpointsChange', breakpoints);
	}

	function updateBreakpointDecorations() {
		if (!editor || !monaco) return;

		const decorations: Monaco.editor.IModelDeltaDecoration[] = breakpoints.map(line => ({
			range: new monaco.Range(line, 1, line, 1),
			options: {
				isWholeLine: true,
				glyphMarginClassName: 'breakpoint-glyph',
				glyphMarginHoverMessage: { value: `Breakpoint at line ${line}` },
				className: 'breakpoint-line',
				marginClassName: 'breakpoint-line-margin',
				stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges
			}
		}));

		breakpointDecorations = editor.deltaDecorations(breakpointDecorations, decorations);
	}

	function updateCurrentLineDecoration() {
		if (!editor || !monaco) return;

		if (currentLine && currentLine > 0) {
			const decorations: Monaco.editor.IModelDeltaDecoration[] = [{
				range: new monaco.Range(currentLine, 1, currentLine, 1),
				options: {
					isWholeLine: true,
					className: 'current-execution-line',
					glyphMarginClassName: 'current-execution-glyph',
					stickiness: monaco.editor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges
				}
			}];
			currentLineDecorations = editor.deltaDecorations(currentLineDecorations, decorations);

			// Scroll to the current line
			editor.revealLineInCenter(currentLine);
		} else {
			currentLineDecorations = editor.deltaDecorations(currentLineDecorations, []);
		}
	}

	// Update breakpoint decorations when breakpoints prop changes externally
	$effect(() => {
		if (editor && monaco && isInitialized && breakpointsEnabled) {
			// Reference breakpoints to track changes
			const _bp = breakpoints;
			updateBreakpointDecorations();
		}
	});

	// Update current line decoration when currentLine prop changes
	$effect(() => {
		if (editor && monaco && isInitialized) {
			const _line = currentLine;
			updateCurrentLineDecoration();
		}
	});

	onDestroy(() => {
		if (editor) {
			editor.dispose();
			editor = null;
		}
	});

	// Update editor when value prop changes externally
	$effect(() => {
		if (editor && isInitialized) {
			const currentValue = editor.getValue();
			if (value !== currentValue) {
				editor.setValue(value || '');
			}
		}
	});

	// Update editor read-only state when prop changes
	$effect(() => {
		// Explicitly reference readonly to track it
		const isReadOnly = readonly;
		if (editor && isInitialized) {
			editor.updateOptions({ readOnly: isReadOnly });
		}
	});

	// Update other editor options when props change
	$effect(() => {
		if (editor && isInitialized) {
			editor.updateOptions({
				theme,
				fontSize,
				wordWrap: wordWrap ? 'on' : 'off',
				lineNumbers: lineNumbers ? 'on' : 'off',
			});
		}
	});

	// Update language when it changes
	$effect(() => {
		if (editor && monaco && isInitialized) {
			const model = editor.getModel();
			if (model) {
				monaco.editor.setModelLanguage(model, language);
			}
		}
	});

	export function focus() {
		editor?.focus();
	}

	export function getValue(): string {
		return editor?.getValue() ?? value;
	}

	export function setValue(newValue: string) {
		if (editor) {
			editor.setValue(newValue);
		}
		value = newValue;
	}

	export function format() {
		editor?.getAction('editor.action.formatDocument')?.run();
	}
</script>

<div class="monaco-editor-wrapper relative rounded-lg overflow-hidden border border-gray-300 dark:border-gray-700">
	{#if !isInitialized}
		<div
			class="flex items-center justify-center bg-gray-100 dark:bg-gray-800 text-gray-500 text-sm"
			style="height: {height}"
		>
			Loading editor...
		</div>
	{/if}
	<div
		bind:this={container}
		class="monaco-container"
		class:hidden={!isInitialized}
		style="height: {height}"
	></div>
	{#if placeholder && !value && isInitialized}
		<div class="absolute top-2 left-12 text-gray-400 text-sm pointer-events-none font-mono">
			{placeholder}
		</div>
	{/if}
</div>

<style lang="css">
	.monaco-editor-wrapper {
		width: 100%;
	}
	.monaco-container {
		width: 100%;
	}
	:global(.monaco-editor) {
		border-radius: 0.5rem;
	}
	:global(.monaco-editor .margin) {
		background-color: transparent !important;
	}

	/* Breakpoint glyph - red dot in gutter */
	:global(.breakpoint-glyph) {
		background-color: #e51400;
		border-radius: 50%;
		width: 10px !important;
		height: 10px !important;
		margin-left: 4px;
		margin-top: 4px;
		cursor: pointer;
		box-shadow: 0 0 4px rgba(229, 20, 0, 0.5);
	}

	/* Breakpoint line background - subtle red tint */
	:global(.breakpoint-line) {
		background-color: rgba(229, 20, 0, 0.15) !important;
	}

	/* Breakpoint line margin - darker red strip */
	:global(.breakpoint-line-margin) {
		background-color: rgba(229, 20, 0, 0.3) !important;
	}

	/* Current execution line - bright yellow highlight (when paused at breakpoint) */
	:global(.current-execution-line) {
		background-color: rgba(255, 238, 0, 0.35) !important;
		border-left: 4px solid #ffee00 !important;
		box-shadow: inset 0 0 0 1px rgba(255, 238, 0, 0.3) !important;
	}

	/* Current execution glyph - bright yellow arrow */
	:global(.current-execution-glyph) {
		background-color: rgba(255, 238, 0, 0.2) !important;
	}
	:global(.current-execution-glyph::before) {
		content: '▶';
		color: #ffee00;
		font-size: 14px;
		font-weight: bold;
		position: absolute;
		left: 2px;
		top: -1px;
		text-shadow: 0 0 8px rgba(255, 238, 0, 1), 0 0 2px #000;
		animation: pulse-glow 1.5s ease-in-out infinite;
	}

	@keyframes pulse-glow {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.6; }
	}

	/* Hover effect for gutter area when breakpoints enabled */
	:global(.monaco-editor .margin-view-overlays .line-numbers:hover) {
		cursor: pointer;
	}

	/* Make the glyph margin clickable area more obvious */
	:global(.monaco-editor .glyph-margin:hover) {
		background-color: rgba(229, 20, 0, 0.1);
	}
</style>
