<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails, JoinType } from '$lib/stores/workflow.svelte';
	import {
		X, Database, Cloud, Server, HardDrive, MemoryStick,
		Link, ArrowRight, Info, Save, ChevronDown, ChevronUp,
		Tag, Settings2, FileJson
	} from 'lucide-svelte';
	import SourceTypeSelector from './SourceTypeSelector.svelte';
	import JoinTypeSelector from './JoinTypeSelector.svelte';

	interface Props {
		source?: DataSourceDetails;
		isPrimary?: boolean;
		hasPrimarySource?: boolean;
		open?: boolean;
	}

	let { source, isPrimary = false, hasPrimarySource = false, open = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		save: { source: DataSourceDetails };
		close: void;
	}>();

	// Form state - initialize from source or defaults
	let type = $state<'hf' | 'disk' | 'servicenow' | 'memory'>(source?.type || 'hf');
	let alias = $state(source?.alias || '');
	let joinType = $state<JoinType>(source?.join_type || (isPrimary || !hasPrimarySource ? 'primary' : 'column'));
	let primaryKey = $state(source?.primary_key || '');
	let joinKey = $state(source?.join_key || '');

	// HuggingFace fields
	let repoId = $state(source?.repo_id || '');
	let configName = $state(source?.config_name || '');
	let split = $state(Array.isArray(source?.split) ? source.split.join(', ') : (source?.split || 'train'));
	let streaming = $state(source?.streaming || false);

	// Disk fields
	let filePath = $state(source?.file_path || '');
	let fileFormat = $state(source?.file_format || 'json');
	let encoding = $state(source?.encoding || 'utf-8');

	// ServiceNow fields
	let table = $state(source?.table || '');
	let query = $state(source?.query || '');
	let fields = $state(source?.fields?.join(', ') || '');
	let limit = $state(source?.limit);
	let batchSize = $state(source?.batch_size || 100);
	let orderBy = $state(source?.order_by || '');
	let orderDesc = $state(source?.order_desc || false);

	// Section expansion state
	let showAdvanced = $state(false);

	// Validation state - show errors after first save attempt
	let showErrors = $state(false);

	// Individual field error states
	let aliasError = $derived(showErrors && joinType !== 'primary' && !alias.trim() ? 'Alias is required for non-primary sources' : '');
	let repoIdError = $derived(showErrors && type === 'hf' && !repoId.trim() ? 'Repository ID is required' : '');
	let filePathError = $derived(showErrors && type === 'disk' && !filePath.trim() ? 'File path is required' : '');
	let tableError = $derived(showErrors && type === 'servicenow' && !table.trim() ? 'Table name is required' : '');
	let primaryKeyError = $derived(showErrors && joinType === 'column' && !primaryKey.trim() ? 'Primary key is required for column join' : '');
	let joinKeyError = $derived(showErrors && joinType === 'column' && !joinKey.trim() ? 'Join key is required for column join' : '');

	// Reset form when source changes
	$effect(() => {
		if (source) {
			type = source.type || 'hf';
			alias = source.alias || '';
			joinType = source.join_type || 'primary';
			primaryKey = source.primary_key || '';
			joinKey = source.join_key || '';
			repoId = source.repo_id || '';
			configName = source.config_name || '';
			split = Array.isArray(source.split) ? source.split.join(', ') : (source.split || 'train');
			streaming = source.streaming || false;
			filePath = source.file_path || '';
			fileFormat = source.file_format || 'json';
			encoding = source.encoding || 'utf-8';
			table = source.table || '';
			query = source.query || '';
			fields = source.fields?.join(', ') || '';
			limit = source.limit;
			batchSize = source.batch_size || 100;
			orderBy = source.order_by || '';
			orderDesc = source.order_desc || false;
		}
	});

	// Join types that require key configuration
	let needsKeyConfig = $derived(joinType === 'column');

	// Check if form is valid
	let isValid = $derived(() => {
		// Must have alias if not primary
		if (joinType !== 'primary' && !alias.trim()) return false;

		// Must have type-specific required fields
		if (type === 'hf' && !repoId.trim()) return false;
		if (type === 'disk' && !filePath.trim()) return false;
		if (type === 'servicenow' && !table.trim()) return false;

		// Column join requires keys
		if (joinType === 'column' && (!primaryKey.trim() || !joinKey.trim())) return false;

		return true;
	});

	function handleSave() {
		showErrors = true;
		if (!isValid()) return;

		const newSource: DataSourceDetails = {
			type,
			alias: alias.trim() || undefined,
			join_type: joinType,
			primary_key: joinType === 'column' ? primaryKey : undefined,
			join_key: joinType === 'column' ? joinKey : undefined,
		};

		// Add type-specific fields
		if (type === 'hf') {
			newSource.repo_id = repoId;
			if (configName) newSource.config_name = configName;
			newSource.split = split.includes(',') ? split.split(',').map(s => s.trim()) : split;
			if (streaming) newSource.streaming = streaming;
		} else if (type === 'disk') {
			newSource.file_path = filePath;
			if (fileFormat) newSource.file_format = fileFormat;
			if (encoding && encoding !== 'utf-8') newSource.encoding = encoding;
		} else if (type === 'servicenow') {
			newSource.table = table;
			if (query) newSource.query = query;
			if (fields) newSource.fields = fields.split(',').map(s => s.trim());
			if (limit) newSource.limit = limit;
			if (batchSize !== 100) newSource.batch_size = batchSize;
			if (orderBy) newSource.order_by = orderBy;
			if (orderDesc) newSource.order_desc = orderDesc;
		}

		// Preserve existing transformations
		if (source?.transformations) {
			newSource.transformations = source.transformations;
		}

		dispatch('save', { source: newSource });
	}

	function handleClose() {
		showErrors = false;
		dispatch('close');
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) handleClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
	}

	// Get icon for current type
	function getTypeIcon(t: string) {
		switch (t) {
			case 'hf': return Cloud;
			case 'disk': return HardDrive;
			case 'servicenow': return Server;
			case 'memory': return MemoryStick;
			default: return Database;
		}
	}

	let TypeIcon = $derived(getTypeIcon(type));
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<div
		class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
		onclick={handleBackdropClick}
		role="dialog"
		aria-modal="true"
	>
		<div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
			<!-- Header -->
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-900">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-xl bg-gradient-to-br from-blue-100 to-[#7661FF]/20 dark:from-blue-900/40 dark:to-[#7661FF]/30">
						<Database size={20} class="text-blue-600 dark:text-blue-400" />
					</div>
					<div>
						<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
							{source ? 'Edit Data Source' : 'Add Data Source'}
						</h2>
						<p class="text-xs text-gray-500 dark:text-gray-400">
							Configure where your data comes from
						</p>
					</div>
				</div>
				<button
					onclick={handleClose}
					class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors"
				>
					<X size={20} />
				</button>
			</div>

			<!-- Content -->
			<div class="flex-1 overflow-y-auto">
				<!-- Section 1: Source Type -->
				<div class="p-6 border-b border-gray-100 dark:border-gray-800">
					<div class="flex items-center gap-2 mb-4">
						<div class="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30">
							<Database size={14} class="text-blue-600 dark:text-blue-400" />
						</div>
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Source Type</h3>
					</div>

					<SourceTypeSelector bind:value={type} />
				</div>

				<!-- Section 2: Alias -->
				<div class="px-6 py-4 border-b border-gray-100 dark:border-gray-800">
					<div class="flex items-center gap-2 mb-3">
						<div class="p-1.5 rounded-lg bg-[#7661FF]/15 dark:bg-[#7661FF]/20">
							<Tag size={14} class="text-[#7661FF] dark:text-[#BF71F2]" />
						</div>
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
							Alias
							{#if joinType !== 'primary'}<span class="text-red-500 ml-1">*</span>{/if}
						</h3>
					</div>

					<input
						type="text"
						bind:value={alias}
						placeholder="e.g., incidents, users, products"
						class="w-full px-4 py-2.5 border rounded-xl bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 transition-all {aliasError ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : 'border-gray-200 dark:border-gray-700 focus:ring-[#52B8FF] focus:border-[#52B8FF]'}"
					/>
					{#if aliasError}
						<p class="text-xs text-red-500 mt-1">{aliasError}</p>
					{/if}
					<p class="text-xs text-gray-500 dark:text-gray-400 mt-2 flex items-center gap-1">
						<Info size={12} />
						Use in prompts: <code class="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono text-[#7661FF] dark:text-[#BF71F2]">{'{column_name}'}</code>
					</p>
				</div>

				<!-- Section 3: Join Configuration (for non-primary) -->
				{#if !isPrimary}
					<div class="px-6 py-4 border-b border-gray-100 dark:border-gray-800">
						<div class="flex items-center gap-2 mb-4">
							<div class="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30">
								<Link size={14} class="text-emerald-600 dark:text-emerald-400" />
							</div>
							<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Join Strategy</h3>
						</div>

						<JoinTypeSelector
							bind:value={joinType}
							excludePrimary={hasPrimarySource && source?.join_type !== 'primary'}
						/>

						<!-- Key Configuration (for column join) -->
						{#if needsKeyConfig}
							<div class="mt-4 p-4 bg-[#7661FF]/10 dark:bg-[#7661FF]/15 rounded-xl border border-[#7661FF]/30 dark:border-[#7661FF]/40">
								<div class="text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] mb-3 flex items-center gap-1">
									<Link size={12} />
									Column Join Keys
								</div>
								<div class="grid grid-cols-2 gap-3">
									<div>
										<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1.5">
											Primary Key <span class="text-red-500">*</span>
										</label>
										<input
											type="text"
											bind:value={primaryKey}
											placeholder="Column in primary source"
											class="w-full px-3 py-2 text-sm font-mono border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 {primaryKeyError ? 'border-red-500 focus:ring-red-500' : 'border-[#7661FF]/30 dark:border-[#7661FF]/40 focus:ring-[#52B8FF]'}"
										/>
										{#if primaryKeyError}
											<p class="text-xs text-red-500 mt-1">{primaryKeyError}</p>
										{/if}
									</div>
									<div>
										<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1.5">
											Join Key <span class="text-red-500">*</span>
										</label>
										<input
											type="text"
											bind:value={joinKey}
											placeholder="Column in this source"
											class="w-full px-3 py-2 text-sm font-mono border rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 {joinKeyError ? 'border-red-500 focus:ring-red-500' : 'border-[#7661FF]/30 dark:border-[#7661FF]/40 focus:ring-[#52B8FF]'}"
										/>
										{#if joinKeyError}
											<p class="text-xs text-red-500 mt-1">{joinKeyError}</p>
										{/if}
									</div>
								</div>
								<div class="mt-3 text-xs text-[#7661FF] dark:text-[#BF71F2] flex items-center gap-2 justify-center p-2 bg-white dark:bg-gray-800/50 rounded-lg">
									<span class="font-mono font-medium">{primaryKey || 'primary_key'}</span>
									<ArrowRight size={14} />
									<span class="font-mono font-medium">{joinKey || 'join_key'}</span>
								</div>
							</div>
						{/if}
					</div>
				{/if}

				<!-- Section 4: Type-specific Configuration -->
				<div class="px-6 py-4">
					<div class="flex items-center gap-2 mb-4">
						<div class="p-1.5 rounded-lg bg-amber-100 dark:bg-amber-900/30">
							<Settings2 size={14} class="text-amber-600 dark:text-amber-400" />
						</div>
						<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Source Configuration</h3>
					</div>

					{#if type === 'hf'}
						<!-- HuggingFace -->
						<div class="space-y-4">
							<div>
								<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
									Repository ID <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<Cloud size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-amber-500" />
									<input
										type="text"
										bind:value={repoId}
										placeholder="username/dataset-name"
										class="w-full pl-10 pr-4 py-2.5 font-mono border rounded-xl bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 {repoIdError ? 'border-red-500 focus:ring-red-500' : 'border-gray-200 dark:border-gray-700 focus:ring-[#52B8FF]'}"
									/>
								</div>
								{#if repoIdError}
									<p class="text-xs text-red-500 mt-1">{repoIdError}</p>
								{/if}
							</div>
							<div class="grid grid-cols-2 gap-4">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Config Name</label>
									<input
										type="text"
										bind:value={configName}
										placeholder="default"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Split</label>
									<input
										type="text"
										bind:value={split}
										placeholder="train"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
							</div>
							<label class="flex items-center gap-3 cursor-pointer p-3 bg-gray-50 dark:bg-gray-800 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">
								<input
									type="checkbox"
									bind:checked={streaming}
									class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-[#7661FF] focus:ring-[#52B8FF]"
								/>
								<div>
									<span class="text-sm text-gray-700 dark:text-gray-300 font-medium">Enable streaming mode</span>
									<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Load data progressively without loading everything into memory</p>
								</div>
							</label>
						</div>

					{:else if type === 'disk'}
						<!-- Disk -->
						<div class="space-y-4">
							<div>
								<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
									File Path <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<HardDrive size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-blue-500" />
									<input
										type="text"
										bind:value={filePath}
										placeholder="/path/to/data.json"
										class="w-full pl-10 pr-4 py-2.5 font-mono border rounded-xl bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 {filePathError ? 'border-red-500 focus:ring-red-500' : 'border-gray-200 dark:border-gray-700 focus:ring-[#52B8FF]'}"
									/>
								</div>
								{#if filePathError}
									<p class="text-xs text-red-500 mt-1">{filePathError}</p>
								{/if}
							</div>
							<div class="grid grid-cols-2 gap-4">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">File Format</label>
									<select
										bind:value={fileFormat}
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									>
										<option value="json">JSON</option>
										<option value="jsonl">JSONL</option>
										<option value="csv">CSV</option>
										<option value="parquet">Parquet</option>
										<option value="folder">Folder</option>
									</select>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Encoding</label>
									<input
										type="text"
										bind:value={encoding}
										placeholder="utf-8"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
									/>
								</div>
							</div>
						</div>

					{:else if type === 'servicenow'}
						<!-- ServiceNow -->
						<div class="space-y-4">
							<div>
								<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
									Table Name <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<Server size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-500" />
									<input
										type="text"
										bind:value={table}
										placeholder="incident"
										class="w-full pl-10 pr-4 py-2.5 font-mono border rounded-xl bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 {tableError ? 'border-red-500 focus:ring-red-500' : 'border-gray-200 dark:border-gray-700 focus:ring-[#52B8FF]'}"
									/>
								</div>
								{#if tableError}
									<p class="text-xs text-red-500 mt-1">{tableError}</p>
								{/if}
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Query Filter</label>
								<input
									type="text"
									bind:value={query}
									placeholder="active=true^priority=1"
									class="w-full px-3 py-2.5 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Fields (comma-separated)</label>
								<input
									type="text"
									bind:value={fields}
									placeholder="sys_id, number, short_description"
									class="w-full px-3 py-2.5 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
							</div>

							<!-- Advanced Options -->
							<button
								type="button"
								onclick={() => showAdvanced = !showAdvanced}
								class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
							>
								{#if showAdvanced}
									<ChevronUp size={16} />
								{:else}
									<ChevronDown size={16} />
								{/if}
								Advanced Options
							</button>

							{#if showAdvanced}
								<div class="grid grid-cols-2 gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-xl">
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Limit</label>
										<input
											type="number"
											bind:value={limit}
											placeholder="1000"
											class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Batch Size</label>
										<input
											type="number"
											bind:value={batchSize}
											class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1.5">Order By</label>
										<input
											type="text"
											bind:value={orderBy}
											placeholder="sys_created_on"
											class="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100"
										/>
									</div>
									<div class="flex items-end">
										<label class="flex items-center gap-2 cursor-pointer pb-2">
											<input
												type="checkbox"
												bind:checked={orderDesc}
												class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-[#7661FF]"
											/>
											<span class="text-sm text-gray-700 dark:text-gray-300">Descending</span>
										</label>
									</div>
								</div>
							{/if}
						</div>

					{:else if type === 'memory'}
						<!-- Memory -->
						<div class="flex items-start gap-3 p-4 bg-[#BF71F2]/10 dark:bg-[#BF71F2]/15 rounded-xl border border-[#BF71F2]/30 dark:border-[#BF71F2]/40">
							<div class="p-2 rounded-lg bg-[#BF71F2]/20 dark:bg-[#BF71F2]/30">
								<MemoryStick size={16} class="text-[#BF71F2] dark:text-[#BF71F2]" />
							</div>
							<div class="text-sm text-[#BF71F2] dark:text-[#BF71F2]">
								<p class="font-medium">In-Memory Data Source</p>
								<p class="text-xs mt-1 text-[#BF71F2]/80 dark:text-[#BF71F2]/80">
									Data will be provided inline in the configuration or through input parameters at runtime.
									Use this for small datasets or dynamic data passed from previous workflow steps.
								</p>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
				<div class="text-xs text-gray-500 dark:text-gray-400">
					{#if !isValid()}
						Fill in required fields marked with <span class="text-red-500">*</span>
					{:else}
						<span class="text-emerald-600 dark:text-emerald-400">Ready to save</span>
					{/if}
				</div>
				<div class="flex items-center gap-3">
					<button
						onclick={handleClose}
						class="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition-colors"
					>
						Cancel
					</button>
					<button
						onclick={handleSave}
						class="flex items-center gap-2 px-5 py-2 text-sm bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-xl transition-colors shadow-sm hover:shadow-md font-medium"
					>
						<Save size={16} />
						{source ? 'Save Changes' : 'Add Source'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
