<script lang="ts">
	import { onMount } from 'svelte';
	import { type Execution } from '$lib/stores/workflow.svelte';
	import {
		TrendingUp, TrendingDown, Zap, DollarSign, CheckCircle2, XCircle, Activity,
		BarChart3, PieChart, LineChart, Cpu, Server, Timer, Layers, Target, Gauge,
		AlertTriangle, Award, Lightbulb, Sparkles, Info, Calendar, Database, CircleDollarSign
	} from 'lucide-svelte';
	import type { Chart as ChartType } from 'chart.js';

	// Chart.js will be lazy loaded
	let ChartJS: typeof ChartType | null = null;
	let chartJsLoaded = $state(false);

	interface Props { runs: Execution[]; totalRuns: number; }
	let { runs, totalRuns }: Props = $props();

	type TabType = 'overview' | 'models' | 'performance' | 'cost';
	let activeTab = $state<TabType>('overview');

	let tokenChartCanvas: HTMLCanvasElement;
	let costChartCanvas: HTMLCanvasElement;
	let latencyChartCanvas: HTMLCanvasElement;
	let runsTimelineCanvas: HTMLCanvasElement;
	let modelLatencyCanvas: HTMLCanvasElement;
	let throughputChartCanvas: HTMLCanvasElement;
	let costTrendCanvas: HTMLCanvasElement;

	let charts: Record<string, ChartType | null> = {};

	let stats = $derived(() => {
		const completedRuns = runs.filter(r => r.status === 'completed' && r.metadata);
		let totalTokens = 0, totalPromptTokens = 0, totalCompletionTokens = 0, totalCost = 0, totalDuration = 0, totalRecords = 0, totalRequests = 0;
		let modelStats: Record<string, { tokens: number; promptTokens: number; completionTokens: number; cost: number; requests: number; latency: number }> = {};
		let nodeStats: Record<string, { executions: number; avgLatency: number; totalLatency: number }> = {};
		let workflowStats: Record<string, { runs: number; cost: number; tokens: number; avgDuration: number; totalDuration: number }> = {};

		completedRuns.forEach(run => {
			if (run.metadata) {
				const m = run.metadata;
				totalTokens += m.aggregate_statistics.tokens.total_tokens;
				totalPromptTokens += m.aggregate_statistics.tokens.total_prompt_tokens;
				totalCompletionTokens += m.aggregate_statistics.tokens.total_completion_tokens;
				totalCost += m.aggregate_statistics.cost.total_cost_usd;
				totalRecords += m.aggregate_statistics.records.total_processed;
				totalRequests += m.aggregate_statistics.requests.total_requests;

				Object.entries(m.models).forEach(([name, model]) => {
					if (!modelStats[name]) modelStats[name] = { tokens: 0, promptTokens: 0, completionTokens: 0, cost: 0, requests: 0, latency: 0 };
					modelStats[name].tokens += model.token_statistics.total_tokens;
					modelStats[name].promptTokens += model.token_statistics.prompt_tokens;
					modelStats[name].completionTokens += model.token_statistics.completion_tokens;
					modelStats[name].cost += model.cost.total_cost_usd;
					modelStats[name].requests += model.performance.total_requests;
					modelStats[name].latency += model.performance.total_latency_seconds;
				});

				Object.entries(m.nodes).forEach(([name, node]) => {
					if (!nodeStats[name]) nodeStats[name] = { executions: 0, avgLatency: 0, totalLatency: 0 };
					nodeStats[name].executions += node.total_executions;
					nodeStats[name].totalLatency += node.total_latency_seconds;
				});

				const wfName = run.workflow_name || 'Unknown';
				if (!workflowStats[wfName]) workflowStats[wfName] = { runs: 0, cost: 0, tokens: 0, avgDuration: 0, totalDuration: 0 };
				workflowStats[wfName].runs += 1;
				workflowStats[wfName].cost += m.aggregate_statistics.cost.total_cost_usd;
				workflowStats[wfName].tokens += m.aggregate_statistics.tokens.total_tokens;
				workflowStats[wfName].totalDuration += run.duration_ms || 0;
			}
			if (run.duration_ms) totalDuration += run.duration_ms;
		});

		Object.keys(nodeStats).forEach(n => { if (nodeStats[n].executions > 0) nodeStats[n].avgLatency = nodeStats[n].totalLatency / nodeStats[n].executions; });
		Object.keys(workflowStats).forEach(n => { if (workflowStats[n].runs > 0) workflowStats[n].avgDuration = workflowStats[n].totalDuration / workflowStats[n].runs; });

		const avgDuration = completedRuns.length > 0 ? totalDuration / completedRuns.length : 0;
		const successRate = runs.length > 0 ? (completedRuns.length / runs.length) * 100 : 0;

		return {
			totalRuns: runs.length, completedRuns: completedRuns.length, failedRuns: runs.filter(r => r.status === 'failed').length,
			runningRuns: runs.filter(r => r.status === 'running').length, totalTokens, totalPromptTokens, totalCompletionTokens,
			totalCost, totalRecords, totalRequests, avgDuration, successRate,
			avgTokensPerRun: completedRuns.length > 0 ? totalTokens / completedRuns.length : 0,
			avgCostPerRun: completedRuns.length > 0 ? totalCost / completedRuns.length : 0,
			avgTokensPerSecond: totalDuration > 0 ? totalTokens / (totalDuration / 1000) : 0,
			modelStats, nodeStats, workflowStats
		};
	});

	let insights = $derived(() => {
		const s = stats(); const list: Array<{ type: 'success' | 'warning' | 'info' | 'tip'; title: string; description: string; metric?: string }> = [];
		if (s.successRate >= 95) list.push({ type: 'success', title: 'Excellent Success Rate', description: `${s.successRate.toFixed(1)}% of runs completed successfully.`, metric: `${s.successRate.toFixed(1)}%` });
		else if (s.successRate < 80 && s.totalRuns > 5) list.push({ type: 'warning', title: 'Low Success Rate', description: `Only ${s.successRate.toFixed(1)}% success. Review failed runs.`, metric: `${s.successRate.toFixed(1)}%` });
		if (s.avgTokensPerSecond > 100) list.push({ type: 'success', title: 'High Throughput', description: `${s.avgTokensPerSecond.toFixed(0)} tokens/sec average throughput.`, metric: `${s.avgTokensPerSecond.toFixed(0)} tok/s` });
		const nodeEntries = Object.entries(s.nodeStats);
		if (nodeEntries.length > 1) {
			const slowest = nodeEntries.reduce((a, b) => a[1].avgLatency > b[1].avgLatency ? a : b);
			if (slowest[1].avgLatency > 1) list.push({ type: 'info', title: 'Bottleneck Detected', description: `"${slowest[0]}" has highest latency. Consider optimizing.`, metric: `${(slowest[1].avgLatency * 1000).toFixed(0)}ms` });
		}
		return list;
	});

	let performers = $derived(() => {
		const s = stats(); const m = Object.entries(s.modelStats);
		let fastest = { name: '-', value: 0 }, cheapest = { name: '-', value: 0 }, mostUsed = { name: '-', value: 0 };
		if (m.length > 0) {
			const byLat = m.filter(([_, x]) => x.requests > 0).sort((a, b) => (a[1].latency / a[1].requests) - (b[1].latency / b[1].requests));
			if (byLat.length) fastest = { name: byLat[0][0], value: (byLat[0][1].latency / byLat[0][1].requests) * 1000 };
			const byCost = m.filter(([_, x]) => x.tokens > 0).sort((a, b) => (a[1].cost / a[1].tokens) - (b[1].cost / b[1].tokens));
			if (byCost.length) cheapest = { name: byCost[0][0], value: (byCost[0][1].cost / byCost[0][1].tokens) * 1000000 };
			const byUse = m.sort((a, b) => b[1].requests - a[1].requests);
			if (byUse.length) mostUsed = { name: byUse[0][0], value: byUse[0][1].requests };
		}
		return { fastest, cheapest, mostUsed };
	});

	function formatNumber(n: number): string { if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`; if (n >= 1000) return `${(n / 1000).toFixed(1)}K`; return n.toLocaleString(); }
	function formatCost(usd: number): string { if (usd < 0.001) return `<$0.001`; if (usd < 0.01) return `$${usd.toFixed(4)}`; return `$${usd.toFixed(2)}`; }
	function formatDuration(ms: number): string { if (ms < 1000) return `${ms.toFixed(0)}ms`; const s = ms / 1000; if (s < 60) return `${s.toFixed(1)}s`; return `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`; }

	const colors = {
		violet: { main: 'rgba(139, 92, 246, 1)', light: 'rgba(139, 92, 246, 0.2)', bg: 'rgba(139, 92, 246, 0.8)' },
		blue: { main: 'rgba(59, 130, 246, 1)', light: 'rgba(59, 130, 246, 0.2)', bg: 'rgba(59, 130, 246, 0.8)' },
		emerald: { main: 'rgba(16, 185, 129, 1)', light: 'rgba(16, 185, 129, 0.2)', bg: 'rgba(16, 185, 129, 0.8)' },
		amber: { main: 'rgba(245, 158, 11, 1)', light: 'rgba(245, 158, 11, 0.2)', bg: 'rgba(245, 158, 11, 0.8)' },
		red: { main: 'rgba(239, 68, 68, 1)', light: 'rgba(239, 68, 68, 0.2)', bg: 'rgba(239, 68, 68, 0.8)' },
		pink: { main: 'rgba(236, 72, 153, 1)', bg: 'rgba(236, 72, 153, 0.8)' },
	};
	const chartColors = [colors.violet.bg, colors.blue.bg, colors.emerald.bg, colors.amber.bg, colors.pink.bg, colors.red.bg];
	const commonOpts = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'top' as const, labels: { boxWidth: 12, padding: 12, font: { size: 11 }, usePointStyle: true } } } };

	async function initCharts() {
		// Lazy load Chart.js if not already loaded
		if (!ChartJS) {
			const { Chart, registerables } = await import('chart.js');
			Chart.register(...registerables);
			ChartJS = Chart;
			chartJsLoaded = true;
		}

		const s = stats(); const completedRuns = runs.filter(r => r.status === 'completed' && r.metadata);

		if (activeTab === 'overview' || activeTab === 'models') {
			if (tokenChartCanvas && completedRuns.length > 0) {
				const recent = completedRuns.slice(-12);
				if (charts.token) charts.token.destroy();
				charts.token = new ChartJS(tokenChartCanvas, { type: 'bar', data: { labels: recent.map(r => r.workflow_name?.slice(0, 10) || r.id.slice(0, 6)), datasets: [{ label: 'Prompt', data: recent.map(r => r.metadata?.aggregate_statistics.tokens.total_prompt_tokens || 0), backgroundColor: colors.violet.bg, borderRadius: 4 }, { label: 'Completion', data: recent.map(r => r.metadata?.aggregate_statistics.tokens.total_completion_tokens || 0), backgroundColor: colors.blue.bg, borderRadius: 4 }] }, options: { ...commonOpts, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } } } });
			}
			if (runsTimelineCanvas && runs.length > 0) {
				const groups: Record<string, { completed: number; failed: number }> = {};
				runs.forEach(r => { if (r.started_at) { const d = new Date(r.started_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); if (!groups[d]) groups[d] = { completed: 0, failed: 0 }; if (r.status === 'completed') groups[d].completed++; else if (r.status === 'failed') groups[d].failed++; } });
				const dates = Object.keys(groups).slice(-10);
				if (charts.timeline) charts.timeline.destroy();
				charts.timeline = new ChartJS(runsTimelineCanvas, { type: 'bar', data: { labels: dates, datasets: [{ label: 'Completed', data: dates.map(d => groups[d].completed), backgroundColor: colors.emerald.bg, borderRadius: 4 }, { label: 'Failed', data: dates.map(d => groups[d].failed), backgroundColor: colors.red.bg, borderRadius: 4 }] }, options: { ...commonOpts, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true } } } });
			}
			if (latencyChartCanvas && completedRuns.length > 0) {
				const recent = completedRuns.slice(-15); const latencies = recent.map(r => (r.duration_ms || 0) / 1000);
				if (charts.latency) charts.latency.destroy();
				charts.latency = new ChartJS(latencyChartCanvas, { type: 'line', data: { labels: recent.map((_, i) => `${i + 1}`), datasets: [{ label: 'Duration (s)', data: latencies, borderColor: colors.amber.main, backgroundColor: colors.amber.light, fill: true, tension: 0.4, pointRadius: 3 }] }, options: { ...commonOpts, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true }, x: { grid: { display: false } } } } });
			}
			if (costChartCanvas && Object.keys(s.modelStats).length > 0) {
				const names = Object.keys(s.modelStats);
				if (charts.cost) charts.cost.destroy();
				charts.cost = new ChartJS(costChartCanvas, { type: 'doughnut', data: { labels: names, datasets: [{ data: names.map(n => s.modelStats[n].cost), backgroundColor: chartColors.slice(0, names.length), borderWidth: 0 }] }, options: { responsive: true, maintainAspectRatio: false, cutout: '65%', plugins: { legend: { position: 'right', labels: { boxWidth: 12, padding: 12, font: { size: 11 } } } } } });
			}
		}
		if (activeTab === 'models' && modelLatencyCanvas && Object.keys(s.modelStats).length > 0) {
			const names = Object.keys(s.modelStats);
			if (charts.modelLatency) charts.modelLatency.destroy();
			charts.modelLatency = new ChartJS(modelLatencyCanvas, { type: 'bar', data: { labels: names, datasets: [{ label: 'Avg Latency (ms)', data: names.map(n => { const m = s.modelStats[n]; return m.requests > 0 ? (m.latency / m.requests) * 1000 : 0; }), backgroundColor: chartColors.slice(0, names.length), borderRadius: 4 }] }, options: { ...commonOpts, indexAxis: 'y', plugins: { legend: { display: false } } } });
		}
		if (activeTab === 'performance' && throughputChartCanvas && completedRuns.length > 0) {
			const recent = completedRuns.slice(-15); const throughputs = recent.map(r => r.metadata && r.duration_ms ? r.metadata.aggregate_statistics.tokens.total_tokens / (r.duration_ms / 1000) : 0);
			if (charts.throughput) charts.throughput.destroy();
			charts.throughput = new ChartJS(throughputChartCanvas, { type: 'line', data: { labels: recent.map((_, i) => `${i + 1}`), datasets: [{ label: 'Tokens/sec', data: throughputs, borderColor: colors.emerald.main, backgroundColor: colors.emerald.light, fill: true, tension: 0.4, pointRadius: 3 }] }, options: { ...commonOpts, plugins: { legend: { display: false } } } });
		}
		if (activeTab === 'cost' && costTrendCanvas && completedRuns.length > 0) {
			const recent = completedRuns.slice(-15); const costs = recent.map(r => r.metadata?.aggregate_statistics.cost.total_cost_usd || 0);
			let cum = 0; const cumCosts = costs.map(c => { cum += c; return cum; });
			if (charts.costTrend) charts.costTrend.destroy();
			charts.costTrend = new ChartJS(costTrendCanvas, { type: 'line', data: { labels: recent.map((_, i) => `${i + 1}`), datasets: [{ label: 'Per Run ($)', data: costs, borderColor: colors.emerald.main, backgroundColor: colors.emerald.light, fill: true, tension: 0.4, yAxisID: 'y' }, { label: 'Cumulative ($)', data: cumCosts, borderColor: colors.violet.main, borderDash: [5, 5], fill: false, tension: 0.4, yAxisID: 'y1' }] }, options: { ...commonOpts, scales: { y: { beginAtZero: true, position: 'left' }, y1: { beginAtZero: true, position: 'right', grid: { display: false } }, x: { grid: { display: false } } } } });
		}
	}

	// Track both runs and activeTab - reinitialize charts when either changes
	$effect(() => {
		// Access both to make the effect reactive to them
		const _ = runs.length;
		const tab = activeTab;

		if (runs.length > 0) {
			// Use longer timeout to ensure DOM has updated after tab switch
			setTimeout(() => {
				initCharts();
			}, 150);
		}
	});

	onMount(() => {
		setTimeout(initCharts, 100);
		return () => Object.values(charts).forEach(c => c?.destroy());
	});
</script>

<div class="h-full flex flex-col bg-gray-50 dark:bg-gray-900/50">
	<div class="flex-shrink-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h2 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Analytics Dashboard</h2>
				<p class="text-sm text-gray-500">{runs.length} run{runs.length !== 1 ? 's' : ''} {#if runs.length !== totalRuns}<span class="text-violet-600">(filtered from {totalRuns})</span>{/if}</p>
			</div>
		</div>
		<div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1 w-fit">
			{#each [{ id: 'overview', label: 'Overview', icon: BarChart3 }, { id: 'models', label: 'Models', icon: Cpu }, { id: 'performance', label: 'Performance', icon: Gauge }, { id: 'cost', label: 'Cost', icon: CircleDollarSign }] as tab}
				<button onclick={() => activeTab = tab.id as TabType} class="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all {activeTab === tab.id ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'}">
					<svelte:component this={tab.icon} size={16} />{tab.label}
				</button>
			{/each}
		</div>
	</div>

	<div class="flex-1 overflow-auto p-6">
		{#if runs.length === 0}
			<div class="h-full flex items-center justify-center">
				<div class="text-center">
					<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 dark:from-violet-900/30 dark:to-purple-900/30 flex items-center justify-center">
						<BarChart3 size={40} class="text-violet-500" />
					</div>
					<h3 class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">No Analytics Data</h3>
					<p class="text-gray-500 max-w-sm">Run workflows to see analytics.</p>
				</div>
			</div>
		{:else if activeTab === 'overview'}
			<div class="space-y-6">
				<div class="grid grid-cols-4 gap-4">
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-start justify-between mb-3">
							<div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/30"><Target size={20} class="text-emerald-600" /></div>
							{#if stats().successRate >= 90}<span class="flex items-center gap-1 text-xs text-emerald-600 bg-emerald-100 px-2 py-1 rounded-full"><TrendingUp size={12} />Good</span>{:else if stats().successRate < 70}<span class="flex items-center gap-1 text-xs text-red-600 bg-red-100 px-2 py-1 rounded-full"><TrendingDown size={12} />Low</span>{/if}
						</div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats().successRate.toFixed(1)}%</div>
						<div class="text-sm text-gray-500">Success Rate</div>
						<div class="mt-2 text-xs text-gray-400">{stats().completedRuns} completed / {stats().failedRuns} failed</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-start justify-between mb-3">
							<div class="p-2 rounded-lg bg-violet-100 dark:bg-violet-900/30"><Zap size={20} class="text-violet-600" /></div>
							<span class="text-xs text-gray-500">{formatNumber(stats().avgTokensPerRun)}/run</span>
						</div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{formatNumber(stats().totalTokens)}</div>
						<div class="text-sm text-gray-500">Total Tokens</div>
						<div class="mt-2 text-xs text-gray-400">↑{formatNumber(stats().totalPromptTokens)} ↓{formatNumber(stats().totalCompletionTokens)}</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-start justify-between mb-3">
							<div class="p-2 rounded-lg bg-emerald-100 dark:bg-emerald-900/30"><DollarSign size={20} class="text-emerald-600" /></div>
							<span class="text-xs text-gray-500">{formatCost(stats().avgCostPerRun)}/run</span>
						</div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{formatCost(stats().totalCost)}</div>
						<div class="text-sm text-gray-500">Total Cost</div>
						<div class="mt-2 text-xs text-gray-400">{stats().totalRequests.toLocaleString()} requests</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-start justify-between mb-3">
							<div class="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/30"><Timer size={20} class="text-amber-600" /></div>
							<span class="text-xs text-gray-500">{stats().avgTokensPerSecond.toFixed(0)} tok/s</span>
						</div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{formatDuration(stats().avgDuration)}</div>
						<div class="text-sm text-gray-500">Avg Duration</div>
						<div class="mt-2 text-xs text-gray-400">{stats().totalRecords.toLocaleString()} records</div>
					</div>
				</div>
				{#if insights().length > 0}
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><Lightbulb size={18} class="text-amber-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Insights</h3></div>
						<div class="grid grid-cols-2 gap-3">
							{#each insights() as insight}
								<div class="flex items-start gap-3 p-3 rounded-lg {insight.type === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/20' : insight.type === 'warning' ? 'bg-amber-50 dark:bg-amber-900/20' : insight.type === 'info' ? 'bg-blue-50 dark:bg-blue-900/20' : 'bg-violet-50 dark:bg-violet-900/20'}">
									{#if insight.type === 'success'}<Award size={18} class="text-emerald-600 flex-shrink-0" />{:else if insight.type === 'warning'}<AlertTriangle size={18} class="text-amber-600 flex-shrink-0" />{:else if insight.type === 'info'}<Info size={18} class="text-blue-600 flex-shrink-0" />{:else}<Sparkles size={18} class="text-violet-600 flex-shrink-0" />{/if}
									<div class="flex-1"><div class="flex items-center justify-between"><span class="font-medium text-sm text-gray-900 dark:text-gray-100">{insight.title}</span>{#if insight.metric}<span class="text-xs font-mono px-2 py-0.5 rounded bg-white dark:bg-gray-700 text-gray-600">{insight.metric}</span>{/if}</div><p class="text-xs text-gray-600 mt-1">{insight.description}</p></div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
				<div class="grid grid-cols-2 gap-6">
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><BarChart3 size={18} class="text-violet-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Token Usage</h3></div>
						<div class="h-64"><canvas bind:this={tokenChartCanvas}></canvas></div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><Calendar size={18} class="text-blue-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Runs Over Time</h3></div>
						<div class="h-64"><canvas bind:this={runsTimelineCanvas}></canvas></div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><LineChart size={18} class="text-amber-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Latency Trend</h3></div>
						<div class="h-64"><canvas bind:this={latencyChartCanvas}></canvas></div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><PieChart size={18} class="text-emerald-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Cost by Model</h3></div>
						<div class="h-64"><canvas bind:this={costChartCanvas}></canvas></div>
					</div>
				</div>
			</div>
		{:else if activeTab === 'models'}
			<div class="space-y-6">
				<div class="grid grid-cols-3 gap-4">
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-3"><Award size={18} class="text-emerald-500" /><span class="text-sm text-gray-500">Fastest</span></div>
						<div class="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">{performers().fastest.name}</div>
						<div class="text-sm text-emerald-600">{performers().fastest.value.toFixed(0)}ms avg</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-3"><DollarSign size={18} class="text-emerald-500" /><span class="text-sm text-gray-500">Cheapest</span></div>
						<div class="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">{performers().cheapest.name}</div>
						<div class="text-sm text-emerald-600">${performers().cheapest.value.toFixed(4)}/1M tok</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-3"><Activity size={18} class="text-violet-500" /><span class="text-sm text-gray-500">Most Used</span></div>
						<div class="text-lg font-bold text-gray-900 dark:text-gray-100 truncate">{performers().mostUsed.name}</div>
						<div class="text-sm text-violet-600">{performers().mostUsed.value.toLocaleString()} requests</div>
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
					<div class="flex items-center gap-2 mb-4"><Timer size={18} class="text-amber-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Model Latency Comparison</h3></div>
					<div class="h-72"><canvas bind:this={modelLatencyCanvas}></canvas></div>
				</div>
				{#if Object.keys(stats().modelStats).length > 0}
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><Server size={18} class="text-violet-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Model Details</h3></div>
						<table class="w-full text-sm">
							<thead><tr class="text-left text-xs text-gray-500 uppercase border-b border-gray-200 dark:border-gray-700"><th class="pb-3">Model</th><th class="pb-3 text-right">Requests</th><th class="pb-3 text-right">Tokens</th><th class="pb-3 text-right">Latency</th><th class="pb-3 text-right">Throughput</th><th class="pb-3 text-right">Cost</th></tr></thead>
							<tbody>
								{#each Object.entries(stats().modelStats) as [name, m]}
									{@const lat = m.requests > 0 ? m.latency / m.requests : 0}
									{@const tput = m.latency > 0 ? m.tokens / m.latency : 0}
									<tr class="border-b border-gray-100 dark:border-gray-800">
										<td class="py-3 font-medium text-gray-900 dark:text-gray-100">{name}</td>
										<td class="py-3 text-right text-gray-600">{m.requests.toLocaleString()}</td>
										<td class="py-3 text-right text-gray-600">{formatNumber(m.tokens)}</td>
										<td class="py-3 text-right"><span class="px-2 py-1 rounded text-xs font-medium {lat < 0.5 ? 'bg-emerald-100 text-emerald-700' : lat < 1 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}">{(lat * 1000).toFixed(0)}ms</span></td>
										<td class="py-3 text-right text-emerald-600 font-medium">{tput.toFixed(0)} tok/s</td>
										<td class="py-3 text-right text-gray-600">{formatCost(m.cost)}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		{:else if activeTab === 'performance'}
			<div class="space-y-6">
				<div class="grid grid-cols-4 gap-4">
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><Gauge size={18} class="text-emerald-500" /><span class="text-sm text-gray-500">Throughput</span></div>
						<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats().avgTokensPerSecond.toFixed(0)}</div>
						<div class="text-xs text-gray-500">tokens/sec avg</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><Timer size={18} class="text-amber-500" /><span class="text-sm text-gray-500">Avg Duration</span></div>
						<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatDuration(stats().avgDuration)}</div>
						<div class="text-xs text-gray-500">per run</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><Database size={18} class="text-blue-500" /><span class="text-sm text-gray-500">Records</span></div>
						<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatNumber(stats().totalRecords)}</div>
						<div class="text-xs text-gray-500">processed</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><Activity size={18} class="text-violet-500" /><span class="text-sm text-gray-500">Requests</span></div>
						<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatNumber(stats().totalRequests)}</div>
						<div class="text-xs text-gray-500">API calls</div>
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
					<div class="flex items-center gap-2 mb-4"><TrendingUp size={18} class="text-emerald-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Throughput Over Time</h3></div>
					<div class="h-72"><canvas bind:this={throughputChartCanvas}></canvas></div>
				</div>
				{#if Object.keys(stats().nodeStats).length > 0}
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><Layers size={18} class="text-violet-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Node Performance</h3></div>
						<div class="space-y-3">
							{#each Object.entries(stats().nodeStats).sort((a, b) => b[1].avgLatency - a[1].avgLatency) as [name, node]}
								{@const max = Math.max(...Object.values(stats().nodeStats).map(n => n.avgLatency))}
								{@const pct = max > 0 ? (node.avgLatency / max) * 100 : 0}
								<div class="flex items-center gap-4">
									<div class="w-32 truncate text-sm font-medium text-gray-700 dark:text-gray-300" title={name}>{name}</div>
									<div class="flex-1 h-6 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
										<div class="h-full rounded-full transition-all {pct > 66 ? 'bg-red-500' : pct > 33 ? 'bg-amber-500' : 'bg-emerald-500'}" style="width: {pct}%"></div>
									</div>
									<div class="w-20 text-right text-sm font-mono text-gray-600">{(node.avgLatency * 1000).toFixed(0)}ms</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{:else if activeTab === 'cost'}
			<div class="space-y-6">
				<div class="grid grid-cols-3 gap-4">
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><DollarSign size={18} class="text-emerald-500" /><span class="text-sm text-gray-500">Total Spent</span></div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{formatCost(stats().totalCost)}</div>
						<div class="text-xs text-gray-500">{stats().completedRuns} runs</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><BarChart3 size={18} class="text-violet-500" /><span class="text-sm text-gray-500">Avg per Run</span></div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{formatCost(stats().avgCostPerRun)}</div>
						<div class="text-xs text-gray-500">average cost</div>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700 shadow-sm">
						<div class="flex items-center gap-2 mb-2"><Zap size={18} class="text-amber-500" /><span class="text-sm text-gray-500">Cost per 1M Tokens</span></div>
						<div class="text-3xl font-bold text-gray-900 dark:text-gray-100">{stats().totalTokens > 0 ? formatCost((stats().totalCost / stats().totalTokens) * 1000000) : '-'}</div>
						<div class="text-xs text-gray-500">efficiency</div>
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
					<div class="flex items-center gap-2 mb-4"><LineChart size={18} class="text-emerald-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Cost Trend</h3></div>
					<div class="h-72"><canvas bind:this={costTrendCanvas}></canvas></div>
				</div>
				{#if Object.keys(stats().workflowStats).length > 0}
					<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
						<div class="flex items-center gap-2 mb-4"><CircleDollarSign size={18} class="text-violet-500" /><h3 class="font-semibold text-gray-900 dark:text-gray-100">Cost by Workflow</h3></div>
						<div class="space-y-3">
							{#each Object.entries(stats().workflowStats).sort((a, b) => b[1].cost - a[1].cost) as [name, wf]}
								{@const max = Math.max(...Object.values(stats().workflowStats).map(w => w.cost))}
								{@const pct = max > 0 ? (wf.cost / max) * 100 : 0}
								<div class="flex items-center gap-4">
									<div class="w-40 truncate text-sm font-medium text-gray-700 dark:text-gray-300" title={name}>{name}</div>
									<div class="flex-1 h-6 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
										<div class="h-full bg-violet-500 rounded-full" style="width: {pct}%"></div>
									</div>
									<div class="w-24 text-right text-sm font-medium text-gray-900 dark:text-gray-100">{formatCost(wf.cost)}</div>
									<div class="w-16 text-right text-xs text-gray-500">{wf.runs} runs</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>
