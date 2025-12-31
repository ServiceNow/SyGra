<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSinkDetails } from '$lib/stores/workflow.svelte';
	import {
		Plus, Download, ChevronDown, ChevronUp, Server, HardDrive, Cloud,
		FileJson, Trash2, Edit3, Check
	} from 'lucide-svelte';
	import type { Component } from 'svelte';
	import VisualSelectionCard from '../common/VisualSelectionCard.svelte';

	type SinkType = 'disk' | 'hf' | 'servicenow' | 'json' | 'jsonl';

	interface Props {
		sinks: DataSinkDetails[];
		isEditing?: boolean;
	}

	let { sinks = [], isEditing = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		update: { sinks: DataSinkDetails[] };
	}>();

	let isExpanded = $state(true);
	let showEditor = $state(false);
	let editingIndex = $state<number | null>(null);

	// Editor form state
	let editType = $state<SinkType>('disk');
	let editAlias = $state('');
	let editFilePath = $state('');
	let editRepoId = $state('');
	let editSplit = $state('train');
	let editTable = $state('');
	let editOperation = $state<'insert' | 'update'>('insert');

	// Sink type configurations
	const sinkTypeConfig: Record<SinkType, {
		icon: Component<{ size?: number; class?: string }>;
		label: string;
		bgClass: string;
		iconClass: string;
	}> = {
		disk: { icon: HardDrive, label: 'Disk', bgClass: 'bg-blue-100 dark:bg-blue-900/30', iconClass: 'text-blue-600 dark:text-blue-400' },
		hf: { icon: Cloud, label: 'HuggingFace', bgClass: 'bg-amber-100 dark:bg-amber-900/30', iconClass: 'text-amber-600 dark:text-amber-400' },
		servicenow: { icon: Server, label: 'ServiceNow', bgClass: 'bg-emerald-100 dark:bg-emerald-900/30', iconClass: 'text-emerald-600 dark:text-emerald-400' },
		json: { icon: FileJson, label: 'JSON', bgClass: 'bg-violet-100 dark:bg-violet-900/30', iconClass: 'text-violet-600 dark:text-violet-400' },
		jsonl: { icon: FileJson, label: 'JSONL', bgClass: 'bg-pink-100 dark:bg-pink-900/30', iconClass: 'text-pink-600 dark:text-pink-400' }
	};

	let isMultiSink = $derived(sinks.length > 1);

	function resetForm() {
		editType = 'disk';
		editAlias = '';
		editFilePath = '';
		editRepoId = '';
		editSplit = 'train';
		editTable = '';
		editOperation = 'insert';
	}

	function loadSinkToForm(sink: DataSinkDetails) {
		editType = sink.type || 'disk';
		editAlias = sink.alias || '';
		editFilePath = sink.file_path || '';
		editRepoId = sink.repo_id || '';
		editSplit = sink.split || 'train';
		editTable = sink.table || '';
		editOperation = sink.operation || 'insert';
	}

	function handleAddSink() {
		resetForm();
		editingIndex = null;
		showEditor = true;
	}

	function handleEditSink(index: number) {
		loadSinkToForm(sinks[index]);
		editingIndex = index;
		showEditor = true;
	}

	function handleRemoveSink(index: number) {
		dispatch('update', { sinks: sinks.filter((_, i) => i !== index) });
	}

	function handleSaveSink() {
		const newSink: DataSinkDetails = { type: editType };
		if (editAlias) newSink.alias = editAlias;

		if (editType === 'disk' || editType === 'json' || editType === 'jsonl') {
			if (editFilePath) newSink.file_path = editFilePath;
		} else if (editType === 'hf') {
			if (editRepoId) newSink.repo_id = editRepoId;
			if (editSplit) newSink.split = editSplit;
		} else if (editType === 'servicenow') {
			if (editTable) newSink.table = editTable;
			newSink.operation = editOperation;
		}

		let newSinks: DataSinkDetails[];
		if (editingIndex !== null) {
			newSinks = sinks.map((s, i) => i === editingIndex ? newSink : s);
		} else {
			newSinks = [...sinks, newSink];
		}

		dispatch('update', { sinks: newSinks });
		showEditor = false;
		editingIndex = null;
	}

	let isValid = $derived(() => {
		if (editType === 'disk' || editType === 'json' || editType === 'jsonl') return !!editFilePath.trim();
		if (editType === 'hf') return !!editRepoId.trim();
		if (editType === 'servicenow') return !!editTable.trim();
		return true;
	});

	function getSinkDetail(sink: DataSinkDetails): string {
		switch (sink.type) {
			case 'disk': case 'json': case 'jsonl': return sink.file_path?.split('/').pop() || 'No file';
			case 'hf': return sink.repo_id || 'No repo';
			case 'servicenow': return sink.table || 'No table';
			default: return 'Configure';
		}
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
			<div class="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
				<Download size={14} class="text-emerald-600 dark:text-emerald-400" />
			</div>
			<div>
				<div class="text-sm font-medium text-gray-900 dark:text-gray-100">
					Data Sink{isMultiSink ? 's' : ''}
				</div>
				<div class="text-[10px] text-gray-500 dark:text-gray-400">
					{sinks.length === 0 ? 'Optional' : `${sinks.length} configured`}
				</div>
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if isEditing && isExpanded && !showEditor}
				<button
					onclick={(e) => { e.stopPropagation(); handleAddSink(); }}
					class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/30 hover:bg-emerald-200 dark:hover:bg-emerald-900/50 rounded transition-colors"
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
			{#if showEditor}
				<!-- Sink Editor -->
				<div class="space-y-4">
					<!-- Type Selector -->
					<div>
						<div class="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">Type</div>
						<div class="grid grid-cols-3 gap-2">
							{#each Object.entries(sinkTypeConfig) as [type, config]}
								{@const Icon = config.icon}
								<VisualSelectionCard
									selected={editType === type}
									label={config.label}
									icon={Icon}
									iconBgClass={config.bgClass}
									iconClass={config.iconClass}
									size="xs"
									onclick={() => editType = type as SinkType}
								/>
							{/each}
						</div>
					</div>

					<!-- Alias (required for multi-sink) -->
					{#if isMultiSink || sinks.length > 0}
						<div>
							<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Alias {isMultiSink ? '*' : ''}</label>
							<input type="text" bind:value={editAlias} placeholder="output_sink" class="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
						</div>
					{/if}

					<!-- Type-specific fields -->
					{#if editType === 'disk' || editType === 'json' || editType === 'jsonl'}
						<div>
							<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">File Path *</label>
							<input type="text" bind:value={editFilePath} placeholder="output/data.jsonl" class="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
						</div>
					{:else if editType === 'hf'}
						<div class="space-y-3">
							<div>
								<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Repository ID *</label>
								<input type="text" bind:value={editRepoId} placeholder="username/dataset" class="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
							</div>
							<div>
								<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Split</label>
								<input type="text" bind:value={editSplit} placeholder="train" class="w-full px-2 py-1.5 text-xs border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
							</div>
						</div>
					{:else if editType === 'servicenow'}
						<div class="space-y-3">
							<div>
								<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Table Name *</label>
								<input type="text" bind:value={editTable} placeholder="u_output_table" class="w-full px-2 py-1.5 text-xs font-mono border border-gray-200 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100" />
							</div>
							<div>
								<label class="block text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase mb-1">Operation</label>
								<div class="flex gap-2">
									{#each ['insert', 'update'] as op}
										<button type="button" onclick={() => editOperation = op as 'insert' | 'update'} class="flex-1 px-3 py-1.5 text-xs font-medium rounded border transition-all {editOperation === op ? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300' : 'border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400'}">
											{op.charAt(0).toUpperCase() + op.slice(1)}
										</button>
									{/each}
								</div>
							</div>
						</div>
					{/if}

					<!-- Actions -->
					<div class="flex items-center justify-end gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
						<button onclick={() => { showEditor = false; editingIndex = null; }} class="px-3 py-1.5 text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors">
							Cancel
						</button>
						<button onclick={handleSaveSink} disabled={!isValid()} class="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 dark:disabled:bg-gray-700 text-white rounded transition-colors">
							<Check size={14} />
							{editingIndex !== null ? 'Save' : 'Add'}
						</button>
					</div>
				</div>
			{:else if sinks.length === 0}
				<div class="text-center py-6">
					<Download size={24} class="mx-auto mb-2 text-gray-300 dark:text-gray-600" />
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">No sink configured (optional)</p>
					{#if isEditing}
						<button onclick={handleAddSink} class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors">
							<Plus size={14} />
							Add Sink
						</button>
					{/if}
				</div>
			{:else}
				<!-- Sink List -->
				<div class="space-y-2">
					{#each sinks as sink, index}
						{@const config = sinkTypeConfig[sink.type] || sinkTypeConfig.disk}
						{@const Icon = config.icon}
						<div class="group flex items-center gap-2 p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-all">
							<div class="flex-shrink-0 p-1.5 rounded-lg {config.bgClass}">
								<Icon size={14} class={config.iconClass} />
							</div>
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-1.5">
									<span class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
										{sink.alias || config.label}
									</span>
									{#if sink.alias}
										<span class="text-[10px] text-gray-400 dark:text-gray-500">{config.label}</span>
									{/if}
									{#if sink.operation}
										<span class="text-[9px] px-1 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 rounded">{sink.operation}</span>
									{/if}
								</div>
								<div class="text-[10px] text-gray-500 dark:text-gray-400 font-mono truncate">{getSinkDetail(sink)}</div>
							</div>
							{#if isEditing}
								<div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
									<button onclick={() => handleEditSink(index)} class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 transition-colors" title="Edit">
										<Edit3 size={12} />
									</button>
									<button onclick={() => handleRemoveSink(index)} class="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-colors" title="Remove">
										<Trash2 size={12} />
									</button>
								</div>
							{/if}
						</div>
					{/each}
				</div>

				{#if isEditing}
					<button onclick={handleAddSink} class="w-full mt-3 flex items-center justify-center gap-1.5 px-3 py-2 text-xs text-gray-500 dark:text-gray-400 hover:text-emerald-600 dark:hover:text-emerald-400 bg-gray-50 dark:bg-gray-800 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 border border-dashed border-gray-300 dark:border-gray-600 hover:border-emerald-400 dark:hover:border-emerald-500 rounded-lg transition-all">
						<Plus size={14} />
						Add Sink
					</button>
				{/if}
			{/if}
		</div>
	{/if}
</div>
