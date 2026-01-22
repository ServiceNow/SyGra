<script lang="ts">
	import { onMount } from 'svelte';
	import { pushState } from '$app/navigation';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import type { Execution, ExecutionMetadata } from '$lib/stores/workflow.svelte';
	import {
		X, CheckCircle2, XCircle, Clock, Loader2, FileJson, FileText,
		Calendar, Timer, Hash, Database, ChevronDown, Copy, Check,
		Activity, Layers, ArrowRight, DollarSign, Zap, Cpu, GitBranch,
		BarChart3, Server, Box, TrendingUp, ArrowLeft, PieChart, Gauge,
		ExternalLink
	} from 'lucide-svelte';
	import type { Chart as ChartType } from 'chart.js';

	// Chart.js will be lazy loaded
	let ChartJS: typeof ChartType | null = null;
	let chartJsLoaded = $state(false);

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
		pending: { color: 'text-text-muted', bg: 'bg-surface-secondary', icon: Clock },
		running: { color: 'text-info', bg: 'bg-info-light', icon: Loader2 },
		completed: { color: 'text-status-completed', bg: 'bg-success-light', icon: CheckCircle2 },
		failed: { color: 'text-error', bg: 'bg-error-light', icon: XCircle },
		cancelled: { color: 'text-warning', bg: 'bg-warning-light', icon: XCircle },
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

	// Generate HuggingFace dataset URL
	function getHuggingFaceUrl(datasetPath: string): string | null {
		if (!datasetPath) return null;
		// HF dataset paths are typically in format "org/dataset" or "dataset"
		// Clean the path and construct URL
		const cleanPath = datasetPath.trim();
		if (cleanPath.includes('/') || /^[a-zA-Z0-9_-]+$/.test(cleanPath)) {
			return `https://huggingface.co/datasets/${cleanPath}`;
		}
		return null;
	}

	// Generate GitHub commit URL (if remote URL is available in metadata)
	function getGitHubCommitUrl(gitInfo: { commit_hash?: string; remote_url?: string; branch?: string }): string | null {
		if (!gitInfo?.commit_hash) return null;

		// If remote_url is provided, parse it
		if (gitInfo.remote_url) {
			let repoUrl = gitInfo.remote_url;
			// Convert SSH to HTTPS format
			if (repoUrl.startsWith('git@github.com:')) {
				repoUrl = repoUrl.replace('git@github.com:', 'https://github.com/').replace(/\.git$/, '');
			} else if (repoUrl.startsWith('https://github.com/')) {
				repoUrl = repoUrl.replace(/\.git$/, '');
			} else {
				return null; // Not a GitHub URL
			}
			return `${repoUrl}/commit/${gitInfo.commit_hash}`;
		}

		return null;
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
	let tokenPieChart: ChartType | null = null;
	let nodeLatencyChart: ChartType | null = null;
	let modelTokensChart: ChartType | null = null;

	async function initCharts() {
		if (!metadata) return;

		// Lazy load Chart.js if not already loaded
		if (!ChartJS) {
			const { Chart, registerables } = await import('chart.js');
			Chart.register(...registerables);
			ChartJS = Chart;
			chartJsLoaded = true;
		}

		// Token distribution pie chart
		if (tokenPieCanvas && metadata.aggregate_statistics) {
			const promptTokens = metadata.aggregate_statistics.tokens.total_prompt_tokens;
			const completionTokens = metadata.aggregate_statistics.tokens.total_completion_tokens;

			if (tokenPieChart) tokenPieChart.destroy();
			tokenPieChart = new ChartJS(tokenPieCanvas, {
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
			nodeLatencyChart = new ChartJS(nodeLantencyCanvas, {
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
			modelTokensChart = new ChartJS(modelTokensCanvas, {
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
		pushState(url.toString(), {});
	}
</script>

<div class="h-full w-full flex flex-col bg-surface">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-surface-border px-6 py-4">
		<div class="flex items-center gap-4 mb-4">
			<button
				onclick={goBack}
				class="p-2 hover:bg-surface-hover rounded-lg transition-colors"
				title="Back to runs"
			>
				<ArrowLeft size={20} class="text-text-muted" />
			</button>
			<div class="flex-1">
				<h1 class="text-xl font-bold text-text-primary">
					{execution.workflow_name || 'Unknown Workflow'}
				</h1>
				<div class="flex items-center gap-3 text-sm text-text-muted">
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
				class="flex items-center gap-2 px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover rounded-lg"
			>
				{#if copiedField === 'id'}
					<Check size={14} class="text-status-completed" />
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
					class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === tab.id ? 'bg-info-light text-info' : 'text-text-secondary hover:bg-surface-hover'}"
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
					<div class="p-4 bg-surface-secondary rounded-xl">
						<div class="flex items-center gap-2 text-text-muted text-sm mb-1">
							<Calendar size={14} />
							Started
						</div>
						<div class="font-medium text-text-primary">
							{formatDate(execution.started_at)}
						</div>
					</div>
					<div class="p-4 bg-surface-secondary rounded-xl">
						<div class="flex items-center gap-2 text-text-muted text-sm mb-1">
							<Timer size={14} />
							Duration
						</div>
						<div class="font-medium text-text-primary">
							{formatDuration(execution.duration_ms)}
						</div>
					</div>
					<div class="p-4 bg-surface-secondary rounded-xl">
						<div class="flex items-center gap-2 text-text-muted text-sm mb-1">
							<Database size={14} />
							Output Records
						</div>
						<div class="font-medium text-text-primary">
							{outputCount()}
						</div>
					</div>
					<div class="p-4 bg-surface-secondary rounded-xl">
						<div class="flex items-center gap-2 text-text-muted text-sm mb-1">
							<Hash size={14} />
							Run ID
						</div>
						<div class="font-medium text-text-primary font-mono text-sm truncate">
							{execution.id}
						</div>
					</div>
				</div>

				<!-- Output file -->
				{#if execution.output_file}
					<div class="p-4 bg-surface-secondary rounded-xl">
						<div class="flex items-center gap-2 text-text-muted text-sm mb-2">
							<FileJson size={14} />
							Output File
						</div>
						<div class="font-mono text-sm text-text-secondary break-all">
							{execution.output_file}
						</div>
					</div>
				{/if}

				<!-- Error -->
				{#if execution.error}
					<div class="p-4 bg-error-light border border-error/30 rounded-xl">
						<div class="flex items-center gap-2 text-error font-medium mb-2">
							<XCircle size={16} />
							Error
						</div>
						<pre class="text-sm text-error whitespace-pre-wrap">{execution.error}</pre>
					</div>
				{/if}

				<!-- Node states -->
				{#if Object.keys(execution.node_states).length > 0}
					<div>
						<h3 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
							<Layers size={16} />
							Node Execution States
						</h3>
						<div class="space-y-2">
							{#each Object.entries(execution.node_states) as [nodeId, nodeState]}
								{@const nodeStatus = statusConfig[nodeState.status as keyof typeof statusConfig] || statusConfig.pending}
								{@const NodeStatusIcon = nodeStatus.icon}
								<div class="flex items-center gap-3 p-3 bg-surface-secondary rounded-lg">
									<NodeStatusIcon size={16} class={nodeStatus.color} />
									<span class="font-medium text-text-primary">{nodeId}</span>
									<ArrowRight size={14} class="text-text-muted" />
									<span class="text-sm {nodeStatus.color}">{nodeState.status}</span>
									{#if nodeState.duration_ms}
										<span class="text-xs text-text-muted ml-auto">{formatDuration(nodeState.duration_ms)}</span>
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
						<div class="text-sm text-text-muted">
							Showing {Array.isArray(sampleOutput()) ? Math.min(5, outputCount()) : 1} of {outputCount()} records
						</div>
						<button
							onclick={() => copyToClipboard(JSON.stringify(execution.output_data, null, 2), 'output')}
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover rounded-lg"
						>
							{#if copiedField === 'output'}
								<Check size={14} class="text-status-completed" />
								Copied
							{:else}
								<Copy size={14} />
								Copy All
							{/if}
						</button>
					</div>

					{#if Array.isArray(sampleOutput())}
						{#each sampleOutput() as record, i}
							<details class="group bg-surface-secondary rounded-lg overflow-hidden" open={i === 0}>
								<summary class="cursor-pointer px-4 py-3 flex items-center gap-2 hover:bg-surface-hover">
									<ChevronDown size={16} class="transition-transform group-open:rotate-180 text-text-muted" />
									<span class="font-medium text-text-secondary">Record {i + 1}</span>
								</summary>
								<pre class="p-4 text-sm text-text-secondary overflow-auto max-h-64 bg-brand-primary/5">{JSON.stringify(record, null, 2)}</pre>
							</details>
						{/each}
					{:else}
						<pre class="p-4 bg-surface-secondary rounded-lg text-sm text-text-secondary overflow-auto">{JSON.stringify(sampleOutput(), null, 2)}</pre>
					{/if}
				{:else}
					<div class="text-center py-12 text-text-muted">
						<FileJson size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm">No output data available</p>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'logs'}
			<!-- Logs Tab -->
			<div class="bg-brand-primary rounded-lg overflow-hidden">
				{#if execution.logs.length > 0}
					<div class="max-h-[600px] overflow-auto p-4 font-mono text-sm">
						{#each execution.logs as log, i}
							<div class="text-gray-300 hover:bg-white/5 px-2 py-0.5 rounded">
								<span class="text-gray-500 select-none mr-4">{i + 1}</span>
								{log}
							</div>
						{/each}
					</div>
				{:else}
					<div class="text-center py-12 text-gray-400">
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
						<div class="bg-success-light rounded-xl p-4 border border-status-completed/30">
							<div class="flex items-center gap-2 mb-2">
								<DollarSign size={16} class="text-status-completed" />
								<span class="text-xs font-medium text-status-completed uppercase">Total Cost</span>
							</div>
							<div class="text-2xl font-bold text-status-completed">
								{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}
							</div>
							<div class="text-xs text-status-completed/70 mt-1">
								{formatCost(metadata.aggregate_statistics.cost.average_cost_per_record)}/record
							</div>
						</div>

						<div class="bg-info-light rounded-xl p-4 border border-info/30">
							<div class="flex items-center gap-2 mb-2">
								<Zap size={16} class="text-info" />
								<span class="text-xs font-medium text-info uppercase">Total Tokens</span>
							</div>
							<div class="text-2xl font-bold text-info">
								{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}
							</div>
							<div class="text-xs text-info/70 mt-1">
								{formatNumber(metadata.aggregate_statistics.tokens.total_prompt_tokens)} prompt
							</div>
						</div>

						<div class="bg-brand-primary/10 rounded-xl p-4 border border-brand-primary/30">
							<div class="flex items-center gap-2 mb-2">
								<TrendingUp size={16} class="text-brand-primary dark:text-info" />
								<span class="text-xs font-medium text-brand-primary dark:text-info uppercase">Success Rate</span>
							</div>
							<div class="text-2xl font-bold text-brand-primary dark:text-info">
								{formatPercent(metadata.aggregate_statistics.records.success_rate)}
							</div>
							<div class="text-xs text-brand-primary/70 dark:text-info/70 mt-1">
								{metadata.aggregate_statistics.records.total_processed} processed
							</div>
						</div>

						<div class="bg-warning-light rounded-xl p-4 border border-warning/30">
							<div class="flex items-center gap-2 mb-2">
								<Server size={16} class="text-warning" />
								<span class="text-xs font-medium text-warning uppercase">Requests</span>
							</div>
							<div class="text-2xl font-bold text-warning">
								{metadata.aggregate_statistics.requests.total_requests}
							</div>
							<div class="text-xs text-warning/70 mt-1">
								{metadata.aggregate_statistics.requests.total_failures} failures
							</div>
						</div>
					</div>

					<!-- Interactive Charts Row -->
					<div class="grid grid-cols-3 gap-4">
						<!-- Token Distribution -->
						<div class="bg-surface rounded-xl border border-surface-border p-4">
							<div class="flex items-center gap-2 mb-3">
								<PieChart size={16} class="text-info" />
								<h4 class="text-sm font-semibold text-text-secondary">Token Distribution</h4>
							</div>
							<div class="h-40">
								<canvas bind:this={tokenPieCanvas}></canvas>
							</div>
						</div>

						<!-- Model Token Usage -->
						<div class="bg-surface rounded-xl border border-surface-border p-4">
							<div class="flex items-center gap-2 mb-3">
								<BarChart3 size={16} class="text-brand-primary dark:text-info" />
								<h4 class="text-sm font-semibold text-text-secondary">Model Token Usage</h4>
							</div>
							<div class="h-40">
								<canvas bind:this={modelTokensCanvas}></canvas>
							</div>
						</div>

						<!-- Node Latency Heatmap -->
						<div class="bg-surface rounded-xl border border-surface-border p-4">
							<div class="flex items-center gap-2 mb-3">
								<Gauge size={16} class="text-warning" />
								<h4 class="text-sm font-semibold text-text-secondary">Node Latency</h4>
								<span class="ml-auto flex items-center gap-1 text-xs">
									<span class="w-2 h-2 rounded bg-status-completed"></span>Fast
									<span class="w-2 h-2 rounded bg-warning ml-1"></span>Med
									<span class="w-2 h-2 rounded bg-error ml-1"></span>Slow
								</span>
							</div>
							<div class="h-40">
								<canvas bind:this={nodeLantencyCanvas}></canvas>
							</div>
						</div>
					</div>

					<!-- Execution & Dataset -->
					<div class="grid grid-cols-2 gap-4">
						<div class="bg-surface-secondary rounded-xl p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
								<Activity size={16} />
								Execution Details
							</h4>
							<div class="space-y-2 text-sm">
								<div class="flex justify-between">
									<span class="text-text-muted">Task:</span>
									<span class="text-text-primary font-mono text-xs">{metadata.execution.task_name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-text-muted">Run Name:</span>
									<span class="text-text-primary">{metadata.execution.run_name}</span>
								</div>
								<div class="flex justify-between">
									<span class="text-text-muted">Duration:</span>
									<span class="text-text-primary">{metadata.execution.timing.duration_seconds.toFixed(2)}s</span>
								</div>
								{#if metadata.execution.git}
									<div class="flex justify-between items-start gap-2">
										<span class="text-text-muted flex items-center gap-1 flex-shrink-0"><GitBranch size={12} /> Git:</span>
										<div class="flex items-center gap-1.5 flex-wrap justify-end">
											<span class="text-text-primary font-mono text-xs">{metadata.execution.git.branch}</span>
											<span class="text-text-muted">@</span>
											{@const gitUrl = getGitHubCommitUrl(metadata.execution.git)}
											{#if gitUrl}
												<a
													href={gitUrl}
													target="_blank"
													rel="noopener noreferrer"
													class="font-mono text-xs text-brand-primary dark:text-info hover:underline flex items-center gap-1"
													title="View commit on GitHub: {metadata.execution.git.commit_hash}"
												>
													{metadata.execution.git.commit_hash.slice(0, 7)}
													<ExternalLink size={10} />
												</a>
											{:else}
												<button
													onclick={() => copyToClipboard(metadata.execution.git.commit_hash, 'git')}
													class="font-mono text-xs text-text-primary hover:text-info flex items-center gap-1"
													title="Click to copy full hash: {metadata.execution.git.commit_hash}"
												>
													{metadata.execution.git.commit_hash.slice(0, 7)}
													{#if copiedField === 'git'}
														<Check size={10} class="text-status-completed" />
													{:else}
														<Copy size={10} class="opacity-50" />
													{/if}
												</button>
											{/if}
											{#if metadata.execution.git.is_dirty}
												<span class="text-warning text-xs">(dirty)</span>
											{/if}
										</div>
									</div>
								{/if}
							</div>
						</div>

						<div class="bg-surface-secondary rounded-xl p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
								<Database size={16} />
								Dataset
							</h4>
							<div class="space-y-2 text-sm">
								<div class="flex justify-between items-center">
									<span class="text-text-muted">Type:</span>
									<span class="px-2 py-0.5 text-xs rounded-full font-medium {metadata.dataset.source_type === 'hf' ? 'bg-warning-light text-warning' : metadata.dataset.source_type === 'servicenow' ? 'bg-success-light text-status-completed' : 'bg-info-light text-info'}">
										{metadata.dataset.source_type === 'hf' ? 'HuggingFace' : metadata.dataset.source_type === 'servicenow' ? 'ServiceNow' : 'Local File'}
									</span>
								</div>
								<div class="flex flex-col gap-1">
									<span class="text-text-muted">Source:</span>
									{@const hfUrl = metadata.dataset.source_type === 'hf' ? getHuggingFaceUrl(metadata.dataset.source_path) : null}
									{#if hfUrl}
										<a
											href={hfUrl}
											target="_blank"
											rel="noopener noreferrer"
											class="text-brand-primary dark:text-info hover:underline font-mono text-xs break-all flex items-center gap-1"
										>
											{metadata.dataset.source_path}
											<ExternalLink size={10} class="flex-shrink-0" />
										</a>
									{:else}
										<span class="text-text-primary font-mono text-xs break-all">
											{metadata.dataset.source_path}
										</span>
									{/if}
								</div>
								<div class="flex justify-between">
									<span class="text-text-muted">Records Processed:</span>
									<span class="text-text-primary">{metadata.dataset.num_records_processed.toLocaleString()}</span>
								</div>
								{#if metadata.dataset.start_index > 0}
									<div class="flex justify-between">
										<span class="text-text-muted">Start Index:</span>
										<span class="text-text-primary">{metadata.dataset.start_index}</span>
									</div>
								{/if}
								{#if metadata.dataset.dataset_version}
									<div class="flex flex-col gap-1">
										<span class="text-text-muted">Version:</span>
										<span class="text-text-primary font-mono text-xs break-all">{metadata.dataset.dataset_version}</span>
									</div>
								{/if}
								{#if metadata.dataset.dataset_hash}
									<div class="flex flex-col gap-1">
										<span class="text-text-muted">Data Hash:</span>
										<button
											onclick={() => copyToClipboard(metadata.dataset.dataset_hash, 'hash')}
											class="text-text-primary font-mono text-xs break-all text-left hover:text-info flex items-center gap-1"
											title="Click to copy full hash"
										>
											{metadata.dataset.dataset_hash}
											{#if copiedField === 'hash'}
												<Check size={10} class="text-status-completed flex-shrink-0" />
											{:else}
												<Copy size={10} class="opacity-50 flex-shrink-0" />
											{/if}
										</button>
									</div>
								{/if}
							</div>
						</div>
					</div>

					<!-- Models -->
					{#if Object.keys(metadata.models).length > 0}
						<div class="bg-surface-secondary rounded-xl p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
								<Cpu size={16} />
								Model Performance
							</h4>
							<div class="space-y-3">
								{#each Object.entries(metadata.models) as [modelName, model]}
									{@const latencyRange = model.performance.latency_statistics.max - model.performance.latency_statistics.min}
									{@const p50Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p50 - model.performance.latency_statistics.min) / latencyRange) * 100 : 50}
									{@const p95Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p95 - model.performance.latency_statistics.min) / latencyRange) * 100 : 95}
									<div class="bg-surface rounded-lg p-4 border border-surface-border">
										<div class="flex items-center justify-between mb-3">
											<div>
												<span class="font-medium text-text-primary">{modelName}</span>
												<span class="text-xs text-text-muted ml-2">{model.model_type}</span>
											</div>
											<div class="flex items-center gap-4 text-sm">
												<span class="text-status-completed font-medium">{formatCost(model.cost.total_cost_usd)}</span>
												<span class="text-info">{formatNumber(model.token_statistics.total_tokens)} tokens</span>
											</div>
										</div>
										<div class="grid grid-cols-4 gap-4 text-xs">
											<div>
												<div class="text-text-muted mb-1">Requests</div>
												<div class="font-medium text-text-primary">{model.performance.total_requests}</div>
											</div>
											<div>
												<div class="text-text-muted mb-1">Avg Latency</div>
												<div class="font-medium text-text-primary">{formatLatency(model.performance.average_latency_seconds)}</div>
											</div>
											<div>
												<div class="text-text-muted mb-1">Throughput</div>
												<div class="font-medium text-text-primary">{model.performance.tokens_per_second.toFixed(1)} tok/s</div>
											</div>
											<div>
												<div class="text-text-muted mb-1">P95 Latency</div>
												<div class="font-medium text-text-primary">{formatLatency(model.performance.latency_statistics.p95)}</div>
											</div>
										</div>
										<!-- Latency bar -->
										<div class="mt-3 pt-3 border-t border-surface-border">
											<div class="h-2 bg-surface-secondary rounded-full overflow-hidden">
												<div class="h-full flex">
													<div class="bg-status-completed" style="width: {p50Pct}%"></div>
													<div class="bg-warning" style="width: {p95Pct - p50Pct}%"></div>
													<div class="bg-error" style="width: {100 - p95Pct}%"></div>
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
						<div class="bg-surface-secondary rounded-xl p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-3 flex items-center gap-2">
								<Box size={16} />
								Node Stats
							</h4>
							<table class="w-full text-sm">
								<thead>
									<tr class="text-left text-xs text-text-muted uppercase border-b border-surface-border">
										<th class="pb-2 font-medium">Node</th>
										<th class="pb-2 font-medium">Type</th>
										<th class="pb-2 font-medium text-right">Executions</th>
										<th class="pb-2 font-medium text-right">Avg Latency</th>
										<th class="pb-2 font-medium text-right">Tokens</th>
									</tr>
								</thead>
								<tbody>
									{#each Object.entries(metadata.nodes) as [nodeName, node]}
										<tr class="border-b border-surface-border/50">
											<td class="py-2 font-medium text-text-primary">{nodeName}</td>
											<td class="py-2">
												<span class="text-xs px-2 py-0.5 rounded bg-info-light text-info">
													{node.node_type}
												</span>
											</td>
											<td class="py-2 text-right text-text-secondary">{node.total_executions}</td>
											<td class="py-2 text-right text-text-secondary">{formatLatency(node.average_latency_seconds)}</td>
											<td class="py-2 text-right text-text-secondary">
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
						<summary class="cursor-pointer text-sm font-medium text-text-secondary hover:text-text-primary flex items-center gap-2">
							<ChevronDown size={16} class="transition-transform group-open:rotate-180" />
							Raw Metadata JSON
						</summary>
						<pre class="mt-2 p-4 bg-brand-primary text-gray-100 rounded-lg text-xs overflow-auto max-h-64">{JSON.stringify(metadata, null, 2)}</pre>
					</details>
				</div>
			{:else}
				<div class="text-center py-12 text-text-muted">
					<BarChart3 size={48} class="mx-auto mb-4 opacity-50" />
					<p class="text-sm font-medium">No metadata available</p>
					<p class="text-xs mt-1">Metadata is collected when runs complete</p>
				</div>
			{/if}
		{/if}
	</div>
</div>
