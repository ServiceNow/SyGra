<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { Execution } from '$lib/stores/workflow.svelte';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import {
		X, Copy, CheckCircle2, XCircle, Clock, FileJson, Download,
		ExternalLink, Layers, Timer, AlertCircle, Play
	} from 'lucide-svelte';

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	const dispatch = createEventDispatcher<{ close: void }>();

	let copied = $state(false);

	let recordCount = $derived(() => {
		if (Array.isArray(execution.output_data)) {
			return execution.output_data.length;
		} else if (execution.output_data && typeof execution.output_data === 'object') {
			return 1;
		}
		return 0;
	});

	let statusConfig = $derived(() => {
		if (execution.status === 'completed') {
			return {
				bg: 'bg-green-100 dark:bg-green-900/30',
				text: 'text-green-700 dark:text-green-400',
				icon: CheckCircle2,
				label: 'Completed'
			};
		} else if (execution.status === 'failed') {
			return {
				bg: 'bg-red-100 dark:bg-red-900/30',
				text: 'text-red-700 dark:text-red-400',
				icon: XCircle,
				label: 'Failed'
			};
		} else if (execution.status === 'running') {
			return {
				bg: 'bg-blue-100 dark:bg-blue-900/30',
				text: 'text-blue-700 dark:text-blue-400',
				icon: Play,
				label: 'Running'
			};
		}
		return {
			bg: 'bg-gray-100 dark:bg-gray-700',
			text: 'text-gray-700 dark:text-gray-400',
			icon: Clock,
			label: execution.status
		};
	});

	async function copyOutput() {
		const text = execution.output_data ? JSON.stringify(execution.output_data, null, 2) : '';
		await navigator.clipboard.writeText(text);
		copied = true;
		setTimeout(() => copied = false, 2000);
	}

	function downloadOutput() {
		const text = execution.output_data ? JSON.stringify(execution.output_data, null, 2) : '';
		const blob = new Blob([text], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `output_${execution.id}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	function viewInRuns() {
		// Navigate to runs view with this run selected
		uiStore.setView('runs');
		uiStore.selectRun(execution.id);
		const url = new URL(window.location.href);
		url.searchParams.set('view', 'runs');
		url.searchParams.set('run', execution.id);
		window.history.pushState({}, '', url.toString());
		dispatch('close');
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dispatch('close');
		}
	}

	function formatDuration(ms: number | undefined): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
		const mins = Math.floor(ms / 60000);
		const secs = ((ms % 60000) / 1000).toFixed(0);
		return `${mins}m ${secs}s`;
	}

	function formatDate(dateString: string | undefined): string {
		if (!dateString) return '-';
		const date = new Date(dateString);
		return date.toLocaleString('en-US', {
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('close')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-4">
				<div class="w-10 h-10 rounded-xl {statusConfig().bg} flex items-center justify-center">
					<svelte:component this={statusConfig().icon} size={20} class={statusConfig().text} />
				</div>
				<div>
					<h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						Execution Results
					</h3>
					<div class="flex items-center gap-2 mt-0.5">
						<span class="text-xs text-gray-500 dark:text-gray-400">
							{execution.workflow_name || 'Workflow'}
						</span>
						<span class="text-gray-300 dark:text-gray-600">•</span>
						<span class="text-xs text-gray-500 dark:text-gray-400">
							{formatDate(execution.started_at)}
						</span>
					</div>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {statusConfig().bg} {statusConfig().text}">
					<svelte:component this={statusConfig().icon} size={12} />
					{statusConfig().label}
				</span>
				<button
					onclick={() => dispatch('close')}
					class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
				>
					<X size={18} />
				</button>
			</div>
		</div>

		<!-- Body -->
		<div class="flex-1 overflow-y-auto p-6 space-y-6">
			<!-- Summary stats -->
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
						<Timer size={14} />
						Duration
					</div>
					<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">
						{formatDuration(execution.duration_ms)}
					</div>
				</div>
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
						<FileJson size={14} />
						Records
					</div>
					<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">
						{recordCount()}
					</div>
				</div>
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
						<Layers size={14} />
						Nodes
					</div>
					<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">
						{Object.keys(execution.node_states).length}
					</div>
				</div>
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
						<Clock size={14} />
						Started
					</div>
					<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						{formatDate(execution.started_at)}
					</div>
				</div>
			</div>

			<!-- Output file -->
			{#if execution.output_file}
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
						<FileJson size={16} class="text-violet-500" />
						Output File
					</div>
					<div class="bg-gray-900 dark:bg-gray-950 rounded-lg p-3">
						<code class="text-sm text-green-400 break-all font-mono">
							{execution.output_file}
						</code>
					</div>
				</div>
			{/if}

			<!-- Error -->
			{#if execution.error}
				<div class="bg-red-50 dark:bg-red-900/10 rounded-xl p-4 border border-red-200 dark:border-red-800">
					<div class="flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-400 mb-3">
						<AlertCircle size={16} />
						Error
					</div>
					<pre class="text-sm text-red-800 dark:text-red-400 whitespace-pre-wrap font-mono bg-red-100 dark:bg-red-900/20 rounded-lg p-3">{execution.error}</pre>
				</div>
			{/if}

			<!-- Output data -->
			{#if execution.output_data}
				<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center justify-between mb-3">
						<div class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
							<FileJson size={16} class="text-violet-500" />
							Output Data
						</div>
						<div class="flex items-center gap-1">
							<button
								onclick={copyOutput}
								class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
							>
								{#if copied}
									<CheckCircle2 size={14} class="text-green-500" />
									Copied!
								{:else}
									<Copy size={14} />
									Copy
								{/if}
							</button>
							<button
								onclick={downloadOutput}
								class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
							>
								<Download size={14} />
								Download
							</button>
						</div>
					</div>
					<div class="bg-gray-900 dark:bg-gray-950 rounded-lg p-4 max-h-80 overflow-auto">
						<pre class="text-sm text-gray-300 whitespace-pre-wrap font-mono">{JSON.stringify(execution.output_data, null, 2)}</pre>
					</div>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-between px-6 py-4 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl border-t border-gray-200 dark:border-gray-800">
			<button
				onclick={viewInRuns}
				class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
			>
				<ExternalLink size={16} />
				View in Runs
			</button>
			<button
				onclick={() => dispatch('close')}
				class="px-5 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium text-white transition-colors"
			>
				Close
			</button>
		</div>
	</div>
</div>
