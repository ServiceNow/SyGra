<script lang="ts">
	import { onMount } from 'svelte';
	import { pushState } from '$app/navigation';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import type { Execution, ExecutionMetadata } from '$lib/stores/workflow.svelte';
	import {
		X, CheckCircle2, XCircle, Clock, Loader2, FileJson, FileText,
		Calendar, Timer, Hash, Database, ChevronDown, Copy, Check,
		Activity, ArrowRight, DollarSign, Zap, Cpu, GitBranch,
		BarChart3, Server, Box, TrendingUp, ArrowLeft, PieChart, Gauge,
		Download, Star, Play, Share2, ExternalLink, RefreshCw
	} from 'lucide-svelte';
	import type { Chart as ChartType } from 'chart.js';
	import LogViewer from './LogViewer.svelte';
	import DataTableViewer from '$lib/components/common/DataTableViewer.svelte';
	import RunExecutionGraph from './RunExecutionGraph.svelte';

	// Chart.js will be lazy loaded
	let ChartJS: typeof ChartType | null = null;
	let chartJsLoaded = $state(false);

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	// Tab state
	type TabId = 'overview' | 'execution' | 'output' | 'logs' | 'metadata';
	let activeTab = $state<TabId>('overview');

	// Copy state
	let copiedField = $state<string | null>(null);

	// Status styling using design tokens
	const statusConfig = {
		pending: { color: 'text-text-muted', bg: 'bg-surface-tertiary', icon: Clock, label: 'Pending' },
		running: { color: 'text-info', bg: 'bg-info-light', icon: Loader2, label: 'Running' },
		completed: { color: 'text-success', bg: 'bg-success-light', icon: CheckCircle2, label: 'Completed' },
		failed: { color: 'text-error', bg: 'bg-error-light', icon: XCircle, label: 'Failed' },
		cancelled: { color: 'text-warning', bg: 'bg-warning-light', icon: XCircle, label: 'Cancelled' },
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

	// Generate HuggingFace dataset URL
	function getHuggingFaceUrl(datasetPath: string): string | null {
		if (!datasetPath) return null;
		const cleanPath = datasetPath.trim();
		if (cleanPath.includes('/') || /^[a-zA-Z0-9_-]+$/.test(cleanPath)) {
			return `https://huggingface.co/datasets/${cleanPath}`;
		}
		return null;
	}

	// Generate GitHub commit URL
	function getGitHubCommitUrl(gitInfo: { commit_hash?: string; remote_url?: string }): string | null {
		if (!gitInfo?.commit_hash) return null;
		if (gitInfo.remote_url) {
			let repoUrl = gitInfo.remote_url;
			if (repoUrl.startsWith('git@github.com:')) {
				repoUrl = repoUrl.replace('git@github.com:', 'https://github.com/').replace(/\.git$/, '');
			} else if (repoUrl.startsWith('https://github.com/')) {
				repoUrl = repoUrl.replace(/\.git$/, '');
			} else {
				return null;
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
	let modelTokensCanvas: HTMLCanvasElement;

	// Chart instances
	let tokenPieChart: ChartType | null = null;
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
			modelTokensChart = new ChartJS(modelTokensCanvas, {
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
		pushState(url.toString(), {});
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

<div class="h-full w-full flex flex-col bg-surface">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-[var(--border)]">
		<!-- Top bar with back button and actions -->
		<div class="flex items-center justify-between px-6 py-4">
			<div class="flex items-center gap-4">
				<button
					onclick={goBack}
					class="p-2 hover:bg-surface-hover rounded-lg transition-colors"
					title="Back to runs"
				>
					<ArrowLeft size={20} class="text-text-muted" />
				</button>

				<div>
					<div class="flex items-center gap-3">
						<h1 class="text-xl font-bold text-text-primary">
							{execution.workflow_name || 'Unknown Workflow'}
						</h1>
						<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {status.color} {status.bg}">
							<StatusIcon size={12} class={execution.status === 'running' ? 'animate-spin' : ''} />
							{status.label}
						</span>
					</div>
					<div class="flex items-center gap-3 text-sm text-text-muted mt-1">
						<span class="font-mono">{execution.id}</span>
						<span>•</span>
						<span>{formatRelativeTime(execution.started_at)}</span>
					</div>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<button
					onclick={() => copyToClipboard(execution.id, 'id')}
					class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-surface-hover rounded-lg transition-colors"
				>
					{#if copiedField === 'id'}
						<Check size={14} class="text-success" />
						Copied
					{:else}
						<Copy size={14} />
						Copy ID
					{/if}
				</button>
				<button
					onclick={downloadOutput}
					class="flex items-center gap-2 px-3 py-2 text-sm text-text-secondary hover:bg-surface-hover rounded-lg transition-colors"
					title="Download output"
				>
					<Download size={14} />
				</button>
			</div>
		</div>

		<!-- Quick stats bar -->
		<div class="flex items-center gap-6 px-6 py-3 bg-surface-secondary border-t border-[var(--border)]">
			<div class="flex items-center gap-2">
				<Timer size={16} class="text-text-muted" />
				<span class="text-sm text-text-secondary">Duration:</span>
				<span class="text-sm font-medium text-text-primary">{formatDuration(execution.duration_ms)}</span>
			</div>

			{#if metadata?.aggregate_statistics}
				<div class="flex items-center gap-2">
					<Zap size={16} class="text-node-llm" />
					<span class="text-sm text-text-secondary">Tokens:</span>
					<span class="text-sm font-medium text-text-primary">{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}</span>
				</div>

				<div class="flex items-center gap-2">
					<DollarSign size={16} class="text-success" />
					<span class="text-sm text-text-secondary">Cost:</span>
					<span class="text-sm font-medium text-text-primary">{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}</span>
				</div>

				<div class="flex items-center gap-2">
					<Database size={16} class="text-info" />
					<span class="text-sm text-text-secondary">Records:</span>
					<span class="text-sm font-medium text-text-primary">{metadata.aggregate_statistics.records.total_processed}</span>
				</div>

				<div class="flex items-center gap-2">
					<TrendingUp size={16} class={metadata.aggregate_statistics.records.success_rate >= 0.9 ? 'text-success' : 'text-warning'} />
					<span class="text-sm text-text-secondary">Success:</span>
					<span class="text-sm font-medium {metadata.aggregate_statistics.records.success_rate >= 0.9 ? 'text-success' : 'text-warning'}">
						{formatPercent(metadata.aggregate_statistics.records.success_rate)}
					</span>
				</div>
			{/if}
		</div>

		<!-- Tabs -->
		<div class="flex gap-1 px-6 py-2 border-t border-[var(--border)]">
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
					class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors {activeTab === tab.id ? 'bg-info-light text-info' : 'text-text-secondary hover:bg-surface-hover'}"
				>
					<TabIcon size={16} />
					{tab.label}
					{#if tab.count !== undefined && tab.count > 0}
						<span class="text-xs px-1.5 py-0.5 rounded-full bg-surface-tertiary text-text-secondary">
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
						<div class="bg-success-light rounded-xl p-4 border border-success-border">
							<div class="flex items-center gap-2 mb-2">
								<DollarSign size={16} class="text-success" />
								<span class="text-xs font-medium text-success uppercase">Total Cost</span>
							</div>
							<div class="text-2xl font-bold text-success">
								{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}
							</div>
							<div class="text-xs text-success/70 mt-1">
								{formatCost(metadata.aggregate_statistics.cost.average_cost_per_record)}/record
							</div>
						</div>

						<div class="bg-node-llm-bg rounded-xl p-4 border border-node-llm/30">
							<div class="flex items-center gap-2 mb-2">
								<Zap size={16} class="text-node-llm" />
								<span class="text-xs font-medium text-node-llm uppercase">Tokens</span>
							</div>
							<div class="text-2xl font-bold text-node-llm">
								{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}
							</div>
							<div class="text-xs text-node-llm/70 mt-1">
								{formatNumber(metadata.aggregate_statistics.tokens.total_prompt_tokens)} in / {formatNumber(metadata.aggregate_statistics.tokens.total_completion_tokens)} out
							</div>
						</div>

						<div class="bg-info-light rounded-xl p-4 border border-info-border">
							<div class="flex items-center gap-2 mb-2">
								<Server size={16} class="text-info" />
								<span class="text-xs font-medium text-info uppercase">Requests</span>
							</div>
							<div class="text-2xl font-bold text-info">
								{metadata.aggregate_statistics.requests.total_requests}
							</div>
							<div class="text-xs text-info/70 mt-1">
								{metadata.aggregate_statistics.requests.total_failures} failed
							</div>
						</div>

						<div class="bg-warning-light rounded-xl p-4 border border-warning-border">
							<div class="flex items-center gap-2 mb-2">
								<Timer size={16} class="text-warning" />
								<span class="text-xs font-medium text-warning uppercase">Duration</span>
							</div>
							<div class="text-2xl font-bold text-warning">
								{formatDuration(execution.duration_ms)}
							</div>
							<div class="text-xs text-warning/70 mt-1">
								Started {formatDate(execution.started_at)}
							</div>
						</div>
					</div>
				{/if}

				<!-- Error -->
				{#if execution.error}
					<div class="p-4 bg-error-light border border-error-border rounded-xl">
						<div class="flex items-center gap-2 text-error font-medium mb-2">
							<XCircle size={16} />
							Error
						</div>
						<pre class="text-sm text-error whitespace-pre-wrap font-mono bg-error-light/50 p-3 rounded-lg">{execution.error}</pre>
					</div>
				{/if}

				<!-- Run Details Grid -->
				<div class="grid grid-cols-2 gap-6">
					<!-- Execution Info -->
					<div class="bg-surface-secondary rounded-xl p-4">
						<h3 class="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
							<Activity size={16} />
							Execution Details
						</h3>
						<div class="space-y-3 text-sm">
							<div class="flex justify-between items-start gap-2">
								<span class="text-text-muted flex-shrink-0">Run ID</span>
								<button
									onclick={() => copyToClipboard(execution.id, 'run_id')}
									class="font-mono text-xs text-text-primary hover:text-info flex items-center gap-1 text-right break-all"
									title="Click to copy: {execution.id}"
								>
									{execution.id}
									{#if copiedField === 'run_id'}
										<Check size={10} class="text-success flex-shrink-0" />
									{:else}
										<Copy size={10} class="opacity-50 flex-shrink-0" />
									{/if}
								</button>
							</div>
							<div class="flex justify-between items-start gap-2">
								<span class="text-text-muted flex-shrink-0">Workflow</span>
								<span class="text-text-primary text-right break-all">{execution.workflow_name || '-'}</span>
							</div>
							<div class="flex justify-between">
								<span class="text-text-muted">Started</span>
								<span class="text-text-primary">{formatDate(execution.started_at)}</span>
							</div>
							{#if execution.output_file}
								<div class="flex justify-between items-start gap-2">
									<span class="text-text-muted flex-shrink-0">Output File</span>
									<button
										onclick={() => copyToClipboard(execution.output_file, 'output_file')}
										class="font-mono text-xs text-text-primary hover:text-info flex items-center gap-1 text-right break-all"
										title="Click to copy full path: {execution.output_file}"
									>
										{execution.output_file.split('/').pop()}
										{#if copiedField === 'output_file'}
											<Check size={10} class="text-success flex-shrink-0" />
										{:else}
											<Copy size={10} class="opacity-50 flex-shrink-0" />
										{/if}
									</button>
								</div>
							{/if}
							{#if metadata?.execution?.git}
								<div class="flex justify-between items-start gap-2">
									<span class="text-text-muted flex items-center gap-1 flex-shrink-0">
										<GitBranch size={12} /> Git
									</span>
									<div class="flex items-center gap-1.5 flex-wrap justify-end">
										<span class="text-text-primary font-mono text-xs">{metadata.execution.git.branch}</span>
										<span class="text-text-muted">@</span>
										{#if metadata.execution.git.commit_hash}
											{@const gitUrl = getGitHubCommitUrl(metadata.execution.git)}
											{#if gitUrl}
												<a
													href={gitUrl}
													target="_blank"
													rel="noopener noreferrer"
													class="font-mono text-xs text-text-link hover:underline flex items-center gap-1"
													title="View commit on GitHub: {metadata.execution.git.commit_hash}"
												>
													{metadata.execution.git.commit_hash.slice(0, 7)}
													<ExternalLink size={10} />
												</a>
											{:else}
												<button
													onclick={() => copyToClipboard(metadata.execution.git.commit_hash, 'git')}
													class="font-mono text-xs text-text-primary hover:text-info flex items-center gap-1"
													title="Click to copy: {metadata.execution.git.commit_hash}"
												>
													{metadata.execution.git.commit_hash.slice(0, 7)}
													{#if copiedField === 'git'}
														<Check size={10} class="text-success" />
													{:else}
														<Copy size={10} class="opacity-50" />
													{/if}
												</button>
											{/if}
										{/if}
										{#if metadata.execution.git.is_dirty}
											<span class="text-warning text-xs">(dirty)</span>
										{/if}
									</div>
								</div>
							{/if}
						</div>
					</div>

					<!-- Dataset Info -->
					{#if metadata?.dataset}
						<div class="bg-surface-secondary rounded-xl p-4">
							<h3 class="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
								<Database size={16} />
								Dataset
							</h3>
							<div class="space-y-3 text-sm">
								<div class="flex justify-between items-center">
									<span class="text-text-muted">Type</span>
									<span class="px-2 py-0.5 text-xs rounded-full font-medium {metadata.dataset.source_type === 'hf' ? 'bg-warning-light text-warning' : metadata.dataset.source_type === 'servicenow' ? 'bg-success-light text-success' : 'bg-info-light text-info'}">
										{metadata.dataset.source_type === 'hf' ? 'HuggingFace' : metadata.dataset.source_type === 'servicenow' ? 'ServiceNow' : 'Local'}
									</span>
								</div>
								<div class="flex justify-between items-start gap-2">
									<span class="text-text-muted flex-shrink-0">Source</span>
									{#if metadata.dataset.source_type === 'hf'}
										{@const hfUrl = getHuggingFaceUrl(metadata.dataset.source_path)}
										{#if hfUrl}
											<a
												href={hfUrl}
												target="_blank"
												rel="noopener noreferrer"
												class="font-mono text-xs text-text-link hover:underline flex items-center gap-1 break-all text-right"
											>
												{metadata.dataset.source_path}
												<ExternalLink size={10} class="flex-shrink-0" />
											</a>
										{:else}
											<span class="text-text-primary font-mono text-xs break-all text-right">
												{metadata.dataset.source_path}
											</span>
										{/if}
									{:else}
										<span class="text-text-primary font-mono text-xs break-all text-right">
											{metadata.dataset.source_path}
										</span>
									{/if}
								</div>
								{#if metadata.dataset.dataset_version}
									<div class="flex justify-between items-start gap-2">
										<span class="text-text-muted flex-shrink-0">Version</span>
										<span class="text-text-primary font-mono text-xs break-all text-right">
											{metadata.dataset.dataset_version}
										</span>
									</div>
								{/if}
								<div class="flex justify-between">
									<span class="text-text-muted">Records</span>
									<span class="text-text-primary">{metadata.dataset.num_records_processed}</span>
								</div>
								{#if metadata.dataset.dataset_hash}
									<div class="flex justify-between items-start gap-2">
										<span class="text-text-muted flex-shrink-0">Hash</span>
										<button
											onclick={() => copyToClipboard(metadata.dataset.dataset_hash, 'dataset_hash')}
											class="font-mono text-xs text-text-primary hover:text-info flex items-center gap-1 break-all text-right"
											title="Click to copy: {metadata.dataset.dataset_hash}"
										>
											{metadata.dataset.dataset_hash}
											{#if copiedField === 'dataset_hash'}
												<Check size={10} class="text-success flex-shrink-0" />
											{:else}
												<Copy size={10} class="opacity-50 flex-shrink-0" />
											{/if}
										</button>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>

				<!-- Models used -->
				{#if metadata?.models && Object.keys(metadata.models).length > 0}
					<div class="bg-surface-secondary rounded-xl p-4">
						<h3 class="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
							<Cpu size={16} />
							Models Used
						</h3>
						<div class="flex flex-wrap gap-2">
							{#each Object.entries(metadata.models) as [name, model]}
								<div class="flex items-center gap-2 px-3 py-2 bg-surface-elevated rounded-lg border border-[var(--border)]">
									<span class="font-medium text-text-primary">{name}</span>
									<span class="text-xs text-text-muted">{model.model_type}</span>
									<span class="text-xs text-node-llm">{formatNumber(model.token_statistics.total_tokens)} tok</span>
									<span class="text-xs text-success">{formatCost(model.cost.total_cost_usd)}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'execution'}
			<!-- Execution Flow Tab - Graph with Timeline sidebar -->
			<div class="h-[600px] bg-surface-secondary rounded-xl overflow-hidden border border-[var(--border)]">
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
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover rounded-lg border border-[var(--border)]"
						>
							{#if copiedField === 'output'}
								<Check size={14} class="text-success" />
								Copied
							{:else}
								<Copy size={14} />
								Copy All
							{/if}
						</button>
						<button
							onclick={downloadOutput}
							class="flex items-center gap-2 px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover rounded-lg border border-[var(--border)]"
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
					<div class="text-center py-12 text-text-muted">
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
						<div class="bg-surface-elevated rounded-xl border border-[var(--border)] p-4">
							<div class="flex items-center gap-2 mb-3">
								<PieChart size={16} class="text-node-llm" />
								<h4 class="text-sm font-semibold text-text-secondary">Token Distribution</h4>
							</div>
							<div class="h-48">
								<canvas bind:this={tokenPieCanvas}></canvas>
							</div>
						</div>

						<div class="bg-surface-elevated rounded-xl border border-[var(--border)] p-4">
							<div class="flex items-center gap-2 mb-3">
								<BarChart3 size={16} class="text-info" />
								<h4 class="text-sm font-semibold text-text-secondary">Token Usage by Model</h4>
							</div>
							<div class="h-48">
								<canvas bind:this={modelTokensCanvas}></canvas>
							</div>
						</div>
					</div>

					<!-- Model Performance -->
					{#if Object.keys(metadata.models).length > 0}
						<div class="bg-surface-elevated rounded-xl border border-[var(--border)] p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
								<Cpu size={16} />
								Model Performance
							</h4>
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="text-left text-xs text-text-muted uppercase border-b border-[var(--border)]">
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
											<tr class="border-b border-surface-border">
												<td class="py-3 font-medium text-text-primary">{name}</td>
												<td class="py-3 text-right text-text-secondary">{model.performance.total_requests}</td>
												<td class="py-3 text-right text-node-llm">{formatNumber(model.token_statistics.total_tokens)}</td>
												<td class="py-3 text-right text-text-secondary">{formatLatency(model.performance.average_latency_seconds)}</td>
												<td class="py-3 text-right text-info">{model.performance.tokens_per_second.toFixed(1)} tok/s</td>
												<td class="py-3 text-right text-success">{formatCost(model.cost.total_cost_usd)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					{/if}

					<!-- Node Stats -->
					{#if Object.keys(metadata.nodes).length > 0}
						<div class="bg-surface-elevated rounded-xl border border-[var(--border)] p-4">
							<h4 class="text-sm font-semibold text-text-secondary mb-4 flex items-center gap-2">
								<Box size={16} />
								Node Statistics
							</h4>
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="text-left text-xs text-text-muted uppercase border-b border-[var(--border)]">
											<th class="pb-2 font-medium">Node</th>
											<th class="pb-2 font-medium">Type</th>
											<th class="pb-2 font-medium text-right">Executions</th>
											<th class="pb-2 font-medium text-right">Avg Latency</th>
											<th class="pb-2 font-medium text-right">Tokens</th>
										</tr>
									</thead>
									<tbody>
										{#each Object.entries(metadata.nodes) as [name, node]}
											<tr class="border-b border-surface-border">
												<td class="py-2 font-medium text-text-primary">{name}</td>
												<td class="py-2">
													<span class="text-xs px-2 py-0.5 rounded bg-node-llm-bg text-node-llm">
														{node.node_type}
													</span>
												</td>
												<td class="py-2 text-right text-text-secondary">{node.total_executions}</td>
												<td class="py-2 text-right text-text-secondary">{formatLatency(node.average_latency_seconds)}</td>
												<td class="py-2 text-right text-text-secondary">
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
						<summary class="cursor-pointer text-sm font-medium text-text-secondary hover:text-text-primary flex items-center gap-2">
							<ChevronDown size={16} class="transition-transform group-open:rotate-180" />
							Raw Metadata JSON
						</summary>
						<pre class="mt-2 p-4 bg-brand-primary text-white rounded-lg text-xs overflow-auto max-h-64 font-mono">{JSON.stringify(metadata, null, 2)}</pre>
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
