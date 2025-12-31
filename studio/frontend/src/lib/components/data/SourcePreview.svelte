<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		Eye, RefreshCw, Loader2, ChevronRight, Columns3, Rows3,
		AlertCircle, Table2
	} from 'lucide-svelte';

	interface PreviewData {
		records: Record<string, unknown>[];
		total?: number | string;
		message?: string;
		source_type?: string;
	}

	interface Props {
		data?: PreviewData | null;
		loading?: boolean;
		sourceIndex: number;
		sourceAlias?: string;
	}

	let { data = null, loading = false, sourceIndex, sourceAlias }: Props = $props();

	const dispatch = createEventDispatcher<{
		fetch: { index: number };
		refresh: { index: number };
	}>();

	// Local state
	let expandedRows = $state<Set<number>>(new Set());

	// Derived values
	let columns = $derived(data?.records?.[0] ? Object.keys(data.records[0]) : []);
	let hasData = $derived(data?.records && data.records.length > 0);
	let totalDisplay = $derived(() => {
		if (!data?.total) return null;
		if (typeof data.total === 'number') return data.total.toLocaleString();
		return data.total;
	});

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
		dispatch('fetch', { index: sourceIndex });
	}

	function handleRefresh() {
		dispatch('refresh', { index: sourceIndex });
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
		if (typeof value === 'object') {
			const str = JSON.stringify(value);
			return {
				type: 'object',
				display: str.length > 40 ? str.slice(0, 40) + '...' : str,
				full: JSON.stringify(value, null, 2)
			};
		}
		const str = String(value);
		return {
			type: 'string',
			display: str.length > 60 ? str.slice(0, 60) + '...' : str,
			full: str.length > 60 ? str : undefined
		};
	}
</script>

<div class="border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-800/30">
	{#if loading}
		<!-- Loading State -->
		<div class="flex items-center justify-center gap-2 py-6">
			<Loader2 size={16} class="animate-spin text-blue-500" />
			<span class="text-xs text-gray-500 dark:text-gray-400">Loading preview...</span>
		</div>

	{:else if data?.message && !hasData}
		<!-- Message/Error State -->
		<div class="p-3">
			<div class="flex items-start gap-2 p-2.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
				<AlertCircle size={14} class="text-amber-500 mt-0.5 flex-shrink-0" />
				<p class="text-xs text-amber-700 dark:text-amber-300">{data.message}</p>
			</div>
		</div>

	{:else if hasData}
		<!-- Data Table -->
		<div class="overflow-hidden">
			<!-- Stats Bar -->
			<div class="flex items-center justify-between px-3 py-2 bg-gray-100/50 dark:bg-gray-800/50 border-b border-gray-100 dark:border-gray-700">
				<div class="flex items-center gap-3">
					<div class="flex items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400">
						<Columns3 size={10} class="text-blue-500" />
						<span class="font-medium">{columns.length}</span> cols
					</div>
					<div class="flex items-center gap-1 text-[10px] text-gray-500 dark:text-gray-400">
						<Rows3 size={10} class="text-emerald-500" />
						<span class="font-medium">{data?.records?.length || 0}</span>
						{#if totalDisplay()}
							<span class="text-gray-400">of {totalDisplay()}</span>
						{/if}
					</div>
				</div>
				<button
					onclick={handleRefresh}
					class="flex items-center gap-1 px-1.5 py-0.5 text-[10px] text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
				>
					<RefreshCw size={10} />
					Refresh
				</button>
			</div>

			<!-- Table -->
			<div class="overflow-auto max-h-64">
				<table class="w-full text-xs">
					<thead class="sticky top-0 bg-gray-100 dark:bg-gray-800 z-10">
						<tr>
							<th class="px-2 py-1.5 text-left text-[10px] font-semibold text-gray-500 dark:text-gray-400 border-b border-r border-gray-200 dark:border-gray-700 w-8 bg-gray-100 dark:bg-gray-800">
								#
							</th>
							{#each columns as col}
								<th class="px-2 py-1.5 text-left text-[10px] font-semibold text-gray-700 dark:text-gray-300 border-b border-r border-gray-200 dark:border-gray-700 whitespace-nowrap bg-gray-100 dark:bg-gray-800 max-w-[150px] truncate">
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
									class="hover:bg-blue-50/50 dark:hover:bg-blue-900/10 cursor-pointer transition-colors
										{expandedRows.has(i) ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
									onclick={() => toggleRowExpand(i)}
								>
									<td class="px-2 py-1.5 text-[10px] text-gray-400 border-r border-gray-100 dark:border-gray-800 font-mono text-center">
										<span class="inline-flex items-center gap-1">
											<ChevronRight
												size={10}
												class="text-gray-400 transition-transform {expandedRows.has(i) ? 'rotate-90' : ''}"
											/>
											{i + 1}
										</span>
									</td>
									{#each columns as col}
										{@const formatted = formatValue(record[col])}
										<td class="px-2 py-1.5 border-r border-gray-100 dark:border-gray-800 max-w-[150px]">
											{#if formatted.type === 'null'}
												<span class="text-gray-300 dark:text-gray-600 italic text-[10px]">null</span>
											{:else if formatted.type === 'boolean'}
												<span class="px-1 py-0.5 rounded text-[9px] font-semibold
													{record[col] === true ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
													{formatted.display}
												</span>
											{:else if formatted.type === 'number'}
												<span class="font-mono text-[10px] text-violet-600 dark:text-violet-400">{formatted.display}</span>
											{:else if formatted.type === 'object'}
												<span class="text-[10px] text-gray-500 dark:text-gray-400 font-mono truncate block">{formatted.display}</span>
											{:else}
												<span class="text-[10px] text-gray-700 dark:text-gray-300 truncate block">{formatted.display}</span>
											{/if}
										</td>
									{/each}
								</tr>

								<!-- Expanded Row Detail -->
								{#if expandedRows.has(i)}
									<tr class="bg-gray-50/80 dark:bg-gray-800/70">
										<td colspan={columns.length + 1} class="p-0">
											<div class="p-3 space-y-2 border-l-3 border-blue-400 dark:border-blue-500 ml-2">
												{#each columns as col}
													{@const value = record[col]}
													{@const formatted = formatValue(value)}
													<div class="flex gap-3">
														<span class="text-[10px] font-bold text-gray-500 dark:text-gray-400 min-w-[100px] flex-shrink-0 pt-0.5">
															{col}
														</span>
														<div class="flex-1 min-w-0">
															{#if formatted.type === 'null'}
																<span class="text-[10px] text-gray-300 dark:text-gray-600 italic">null</span>
															{:else if formatted.type === 'boolean'}
																<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold
																	{value === true ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
																	{formatted.display}
																</span>
															{:else if formatted.type === 'number'}
																<span class="text-xs font-mono text-violet-600 dark:text-violet-400">{value}</span>
															{:else if formatted.type === 'object'}
																<pre class="text-[10px] font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-32 overflow-auto">{formatted.full}</pre>
															{:else}
																<div class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-32 overflow-auto">
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
		<!-- Empty State - Ready to Preview -->
		<div class="text-center py-5">
			<div class="w-10 h-10 mx-auto mb-2 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 flex items-center justify-center">
				<Table2 size={18} class="text-blue-500 dark:text-blue-400" />
			</div>
			<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
				Preview sample records from this source
			</p>
			<button
				onclick={handleFetch}
				class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
			>
				<Eye size={14} />
				Load Preview
			</button>
		</div>
	{/if}
</div>
