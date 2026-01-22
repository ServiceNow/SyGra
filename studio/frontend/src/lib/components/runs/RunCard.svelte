<script lang="ts">
	import { type Execution } from '$lib/stores/workflow.svelte';
	import {
		CheckCircle2, XCircle, Clock, Loader2, Ban, Timer, Zap, DollarSign,
		MoreVertical, Play, Copy, Trash2, Star, StarOff, ChevronRight, GitBranch
	} from 'lucide-svelte';
	import RunTimelineBar from './RunTimelineBar.svelte';

	interface Props {
		run: Execution;
		selected?: boolean;
		pinned?: boolean;
		onSelect?: () => void;
		onPin?: () => void;
		onDelete?: () => void;
		onRerun?: () => void;
	}

	let { run, selected = false, pinned = false, onSelect, onPin, onDelete, onRerun }: Props = $props();

	let showMenu = $state(false);

	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string; border: string; label: string }> = {
		pending: { icon: Clock, color: 'text-status-pending', bg: 'bg-status-pending/10', border: 'border-status-pending/20', label: 'Pending' },
		running: { icon: Loader2, color: 'text-status-running', bg: 'bg-status-running/10', border: 'border-status-running/20', label: 'Running' },
		completed: { icon: CheckCircle2, color: 'text-status-completed', bg: 'bg-status-completed/10', border: 'border-status-completed/20', label: 'Completed' },
		failed: { icon: XCircle, color: 'text-status-failed', bg: 'bg-status-failed/10', border: 'border-status-failed/20', label: 'Failed' },
		cancelled: { icon: Ban, color: 'text-status-cancelled', bg: 'bg-status-cancelled/10', border: 'border-status-cancelled/20', label: 'Cancelled' }
	};

	let status = $derived(statusConfig[run.status] || statusConfig.pending);
	let StatusIcon = $derived(status.icon);

	function formatDate(date?: string): string {
		if (!date) return '-';
		const d = new Date(date);
		const now = new Date();
		const diff = now.getTime() - d.getTime();

		if (diff < 60000) return 'Just now';
		if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
		if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
		if (diff < 172800000) return 'Yesterday';
		return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
	}

	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		const m = Math.floor(s / 60);
		return `${m}m ${s % 60}s`;
	}

	function formatTokens(metadata: any): string {
		if (!metadata?.aggregate_statistics?.tokens?.total_tokens) return '-';
		const tokens = metadata.aggregate_statistics.tokens.total_tokens;
		if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
		if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
		return tokens.toString();
	}

	function formatCost(metadata: any): string {
		if (!metadata?.aggregate_statistics?.cost?.total_cost_usd) return '-';
		const cost = metadata.aggregate_statistics.cost.total_cost_usd;
		if (cost < 0.01) return '<$0.01';
		return `$${cost.toFixed(2)}`;
	}

	function toggleMenu(e: MouseEvent) {
		e.stopPropagation();
		showMenu = !showMenu;
	}

	function handleAction(e: MouseEvent, action: () => void) {
		e.stopPropagation();
		showMenu = false;
		action();
	}
</script>

<svelte:window onclick={() => showMenu = false} />

<div
	class="group relative bg-surface-primary border rounded-2xl p-5 cursor-pointer transition-all duration-300 hover:shadow-elevation-2 hover:-translate-y-1 {selected ? 'border-brand-accent ring-2 ring-brand-accent/20 shadow-elevation-2' : 'border-surface-border hover:border-brand-accent/50'}"
	onclick={onSelect}
	role="button"
	tabindex="0"
>
	<!-- Pinned indicator -->
	{#if pinned}
		<div class="absolute -top-2 -right-2 w-6 h-6 bg-amber-500 rounded-full flex items-center justify-center shadow-md">
			<Star size={12} class="text-white fill-current" />
		</div>
	{/if}

	<!-- Header -->
	<div class="flex items-start justify-between mb-4">
		<div class="flex items-center gap-3">
			<!-- Status icon with gradient background -->
			<div class="w-12 h-12 rounded-xl flex items-center justify-center {status.bg} border {status.border}">
				<StatusIcon size={22} class="{status.color} {run.status === 'running' ? 'animate-spin' : ''}" />
			</div>
			<div class="flex-1 min-w-0">
				<h3 class="font-semibold text-text-primary group-hover:text-brand-accent transition-colors line-clamp-1">
					{run.workflow_name || 'Unknown Workflow'}
				</h3>
				<p class="text-xs text-text-muted font-mono">{run.id.slice(0, 12)}...</p>
			</div>
		</div>

		<!-- Actions -->
		<div class="relative">
			<button
				onclick={toggleMenu}
				class="p-2 text-text-muted hover:text-text-primary hover:bg-surface-secondary rounded-lg transition-all duration-200 opacity-0 group-hover:opacity-100"
			>
				<MoreVertical size={16} />
			</button>
			{#if showMenu}
				<div class="absolute right-0 top-full mt-1 w-44 bg-surface-primary rounded-xl shadow-elevation-3 border border-surface-border py-1.5 z-50 animate-scale-in origin-top-right">
					{#if !pinned}
						<button
							onclick={(e) => handleAction(e, onPin || (() => {}))}
							class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
						>
							<Star size={14} />
							Pin Run
						</button>
					{:else}
						<button
							onclick={(e) => handleAction(e, onPin || (() => {}))}
							class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
						>
							<StarOff size={14} />
							Unpin
						</button>
					{/if}
					<button
						onclick={(e) => handleAction(e, onRerun || (() => {}))}
						class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
					>
						<Play size={14} />
						Re-run
					</button>
					<button
						onclick={(e) => { navigator.clipboard.writeText(run.id); showMenu = false; }}
						class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
					>
						<Copy size={14} />
						Copy ID
					</button>
					<div class="h-px bg-surface-border my-1.5 mx-3"></div>
					<button
						onclick={(e) => handleAction(e, onDelete || (() => {}))}
						class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-status-failed hover:bg-status-failed/10 transition-colors"
					>
						<Trash2 size={14} />
						Delete
					</button>
				</div>
			{/if}
		</div>
	</div>

	<!-- Status badge -->
	<div class="mb-4">
		<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold {status.bg} {status.color} border {status.border}">
			<StatusIcon size={12} class={run.status === 'running' ? 'animate-spin' : ''} />
			{status.label}
		</span>
	</div>

	<!-- Timeline bar -->
	{#if Object.keys(run.node_states).length > 0}
		<div class="mb-4">
			<RunTimelineBar nodeStates={run.node_states} totalDuration={run.duration_ms} />
		</div>
	{/if}

	<!-- Stats -->
	<div class="grid grid-cols-3 gap-3">
		<div class="flex flex-col items-center p-2.5 rounded-xl bg-surface-secondary/50">
			<Timer size={14} class="text-text-muted mb-1" />
			<span class="text-sm font-semibold text-text-primary">{formatDuration(run.duration_ms)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Duration</span>
		</div>
		<div class="flex flex-col items-center p-2.5 rounded-xl bg-surface-secondary/50">
			<Zap size={14} class="text-brand-accent mb-1" />
			<span class="text-sm font-semibold text-text-primary">{formatTokens(run.metadata)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Tokens</span>
		</div>
		<div class="flex flex-col items-center p-2.5 rounded-xl bg-surface-secondary/50">
			<DollarSign size={14} class="text-status-completed mb-1" />
			<span class="text-sm font-semibold text-text-primary">{formatCost(run.metadata)}</span>
			<span class="text-[10px] text-text-muted uppercase tracking-wider">Cost</span>
		</div>
	</div>

	<!-- Footer -->
	<div class="flex items-center justify-between mt-4 pt-4 border-t border-surface-border">
		<span class="text-xs text-text-muted font-medium">{formatDate(run.started_at)}</span>
		<div class="flex items-center gap-1 text-xs text-text-muted group-hover:text-brand-accent transition-colors">
			<span>View details</span>
			<ChevronRight size={14} />
		</div>
	</div>
</div>
