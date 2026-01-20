<script lang="ts">
	import { CheckCircle2, XCircle, Clock, Loader2, Ban, ChevronRight, Timer, Zap } from 'lucide-svelte';

	interface NodeState {
		status: string;
		duration_ms?: number;
		started_at?: string;
		completed_at?: string;
	}

	interface Props {
		nodeStates: Record<string, NodeState>;
		totalDuration?: number;
	}

	let { nodeStates, totalDuration }: Props = $props();

	const statusConfig: Record<string, { icon: typeof Clock; color: string; bgColor: string; borderColor: string }> = {
		pending: { icon: Clock, color: 'text-gray-400', bgColor: 'bg-gray-100 dark:bg-gray-800', borderColor: 'border-gray-300 dark:border-gray-600' },
		running: { icon: Loader2, color: 'text-blue-500', bgColor: 'bg-blue-50 dark:bg-blue-900/20', borderColor: 'border-blue-300 dark:border-blue-600' },
		completed: { icon: CheckCircle2, color: 'text-emerald-500', bgColor: 'bg-emerald-50 dark:bg-emerald-900/20', borderColor: 'border-emerald-300 dark:border-emerald-600' },
		failed: { icon: XCircle, color: 'text-red-500', bgColor: 'bg-red-50 dark:bg-red-900/20', borderColor: 'border-red-300 dark:border-red-600' },
		cancelled: { icon: Ban, color: 'text-red-500', bgColor: 'bg-red-50 dark:bg-red-900/20', borderColor: 'border-red-300 dark:border-red-600' }
	};

	let nodes = $derived(() => {
		return Object.entries(nodeStates).map(([id, state]) => {
			const config = statusConfig[state.status] || statusConfig.pending;
			return {
				id,
				...state,
				...config,
				Icon: config.icon
			};
		});
	});

	let totalMs = $derived(() => {
		if (totalDuration) return totalDuration;
		return nodes().reduce((sum, n) => sum + (n.duration_ms || 0), 0) || 1;
	});

	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		const m = Math.floor(s / 60);
		return `${m}m ${Math.floor(s % 60)}s`;
	}
</script>

<div class="space-y-3">
	{#each nodes() as node, i}
		{@const widthPct = Math.min(Math.max((node.duration_ms || 0) / totalMs() * 100, 5), 100)}
		<div class="flex items-center gap-3">
			<!-- Node info -->
			<div class="w-32 flex-shrink-0">
				<div class="flex items-center gap-2">
					<node.Icon size={16} class="{node.color} {node.status === 'running' ? 'animate-spin' : ''}" />
					<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate" title={node.id}>
						{node.id}
					</span>
				</div>
			</div>

			<!-- Timeline bar -->
			<div class="flex-1 h-8 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden relative">
				<div
					class="h-full transition-all duration-300 flex items-center px-3 {node.bgColor}"
					style="width: {widthPct}%"
				>
					{#if node.duration_ms}
						<span class="text-xs font-medium {node.color} whitespace-nowrap">
							{formatDuration(node.duration_ms)}
						</span>
					{/if}
				</div>
			</div>

			<!-- Status badge -->
			<div class="w-24 flex-shrink-0 text-right">
				<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium {node.color} {node.bgColor}">
					{node.status}
				</span>
			</div>
		</div>

		{#if i < nodes().length - 1}
			<div class="flex items-center gap-3 pl-4">
				<div class="w-32 flex-shrink-0 flex justify-center">
					<div class="h-4 w-0.5 bg-gray-300 dark:bg-gray-600"></div>
				</div>
			</div>
		{/if}
	{/each}
</div>
