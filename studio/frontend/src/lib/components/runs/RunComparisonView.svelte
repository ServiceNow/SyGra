<script lang="ts">
	import { onMount } from 'svelte';
	import { type Execution } from '$lib/stores/workflow.svelte';
	import {
		GitCompare, ArrowLeft, CheckCircle2, XCircle, Clock, Loader2, Ban,
		TrendingUp, TrendingDown, Minus, Zap, DollarSign, Timer, Database,
		Activity, Cpu, Server, BarChart3, ArrowRight, Download, Copy, Check,
		Trophy, Medal, Award, Target, Gauge, PieChart, Layers, ChevronDown,
		ArrowUpRight, ArrowDownRight, Equal
	} from 'lucide-svelte';
	import type { Chart as ChartType } from 'chart.js';

	// Chart.js will be lazy loaded
	let ChartJS: typeof ChartType | null = null;
	let chartJsLoaded = $state(false);

	interface Props {
		runs: Execution[];
		onBack: () => void;
	}

	let { runs, onBack }: Props = $props();

	// Tab state
	type TabId = 'overview' | 'metrics' | 'models' | 'nodes' | 'timeline';
	let activeTab = $state<TabId>('overview');

	// Copy state
	let copied = $state(false);

	// Chart refs
	let metricsBarCanvas: HTMLCanvasElement;
	let tokenCompareCanvas: HTMLCanvasElement;
	let costCompareCanvas: HTMLCanvasElement;
	let latencyCompareCanvas: HTMLCanvasElement;
	let radarCanvas: HTMLCanvasElement;
	let modelTokensCanvas: HTMLCanvasElement;
	let modelLatencyCanvas: HTMLCanvasElement;
	let nodeLatencyCanvas: HTMLCanvasElement;

	// Chart instances
	let metricsBarChart: ChartType | null = null;
	let tokenCompareChart: ChartType | null = null;
	let costCompareChart: ChartType | null = null;
	let latencyCompareChart: ChartType | null = null;
	let radarChart: ChartType | null = null;
	let modelTokensChart: ChartType | null = null;
	let modelLatencyChart: ChartType | null = null;
	let nodeLatencyChart: ChartType | null = null;

	// Status config
	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string }> = {
		pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800' },
		running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30' },
		completed: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
		failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30' },
		cancelled: { icon: Ban, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30' }
	};

	// Color palette for runs
	const runColors = [
		'rgba(139, 92, 246, 0.8)',  // Violet
		'rgba(59, 130, 246, 0.8)',  // Blue
		'rgba(16, 185, 129, 0.8)',  // Emerald
		'rgba(245, 158, 11, 0.8)',  // Amber
		'rgba(239, 68, 68, 0.8)',   // Red
		'rgba(236, 72, 153, 0.8)',  // Pink
		'rgba(20, 184, 166, 0.8)',  // Teal
		'rgba(168, 85, 247, 0.8)',  // Purple
	];

	// Get metrics from run
	function getMetrics(run: Execution) {
		return {
			duration: run.duration_ms || 0,
			tokens: run.metadata?.aggregate_statistics?.tokens?.total_tokens || 0,
			promptTokens: run.metadata?.aggregate_statistics?.tokens?.total_prompt_tokens || 0,
			completionTokens: run.metadata?.aggregate_statistics?.tokens?.total_completion_tokens || 0,
			cost: run.metadata?.aggregate_statistics?.cost?.total_cost_usd || 0,
			records: run.metadata?.aggregate_statistics?.records?.total_processed || 0,
			successRate: run.metadata?.aggregate_statistics?.records?.success_rate || 0,
			requests: run.metadata?.aggregate_statistics?.requests?.total_requests || 0,
			failures: run.metadata?.aggregate_statistics?.requests?.total_failures || 0
		};
	}

	// Get run label
	function getRunLabel(run: Execution, index: number): string {
		const name = run.workflow_name || 'Run';
		return `${name.slice(0, 12)}${name.length > 12 ? '...' : ''} (${run.id.slice(0, 6)})`;
	}

	// Get short run label
	function getShortLabel(run: Execution): string {
		return run.id.slice(0, 8);
	}

	// Compute comparison stats
	let comparisonStats = $derived(() => {
		const metrics = runs.map(getMetrics);

		const durations = metrics.map(m => m.duration);
		const tokens = metrics.map(m => m.tokens);
		const costs = metrics.map(m => m.cost);
		const successRates = metrics.map(m => m.successRate);

		return {
			duration: {
				min: Math.min(...durations),
				max: Math.max(...durations),
				avg: durations.reduce((a, b) => a + b, 0) / durations.length,
				bestIdx: durations.indexOf(Math.min(...durations)),
				worstIdx: durations.indexOf(Math.max(...durations))
			},
			tokens: {
				min: Math.min(...tokens),
				max: Math.max(...tokens),
				avg: tokens.reduce((a, b) => a + b, 0) / tokens.length,
				bestIdx: tokens.indexOf(Math.min(...tokens)), // Less is better for tokens
				worstIdx: tokens.indexOf(Math.max(...tokens))
			},
			cost: {
				min: Math.min(...costs),
				max: Math.max(...costs),
				avg: costs.reduce((a, b) => a + b, 0) / costs.length,
				bestIdx: costs.indexOf(Math.min(...costs)),
				worstIdx: costs.indexOf(Math.max(...costs))
			},
			successRate: {
				min: Math.min(...successRates),
				max: Math.max(...successRates),
				avg: successRates.reduce((a, b) => a + b, 0) / successRates.length,
				bestIdx: successRates.indexOf(Math.max(...successRates)), // Higher is better
				worstIdx: successRates.indexOf(Math.min(...successRates))
			}
		};
	});

	// Get all unique models across runs
	let allModels = $derived(() => {
		const models = new Set<string>();
		runs.forEach(run => {
			if (run.metadata?.models) {
				Object.keys(run.metadata.models).forEach(m => models.add(m));
			}
		});
		return Array.from(models);
	});

	// Get all unique nodes across runs
	let allNodes = $derived(() => {
		const nodes = new Set<string>();
		runs.forEach(run => {
			if (run.metadata?.nodes) {
				Object.keys(run.metadata.nodes).forEach(n => nodes.add(n));
			}
		});
		return Array.from(nodes);
	});

	// Best runs for each category
	let fastestRun = $derived(runs[comparisonStats().duration.bestIdx]);
	let lowestTokensRun = $derived(runs[comparisonStats().tokens.bestIdx]);
	let cheapestRun = $derived(runs[comparisonStats().cost.bestIdx]);
	let mostReliableRun = $derived(runs[comparisonStats().successRate.bestIdx]);

	// Format helpers
	function formatDuration(ms: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		const m = Math.floor(s / 60);
		return `${m}m ${s % 60}s`;
	}

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toLocaleString();
	}

	function formatCost(usd: number): string {
		if (!usd) return '$0';
		if (usd < 0.01) return `$${(usd * 100).toFixed(2)}¢`;
		return `$${usd.toFixed(4)}`;
	}

	function formatPercent(rate: number): string {
		return `${(rate * 100).toFixed(1)}%`;
	}

	function formatDelta(current: number, baseline: number, lowerIsBetter: boolean = false): { value: string; direction: 'up' | 'down' | 'same'; isGood: boolean } {
		if (baseline === 0) return { value: '-', direction: 'same', isGood: true };
		const delta = ((current - baseline) / baseline) * 100;
		const direction = delta > 0.5 ? 'up' : delta < -0.5 ? 'down' : 'same';
		const isGood = lowerIsBetter ? delta < 0 : delta > 0;
		return {
			value: `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`,
			direction,
			isGood: direction === 'same' ? true : isGood
		};
	}

	// Initialize charts
	async function initCharts() {
		// Lazy load Chart.js if not already loaded
		if (!ChartJS) {
			const { Chart, registerables } = await import('chart.js');
			Chart.register(...registerables);
			ChartJS = Chart;
			chartJsLoaded = true;
		}

		const labels = runs.map((r, i) => getShortLabel(r));
		const metrics = runs.map(getMetrics);

		// Metrics comparison bar chart
		if (metricsBarCanvas) {
			if (metricsBarChart) metricsBarChart.destroy();
			metricsBarChart = new ChartJS(metricsBarCanvas, {
				type: 'bar',
				data: {
					labels,
					datasets: [
						{
							label: 'Duration (s)',
							data: metrics.map(m => m.duration / 1000),
							backgroundColor: 'rgba(245, 158, 11, 0.8)',
							borderRadius: 4,
							yAxisID: 'y'
						},
						{
							label: 'Tokens (K)',
							data: metrics.map(m => m.tokens / 1000),
							backgroundColor: 'rgba(139, 92, 246, 0.8)',
							borderRadius: 4,
							yAxisID: 'y1'
						}
					]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } }
					},
					scales: {
						y: { type: 'linear', position: 'left', beginAtZero: true, title: { display: true, text: 'Duration (s)' } },
						y1: { type: 'linear', position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Tokens (K)' } }
					}
				}
			});
		}

		// Token distribution stacked bar
		if (tokenCompareCanvas) {
			if (tokenCompareChart) tokenCompareChart.destroy();
			tokenCompareChart = new ChartJS(tokenCompareCanvas, {
				type: 'bar',
				data: {
					labels,
					datasets: [
						{
							label: 'Prompt Tokens',
							data: metrics.map(m => m.promptTokens),
							backgroundColor: 'rgba(139, 92, 246, 0.8)',
							borderRadius: 4
						},
						{
							label: 'Completion Tokens',
							data: metrics.map(m => m.completionTokens),
							backgroundColor: 'rgba(59, 130, 246, 0.8)',
							borderRadius: 4
						}
					]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
				}
			});
		}

		// Cost comparison
		if (costCompareCanvas) {
			if (costCompareChart) costCompareChart.destroy();
			costCompareChart = new ChartJS(costCompareCanvas, {
				type: 'bar',
				data: {
					labels,
					datasets: [{
						label: 'Cost ($)',
						data: metrics.map(m => m.cost),
						backgroundColor: runColors.slice(0, runs.length),
						borderRadius: 4
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: { y: { beginAtZero: true } }
				}
			});
		}

		// Latency comparison
		if (latencyCompareCanvas) {
			if (latencyCompareChart) latencyCompareChart.destroy();
			latencyCompareChart = new ChartJS(latencyCompareCanvas, {
				type: 'bar',
				data: {
					labels,
					datasets: [{
						label: 'Duration (s)',
						data: metrics.map(m => m.duration / 1000),
						backgroundColor: runColors.slice(0, runs.length),
						borderRadius: 4
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { display: false } },
					scales: { y: { beginAtZero: true } }
				}
			});
		}

		// Radar chart for multi-dimensional comparison
		if (radarCanvas && runs.length >= 2) {
			// Normalize metrics to 0-100 scale
			const maxDuration = Math.max(...metrics.map(m => m.duration)) || 1;
			const maxTokens = Math.max(...metrics.map(m => m.tokens)) || 1;
			const maxCost = Math.max(...metrics.map(m => m.cost)) || 1;
			const maxRecords = Math.max(...metrics.map(m => m.records)) || 1;
			const maxRequests = Math.max(...metrics.map(m => m.requests)) || 1;

			if (radarChart) radarChart.destroy();
			radarChart = new ChartJS(radarCanvas, {
				type: 'radar',
				data: {
					labels: ['Speed', 'Token Efficiency', 'Cost Efficiency', 'Success Rate', 'Throughput'],
					datasets: runs.map((run, i) => ({
						label: getShortLabel(run),
						data: [
							100 - (metrics[i].duration / maxDuration * 100), // Invert: faster is better
							100 - (metrics[i].tokens / maxTokens * 100), // Invert: fewer tokens is better
							100 - (metrics[i].cost / maxCost * 100), // Invert: lower cost is better
							metrics[i].successRate * 100,
							(metrics[i].records / maxRecords) * 100
						],
						borderColor: runColors[i],
						backgroundColor: runColors[i].replace('0.8', '0.2'),
						borderWidth: 2,
						pointRadius: 3
					}))
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { r: { beginAtZero: true, max: 100 } }
				}
			});
		}
	}

	function initModelCharts() {
		const labels = runs.map((r, i) => getShortLabel(r));
		const models = allModels();

		// Model tokens comparison
		if (modelTokensCanvas && models.length > 0) {
			const datasets = models.map((model, mIdx) => ({
				label: model,
				data: runs.map(run => run.metadata?.models?.[model]?.token_statistics?.total_tokens || 0),
				backgroundColor: runColors[mIdx % runColors.length],
				borderRadius: 4
			}));

			if (modelTokensChart) modelTokensChart.destroy();
			modelTokensChart = new ChartJS(modelTokensCanvas, {
				type: 'bar',
				data: { labels, datasets },
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { y: { beginAtZero: true } }
				}
			});
		}

		// Model latency comparison
		if (modelLatencyCanvas && models.length > 0) {
			const datasets = models.map((model, mIdx) => ({
				label: model,
				data: runs.map(run => {
					const m = run.metadata?.models?.[model];
					return m?.performance?.average_latency_seconds ? m.performance.average_latency_seconds * 1000 : 0;
				}),
				backgroundColor: runColors[mIdx % runColors.length],
				borderRadius: 4
			}));

			if (modelLatencyChart) modelLatencyChart.destroy();
			modelLatencyChart = new ChartJS(modelLatencyCanvas, {
				type: 'bar',
				data: { labels, datasets },
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { y: { beginAtZero: true, title: { display: true, text: 'Latency (ms)' } } }
				}
			});
		}
	}

	function initNodeCharts() {
		const labels = runs.map((r, i) => getShortLabel(r));
		const nodes = allNodes();

		// Node latency comparison
		if (nodeLatencyCanvas && nodes.length > 0) {
			const datasets = nodes.map((node, nIdx) => ({
				label: node,
				data: runs.map(run => {
					const n = run.metadata?.nodes?.[node];
					return n?.average_latency_seconds ? n.average_latency_seconds * 1000 : 0;
				}),
				backgroundColor: runColors[nIdx % runColors.length],
				borderRadius: 4
			}));

			if (nodeLatencyChart) nodeLatencyChart.destroy();
			nodeLatencyChart = new ChartJS(nodeLatencyCanvas, {
				type: 'bar',
				data: { labels, datasets },
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: { legend: { position: 'top', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } } },
					scales: { y: { beginAtZero: true, title: { display: true, text: 'Latency (ms)' } } }
				}
			});
		}
	}

	// Initialize charts when tab changes
	$effect(() => {
		if (activeTab === 'overview' || activeTab === 'metrics') {
			setTimeout(initCharts, 50);
		} else if (activeTab === 'models') {
			setTimeout(initModelCharts, 50);
		} else if (activeTab === 'nodes') {
			setTimeout(initNodeCharts, 50);
		}
	});

	onMount(() => {
		initCharts();
		return () => {
			metricsBarChart?.destroy();
			tokenCompareChart?.destroy();
			costCompareChart?.destroy();
			latencyCompareChart?.destroy();
			radarChart?.destroy();
			modelTokensChart?.destroy();
			modelLatencyChart?.destroy();
			nodeLatencyChart?.destroy();
		};
	});

	async function exportComparison() {
		const data = {
			comparison_date: new Date().toISOString(),
			runs: runs.map((run, i) => ({
				id: run.id,
				workflow: run.workflow_name,
				status: run.status,
				metrics: getMetrics(run)
			})),
			summary: comparisonStats()
		};
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `run-comparison-${new Date().toISOString().slice(0, 10)}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	async function copyComparisonSummary() {
		const stats = comparisonStats();
		const summary = `Run Comparison Summary (${runs.length} runs)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Duration: ${formatDuration(stats.duration.min)} - ${formatDuration(stats.duration.max)} (avg: ${formatDuration(stats.duration.avg)})
Tokens: ${formatNumber(stats.tokens.min)} - ${formatNumber(stats.tokens.max)} (avg: ${formatNumber(stats.tokens.avg)})
Cost: ${formatCost(stats.cost.min)} - ${formatCost(stats.cost.max)} (avg: ${formatCost(stats.cost.avg)})
Success Rate: ${formatPercent(stats.successRate.min)} - ${formatPercent(stats.successRate.max)} (avg: ${formatPercent(stats.successRate.avg)})

Runs:
${runs.map((r, i) => `  ${i + 1}. ${r.workflow_name || 'Unknown'} (${r.id.slice(0, 8)}) - ${r.status}`).join('\n')}
`;
		await navigator.clipboard.writeText(summary);
		copied = true;
		setTimeout(() => copied = false, 2000);
	}
</script>

<div class="flex-1 w-full min-h-0 flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div class="flex items-center gap-4">
				<button
					onclick={onBack}
					class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
					title="Back to runs"
				>
					<ArrowLeft size={20} class="text-gray-500" />
				</button>
				<div>
					<h1 class="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
						<GitCompare size={24} class="text-violet-500" />
						Run Comparison
					</h1>
					<p class="text-sm text-gray-500">Comparing {runs.length} runs</p>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<button
					onclick={copyComparisonSummary}
					class="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					{#if copied}
						<Check size={16} class="text-emerald-500" />
						Copied
					{:else}
						<Copy size={16} />
						Copy Summary
					{/if}
				</button>
				<button
					onclick={exportComparison}
					class="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					<Download size={16} />
					Export
				</button>
			</div>
		</div>

		<!-- Run chips -->
		<div class="flex flex-wrap items-center gap-2 mb-4">
			{#each runs as run, i}
				{@const status = statusConfig[run.status] || statusConfig.pending}
				{@const StatusIcon = status.icon}
				<div class="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
					<div class="w-3 h-3 rounded-full" style="background-color: {runColors[i]}"></div>
					<span class="text-sm font-medium text-gray-800 dark:text-gray-200">{run.workflow_name || 'Unknown'}</span>
					<span class="text-xs text-gray-500 font-mono">{run.id.slice(0, 8)}</span>
					<StatusIcon size={14} class="{status.color} {run.status === 'running' ? 'animate-spin' : ''}" />
				</div>
			{/each}
		</div>

		<!-- Tabs -->
		<div class="flex gap-1">
			{#each [
				{ id: 'overview', label: 'Overview', icon: Activity },
				{ id: 'metrics', label: 'Metrics', icon: BarChart3 },
				{ id: 'models', label: 'Models', icon: Cpu },
				{ id: 'nodes', label: 'Nodes', icon: Layers }
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
	<div class="flex-1 min-h-0 overflow-auto p-6">
		{#if activeTab === 'overview'}
			<!-- Overview Tab -->
			<div class="space-y-6">
				<!-- Winner Cards -->
				<div class="grid grid-cols-4 gap-4">
					<!-- Fastest Run -->
					<div class="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl p-4 border border-amber-200 dark:border-amber-800">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-2">
								<Trophy size={18} class="text-amber-600 dark:text-amber-400" />
								<span class="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase">Fastest</span>
							</div>
							<Timer size={16} class="text-amber-500" />
						</div>
						<div class="text-2xl font-bold text-amber-700 dark:text-amber-300 mb-1">
							{formatDuration(getMetrics(fastestRun).duration)}
						</div>
						<div class="text-xs text-amber-600/80 dark:text-amber-400/80 truncate">
							{fastestRun?.workflow_name || 'Unknown'} ({fastestRun?.id.slice(0, 6)})
						</div>
					</div>

					<!-- Most Token Efficient -->
					<div class="bg-gradient-to-br from-violet-50 to-violet-100 dark:from-violet-900/20 dark:to-violet-800/20 rounded-xl p-4 border border-violet-200 dark:border-violet-800">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-2">
								<Medal size={18} class="text-violet-600 dark:text-violet-400" />
								<span class="text-xs font-semibold text-violet-600 dark:text-violet-400 uppercase">Lowest Tokens</span>
							</div>
							<Zap size={16} class="text-violet-500" />
						</div>
						<div class="text-2xl font-bold text-violet-700 dark:text-violet-300 mb-1">
							{formatNumber(getMetrics(lowestTokensRun).tokens)}
						</div>
						<div class="text-xs text-violet-600/80 dark:text-violet-400/80 truncate">
							{lowestTokensRun?.workflow_name || 'Unknown'} ({lowestTokensRun?.id.slice(0, 6)})
						</div>
					</div>

					<!-- Cheapest Run -->
					<div class="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 rounded-xl p-4 border border-emerald-200 dark:border-emerald-800">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-2">
								<Award size={18} class="text-emerald-600 dark:text-emerald-400" />
								<span class="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase">Cheapest</span>
							</div>
							<DollarSign size={16} class="text-emerald-500" />
						</div>
						<div class="text-2xl font-bold text-emerald-700 dark:text-emerald-300 mb-1">
							{formatCost(getMetrics(cheapestRun).cost)}
						</div>
						<div class="text-xs text-emerald-600/80 dark:text-emerald-400/80 truncate">
							{cheapestRun?.workflow_name || 'Unknown'} ({cheapestRun?.id.slice(0, 6)})
						</div>
					</div>

					<!-- Highest Success Rate -->
					<div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-2">
								<Target size={18} class="text-blue-600 dark:text-blue-400" />
								<span class="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase">Most Reliable</span>
							</div>
							<TrendingUp size={16} class="text-blue-500" />
						</div>
						<div class="text-2xl font-bold text-blue-700 dark:text-blue-300 mb-1">
							{formatPercent(getMetrics(mostReliableRun).successRate)}
						</div>
						<div class="text-xs text-blue-600/80 dark:text-blue-400/80 truncate">
							{mostReliableRun?.workflow_name || 'Unknown'} ({mostReliableRun?.id.slice(0, 6)})
						</div>
					</div>
				</div>

				<!-- Charts Row -->
				<div class="grid grid-cols-2 gap-6">
					<!-- Metrics Comparison Bar Chart -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<BarChart3 size={16} class="text-violet-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Duration vs Tokens</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={metricsBarCanvas}></canvas>
						</div>
					</div>

					<!-- Radar Chart -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<Gauge size={16} class="text-blue-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Multi-Dimensional Comparison</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={radarCanvas}></canvas>
						</div>
					</div>
				</div>

				<!-- Detailed Comparison Table -->
				<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
					<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
						<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
							<Activity size={16} class="text-violet-500" />
							Detailed Metrics Comparison
						</h3>
					</div>
					<div class="overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
									<th class="text-left py-3 px-4 font-semibold text-gray-600 dark:text-gray-400 sticky left-0 bg-gray-50 dark:bg-gray-800/50">Metric</th>
									{#each runs as run, i}
										<th class="text-left py-3 px-4 min-w-40">
											<div class="flex items-center gap-2">
												<div class="w-3 h-3 rounded-full flex-shrink-0" style="background-color: {runColors[i]}"></div>
												<div class="flex flex-col">
													<span class="font-medium text-gray-800 dark:text-gray-200 truncate">{run.workflow_name || 'Unknown'}</span>
													<span class="text-xs font-normal text-gray-500 font-mono">{run.id.slice(0, 8)}</span>
												</div>
											</div>
										</th>
									{/each}
									<th class="text-left py-3 px-4 font-semibold text-gray-600 dark:text-gray-400">Range</th>
								</tr>
							</thead>
							<tbody>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">Status</td>
									{#each runs as run, i}
										{@const status = statusConfig[run.status] || statusConfig.pending}
										{@const StatusIcon = status.icon}
										<td class="py-3 px-4">
											<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {status.color} {status.bg}">
												<StatusIcon size={12} class={run.status === 'running' ? 'animate-spin' : ''} />
												{run.status}
											</span>
										</td>
									{/each}
									<td class="py-3 px-4 text-gray-500">-</td>
								</tr>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<Timer size={14} class="text-amber-500" />
											Duration
										</div>
									</td>
									{#each runs as run, i}
										{@const metrics = getMetrics(run)}
										{@const isBest = i === comparisonStats().duration.bestIdx}
										{@const isWorst = i === comparisonStats().duration.worstIdx}
										<td class="py-3 px-4">
											<div class="flex items-center gap-2">
												<span class="font-mono {isBest ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : isWorst ? 'text-red-600 dark:text-red-400' : 'text-gray-800 dark:text-gray-200'}">
													{formatDuration(metrics.duration)}
												</span>
												{#if isBest}
													<Trophy size={14} class="text-amber-500" />
												{/if}
											</div>
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">
										{formatDuration(comparisonStats().duration.min)} - {formatDuration(comparisonStats().duration.max)}
									</td>
								</tr>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<Zap size={14} class="text-violet-500" />
											Tokens
										</div>
									</td>
									{#each runs as run, i}
										{@const metrics = getMetrics(run)}
										{@const isBest = i === comparisonStats().tokens.bestIdx}
										{@const isWorst = i === comparisonStats().tokens.worstIdx}
										<td class="py-3 px-4">
											<div class="flex items-center gap-2">
												<span class="font-mono {isBest ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : isWorst ? 'text-red-600 dark:text-red-400' : 'text-violet-600 dark:text-violet-400'}">
													{formatNumber(metrics.tokens)}
												</span>
												{#if isBest}
													<Medal size={14} class="text-violet-500" />
												{/if}
											</div>
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">
										{formatNumber(comparisonStats().tokens.min)} - {formatNumber(comparisonStats().tokens.max)}
									</td>
								</tr>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<DollarSign size={14} class="text-emerald-500" />
											Cost
										</div>
									</td>
									{#each runs as run, i}
										{@const metrics = getMetrics(run)}
										{@const isBest = i === comparisonStats().cost.bestIdx}
										{@const isWorst = i === comparisonStats().cost.worstIdx}
										<td class="py-3 px-4">
											<div class="flex items-center gap-2">
												<span class="font-mono {isBest ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : isWorst ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}">
													{formatCost(metrics.cost)}
												</span>
												{#if isBest}
													<Award size={14} class="text-emerald-500" />
												{/if}
											</div>
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">
										{formatCost(comparisonStats().cost.min)} - {formatCost(comparisonStats().cost.max)}
									</td>
								</tr>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<TrendingUp size={14} class="text-blue-500" />
											Success Rate
										</div>
									</td>
									{#each runs as run, i}
										{@const metrics = getMetrics(run)}
										{@const isBest = i === comparisonStats().successRate.bestIdx}
										{@const isWorst = i === comparisonStats().successRate.worstIdx}
										<td class="py-3 px-4">
											<div class="flex items-center gap-2">
												<span class="font-medium {isBest ? 'text-emerald-600 dark:text-emerald-400' : isWorst && metrics.successRate < 0.9 ? 'text-red-600 dark:text-red-400' : metrics.successRate >= 0.9 ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}">
													{formatPercent(metrics.successRate)}
												</span>
												{#if isBest}
													<Target size={14} class="text-blue-500" />
												{/if}
											</div>
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">
										{formatPercent(comparisonStats().successRate.min)} - {formatPercent(comparisonStats().successRate.max)}
									</td>
								</tr>
								<tr class="border-b border-gray-100 dark:border-gray-800">
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<Database size={14} class="text-blue-500" />
											Records
										</div>
									</td>
									{#each runs as run}
										{@const metrics = getMetrics(run)}
										<td class="py-3 px-4 text-gray-800 dark:text-gray-200">
											{metrics.records.toLocaleString()}
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">-</td>
								</tr>
								<tr>
									<td class="py-3 px-4 font-medium text-gray-600 dark:text-gray-400 sticky left-0 bg-white dark:bg-gray-800">
										<div class="flex items-center gap-2">
											<Server size={14} class="text-pink-500" />
											Requests
										</div>
									</td>
									{#each runs as run}
										{@const metrics = getMetrics(run)}
										<td class="py-3 px-4 text-gray-800 dark:text-gray-200">
											{metrics.requests} <span class="text-xs text-red-500">({metrics.failures} failed)</span>
										</td>
									{/each}
									<td class="py-3 px-4 text-xs text-gray-500">-</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</div>

		{:else if activeTab === 'metrics'}
			<!-- Metrics Tab -->
			<div class="space-y-6">
				<div class="grid grid-cols-2 gap-6">
					<!-- Token Distribution -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<Zap size={16} class="text-violet-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Distribution</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={tokenCompareCanvas}></canvas>
						</div>
					</div>

					<!-- Cost Comparison -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<DollarSign size={16} class="text-emerald-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Cost Comparison</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={costCompareCanvas}></canvas>
						</div>
					</div>
				</div>

				<div class="grid grid-cols-2 gap-6">
					<!-- Latency Comparison -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<Timer size={16} class="text-amber-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Duration Comparison</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={latencyCompareCanvas}></canvas>
						</div>
					</div>

					<!-- Stats Summary -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<Activity size={16} class="text-blue-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Statistical Summary</h3>
						</div>
						<div class="space-y-4">
							{#each [
								{ label: 'Duration', stats: comparisonStats().duration, format: formatDuration, icon: Timer, color: 'amber' },
								{ label: 'Tokens', stats: comparisonStats().tokens, format: formatNumber, icon: Zap, color: 'violet' },
								{ label: 'Cost', stats: comparisonStats().cost, format: formatCost, icon: DollarSign, color: 'emerald' },
								{ label: 'Success Rate', stats: comparisonStats().successRate, format: formatPercent, icon: TrendingUp, color: 'blue' }
							] as item}
								{@const Icon = item.icon}
								<div class="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
									<div class="flex items-center gap-2">
										<Icon size={16} class="text-{item.color}-500" />
										<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{item.label}</span>
									</div>
									<div class="text-sm text-right">
										<div class="text-gray-500">
											<span class="text-emerald-600 dark:text-emerald-400">{item.format(item.stats.min)}</span>
											<span class="mx-1">→</span>
											<span class="text-red-600 dark:text-red-400">{item.format(item.stats.max)}</span>
										</div>
										<div class="text-xs text-gray-400">avg: {item.format(item.stats.avg)}</div>
									</div>
								</div>
							{/each}
						</div>
					</div>
				</div>
			</div>

		{:else if activeTab === 'models'}
			<!-- Models Tab -->
			<div class="space-y-6">
				{#if allModels().length === 0}
					<div class="text-center py-12 text-gray-500">
						<Cpu size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm font-medium">No model data available</p>
						<p class="text-xs mt-1">Model metrics are collected when runs complete</p>
					</div>
				{:else}
					<div class="grid grid-cols-2 gap-6">
						<!-- Model Token Usage -->
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-4">
								<Zap size={16} class="text-violet-500" />
								<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Usage by Model</h3>
							</div>
							<div class="h-64">
								<canvas bind:this={modelTokensCanvas}></canvas>
							</div>
						</div>

						<!-- Model Latency -->
						<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
							<div class="flex items-center gap-2 mb-4">
								<Timer size={16} class="text-amber-500" />
								<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Average Latency by Model</h3>
							</div>
							<div class="h-64">
								<canvas bind:this={modelLatencyCanvas}></canvas>
							</div>
						</div>
					</div>

					<!-- Model Details Table -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
						<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
								<Cpu size={16} class="text-violet-500" />
								Model Performance Details
							</h3>
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
										<th class="text-left py-3 px-4 font-semibold text-gray-600 dark:text-gray-400">Model</th>
										{#each runs as run, i}
											<th class="text-left py-3 px-4 min-w-48">
												<div class="flex items-center gap-2">
													<div class="w-3 h-3 rounded-full" style="background-color: {runColors[i]}"></div>
													<span class="text-gray-800 dark:text-gray-200 truncate">{run.workflow_name?.slice(0, 15) || run.id.slice(0, 8)}</span>
												</div>
											</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each allModels() as modelName}
										<tr class="border-b border-gray-100 dark:border-gray-800">
											<td class="py-3 px-4 font-medium text-gray-700 dark:text-gray-300">{modelName}</td>
											{#each runs as run}
												{@const model = run.metadata?.models?.[modelName]}
												<td class="py-3 px-4">
													{#if model}
														<div class="space-y-1">
															<div class="flex items-center gap-2 text-xs">
																<Zap size={12} class="text-violet-500" />
																<span class="text-violet-600 dark:text-violet-400">{formatNumber(model.token_statistics?.total_tokens || 0)}</span>
															</div>
															<div class="flex items-center gap-2 text-xs">
																<Timer size={12} class="text-amber-500" />
																<span class="text-amber-600 dark:text-amber-400">{((model.performance?.average_latency_seconds || 0) * 1000).toFixed(0)}ms</span>
															</div>
															<div class="flex items-center gap-2 text-xs">
																<DollarSign size={12} class="text-emerald-500" />
																<span class="text-emerald-600 dark:text-emerald-400">{formatCost(model.cost?.total_cost_usd || 0)}</span>
															</div>
															<div class="flex items-center gap-2 text-xs">
																<Server size={12} class="text-blue-500" />
																<span class="text-blue-600 dark:text-blue-400">{model.performance?.total_requests || 0} req</span>
															</div>
														</div>
													{:else}
														<span class="text-gray-400">-</span>
													{/if}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/if}
			</div>

		{:else if activeTab === 'nodes'}
			<!-- Nodes Tab -->
			<div class="space-y-6">
				{#if allNodes().length === 0}
					<div class="text-center py-12 text-gray-500">
						<Layers size={48} class="mx-auto mb-4 opacity-50" />
						<p class="text-sm font-medium">No node data available</p>
						<p class="text-xs mt-1">Node metrics are collected when runs complete</p>
					</div>
				{:else}
					<!-- Node Latency Chart -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
						<div class="flex items-center gap-2 mb-4">
							<Layers size={16} class="text-blue-500" />
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Node Execution Latency Comparison</h3>
						</div>
						<div class="h-64">
							<canvas bind:this={nodeLatencyCanvas}></canvas>
						</div>
					</div>

					<!-- Node Details Table -->
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
						<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
							<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
								<Layers size={16} class="text-blue-500" />
								Node Execution Details
							</h3>
						</div>
						<div class="overflow-x-auto">
							<table class="w-full text-sm">
								<thead>
									<tr class="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
										<th class="text-left py-3 px-4 font-semibold text-gray-600 dark:text-gray-400">Node</th>
										{#each runs as run, i}
											<th class="text-left py-3 px-4 min-w-40">
												<div class="flex items-center gap-2">
													<div class="w-3 h-3 rounded-full" style="background-color: {runColors[i]}"></div>
													<span class="text-gray-800 dark:text-gray-200 truncate">{run.workflow_name?.slice(0, 15) || run.id.slice(0, 8)}</span>
												</div>
											</th>
										{/each}
									</tr>
								</thead>
								<tbody>
									{#each allNodes() as nodeName}
										<tr class="border-b border-gray-100 dark:border-gray-800">
											<td class="py-3 px-4 font-medium text-gray-700 dark:text-gray-300">{nodeName}</td>
											{#each runs as run}
												{@const node = run.metadata?.nodes?.[nodeName]}
												<td class="py-3 px-4">
													{#if node}
														<div class="space-y-1">
															<div class="text-xs">
																<span class="text-gray-500">Type:</span>
																<span class="ml-1 px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300">{node.node_type}</span>
															</div>
															<div class="text-xs text-gray-600 dark:text-gray-400">
																{node.total_executions} exec • {((node.average_latency_seconds || 0) * 1000).toFixed(0)}ms avg
															</div>
															{#if node.token_statistics}
																<div class="text-xs text-violet-600 dark:text-violet-400">
																	{formatNumber(node.token_statistics.total_tokens)} tokens
																</div>
															{/if}
														</div>
													{:else}
														<span class="text-gray-400">-</span>
													{/if}
												</td>
											{/each}
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
