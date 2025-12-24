<script lang="ts">
	import { onMount } from 'svelte';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import type { Execution, ExecutionMetadata } from '$lib/stores/workflow.svelte';
	import {
		X, CheckCircle2, XCircle, Clock, Loader2, FileJson, FileText,
		Calendar, Timer, Hash, Database, ChevronDown, Copy, Check,
		Activity, Layers, ArrowRight, DollarSign, Zap, Cpu, GitBranch,
		BarChart3, Server, Box, TrendingUp, ArrowLeft, PieChart, Gauge
	} from 'lucide-svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	// Tab state
	type TabId = 'overview' | 'output' | 'logs' | 'metadata';
	let activeTab = $state<TabId>('overview');

	// Copy state
	let copiedField = $state<string | null>(null);

	// Status styling
	const statusConfig = {
		pending: { color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', icon: Clock },
		running: { color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', icon: Loader2 },
		completed: { color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', icon: CheckCircle2 },
		failed: { color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', icon: XCircle },
		cancelled: { color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30', icon: XCircle },
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
	let nodeLantencyCanvas: HTMLCanvasElement;
	let modelTokensCanvas: HTMLCanvasElement;

	// Chart instances
	let tokenPieChart: Chart | null = null;
	let nodeLatencyChart: Chart | null = null;
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
					labels: ['Prompt Tokens', 'Completion Tokens'],
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

		// Node latency chart
		if (nodeLantencyCanvas && metadata.nodes && Object.keys(metadata.nodes).length > 0) {
			const nodeNames = Object.keys(metadata.nodes);
			const avgLatencies = nodeNames.map(n => metadata.nodes[n].average_latency_seconds * 1000);

			// Color based on latency
			const maxLatency = Math.max(...avgLatencies);
			const colors = avgLatencies.map(l => {
				const ratio = maxLatency > 0 ? l / maxLatency : 0;
				if (ratio < 0.33) return 'rgba(16, 185, 129, 0.8)';
				if (ratio < 0.66) return 'rgba(245, 158, 11, 0.8)';
				return 'rgba(239, 68, 68, 0.8)';
			});

			if (nodeLatencyChart) nodeLatencyChart.destroy();
			nodeLatencyChart = new Chart(nodeLantencyCanvas, {
				type: 'bar',
				data: {
					labels: nodeNames,
					datasets: [{
						label: 'Avg Latency (ms)',
						data: avgLatencies,
						backgroundColor: colors,
						borderRadius: 4
					}]
				},
				options: {
					indexAxis: 'y',
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: { x: { beginAtZero: true } }
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
						{
							label: 'Prompt',
							data: promptTokens,
							backgroundColor: 'rgba(139, 92, 246, 0.8)',
							borderRadius: 4
						},
						{
							label: 'Completion',
							data: completionTokens,
							backgroundColor: 'rgba(59, 130, 246, 0.8)',
							borderRadius: 4
						}
					]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: {
						x: { stacked: true, grid: { display: false } },
						y: { stacked: true, beginAtZero: true }
					}
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
			nodeLatencyChart?.destroy();
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
		// Update URL to remove run param
		const url = new URL(window.location.href);
		url.searchParams.delete('run');
		window.history.pushState({}, '', url.toString());
	}
</script>

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center gap-4 mb-4">
			<button
				onclick={goBack}
				class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				title="Back to runs"
			>
				<ArrowLeft size={20} class="text-gray-500" />
			</button>
			<div class="flex-1">
				<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100">
					{execution.workflow_name || 'Unknown Workflow'}
				</h1>
				<div class="flex items-center gap-3 text-sm text-gray-500">
					<span class="font-mono">{execution.id.slice(0, 12)}...</span>
					<span>·</span>
					<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium {status.color} {status.bg}">
						<StatusIcon size={12} class={execution.status === 'running' ? 'animate-spin' : ''} />
						{execution.status}
					</span>
				</div>
			</div>
			<button
				onclick={() => copyToClipboard(execution.id, 'id')}
				class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
			>
				{#if copiedField === 'id'}
					<Check size={14} class="text-green-500" />
					Copied
				{:else}
					<Copy size={14} />
					Copy ID
				{/if}
			</button>
		</div>

		<!-- Tabs -->
		<div class="flex gap-1">
			{#each [
				{ id: 'overview', label: 'Overview', icon: Activity },
				{ id: 'output', label: 'Output', icon: FileJson },
				{ id: 'logs', label: 'Logs', icon: FileText },
				{ id: 'metadata', label: 'Metadata', icon: BarChart3 }
			] as tab}
				{@const TabIcon = tab.icon}
				<button
					onclick={() => activeTab = tab.id as TabId}
					class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === tab.id ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'}"
				>
					<TabIcon size={16} />
					{tab.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto p-6">
		{#if activeTab === 'overview'}
			<!-- Overview Tab -->
			<div class="space-y-6">
				<!-- Quick stats -->
				<div class="grid grid-cols-4 gap-4">
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-1">
							<Calendar size={14} />
							Started
						</div>
						<div class="font-medium text-gray-900 dark:text-gray-100">
							{formatDate(execution.started_at)}
						</div>
					</div>
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-1">
							<Timer size={14} />
							Duration
						</div>
						<div class="font-medium text-gray-900 dark:text-gray-100">
							{formatDuration(execution.duration_ms)}
						</div>
					</div>
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-1">
							<Database size={14} />
							Output Records
						</div>
						<div class="font-medium text-gray-900 dark:text-gray-100">
							{outputCount()}
						</div>
					</div>
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-1">
							<Hash size={14} />
							Run ID
						</div>
						<div class="font-medium text-gray-900 dark:text-gray-100 font-mono text-sm truncate">
							{execution.id}
						</div>
					</div>
				</div>

				<!-- Output file -->
				{#if execution.output_file}
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl">
						<div class="flex items-center gap-2 text-gray-500 text-sm mb-2">
							<FileJson size={14} />
							Output File
						</div>
						<div class="font-mono text-sm text-gray-700 dark:text-gray-300 break-all">
							{execution.output_file}
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
						<pre class="text-sm text-red-700 dark:text-red-300 whitespace-pre-wrap">{execution.error}</pre>
					</div>
				{/if}

				<!-- Node states -->
				{#if Object.keys(execution.node_states).length > 0}
					<div>
						<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
							<Layers size={16} />
							Node Execution States
						</h3>
						<div class="space-y-2">
							{#each Object.entries(execution.node_states) as [nodeId, nodeState]}
								{@const nodeStatus = statusConfig[nodeState.status as keyof typeof statusConfig] || statusConfig.pending}
								{@const NodeStatusIcon = nodeStatus.icon}
								<div class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
									<NodeStatusIcon size={16} class={nodeStatus.color} />
									<span class="font-medium text-gray-900 dark:text-gray-100">{nodeId}</span>
									<ArrowRight size={14} class="text-gray-400" />
									<span class="text-sm {nodeStatus.color}">{nodeState.status}</span>
									{#if nodeState.duration_ms}
										<span class="text-xs text-gray-500 ml-auto">{formatDuration(nodeState.duration_ms)}</span>
									{/if}
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'output'}
			<!-- Output Tab -->
			<div class="space-y-4">
				{#if sampleOutput()}
					<div class="flex items-center justify-between mb-4">
						<div class="text-sm text-gray-500">
							Showing {Array.isArray(sampleOutput()) ? Math.min(5, outputCount()) : 1} of {outputCount()} records
						</div>
						<button
							onclick={() => copyToClipboard(JSON.stringify(execution.output_data, null, 2), 'output')}
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
						>
							{#if copiedField === 'output'}
								<Check size={14} class="text-green-500" />
								Copied
							{:else}
								<Copy size={14} />
								Copy All
							{/if}
						</button>
					</div>

					{#if Array.isArray(sampleOutput())}
						{#each sampleOutput() as record, i}
							<details class="group bg-gray-50 dark:bg-gray-800/50 rounded-lg overflow-hidden" open={i === 0}>
								<summary class="cursor-pointer px-4 py-3 flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-800">
									<ChevronDown size={16} class="transition-transform group-open:rotate-180 text-gray-400" />
									<span class="font-medium text-gray-700 dark:text-gray-300">Record {i + 1}</span>
								</summary>
								<pre class="p-4 text-sm text-gray-700 dark:text-gray-300 overflow-auto max-h-64 bg-gray-100 dark:bg-gray-900">{JSON.stringify(record, null, 2)}</pre>
							</details>
						{/each}
					{:else}
						<pre class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg text-sm text-gray-700 dark:text-gray-300 overflow-auto">{JSON.stringify(sampleOutput(), null, 2)}</pre>
					{/if}
				{:else}
					<div class="text-center py-12 text-gray-500">
						<FileJson size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm">No output data available</p>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'logs'}
			<!-- Logs Tab -->
			<div class="bg-gray-900 rounded-lg overflow-hidden">
				{#if execution.logs.length > 0}
					<div class="max-h-[600px] overflow-auto p-4 font-mono text-sm">
						{#each execution.logs as log, i}
							<div class="text-gray-300 hover:bg-gray-800 px-2 py-0.5 rounded">
								<span class="text-gray-500 select-none mr-4">{i + 1}</span>
								{log}
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-center py-12 text-gray-500">
						<FileText size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm">No logs captured</p>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'metadata'}
			<!-- Metadata Tab -->
			{#if metadata}
				<div class="space-y-6">
					<!-- Key Metrics Cards -->
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
								<span class="text-xs font-medium text-violet-600 dark:text-violet-400 uppercase">Total Tokens</span>
							</div>
							<div class="text-2xl font-bold text-violet-700 dark:text-violet-300">
								{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}
							</div>
							<div class="text-xs text-violet-600/70 dark:text-violet-400/70 mt-1">
								{formatNumber(metadata.aggregate_statistics.tokens.total_prompt_tokens)} prompt
							</div>
						</div>

						<div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
							<div class="flex items-center gap-2 mb-2">
								<TrendingUp size={16} class="text-blue-600 dark:text-blue-400" />
								<span class="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase">Success Rate</span>
							</div>
							<div class="text-2xl font-bold text-blue-700 dark:text-blue-300">
								{formatPercent(metadata.aggregate_statistics.records.success_rate)}
							</div>
							<div class="text-xs text-blue-600/70 dark:text-blue-400/70 mt-1">
								{metadata.aggregate_statistics.records.total_processed} processed
							</div>
						</div>

						<div class="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl p-4 border border-amber-200 dark:border-amber-800">
							<div class="flex items-center gap-2 mb-2">
								<Server size={16} class="text-amber-600 dark:text-amber-400" />
								<span class="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase">Requests</span>
							</div>
							<div class="text-2xl font-bold text-amber-700 dark:text-amber-300">
								{metadata.aggregate_statistics.requests.total_requests}
							</div>
							<div class="text-xs text-amber-600/70 dark:text-amber-400/70 mt-1">
								{metadata.aggregate_statistics.requests.total_failures} failures
							</div>
						</div>
					</div>

					<!-- Interactive Charts Row -->
					<div class="grid grid-cols-3 gap-4">
						<!-- Token Distribution -->
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-3">
								<PieChart size={16} class="text-violet-500" />
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Distribution</h4>
							</div>
							<div class="h-40">
								<canvas bind:this={tokenPieCanvas}></canvas>
							</div>
						</div>

						<!-- Model Token Usage -->
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-3">
								<BarChart3 size={16} class="text-blue-500" />
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Model Token Usage</h4>
							</div>
							<div class="h-40">
								<canvas bind:this={modelTokensCanvas}></canvas>
							</div>
						</div>

						<!-- Node Latency Heatmap -->
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-3">
								<Gauge size={16} class="text-amber-500" />
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Node Latency</h4>
								<span class="ml-auto flex items-center gap-1 text-xs">
									<span class="w-2 h-2 rounded bg-emerald-500"></span>Fast
									<span class="w-2 h-2 rounded bg-amber-500 ml-1"></span>Med
									<span class="w-2 h-2 rounded bg-red-500 ml-1"></span>Slow
								</span>
							</div>
							<div class="h-40">
								<canvas bind:this={nodeLantencyCanvas}></canvas>
							</div>
						</div>
					</div>

					<!-- Execution & Dataset -->
					<div class="grid grid-cols-2 gap-4">
						<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
								<Activity size={16} />
								Execution Details
							</h4>
							<div class="space-y-2 text-sm">
								<div class="flex justify-between">
									<span class="text-gray-500">Task:</span>
									<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.execution.task_name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Run Name:</span>
									<span class="text-gray-800 dark:text-gray-200">{metadata.execution.run_name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Duration:</span>
									<span class="text-gray-800 dark:text-gray-200">{metadata.execution.timing.duration_seconds.toFixed(2)}s</span>
								</div>
								{#if metadata.execution.git}
									<div class="flex justify-between items-center">
										<span class="text-gray-500 flex items-center gap-1"><GitBranch size={12} /> Git:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">
											{metadata.execution.git.branch} @ {metadata.execution.git.commit_hash.slice(0, 7)}
										</span>
									</div>
								{/if}
							</div>
						</div>

						<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
								<Database size={16} />
								Dataset
							</h4>
							<div class="space-y-2 text-sm">
								<div class="flex justify-between items-center">
									<span class="text-gray-500">Type:</span>
									<span class="px-2 py-0.5 text-xs rounded-full font-medium {metadata.dataset.source_type === 'hf' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300' : metadata.dataset.source_type === 'servicenow' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300' : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'}">
										{metadata.dataset.source_type === 'hf' ? 'HuggingFace' : metadata.dataset.source_type === 'servicenow' ? 'ServiceNow' : 'Local File'}
									</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Source:</span>
									<span class="text-gray-800 dark:text-gray-200 font-mono text-xs truncate max-w-48" title={metadata.dataset.source_path}>
										{metadata.dataset.source_path}
									</span>
								</div>
								<div class="flex justify-between">
									<span class="text-gray-500">Records Processed:</span>
									<span class="text-gray-800 dark:text-gray-200">{metadata.dataset.num_records_processed.toLocaleString()}</span>
								</div>
								{#if metadata.dataset.start_index > 0}
									<div class="flex justify-between">
										<span class="text-gray-500">Start Index:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.dataset.start_index}</span>
									</div>
								{/if}
								{#if metadata.dataset.dataset_hash}
									<div class="flex justify-between">
										<span class="text-gray-500">Data Hash:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.dataset.dataset_hash.slice(0, 12)}...</span>
									</div>
								{/if}
							</div>
						</div>
					</div>

					<!-- Models -->
					{#if Object.keys(metadata.models).length > 0}
						<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
								<Cpu size={16} />
								Model Performance
							</h4>
							<div class="space-y-3">
								{#each Object.entries(metadata.models) as [modelName, model]}
									{@const latencyRange = model.performance.latency_statistics.max - model.performance.latency_statistics.min}
									{@const p50Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p50 - model.performance.latency_statistics.min) / latencyRange) * 100 : 50}
									{@const p95Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p95 - model.performance.latency_statistics.min) / latencyRange) * 100 : 95}
									<div class="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
										<div class="flex items-center justify-between mb-3">
											<div>
												<span class="font-medium text-gray-800 dark:text-gray-200">{modelName}</span>
												<span class="text-xs text-gray-500 ml-2">{model.model_type}</span>
											</div>
											<div class="flex items-center gap-4 text-sm">
												<span class="text-emerald-600 dark:text-emerald-400 font-medium">{formatCost(model.cost.total_cost_usd)}</span>
												<span class="text-violet-600 dark:text-violet-400">{formatNumber(model.token_statistics.total_tokens)} tokens</span>
											</div>
										</div>
										<div class="grid grid-cols-4 gap-4 text-xs">
											<div>
												<div class="text-gray-500 mb-1">Requests</div>
												<div class="font-medium text-gray-800 dark:text-gray-200">{model.performance.total_requests}</div>
											</div>
											<div>
												<div class="text-gray-500 mb-1">Avg Latency</div>
												<div class="font-medium text-gray-800 dark:text-gray-200">{formatLatency(model.performance.average_latency_seconds)}</div>
											</div>
											<div>
												<div class="text-gray-500 mb-1">Throughput</div>
												<div class="font-medium text-gray-800 dark:text-gray-200">{model.performance.tokens_per_second.toFixed(1)} tok/s</div>
											</div>
											<div>
												<div class="text-gray-500 mb-1">P95 Latency</div>
												<div class="font-medium text-gray-800 dark:text-gray-200">{formatLatency(model.performance.latency_statistics.p95)}</div>
											</div>
										</div>
										<!-- Latency bar -->
										<div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
											<div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
												<div class="h-full flex">
													<div class="bg-emerald-400" style="width: {p50Pct}%"></div>
													<div class="bg-amber-400" style="width: {p95Pct - p50Pct}%"></div>
													<div class="bg-red-400" style="width: {100 - p95Pct}%"></div>
												</div>
											</div>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Nodes -->
					{#if Object.keys(metadata.nodes).length > 0}
						<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
							<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
								<Box size={16} />
								Node Stats
							</h4>
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
									{#each Object.entries(metadata.nodes) as [nodeName, node]}
										<tr class="border-b border-gray-100 dark:border-gray-800">
											<td class="py-2 font-medium text-gray-800 dark:text-gray-200">{nodeName}</td>
											<td class="py-2">
												<span class="text-xs px-2 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300">
													{node.node_type}
												</span>
											</td>
											<td class="py-2 text-right text-gray-600 dark:text-gray-400">{node.total_executions}</td>
											<td class="py-2 text-right text-gray-600 dark:text-gray-400">{formatLatency(node.average_latency_seconds)}</td>
											<td class="py-2 text-right text-gray-600 dark:text-gray-400">
												{#if node.token_statistics}
													{formatNumber(node.token_statistics.total_tokens)}
												{:else}
													-
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					{/if}

					<!-- Raw JSON -->
					<details class="group">
						<summary class="cursor-pointer text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 flex items-center gap-2">
							<ChevronDown size={16} class="transition-transform group-open:rotate-180" />
							Raw Metadata JSON
						</summary>
						<pre class="mt-2 p-4 bg-gray-900 text-gray-100 rounded-lg text-xs overflow-auto max-h-64">{JSON.stringify(metadata, null, 2)}</pre>
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
