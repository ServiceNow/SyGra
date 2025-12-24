<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, Play, ChevronDown, Settings, Database, Hash, Layers, Clock, Tag, FolderOutput, Bug, RotateCcw, Gauge, FileJson, HardDrive, Cloud, Globe, FileText, Eye, EyeOff, Loader2, AlertCircle } from 'lucide-svelte';
	import DataTableViewer from '$lib/components/common/DataTableViewer.svelte';

	interface DataSource {
		type?: string;
		file_path?: string;
		file_format?: string;
		repo_id?: string;
		config_name?: string;
		split?: string;
		dataset_name?: string;
		table_name?: string;
		instance?: string;
		transformations?: unknown[];
		[key: string]: unknown;
	}

	interface DataConfig {
		source?: DataSource | DataSource[];
		sink?: {
			type?: string;
			file_path?: string;
			[key: string]: unknown;
		};
		[key: string]: unknown;
	}

	interface Props {
		workflowName: string;
		workflowId?: string;
		dataConfig?: DataConfig | null;
		nodeCount?: number;
	}

	let { workflowName, workflowId = '', dataConfig = null, nodeCount = 0 }: Props = $props();

	// Execution options interface matching main.py and ExecutionRequest model
	interface ExecutionOptions {
		inputData: Record<string, unknown>;
		startIndex: number;
		numRecords: number;
		batchSize: number;
		checkpointInterval: number;
		runName: string;
		outputWithTs: boolean;
		outputDir: string;
		debug: boolean;
		resume: boolean | null;
		quality: boolean;
		disableMetadata: boolean;
		runArgs: Record<string, unknown>;
	}

	const dispatch = createEventDispatcher<{
		run: ExecutionOptions;
		close: void;
	}>();

	// Generate default run name with timestamp
	function generateRunName(): string {
		const now = new Date();
		const timestamp = now.toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
		return `run_${timestamp}`;
	}

	// Core execution parameters (defaults from main.py)
	let startIndex = $state(0);
	let numRecords = $state(10);
	let batchSize = $state(25);
	let checkpointInterval = $state(100);

	// Output options
	let runName = $state('');
	let outputWithTs = $state(true);
	let outputDir = $state('');

	// Execution options
	let debug = $state(false);
	let resume = $state<boolean | null>(null);
	let quality = $state(false);
	let disableMetadata = $state(false);

	// Custom arguments
	let runArgsText = $state('{}');
	let runArgsError = $state<string | null>(null);

	// UI state
	let showAdvanced = $state(false);
	let showDataPreview = $state(false);
	let previewLoading = $state(false);
	let previewData = $state<{ records: unknown[]; total: number | string | null; message: string | null } | null>(null);
	let expandedRows = $state<Set<number>>(new Set());

	function toggleRowExpand(index: number) {
		if (expandedRows.has(index)) {
			expandedRows.delete(index);
			expandedRows = new Set(expandedRows);
		} else {
			expandedRows.add(index);
			expandedRows = new Set(expandedRows);
		}
	}

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return 'null';
		if (typeof value === 'object') return JSON.stringify(value, null, 2);
		return String(value);
	}

	// Derived: parse data source info
	let dataSource = $derived(() => {
		if (!dataConfig?.source) return null;
		// Handle array or single source
		const src = Array.isArray(dataConfig.source) ? dataConfig.source[0] : dataConfig.source;
		return src || null;
	});

	// Derived: data source type
	let sourceType = $derived(() => {
		const src = dataSource();
		return (src?.type || '').toLowerCase();
	});

	// Derived: is HuggingFace source
	let isHuggingFace = $derived(() => {
		const type = sourceType();
		return type === 'hf' || type === 'huggingface';
	});

	// Derived: is ServiceNow source
	let isServiceNow = $derived(() => {
		const type = sourceType();
		return type === 'servicenow' || type === 'snow';
	});

	// Derived: is local file source
	let isLocalFile = $derived(() => {
		const type = sourceType();
		return type === 'disk' || type === 'local_file' || type === 'local' || type === 'json' || type === 'jsonl' || type === 'csv';
	});

	// Derived: data source type label
	let sourceTypeLabel = $derived(() => {
		if (isHuggingFace()) return 'Hugging Face Dataset';
		if (isServiceNow()) return 'ServiceNow';
		if (isLocalFile()) return 'Local File';
		const type = sourceType();
		if (type) return type.charAt(0).toUpperCase() + type.slice(1);
		return 'Data Source';
	});

	// Derived: format file path for display
	let displayPath = $derived(() => {
		const src = dataSource();
		if (!src) return null;

		// Try different path fields
		const path = src.file_path || (src as any).path;
		if (!path) return null;

		// Shorten long paths
		if (path.length > 60) {
			const parts = path.split('/');
			if (parts.length > 3) {
				return `.../${parts.slice(-3).join('/')}`;
			}
		}
		return path;
	});

	// Derived: file format
	let fileFormat = $derived(() => {
		const src = dataSource();
		if (!src) return null;
		return src.file_format || (src as any).format || null;
	});

	// Fetch sample data from API
	async function fetchPreviewData() {
		if (!workflowId || previewLoading) return;

		previewLoading = true;
		previewData = null;

		try {
			const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}/sample-data?limit=3`);
			if (response.ok) {
				previewData = await response.json();
			} else {
				const errorText = await response.text();
				previewData = { records: [], total: 0, message: `API Error (${response.status}): ${errorText.substring(0, 100)}` };
			}
		} catch (error) {
			previewData = { records: [], total: 0, message: `Network error: ${error instanceof Error ? error.message : String(error)}` };
		} finally {
			previewLoading = false;
		}
	}

	// Toggle preview and fetch data if needed
	function togglePreview() {
		showDataPreview = !showDataPreview;
		if (showDataPreview && !previewData && !previewLoading) {
			fetchPreviewData();
		}
	}

	function handleRun() {
		let runArgs: Record<string, unknown> = {};
		if (runArgsText.trim() && runArgsText.trim() !== '{}') {
			try {
				runArgs = JSON.parse(runArgsText);
				runArgsError = null;
			} catch (e) {
				runArgsError = 'Invalid JSON format for run args';
				return;
			}
		}

		dispatch('run', {
			inputData: {},
			startIndex,
			numRecords,
			batchSize,
			checkpointInterval,
			runName: runName || generateRunName(),
			outputWithTs,
			outputDir: outputDir || '',
			debug,
			resume,
			quality,
			disableMetadata,
			runArgs
		});
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dispatch('close');
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('close')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
			<div>
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
					Run Workflow
				</h3>
				<p class="text-sm text-gray-500 mt-0.5">{workflowName}</p>
			</div>
			<button
				onclick={() => dispatch('close')}
				class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Body (scrollable) -->
		<div class="flex-1 overflow-y-auto p-6 space-y-5">
			<!-- Data Source Info (read-only) -->
			{#if dataSource() || nodeCount > 0}
				<div class="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-800/30 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
					<div class="flex items-center justify-between mb-3">
						<div class="flex items-center gap-2.5">
							<!-- Source Type Icon -->
							{#if isHuggingFace()}
								<div class="p-1.5 rounded-lg bg-yellow-100 dark:bg-yellow-900/30">
									<span class="text-base">🤗</span>
								</div>
							{:else if isServiceNow()}
								<div class="p-1.5 rounded-lg bg-green-100 dark:bg-green-900/30">
									<Globe size={16} class="text-green-600 dark:text-green-400" />
								</div>
							{:else if isLocalFile()}
								<div class="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
									<FileText size={16} class="text-blue-600 dark:text-blue-400" />
								</div>
							{:else}
								<div class="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30">
									<Database size={16} class="text-violet-600 dark:text-violet-400" />
								</div>
							{/if}
							<span class="text-sm font-semibold text-gray-800 dark:text-gray-200">{sourceTypeLabel()}</span>
						</div>
						{#if nodeCount > 0}
							<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800 px-2 py-1 rounded-full border border-gray-200 dark:border-gray-600">
								<Layers size={12} />
								<span>{nodeCount} nodes</span>
							</div>
						{/if}
					</div>

					<!-- Data Source Details -->
					{#if dataSource()}
						<div class="space-y-2 text-sm">
							<!-- HuggingFace specific info -->
							{#if isHuggingFace()}
								{#if dataSource()?.repo_id}
									<div class="flex items-start gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Dataset:</span>
										<a href="https://huggingface.co/datasets/{dataSource()?.repo_id}" target="_blank" rel="noopener" class="text-yellow-600 dark:text-yellow-400 hover:underline font-mono text-xs break-all">
											{dataSource()?.repo_id}
										</a>
									</div>
								{/if}
								{#if dataSource()?.config_name}
									<div class="flex items-center gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Config:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs bg-white dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-600">{dataSource()?.config_name}</span>
									</div>
								{/if}
								{#if dataSource()?.split}
									<div class="flex items-center gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Split:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs bg-white dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-600">{dataSource()?.split}</span>
									</div>
								{/if}
							<!-- Local file info -->
							{:else if isLocalFile()}
								{#if displayPath()}
									<div class="flex items-start gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Path:</span>
										<code class="text-gray-800 dark:text-gray-200 font-mono text-xs bg-white dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-600 break-all" title={dataSource()?.file_path || ''}>
											{displayPath()}
										</code>
									</div>
								{/if}
								{#if fileFormat()}
									<div class="flex items-center gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Format:</span>
										<span class="text-gray-800 dark:text-gray-200 font-medium uppercase text-xs bg-white dark:bg-gray-800 px-2 py-0.5 rounded border border-gray-200 dark:border-gray-600">{fileFormat()}</span>
									</div>
								{/if}
							<!-- ServiceNow info -->
							{:else if isServiceNow()}
								{#if dataSource()?.instance}
									<div class="flex items-center gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Instance:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{dataSource()?.instance}</span>
									</div>
								{/if}
								{#if dataSource()?.table_name}
									<div class="flex items-center gap-2">
										<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Table:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{dataSource()?.table_name}</span>
									</div>
								{/if}
							{/if}

							<!-- Transformations indicator -->
							{#if dataSource()?.transformations && Array.isArray(dataSource()?.transformations) && dataSource()?.transformations.length > 0}
								<div class="flex items-center gap-2 pt-1">
									<span class="text-gray-500 dark:text-gray-400 flex-shrink-0 w-16">Transform:</span>
									<span class="text-xs text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 px-2 py-0.5 rounded">
										{dataSource()?.transformations.length} transformation{dataSource()?.transformations.length > 1 ? 's' : ''} applied
									</span>
								</div>
							{/if}
						</div>

						<!-- Data Preview Toggle -->
						<button
							type="button"
							onclick={togglePreview}
							disabled={previewLoading}
							class="mt-3 flex items-center gap-1.5 text-xs font-medium text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 transition-colors disabled:opacity-50"
						>
							{#if previewLoading}
								<Loader2 size={14} class="animate-spin" />
								<span>Loading preview...</span>
							{:else if showDataPreview}
								<EyeOff size={14} />
								<span>Hide Preview</span>
							{:else}
								<Eye size={14} />
								<span>Preview Sample Records</span>
							{/if}
						</button>

						{#if showDataPreview}
							<div class="mt-3">
								<DataTableViewer
									data={previewData?.records ?? null}
									title="Sample Data"
									total={previewData?.total}
									maxRecords={5}
									loading={previewLoading}
									error={previewData?.message && (!previewData?.records || previewData.records.length === 0) ? previewData.message : null}
									showViewToggle={false}
									defaultView="table"
								/>
							</div>
						{/if}
					{:else}
						<p class="text-sm text-gray-500 dark:text-gray-400 italic">No data source configured. This workflow may use inline data or weighted samplers.</p>
					{/if}
				</div>
			{/if}

			<!-- Execution Parameters Section -->
			<div>
				<div class="flex items-center gap-2 mb-3">
					<Hash size={16} class="text-violet-500" />
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Execution Parameters</span>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label class="block text-sm text-gray-600 dark:text-gray-400 mb-1.5" for="num-records">
							Number of Records
						</label>
						<input
							id="num-records"
							type="number"
							bind:value={numRecords}
							min="1"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
						/>
						<p class="mt-1 text-xs text-gray-500">How many records to process</p>
					</div>
					<div>
						<label class="block text-sm text-gray-600 dark:text-gray-400 mb-1.5" for="start-index">
							Start Index
						</label>
						<input
							id="start-index"
							type="number"
							bind:value={startIndex}
							min="0"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
						/>
						<p class="mt-1 text-xs text-gray-500">Skip first N records (default: 0)</p>
					</div>
				</div>
			</div>

			<!-- Run Identification Section -->
			<div>
				<div class="flex items-center gap-2 mb-3">
					<Tag size={16} class="text-violet-500" />
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Run Identification</span>
				</div>

				<div>
					<label class="block text-sm text-gray-600 dark:text-gray-400 mb-1.5" for="run-name">
						Run Name
						<span class="text-gray-400 font-normal">(optional)</span>
					</label>
					<input
						id="run-name"
						type="text"
						bind:value={runName}
						placeholder={generateRunName()}
						class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
					/>
					<p class="mt-1 text-xs text-gray-500">Leave empty for auto-generated name with timestamp</p>
				</div>
			</div>

			<!-- Advanced Options toggle -->
			<button
				type="button"
				onclick={() => showAdvanced = !showAdvanced}
				class="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
			>
				<Settings size={16} />
				Advanced Options
				<ChevronDown size={16} class="transition-transform {showAdvanced ? 'rotate-180' : ''}" />
			</button>

			{#if showAdvanced}
				<div class="space-y-4 pl-4 border-l-2 border-gray-200 dark:border-gray-700">
					<!-- Batch settings -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="batch-size">
								Batch Size
							</label>
							<input
								id="batch-size"
								type="number"
								bind:value={batchSize}
								min="1"
								class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
							/>
							<p class="mt-1 text-xs text-gray-500">Records per batch</p>
						</div>
						<div>
							<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="checkpoint">
								Checkpoint Interval
							</label>
							<input
								id="checkpoint"
								type="number"
								bind:value={checkpointInterval}
								min="1"
								class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
							/>
							<p class="mt-1 text-xs text-gray-500">Records between saves</p>
						</div>
					</div>

					<!-- Output options -->
					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="output-dir">
							Output Directory (optional)
						</label>
						<input
							id="output-dir"
							type="text"
							bind:value={outputDir}
							placeholder="Leave empty for default"
							class="w-full px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
						/>
					</div>

					<!-- Boolean toggles -->
					<div class="grid grid-cols-2 gap-4">
						<label class="flex items-center gap-2 cursor-pointer">
							<input
								type="checkbox"
								bind:checked={outputWithTs}
								class="w-4 h-4 text-violet-600 border-gray-300 rounded focus:ring-violet-500"
							/>
							<span class="text-sm text-gray-700 dark:text-gray-300">Add timestamp to output</span>
						</label>
						<label class="flex items-center gap-2 cursor-pointer">
							<input
								type="checkbox"
								bind:checked={debug}
								class="w-4 h-4 text-violet-600 border-gray-300 rounded focus:ring-violet-500"
							/>
							<span class="text-sm text-gray-700 dark:text-gray-300">Debug mode</span>
						</label>
						<label class="flex items-center gap-2 cursor-pointer">
							<input
								type="checkbox"
								bind:checked={quality}
								class="w-4 h-4 text-violet-600 border-gray-300 rounded focus:ring-violet-500"
							/>
							<span class="text-sm text-gray-700 dark:text-gray-300">Enable quality metrics</span>
						</label>
						<label class="flex items-center gap-2 cursor-pointer">
							<input
								type="checkbox"
								bind:checked={disableMetadata}
								class="w-4 h-4 text-violet-600 border-gray-300 rounded focus:ring-violet-500"
							/>
							<span class="text-sm text-gray-700 dark:text-gray-300">Disable metadata</span>
						</label>
					</div>

					<!-- Resume option -->
					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
							Resume Behavior
						</label>
						<div class="flex gap-4">
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="radio"
									name="resume"
									checked={resume === null}
									onchange={() => resume = null}
									class="w-4 h-4 text-violet-600 border-gray-300 focus:ring-violet-500"
								/>
								<span class="text-sm text-gray-700 dark:text-gray-300">Default</span>
							</label>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="radio"
									name="resume"
									checked={resume === true}
									onchange={() => resume = true}
									class="w-4 h-4 text-violet-600 border-gray-300 focus:ring-violet-500"
								/>
								<span class="text-sm text-gray-700 dark:text-gray-300">Force Resume</span>
							</label>
							<label class="flex items-center gap-2 cursor-pointer">
								<input
									type="radio"
									name="resume"
									checked={resume === false}
									onchange={() => resume = false}
									class="w-4 h-4 text-violet-600 border-gray-300 focus:ring-violet-500"
								/>
								<span class="text-sm text-gray-700 dark:text-gray-300">No Resume</span>
							</label>
						</div>
					</div>

					<!-- Custom run args -->
					<div>
						<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1" for="run-args">
							Custom Run Arguments (JSON)
						</label>
						<textarea
							id="run-args"
							bind:value={runArgsText}
							class="w-full h-20 px-3 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono text-sm focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none"
							placeholder={'{"custom_key": "custom_value"}'}
						></textarea>
						{#if runArgsError}
							<p class="mt-1 text-xs text-red-500">{runArgsError}</p>
						{/if}
					</div>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl border-t border-gray-200 dark:border-gray-700">
			<button
				onclick={() => dispatch('close')}
				class="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 transition-colors"
			>
				Cancel
			</button>
			<button
				onclick={handleRun}
				class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium text-white transition-colors"
			>
				<Play size={16} />
				Run Workflow
			</button>
		</div>
	</div>
</div>
