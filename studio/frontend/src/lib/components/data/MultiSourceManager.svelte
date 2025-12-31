<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails } from '$lib/stores/workflow.svelte';
	import { JOIN_TYPE_METADATA } from '$lib/stores/workflow.svelte';
	import SourceCard from './SourceCard.svelte';
	import SourceEditor from './SourceEditor.svelte';
	import { Plus, Database, ChevronDown, ChevronUp, Link, Layers } from 'lucide-svelte';

	interface PreviewData {
		records: Record<string, unknown>[];
		total?: number | string;
		message?: string;
		source_type?: string;
	}

	interface Props {
		sources: DataSourceDetails[];
		idColumn?: string;
		isEditing?: boolean;
		sourcePreviewData?: Map<number, PreviewData | null>;
		sourcePreviewLoading?: Map<number, boolean>;
	}

	let {
		sources = [],
		idColumn,
		isEditing = false,
		sourcePreviewData = new Map(),
		sourcePreviewLoading = new Map()
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		update: { sources: DataSourceDetails[]; idColumn?: string };
		previewFetch: { index: number };
		previewRefresh: { index: number };
	}>();

	// Local state
	let isExpanded = $state(true);
	let showEditor = $state(false);
	let editingIndex = $state<number | null>(null);
	let editIdColumn = $state(idColumn || '');

	// Sync idColumn
	$effect(() => {
		editIdColumn = idColumn || '';
	});

	// Find primary source
	let primaryIndex = $derived(sources.findIndex(s => s.join_type === 'primary'));
	let hasPrimarySource = $derived(primaryIndex >= 0);
	let isMultiSource = $derived(sources.length > 1);

	// Editing source
	let editingSource = $derived(editingIndex !== null ? sources[editingIndex] : undefined);
	let editingIsPrimary = $derived(editingIndex !== null && editingIndex === primaryIndex);

	function handleAddSource() {
		editingIndex = null;
		showEditor = true;
	}

	function handleEditSource(index: number) {
		editingIndex = index;
		showEditor = true;
	}

	function handleRemoveSource(index: number) {
		const newSources = sources.filter((_, i) => i !== index);
		dispatch('update', { sources: newSources, idColumn: editIdColumn || undefined });
	}

	function handleMakePrimary(index: number) {
		const newSources = sources.map((s, i) => {
			if (i === primaryIndex) {
				return { ...s, join_type: 'column' as const, primary_key: '', join_key: '' };
			}
			if (i === index) {
				return { ...s, join_type: 'primary' as const, primary_key: undefined, join_key: undefined };
			}
			return s;
		});
		dispatch('update', { sources: newSources, idColumn: editIdColumn || undefined });
	}

	function handleSaveSource(e: CustomEvent<{ source: DataSourceDetails }>) {
		const newSource = e.detail.source;
		let newSources: DataSourceDetails[];

		if (editingIndex !== null) {
			newSources = sources.map((s, i) => i === editingIndex ? newSource : s);
		} else {
			newSources = [...sources, newSource];
		}

		// If new source is primary, ensure only one primary exists
		if (newSource.join_type === 'primary') {
			const newIndex = editingIndex !== null ? editingIndex : newSources.length - 1;
			newSources = newSources.map((s, i) => {
				if (i !== newIndex && s.join_type === 'primary') {
					return { ...s, join_type: 'column', primary_key: '', join_key: '' };
				}
				return s;
			});
		}

		dispatch('update', { sources: newSources, idColumn: editIdColumn || undefined });
		showEditor = false;
		editingIndex = null;
	}

	function handleIdColumnChange() {
		dispatch('update', { sources, idColumn: editIdColumn || undefined });
	}

	function handlePreviewFetch(e: CustomEvent<{ index: number }>) {
		dispatch('previewFetch', e.detail);
	}

	function handlePreviewRefresh(e: CustomEvent<{ index: number }>) {
		dispatch('previewRefresh', e.detail);
	}
</script>

<div class="border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-900 overflow-hidden">
	<!-- Header -->
	<div
		role="button"
		tabindex="0"
		onclick={() => isExpanded = !isExpanded}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') isExpanded = !isExpanded; }}
		class="flex items-center justify-between px-3 py-2.5 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors cursor-pointer"
	>
		<div class="flex items-center gap-2">
			<div class="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
				{#if isMultiSource}
					<Layers size={14} class="text-blue-600 dark:text-blue-400" />
				{:else}
					<Database size={14} class="text-blue-600 dark:text-blue-400" />
				{/if}
			</div>
			<div>
				<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
					Data Source{isMultiSource ? 's' : ''}
				</div>
				<div class="text-[10px] text-gray-500 dark:text-gray-400">
					{#if sources.length === 0}
						Not configured
					{:else}
						{sources.length} source{sources.length !== 1 ? 's' : ''}
					{/if}
				</div>
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if isEditing && isExpanded}
				<button
					onclick={(e) => { e.stopPropagation(); handleAddSource(); }}
					class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50 rounded transition-colors"
				>
					<Plus size={12} />
					Add
				</button>
			{/if}
			<div class="text-gray-400">
				{#if isExpanded}<ChevronUp size={16} />{:else}<ChevronDown size={16} />{/if}
			</div>
		</div>
	</div>

	{#if isExpanded}
		<div class="p-3 border-t border-gray-100 dark:border-gray-800">
			{#if sources.length === 0}
				<!-- Empty State -->
				<div class="text-center py-6">
					<Database size={24} class="mx-auto mb-2 text-gray-300 dark:text-gray-600" />
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">No data sources configured</p>
					{#if isEditing}
						<button
							onclick={handleAddSource}
							class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
						>
							<Plus size={14} />
							Add Data Source
						</button>
					{/if}
				</div>
			{:else}
				<!-- ID Column (only for multiple sources) -->
				{#if isMultiSource && isEditing}
					<div class="mb-3 p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
						<div class="flex items-center gap-1.5 mb-1.5">
							<Link size={10} class="text-violet-500" />
							<label class="text-[10px] font-medium text-gray-600 dark:text-gray-400">ID Column</label>
						</div>
						<input
							type="text"
							bind:value={editIdColumn}
							onchange={handleIdColumnChange}
							placeholder="sys_id"
							class="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-violet-500"
						/>
					</div>
				{:else if isMultiSource && idColumn}
					<div class="mb-3 flex items-center gap-1.5 text-[10px] text-gray-500 dark:text-gray-400 px-1">
						<Link size={10} class="text-violet-500" />
						<span>ID:</span>
						<code class="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono">{idColumn}</code>
					</div>
				{/if}

				<!-- Source List -->
				<div class="space-y-2">
					{#each sources as source, index}
						{@const isPrimary = source.join_type === 'primary'}
						<SourceCard
							{source}
							{index}
							{isEditing}
							{isPrimary}
							showJoinInfo={isMultiSource}
							showAlias={isMultiSource}
							previewData={sourcePreviewData.get(index)}
							previewLoading={sourcePreviewLoading.get(index) || false}
							on:edit={() => handleEditSource(index)}
							on:remove={() => handleRemoveSource(index)}
							on:makePrimary={() => handleMakePrimary(index)}
							on:previewFetch={handlePreviewFetch}
							on:previewRefresh={handlePreviewRefresh}
						/>
					{/each}
				</div>

				<!-- Add more button -->
				{#if isEditing}
					<button
						onclick={handleAddSource}
						class="w-full mt-3 flex items-center justify-center gap-1.5 px-3 py-2 text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 bg-gray-50 dark:bg-gray-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-dashed border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 rounded-lg transition-all"
					>
						<Plus size={14} />
						Add Source
					</button>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<!-- Source Editor Modal -->
<SourceEditor
	source={editingSource}
	isPrimary={editingIsPrimary}
	{hasPrimarySource}
	requireAlias={isMultiSource || sources.length > 0}
	open={showEditor}
	on:save={handleSaveSource}
	on:close={() => { showEditor = false; editingIndex = null; }}
/>
