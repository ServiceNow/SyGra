<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails } from '$lib/stores/workflow.svelte';
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

	// Computed states
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
			// Editing existing source
			newSources = sources.map((s, i) => i === editingIndex ? newSource : s);
		} else {
			// Adding new source
			if (sources.length === 0) {
				// First source - no alias/join needed yet
				newSources = [newSource];
			} else if (sources.length === 1) {
				// Converting from single to multi-source
				// Ensure first source has alias and join_type
				const firstSource = sources[0];
				const updatedFirst: DataSourceDetails = {
					...firstSource,
					alias: firstSource.alias || deriveAlias(firstSource),
					join_type: 'primary'
				};
				// New source should be secondary
				if (!newSource.join_type || newSource.join_type === 'primary') {
					newSource.join_type = 'column';
				}
				newSources = [updatedFirst, newSource];
			} else {
				// Adding to existing multi-source setup
				if (!newSource.join_type) {
					newSource.join_type = hasPrimarySource ? 'column' : 'primary';
				}
				newSources = [...sources, newSource];
			}
		}

		// Ensure only one primary exists
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

	// Derive a default alias from source config
	function deriveAlias(source: DataSourceDetails): string {
		if (source.type === 'hf' && source.repo_id) {
			// Use last part of repo_id (e.g., "glaive-code-assistant" from "glaiveai/glaive-code-assistant-v2")
			const parts = source.repo_id.split('/');
			const name = parts[parts.length - 1].split('-')[0];
			return name.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 20) || 'hf_data';
		}
		if (source.type === 'servicenow' && source.table) {
			return source.table.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 20);
		}
		if (source.type === 'disk' && source.file_path) {
			const fileName = source.file_path.split('/').pop()?.split('.')[0] || 'file';
			return fileName.toLowerCase().replace(/[^a-z0-9]/g, '_').slice(0, 20);
		}
		return 'data';
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

<div class="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 overflow-hidden">
	<!-- Header -->
	<button
		onclick={() => isExpanded = !isExpanded}
		class="w-full flex items-center justify-between px-3 py-2.5 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
	>
		<div class="flex items-center gap-2">
			<div class="p-1.5 rounded-md bg-blue-100 dark:bg-blue-900/30">
				{#if isMultiSource}
					<Layers size={14} class="text-blue-600 dark:text-blue-400" />
				{:else}
					<Database size={14} class="text-blue-600 dark:text-blue-400" />
				{/if}
			</div>
			<div class="text-left">
				<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
					Data Source{isMultiSource ? 's' : ''}
				</div>
				<div class="text-[10px] text-gray-500 dark:text-gray-400">
					{#if sources.length === 0}
						Not configured
					{:else if isMultiSource}
						{sources.length} sources configured
					{:else}
						{sources[0]?.type === 'hf' ? 'HuggingFace' : sources[0]?.type === 'servicenow' ? 'ServiceNow' : 'Local File'}
					{/if}
				</div>
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if isEditing && isExpanded && sources.length > 0}
				<span
					role="button"
					tabindex="0"
					onclick={(e) => { e.stopPropagation(); handleAddSource(); }}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleAddSource(); }}}
					class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-900/50 rounded transition-colors"
				>
					<Plus size={12} />
					Add
				</span>
			{/if}
			<div class="text-gray-400">
				{#if isExpanded}<ChevronUp size={16} />{:else}<ChevronDown size={16} />{/if}
			</div>
		</div>
	</button>

	{#if isExpanded}
		<div class="p-3 border-t border-gray-100 dark:border-gray-800">
			{#if sources.length === 0}
				<!-- Empty State -->
				<div class="text-center py-6">
					<Database size={24} class="mx-auto mb-2 text-gray-300 dark:text-gray-600" />
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">No data source configured</p>
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
				<!-- ID Column (only show when multiple sources exist) -->
				{#if isMultiSource}
					<div class="mb-3 p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg">
						<div class="flex items-center gap-1.5 mb-1.5">
							<Link size={10} class="text-blue-500" />
							<span class="text-[10px] font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">ID Column</span>
						</div>
						{#if isEditing}
							<input
								type="text"
								bind:value={editIdColumn}
								onchange={handleIdColumnChange}
								placeholder="e.g., sys_id"
								class="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-1 focus:ring-blue-400 focus:border-blue-400"
							/>
							<p class="text-[10px] text-gray-400 dark:text-gray-500 mt-1">Used to track records across joined sources</p>
						{:else if idColumn}
							<code class="text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 px-2 py-1 rounded font-mono text-gray-700 dark:text-gray-300">{idColumn}</code>
						{:else}
							<span class="text-[10px] text-gray-400 italic">Not set</span>
						{/if}
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

				<!-- Add more button (for multi-source or first additional source) -->
				{#if isEditing}
					<button
						onclick={handleAddSource}
						class="w-full mt-3 flex items-center justify-center gap-1.5 px-3 py-2 text-xs text-gray-500 dark:text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 bg-gray-50 dark:bg-gray-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-dashed border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 rounded-lg transition-all"
					>
						<Plus size={14} />
						{isMultiSource ? 'Add Another Source' : 'Add Second Source (Enable Multi-Source)'}
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
