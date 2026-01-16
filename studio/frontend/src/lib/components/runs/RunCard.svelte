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

	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string; label: string }> = {
		pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', label: 'Pending' },
		running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Running' },
		completed: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30', label: 'Completed' },
		failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Failed' },
		cancelled: { icon: Ban, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Cancelled' }
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
	class="group relative bg-white dark:bg-gray-800 border rounded-xl p-4 cursor-pointer transition-all hover:shadow-md {selected ? 'border-[#7661FF] ring-2 ring-[#7661FF]/20' : 'border-gray-200 dark:border-gray-700 hover:border-[#52B8FF] dark:hover:border-[#7661FF]'}"
	onclick={onSelect}
	role="button"
	tabindex="0"
>
	<!-- Header -->
	<div class="flex items-start justify-between mb-3">
		<div class="flex items-center gap-3">
			<!-- Status icon -->
			<div class="w-10 h-10 rounded-lg flex items-center justify-center {status.bg}">
				<StatusIcon size={20} class="{status.color} {run.status === 'running' ? 'animate-spin' : ''}" />
			</div>
			<div>
				<h3 class="font-medium text-gray-900 dark:text-gray-100 group-hover:text-[#7661FF] dark:group-hover:text-[#52B8FF] transition-colors line-clamp-1">
					{run.workflow_name || 'Unknown Workflow'}
				</h3>
				<p class="text-xs text-gray-500 font-mono">{run.id.slice(0, 12)}...</p>
			</div>
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-1">
			{#if pinned}
				<button
					onclick={(e) => handleAction(e, onPin || (() => {}))}
					class="p-1.5 text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/20 rounded-lg transition-colors"
					title="Unpin"
				>
					<Star size={16} fill="currentColor" />
				</button>
			{/if}
			<div class="relative">
				<button
					onclick={toggleMenu}
					class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
				>
					<MoreVertical size={16} />
				</button>
				{#if showMenu}
					<div class="absolute right-0 top-full mt-1 w-40 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
						{#if !pinned}
							<button
								onclick={(e) => handleAction(e, onPin || (() => {}))}
								class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								<Star size={14} />
								Pin Run
							</button>
						{:else}
							<button
								onclick={(e) => handleAction(e, onPin || (() => {}))}
								class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
							>
								<StarOff size={14} />
								Unpin
							</button>
						{/if}
						<button
							onclick={(e) => handleAction(e, onRerun || (() => {}))}
							class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
						>
							<Play size={14} />
							Re-run
						</button>
						<button
							onclick={(e) => { navigator.clipboard.writeText(run.id); showMenu = false; }}
							class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
						>
							<Copy size={14} />
							Copy ID
						</button>
						<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>
						<button
							onclick={(e) => handleAction(e, onDelete || (() => {}))}
							class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
						>
							<Trash2 size={14} />
							Delete
						</button>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Timeline bar -->
	{#if Object.keys(run.node_states).length > 0}
		<div class="mb-3">
			<RunTimelineBar nodeStates={run.node_states} totalDuration={run.duration_ms} />
		</div>
	{/if}

	<!-- Stats -->
	<div class="grid grid-cols-3 gap-3 text-sm">
		<div class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
			<Timer size={14} class="text-gray-400" />
			<span>{formatDuration(run.duration_ms)}</span>
		</div>
		<div class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
			<Zap size={14} class="text-[#7661FF]" />
			<span>{formatTokens(run.metadata)}</span>
		</div>
		<div class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
			<DollarSign size={14} class="text-emerald-400" />
			<span>{formatCost(run.metadata)}</span>
		</div>
	</div>

	<!-- Footer -->
	<div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
		<span class="text-xs text-gray-500">{formatDate(run.started_at)}</span>
		<ChevronRight size={16} class="text-gray-400 group-hover:text-[#7661FF] transition-colors" />
	</div>
</div>
