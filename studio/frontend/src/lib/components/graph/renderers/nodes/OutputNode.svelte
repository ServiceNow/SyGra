<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { FileOutput, FileJson, Map, Code, ArrowRight, Settings } from 'lucide-svelte';
	import type { OutputConfig } from '$lib/stores/workflow.svelte';

	interface OutputMap {
		[key: string]: {
			from?: string;
			value?: unknown;
			transform?: string;
		};
	}

	interface Props {
		data: {
			id: string;
			summary: string;
			description?: string;
			output_config?: OutputConfig & {
				generator?: string;
				output_map?: OutputMap;
			};
			executionState?: any;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

	// Get output map keys
	let outputMapKeys = $derived(() => {
		const outputMap = data.output_config?.output_map;
		if (!outputMap) return [];
		return Object.keys(outputMap).slice(0, 4); // Show first 4
	});

	let totalMappings = $derived(() => {
		const outputMap = data.output_config?.output_map;
		if (!outputMap) return 0;
		return Object.keys(outputMap).length;
	});

	// Extract generator class name
	let generatorName = $derived(() => {
		const gen = data.output_config?.generator;
		if (!gen) return null;
		return gen.split('.').pop() || gen;
	});
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || 'Output'}
	sublabel={totalMappings() > 0 ? `${totalMappings()} mapping(s)` : 'Configure output'}
	icon={Settings}
	color="#10b981"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	showSourceHandle={false}
	nodeType="output"
	hasRunningNode={data.hasRunningNode}
>
	<div class="text-xs space-y-2">
		<!-- Generator -->
		{#if generatorName()}
			<div class="space-y-1">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 font-medium">
					<Code size={10} />
					<span>Generator</span>
				</div>
				<div class="flex items-center gap-1.5 text-gray-600 dark:text-gray-400 pl-3">
					<span class="truncate font-mono text-[10px] bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded">
						{generatorName()}
					</span>
				</div>
			</div>
		{/if}

		<!-- Output Map -->
		{#if outputMapKeys().length > 0}
			<div class="space-y-1" class:pt-1={generatorName()}>
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 font-medium">
					<Map size={10} />
					<span>Output Map</span>
				</div>
				{#each outputMapKeys() as key}
					{@const mapping = data.output_config?.output_map?.[key]}
					<div class="flex items-center gap-1 text-gray-600 dark:text-gray-400 pl-3 text-[10px]">
						<span class="truncate max-w-[60px]" title={key}>{key.split('->').pop() || key}</span>
						<ArrowRight size={8} class="text-gray-400 flex-shrink-0" />
						{#if mapping?.from}
							<span class="truncate text-blue-600 dark:text-blue-400">{mapping.from}</span>
						{:else if mapping?.value !== undefined}
							<span class="truncate text-green-600 dark:text-green-400">static</span>
						{/if}
						{#if mapping?.transform}
							<span class="text-[8px] px-0.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400">
								fn
							</span>
						{/if}
					</div>
				{/each}
				{#if totalMappings() > 4}
					<div class="text-[10px] text-gray-400 pl-3">
						+{totalMappings() - 4} more...
					</div>
				{/if}
			</div>
		{/if}

		<!-- Empty state -->
		{#if !generatorName() && outputMapKeys().length === 0}
			<div class="text-gray-500 dark:text-gray-400 italic">
				Click to configure output mapping
			</div>
		{/if}
	</div>
</NodeWrapper>
