<script lang="ts">
	import { executionStore, uiStore, workflowStore, type Execution } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
	import {
		Search, Filter, RefreshCw, CheckCircle2, XCircle, Clock, Loader2,
		ChevronDown, ArrowUpDown, Calendar, Timer, DollarSign, Zap, X, GitBranch,
		Trash2, CheckSquare, Square, MinusSquare, Ban, BarChart3, Table, GitCompare, Activity
	} from 'lucide-svelte';
	import ConfirmationModal from '../common/ConfirmationModal.svelte';
	import RunsAnalyticsDashboard from './RunsAnalyticsDashboard.svelte';
	import CustomSelect from '../common/CustomSelect.svelte';
	import RunTimelineBar from './RunTimelineBar.svelte';

	let executionHistory = $derived(executionStore.executionHistory);
	let totalExecutions = $derived(executionStore.totalExecutions);
	let hasMoreExecutions = $derived(executionStore.hasMoreExecutions);
	let isLoadingMore = $derived(executionStore.isLoadingMore);
	let workflows = $derived(workflowStore.workflows);
	let selectedRunId = $derived(uiStore.selectedRunId);

	// View mode: 'table' or 'analytics'
	type ViewMode = 'table' | 'analytics' | 'compare';
	let viewMode = $state<ViewMode>('table');

	// Selection state
	let selectedRunIds = $state<Set<string>>(new Set());

	// Confirmation modal state
	let showDeleteConfirm = $state(false);
	let deleteCount = $state(0);

	// Filters
	let searchQuery = $state('');
	let statusFilter = $state<string>('all');
	let workflowFilter = $state<string>('all');
	let dateFilter = $state<string>('all');
	let sortField = $state<'started_at' | 'workflow_name' | 'status' | 'duration_ms'>('started_at');
	let sortDirection = $state<'asc' | 'desc'>('desc');

	// Get unique workflow names from history
	let uniqueWorkflows = $derived(() => {
		const names = new Set<string>();
		executionHistory.forEach(e => {
			if (e.workflow_name) names.add(e.workflow_name);
		});
		return Array.from(names).sort();
	});

	// Workflow filter options
	let workflowOptions = $derived([
		{ value: 'all', label: 'All Workflows' },
		...uniqueWorkflows().map(wf => ({ value: wf, label: wf }))
	]);

	// Status filter options
	const statusOptions = [
		{ value: 'all', label: 'All Status' },
		{ value: 'completed', label: '✓ Completed' },
		{ value: 'running', label: '● Running' },
		{ value: 'failed', label: '✗ Failed' },
		{ value: 'cancelled', label: '◯ Cancelled' },
		{ value: 'pending', label: '○ Pending' }
	];

	// Date filter options
	const dateOptions = [
		{ value: 'all', label: 'All Time' },
		{ value: 'today', label: 'Today' },
		{ value: 'yesterday', label: 'Since Yesterday' },
		{ value: 'week', label: 'Last 7 Days' },
		{ value: 'month', label: 'Last 30 Days' }
	];

	// Check if any filter is active
	let hasActiveFilters = $derived(
		searchQuery !== '' || statusFilter !== 'all' || workflowFilter !== 'all' || dateFilter !== 'all'
	);

	// Status config using design system tokens
	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string }> = {
		pending: { icon: Clock, color: 'text-text-muted', bg: 'bg-surface-tertiary' },
		running: { icon: Loader2, color: 'text-info', bg: 'bg-info-light' },
		completed: { icon: CheckCircle2, color: 'text-success', bg: 'bg-success-light' },
		failed: { icon: XCircle, color: 'text-error', bg: 'bg-error-light' },
		cancelled: { icon: Ban, color: 'text-warning', bg: 'bg-warning-light' }
	};

	// Date filter helper
	function isWithinDateRange(dateStr: string | undefined, range: string): boolean {
		if (!dateStr || range === 'all') return true;
		const date = new Date(dateStr);
		const now = new Date();
		const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

		switch (range) {
			case 'today':
				return date >= today;
			case 'yesterday': {
				const yesterday = new Date(today);
				yesterday.setDate(yesterday.getDate() - 1);
				return date >= yesterday;
			}
			case 'week': {
				const weekAgo = new Date(today);
				weekAgo.setDate(weekAgo.getDate() - 7);
				return date >= weekAgo;
			}
			case 'month': {
				const monthAgo = new Date(today);
				monthAgo.setDate(monthAgo.getDate() - 30);
				return date >= monthAgo;
			}
			default:
				return true;
		}
	}

	// Filtered and sorted runs
	let filteredRuns = $derived(() => {
		let runs = [...executionHistory];

		// Filter by search
		if (searchQuery) {
			const query = searchQuery.toLowerCase();
			runs = runs.filter(r =>
				r.workflow_name?.toLowerCase().includes(query) ||
				r.id.toLowerCase().includes(query)
			);
		}

		// Filter by status
		if (statusFilter !== 'all') {
			runs = runs.filter(r => r.status === statusFilter);
		}

		// Filter by workflow
		if (workflowFilter !== 'all') {
			runs = runs.filter(r => r.workflow_name === workflowFilter);
		}

		// Filter by date
		if (dateFilter !== 'all') {
			runs = runs.filter(r => isWithinDateRange(r.started_at, dateFilter));
		}

		// Sort
		runs.sort((a, b) => {
			let comparison = 0;
			switch (sortField) {
				case 'started_at':
					comparison = new Date(a.started_at || 0).getTime() - new Date(b.started_at || 0).getTime();
					break;
				case 'workflow_name':
					comparison = (a.workflow_name || '').localeCompare(b.workflow_name || '');
					break;
				case 'status':
					comparison = a.status.localeCompare(b.status);
					break;
				case 'duration_ms':
					comparison = (a.duration_ms || 0) - (b.duration_ms || 0);
					break;
			}
			return sortDirection === 'asc' ? comparison : -comparison;
		});

		return runs;
	});

	function clearFilters() {
		searchQuery = '';
		statusFilter = 'all';
		workflowFilter = 'all';
		dateFilter = 'all';
	}

	function selectRun(run: Execution) {
		uiStore.selectRun(run.id);
		// Update URL for browser history
		const url = new URL(window.location.href);
		url.searchParams.set('view', 'runs');
		url.searchParams.set('run', run.id);
		pushState(url.toString(), {});
	}

	function toggleSort(field: typeof sortField) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'desc';
		}
	}

	async function refresh() {
		// Force refresh to detect files added/deleted externally on disk
		await executionStore.loadExecutionHistory(undefined, 50, true);
	}

	async function loadMore() {
		await executionStore.loadMoreExecutions();
	}

	function formatDate(date?: string): string {
		if (!date) return '-';
		return new Date(date).toLocaleDateString([], {
			month: 'short', day: 'numeric', year: 'numeric'
		});
	}

	function formatTime(date?: string): string {
		if (!date) return '';
		return new Date(date).toLocaleTimeString([], {
			hour: '2-digit', minute: '2-digit'
		});
	}

	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const seconds = Math.floor(ms / 1000);
		if (seconds < 60) return `${seconds}s`;
		const minutes = Math.floor(seconds / 60);
		const remainingSeconds = seconds % 60;
		return `${minutes}m ${remainingSeconds}s`;
	}

	function formatCost(metadata: any): string {
		if (!metadata?.aggregate_statistics?.cost?.total_cost_usd) return '-';
		const cost = metadata.aggregate_statistics.cost.total_cost_usd;
		if (cost < 0.01) return `<$0.01`;
		return `$${cost.toFixed(2)}`;
	}

	function formatTokens(metadata: any): string {
		if (!metadata?.aggregate_statistics?.tokens?.total_tokens) return '-';
		const tokens = metadata.aggregate_statistics.tokens.total_tokens;
		if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(1)}M`;
		if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}K`;
		return tokens.toLocaleString();
	}

	// Selection helpers
	let allSelected = $derived(() => {
		const runs = filteredRuns();
		return runs.length > 0 && runs.every(r => selectedRunIds.has(r.id));
	});

	let someSelected = $derived(() => {
		const runs = filteredRuns();
		return runs.some(r => selectedRunIds.has(r.id)) && !allSelected();
	});

	let selectionCount = $derived(selectedRunIds.size);

	function toggleSelectAll() {
		const runs = filteredRuns();
		if (allSelected()) {
			selectedRunIds = new Set();
		} else {
			selectedRunIds = new Set(runs.map(r => r.id));
		}
	}

	function toggleSelectRun(runId: string, e: Event) {
		e.stopPropagation();
		const newSet = new Set(selectedRunIds);
		if (newSet.has(runId)) {
			newSet.delete(runId);
		} else {
			newSet.add(runId);
		}
		selectedRunIds = newSet;
	}

	function clearSelection() {
		selectedRunIds = new Set();
	}

	function requestDeleteSelectedRuns() {
		if (selectedRunIds.size === 0) return;
		deleteCount = selectedRunIds.size;
		showDeleteConfirm = true;
	}

	async function confirmDeleteRuns() {
		const success = await executionStore.removeMultipleFromHistory(Array.from(selectedRunIds));
		if (!success) {
			console.error('Some executions failed to delete');
		}
		selectedRunIds = new Set();
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	function cancelDeleteRuns() {
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	// Get all unique models from selected runs for comparison
	let comparisonModels = $derived(() => {
		const selectedRuns = executionHistory.filter(r => selectedRunIds.has(r.id));
		const models = selectedRuns.flatMap(r => r.metadata?.models ? Object.keys(r.metadata.models) : []);
		return [...new Set(models)];
	});

	// Get selected runs for comparison
	let selectedRunsForComparison = $derived(() => {
		return executionHistory.filter(r => selectedRunIds.has(r.id));
	});
</script>

<div class="h-full w-full flex flex-col bg-surface">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-surface-border px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h1 class="text-2xl font-bold text-text-primary">Runs</h1>
				<p class="text-sm text-text-muted">
					{filteredRuns().length} of {totalExecutions || executionHistory.length} runs
					{#if hasMoreExecutions}
						<span class="text-info"> (more available)</span>
					{/if}
					{#if selectionCount > 0}
						<span class="ml-2 text-info">• {selectionCount} selected</span>
					{/if}
				</p>
			</div>
			<div class="flex items-center gap-2">
				<!-- View Mode Toggle - Icon only, subtle -->
				<div class="flex items-center gap-0.5">
					<button
						onclick={() => viewMode = 'table'}
						class="p-2 rounded-lg transition-colors {viewMode === 'table' ? 'bg-info-light text-info' : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover'}"
						title="List view"
					>
						<Table size={18} />
					</button>
					<button
						onclick={() => viewMode = 'analytics'}
						class="p-2 rounded-lg transition-colors {viewMode === 'analytics' ? 'bg-info-light text-info' : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover'}"
						title="Analytics"
					>
						<BarChart3 size={18} />
					</button>
					{#if selectionCount >= 2}
						<button
							onclick={() => viewMode = 'compare'}
							class="p-2 rounded-lg transition-colors {viewMode === 'compare' ? 'bg-info-light text-info' : 'text-text-muted hover:text-text-secondary hover:bg-surface-hover'}"
							title="Compare {selectionCount} runs"
						>
							<GitCompare size={18} />
						</button>
					{/if}
				</div>

				<div class="w-px h-6 bg-surface-border"></div>

				{#if selectionCount > 0}
					<button
						onclick={clearSelection}
						class="p-2 rounded-lg hover:bg-surface-hover text-text-muted transition-colors"
						title="Clear selection"
					>
						<X size={18} />
					</button>
					<button
						onclick={requestDeleteSelectedRuns}
						class="flex items-center gap-2 px-3 py-2 rounded-lg bg-error-light hover:bg-error/10 text-error transition-colors text-sm font-medium"
						title="Delete selected runs"
					>
						<Trash2 size={16} />
						<span>Delete ({selectionCount})</span>
					</button>
					<div class="w-px h-6 bg-surface-border"></div>
				{/if}
				<button
					onclick={refresh}
					class="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/90 text-brand-primary rounded-lg transition-colors"
				>
					<RefreshCw size={16} />
					Refresh
				</button>
			</div>
		</div>

		<!-- Filters -->
		<div class="flex flex-wrap items-center gap-3">
			<!-- Search -->
			<div class="relative flex-1 min-w-64 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
				<input
					type="text"
					placeholder="Search by workflow name or run ID..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-2 border border-surface-border rounded-lg bg-surface text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-info text-sm"
				/>
			</div>

			<!-- Workflow filter -->
			<CustomSelect
				options={workflowOptions}
				bind:value={workflowFilter}
				placeholder="All Workflows"
				searchable={workflowOptions.length > 5}
				searchPlaceholder="Search workflows..."
				class="w-44"
			/>

			<!-- Status filter -->
			<CustomSelect
				options={statusOptions}
				bind:value={statusFilter}
				placeholder="All Status"
				searchable={false}
				class="w-36"
			/>

			<!-- Date filter -->
			<CustomSelect
				options={dateOptions}
				bind:value={dateFilter}
				placeholder="All Time"
				searchable={false}
				class="w-40"
			/>

			<!-- Clear filters -->
			{#if hasActiveFilters}
				<button
					onclick={clearFilters}
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-hover rounded-lg transition-colors"
				>
					<X size={14} />
					Clear filters
				</button>
			{/if}
		</div>

		<!-- Active filter tags -->
		{#if hasActiveFilters}
			<div class="flex flex-wrap items-center gap-2 mt-3">
				{#if statusFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-info-light text-info">
						Status: {statusFilter}
						<button onclick={() => statusFilter = 'all'} class="hover:opacity-70">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if workflowFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-info-light text-info">
						Workflow: {workflowFilter}
						<button onclick={() => workflowFilter = 'all'} class="hover:opacity-70">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if dateFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-warning-light text-warning">
						Date: {dateFilter === 'today' ? 'Today' : dateFilter === 'yesterday' ? 'Since Yesterday' : dateFilter === 'week' ? 'Last 7 Days' : 'Last 30 Days'}
						<button onclick={() => dateFilter = 'all'} class="hover:opacity-70">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if searchQuery}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-surface-secondary text-text-secondary">
						Search: "{searchQuery}"
						<button onclick={() => searchQuery = ''} class="hover:text-text-primary">
							<X size={12} />
						</button>
					</span>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Content based on view mode -->
	{#if viewMode === 'analytics'}
		<!-- Analytics Dashboard -->
		<div class="flex-1 overflow-auto p-6">
			<RunsAnalyticsDashboard runs={filteredRuns()} totalRuns={executionHistory.length} />
		</div>
	{:else if viewMode === 'compare' && selectionCount >= 2}
		<!-- Run Comparison View -->
		<div class="flex-1 overflow-auto p-6">
			<div class="space-y-6">
				<h2 class="text-lg font-semibold text-text-primary flex items-center gap-2">
					<GitCompare size={20} class="text-info" />
					Comparing {selectionCount} Runs
				</h2>

				<!-- Comparison Table -->
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-surface-border">
								<th class="text-left py-3 px-4 font-semibold text-text-secondary">Metric</th>
								{#each selectedRunsForComparison() as run}
									<th class="text-left py-3 px-4 font-medium text-text-primary">
										{run.workflow_name || run.id.slice(0, 8)}
									</th>
								{/each}
							</tr>
						</thead>
						<tbody>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Status</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4">
										<span class="px-2 py-1 rounded-full text-xs font-medium {run.status === 'completed' ? 'bg-success-light text-status-completed' : run.status === 'failed' ? 'bg-error-light text-error' : 'bg-surface-secondary text-text-secondary'}">
											{run.status}
										</span>
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Duration</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4 font-mono text-text-primary">
										{run.duration_ms ? formatDuration(run.duration_ms) : '-'}
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Total Tokens</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4 font-mono text-info">
										{formatTokens(run.metadata)}
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Cost</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4 font-mono text-status-completed">
										{formatCost(run.metadata)}
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Records Processed</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4 text-text-primary">
										{run.metadata?.aggregate_statistics?.records?.total_processed?.toLocaleString() || '-'}
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Success Rate</td>
								{#each selectedRunsForComparison() as run}
									{@const rate = run.metadata?.aggregate_statistics?.records?.success_rate}
									<td class="py-3 px-4">
										{#if rate !== undefined}
											<span class="font-medium {rate >= 0.9 ? 'text-status-completed' : rate >= 0.7 ? 'text-warning' : 'text-error'}">
												{(rate * 100).toFixed(1)}%
											</span>
										{:else}
											<span class="text-text-muted">-</span>
										{/if}
									</td>
								{/each}
							</tr>
							<tr class="border-b border-surface-border/50">
								<td class="py-3 px-4 text-text-secondary">Models Used</td>
								{#each selectedRunsForComparison() as run}
									<td class="py-3 px-4">
										{#if run.metadata?.models}
											<div class="flex flex-wrap gap-1">
												{#each Object.keys(run.metadata.models) as model}
													<span class="text-xs px-2 py-0.5 rounded bg-info-light text-info">
														{model}
													</span>
												{/each}
											</div>
										{:else}
											<span class="text-text-muted">-</span>
										{/if}
									</td>
								{/each}
							</tr>
						</tbody>
					</table>
				</div>

				<!-- Per-Model Comparison if metadata available -->
				{#if comparisonModels().length > 0}
					<div class="bg-surface-secondary rounded-xl p-4">
						<h3 class="text-sm font-semibold text-text-secondary mb-4">Model Performance Comparison</h3>
						<table class="w-full text-sm">
							<thead>
								<tr class="border-b border-surface-border">
									<th class="text-left py-2 px-3 text-xs text-text-muted uppercase">Model</th>
									{#each selectedRunsForComparison() as run}
										<th class="text-left py-2 px-3 text-xs text-text-muted uppercase">{run.workflow_name?.slice(0, 12) || run.id.slice(0, 8)}</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each comparisonModels() as modelName}
									<tr class="border-b border-surface-border/50">
										<td class="py-2 px-3 font-medium text-text-secondary">{modelName}</td>
										{#each selectedRunsForComparison() as run}
											{@const model = run.metadata?.models?.[modelName]}
											<td class="py-2 px-3">
												{#if model}
													<div class="space-y-1 text-xs">
														<div class="text-info">{model.token_statistics?.total_tokens?.toLocaleString() || 0} tokens</div>
														<div class="text-warning">{(model.performance?.average_latency_seconds * 1000).toFixed(0)}ms avg</div>
														<div class="text-status-completed">${model.cost?.total_cost_usd?.toFixed(4) || '0'}</div>
													</div>
												{:else}
													<span class="text-text-muted">-</span>
												{/if}
											</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<!-- Table View -->
		<div class="flex-1 overflow-auto">
			<table class="w-full">
			<thead class="sticky top-0 bg-surface-secondary border-b border-surface-border">
				<tr>
					<th class="text-left px-4 py-3 w-12">
						<button
							onclick={toggleSelectAll}
							class="p-1 rounded hover:bg-surface-hover text-text-muted transition-colors"
							title={allSelected() ? 'Deselect all' : 'Select all'}
						>
							{#if allSelected()}
								<CheckSquare size={18} class="text-info" />
							{:else if someSelected()}
								<MinusSquare size={18} class="text-info" />
							{:else}
								<Square size={18} />
							{/if}
						</button>
					</th>
					<th class="text-left px-4 py-3">
						<button
							onclick={() => toggleSort('workflow_name')}
							class="flex items-center gap-1 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-secondary"
						>
							Workflow
							<ArrowUpDown size={14} class={sortField === 'workflow_name' ? 'text-info' : ''} />
						</button>
					</th>
					<th class="text-left px-6 py-3">
						<button
							onclick={() => toggleSort('status')}
							class="flex items-center gap-1 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-secondary"
						>
							Status
							<ArrowUpDown size={14} class={sortField === 'status' ? 'text-info' : ''} />
						</button>
					</th>
					<th class="text-left px-6 py-3">
						<button
							onclick={() => toggleSort('started_at')}
							class="flex items-center gap-1 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-secondary"
						>
							Started
							<ArrowUpDown size={14} class={sortField === 'started_at' ? 'text-info' : ''} />
						</button>
					</th>
					<th class="text-left px-6 py-3">
						<button
							onclick={() => toggleSort('duration_ms')}
							class="flex items-center gap-1 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-secondary"
						>
							Duration
							<ArrowUpDown size={14} class={sortField === 'duration_ms' ? 'text-info' : ''} />
						</button>
					</th>
					<th class="text-left px-6 py-3 min-w-[120px]">
						<span class="flex items-center gap-1 text-xs font-semibold text-text-muted uppercase tracking-wider">
							<Activity size={12} />
							Timeline
						</span>
					</th>
					<th class="text-left px-6 py-3">
						<span class="text-xs font-semibold text-text-muted uppercase tracking-wider">
							Tokens
						</span>
					</th>
					<th class="text-left px-6 py-3">
						<span class="text-xs font-semibold text-text-muted uppercase tracking-wider">
							Cost
						</span>
					</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-surface-border">
				{#each filteredRuns() as run (run.id)}
					{@const status = statusConfig[run.status] || statusConfig.pending}
					{@const StatusIcon = status.icon}
					{@const isSelected = selectedRunIds.has(run.id)}
					<tr
						onclick={() => selectRun(run)}
						class="cursor-pointer transition-colors {isSelected ? 'bg-info-light' : selectedRunId === run.id ? 'bg-info-light/50' : 'hover:bg-surface-hover'}"
					>
						<td class="px-4 py-4">
							<button
								onclick={(e) => toggleSelectRun(run.id, e)}
								class="p-1 rounded hover:bg-surface-hover transition-colors"
							>
								{#if isSelected}
									<CheckSquare size={18} class="text-info" />
								{:else}
									<Square size={18} class="text-text-muted" />
								{/if}
							</button>
						</td>
						<td class="px-4 py-4">
							<div class="flex flex-col">
								<span class="font-medium text-text-primary">
									{run.workflow_name || 'Unknown Workflow'}
								</span>
								<span class="text-xs text-text-muted font-mono">
									{run.id.slice(0, 8)}...
								</span>
							</div>
						</td>
						<td class="px-6 py-4">
							<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {status.color} {status.bg}">
								<StatusIcon size={12} class={run.status === 'running' ? 'animate-spin' : ''} />
								{run.status}
							</span>
						</td>
						<td class="px-6 py-4">
							<div class="flex flex-col">
								<span class="text-sm text-text-primary">
									{formatDate(run.started_at)}
								</span>
								<span class="text-xs text-text-muted">
									{formatTime(run.started_at)}
								</span>
							</div>
						</td>
						<td class="px-6 py-4">
							<span class="text-sm text-text-primary flex items-center gap-1">
								<Timer size={14} class="text-text-muted" />
								{formatDuration(run.duration_ms)}
							</span>
						</td>
						<td class="px-6 py-4">
							{#if run.node_states && Object.keys(run.node_states).length > 0}
								<div class="min-w-[100px]">
									<RunTimelineBar
										nodeStates={run.node_states}
										totalDuration={run.duration_ms}
									/>
								</div>
							{:else}
								<span class="text-xs text-text-muted">-</span>
							{/if}
						</td>
						<td class="px-6 py-4">
							<span class="text-sm text-text-primary flex items-center gap-1">
								<Zap size={14} class="text-info" />
								{formatTokens(run.metadata)}
							</span>
						</td>
						<td class="px-6 py-4">
							<span class="text-sm text-text-primary flex items-center gap-1">
								<DollarSign size={14} class="text-status-completed" />
								{formatCost(run.metadata)}
							</span>
						</td>
					</tr>
				{:else}
					<tr>
						<td colspan="8" class="px-6 py-12 text-center">
							<div class="text-text-muted">
								{#if searchQuery || statusFilter !== 'all'}
									<p class="text-lg font-medium mb-1">No matching runs</p>
									<p class="text-sm">Try adjusting your filters</p>
								{:else}
									<p class="text-lg font-medium mb-1">No runs yet</p>
									<p class="text-sm">Execute a workflow to see runs here</p>
								{/if}
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<!-- Load More Button -->
		{#if hasMoreExecutions}
			<div class="flex justify-center py-4 border-t border-surface-border bg-surface-secondary">
				<button
					onclick={loadMore}
					disabled={isLoadingMore}
					class="flex items-center gap-2 px-6 py-2 bg-surface border border-surface-border rounded-lg text-sm font-medium text-text-secondary hover:bg-surface-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
				>
					{#if isLoadingMore}
						<Loader2 size={16} class="animate-spin" />
						Loading...
					{:else}
						<ChevronDown size={16} />
						Load More ({totalExecutions - executionHistory.length} remaining)
					{/if}
				</button>
			</div>
		{/if}
		</div>
	{/if}
</div>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmationModal
		title="Delete {deleteCount} Run{deleteCount > 1 ? 's' : ''}"
		message="Are you sure you want to delete {deleteCount} selected run{deleteCount > 1 ? 's' : ''}? This action cannot be undone."
		confirmText="Delete"
		cancelText="Cancel"
		variant="danger"
		icon="trash"
		on:confirm={confirmDeleteRuns}
		on:cancel={cancelDeleteRuns}
	/>
{/if}
