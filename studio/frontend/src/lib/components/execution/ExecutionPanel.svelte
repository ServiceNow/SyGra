<script lang="ts">
	import type { Execution } from '$lib/stores/workflow.svelte';
	import { uiStore } from '$lib/stores/workflow.svelte';
	import { Clock, CheckCircle2, XCircle, Loader2, Eye, ChevronUp, GripHorizontal } from 'lucide-svelte';

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	let expanded = $state(false);

	// Auto-scroll state
	let logsContainer = $state<HTMLDivElement | null>(null);
	let shouldAutoScroll = $state(true); // Track if we should auto-scroll
	let previousLogCount = $state(0);

	// Check if user is at bottom of logs (with threshold)
	function isNearBottom(element: HTMLElement, threshold = 50): boolean {
		return element.scrollHeight - element.scrollTop - element.clientHeight < threshold;
	}

	// Handle scroll to detect if user scrolled away from bottom
	function handleLogsScroll(e: Event) {
		const target = e.target as HTMLElement;
		shouldAutoScroll = isNearBottom(target);
	}

	// Auto-scroll to bottom when new logs arrive
	$effect(() => {
		const logCount = execution.logs.length;
		if (logsContainer && logCount > previousLogCount && shouldAutoScroll) {
			// Use requestAnimationFrame for smooth scrolling after DOM update
			requestAnimationFrame(() => {
				if (logsContainer) {
					logsContainer.scrollTop = logsContainer.scrollHeight;
				}
			});
		}
		previousLogCount = logCount;
	});

	// Scroll to bottom when panel is first expanded
	$effect(() => {
		if (expanded && logsContainer) {
			requestAnimationFrame(() => {
				if (logsContainer) {
					logsContainer.scrollTop = logsContainer.scrollHeight;
					shouldAutoScroll = true;
				}
			});
		}
	});

	// Resizable panel state
	let panelHeight = $state(200); // default height when expanded
	let isResizing = $state(false);
	let startY = $state(0);
	let startHeight = $state(0);

	function handleResizeMouseDown(e: MouseEvent) {
		isResizing = true;
		startY = e.clientY;
		startHeight = panelHeight;
		document.addEventListener('mousemove', handleResizeMouseMove);
		document.addEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = 'ns-resize';
		document.body.style.userSelect = 'none';
	}

	function handleResizeMouseMove(e: MouseEvent) {
		if (!isResizing) return;
		const diff = startY - e.clientY; // negative because we're dragging up
		const newHeight = Math.max(100, Math.min(500, startHeight + diff));
		panelHeight = newHeight;
	}

	function handleResizeMouseUp() {
		isResizing = false;
		document.removeEventListener('mousemove', handleResizeMouseMove);
		document.removeEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
	}

	let statusColor = $derived(() => {
		switch (execution.status) {
			case 'running': return 'bg-info';
			case 'completed': return 'bg-success';
			case 'failed': return 'bg-error';
			case 'cancelled': return 'bg-warning';
			default: return 'bg-gray-400';
		}
	});

	let StatusIcon = $derived(() => {
		switch (execution.status) {
			case 'running': return Loader2;
			case 'completed': return CheckCircle2;
			case 'failed': return XCircle;
			default: return Clock;
		}
	});

	let completedNodes = $derived(
		Object.values(execution.node_states).filter(s => s.status === 'completed').length
	);
	let runningNodes = $derived(
		Object.values(execution.node_states).filter(s => s.status === 'running').length
	);
	let totalNodes = $derived(Object.keys(execution.node_states).length);
	let progressPercent = $derived(totalNodes > 0 ? (completedNodes / totalNodes) * 100 : 0);

	// Get current running node name
	let currentNodeName = $derived(() => {
		if (execution.current_node) {
			return execution.current_node;
		}
		// Fallback: find first running node
		const runningEntry = Object.entries(execution.node_states).find(([_, s]) => s.status === 'running');
		return runningEntry ? runningEntry[0] : null;
	});

	// Status message based on state
	let statusMessage = $derived(() => {
		if (execution.status === 'completed') {
			return `Completed ${completedNodes}/${totalNodes} nodes`;
		}
		if (execution.status === 'failed') {
			return `Failed at ${currentNodeName() || 'unknown'}`;
		}
		if (execution.status === 'cancelled') {
			return 'Cancelled';
		}
		if (execution.status === 'running') {
			const nodeName = currentNodeName();
			if (nodeName) {
				return `Running ${nodeName} (${completedNodes + 1}/${totalNodes})`;
			}
			return `Running ${completedNodes}/${totalNodes}`;
		}
		return 'Pending';
	});
</script>

<footer class="border-t border-gray-200 dark:border-gray-800 bg-surface relative">
	<!-- Resize handle (only visible when expanded) -->
	{#if expanded}
		<div
			class="absolute top-0 left-0 right-0 h-1 cursor-ns-resize hover:bg-[#52B8FF]/50 transition-colors z-20 group"
			onmousedown={handleResizeMouseDown}
			role="separator"
			aria-orientation="horizontal"
		>
			<div class="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1 opacity-0 group-hover:opacity-100 transition-opacity">
				<GripHorizontal size={12} class="text-gray-400" />
			</div>
		</div>
	{/if}
	<!-- Progress bar (thin bar at top of footer) -->
	{#if execution.status === 'running' || progressPercent > 0}
		<div class="absolute top-0 left-0 right-0 h-0.5 bg-gray-200 dark:bg-gray-700 overflow-hidden">
			<div
				class="h-full transition-all duration-300 ease-out"
				class:bg-info={execution.status === 'running'}
				class:bg-success={execution.status === 'completed'}
				class:bg-error={execution.status === 'failed'}
				class:bg-warning={execution.status === 'cancelled'}
				class:bg-gray-400={execution.status === 'pending'}
				class:animate-pulse={execution.status === 'running'}
				style="width: {progressPercent}%"
			></div>
		</div>
	{/if}

	<!-- Status bar -->
	<div class="px-6 py-3 flex items-center justify-between">
		<div class="flex items-center gap-4">
			<!-- Status indicator -->
			<div class="flex items-center gap-2">
				<div
					class="w-2.5 h-2.5 rounded-full"
					class:animate-pulse={execution.status === 'running'}
					class:bg-gray-400={execution.status === 'pending'}
					class:bg-info={execution.status === 'running'}
					class:bg-success={execution.status === 'completed'}
					class:bg-error={execution.status === 'failed'}
					class:bg-warning={execution.status === 'cancelled'}
				></div>
				<span class="text-sm font-medium text-gray-700 dark:text-gray-300">
					{statusMessage()}
				</span>
			</div>

			<!-- Duration -->
			{#if execution.duration_ms}
				<div class="text-sm text-gray-500 flex items-center gap-1">
					<Clock size={12} />
					{(execution.duration_ms / 1000).toFixed(2)}s
				</div>
			{/if}
		</div>

		<div class="flex items-center gap-2">
			{#if execution.status === 'completed' || execution.status === 'failed'}
				<button
					onclick={() => uiStore.openResultsModal()}
					class="flex items-center gap-2 px-3 py-1.5 bg-[#7661FF]/15 hover:bg-[#7661FF]/25 dark:bg-[#7661FF]/20 dark:hover:bg-[#7661FF]/30 rounded-lg text-[#7661FF] dark:text-[#BF71F2] text-sm font-medium transition-colors"
				>
					<Eye size={14} />
					View Results
				</button>
			{/if}

			<button
				onclick={() => expanded = !expanded}
				class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
				title={expanded ? 'Collapse logs' : 'Expand logs'}
			>
				<span class="transition-transform inline-block {expanded ? 'rotate-180' : ''}">
					<ChevronUp size={18} />
				</span>
			</button>
		</div>
	</div>

	<!-- Expanded logs -->
	{#if expanded}
		<div class="px-6 pb-4">
			<div
				bind:this={logsContainer}
				onscroll={handleLogsScroll}
				class="bg-gray-900 rounded-lg p-4 overflow-auto scroll-smooth"
				style="height: {panelHeight}px;"
			>
				{#if execution.logs.length > 0}
					{#each execution.logs as log}
						<div class="text-xs text-gray-300 font-mono">{log}</div>
					{/each}
				{:else}
					<div class="text-xs text-gray-500 font-mono">No logs available</div>
				{/if}
			</div>
		</div>
	{/if}
</footer>
