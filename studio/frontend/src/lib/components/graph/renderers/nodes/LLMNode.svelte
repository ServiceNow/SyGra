<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Bot, Sparkles, Wrench, Thermometer } from 'lucide-svelte';

	interface Props {
		data: {
			id: string;
			summary: string;
			model?: { name: string; provider: string; parameters?: Record<string, any> };
			tools?: string[];
			executionState?: any;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

	let toolCount = $derived(data.tools?.length ?? 0);
	let temperature = $derived(data.model?.parameters?.temperature);
	let maxTokens = $derived(data.model?.parameters?.max_tokens);
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || data.id}
	sublabel={data.model?.name}
	icon={Bot}
	color="#7661FF"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	nodeType="llm"
	hasRunningNode={data.hasRunningNode}
>
	<div class="space-y-1">
		{#if data.model}
			<div class="flex items-center gap-2 text-xs">
				<Sparkles size={12} class="text-node-llm" />
				<span class="text-text-muted">{data.model.provider}</span>
			</div>
		{/if}
		{#if temperature !== undefined || maxTokens !== undefined}
			<div class="flex items-center gap-3 text-xs text-text-muted">
				{#if temperature !== undefined}
					<span class="flex items-center gap-1">
						<Thermometer size={10} />
						<span>{temperature}</span>
					</span>
				{/if}
				{#if maxTokens !== undefined}
					<span>max: {maxTokens}</span>
				{/if}
			</div>
		{/if}
		{#if toolCount > 0}
			<div class="flex items-center gap-1.5 text-xs text-node-llm">
				<Wrench size={12} />
				<span>{toolCount} tool{toolCount !== 1 ? 's' : ''}</span>
			</div>
		{/if}
	</div>
</NodeWrapper>
