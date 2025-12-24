<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Database, FileJson, Cloud, Server, ArrowDown, ArrowUp, Layers } from 'lucide-svelte';
	import type { DataSourceConfig } from '$lib/stores/workflow.svelte';

	interface DataSource {
		type?: string;
		alias?: string;
		repo_id?: string;
		table?: string;
		file_path?: string;
		file_format?: string;
		split?: string | string[];
		join_type?: string;
		[key: string]: unknown;
	}

	interface DataSink {
		alias?: string;
		type?: string;
		table?: string;
		operation?: string;
		file_path?: string;
		repo_id?: string;
		[key: string]: unknown;
	}

	interface Props {
		data: {
			id: string;
			summary: string;
			description?: string;
			data_config?: DataSourceConfig & {
				source?: DataSource | DataSource[];
				sink?: DataSink | DataSink[];
			};
			executionState?: any;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

	// Get sources as array
	let sources = $derived(() => {
		const source = data.data_config?.source;
		if (!source) return [];
		return Array.isArray(source) ? source : [source];
	});

	// Get sinks as array
	let sinks = $derived(() => {
		const sink = data.data_config?.sink;
		if (!sink) return [];
		return Array.isArray(sink) ? sink : [sink];
	});

	// Determine primary source type for icon
	let primarySourceType = $derived(() => {
		const srcs = sources();
		if (srcs.length === 0) return 'disk';
		return srcs[0].type || 'disk';
	});

	let SourceIcon = $derived(() => {
		switch (primarySourceType()) {
			case 'hf': return Cloud;
			case 'servicenow': return Server;
			case 'disk': return FileJson;
			default: return Database;
		}
	});

	function getSourceLabel(src: DataSource): string {
		if (src.alias) return src.alias;
		switch (src.type) {
			case 'hf': return src.repo_id || 'HuggingFace';
			case 'servicenow': return src.table || 'ServiceNow';
			case 'disk': return src.file_path?.split('/').pop() || 'Local File';
			default: return 'Source';
		}
	}

	function getSinkLabel(sink: DataSink): string {
		if (sink.alias) return sink.alias;
		switch (sink.type) {
			case 'servicenow': return sink.table || 'ServiceNow';
			case 'hf': return sink.repo_id || 'HuggingFace';
			case 'disk': return sink.file_path?.split('/').pop() || 'Local File';
			default: return sink.table || sink.repo_id || sink.file_path?.split('/').pop() || 'Sink';
		}
	}

	function getSinkIcon(sink: DataSink) {
		switch (sink.type) {
			case 'hf': return Cloud;
			case 'servicenow': return Server;
			case 'disk': return FileJson;
			default: return Database;
		}
	}

	function getSourceIcon(src: DataSource) {
		switch (src.type) {
			case 'hf': return Cloud;
			case 'servicenow': return Server;
			case 'disk': return FileJson;
			default: return Database;
		}
	}
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || 'Data'}
	sublabel={sources().length > 0 ? `${sources().length} source(s)` : 'Configure data'}
	icon={sources().length > 1 ? Layers : SourceIcon()}
	color="#0ea5e9"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	showTargetHandle={false}
	nodeType="data"
	hasRunningNode={data.hasRunningNode}
>
	<div class="text-xs space-y-2">
		<!-- Sources -->
		{#if sources().length > 0}
			<div class="space-y-1">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 font-medium">
					<ArrowDown size={10} />
					<span>Sources</span>
				</div>
				{#each sources() as src}
					{@const Icon = getSourceIcon(src)}
					<div class="flex items-center gap-1.5 text-gray-600 dark:text-gray-400 pl-3">
						<Icon size={12} />
						<span class="truncate">{getSourceLabel(src)}</span>
						{#if src.join_type && src.join_type !== 'primary'}
							<span class="text-[10px] px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500">
								{src.join_type}
							</span>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		<!-- Sinks -->
		{#if sinks().length > 0}
			<div class="space-y-1 pt-1 border-t border-gray-100 dark:border-gray-700">
				<div class="flex items-center gap-1 text-gray-500 dark:text-gray-400 font-medium">
					<ArrowUp size={10} />
					<span>Sinks</span>
				</div>
				{#each sinks() as sink}
					{@const SinkIcon = getSinkIcon(sink)}
					<div class="flex items-center gap-1.5 text-gray-600 dark:text-gray-400 pl-3">
						<SinkIcon size={12} />
						<span class="truncate">{getSinkLabel(sink)}</span>
						{#if sink.operation}
							<span class="text-[10px] px-1 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
								{sink.operation}
							</span>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		<!-- Empty state -->
		{#if sources().length === 0 && sinks().length === 0}
			<div class="text-gray-500 dark:text-gray-400 italic">
				Click to configure data source & sink
			</div>
		{/if}
	</div>
</NodeWrapper>
