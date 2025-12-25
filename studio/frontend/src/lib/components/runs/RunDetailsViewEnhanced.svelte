<script lang="ts">
	import { onMount } from 'svelte';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import type { Execution, ExecutionMetadata } from '$lib/stores/workflow.svelte';
	import {
		X, CheckCircle2, XCircle, Clock, Loader2, FileJson, FileText,
		Calendar, Timer, Hash, Database, ChevronDown, Copy, Check,
		Activity, ArrowRight, DollarSign, Zap, Cpu, GitBranch,
		BarChart3, Server, Box, TrendingUp, ArrowLeft, PieChart, Gauge,
		Download, Star, Play, Share2, ExternalLink, RefreshCw
	} from 'lucide-svelte';
	import { Chart, registerables } from 'chart.js';
	import LogViewer from './LogViewer.svelte';
	import DataTableViewer from '$lib/components/common/DataTableViewer.svelte';
	import RunExecutionGraph from './RunExecutionGraph.svelte';

	Chart.register(...registerables);

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	// Tab state
	type TabId = 'overview' | 'execution' | 'output' | 'logs' | 'metadata';
	let activeTab = $state<TabId>('overview');

	// Copy state
	let copiedField = $state<string | null>(null);

	// Status styling
	const statusConfig = {
		pending: { color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', icon: Clock, label: 'Pending' },
		running: { color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', icon: Loader2, label: 'Running' },
		completed: { color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: CheckCircle2, label: 'Completed' },
		failed: { color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', icon: XCircle, label: 'Failed' },
		cancelled: { color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', icon: XCircle, label: 'Cancelled' },
	};

	let status = $derived(statusConfig[execution.status as keyof typeof statusConfig] || statusConfig.pending);
	let StatusIcon = $derived(status.icon);

	// Format helpers
	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const seconds = Math.floor(ms / 1000);
		if (seconds < 60) return `${seconds}s`;
		const minutes = Math.floor(seconds / 60);
		const remainingSeconds = seconds % 60;
		return `${minutes}m ${remainingSeconds}s`;
	}

	function formatDate(date?: string): string {
		if (!date) return '-';
		return new Date(date).toLocaleString();
	}

	function formatRelativeTime(date?: string): string {
		if (!date) return '-';
		const d = new Date(date);
		const now = new Date();
		const diff = now.getTime() - d.getTime();

		if (diff < 60000) return 'Just now';
		if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
		if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
		return formatDate(date);
	}

	async function copyToClipboard(text: string, field: string) {
		await navigator.clipboard.writeText(text);
		copiedField = field;
		setTimeout(() => copiedField = null, 2000);
	}

	let sampleOutput = $derived(() => {
		if (!execution.output_data) return null;
		if (Array.isArray(execution.output_data)) {
			return execution.output_data.slice(0, 5);
		}
		return execution.output_data;
	});

	let outputCount = $derived(() => {
		if (!execution.output_data) return 0;
		if (Array.isArray(execution.output_data)) {
			return execution.output_data.length;
		}
		return 1;
	});

	let metadata = $derived(execution.metadata);

	// Chart refs
	let tokenPieCanvas: HTMLCanvasElement;
	let modelTokensCanvas: HTMLCanvasElement;

	// Chart instances
	let tokenPieChart: Chart | null = null;
	let modelTokensChart: Chart | null = null;

	function initCharts() {
		if (!metadata) return;

		// Token distribution pie chart
		if (tokenPieCanvas && metadata.aggregate_statistics) {
			const promptTokens = metadata.aggregate_statistics.tokens.total_prompt_tokens;
			const completionTokens = metadata.aggregate_statistics.tokens.total_completion_tokens;

			if (tokenPieChart) tokenPieChart.destroy();
			tokenPieChart = new Chart(tokenPieCanvas, {
				type: 'doughnut',
				data: {
					labels: ['Prompt', 'Completion'],
					datasets: [{
						data: [promptTokens, completionTokens],
						backgroundColor: ['rgba(139, 92, 246, 0.8)', 'rgba(59, 130, 246, 0.8)'],
						borderWidth: 0
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: '65%',
					plugins: {
						legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } }
					}
				}
			});
		}

		// Model tokens chart
		if (modelTokensCanvas && metadata.models && Object.keys(metadata.models).length > 0) {
			const modelNames = Object.keys(metadata.models);
			const promptTokens = modelNames.map(n => metadata.models[n].token_statistics.total_prompt_tokens);
			const completionTokens = modelNames.map(n => metadata.models[n].token_statistics.total_completion_tokens);

			if (modelTokensChart) modelTokensChart.destroy();
			modelTokensChart = new Chart(modelTokensCanvas, {
				type: 'bar',
				data: {
					labels: modelNames,
					datasets: [
						{ label: 'Prompt', data: promptTokens, backgroundColor: 'rgba(139, 92, 246, 0.8)', borderRadius: 4 },
						{ label: 'Completion', data: completionTokens, backgroundColor: 'rgba(59, 130, 246, 0.8)', borderRadius: 4 }
					]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } }
				}
			});
		}
	}

	// Initialize charts when tab changes to metadata
	$effect(() => {
		if (activeTab === 'metadata' && metadata) {
			setTimeout(initCharts, 50);
		}
	});

	onMount(() => {
		return () => {
			tokenPieChart?.destroy();
			modelTokensChart?.destroy();
		};
	});

	function formatCost(usd: number): string {
		if (usd < 0.01) return `$${(usd * 100).toFixed(3)}¢`;
		return `$${usd.toFixed(4)}`;
	}

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toLocaleString();
	}

	function formatPercent(rate: number): string {
		return `${(rate * 100).toFixed(1)}%`;
	}

	function formatLatency(seconds: number): string {
		if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
		return `${seconds.toFixed(2)}s`;
	}

	function goBack() {
		uiStore.clearSelectedRun();
		const url = new URL(window.location.href);
		url.searchParams.delete('run');
		window.history.pushState({}, '', url.toString());
	}

	async function downloadOutput() {
		if (!execution.output_data) return;
		const data = JSON.stringify(execution.output_data, null, 2);
		const blob = new Blob([data], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `run-${execution.id.slice(0, 8)}-output.json`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800">
		<!-- Top bar with back button and actions -->
		<div class="flex items-center justify-between px-6 py-4">
			<div class="flex items-center gap-4">
				<button
					onclick={goBack}
					class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
					title="Back to runs"
				>
					<ArrowLeft size={20} class="text-gray-500" />
				</button>

				<div>
					<div class="flex items-center gap-3">
						<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">
							{execution.workflow_name || 'Unknown Workflow'}
						</h1>
						<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {status.color} {status.bg}">
							<StatusIcon size={12} class={execution.status === 'running' ? 'animate-spin' : ''} />
							{status.label}
						</span>
					</div>
					<div class="flex items-center gap-3 text-sm text-gray-500 mt-1">
						<span class="font-mono">{execution.id}</span>
						<span>•</span>
						<span>{formatRelativeTime(execution.started_at)}</span>
					</div>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<button
					onclick={() => copyToClipboard(execution.id, 'id')}
					class="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					{#if copiedField === 'id'}
						<Check size={14} class="text-emerald-500" />
						Copied
					{:else}
						<Copy size={14} />
						Copy ID
					{/if}
				</button>
				<button
					onclick={downloadOutput}
					class="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
					title="Download output"
				>
					<Download size={14} />
				</button>
			</div>
		</div>

		<!-- Quick stats bar -->
		<div class="flex items-center gap-6 px-6 py-3 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700">
			<div class="flex items-center gap-2">
				<Timer size={16} class="text-gray-400" />
				<span class="text-sm text-gray-600 dark:text-gray-400">Duration:</span>
				<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{formatDuration(execution.duration_ms)}</span>
			</div>

			{#if metadata?.aggregate_statistics}
				<div class="flex items-center gap-2">
					<Zap size={16} class="text-violet-500" />
					<span class="text-sm text-gray-600 dark:text-gray-400">Tokens:</span>
					<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}</span>
				</div>

				<div class="flex items-center gap-2">
					<DollarSign size={16} class="text-emerald-500" />
					<span class="text-sm text-gray-600 dark:text-gray-400">Cost:</span>
					<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}</span>
				</div>

				<div class="flex items-center gap-2">
					<Database size={16} class="text-blue-500" />
					<span class="text-sm text-gray-600 dark:text-gray-400">Records:</span>
					<span class="text-sm font-medium text-gray-900 dark:text-gray-100">{metadata.aggregate_statistics.records.total_processed}</span>
				</div>

				<div class="flex items-center gap-2">
					<TrendingUp size={16} class={metadata.aggregate_statistics.records.success_rate >= 0.9 ? 'text-emerald-500' : 'text-amber-500'} />
					<span class="text-sm text-gray-600 dark:text-gray-400">Success:</span>
					<span class="text-sm font-medium {metadata.aggregate_statistics.records.success_rate >= 0.9 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}">
						{formatPercent(metadata.aggregate_statistics.records.success_rate)}
					</span>
				</div>
			{/if}
		</div>

		<!-- Tabs -->
		<div class="flex gap-1 px-6 py-2 border-t border-gray-200 dark:border-gray-700">
			{#each [
				{ id: 'overview', label: 'Overview', icon: Activity },
				{ id: 'execution', label: 'Execution Flow', icon: GitBranch },
				{ id: 'output', label: 'Output', icon: FileJson, count: outputCount() },
				{ id: 'logs', label: 'Logs', icon: FileText, count: execution.logs.length },
				{ id: 'metadata', label: 'Metadata', icon: BarChart3 }
			] as tab}
				{@const TabIcon = tab.icon}
				<button
					onclick={() => activeTab = tab.id as TabId}
					class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === tab.id ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
				>
					<TabIcon size={16} />
					{tab.label}
					{#if tab.count !== undefined && tab.count > 0}
						<span class="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
							{tab.count}
						</span>
					{/if}
				</button>
			{/each}
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto p-6">
		{#if activeTab === 'overview'}
			<!-- Overview Tab -->
			<div class="space-y-6">
				<!-- Key Metrics Cards -->
				{#if metadata?.aggregate_statistics}
					<div class="grid grid-cols-4 gap-4">
						<div class="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 rounded-xl p-4 border border-emerald-200 dark:border-emerald-800">
							<div class="flex items-center gap-2 mb-2">
								<DollarSign size={16} class="text-emerald-600 dark:text-emerald-400" />
								<span class="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase">Total Cost</span>
							</div>
							<div class="text-2xl font-bold text-emerald-700 dark:text-emerald-300">
								{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}
							</div>
							<div class="text-xs text-emerald-600/70 dark:text-emerald-400/70 mt-1">
								{formatCost(metadata.aggregate_statistics.cost.average_cost_per_record)}/record
							</div>
						</div>

						<div class="bg-gradient-to-br from-violet-50 to-violet-100 dark:from-violet-900/20 dark:to-violet-800/20 rounded-xl p-4 border border-violet-200 dark:border-violet-800">
							<div class="flex items-center gap-2 mb-2">
								<Zap size={16} class="text-violet-600 dark:text-violet-400" />
								<span class="text-xs font-medium text-violet-600 dark:text-violet-400 uppercase">Tokens</span>
							</div>
							<div class="text-2xl font-bold text-violet-700 dark:text-violet-300">
								{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}
							</div>
							<div class="text-xs text-violet-600/70 dark:text-violet-400/70 mt-1">
								{formatNumber(metadata.aggregate_statistics.tokens.total_prompt_tokens)} in / {formatNumber(metadata.aggregate_statistics.tokens.total_completion_tokens)} out
							</div>
						</div>

						<div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
							<div class="flex items-center gap-2 mb-2">
								<Server size={16} class="text-blue-600 dark:text-blue-400" />
								<span class="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase">Requests</span>
							</div>
							<div class="text-2xl font-bold text-blue-700 dark:text-blue-300">
								{metadata.aggregate_statistics.requests.total_requests}
							</div>
							<div class="text-xs text-blue-600/70 dark:text-blue-400/70 mt-1">
								{metadata.aggregate_statistics.requests.total_failures} failed
							</div>
						</div>

						<div class="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl p-4 border border-amber-200 dark:border-amber-800">
							<div class="flex items-center gap-2 mb-2">
								<Timer size={16} class="text-amber-600 dark:text-amber-400" />
								<span class="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase">Duration</span>
							</div>
							<div class="text-2xl font-bold text-amber-700 dark:text-amber-300">
								{formatDuration(execution.duration_ms)}
							</div>
							<div class="text-xs text-amber-600/70 dark:text-amber-400/70 mt-1">
								Started {formatDate(execution.started_at)}
							</div>
						</div>
					</div>
				{/if}

				<!-- Error -->
				{#if execution.error}
					<div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
						<div class="flex items-center gap-2 text-red-600 dark:text-red-400 font-medium mb-2">
							<XCircle size={16} />
							Error
						</div>
						<pre class="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap font-mono bg-red-100 dark:bg-red-900/30 p-3 rounded-lg">{execution.error}</pre>
					</div>
				{/if}

				<!-- Run Details Grid -->
				<div class="grid grid-cols-2 gap-6">
					<!-- Execution Info -->
					<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
						<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
							<Activity size={16} />
							Execution Details
						</h3>
						<div class="space-y-3 text-sm">
							<div class="flex justify-between">
								<span class="text-gray-500">Run ID</span>
								<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{execution.id}</span>
							</div>
							<div class="flex justify-between">
								<span class="text-gray-500">Workflow</span>
								<span class="text-gray-800 dark:text-gray-200">{execution.workflow_name || '-'}</span>
							</div>
							<div class="flex justify-between">
								<span class="text-gray-500">Started</span>
								<span class="text-gray-800 dark:text-gray-200">{formatDate(execution.started_at)}</span>
							</div>
							{#if execution.output_file}
								<div class="flex justify-between">
									<span class="text-gray-500">Output File</span>
									<span class="text-gray-800 dark:text-gray-200 font-mono text-xs truncate max-w-48" title={execution.output_file}>
										{execution.output_file.split('/').pop()}
									</span>
								</div>
							{/if}
							{#if metadata?.execution?.git}
								<div class="flex justify-between items-center">
									<span class="text-gray-500 flex items-center gap-1">
										<GitBranch size={12} /> Git
									</span>
									<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">
										{metadata.execution.git.branch} @ {metadata.execution.git.commit_hash.slice(0, 7)}
									</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Dataset Info -->
					{#if metadata?.dataset}
						<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
								<Database size={16} />
								Dataset
							</h3>
							<div class="space-y-3 text-sm">
								<div class="flex justify-between items-center">
									<span class="text-gray-500">Type</span>
									<span class="px-2 py-0.5 text-xs rounded-full font-medium {metadata.dataset.source_type === 'hf' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : metadata.dataset.source_type === 'servicenow' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'}">
										{metadata.dataset.source_type === 'hf' ? 'HuggingFace' : metadata.dataset.source_type === 'servicenow' ? 'ServiceNow' : 'Local'}
									</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Source</span>
									<span class="text-gray-800 dark:text-gray-200 font-mono text-xs truncate max-w-48" title={metadata.dataset.source_path}>
										{metadata.dataset.source_path}
									</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Records</span>
									<span class="text-gray-800 dark:text-gray-200">{metadata.dataset.num_records_processed}</span>
								</div>
								{#if metadata.dataset.dataset_hash}
									<div class="flex justify-between">
										<span class="text-gray-500">Hash</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.dataset.dataset_hash.slice(0, 12)}...</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>

				<!-- Models used -->
				{#if metadata?.models && Object.keys(metadata.models).length > 0}
					<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
						<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
							<Cpu size={16} />
							Models Used
						</h3>
						<div class="flex flex-wrap gap-2">
							{#each Object.entries(metadata.models) as [name, model]}
								<div class="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
									<span class="font-medium text-gray-800 dark:text-gray-200">{name}</span>
									<span class="text-xs text-gray-500">{model.model_type}</span>
									<span class="text-xs text-violet-600 dark:text-violet-400">{formatNumber(model.token_statistics.total_tokens)} tok</span>
									<span class="text-xs text-emerald-600 dark:text-emerald-400">{formatCost(model.cost.total_cost_usd)}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'execution'}
			<!-- Execution Flow Tab - Graph with Timeline sidebar -->
			<div class="h-[600px] bg-gray-50 dark:bg-gray-800/50 rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700">
				<RunExecutionGraph {execution} />
			</div>

		{:else if activeTab === 'output'}
			<!-- Output Tab -->
			<div class="space-y-4">
				{#if execution.output_data}
					<!-- Action buttons -->
					<div class="flex items-center justify-end gap-2">
						<button
							onclick={() => copyToClipboard(JSON.stringify(execution.output_data, null, 2), 'output')}
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
						>
							{#if copiedField === 'output'}
								<Check size={14} class="text-emerald-500" />
								Copied
							{:else}
								<Copy size={14} />
								Copy All
							{/if}
						</button>
						<button
							onclick={downloadOutput}
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
						>
							<Download size={14} />
							Download
						</button>
					</div>

					<!-- Data Table Viewer -->
					<DataTableViewer
						data={Array.isArray(execution.output_data) ? execution.output_data : [execution.output_data]}
						title="Output Data"
						total={outputCount()}
						maxRecords={20}
						showViewToggle={true}
						defaultView="table"
					/>
				{:else}
					<div class="text-center py-12 text-gray-500">
						<FileJson size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm font-medium">No output data available</p>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'logs'}
			<!-- Logs Tab -->
			<div class="h-[600px]">
				<LogViewer logs={execution.logs} title="Execution Logs" />
			</div>

		{:else if activeTab === 'metadata'}
			<!-- Metadata Tab -->
			{#if metadata}
				<div class="space-y-6">
					<!-- Charts Row -->
					<div class="grid grid-cols-2 gap-4">
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-3">
								<PieChart size={16} class="text-violet-500" />
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Distribution</h4>
							</div>
							<div class="h-48">
								<canvas bind:this={tokenPieCanvas}></canvas>
							</div>
						</div>

						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-3">
								<BarChart3 size={16} class="text-blue-500" />
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Usage by Model</h4>
							</div>
							<div class="h-48">
								<canvas bind:this={modelTokensCanvas}></canvas>
							</div>
						</div>
					</div>

					<!-- Model Performance -->
					{#if Object.keys(metadata.models).length > 0}
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
								<Cpu size={16} />
								Model Performance
							</h4>
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="text-left text-xs text-gray-500 uppercase border-b border-gray-200 dark:border-gray-700">
											<th class="pb-2 font-medium">Model</th>
											<th class="pb-2 font-medium text-right">Requests</th>
											<th class="pb-2 font-medium text-right">Tokens</th>
											<th class="pb-2 font-medium text-right">Avg Latency</th>
											<th class="pb-2 font-medium text-right">Throughput</th>
											<th class="pb-2 font-medium text-right">Cost</th>
										</tr>
									</thead>
									<tbody>
										{#each Object.entries(metadata.models) as [name, model]}
											<tr class="border-b border-gray-100 dark:border-gray-800">
												<td class="py-3 font-medium text-gray-800 dark:text-gray-200">{name}</td>
												<td class="py-3 text-right text-gray-600 dark:text-gray-400">{model.performance.total_requests}</td>
												<td class="py-3 text-right text-violet-600 dark:text-violet-400">{formatNumber(model.token_statistics.total_tokens)}</td>
												<td class="py-3 text-right text-gray-600 dark:text-gray-400">{formatLatency(model.performance.average_latency_seconds)}</td>
												<td class="py-3 text-right text-blue-600 dark:text-blue-400">{model.performance.tokens_per_second.toFixed(1)} tok/s</td>
												<td class="py-3 text-right text-emerald-600 dark:text-emerald-400">{formatCost(model.cost.total_cost_usd)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/if}

					<!-- Node Stats -->
					{#if Object.keys(metadata.nodes).length > 0}
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
								<Box size={16} />
								Node Statistics
							</h4>
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="text-left text-xs text-gray-500 uppercase border-b border-gray-200 dark:border-gray-700">
											<th class="pb-2 font-medium">Node</th>
											<th class="pb-2 font-medium">Type</th>
											<th class="pb-2 font-medium text-right">Executions</th>
											<th class="pb-2 font-medium text-right">Avg Latency</th>
											<th class="pb-2 font-medium text-right">Tokens</th>
										</tr>
									</thead>
									<tbody>
										{#each Object.entries(metadata.nodes) as [name, node]}
											<tr class="border-b border-gray-100 dark:border-gray-800">
												<td class="py-2 font-medium text-gray-800 dark:text-gray-200">{name}</td>
												<td class="py-2">
													<span class="text-xs px-2 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300">
														{node.node_type}
													</span>
												</td>
												<td class="py-2 text-right text-gray-600 dark:text-gray-400">{node.total_executions}</td>
												<td class="py-2 text-right text-gray-600 dark:text-gray-400">{formatLatency(node.average_latency_seconds)}</td>
												<td class="py-2 text-right text-gray-600 dark:text-gray-400">
													{node.token_statistics ? formatNumber(node.token_statistics.total_tokens) : '-'}
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/if}

					<!-- Raw JSON -->
					<details class="group">
						<summary class="cursor-pointer text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 flex items-center gap-2">
							<ChevronDown size={16} class="transition-transform group-open:rotate-180" />
							Raw Metadata JSON
						</summary>
						<pre class="mt-2 p-4 bg-gray-900 text-gray-100 rounded-lg text-xs overflow-auto max-h-64 font-mono">{JSON.stringify(metadata, null, 2)}</pre>
					</details>
				</div>
			{:else}
				<div class="text-center py-12 text-gray-500">
					<BarChart3 size={48} class="mx-auto mb-4 opacity-50" />
					<p class="text-sm font-medium">No metadata available</p>
					<p class="text-xs mt-1">Metadata is collected when runs complete</p>
				</div>
			{/if}
		{/if}
	</div>
</div>
