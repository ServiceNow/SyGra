<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails, DataSinkDetails, TransformConfig } from '$lib/stores/workflow.svelte';
	import MultiSourceManager from './MultiSourceManager.svelte';
	import TransformPipeline from './TransformPipeline.svelte';
	import SinkManager from './SinkManager.svelte';

	interface SourcePreviewData {
		records: Record<string, unknown>[];
		total?: number | string;
		message?: string;
		source_type?: string;
	}

	interface Props {
		sources: DataSourceDetails[];
		sinks: DataSinkDetails[];
		transforms: TransformConfig[];
		idColumn?: string;
		isEditing?: boolean;
		sourcePreviewData?: Map<number, SourcePreviewData | null>;
		sourcePreviewLoading?: Map<number, boolean>;
	}

	let {
		sources = [],
		sinks = [],
		transforms = [],
		idColumn,
		isEditing = false,
		sourcePreviewData = new Map(),
		sourcePreviewLoading = new Map()
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		sourcesUpdate: { sources: DataSourceDetails[]; idColumn?: string };
		sinksUpdate: { sinks: DataSinkDetails[] };
		transformsUpdate: { transforms: TransformConfig[] };
		sourcePreviewFetch: { index: number };
		sourcePreviewRefresh: { index: number };
	}>();

	let hasSource = $derived(sources.length > 0);

	function handleSourcesUpdate(e: CustomEvent<{ sources: DataSourceDetails[]; idColumn?: string }>) {
		dispatch('sourcesUpdate', e.detail);
	}

	function handleSinksUpdate(e: CustomEvent<{ sinks: DataSinkDetails[] }>) {
		dispatch('sinksUpdate', e.detail);
	}

	function handleTransformsUpdate(e: CustomEvent<{ transforms: TransformConfig[] }>) {
		dispatch('transformsUpdate', e.detail);
	}

	function handleSourcePreviewFetch(e: CustomEvent<{ index: number }>) {
		dispatch('sourcePreviewFetch', e.detail);
	}

	function handleSourcePreviewRefresh(e: CustomEvent<{ index: number }>) {
		dispatch('sourcePreviewRefresh', e.detail);
	}
</script>

<div class="space-y-3">
	<!-- Data Sources (with per-source preview) -->
	<MultiSourceManager
		{sources}
		{idColumn}
		{isEditing}
		{sourcePreviewData}
		{sourcePreviewLoading}
		on:update={handleSourcesUpdate}
		on:previewFetch={handleSourcePreviewFetch}
		on:previewRefresh={handleSourcePreviewRefresh}
	/>

	<!-- Transform Pipeline -->
	{#if hasSource || isEditing}
		<TransformPipeline
			{transforms}
			{isEditing}
			on:update={handleTransformsUpdate}
		/>
	{/if}

	<!-- Data Sink -->
	{#if hasSource || isEditing}
		<SinkManager
			{sinks}
			{isEditing}
			on:update={handleSinksUpdate}
		/>
	{/if}
</div>
