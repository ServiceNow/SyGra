<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { Bot, Wrench } from 'lucide-svelte';
	import type { NodeProps } from '@xyflow/svelte';

	type $$Props = NodeProps;

	export let data: {
		label?: string;
		description?: string;
		model?: { name: string; model_type: string };
		tools?: string[];
		status?: string;
		isRunning?: boolean;
	} = {};
	export let selected: boolean = false;
</script>

<div
	class="px-4 py-3 rounded-xl shadow-lg border-2 transition-all duration-200 min-w-[180px]"
	class:border-pink-500={selected}
	class:border-pink-200={!selected}
	class:dark:border-pink-700={!selected}
	class:bg-gradient-to-br={true}
	class:from-pink-50={true}
	class:to-white={true}
	class:dark:from-pink-950={true}
	class:dark:to-gray-900={true}
	class:ring-2={data.isRunning}
	class:ring-pink-400={data.isRunning}
	class:animate-pulse={data.isRunning}
>
	<!-- Header -->
	<div class="flex items-center gap-2 mb-2">
		<div class="w-8 h-8 rounded-lg bg-pink-500 flex items-center justify-center">
			<Bot size={18} class="text-white" />
		</div>
		<div class="flex-1 min-w-0">
			<div class="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">
				{data.label || 'Agent'}
			</div>
			{#if data.model?.name}
				<div class="text-xs text-pink-600 dark:text-pink-400 truncate">
					{data.model.name}
				</div>
			{/if}
		</div>
	</div>

	<!-- Tools indicator -->
	{#if data.tools && data.tools.length > 0}
		<div class="flex items-center gap-1.5 px-2 py-1 bg-pink-100 dark:bg-pink-900/30 rounded-md">
			<Wrench size={12} class="text-pink-500" />
			<span class="text-xs text-pink-700 dark:text-pink-300">
				{data.tools.length} tool{data.tools.length !== 1 ? 's' : ''}
			</span>
		</div>
	{:else}
		<div class="text-xs text-gray-400 dark:text-gray-500 italic">
			No tools attached
		</div>
	{/if}

	<!-- Status badge -->
	{#if data.status}
		<div class="mt-2 text-xs px-2 py-0.5 rounded-full inline-block"
			class:bg-green-100={data.status === 'completed'}
			class:text-green-700={data.status === 'completed'}
			class:bg-yellow-100={data.status === 'running'}
			class:text-yellow-700={data.status === 'running'}
			class:bg-red-100={data.status === 'failed'}
			class:text-red-700={data.status === 'failed'}
		>
			{data.status}
		</div>
	{/if}
</div>

<!-- Input handle -->
<Handle type="target" position={Position.Top} class="!w-3 !h-3 !bg-pink-400 !border-2 !border-white" />

<!-- Output handle -->
<Handle type="source" position={Position.Bottom} class="!w-3 !h-3 !bg-pink-400 !border-2 !border-white" />

<!-- Tool input handle (left side for connecting tools) -->
<Handle
	type="target"
	position={Position.Left}
	id="tools"
	class="!w-3 !h-3 !bg-teal-400 !border-2 !border-white"
	style="top: 50%"
/>
