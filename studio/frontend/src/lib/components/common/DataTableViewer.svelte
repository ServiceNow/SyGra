<script lang="ts">
	import { Database, ChevronDown, ChevronRight, Table, Code, Loader2, AlertCircle, Search, ChevronLeft, ChevronsLeft, ChevronsRight } from 'lucide-svelte';

	interface Props {
		data: unknown[] | null;
		title?: string;
		total?: number | string | null;
		maxRecords?: number;
		loading?: boolean;
		error?: string | null;
		showViewToggle?: boolean;
		defaultView?: 'table' | 'json';
		compact?: boolean;
	}

	let {
		data = null,
		title = 'Data',
		total = null,
		maxRecords = 20,
		loading = false,
		error = null,
		showViewToggle = true,
		defaultView = 'table',
		compact = false
	}: Props = $props();

	// View state
	let viewMode = $state<'table' | 'json'>(defaultView);
	let expandedRows = $state<Set<number>>(new Set());
	let searchQuery = $state('');
	let currentPage = $state(0);

	// Pagination
	let pageSize = $derived(maxRecords);

	// Filtered and paginated data
	let filteredData = $derived(() => {
		if (!data || !Array.isArray(data)) return [];
		if (!searchQuery.trim()) return data;

		const query = searchQuery.toLowerCase();
		return data.filter(record => {
			if (typeof record === 'object' && record !== null) {
				return Object.values(record).some(val =>
					String(val).toLowerCase().includes(query)
				);
			}
			return String(record).toLowerCase().includes(query);
		});
	});

	let totalPages = $derived(Math.ceil(filteredData().length / pageSize));

	let paginatedData = $derived(() => {
		const start = currentPage * pageSize;
		return filteredData().slice(start, start + pageSize);
	});

	// Get columns from first record
	let columns = $derived(() => {
		if (!data || !Array.isArray(data) || data.length === 0) return [];
		const firstRecord = data[0];
		if (typeof firstRecord === 'object' && firstRecord !== null) {
			return Object.keys(firstRecord);
		}
		return ['value'];
	});

	// Display count
	let displayCount = $derived(() => {
		const filtered = filteredData().length;
		const totalCount = total ?? data?.length ?? 0;
		const showing = paginatedData().length;

		if (searchQuery.trim()) {
			return `${showing} of ${filtered} filtered (${totalCount} total)`;
		}
		if (typeof totalCount === 'number') {
			return `${showing} of ${totalCount.toLocaleString()}`;
		}
		return `${showing} records`;
	});

	function toggleRowExpand(index: number) {
		const actualIndex = currentPage * pageSize + index;
		if (expandedRows.has(actualIndex)) {
			expandedRows.delete(actualIndex);
		} else {
			expandedRows.add(actualIndex);
		}
		expandedRows = new Set(expandedRows);
	}

	function isExpanded(index: number): boolean {
		return expandedRows.has(currentPage * pageSize + index);
	}

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return 'null';
		if (typeof value === 'object') return JSON.stringify(value, null, 2);
		return String(value);
	}

	function goToPage(page: number) {
		currentPage = Math.max(0, Math.min(page, totalPages - 1));
	}
</script>

<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
	<!-- Header -->
	<div class="bg-gray-50 dark:bg-gray-800 px-4 py-3 border-b border-gray-200 dark:border-gray-700">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<Database size={16} class="text-[#7661FF]" />
				<span class="font-medium text-gray-700 dark:text-gray-300">{title}</span>
				{#if columns().length > 0}
					<span class="text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-700 px-2 py-0.5 rounded">
						{columns().length} columns
					</span>
				{/if}
			</div>

			<div class="flex items-center gap-3">
				<!-- Search -->
				{#if data && data.length > 5}
					<div class="relative">
						<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search..."
							class="pl-8 pr-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 placeholder-gray-400 focus:ring-2 focus:ring-[#52B8FF]/40 focus:border-[#52B8FF] w-48"
						/>
					</div>
				{/if}

				<!-- View Toggle -->
				{#if showViewToggle}
					<div class="flex items-center bg-gray-200 dark:bg-gray-700 rounded-lg p-0.5">
						<button
							onclick={() => viewMode = 'table'}
							class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors {viewMode === 'table' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-200 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
						>
							<Table size={12} />
							Table
						</button>
						<button
							onclick={() => viewMode = 'json'}
							class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md transition-colors {viewMode === 'json' ? 'bg-white dark:bg-gray-600 text-gray-800 dark:text-gray-200 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
						>
							<Code size={12} />
							JSON
						</button>
					</div>
				{/if}

				<!-- Record Count -->
				<span class="text-xs text-gray-500 dark:text-gray-400">
					{displayCount()}
				</span>
			</div>
		</div>
	</div>

	<!-- Content -->
	<div class="relative">
		{#if loading}
			<div class="flex items-center justify-center py-12">
				<Loader2 size={24} class="animate-spin text-[#7661FF]" />
				<span class="ml-2 text-sm text-gray-500">Loading data...</span>
			</div>
		{:else if error}
			<div class="flex items-center gap-2 p-4 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300">
				<AlertCircle size={16} />
				<span class="text-sm">{error}</span>
			</div>
		{:else if !data || data.length === 0}
			<div class="text-center py-12 text-gray-500">
				<Database size={32} class="mx-auto mb-3 opacity-40" />
				<p class="text-sm">No data available</p>
			</div>
		{:else if viewMode === 'json'}
			<!-- JSON View -->
			<div class="max-h-[500px] overflow-auto">
				<pre class="p-4 text-xs font-mono text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{JSON.stringify(paginatedData(), null, 2)}</pre>
			</div>
		{:else}
			<!-- Table View -->
			<div class="overflow-auto max-h-[500px]">
				<table class="w-full text-sm">
					<thead class="sticky top-0 bg-gray-100 dark:bg-gray-800 z-10">
						<tr>
							<th class="px-3 py-2 text-left font-medium text-gray-500 dark:text-gray-400 border-b border-r border-gray-200 dark:border-gray-700 w-12">#</th>
							{#each columns() as col}
								<th class="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300 border-b border-r border-gray-200 dark:border-gray-700 whitespace-nowrap">
									{col}
								</th>
							{/each}
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
						{#each paginatedData() as record, i}
							{@const rowIndex = currentPage * pageSize + i + 1}
							<!-- Compact row -->
							<tr
								class="hover:bg-blue-50 dark:hover:bg-blue-900/20 cursor-pointer transition-colors {isExpanded(i) ? 'bg-blue-50 dark:bg-blue-900/20' : ''}"
								onclick={() => toggleRowExpand(i)}
							>
								<td class="px-3 py-2 text-gray-400 border-r border-gray-100 dark:border-gray-800 font-mono text-xs">
									<span class="inline-flex items-center gap-1.5">
										<span class="text-gray-300 dark:text-gray-600 transition-transform {isExpanded(i) ? 'rotate-90' : ''}">
											<ChevronRight size={12} />
										</span>
										{rowIndex}
									</span>
								</td>
								{#each columns() as col}
									{@const value = typeof record === 'object' && record !== null ? (record as Record<string, unknown>)[col] : record}
									<td class="px-3 py-2 border-r border-gray-100 dark:border-gray-800 max-w-xs">
										{#if value === null || value === undefined}
											<span class="text-gray-300 dark:text-gray-600 italic text-xs">null</span>
										{:else if typeof value === 'boolean'}
											<span class="px-1.5 py-0.5 rounded text-xs font-medium {value ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
												{value}
											</span>
										{:else if typeof value === 'number'}
											<span class="font-mono text-blue-600 dark:text-blue-400 text-xs">{value.toLocaleString()}</span>
										{:else if typeof value === 'object'}
											<span class="text-gray-500 dark:text-gray-400 font-mono text-xs truncate block max-w-[250px]">
												{JSON.stringify(value).slice(0, 60)}{JSON.stringify(value).length > 60 ? '...' : ''}
											</span>
										{:else}
											<span class="text-gray-700 dark:text-gray-300 text-xs truncate block max-w-[250px]">
												{String(value).slice(0, 100)}{String(value).length > 100 ? '...' : ''}
											</span>
										{/if}
									</td>
								{/each}
							</tr>
							<!-- Expanded row detail -->
							{#if isExpanded(i)}
								<tr class="bg-gray-50 dark:bg-gray-800/70">
									<td colspan={columns().length + 1} class="p-0">
										<div class="p-4 space-y-3 border-l-4 border-[#7661FF] dark:border-[#BF71F2] ml-3">
											{#each columns() as col}
												{@const value = typeof record === 'object' && record !== null ? (record as Record<string, unknown>)[col] : record}
												<div class="flex gap-4">
													<span class="text-xs font-semibold text-gray-500 dark:text-gray-400 min-w-[120px] flex-shrink-0 pt-0.5">
														{col}
													</span>
													<div class="flex-1 min-w-0">
														{#if value === null || value === undefined}
															<span class="text-xs text-gray-300 dark:text-gray-600 italic">null</span>
														{:else if typeof value === 'boolean'}
															<span class="px-2 py-0.5 rounded text-xs font-medium {value ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
																{value}
															</span>
														{:else if typeof value === 'number'}
															<span class="text-sm font-mono text-blue-600 dark:text-blue-400">{value.toLocaleString()}</span>
														{:else if typeof value === 'object'}
															<pre class="text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all bg-white dark:bg-gray-900 p-3 rounded-lg border border-gray-200 dark:border-gray-700 max-h-48 overflow-auto">{JSON.stringify(value, null, 2)}</pre>
														{:else}
															<div class="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words bg-white dark:bg-gray-900 p-3 rounded-lg border border-gray-200 dark:border-gray-700 max-h-48 overflow-auto">
																{String(value)}
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
					</tbody>
				</table>
			</div>

			<!-- Column list (collapsed) -->
			{#if columns().length > 5}
				<details class="border-t border-gray-200 dark:border-gray-700">
					<summary class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50">
						View all {columns().length} columns
					</summary>
					<div class="px-4 py-3 flex flex-wrap gap-2 bg-gray-50 dark:bg-gray-800/50">
						{#each columns() as col}
							<span class="px-2 py-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded text-xs font-mono text-gray-600 dark:text-gray-300">
								{col}
							</span>
						{/each}
					</div>
				</details>
			{/if}
		{/if}
	</div>

	<!-- Pagination -->
	{#if totalPages > 1 && !loading}
		<div class="flex items-center justify-between px-4 py-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
			<div class="text-xs text-gray-500 dark:text-gray-400">
				Page {currentPage + 1} of {totalPages}
			</div>
			<div class="flex items-center gap-1">
				<button
					onclick={() => goToPage(0)}
					disabled={currentPage === 0}
					class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
					title="First page"
				>
					<ChevronsLeft size={14} class="text-gray-600 dark:text-gray-400" />
				</button>
				<button
					onclick={() => goToPage(currentPage - 1)}
					disabled={currentPage === 0}
					class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
					title="Previous page"
				>
					<ChevronLeft size={14} class="text-gray-600 dark:text-gray-400" />
				</button>

				<!-- Page numbers -->
				{#each Array(Math.min(5, totalPages)) as _, idx}
					{@const pageNum = totalPages <= 5 ? idx : Math.max(0, Math.min(currentPage - 2, totalPages - 5)) + idx}
					{#if pageNum < totalPages}
						<button
							onclick={() => goToPage(pageNum)}
							class="w-7 h-7 text-xs rounded transition-colors {currentPage === pageNum ? 'bg-[#7661FF] text-white' : 'text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}"
						>
							{pageNum + 1}
						</button>
					{/if}
				{/each}

				<button
					onclick={() => goToPage(currentPage + 1)}
					disabled={currentPage >= totalPages - 1}
					class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
					title="Next page"
				>
					<ChevronRight size={14} class="text-gray-600 dark:text-gray-400" />
				</button>
				<button
					onclick={() => goToPage(totalPages - 1)}
					disabled={currentPage >= totalPages - 1}
					class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
					title="Last page"
				>
					<ChevronsRight size={14} class="text-gray-600 dark:text-gray-400" />
				</button>
			</div>
		</div>
	{/if}
</div>
