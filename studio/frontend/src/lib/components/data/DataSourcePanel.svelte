<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { workflowStore, type DataSourceConfig, type DataSourceDetails, type OutputConfig } from '$lib/stores/workflow.svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import {
		Database, FileJson, Cloud, Server, ChevronDown, ChevronUp,
		File, FileText, Table, Filter, Columns, Hash, ArrowRight,
		HardDrive, Globe, Settings, Eye, EyeOff, Copy, Check,
		X, Edit3, Save, Loader2, Code, Plus, Trash2
	} from 'lucide-svelte';

	interface TransformConfig {
		transform: string;
		params?: Record<string, unknown>;
	}

	interface Props {
		dataConfig?: DataSourceConfig;
		outputConfig?: OutputConfig;
		sampleData?: Record<string, unknown>[];
		collapsed?: boolean;
	}

	let { dataConfig, outputConfig, sampleData = [], collapsed = false }: Props = $props();

	const dispatch = createEventDispatcher<{ close: void }>();

	let isExpanded = $state(!collapsed);
	let showSampleData = $state(false);
	let copiedField = $state<string | null>(null);
	let showTransformations = $state(false);

	// Resizable panel state
	let panelWidth = $state(420); // default width for good visibility
	let isResizing = $state(false);
	let startX = $state(0);
	let startWidth = $state(0);

	function handleResizeMouseDown(e: MouseEvent) {
		isResizing = true;
		startX = e.clientX;
		startWidth = panelWidth;
		document.addEventListener('mousemove', handleResizeMouseMove);
		document.addEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = 'ew-resize';
		document.body.style.userSelect = 'none';
	}

	function handleResizeMouseMove(e: MouseEvent) {
		if (!isResizing) return;
		const diff = startX - e.clientX;
		const newWidth = Math.max(320, Math.min(700, startWidth + diff));
		panelWidth = newWidth;
	}

	function handleResizeMouseUp() {
		isResizing = false;
		document.removeEventListener('mousemove', handleResizeMouseMove);
		document.removeEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
	}

	// Edit state
	let isEditing = $state(false);
	let isSaving = $state(false);
	let hasChanges = $state(false);

	// Editable fields for HuggingFace
	let editRepoId = $state('');
	let editConfigName = $state('');
	let editSplit = $state('');
	let editStreaming = $state(false);

	// Editable fields for Local File
	let editFilePath = $state('');
	let editEncoding = $state('utf-8');

	// Editable fields for ServiceNow
	let editTable = $state('');
	let editQuery = $state('');
	let editFields = $state('');
	let editLimit = $state<number | undefined>(undefined);
	let editBatchSize = $state(100);

	// Transformations editing
	let editTransformations = $state<TransformConfig[]>([]);
	let transformationCodes = $state<string[]>([]);
	let expandedTransform = $state<number | null>(null);

	// Initialize edit state when dataConfig changes
	$effect(() => {
		const src = dataConfig?.source;
		if (src) {
			editRepoId = src.repo_id ?? '';
			editConfigName = src.config_name ?? '';
			editSplit = Array.isArray(src.split) ? src.split.join(', ') : (src.split ?? 'train');
			editStreaming = src.streaming ?? false;
			editFilePath = src.file_path ?? '';
			editEncoding = src.encoding ?? 'utf-8';
			editTable = src.table ?? '';
			editQuery = src.query ?? '';
			editFields = src.fields?.join(', ') ?? '';
			editLimit = src.limit;
			editBatchSize = src.batch_size ?? 100;
			// Initialize transformations
			editTransformations = src.transformations ? JSON.parse(JSON.stringify(src.transformations)) : [];
			// Initialize code placeholders for each transformation
			transformationCodes = (src.transformations ?? []).map((t: TransformConfig) =>
				`# Transform: ${t.transform}\n# Params: ${JSON.stringify(t.params || {}, null, 2)}\n\nclass ${t.transform.split('.').pop()}:\n    def __init__(self, **params):\n        self.params = params\n    \n    def transform(self, record):\n        # Transformation logic\n        return record`
			);
		}
	});

	// Get source type icon and color
	function getSourceTypeInfo(type?: string) {
		switch (type) {
			case 'hf':
				return { icon: Cloud, label: 'HuggingFace', color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30' };
			case 'disk':
				return { icon: HardDrive, label: 'Local File', color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30' };
			case 'servicenow':
				return { icon: Server, label: 'ServiceNow', color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30' };
			default:
				return { icon: Database, label: 'Unknown', color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800' };
		}
	}

	// Get output type info
	function getOutputTypeInfo(type?: string) {
		switch (type) {
			case 'json':
			case 'jsonl':
				return { icon: FileJson, label: type.toUpperCase() };
			case 'csv':
			case 'parquet':
				return { icon: FileText, label: type.toUpperCase() };
			case 'hf':
				return { icon: Cloud, label: 'HuggingFace' };
			case 'servicenow':
				return { icon: Server, label: 'ServiceNow' };
			default:
				return { icon: File, label: 'File' };
		}
	}

	// Get file extension from path
	function getFileExtension(path?: string): string {
		if (!path) return '';
		const ext = path.split('.').pop()?.toLowerCase() || '';
		return ext;
	}

	async function copyToClipboard(text: string, field: string) {
		await navigator.clipboard.writeText(text);
		copiedField = field;
		setTimeout(() => copiedField = null, 2000);
	}

	function startEditing() {
		isEditing = true;
	}

	function cancelEditing() {
		// Reset to original values
		const src = dataConfig?.source;
		if (src) {
			editRepoId = src.repo_id ?? '';
			editConfigName = src.config_name ?? '';
			editSplit = Array.isArray(src.split) ? src.split.join(', ') : (src.split ?? 'train');
			editStreaming = src.streaming ?? false;
			editFilePath = src.file_path ?? '';
			editEncoding = src.encoding ?? 'utf-8';
			editTable = src.table ?? '';
			editQuery = src.query ?? '';
			editFields = src.fields?.join(', ') ?? '';
			editLimit = src.limit;
			editBatchSize = src.batch_size ?? 100;
			editTransformations = src.transformations ? JSON.parse(JSON.stringify(src.transformations)) : [];
		}
		hasChanges = false;
		isEditing = false;
		expandedTransform = null;
	}

	async function saveChanges() {
		if (!dataConfig?.source) return;

		isSaving = true;

		const sourceType = dataConfig.source.type;
		const updatedSource: DataSourceDetails = {
			type: sourceType,
		};

		if (sourceType === 'hf') {
			updatedSource.repo_id = editRepoId;
			updatedSource.config_name = editConfigName || undefined;
			updatedSource.split = editSplit.includes(',') ? editSplit.split(',').map(s => s.trim()) : editSplit;
			updatedSource.streaming = editStreaming;
		} else if (sourceType === 'disk') {
			updatedSource.file_path = editFilePath;
			updatedSource.encoding = editEncoding;
		} else if (sourceType === 'servicenow') {
			updatedSource.table = editTable;
			updatedSource.query = editQuery || undefined;
			updatedSource.fields = editFields ? editFields.split(',').map(s => s.trim()) : undefined;
			updatedSource.limit = editLimit;
			updatedSource.batch_size = editBatchSize;
		}

		// Include transformations if any
		if (editTransformations.length > 0) {
			updatedSource.transformations = editTransformations;
		}

		const success = await workflowStore.updateDataConfig({ source: updatedSource });

		if (success) {
			hasChanges = false;
			isEditing = false;
		}

		isSaving = false;
	}

	function addTransformation() {
		editTransformations = [...editTransformations, { transform: '', params: {} }];
		transformationCodes = [...transformationCodes, '# New transformation\n\nclass NewTransform:\n    def __init__(self, **params):\n        self.params = params\n    \n    def transform(self, record):\n        # Transformation logic\n        return record'];
		expandedTransform = editTransformations.length - 1;
		markChanged();
	}

	function removeTransformation(index: number) {
		editTransformations = editTransformations.filter((_, i) => i !== index);
		transformationCodes = transformationCodes.filter((_, i) => i !== index);
		if (expandedTransform === index) {
			expandedTransform = null;
		} else if (expandedTransform !== null && expandedTransform > index) {
			expandedTransform--;
		}
		markChanged();
	}

	function updateTransformPath(index: number, path: string) {
		editTransformations[index].transform = path;
		editTransformations = [...editTransformations];
		markChanged();
	}

	function updateTransformParams(index: number, paramsStr: string) {
		try {
			editTransformations[index].params = JSON.parse(paramsStr);
			editTransformations = [...editTransformations];
			markChanged();
		} catch {
			// Invalid JSON, ignore
		}
	}

	function markChanged() {
		hasChanges = true;
	}

	function handleClose() {
		dispatch('close');
	}

	// Extract source from data_config (handles nested structure)
	let source = $derived(dataConfig?.source);
	let sourceInfo = $derived(getSourceTypeInfo(source?.type));
	let SourceIcon = $derived(sourceInfo.icon);
</script>

{#if dataConfig && source}
	<div
		class="border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-900 overflow-hidden relative"
		style="width: {panelWidth}px"
	>
		<!-- Resize handle -->
		<div
			class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-violet-500/50 transition-colors z-20"
			onmousedown={handleResizeMouseDown}
			role="separator"
			aria-orientation="vertical"
		>
			<div class="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 rounded-full bg-gray-300 dark:bg-gray-600 opacity-0 hover:opacity-100 transition-opacity"></div>
		</div>

		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50">
			<button
				onclick={() => isExpanded = !isExpanded}
				class="flex items-center gap-3 hover:opacity-80 transition-opacity"
			>
				<div class="p-2 rounded-lg {sourceInfo.bg}">
					<SourceIcon size={18} class={sourceInfo.color} />
				</div>
				<div class="text-left">
					<div class="font-medium text-gray-900 dark:text-gray-100">Data Source</div>
					<div class="text-xs text-gray-500 dark:text-gray-400">{sourceInfo.label}</div>
				</div>
				{#if isExpanded}
					<ChevronUp size={16} class="text-gray-400" />
				{:else}
					<ChevronDown size={16} class="text-gray-400" />
				{/if}
			</button>

			<!-- Action buttons -->
			<div class="flex items-center gap-1">
				{#if isEditing}
					<button
						onclick={cancelEditing}
						class="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
						title="Cancel"
					>
						<X size={16} />
					</button>
					<button
						onclick={saveChanges}
						disabled={isSaving}
						class="p-2 text-violet-600 hover:text-violet-700 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/30 rounded-lg transition-colors disabled:opacity-50"
						title="Save changes"
					>
						{#if isSaving}
							<Loader2 size={16} class="animate-spin" />
						{:else}
							<Save size={16} />
						{/if}
					</button>
				{:else}
					<button
						onclick={startEditing}
						class="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
						title="Edit"
					>
						<Edit3 size={16} />
					</button>
				{/if}
				<button
					onclick={handleClose}
					class="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					title="Close"
				>
					<X size={16} />
				</button>
			</div>
		</div>

		{#if isExpanded}
			<div class="p-4 space-y-4">
				<!-- Source Type Specific Details -->
				{#if source.type === 'disk'}
					<!-- Local File Source -->
					<div class="space-y-3">
						{#if isEditing}
							<!-- Edit Mode -->
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">File Path</label>
								<input
									type="text"
									bind:value={editFilePath}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Encoding</label>
								<input
									type="text"
									bind:value={editEncoding}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
							</div>
						{:else}
							<!-- Display Mode -->
							{#if source.file_path}
								<div class="flex items-start gap-3">
									<File size={16} class="text-gray-400 mt-0.5 flex-shrink-0" />
									<div class="flex-1 min-w-0">
										<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">File Path</div>
										<div class="flex items-center gap-2">
											<code class="text-sm font-mono text-gray-800 dark:text-gray-200 break-all bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
												{source.file_path}
											</code>
											<button
												onclick={() => copyToClipboard(source.file_path!, 'path')}
												class="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
												title="Copy path"
											>
												{#if copiedField === 'path'}
													<Check size={14} class="text-green-500" />
												{:else}
													<Copy size={14} class="text-gray-400" />
												{/if}
											</button>
										</div>
									</div>
								</div>
							{/if}

							<div class="flex items-center gap-6 text-sm">
								{#if source.file_format || getFileExtension(source.file_path)}
									<div class="flex items-center gap-2">
										<FileText size={14} class="text-gray-400" />
										<span class="text-gray-600 dark:text-gray-400">Format:</span>
										<span class="font-medium text-gray-800 dark:text-gray-200 uppercase">
											{source.file_format || getFileExtension(source.file_path)}
										</span>
									</div>
								{/if}
								{#if source.encoding && source.encoding !== 'utf-8'}
									<div class="flex items-center gap-2">
										<Settings size={14} class="text-gray-400" />
										<span class="text-gray-600 dark:text-gray-400">Encoding:</span>
										<span class="font-medium text-gray-800 dark:text-gray-200">{source.encoding}</span>
									</div>
								{/if}
							</div>
						{/if}
					</div>

				{:else if source.type === 'hf'}
					<!-- HuggingFace Source -->
					<div class="space-y-3">
						{#if isEditing}
							<!-- Edit Mode -->
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Repository ID *</label>
								<input
									type="text"
									bind:value={editRepoId}
									oninput={markChanged}
									placeholder="username/dataset-name"
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
								/>
							</div>
							<div class="grid grid-cols-2 gap-3">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Config Name</label>
									<input
										type="text"
										bind:value={editConfigName}
										oninput={markChanged}
										placeholder="default"
										class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Split</label>
									<input
										type="text"
										bind:value={editSplit}
										oninput={markChanged}
										placeholder="train"
										class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
							</div>
							<label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
								<input
									type="checkbox"
									bind:checked={editStreaming}
									onchange={markChanged}
									class="rounded border-gray-300 dark:border-gray-600"
								/>
								Streaming mode
							</label>
						{:else}
							<!-- Display Mode -->
							{#if source.repo_id}
								<div class="flex items-start gap-3">
									<Globe size={16} class="text-gray-400 mt-0.5 flex-shrink-0" />
									<div class="flex-1">
										<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Repository ID</div>
										<a
											href="https://huggingface.co/datasets/{source.repo_id}"
											target="_blank"
											rel="noopener noreferrer"
											class="text-sm font-mono text-violet-600 dark:text-violet-400 hover:underline"
										>
											{source.repo_id}
										</a>
									</div>
								</div>
							{/if}

							<div class="flex flex-wrap items-center gap-4 text-sm">
								{#if source.config_name}
									<div class="flex items-center gap-2">
										<Settings size={14} class="text-gray-400" />
										<span class="text-gray-600 dark:text-gray-400">Config:</span>
										<span class="font-medium text-gray-800 dark:text-gray-200">{source.config_name}</span>
									</div>
								{/if}
								{#if source.split}
								<div class="flex items-center gap-2">
									<Columns size={14} class="text-gray-400" />
									<span class="text-gray-600 dark:text-gray-400">Split:</span>
									<span class="font-medium text-gray-800 dark:text-gray-200">
										{Array.isArray(source.split) ? source.split.join(', ') : source.split}
									</span>
								</div>
							{/if}
							{#if source.streaming}
								<span class="px-2 py-0.5 text-xs rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
									Streaming
								</span>
							{/if}
							</div>
						{/if}
					</div>

				{:else if source.type === 'servicenow'}
					<!-- ServiceNow Source -->
					<div class="space-y-3">
						{#if isEditing}
							<!-- Edit Mode -->
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Table Name *</label>
								<input
									type="text"
									bind:value={editTable}
									oninput={markChanged}
									placeholder="incident"
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Query Filter</label>
								<input
									type="text"
									bind:value={editQuery}
									oninput={markChanged}
									placeholder="active=true^priority=1"
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Fields (comma-separated)</label>
								<input
									type="text"
									bind:value={editFields}
									oninput={markChanged}
									placeholder="sys_id, number, short_description"
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 font-mono"
								/>
							</div>
							<div class="grid grid-cols-2 gap-3">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Limit</label>
									<input
										type="number"
										bind:value={editLimit}
										oninput={markChanged}
										placeholder="1000"
										class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Batch Size</label>
									<input
										type="number"
										bind:value={editBatchSize}
										oninput={markChanged}
										class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
							</div>
						{:else}
							<!-- Display Mode -->
							{#if source.table}
							<div class="flex items-start gap-3">
								<Table size={16} class="text-gray-400 mt-0.5 flex-shrink-0" />
								<div class="flex-1">
									<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Table</div>
									<code class="text-sm font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
										{source.table}
									</code>
								</div>
							</div>
						{/if}

						{#if source.query}
							<div class="flex items-start gap-3">
								<Filter size={16} class="text-gray-400 mt-0.5 flex-shrink-0" />
								<div class="flex-1">
									<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Query</div>
									<code class="text-sm font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded block break-all">
										{source.query}
									</code>
								</div>
							</div>
						{/if}

						{#if source.fields && source.fields.length > 0}
							<div class="flex items-start gap-3">
								<Columns size={16} class="text-gray-400 mt-0.5 flex-shrink-0" />
								<div class="flex-1">
									<div class="text-xs text-gray-500 dark:text-gray-400 mb-1">Fields ({source.fields.length})</div>
									<div class="flex flex-wrap gap-1">
										{#each source.fields.slice(0, 10) as field}
											<span class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded">
												{field}
											</span>
										{/each}
										{#if source.fields.length > 10}
											<span class="text-xs px-2 py-0.5 text-gray-500">
												+{source.fields.length - 10} more
											</span>
										{/if}
									</div>
								</div>
							</div>
						{/if}

						<div class="flex flex-wrap items-center gap-4 text-sm">
							{#if source.limit}
								<div class="flex items-center gap-2">
									<Hash size={14} class="text-gray-400" />
									<span class="text-gray-600 dark:text-gray-400">Limit:</span>
									<span class="font-medium text-gray-800 dark:text-gray-200">{source.limit.toLocaleString()}</span>
								</div>
							{/if}
							{#if source.batch_size}
								<div class="flex items-center gap-2">
									<Database size={14} class="text-gray-400" />
									<span class="text-gray-600 dark:text-gray-400">Batch:</span>
									<span class="font-medium text-gray-800 dark:text-gray-200">{source.batch_size}</span>
								</div>
							{/if}
							{#if source.order_by}
								<div class="flex items-center gap-2">
									<ArrowRight size={14} class="text-gray-400" />
									<span class="text-gray-600 dark:text-gray-400">Order:</span>
									<span class="font-medium text-gray-800 dark:text-gray-200">{source.order_by}</span>
								</div>
							{/if}
						</div>
						{/if}
					</div>
				{/if}

				<!-- Transformations Section -->
				{#if source.transformations?.length > 0 || isEditing}
					<div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
						<div class="flex items-center justify-between mb-3">
							<button
								onclick={() => showTransformations = !showTransformations}
								class="flex items-center gap-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-300"
							>
								<Code size={14} />
								Transformations ({isEditing ? editTransformations.length : source.transformations?.length || 0})
								{#if showTransformations}
									<ChevronUp size={14} />
								{:else}
									<ChevronDown size={14} />
								{/if}
							</button>
							{#if isEditing}
								<button
									onclick={addTransformation}
									class="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
								>
									<Plus size={12} />
									Add
								</button>
							{/if}
						</div>

						{#if showTransformations}
							<div class="space-y-3">
								{#if isEditing}
									<!-- Edit Mode -->
									{#each editTransformations as transform, index}
										<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
											<div class="flex items-start justify-between gap-2 mb-2">
												<div class="flex-1">
													<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Module Path</label>
													<input
														type="text"
														value={transform.transform}
														oninput={(e) => updateTransformPath(index, e.currentTarget.value)}
														placeholder="module.path.ClassName"
														class="w-full px-2 py-1.5 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
													/>
												</div>
												<button
													onclick={() => removeTransformation(index)}
													class="p-1 text-red-500 hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded"
													title="Remove transformation"
												>
													<Trash2 size={14} />
												</button>
											</div>

											<div class="mb-2">
												<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Parameters (JSON)</label>
												<input
													type="text"
													value={JSON.stringify(transform.params || {})}
													oninput={(e) => updateTransformParams(index, e.currentTarget.value)}
													placeholder={"{}"}
													class="w-full px-2 py-1.5 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
												/>
											</div>

											<!-- Code Preview Toggle -->
											<button
												onclick={() => expandedTransform = expandedTransform === index ? null : index}
												class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 mb-2"
											>
												<Code size={12} />
												{expandedTransform === index ? 'Hide Code' : 'Show Code'}
												{#if expandedTransform === index}
													<ChevronUp size={12} />
												{:else}
													<ChevronDown size={12} />
												{/if}
											</button>

											{#if expandedTransform === index}
												<MonacoEditor
													bind:value={transformationCodes[index]}
													language="python"
													height="180px"
													theme="vs-dark"
													fontSize={12}
													readonly={!isEditing}
													on:change={markChanged}
												/>
											{/if}
										</div>
									{/each}

									{#if editTransformations.length === 0}
										<div class="text-sm text-gray-500 dark:text-gray-400 italic text-center py-2">
											No transformations configured. Click "Add" to create one.
										</div>
									{/if}
								{:else}
									<!-- Display Mode -->
									{#each source.transformations || [] as transform, index}
										<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3">
											<div class="flex items-center gap-2 mb-1">
												<Code size={14} class="text-gray-400" />
												<code class="text-sm font-mono text-gray-800 dark:text-gray-200">
													{transform.transform}
												</code>
											</div>
											{#if transform.params && Object.keys(transform.params).length > 0}
												<div class="ml-5 text-xs text-gray-500 dark:text-gray-400">
													Params: <code class="bg-gray-100 dark:bg-gray-700 px-1 rounded">{JSON.stringify(transform.params)}</code>
												</div>
											{/if}

											<!-- Code Preview Toggle -->
											<button
												onclick={() => expandedTransform = expandedTransform === index ? null : index}
												class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 mt-2 ml-5"
											>
												<Code size={12} />
												{expandedTransform === index ? 'Hide Code' : 'View Code'}
												{#if expandedTransform === index}
													<ChevronUp size={12} />
												{:else}
													<ChevronDown size={12} />
												{/if}
											</button>

											{#if expandedTransform === index}
												<div class="mt-2">
													<MonacoEditor
														value={transformationCodes[index] || `# Transform: ${transform.transform}\n# Params: ${JSON.stringify(transform.params || {}, null, 2)}`}
														language="python"
														height="180px"
														theme="vs-dark"
														fontSize={12}
														readonly={true}
													/>
												</div>
											{/if}
										</div>
									{/each}
								{/if}
							</div>
						{/if}
					</div>
				{/if}

				<!-- Output Configuration -->
				{#if outputConfig}
					{@const outInfo = getOutputTypeInfo(outputConfig.type)}
					{@const OutIcon = outInfo.icon}
					<div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
						<div class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
							Output
						</div>
						<div class="flex items-center gap-4 text-sm">
							<div class="flex items-center gap-2">
								<OutIcon size={14} class="text-gray-400" />
								<span class="font-medium text-gray-800 dark:text-gray-200">{outInfo.label}</span>
							</div>
							{#if outputConfig.file_path}
								<code class="text-xs font-mono text-gray-600 dark:text-gray-400 truncate max-w-48" title={outputConfig.file_path}>
									{outputConfig.file_path}
								</code>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Sample Data Preview -->
				{#if sampleData.length > 0}
					<div class="border-t border-gray-200 dark:border-gray-700 pt-4 mt-4">
						<button
							onclick={() => showSampleData = !showSampleData}
							class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
						>
							{#if showSampleData}
								<EyeOff size={14} />
								Hide sample data
							{:else}
								<Eye size={14} />
								Show sample data ({Math.min(3, sampleData.length)} records)
							{/if}
						</button>

						{#if showSampleData}
							<div class="mt-3 space-y-2">
								{#each sampleData.slice(0, 3) as record, i}
									<details class="group">
										<summary class="cursor-pointer text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-2">
											<ChevronDown size={12} class="transition-transform group-open:rotate-180" />
											Record {i + 1}
										</summary>
										<pre class="mt-1 p-2 text-xs bg-gray-100 dark:bg-gray-800 rounded overflow-auto max-h-32">{JSON.stringify(record, null, 2)}</pre>
									</details>
								{/each}
							</div>
						{/if}
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}
