<script lang="ts">
	import { type Execution } from '$lib/stores/workflow.svelte';
	import { CheckCircle2, XCircle, Clock, Loader2, Zap, DollarSign, Timer, TrendingUp } from 'lucide-svelte';

	interface Props {
		runs: Execution[];
	}

	let { runs }: Props = $props();

	let stats = $derived(() => {
		const completed = runs.filter(r => r.status === 'completed');
		const failed = runs.filter(r => r.status === 'failed');
		const running = runs.filter(r => r.status === 'running');

		let totalTokens = 0;
		let totalCost = 0;
		let totalDuration = 0;

		completed.forEach(r => {
			if (r.metadata?.aggregate_statistics) {
				totalTokens += r.metadata.aggregate_statistics.tokens.total_tokens;
				totalCost += r.metadata.aggregate_statistics.cost.total_cost_usd;
			}
			if (r.duration_ms) totalDuration += r.duration_ms;
		});

		const avgDuration = completed.length > 0 ? totalDuration / completed.length : 0;
		const successRate = runs.length > 0 ? (completed.length / runs.length) * 100 : 0;

		return {
			total: runs.length,
			completed: completed.length,
			failed: failed.length,
			running: running.length,
			totalTokens,
			totalCost,
			avgDuration,
			successRate
		};
	});

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toString();
	}

	function formatDuration(ms: number): string {
		if (ms < 1000) return `${ms.toFixed(0)}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(0)}s`;
		return `${Math.floor(s / 60)}m`;
	}

	function formatCost(usd: number): string {
		if (usd < 0.01) return '<$0.01';
		return `$${usd.toFixed(2)}`;
	}
</script>

<div class="flex items-center gap-6 py-2 px-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
	<!-- Status breakdown -->
	<div class="flex items-center gap-4">
		<div class="flex items-center gap-1.5" title="Completed runs">
			<CheckCircle2 size={14} class="text-emerald-500" />
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{stats().completed}</span>
		</div>
		<div class="flex items-center gap-1.5" title="Failed runs">
			<XCircle size={14} class="text-red-500" />
			<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{stats().failed}</span>
		</div>
		{#if stats().running > 0}
			<div class="flex items-center gap-1.5" title="Running">
				<Loader2 size={14} class="text-blue-500 animate-spin" />
				<span class="text-sm font-medium text-gray-700 dark:text-gray-300">{stats().running}</span>
			</div>
		{/if}
	</div>

	<div class="w-px h-6 bg-gray-300 dark:bg-gray-600"></div>

	<!-- Success rate -->
	<div class="flex items-center gap-2" title="Success rate">
		<TrendingUp size={14} class={stats().successRate >= 80 ? 'text-emerald-500' : stats().successRate >= 50 ? 'text-amber-500' : 'text-red-500'} />
		<span class="text-sm font-medium {stats().successRate >= 80 ? 'text-emerald-600 dark:text-emerald-400' : stats().successRate >= 50 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}">
			{stats().successRate.toFixed(0)}%
		</span>
	</div>

	<div class="w-px h-6 bg-gray-300 dark:bg-gray-600"></div>

	<!-- Tokens -->
	<div class="flex items-center gap-2" title="Total tokens">
		<Zap size={14} class="text-violet-500" />
		<span class="text-sm text-gray-600 dark:text-gray-400">{formatNumber(stats().totalTokens)}</span>
	</div>

	<!-- Cost -->
	<div class="flex items-center gap-2" title="Total cost">
		<DollarSign size={14} class="text-emerald-500" />
		<span class="text-sm text-gray-600 dark:text-gray-400">{formatCost(stats().totalCost)}</span>
	</div>

	<!-- Avg Duration -->
	<div class="flex items-center gap-2" title="Average duration">
		<Timer size={14} class="text-amber-500" />
		<span class="text-sm text-gray-600 dark:text-gray-400">{formatDuration(stats().avgDuration)}</span>
	</div>
</div>
