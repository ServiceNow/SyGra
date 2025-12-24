<script lang="ts">
	import { CheckCircle2, XCircle, Clock, Loader2, Ban } from 'lucide-svelte';

	interface Props {
		nodeStates: Record<string, { status: string; duration_ms?: number }>;
		totalDuration?: number;
	}

	let { nodeStates, totalDuration }: Props = $props();

	const statusColors: Record<string, string> = {
		completed: 'bg-emerald-500',
		failed: 'bg-red-500',
		running: 'bg-blue-500',
		pending: 'bg-gray-300 dark:bg-gray-600',
		cancelled: 'bg-red-500'
	};

	let nodes = $derived(() => {
		return Object.entries(nodeStates).map(([id, state]) => ({
			id,
			status: state.status,
			duration: state.duration_ms || 0,
			color: statusColors[state.status] || statusColors.pending
		}));
	});

	let totalMs = $derived(() => {
		if (totalDuration) return totalDuration;
		return nodes().reduce((sum, n) => sum + n.duration, 0) || 1;
	});
</script>

<div class="flex items-center gap-0.5 h-2 w-full rounded overflow-hidden bg-gray-100 dark:bg-gray-800">
	{#each nodes() as node}
		{@const widthPct = Math.max((node.duration / totalMs()) * 100, 5)}
		<div
			class="h-full transition-all {node.color}"
			style="width: {widthPct}%"
			title="{node.id}: {node.status} ({node.duration}ms)"
		></div>
	{/each}
</div>
