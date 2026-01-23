<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails, JoinType } from '$lib/stores/workflow.svelte';
	import {
		X, Database, Cloud, Server, HardDrive,
		Link, ArrowRight, Save, ChevronDown, ChevronUp,
		Tag, Settings2, Check, AlertCircle
	} from 'lucide-svelte';

	interface Props {
		source?: DataSourceDetails;
		isPrimary?: boolean;
		hasPrimarySource?: boolean;
		requireAlias?: boolean;  // True when there are other sources
		open?: boolean;
	}

	let { source, isPrimary = false, hasPrimarySource = false, requireAlias = false, open = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		save: { source: DataSourceDetails };
		close: void;
	}>();

	// Form state (memory type is not supported in UI - only used by Python library)
	let type = $state<'hf' | 'disk' | 'servicenow'>(
		(source?.type === 'memory' ? 'hf' : source?.type) || 'hf'
	);
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

	// UI state
	let showAdvanced = $state(false);
	let showErrors = $state(false);

	// Reset form when source changes
	$effect(() => {
		if (source) {
			type = (source.type === 'memory' ? 'hf' : source.type) || 'hf';
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

	// Computed states
	let needsJoinConfig = $derived(requireAlias && joinType !== 'primary');
	let needsKeyConfig = $derived(joinType === 'column');

	// Validation
	let aliasError = $derived(showErrors && requireAlias && joinType !== 'primary' && !alias.trim() ? 'Required for non-primary sources' : '');
	let repoIdError = $derived(showErrors && type === 'hf' && !repoId.trim() ? 'Repository ID is required' : '');
	let filePathError = $derived(showErrors && type === 'disk' && !filePath.trim() ? 'File path is required' : '');
	let tableError = $derived(showErrors && type === 'servicenow' && !table.trim() ? 'Table name is required' : '');
	let primaryKeyError = $derived(showErrors && needsKeyConfig && !primaryKey.trim() ? 'Primary key is required' : '');
	let joinKeyError = $derived(showErrors && needsKeyConfig && !joinKey.trim() ? 'Join key is required' : '');

	let isValid = $derived(() => {
		if (requireAlias && joinType !== 'primary' && !alias.trim()) return false;
		if (type === 'hf' && !repoId.trim()) return false;
		if (type === 'disk' && !filePath.trim()) return false;
		if (type === 'servicenow' && !table.trim()) return false;
		if (needsKeyConfig && (!primaryKey.trim() || !joinKey.trim())) return false;
		return true;
	});

	// Source type configurations
	const sourceTypes = [
		{ value: 'hf' as const, label: 'HuggingFace', desc: 'Datasets Hub', icon: Cloud, color: 'amber' },
		{ value: 'disk' as const, label: 'Local File', desc: 'JSON, CSV, Parquet', icon: HardDrive, color: 'blue' },
		{ value: 'servicenow' as const, label: 'ServiceNow', desc: 'Table queries', icon: Server, color: 'emerald' }
	];

	// Join type configurations (simplified for UI)
	const joinTypes = [
		{ value: 'primary' as const, label: 'Primary', desc: 'Main data source' },
		{ value: 'column' as const, label: 'Column Join', desc: 'Match by key column' },
		{ value: 'sequential' as const, label: 'Sequential', desc: 'Cycle through records' },
		{ value: 'random' as const, label: 'Random', desc: 'Random matching' },
		{ value: 'cross' as const, label: 'Cross Product', desc: 'All combinations' },
		{ value: 'vstack' as const, label: 'Vertical Stack', desc: 'Append records' }
	];

	function handleSave() {
		showErrors = true;
		if (!isValid()) return;

		const newSource: DataSourceDetails = {
			type,
			...(requireAlias && alias.trim() ? { alias: alias.trim() } : {}),
			...(requireAlias ? { join_type: joinType } : {}),
			...(needsKeyConfig ? { primary_key: primaryKey, join_key: joinKey } : {})
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

		// Preserve transformations
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

	function getColorClasses(color: string, selected: boolean) {
		const colors: Record<string, { bg: string; border: string; icon: string }> = {
			amber: { bg: 'bg-warning-light dark:bg-warning-light', border: 'border-warning-border', icon: 'text-warning dark:text-warning' },
			blue: { bg: 'bg-info-light dark:bg-info-light', border: 'border-info-border', icon: 'text-info dark:text-info' },
			emerald: { bg: 'bg-success-light dark:bg-success-light', border: 'border-success-border', icon: 'text-success dark:text-success' }
		};
		return colors[color] || colors.blue;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- Simple semi-transparent backdrop (no blur) -->
	<div
		class="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
		onclick={handleBackdropClick}
		role="dialog"
		aria-modal="true"
	>
		<div class="bg-white dark:bg-gray-900 rounded-xl shadow-xl w-full max-w-lg max-h-[85vh] overflow-hidden flex flex-col border border-gray-200 dark:border-gray-700">
			<!-- Header -->
			<div class="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-lg bg-info-light dark:bg-info-light">
						<Database size={18} class="text-info dark:text-info" />
					</div>
					<div>
						<h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">
							{source ? 'Edit Data Source' : 'Add Data Source'}
						</h2>
						<p class="text-xs text-gray-500 dark:text-gray-400">
							{requireAlias ? 'Configure source for multi-dataset workflow' : 'Configure your data source'}
						</p>
					</div>
				</div>
				<button
					onclick={handleClose}
					class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Content -->
			<div class="flex-1 overflow-y-auto p-5 space-y-5">
				<!-- Source Type Selection -->
				<div>
					<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">
						Source Type
					</label>
					<div class="grid grid-cols-3 gap-2">
						{#each sourceTypes as st}
							{@const Icon = st.icon}
							{@const isSelected = type === st.value}
							{@const colors = getColorClasses(st.color, isSelected)}
							<button
								type="button"
								onclick={() => type = st.value}
								class="relative flex flex-col items-center p-3 rounded-lg border-2 transition-all
									{isSelected
										? `${colors.bg} ${colors.border} shadow-sm`
										: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 bg-white dark:bg-gray-800'}"
							>
								<Icon size={20} class={isSelected ? colors.icon : 'text-gray-400 dark:text-gray-500'} />
								<span class="text-xs font-medium mt-1.5 {isSelected ? 'text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400'}">
									{st.label}
								</span>
								{#if isSelected}
									<div class="absolute top-1 right-1 w-4 h-4 rounded-full bg-success flex items-center justify-center">
										<Check size={10} class="text-white" strokeWidth={3} />
									</div>
								{/if}
							</button>
						{/each}
					</div>
				</div>

				<!-- Multi-Source Configuration (only shown when there are other sources) -->
				{#if requireAlias}
					<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg space-y-4">
						<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide">
							<Link size={12} />
							Multi-Source Settings
						</div>

						<!-- Alias -->
						<div>
							<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
								Alias {#if joinType !== 'primary'}<span class="text-red-500">*</span>{/if}
							</label>
							<input
								type="text"
								bind:value={alias}
								placeholder="e.g., incidents, users"
								class="w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100
									{aliasError ? 'border-red-400 focus:ring-red-400' : 'border-gray-200 dark:border-gray-600 focus:ring-blue-400'}
									focus:ring-2 focus:border-transparent transition-all"
							/>
							{#if aliasError}
								<p class="text-xs text-red-500 mt-1 flex items-center gap-1">
									<AlertCircle size={10} />
									{aliasError}
								</p>
							{:else}
								<p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
									Reference in prompts: <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">{'{' + (alias || 'alias') + '->field}'}</code>
								</p>
							{/if}
						</div>

						<!-- Join Type -->
						<div>
							<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">Join Strategy</label>
							<select
								bind:value={joinType}
								class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-400 focus:border-transparent"
							>
								{#each joinTypes as jt}
									{#if !(hasPrimarySource && source?.join_type !== 'primary' && jt.value === 'primary')}
										<option value={jt.value}>{jt.label} - {jt.desc}</option>
									{/if}
								{/each}
							</select>
						</div>

						<!-- Join Keys (for column join) -->
						{#if needsKeyConfig}
							<div class="grid grid-cols-2 gap-3 p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-600">
								<div>
									<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
										Primary Key <span class="text-red-500">*</span>
									</label>
									<input
										type="text"
										bind:value={primaryKey}
										placeholder="id column"
										class="w-full px-3 py-2 text-sm font-mono border rounded-lg bg-gray-50 dark:bg-gray-800
											{primaryKeyError ? 'border-red-400' : 'border-gray-200 dark:border-gray-600'}"
									/>
									{#if primaryKeyError}
										<p class="text-xs text-red-500 mt-1">{primaryKeyError}</p>
									{/if}
								</div>
								<div>
									<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
										Join Key <span class="text-red-500">*</span>
									</label>
									<input
										type="text"
										bind:value={joinKey}
										placeholder="id column"
										class="w-full px-3 py-2 text-sm font-mono border rounded-lg bg-gray-50 dark:bg-gray-800
											{joinKeyError ? 'border-red-400' : 'border-gray-200 dark:border-gray-600'}"
									/>
									{#if joinKeyError}
										<p class="text-xs text-red-500 mt-1">{joinKeyError}</p>
									{/if}
								</div>
								<div class="col-span-2 flex items-center justify-center gap-2 text-xs text-gray-500 dark:text-gray-400 pt-1">
									<span class="font-mono bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">{primaryKey || 'primary_key'}</span>
									<ArrowRight size={12} />
									<span class="font-mono bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded">{joinKey || 'join_key'}</span>
								</div>
							</div>
						{/if}
					</div>
				{/if}

				<!-- Source Configuration -->
				<div>
					<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-2">
						<Settings2 size={12} class="inline mr-1" />
						Source Configuration
					</label>

					{#if type === 'hf'}
						<div class="space-y-3">
							<div>
								<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
									Repository ID <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<Cloud size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-amber-500" />
									<input
										type="text"
										bind:value={repoId}
										placeholder="username/dataset-name"
										class="w-full pl-9 pr-3 py-2 text-sm font-mono border rounded-lg bg-white dark:bg-gray-800
											{repoIdError ? 'border-red-400 focus:ring-red-400' : 'border-gray-200 dark:border-gray-600 focus:ring-blue-400'}
											focus:ring-2 focus:border-transparent"
									/>
								</div>
								{#if repoIdError}
									<p class="text-xs text-red-500 mt-1">{repoIdError}</p>
								{/if}
							</div>
							<div class="grid grid-cols-2 gap-3">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Config</label>
									<input
										type="text"
										bind:value={configName}
										placeholder="default"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
									/>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Split</label>
									<input
										type="text"
										bind:value={split}
										placeholder="train"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
									/>
								</div>
							</div>
							<label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
								<input type="checkbox" bind:checked={streaming} class="rounded border-gray-300" />
								Enable streaming mode
							</label>
						</div>

					{:else if type === 'disk'}
						<div class="space-y-3">
							<div>
								<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
									File Path <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<HardDrive size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-blue-500" />
									<input
										type="text"
										bind:value={filePath}
										placeholder="/path/to/data.json"
										class="w-full pl-9 pr-3 py-2 text-sm font-mono border rounded-lg bg-white dark:bg-gray-800
											{filePathError ? 'border-red-400 focus:ring-red-400' : 'border-gray-200 dark:border-gray-600 focus:ring-blue-400'}
											focus:ring-2 focus:border-transparent"
									/>
								</div>
								{#if filePathError}
									<p class="text-xs text-red-500 mt-1">{filePathError}</p>
								{/if}
							</div>
							<div class="grid grid-cols-2 gap-3">
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Format</label>
									<select
										bind:value={fileFormat}
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
									>
										<option value="json">JSON</option>
										<option value="jsonl">JSONL</option>
										<option value="csv">CSV</option>
										<option value="parquet">Parquet</option>
									</select>
								</div>
								<div>
									<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Encoding</label>
									<input
										type="text"
										bind:value={encoding}
										placeholder="utf-8"
										class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
									/>
								</div>
							</div>
						</div>

					{:else if type === 'servicenow'}
						<div class="space-y-3">
							<div>
								<label class="block text-xs text-gray-600 dark:text-gray-400 mb-1">
									Table Name <span class="text-red-500">*</span>
								</label>
								<div class="relative">
									<Server size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-emerald-500" />
									<input
										type="text"
										bind:value={table}
										placeholder="incident"
										class="w-full pl-9 pr-3 py-2 text-sm font-mono border rounded-lg bg-white dark:bg-gray-800
											{tableError ? 'border-red-400 focus:ring-red-400' : 'border-gray-200 dark:border-gray-600 focus:ring-blue-400'}
											focus:ring-2 focus:border-transparent"
									/>
								</div>
								{#if tableError}
									<p class="text-xs text-red-500 mt-1">{tableError}</p>
								{/if}
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Fields (comma-separated)</label>
								<input
									type="text"
									bind:value={fields}
									placeholder="sys_id, number, short_description"
									class="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Query Filter</label>
								<input
									type="text"
									bind:value={query}
									placeholder="active=true^priority=1"
									class="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800"
								/>
							</div>

							<!-- Advanced Options Toggle -->
							<button
								type="button"
								onclick={() => showAdvanced = !showAdvanced}
								class="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
							>
								{#if showAdvanced}<ChevronUp size={14} />{:else}<ChevronDown size={14} />{/if}
								Advanced options
							</button>

							{#if showAdvanced}
								<div class="grid grid-cols-2 gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Limit</label>
										<input
											type="number"
											bind:value={limit}
											placeholder="1000"
											class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Batch Size</label>
										<input
											type="number"
											bind:value={batchSize}
											class="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 dark:text-gray-400 mb-1">Order By</label>
										<input
											type="text"
											bind:value={orderBy}
											placeholder="sys_created_on"
											class="w-full px-3 py-2 text-sm font-mono border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-900"
										/>
									</div>
									<div class="flex items-end pb-2">
										<label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
											<input type="checkbox" bind:checked={orderDesc} class="rounded border-gray-300" />
											Descending
										</label>
									</div>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-between px-5 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
				<div class="text-xs text-gray-500 dark:text-gray-400">
					{#if !isValid() && showErrors}
						<span class="text-red-500 flex items-center gap-1">
							<AlertCircle size={12} />
							Please fill required fields
						</span>
					{:else if isValid()}
						<span class="text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
							<Check size={12} />
							Ready to save
						</span>
					{:else}
						<span class="text-gray-400">Fields marked with * are required</span>
					{/if}
				</div>
				<div class="flex items-center gap-2">
					<button
						onclick={handleClose}
						class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					>
						Cancel
					</button>
					<button
						onclick={handleSave}
						class="flex items-center gap-2 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium"
					>
						<Save size={14} />
						{source ? 'Save' : 'Add Source'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
