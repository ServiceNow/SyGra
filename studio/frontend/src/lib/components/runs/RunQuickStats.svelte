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

<div class="flex items-center gap-4 py-3 px-5 bg-surface-secondary/50 rounded-xl border border-surface-border">
	<!-- Status breakdown -->
	<div class="flex items-center gap-5">
		<div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-status-completed/10" title="Completed runs">
			<CheckCircle2 size={14} class="text-status-completed" />
			<span class="text-sm font-semibold text-status-completed">{stats().completed}</span>
		</div>
		<div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-status-failed/10" title="Failed runs">
			<XCircle size={14} class="text-status-failed" />
			<span class="text-sm font-semibold text-status-failed">{stats().failed}</span>
		</div>
		{#if stats().running > 0}
			<div class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-status-running/10" title="Running">
				<Loader2 size={14} class="text-status-running animate-spin" />
				<span class="text-sm font-semibold text-status-running">{stats().running}</span>
			</div>
		{/if}
	</div>

	<div class="w-px h-8 bg-surface-border"></div>

	<!-- Success rate -->
	<div class="flex items-center gap-2.5" title="Success rate">
		<div class="w-8 h-8 rounded-lg flex items-center justify-center {stats().successRate >= 80 ? 'bg-status-completed/10' : stats().successRate >= 50 ? 'bg-amber-500/10' : 'bg-status-failed/10'}">
			<TrendingUp size={16} class={stats().successRate >= 80 ? 'text-status-completed' : stats().successRate >= 50 ? 'text-amber-500' : 'text-status-failed'} />
		</div>
		<div class="flex flex-col">
			<span class="text-sm font-bold {stats().successRate >= 80 ? 'text-status-completed' : stats().successRate >= 50 ? 'text-amber-500' : 'text-status-failed'}">
				{stats().successRate.toFixed(0)}%
			</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Success</span>
		</div>
	</div>

	<div class="w-px h-8 bg-surface-border"></div>

	<!-- Tokens -->
	<div class="flex items-center gap-2.5" title="Total tokens">
		<div class="w-8 h-8 rounded-lg bg-brand-accent/10 flex items-center justify-center">
			<Zap size={16} class="text-brand-accent" />
		</div>
		<div class="flex flex-col">
			<span class="text-sm font-bold text-text-primary">{formatNumber(stats().totalTokens)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Tokens</span>
		</div>
	</div>

	<!-- Cost -->
	<div class="flex items-center gap-2.5" title="Total cost">
		<div class="w-8 h-8 rounded-lg bg-status-completed/10 flex items-center justify-center">
			<DollarSign size={16} class="text-status-completed" />
		</div>
		<div class="flex flex-col">
			<span class="text-sm font-bold text-text-primary">{formatCost(stats().totalCost)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Cost</span>
		</div>
	</div>

	<!-- Avg Duration -->
	<div class="flex items-center gap-2.5" title="Average duration">
		<div class="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
			<Timer size={16} class="text-amber-500" />
		</div>
		<div class="flex flex-col">
			<span class="text-sm font-bold text-text-primary">{formatDuration(stats().avgDuration)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Avg Time</span>
		</div>
	</div>
</div>
