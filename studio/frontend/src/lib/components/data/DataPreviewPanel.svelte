<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		Eye, EyeOff, Database, Table2, ChevronDown, ChevronUp,
		RefreshCw, Loader2, ChevronRight, Columns3, Rows3, AlertCircle,
		Music, ImageIcon
	} from 'lucide-svelte';
	import MediaRenderer from '$lib/components/common/MediaRenderer.svelte';
	import { isAudio, isImage, isDataUrl, truncateDataUrl } from '$lib/utils/mediaUtils';

	interface DataPreviewData {
		records: Record<string, unknown>[];
		total?: number;
		message?: string;
	}

	interface Props {
		data?: DataPreviewData | null;
		loading?: boolean;
		hasSource?: boolean;
		workflowId?: string;
	}

	let { data = null, loading = false, hasSource = false, workflowId = '' }: Props = $props();

	const dispatch = createEventDispatcher<{
		fetch: void;
		refresh: void;
	}>();

	// Local state
	let isExpanded = $state(true);
	let expandedRows = $state<Set<number>>(new Set());

	// Derived values
	let columns = $derived(data?.records?.[0] ? Object.keys(data.records[0]) : []);
	let hasData = $derived(data?.records && data.records.length > 0);

	function toggleRowExpand(index: number) {
		const newSet = new Set(expandedRows);
		if (newSet.has(index)) {
			newSet.delete(index);
		} else {
			newSet.add(index);
		}
		expandedRows = newSet;
	}

	function handleFetch() {
		dispatch('fetch');
	}

	function handleRefresh() {
		dispatch('refresh');
	}

	function formatValue(value: unknown): { type: string; display: string; full?: string } {
		if (value === null || value === undefined) {
			return { type: 'null', display: 'null' };
		}
		if (typeof value === 'boolean') {
			return { type: 'boolean', display: String(value) };
		}
		if (typeof value === 'number') {
			return { type: 'number', display: String(value) };
		}
		// Check for audio/image before checking for string/object
		if (isAudio(value)) {
			return { type: 'audio', display: 'Audio' };
		}
		if (isImage(value)) {
			return { type: 'image', display: 'Image' };
		}
		if (typeof value === 'object') {
			const str = JSON.stringify(value);
			return {
				type: 'object',
				display: str.length > 50 ? str.slice(0, 50) + '...' : str,
				full: JSON.stringify(value, null, 2)
			};
		}
		// Check for data URLs
		if (typeof value === 'string' && isDataUrl(value)) {
			return { type: 'dataurl', display: truncateDataUrl(value, 40) };
		}
		const str = String(value);
		return {
			type: 'string',
			display: str.length > 80 ? str.slice(0, 80) + '...' : str,
			full: str.length > 80 ? str : undefined
		};
	}
</script>

<div class="border-2 border-gray-200 dark:border-gray-700 rounded-2xl bg-white dark:bg-gray-900 overflow-hidden">
	<!-- Header -->
	<div
		role="button"
		tabindex="0"
		onclick={() => isExpanded = !isExpanded}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') isExpanded = !isExpanded; }}
		class="w-full flex items-center justify-between px-5 py-4 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-900 hover:from-gray-100 hover:to-gray-50 dark:hover:from-gray-750 dark:hover:to-gray-800 transition-colors cursor-pointer"
	>
		<div class="flex items-center gap-4">
			<div class="p-2.5 rounded-xl bg-gradient-to-br from-[#7661FF]/20 to-[#52B8FF]/20 dark:from-[#7661FF]/30 dark:to-[#52B8FF]/30 shadow-sm">
				<Table2 size={20} class="text-[#7661FF] dark:text-[#BF71F2]" />
			</div>
			<div class="text-left">
				<div class="font-semibold text-gray-900 dark:text-gray-100">
					Sample Data Preview
				</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
					{#if loading}
						Loading data...
					{:else if hasData}
						{columns.length} columns, {data?.records?.length || 0} of {(data?.total ?? data?.records?.length ?? 0).toLocaleString()} rows
					{:else if !hasSource}
						Configure a data source first
					{:else}
						Click to preview sample data
					{/if}
				</div>
			</div>
		</div>
		<div class="flex items-center gap-3">
			{#if isExpanded && hasSource}
				{#if hasData}
					<button
						onclick={(e) => { e.stopPropagation(); handleRefresh(); }}
						disabled={loading}
						class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#7661FF] dark:text-[#52B8FF] bg-[#7661FF]/15 dark:bg-[#7661FF]/20 hover:bg-[#7661FF]/25 dark:hover:bg-[#7661FF]/30 disabled:opacity-50 rounded-lg transition-colors"
					>
						<RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
						Refresh
					</button>
				{:else if !loading}
					<button
						onclick={(e) => { e.stopPropagation(); handleFetch(); }}
						class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-[#7661FF] dark:text-[#52B8FF] bg-[#7661FF]/15 dark:bg-[#7661FF]/20 hover:bg-[#7661FF]/25 dark:hover:bg-[#7661FF]/30 rounded-lg transition-colors"
					>
						<Eye size={14} />
						Preview
					</button>
				{/if}
			{/if}
			<div class="p-1.5 rounded-lg text-gray-400">
				{#if isExpanded}
					<ChevronUp size={18} />
				{:else}
					<ChevronDown size={18} />
				{/if}
			</div>
		</div>
	</div>

	{#if isExpanded}
		<div class="border-t border-gray-100 dark:border-gray-800">
			{#if !hasSource}
				<!-- No Source State -->
				<div class="text-center py-10">
					<div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-700 flex items-center justify-center shadow-sm">
						<Database size={24} class="text-gray-400 dark:text-gray-500" />
					</div>
					<p class="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
						No data source configured
					</p>
					<p class="text-xs text-gray-400 dark:text-gray-500 max-w-xs mx-auto">
						Add a data source to preview sample records from your dataset
					</p>
				</div>

			{:else if loading}
				<!-- Loading State -->
				<div class="flex items-center justify-center gap-3 py-12">
					<Loader2 size={20} class="animate-spin text-[#7661FF]" />
					<span class="text-sm text-gray-500 dark:text-gray-400">Loading sample data...</span>
				</div>

			{:else if data?.message}
				<!-- Message State (warnings, errors) -->
				<div class="p-4 m-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-xl">
					<div class="flex items-start gap-3">
						<AlertCircle size={16} class="text-amber-500 mt-0.5 flex-shrink-0" />
						<p class="text-sm text-amber-700 dark:text-amber-300">{data.message}</p>
					</div>
				</div>

			{:else if hasData}
				<!-- Data Table -->
				<div class="overflow-hidden">
					<!-- Column/Row Stats Bar -->
					<div class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/50 border-b border-gray-100 dark:border-gray-800">
						<div class="flex items-center gap-4">
							<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
								<Columns3 size={12} class="text-blue-500" />
								<span class="font-medium">{columns.length}</span> columns
							</div>
							<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
								<Rows3 size={12} class="text-emerald-500" />
								<span class="font-medium">{data?.records?.length || 0}</span> rows
								{#if data?.total && data.total > (data?.records?.length || 0)}
									<span class="text-gray-400">of {data.total.toLocaleString()}</span>
								{/if}
							</div>
						</div>
						<div class="text-xs text-gray-400 dark:text-gray-500">
							Click row to expand
						</div>
					</div>

					<!-- Table Container -->
					<div class="overflow-auto max-h-80">
						<table class="w-full text-xs">
							<thead class="sticky top-0 bg-gray-100 dark:bg-gray-800 z-10">
								<tr>
									<th class="px-3 py-2.5 text-left font-semibold text-gray-500 dark:text-gray-400 border-b border-r border-gray-200 dark:border-gray-700 w-10 bg-gray-100 dark:bg-gray-800">
										#
									</th>
									{#each columns as col}
										<th class="px-3 py-2.5 text-left font-semibold text-gray-700 dark:text-gray-300 border-b border-r border-gray-200 dark:border-gray-700 whitespace-nowrap bg-gray-100 dark:bg-gray-800">
											{col}
										</th>
									{/each}
								</tr>
							</thead>
							<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
								{#if data?.records}
									{#each data.records as record, i}
										<!-- Main Row -->
										<tr
											class="hover:bg-[#7661FF]/5 dark:hover:bg-[#7661FF]/10 cursor-pointer transition-colors
												{expandedRows.has(i) ? 'bg-[#7661FF]/5 dark:bg-[#7661FF]/10' : ''}"
											onclick={() => toggleRowExpand(i)}
										>
											<td class="px-3 py-2 text-gray-400 border-r border-gray-100 dark:border-gray-800 font-mono text-center">
												<span class="inline-flex items-center gap-1.5">
													<ChevronRight
														size={12}
														class="text-gray-400 transition-transform {expandedRows.has(i) ? 'rotate-90' : ''}"
													/>
													{i + 1}
												</span>
											</td>
											{#each columns as col}
												{@const formatted = formatValue(record[col])}
												<td class="px-3 py-2 border-r border-gray-100 dark:border-gray-800 max-w-[200px]">
													{#if formatted.type === 'null'}
														<span class="text-gray-300 dark:text-gray-600 italic">null</span>
													{:else if formatted.type === 'boolean'}
														<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold
															{record[col] === true ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
															{formatted.display}
														</span>
													{:else if formatted.type === 'number'}
														<span class="font-mono text-[#7661FF] dark:text-[#52B8FF]">{formatted.display}</span>
													{:else if formatted.type === 'audio'}
														<!-- Audio indicator -->
														<span class="inline-flex items-center gap-1.5 px-2 py-1 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 rounded-full text-[10px]">
															<Music size={10} />
															<span>Audio</span>
														</span>
													{:else if formatted.type === 'image'}
														<!-- Image indicator -->
														<span class="inline-flex items-center gap-1.5 px-2 py-1 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-full text-[10px]">
															<ImageIcon size={10} />
															<span>Image</span>
														</span>
													{:else if formatted.type === 'object'}
														<span class="text-gray-500 dark:text-gray-400 font-mono truncate block">{formatted.display}</span>
													{:else if formatted.type === 'dataurl'}
														<span class="text-gray-500 dark:text-gray-400 font-mono truncate block">{formatted.display}</span>
													{:else}
														<span class="text-gray-700 dark:text-gray-300 truncate block">{formatted.display}</span>
													{/if}
												</td>
											{/each}
										</tr>

										<!-- Expanded Row Detail -->
										{#if expandedRows.has(i)}
											<tr class="bg-gray-50/80 dark:bg-gray-800/70">
												<td colspan={columns.length + 1} class="p-0">
													<div class="p-4 space-y-3 border-l-4 border-[#7661FF] dark:border-[#BF71F2] ml-3">
														{#each columns as col}
															{@const value = record[col]}
															{@const formatted = formatValue(value)}
															<div class="flex gap-4">
																<span class="text-xs font-bold text-gray-500 dark:text-gray-400 min-w-[120px] flex-shrink-0 pt-1">
																	{col}
																</span>
																<div class="flex-1 min-w-0">
																	{#if formatted.type === 'audio' || formatted.type === 'image'}
																		<!-- Use MediaRenderer for audio/image content -->
																		<MediaRenderer
																			{value}
																			fieldName={col}
																			{workflowId}
																			compact={false}
																			maxImageHeight="200px"
																		/>
																	{:else if formatted.type === 'null'}
																		<span class="text-xs text-gray-300 dark:text-gray-600 italic">null</span>
																	{:else if formatted.type === 'boolean'}
																		<span class="px-2 py-0.5 rounded text-xs font-semibold
																			{value === true ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
																			{formatted.display}
																		</span>
																	{:else if formatted.type === 'number'}
																		<span class="text-sm font-mono text-[#7661FF] dark:text-[#52B8FF]">{value}</span>
																	{:else if formatted.type === 'object'}
																		<pre class="text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all bg-white dark:bg-gray-900 p-3 rounded-lg border border-gray-200 dark:border-gray-700 max-h-48 overflow-auto">{formatted.full}</pre>
																	{:else}
																		<div class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words bg-white dark:bg-gray-900 p-3 rounded-lg border border-gray-200 dark:border-gray-700 max-h-48 overflow-auto">
																			{formatted.full || formatted.display}
																		</div>
																	{/if}
																</div>
															</div>
														{/each}
													</div>
												</td>
											</tr>
										{/if}
									{/each}
								{/if}
							</tbody>
						</table>
					</div>
				</div>

			{:else}
				<!-- Empty State - No Data Loaded Yet -->
				<div class="text-center py-10">
					<div class="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#7661FF]/20 to-[#52B8FF]/20 dark:from-[#7661FF]/30 dark:to-[#52B8FF]/30 flex items-center justify-center shadow-sm">
						<Eye size={24} class="text-[#7661FF] dark:text-[#BF71F2]" />
					</div>
					<p class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
						Ready to preview data
					</p>
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-4 max-w-xs mx-auto">
						Click the button below to load a sample of records from your data source
					</p>
					<button
						onclick={handleFetch}
						class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[#63DF4E] hover:bg-[#63DF4E]/90 text-[#032D42] rounded-xl transition-colors shadow-sm hover:shadow-md"
					>
						<Eye size={16} />
						Load Preview
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>
