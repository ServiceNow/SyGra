<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import StackedBotsIcon from './icons/StackedBotsIcon.svelte';
	import { Bot, Thermometer, Sparkles } from 'lucide-svelte';
	import type { MultiLLMModelConfig } from '$lib/stores/workflow.svelte';

	interface Props {
		data: {
			id: string;
			summary: string;
			models?: Record<string, MultiLLMModelConfig>;
			executionState?: any;
			isCurrentNode?: boolean;
			hasRunningNode?: boolean;
		};
	}

	let { data }: Props = $props();

	let modelEntries = $derived(Object.entries(data.models ?? {}));
	let modelCount = $derived(modelEntries.length);
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || data.id}
	sublabel="{modelCount} model{modelCount !== 1 ? 's' : ''} in parallel"
	icon={StackedBotsIcon}
	color="#06b6d4"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	nodeType="multi_llm"
	hasRunningNode={data.hasRunningNode}
>
	<div class="space-y-1.5">
		{#if modelCount > 0}
			{#each modelEntries.slice(0, 3) as [label, config]}
				<div class="flex items-center justify-between text-xs">
					<div class="flex items-center gap-1.5">
						<Bot size={12} class="text-cyan-500" />
						<span class="font-medium text-gray-700 dark:text-gray-300 truncate max-w-[70px]" title={label}>
							{label}
						</span>
					</div>
					<div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
						<span class="font-mono text-[10px] truncate max-w-[60px]" title={config.name}>
							{config.name}
						</span>
						{#if config.parameters?.temperature !== undefined}
							<span class="flex items-center gap-0.5">
								<Thermometer size={10} />
								<span class="text-[10px]">{config.parameters.temperature}</span>
							</span>
						{/if}
					</div>
				</div>
			{/each}
			{#if modelCount > 3}
				<div class="text-[10px] text-gray-400 dark:text-gray-500 text-center">
					+{modelCount - 3} more model{modelCount - 3 !== 1 ? 's' : ''}
				</div>
			{/if}
		{:else}
			<div class="text-xs text-gray-400 italic text-center py-1">
				No models configured
			</div>
		{/if}
	</div>
</NodeWrapper>
