<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import type { NodeExecutionState } from '$lib/stores/workflow.svelte';
	import { Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-svelte';

	interface Props {
		id: string;
		label: string;
		sublabel?: string;
		icon: any;
		color: string;
		executionState?: NodeExecutionState | null;
		isCurrentNode?: boolean;
		showSourceHandle?: boolean;
		showTargetHandle?: boolean;
		nodeType?: string; // 'data', 'output', 'llm', 'agent', etc.
		hasRunningNode?: boolean; // true if any node in the graph is currently running
		children?: import('svelte').Snippet;
	}

	let {
		id,
		label,
		sublabel,
		icon: Icon,
		color,
		executionState = null,
		isCurrentNode = false,
		showSourceHandle = true,
		showTargetHandle = true,
		nodeType = '',
		hasRunningNode = false,
		children
	}: Props = $props();

	// Don't show status icons for data, output, start, end nodes
	let showStatusIcon = $derived(() => {
		const skipTypes = ['data', 'output', 'start', 'end'];
		return !skipTypes.includes(nodeType.toLowerCase());
	});

	// Should this node be muted (dimmed)?
	// Mute when another node is running and this node is not the current one
	let isMuted = $derived(() => {
		if (!hasRunningNode) return false;
		// Don't mute if this is the running node
		if (executionState?.status === 'running') return false;
		if (isCurrentNode) return false;
		return true;
	});

	let statusColor = $derived(() => {
		if (!executionState) return '';
		switch (executionState.status) {
			case 'running': return 'border-info shadow-info/25';
			case 'completed': return 'border-status-completed';
			case 'failed': return 'border-error';
			default: return 'border-surface-border';
		}
	});

	let StatusIcon = $derived(() => {
		if (!executionState) return null;
		switch (executionState.status) {
			case 'running': return Loader2;
			case 'completed': return CheckCircle2;
			case 'failed': return XCircle;
			default: return Clock;
		}
	});
</script>

<div
	class="relative rounded-xl shadow-lg border-2 bg-surface transition-all min-w-[180px]"
	class:node-running={executionState?.status === 'running'}
	class:border-surface-border={!executionState}
	class:opacity-60={isMuted()}
	style="border-color: {executionState ? '' : ''}"
	style:border-color={executionState?.status === 'running' ? 'var(--color-info, #52B8FF)' :
	                    executionState?.status === 'completed' ? 'var(--color-status-completed, #63DF4E)' :
	                    executionState?.status === 'failed' ? 'var(--color-error, #ef4444)' : ''}
>
	<!-- Target handle (left) -->
	{#if showTargetHandle}
		<Handle
			type="target"
			position={Position.Left}
			class="!w-3 !h-3 !bg-text-muted !border-2 !border-surface"
		/>
	{/if}

	<!-- Node header -->
	<div
		class="flex items-center gap-3 px-4 py-3 rounded-t-lg"
		style="background-color: {color}20"
	>
		<div
			class="w-8 h-8 rounded-lg flex items-center justify-center text-white"
			style="background-color: {color}"
		>
			<Icon size={18} />
		</div>
		<div class="flex-1 min-w-0">
			<div class="text-sm font-semibold text-text-primary truncate">
				{label}
			</div>
			{#if sublabel}
				<div class="text-xs text-text-muted truncate">
					{sublabel}
				</div>
			{/if}
		</div>

		<!-- Status indicator (hidden for data/output/start/end nodes) -->
		{#if StatusIcon() && showStatusIcon()}
			<div class="flex-shrink-0">
				{#if executionState?.status === 'running'}
					<Loader2 size={18} class="text-info animate-spin" />
				{:else if executionState?.status === 'completed'}
					<CheckCircle2 size={18} class="text-status-completed" />
				{:else if executionState?.status === 'failed'}
					<XCircle size={18} class="text-error" />
				{:else}
					<Clock size={18} class="text-text-muted" />
				{/if}
			</div>
		{/if}
	</div>

	<!-- Node content (optional slot) -->
	{#if children}
		<div class="px-4 py-2">
			{@render children()}
		</div>
	{/if}

	<!-- Duration display -->
	{#if executionState?.duration_ms}
		<div class="px-4 py-2 text-xs text-text-muted">
			Duration: {executionState.duration_ms}ms
		</div>
	{/if}

	<!-- Source handle (right) -->
	{#if showSourceHandle}
		<Handle
			type="source"
			position={Position.Right}
			class="!w-3 !h-3 !bg-text-muted !border-2 !border-surface"
		/>
	{/if}
</div>
