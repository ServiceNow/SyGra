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
		children
	}: Props = $props();

	let statusColor = $derived(() => {
		if (!executionState) return '';
		switch (executionState.status) {
			case 'running': return 'border-blue-500 shadow-blue-500/25';
			case 'completed': return 'border-green-500';
			case 'failed': return 'border-red-500';
			default: return 'border-gray-300 dark:border-gray-600';
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
	class="relative rounded-xl shadow-lg border-2 bg-white dark:bg-gray-800 transition-all min-w-[180px]"
	class:node-running={executionState?.status === 'running'}
	class:border-gray-200={!executionState}
	class:dark:border-gray-700={!executionState}
	style="border-color: {executionState ? '' : ''}"
	style:border-color={executionState?.status === 'running' ? '#3b82f6' :
	                    executionState?.status === 'completed' ? '#22c55e' :
	                    executionState?.status === 'failed' ? '#ef4444' : ''}
>
	<!-- Target handle (left) -->
	{#if showTargetHandle}
		<Handle
			type="target"
			position={Position.Left}
			class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500 !border-2 !border-white dark:!border-gray-800"
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
			<div class="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">
				{label}
			</div>
			{#if sublabel}
				<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
					{sublabel}
				</div>
			{/if}
		</div>

		<!-- Status indicator -->
		{#if StatusIcon()}
			<div class="flex-shrink-0">
				{#if executionState?.status === 'running'}
					<Loader2 size={18} class="text-blue-500 animate-spin" />
				{:else if executionState?.status === 'completed'}
					<CheckCircle2 size={18} class="text-green-500" />
				{:else if executionState?.status === 'failed'}
					<XCircle size={18} class="text-red-500" />
				{:else}
					<Clock size={18} class="text-gray-400" />
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
		<div class="px-4 py-2 text-xs text-gray-500">
			Duration: {executionState.duration_ms}ms
		</div>
	{/if}

	<!-- Source handle (right) -->
	{#if showSourceHandle}
		<Handle
			type="source"
			position={Position.Right}
			class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500 !border-2 !border-white dark:!border-gray-800"
		/>
	{/if}
</div>
