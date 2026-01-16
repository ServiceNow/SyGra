<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Bot, Wrench, Sparkles, Thermometer } from 'lucide-svelte';

	interface Props {
		data: {
			id: string;
			summary: string;
			model?: { name: string; provider?: string; parameters?: Record<string, any> };
			tools?: string[];
			executionState?: any;
			isCurrentNode?: boolean;
			hasRunningNode?: boolean;
		};
	}

	let { data }: Props = $props();

	let toolCount = $derived(data.tools?.length ?? 0);
	let temperature = $derived(data.model?.parameters?.temperature);
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || data.id}
	sublabel={data.model?.name}
	icon={Bot}
	color="#ec4899"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	nodeType="agent"
	hasRunningNode={data.hasRunningNode}
>
	<div class="space-y-1">
		{#if data.model?.provider}
			<div class="flex items-center gap-2 text-xs">
				<Sparkles size={12} class="text-pink-500" />
				<span class="text-gray-600 dark:text-gray-400">{data.model.provider}</span>
			</div>
		{/if}
		{#if temperature !== undefined}
			<div class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
				<Thermometer size={10} />
				<span>{temperature}</span>
			</div>
		{/if}
		{#if toolCount > 0}
			<div class="flex items-center gap-1.5 text-xs text-pink-600 dark:text-pink-400">
				<Wrench size={12} />
				<span>{toolCount} tool{toolCount !== 1 ? 's' : ''}</span>
			</div>
		{:else}
			<div class="text-xs text-gray-400 dark:text-gray-500 italic">
				No tools configured
			</div>
		{/if}
	</div>
</NodeWrapper>
