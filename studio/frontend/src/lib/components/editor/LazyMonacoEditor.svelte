<script lang="ts">
	import { onMount } from 'svelte';
	import type { EditorTheme } from '$lib/stores/theme.svelte';

	interface Props {
		value?: string;
		language?: string;
		theme?: EditorTheme;
		height?: string;
		readonly?: boolean;
		minimap?: boolean;
		lineNumbers?: boolean;
		wordWrap?: boolean;
		fontSize?: number;
		placeholder?: string;
		breakpointsEnabled?: boolean;
		breakpoints?: number[];
		currentLine?: number | null;
	}

	let {
		value = $bindable(''),
		language = 'python',
		theme,
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

	let MonacoEditor: typeof import('./MonacoEditor.svelte').default | null = $state(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const module = await import('./MonacoEditor.svelte');
			MonacoEditor = module.default;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load editor';
			console.error('Failed to load Monaco editor:', e);
		} finally {
			loading = false;
		}
	});
</script>

{#if loading}
	<div
		class="flex items-center justify-center bg-gray-900 rounded-lg text-gray-500 text-sm"
		style="height: {height}"
	>
		<div class="flex items-center gap-2">
			<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
				<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
				<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
			</svg>
			<span>Loading editor...</span>
		</div>
	</div>
{:else if error}
	<div
		class="flex items-center justify-center bg-red-900/20 rounded-lg text-red-400 text-sm"
		style="height: {height}"
	>
		<span>Failed to load editor: {error}</span>
	</div>
{:else if MonacoEditor}
	<MonacoEditor
		bind:value
		{language}
		{theme}
		{height}
		{readonly}
		{minimap}
		{lineNumbers}
		{wordWrap}
		{fontSize}
		{placeholder}
		{breakpointsEnabled}
		bind:breakpoints
		{currentLine}
		on:change
		on:save
		on:breakpointsChange
	/>
{/if}
