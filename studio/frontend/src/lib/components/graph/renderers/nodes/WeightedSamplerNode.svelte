<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Shuffle, ListTree } from 'lucide-svelte';
	import type { SamplerConfig } from '$lib/stores/workflow.svelte';

	interface Props {
		data: {
			id: string;
			summary: string;
			description?: string;
			sampler_config?: SamplerConfig;
			executionState?: any;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

	// Get attribute names
	let attributeNames = $derived(() => {
		const config = data.sampler_config;
		if (!config?.attributes) return [];
		return Object.keys(config.attributes).slice(0, 4); // Show first 4
	});

	let totalAttributes = $derived(() => {
		const config = data.sampler_config;
		if (!config?.attributes) return 0;
		return Object.keys(config.attributes).length;
	});
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || 'Weighted Sampler'}
	sublabel={totalAttributes() > 0 ? `${totalAttributes()} attribute(s)` : 'Configure attributes'}
	icon={Shuffle}
	color="#8b5cf6"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
>
	<div class="text-xs space-y-2">
		<!-- Attributes Preview -->
		{#if attributeNames().length > 0}
			<div class="space-y-1">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 font-medium">
					<ListTree size={10} />
					<span>Attributes</span>
				</div>
				{#each attributeNames() as attrName}
					{@const attr = data.sampler_config?.attributes[attrName]}
					<div class="flex items-center gap-1 text-gray-600 dark:text-gray-400 pl-3 text-[10px]">
						<span class="truncate max-w-[80px] font-medium" title={attrName}>{attrName}</span>
						<span class="text-gray-400">:</span>
						<span class="truncate text-blue-600 dark:text-blue-400">
							{attr?.values?.length ?? 0} values
						</span>
					</div>
				{/each}
				{#if totalAttributes() > 4}
					<div class="text-[10px] text-gray-400 pl-3">
						+{totalAttributes() - 4} more...
					</div>
				{/if}
			</div>
		{/if}

		<!-- Empty state -->
		{#if attributeNames().length === 0}
			<div class="text-gray-500 dark:text-gray-400 italic">
				Click to configure sampler attributes
			</div>
		{/if}
	</div>
</NodeWrapper>
