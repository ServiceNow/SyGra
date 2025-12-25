<script lang="ts">
	import { CheckCircle2, XCircle, Clock, Loader2, Ban, AlertTriangle } from 'lucide-svelte';

	interface Props {
		nodeStates: Record<string, { status: string; duration_ms?: number }>;
		totalDuration?: number;
	}

	let { nodeStates, totalDuration }: Props = $props();

	// Threshold for switching between dots and progress bar view
	const MAX_DOTS = 12;

	// Tooltip state
	let hoveredNode = $state<{ id: string; status: string; duration: number; x: number; y: number } | null>(null);
	let hoveredSegment = $state<{ status: string; count: number; x: number; y: number } | null>(null);

	// Status configuration with colors
	const statusConfig: Record<string, { color: string; barColor: string; bgColor: string; icon: typeof Clock; label: string }> = {
		completed: { color: 'bg-emerald-500', barColor: '#10b981', bgColor: 'bg-emerald-100 dark:bg-emerald-900/30', icon: CheckCircle2, label: 'Completed' },
		failed: { color: 'bg-red-500', barColor: '#ef4444', bgColor: 'bg-red-100 dark:bg-red-900/30', icon: XCircle, label: 'Failed' },
		running: { color: 'bg-blue-500 animate-pulse', barColor: '#3b82f6', bgColor: 'bg-blue-100 dark:bg-blue-900/30', icon: Loader2, label: 'Running' },
		pending: { color: 'bg-gray-300 dark:bg-gray-500', barColor: '#9ca3af', bgColor: 'bg-gray-100 dark:bg-gray-800', icon: Clock, label: 'Pending' },
		cancelled: { color: 'bg-orange-500', barColor: '#f97316', bgColor: 'bg-orange-100 dark:bg-orange-900/30', icon: Ban, label: 'Cancelled' },
		skipped: { color: 'bg-orange-400', barColor: '#fb923c', bgColor: 'bg-orange-100 dark:bg-orange-900/30', icon: AlertTriangle, label: 'Skipped' }
	};

	// Node IDs to skip
	const skipNodeIds = ['START', 'END', 'data', 'output'];

	// Process nodes and propagate failed state
	let nodes = $derived(() => {
		const entries = Object.entries(nodeStates)
			.filter(([id]) => !skipNodeIds.some(skip => id.toLowerCase().includes(skip.toLowerCase())));

		let failedFound = false;

		return entries.map(([id, state]) => {
			let effectiveStatus = state.status;

			if (failedFound && (state.status === 'pending' || state.status === 'running')) {
				effectiveStatus = 'skipped';
			}

			if (state.status === 'failed' || state.status === 'cancelled') {
				failedFound = true;
			}

			const config = statusConfig[effectiveStatus] || statusConfig.pending;
			return {
				id,
				originalStatus: state.status,
				status: effectiveStatus,
				duration: state.duration_ms || 0,
				color: config.color,
				barColor: config.barColor,
				bgColor: config.bgColor,
				Icon: config.icon,
				label: config.label
			};
		});
	});

	// Check if should use compact (progress bar) view
	let useCompactView = $derived(() => nodes().length > MAX_DOTS);

	// Status counts for compact view
	let statusCounts = $derived(() => {
		const counts: Record<string, number> = {
			completed: 0,
			failed: 0,
			cancelled: 0,
			running: 0,
			pending: 0,
			skipped: 0
		};
		nodes().forEach(n => {
			counts[n.status] = (counts[n.status] || 0) + 1;
		});
		return counts;
	});

	// Segments for progress bar (only non-zero counts, in order)
	let segments = $derived(() => {
		const order = ['completed', 'running', 'failed', 'cancelled', 'skipped', 'pending'];
		const total = nodes().length || 1;
		return order
			.filter(status => statusCounts()[status] > 0)
			.map(status => ({
				status,
				count: statusCounts()[status],
				percentage: (statusCounts()[status] / total) * 100,
				color: statusConfig[status]?.barColor || '#9ca3af',
				label: statusConfig[status]?.label || status
			}));
	});

	// Check if any node failed
	let hasFailed = $derived(() => {
		return Object.values(nodeStates).some(s => s.status === 'failed' || s.status === 'cancelled');
	});

	function formatDuration(ms: number): string {
		if (ms < 1000) return `${ms}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		const m = Math.floor(s / 60);
		return `${m}m ${Math.floor(s % 60)}s`;
	}

	function handleDotMouseEnter(node: typeof nodes extends () => (infer T)[] ? T : never, event: MouseEvent) {
		const rect = (event.target as HTMLElement).getBoundingClientRect();
		hoveredNode = {
			id: node.id,
			status: node.label,
			duration: node.duration,
			x: rect.left + rect.width / 2,
			y: rect.top
		};
	}

	function handleDotMouseLeave() {
		hoveredNode = null;
	}

	function handleSegmentMouseEnter(segment: { status: string; count: number; label: string }, event: MouseEvent) {
		const rect = (event.target as HTMLElement).getBoundingClientRect();
		hoveredSegment = {
			status: segment.label,
			count: segment.count,
			x: rect.left + rect.width / 2,
			y: rect.top
		};
	}

	function handleSegmentMouseLeave() {
		hoveredSegment = null;
	}
</script>

{#if useCompactView()}
	<!-- Compact Progress Bar View for many nodes -->
	<div class="relative flex items-center gap-2 w-full">
		<!-- Segmented progress bar -->
		<div class="flex-1 h-2.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden flex">
			{#each segments() as segment}
				<div
					class="h-full transition-all cursor-pointer hover:opacity-80"
					style="width: {segment.percentage}%; background-color: {segment.color};"
					onmouseenter={(e) => handleSegmentMouseEnter(segment, e)}
					onmouseleave={handleSegmentMouseLeave}
					role="button"
					tabindex="0"
				></div>
			{/each}
		</div>
		<!-- Count summary -->
		<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 flex-shrink-0">
			<span class="text-emerald-600 dark:text-emerald-400 font-medium">{statusCounts().completed}</span>
			<span>/</span>
			<span>{nodes().length}</span>
		</div>
		<!-- Failed indicator -->
		{#if hasFailed()}
			<div class="flex-shrink-0 text-red-500" title="Execution failed">
				<XCircle size={14} />
			</div>
		{/if}
	</div>

	<!-- Segment tooltip -->
	{#if hoveredSegment}
		<div
			class="fixed z-[100] pointer-events-none transform -translate-x-1/2 -translate-y-full"
			style="left: {hoveredSegment.x}px; top: {hoveredSegment.y - 8}px;"
		>
			<div class="px-2.5 py-1.5 text-xs rounded-lg bg-gray-900 dark:bg-gray-800 text-white shadow-lg border border-gray-700 whitespace-nowrap">
				<div class="font-medium">{hoveredSegment.status}</div>
				<div class="text-gray-300 text-[10px] mt-0.5">
					{hoveredSegment.count} node{hoveredSegment.count !== 1 ? 's' : ''}
				</div>
			</div>
		</div>
	{/if}
{:else}
	<!-- Dots View for fewer nodes -->
	<div class="relative flex items-center gap-1 w-full">
		{#each nodes() as node, i}
			<!-- Dot -->
			<div
				class="w-2.5 h-2.5 rounded-full {node.color} flex-shrink-0 cursor-pointer transition-all hover:scale-150 hover:ring-2 hover:ring-offset-1"
				onmouseenter={(e) => handleDotMouseEnter(node, e)}
				onmouseleave={handleDotMouseLeave}
				role="button"
				tabindex="0"
			></div>
			<!-- Connector line -->
			{#if i < nodes().length - 1}
				<div class="flex-1 h-0.5 min-w-0.5 max-w-2 {nodes()[i + 1].status === 'skipped' || node.status === 'failed' || node.status === 'cancelled' || node.status === 'skipped' ? 'bg-orange-300 dark:bg-orange-700' : node.status === 'completed' ? 'bg-emerald-300 dark:bg-emerald-700' : 'bg-gray-200 dark:bg-gray-700'}"></div>
			{/if}
		{/each}
		<!-- Failed indicator -->
		{#if hasFailed()}
			<div class="ml-1 flex-shrink-0 text-red-500" title="Execution failed">
				<XCircle size={14} />
			</div>
		{/if}
	</div>

	<!-- Dot tooltip -->
	{#if hoveredNode}
		<div
			class="fixed z-[100] pointer-events-none transform -translate-x-1/2 -translate-y-full"
			style="left: {hoveredNode.x}px; top: {hoveredNode.y - 8}px;"
		>
			<div class="px-2.5 py-1.5 text-xs rounded-lg bg-gray-900 dark:bg-gray-800 text-white shadow-lg border border-gray-700 whitespace-nowrap">
				<div class="font-medium">{hoveredNode.id}</div>
				<div class="text-gray-300 text-[10px] mt-0.5">
					{hoveredNode.status} • {formatDuration(hoveredNode.duration)}
				</div>
			</div>
		</div>
	{/if}
{/if}
