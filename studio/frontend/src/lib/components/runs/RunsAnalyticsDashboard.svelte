<script lang="ts">
	import { onMount } from 'svelte';
	import { type Execution, type ExecutionMetadata } from '$lib/stores/workflow.svelte';
	import {
		TrendingUp, TrendingDown, Zap, DollarSign, Clock, CheckCircle2,
		XCircle, Activity, BarChart3, PieChart, LineChart, Cpu, Server,
		ArrowRight, Timer, Hash, Layers, GitCompare, Target, Gauge
	} from 'lucide-svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	interface Props {
		runs: Execution[];
		totalRuns: number;
	}

	let { runs, totalRuns }: Props = $props();

	// Chart canvas refs
	let tokenChartCanvas: HTMLCanvasElement;
	let costChartCanvas: HTMLCanvasElement;
	let latencyChartCanvas: HTMLCanvasElement;
	let runsTimelineCanvas: HTMLCanvasElement;
	let modelComparisonCanvas: HTMLCanvasElement;
	let nodeHeatmapCanvas: HTMLCanvasElement;

	// Chart instances
	let tokenChart: Chart | null = null;
	let costChart: Chart | null = null;
	let latencyChart: Chart | null = null;
	let runsTimelineChart: Chart | null = null;
	let modelComparisonChart: Chart | null = null;
	let nodeHeatmapChart: Chart | null = null;

	// Computed stats from filtered runs
	let stats = $derived(() => {
		const completedRuns = runs.filter(r => r.status === 'completed' && r.metadata);
		const failedRuns = runs.filter(r => r.status === 'failed');

		let totalTokens = 0;
		let totalCost = 0;
		let totalDuration = 0;
		let totalRecords = 0;
		let modelStats: Record<string, { tokens: number; cost: number; requests: number; latency: number }> = {};
		let nodeStats: Record<string, { executions: number; avgLatency: number; totalLatency: number }> = {};

		completedRuns.forEach(run => {
			if (run.metadata) {
				const m = run.metadata;
				totalTokens += m.aggregate_statistics.tokens.total_tokens;
				totalCost += m.aggregate_statistics.cost.total_cost_usd;
				totalRecords += m.aggregate_statistics.records.total_processed;

				// Model stats
				Object.entries(m.models).forEach(([name, model]) => {
					if (!modelStats[name]) {
						modelStats[name] = { tokens: 0, cost: 0, requests: 0, latency: 0 };
					}
					modelStats[name].tokens += model.token_statistics.total_tokens;
					modelStats[name].cost += model.cost.total_cost_usd;
					modelStats[name].requests += model.performance.total_requests;
					modelStats[name].latency += model.performance.total_latency_seconds;
				});

				// Node stats
				Object.entries(m.nodes).forEach(([name, node]) => {
					if (!nodeStats[name]) {
						nodeStats[name] = { executions: 0, avgLatency: 0, totalLatency: 0 };
					}
					nodeStats[name].executions += node.total_executions;
					nodeStats[name].totalLatency += node.total_latency_seconds;
				});
			}
			if (run.duration_ms) {
				totalDuration += run.duration_ms;
			}
		});

		// Calculate average latencies
		Object.keys(nodeStats).forEach(name => {
			if (nodeStats[name].executions > 0) {
				nodeStats[name].avgLatency = nodeStats[name].totalLatency / nodeStats[name].executions;
			}
		});

		const avgDuration = completedRuns.length > 0 ? totalDuration / completedRuns.length : 0;
		const successRate = runs.length > 0 ? (completedRuns.length / runs.length) * 100 : 0;
		const avgTokensPerRun = completedRuns.length > 0 ? totalTokens / completedRuns.length : 0;
		const avgCostPerRun = completedRuns.length > 0 ? totalCost / completedRuns.length : 0;

		return {
			totalRuns: runs.length,
			completedRuns: completedRuns.length,
			failedRuns: failedRuns.length,
			runningRuns: runs.filter(r => r.status === 'running').length,
			totalTokens,
			totalCost,
			totalRecords,
			avgDuration,
			successRate,
			avgTokensPerRun,
			avgCostPerRun,
			modelStats,
			nodeStats,
			recentRuns: runs.slice(0, 10)
		};
	});

	// Token speed stats (tokens per second)
	let tokenSpeedStats = $derived(() => {
		const completedRuns = runs.filter(r => r.status === 'completed' && r.metadata);
		let speeds: number[] = [];

		completedRuns.forEach(run => {
			if (run.metadata && run.duration_ms && run.duration_ms > 0) {
				const tokens = run.metadata.aggregate_statistics.tokens.total_tokens;
				const seconds = run.duration_ms / 1000;
				speeds.push(tokens / seconds);
			}
		});

		if (speeds.length === 0) return { avg: 0, min: 0, max: 0, data: [] };

		return {
			avg: speeds.reduce((a, b) => a + b, 0) / speeds.length,
			min: Math.min(...speeds),
			max: Math.max(...speeds),
			data: speeds
		};
	});

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toLocaleString();
	}

	function formatCost(usd: number): string {
		if (usd < 0.01) return `<$0.01`;
		return `$${usd.toFixed(2)}`;
	}

	function formatDuration(ms: number): string {
		if (ms < 1000) return `${ms.toFixed(0)}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		const m = Math.floor(s / 60);
		const remainingS = s % 60;
		return `${m}m ${remainingS.toFixed(0)}s`;
	}

	// Initialize charts
	function initCharts() {
		const s = stats();
		const completedRuns = runs.filter(r => r.status === 'completed' && r.metadata);

		// Token Usage Chart (Bar)
		if (tokenChartCanvas && completedRuns.length > 0) {
			const labels = completedRuns.slice(-10).map(r => r.workflow_name?.slice(0, 15) || r.id.slice(0, 8));
			const promptTokens = completedRuns.slice(-10).map(r => r.metadata?.aggregate_statistics.tokens.total_prompt_tokens || 0);
			const completionTokens = completedRuns.slice(-10).map(r => r.metadata?.aggregate_statistics.tokens.total_completion_tokens || 0);

			if (tokenChart) tokenChart.destroy();
			tokenChart = new Chart(tokenChartCanvas, {
				type: 'bar',
				data: {
					labels,
					datasets: [
						{
							label: 'Prompt Tokens',
							data: promptTokens,
							backgroundColor: 'rgba(139, 92, 246, 0.8)',
							borderRadius: 4
						},
						{
							label: 'Completion Tokens',
							data: completionTokens,
							backgroundColor: 'rgba(59, 130, 246, 0.8)',
							borderRadius: 4
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
						x: { stacked: true, grid: { display: false } },
						y: { stacked: true, beginAtZero: true }
					}
				}
			});
		}

		// Cost Chart (Doughnut)
		if (costChartCanvas && Object.keys(s.modelStats).length > 0) {
			const modelNames = Object.keys(s.modelStats);
			const modelCosts = modelNames.map(n => s.modelStats[n].cost);

			if (costChart) costChart.destroy();
			costChart = new Chart(costChartCanvas, {
				type: 'doughnut',
				data: {
					labels: modelNames,
					datasets: [{
						data: modelCosts,
						backgroundColor: [
							'rgba(16, 185, 129, 0.8)',
							'rgba(139, 92, 246, 0.8)',
							'rgba(59, 130, 246, 0.8)',
							'rgba(245, 158, 11, 0.8)',
							'rgba(239, 68, 68, 0.8)'
						],
						borderWidth: 0
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					cutout: '60%',
					plugins: {
						legend: { position: 'right', labels: { boxWidth: 12, padding: 8, font: { size: 11 } } }
					}
				}
			});
		}

		// Latency Distribution Chart (Line)
		if (latencyChartCanvas && completedRuns.length > 0) {
			const labels = completedRuns.slice(-15).map((_, i) => `Run ${i + 1}`);
			const latencies = completedRuns.slice(-15).map(r => (r.duration_ms || 0) / 1000);

			if (latencyChart) latencyChart.destroy();
			latencyChart = new Chart(latencyChartCanvas, {
				type: 'line',
				data: {
					labels,
					datasets: [{
						label: 'Duration (s)',
						data: latencies,
						borderColor: 'rgba(245, 158, 11, 1)',
						backgroundColor: 'rgba(245, 158, 11, 0.1)',
						fill: true,
						tension: 0.4,
						pointRadius: 4,
						pointBackgroundColor: 'rgba(245, 158, 11, 1)'
					}]
				},
				options: {
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						legend: { display: false }
					},
					scales: {
						y: { beginAtZero: true }
					}
				}
			});
		}

		// Runs Timeline (Bar - success/failed over time)
		if (runsTimelineCanvas && runs.length > 0) {
			// Group by date
			const dateGroups: Record<string, { completed: number; failed: number }> = {};
			runs.forEach(run => {
				if (run.started_at) {
					const date = new Date(run.started_at).toLocaleDateString();
					if (!dateGroups[date]) dateGroups[date] = { completed: 0, failed: 0 };
					if (run.status === 'completed') dateGroups[date].completed++;
					else if (run.status === 'failed') dateGroups[date].failed++;
				}
			});

			const dates = Object.keys(dateGroups).slice(-7);
			const completed = dates.map(d => dateGroups[d].completed);
			const failed = dates.map(d => dateGroups[d].failed);

			if (runsTimelineChart) runsTimelineChart.destroy();
			runsTimelineChart = new Chart(runsTimelineCanvas, {
				type: 'bar',
				data: {
					labels: dates,
					datasets: [
						{
							label: 'Completed',
							data: completed,
							backgroundColor: 'rgba(16, 185, 129, 0.8)',
							borderRadius: 4
						},
						{
							label: 'Failed',
							data: failed,
							backgroundColor: 'rgba(239, 68, 68, 0.8)',
							borderRadius: 4
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
						x: { stacked: true, grid: { display: false } },
						y: { stacked: true, beginAtZero: true }
					}
				}
			});
		}

		// Model Comparison (Horizontal Bar)
		if (modelComparisonCanvas && Object.keys(s.modelStats).length > 0) {
			const modelNames = Object.keys(s.modelStats);
			const avgLatencies = modelNames.map(n => {
				const m = s.modelStats[n];
				return m.requests > 0 ? (m.latency / m.requests) * 1000 : 0; // ms
			});

			if (modelComparisonChart) modelComparisonChart.destroy();
			modelComparisonChart = new Chart(modelComparisonCanvas, {
				type: 'bar',
				data: {
					labels: modelNames,
					datasets: [{
						label: 'Avg Latency (ms)',
						data: avgLatencies,
						backgroundColor: 'rgba(139, 92, 246, 0.8)',
						borderRadius: 4
					}]
				},
				options: {
					indexAxis: 'y',
					responsive: true,
					maintainAspectRatio: false,
					plugins: {
						legend: { display: false }
					},
					scales: {
						x: { beginAtZero: true }
					}
				}
			});
		}

		// Node Heatmap (Bar showing node latencies)
		if (nodeHeatmapCanvas && Object.keys(s.nodeStats).length > 0) {
			const nodeNames = Object.keys(s.nodeStats);
			const avgLatencies = nodeNames.map(n => s.nodeStats[n].avgLatency * 1000); // ms

			// Color based on latency (green to red)
			const colors = avgLatencies.map(l => {
				const max = Math.max(...avgLatencies);
				const ratio = max > 0 ? l / max : 0;
				if (ratio < 0.33) return 'rgba(16, 185, 129, 0.8)';
				if (ratio < 0.66) return 'rgba(245, 158, 11, 0.8)';
				return 'rgba(239, 68, 68, 0.8)';
			});

			if (nodeHeatmapChart) nodeHeatmapChart.destroy();
			nodeHeatmapChart = new Chart(nodeHeatmapCanvas, {
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
					plugins: {
						legend: { display: false }
					},
					scales: {
						x: { beginAtZero: true }
					}
				}
			});
		}
	}

	// Reactive chart updates when runs change
	$effect(() => {
		if (runs.length > 0) {
			// Small delay to ensure canvas is rendered
			setTimeout(initCharts, 100);
		}
	});

	onMount(() => {
		initCharts();
		return () => {
			// Cleanup charts
			tokenChart?.destroy();
			costChart?.destroy();
			latencyChart?.destroy();
			runsTimelineChart?.destroy();
			modelComparisonChart?.destroy();
			nodeHeatmapChart?.destroy();
		};
	});
</script>

<div class="space-y-6">
	<!-- Summary Cards Row -->
	<div class="grid grid-cols-6 gap-4">
		<!-- Filtered Runs -->
		<div class="bg-gradient-to-br from-violet-50 to-violet-100 dark:from-violet-900/20 dark:to-violet-800/20 rounded-xl p-4 border border-violet-200 dark:border-violet-800">
			<div class="flex items-center justify-between mb-2">
				<Activity size={18} class="text-violet-600 dark:text-violet-400" />
				<span class="text-xs px-2 py-0.5 rounded-full bg-violet-200 dark:bg-violet-800 text-violet-700 dark:text-violet-300">
					{stats().runningRuns} running
				</span>
			</div>
			<div class="text-2xl font-bold text-violet-700 dark:text-violet-300">{runs.length}</div>
			<div class="text-xs text-violet-600/70 dark:text-violet-400/70">
				{#if runs.length !== totalRuns}Filtered from {totalRuns}{:else}Total Runs{/if}
			</div>
		</div>

		<!-- Success Rate -->
		<div class="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 rounded-xl p-4 border border-emerald-200 dark:border-emerald-800">
			<div class="flex items-center justify-between mb-2">
				<Target size={18} class="text-emerald-600 dark:text-emerald-400" />
				{#if stats().successRate >= 90}
					<TrendingUp size={16} class="text-emerald-500" />
				{:else}
					<TrendingDown size={16} class="text-red-500" />
				{/if}
			</div>
			<div class="text-2xl font-bold text-emerald-700 dark:text-emerald-300">{stats().successRate.toFixed(1)}%</div>
			<div class="text-xs text-emerald-600/70 dark:text-emerald-400/70">Success Rate</div>
		</div>

		<!-- Total Tokens -->
		<div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
			<div class="flex items-center justify-between mb-2">
				<Zap size={18} class="text-blue-600 dark:text-blue-400" />
				<span class="text-xs text-blue-500">{formatNumber(stats().avgTokensPerRun)}/run</span>
			</div>
			<div class="text-2xl font-bold text-blue-700 dark:text-blue-300">{formatNumber(stats().totalTokens)}</div>
			<div class="text-xs text-blue-600/70 dark:text-blue-400/70">Total Tokens</div>
		</div>

		<!-- Total Cost -->
		<div class="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 rounded-xl p-4 border border-green-200 dark:border-green-800">
			<div class="flex items-center justify-between mb-2">
				<DollarSign size={18} class="text-green-600 dark:text-green-400" />
				<span class="text-xs text-green-500">{formatCost(stats().avgCostPerRun)}/run</span>
			</div>
			<div class="text-2xl font-bold text-green-700 dark:text-green-300">{formatCost(stats().totalCost)}</div>
			<div class="text-xs text-green-600/70 dark:text-green-400/70">Total Cost</div>
		</div>

		<!-- Token Speed -->
		<div class="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl p-4 border border-amber-200 dark:border-amber-800">
			<div class="flex items-center justify-between mb-2">
				<Gauge size={18} class="text-amber-600 dark:text-amber-400" />
				<span class="text-xs text-amber-500">
					{tokenSpeedStats().max > 0 ? `max ${tokenSpeedStats().max.toFixed(0)}` : '-'}
				</span>
			</div>
			<div class="text-2xl font-bold text-amber-700 dark:text-amber-300">
				{tokenSpeedStats().avg > 0 ? tokenSpeedStats().avg.toFixed(0) : '-'}
			</div>
			<div class="text-xs text-amber-600/70 dark:text-amber-400/70">Avg Tokens/sec</div>
		</div>

		<!-- Avg Duration -->
		<div class="bg-gradient-to-br from-pink-50 to-pink-100 dark:from-pink-900/20 dark:to-pink-800/20 rounded-xl p-4 border border-pink-200 dark:border-pink-800">
			<div class="flex items-center justify-between mb-2">
				<Timer size={18} class="text-pink-600 dark:text-pink-400" />
				<span class="text-xs text-pink-500">{stats().totalRecords.toLocaleString()} records</span>
			</div>
			<div class="text-2xl font-bold text-pink-700 dark:text-pink-300">{formatDuration(stats().avgDuration)}</div>
			<div class="text-xs text-pink-600/70 dark:text-pink-400/70">Avg Duration</div>
		</div>
	</div>

	<!-- Charts Row 1 -->
	<div class="grid grid-cols-3 gap-4">
		<!-- Token Usage Chart -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<BarChart3 size={16} class="text-violet-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Token Usage by Run</h3>
			</div>
			<div class="h-48">
				<canvas bind:this={tokenChartCanvas}></canvas>
			</div>
		</div>

		<!-- Cost Breakdown -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<PieChart size={16} class="text-emerald-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Cost by Model</h3>
			</div>
			<div class="h-48">
				<canvas bind:this={costChartCanvas}></canvas>
			</div>
		</div>

		<!-- Latency Trend -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<LineChart size={16} class="text-amber-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Latency Trend</h3>
			</div>
			<div class="h-48">
				<canvas bind:this={latencyChartCanvas}></canvas>
			</div>
		</div>
	</div>

	<!-- Charts Row 2 -->
	<div class="grid grid-cols-3 gap-4">
		<!-- Runs Timeline -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<Activity size={16} class="text-blue-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Runs Over Time</h3>
			</div>
			<div class="h-48">
				<canvas bind:this={runsTimelineCanvas}></canvas>
			</div>
		</div>

		<!-- Model Performance Comparison -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<Cpu size={16} class="text-violet-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Model Latency Comparison</h3>
			</div>
			<div class="h-48">
				<canvas bind:this={modelComparisonCanvas}></canvas>
			</div>
		</div>

		<!-- Node Latency Heatmap -->
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<Layers size={16} class="text-red-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Node Latency Heatmap</h3>
				<span class="ml-auto flex items-center gap-1 text-xs">
					<span class="w-2 h-2 rounded bg-emerald-500"></span>Fast
					<span class="w-2 h-2 rounded bg-amber-500 ml-2"></span>Medium
					<span class="w-2 h-2 rounded bg-red-500 ml-2"></span>Slow
				</span>
			</div>
			<div class="h-48">
				<canvas bind:this={nodeHeatmapCanvas}></canvas>
			</div>
		</div>
	</div>

	<!-- Model Performance Table -->
	{#if Object.keys(stats().modelStats).length > 0}
		<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
			<div class="flex items-center gap-2 mb-4">
				<Server size={16} class="text-violet-500" />
				<h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Model Performance Summary</h3>
			</div>
			<table class="w-full text-sm">
				<thead>
					<tr class="text-left text-xs text-gray-500 uppercase border-b border-gray-200 dark:border-gray-700">
						<th class="pb-2 font-medium">Model</th>
						<th class="pb-2 font-medium text-right">Requests</th>
						<th class="pb-2 font-medium text-right">Total Tokens</th>
						<th class="pb-2 font-medium text-right">Avg Latency</th>
						<th class="pb-2 font-medium text-right">Throughput</th>
						<th class="pb-2 font-medium text-right">Total Cost</th>
						<th class="pb-2 font-medium text-right">Cost/Request</th>
					</tr>
				</thead>
				<tbody>
					{#each Object.entries(stats().modelStats) as [name, model]}
						{@const avgLatency = model.requests > 0 ? model.latency / model.requests : 0}
						{@const throughput = model.latency > 0 ? model.tokens / model.latency : 0}
						{@const costPerReq = model.requests > 0 ? model.cost / model.requests : 0}
						<tr class="border-b border-gray-100 dark:border-gray-800">
							<td class="py-3 font-medium text-gray-800 dark:text-gray-200">{name}</td>
							<td class="py-3 text-right text-gray-600 dark:text-gray-400">{model.requests.toLocaleString()}</td>
							<td class="py-3 text-right text-gray-600 dark:text-gray-400">{formatNumber(model.tokens)}</td>
							<td class="py-3 text-right text-gray-600 dark:text-gray-400">{(avgLatency * 1000).toFixed(0)}ms</td>
							<td class="py-3 text-right">
								<span class="text-emerald-600 dark:text-emerald-400 font-medium">{throughput.toFixed(1)} tok/s</span>
							</td>
							<td class="py-3 text-right text-gray-600 dark:text-gray-400">{formatCost(model.cost)}</td>
							<td class="py-3 text-right text-gray-600 dark:text-gray-400">{formatCost(costPerReq)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}

	<!-- Quick Stats Cards -->
	<div class="grid grid-cols-4 gap-4">
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 flex items-center gap-3">
			<CheckCircle2 size={20} class="text-emerald-500" />
			<div>
				<div class="text-lg font-bold text-gray-800 dark:text-gray-200">{stats().completedRuns}</div>
				<div class="text-xs text-gray-500">Completed</div>
			</div>
		</div>
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 flex items-center gap-3">
			<XCircle size={20} class="text-red-500" />
			<div>
				<div class="text-lg font-bold text-gray-800 dark:text-gray-200">{stats().failedRuns}</div>
				<div class="text-xs text-gray-500">Failed</div>
			</div>
		</div>
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 flex items-center gap-3">
			<Hash size={20} class="text-blue-500" />
			<div>
				<div class="text-lg font-bold text-gray-800 dark:text-gray-200">{Object.keys(stats().modelStats).length}</div>
				<div class="text-xs text-gray-500">Models Used</div>
			</div>
		</div>
		<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 flex items-center gap-3">
			<Layers size={20} class="text-violet-500" />
			<div>
				<div class="text-lg font-bold text-gray-800 dark:text-gray-200">{Object.keys(stats().nodeStats).length}</div>
				<div class="text-xs text-gray-500">Unique Nodes</div>
			</div>
		</div>
	</div>
</div>
