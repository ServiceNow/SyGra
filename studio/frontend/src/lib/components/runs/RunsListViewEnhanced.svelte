<script lang="ts">
	import { executionStore, uiStore, workflowStore, type Execution } from '$lib/stores/workflow.svelte';
	import {
		Search, RefreshCw, CheckCircle2, XCircle, Clock, Loader2,
		ChevronDown, ArrowUpDown, Calendar, Timer, DollarSign, Zap, X, GitBranch,
		Trash2, CheckSquare, Square, MinusSquare, Ban, BarChart3, Table, GitCompare,
		LayoutGrid, Download, Star, StarOff, ChevronRight, Filter, SlidersHorizontal,
		Play, MoreHorizontal, Eye, Copy, FileJson, ArrowRight, TrendingUp, Gauge,
		Activity, Clock3
	} from 'lucide-svelte';
	import ConfirmationModal from '../common/ConfirmationModal.svelte';
	import RunsAnalyticsDashboard from './RunsAnalyticsDashboardEnhanced.svelte';
	import CustomSelect from '../common/CustomSelect.svelte';
	import RunTimelineBar from './RunTimelineBar.svelte';
	import RunQuickStats from './RunQuickStats.svelte';
	import RunCard from './RunCard.svelte';
	import RunComparisonView from './RunComparisonView.svelte';

	let executionHistory = $derived(executionStore.executionHistory);
	let workflows = $derived(workflowStore.workflows);
	let selectedRunId = $derived(uiStore.selectedRunId);

	// View mode: 'table', 'cards', 'analytics', 'compare'
	type ViewMode = 'table' | 'cards' | 'analytics' | 'compare';
	let viewMode = $state<ViewMode>('table');

	// Initialize view mode from localStorage
	$effect(() => {
		const saved = localStorage.getItem('sygra-runs-view-mode');
		if (saved && ['table', 'cards', 'analytics'].includes(saved)) {
			viewMode = saved as ViewMode;
		}
	});

	// Save view mode to localStorage (only for table/cards)
	function setViewMode(mode: ViewMode) {
		viewMode = mode;
		if (mode === 'table' || mode === 'cards') {
			localStorage.setItem('sygra-runs-view-mode', mode);
		}
	}

	// Selection state
	let selectedRunIds = $state<Set<string>>(new Set());

	// Pinned runs (stored in localStorage)
	let pinnedRunIds = $state<Set<string>>(new Set());

	// Expanded rows in table view
	let expandedRowIds = $state<Set<string>>(new Set());

	// Confirmation modal state
	let showDeleteConfirm = $state(false);
	let deleteCount = $state(0);

	// Filter panel expanded
	let showAdvancedFilters = $state(false);

	// Filters
	let searchQuery = $state('');
	let statusFilter = $state<string>('all');
	let workflowFilter = $state<string>('all');
	let dateFilter = $state<string>('all');
	let sortField = $state<'started_at' | 'workflow_name' | 'status' | 'duration_ms' | 'tokens' | 'cost'>('started_at');
	let sortDirection = $state<'asc' | 'desc'>('desc');
	let showPinnedOnly = $state(false);

	// Initialize pinned runs from localStorage
	$effect(() => {
		const saved = localStorage.getItem('sygra-pinned-runs');
		if (saved) {
			try {
				pinnedRunIds = new Set(JSON.parse(saved));
			} catch {}
		}
	});

	// Save pinned runs to localStorage
	function savePinnedRuns() {
		localStorage.setItem('sygra-pinned-runs', JSON.stringify([...pinnedRunIds]));
	}

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
		{ value: 'hour', label: 'Last Hour' },
		{ value: 'today', label: 'Today' },
		{ value: 'yesterday', label: 'Since Yesterday' },
		{ value: 'week', label: 'Last 7 Days' },
		{ value: 'month', label: 'Last 30 Days' }
	];

	// Check if any filter is active
	let hasActiveFilters = $derived(
		searchQuery !== '' || statusFilter !== 'all' || workflowFilter !== 'all' || dateFilter !== 'all' || showPinnedOnly
	);

	let activeFilterCount = $derived(() => {
		let count = 0;
		if (searchQuery !== '') count++;
		if (statusFilter !== 'all') count++;
		if (workflowFilter !== 'all') count++;
		if (dateFilter !== 'all') count++;
		if (showPinnedOnly) count++;
		return count;
	});

	// Status config
	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string }> = {
		pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800' },
		running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30' },
		completed: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30' },
		failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30' },
		cancelled: { icon: Ban, color: 'text-orange-500', bg: 'bg-orange-100 dark:bg-orange-900/30' }
	};

	// Get effective status - checks if any node failed
	function getEffectiveStatus(run: Execution): string {
		// If the run's status is already failed/cancelled, use that
		if (run.status === 'failed' || run.status === 'cancelled') {
			return run.status;
		}
		// Check if any node failed
		if (run.node_states) {
			const hasFailedNode = Object.values(run.node_states).some(
				(state: any) => state.status === 'failed' || state.status === 'cancelled'
			);
			if (hasFailedNode) {
				return 'failed';
			}
		}
		return run.status;
	}

	// Row action menu state
	let activeMenuRunId = $state<string | null>(null);

	function toggleRowMenu(runId: string, e: MouseEvent) {
		e.stopPropagation();
		activeMenuRunId = activeMenuRunId === runId ? null : runId;
	}

	function closeRowMenu() {
		activeMenuRunId = null;
	}

	// Date filter helper
	function isWithinDateRange(dateStr: string | undefined, range: string): boolean {
		if (!dateStr || range === 'all') return true;
		const date = new Date(dateStr);
		const now = new Date();
		const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

		switch (range) {
			case 'hour':
				return now.getTime() - date.getTime() < 3600000;
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

	// Get tokens from metadata
	function getTokens(run: Execution): number {
		return run.metadata?.aggregate_statistics?.tokens?.total_tokens || 0;
	}

	// Get cost from metadata
	function getCost(run: Execution): number {
		return run.metadata?.aggregate_statistics?.cost?.total_cost_usd || 0;
	}

	// Filtered and sorted runs
	let filteredRuns = $derived(() => {
		let runs = [...executionHistory];

		// Filter by pinned
		if (showPinnedOnly) {
			runs = runs.filter(r => pinnedRunIds.has(r.id));
		}

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

		// Sort - pinned runs first
		runs.sort((a, b) => {
			// Pinned runs always first
			const aPinned = pinnedRunIds.has(a.id);
			const bPinned = pinnedRunIds.has(b.id);
			if (aPinned && !bPinned) return -1;
			if (!aPinned && bPinned) return 1;

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
				case 'tokens':
					comparison = getTokens(a) - getTokens(b);
					break;
				case 'cost':
					comparison = getCost(a) - getCost(b);
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
		showPinnedOnly = false;
	}

	function selectRun(run: Execution) {
		uiStore.selectRun(run.id);
		const url = new URL(window.location.href);
		url.searchParams.set('view', 'runs');
		url.searchParams.set('run', run.id);
		window.history.pushState({}, '', url.toString());
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
		await executionStore.loadExecutionHistory();
	}

	function formatDate(date?: string): string {
		if (!date) return '-';
		return new Date(date).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
	}

	function formatTime(date?: string): string {
		if (!date) return '';
		return new Date(date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	function formatRelativeTime(date?: string): string {
		if (!date) return '-';
		const d = new Date(date);
		const now = new Date();
		const diff = now.getTime() - d.getTime();

		if (diff < 60000) return 'Just now';
		if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
		if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
		if (diff < 172800000) return 'Yesterday';
		return formatDate(date);
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

	function togglePinRun(runId: string) {
		const newSet = new Set(pinnedRunIds);
		if (newSet.has(runId)) {
			newSet.delete(runId);
		} else {
			newSet.add(runId);
		}
		pinnedRunIds = newSet;
		savePinnedRuns();
	}

	function toggleExpandRow(runId: string, e: Event) {
		e.stopPropagation();
		const newSet = new Set(expandedRowIds);
		if (newSet.has(runId)) {
			newSet.delete(runId);
		} else {
			newSet.add(runId);
		}
		expandedRowIds = newSet;
	}

	function requestDeleteSelectedRuns() {
		if (selectedRunIds.size === 0) return;
		deleteCount = selectedRunIds.size;
		showDeleteConfirm = true;
	}

	function confirmDeleteRuns() {
		executionStore.removeMultipleFromHistory(Array.from(selectedRunIds));
		selectedRunIds = new Set();
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	function cancelDeleteRuns() {
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	async function exportRuns() {
		const runs = selectedRunIds.size > 0
			? executionHistory.filter(r => selectedRunIds.has(r.id))
			: filteredRuns();

		const data = JSON.stringify(runs, null, 2);
		const blob = new Blob([data], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `sygra-runs-export-${new Date().toISOString().slice(0, 10)}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}

	// Get selected runs for comparison
	let selectedRunsForComparison = $derived(() => {
		return executionHistory.filter(r => selectedRunIds.has(r.id));
	});

	// Get unique models from selected runs
	let comparisonModels = $derived(() => {
		const selectedRuns = executionHistory.filter(r => selectedRunIds.has(r.id));
		const models = selectedRuns.flatMap(r => r.metadata?.models ? Object.keys(r.metadata.models) : []);
		return [...new Set(models)];
	});

	// Re-run a workflow with the same parameters
	async function rerunWorkflow(run: Execution) {
		closeRowMenu();
		if (!run.workflow_id) return;

		try {
			// Reconstruct execution options from the run's metadata
			const metadata = run.metadata;
			const options: import('$lib/stores/workflow.svelte').ExecutionOptions = {
				inputData: run.input_data || {},
				startIndex: metadata?.dataset?.start_index ?? 0,
				numRecords: metadata?.dataset?.num_records_processed ?? 10,
				batchSize: metadata?.execution?.batch_size ?? 10,
				checkpointInterval: metadata?.execution?.checkpoint_interval ?? 100,
				runName: `${run.workflow_name || 'workflow'}_rerun_${Date.now()}`,
				outputWithTs: true,
				outputDir: '',
				debug: metadata?.execution?.debug ?? false,
				resume: null,
				quality: false,
				disableMetadata: false,
				runArgs: {}
			};

			// Start the execution directly
			await executionStore.startExecution(run.workflow_id, options);

			// Navigate to runs view to see the new execution
			uiStore.setView('runs');
		} catch (e) {
			console.error('Re-run failed:', e);
		}
	}

	// Delete single run
	function deleteSingleRun(runId: string) {
		closeRowMenu();
		executionStore.removeFromHistory(runId);
	}
</script>

<svelte:window onclick={closeRowMenu} />

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div class="flex items-center gap-4">
				<div>
					<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Runs</h1>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						{filteredRuns().length} of {executionHistory.length} runs
						{#if selectionCount > 0}
							<span class="ml-2 text-violet-600 dark:text-violet-400">• {selectionCount} selected</span>
						{/if}
					</p>
				</div>
			</div>

			<div class="flex items-center gap-2">
				<!-- View Mode Toggle -->
				<div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
					<button
						onclick={() => setViewMode('table')}
						class="p-2 rounded-md transition-colors {viewMode === 'table' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
						title="Table view"
					>
						<Table size={16} />
					</button>
					<button
						onclick={() => setViewMode('cards')}
						class="p-2 rounded-md transition-colors {viewMode === 'cards' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
						title="Card view"
					>
						<LayoutGrid size={16} />
					</button>
					<button
						onclick={() => setViewMode('analytics')}
						class="p-2 rounded-md transition-colors {viewMode === 'analytics' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
						title="Analytics"
					>
						<BarChart3 size={16} />
					</button>
					{#if selectionCount >= 2}
						<button
							onclick={() => setViewMode('compare')}
							class="p-2 rounded-md transition-colors {viewMode === 'compare' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
							title="Compare {selectionCount} runs"
						>
							<GitCompare size={16} />
						</button>
					{/if}
				</div>

				<div class="w-px h-8 bg-gray-200 dark:bg-gray-700"></div>

				{#if selectionCount > 0}
					<button
						onclick={clearSelection}
						class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
						title="Clear selection"
					>
						<X size={18} />
					</button>
					<button
						onclick={exportRuns}
						class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 transition-colors text-sm"
						title="Export selected runs"
					>
						<Download size={16} />
					</button>
					<button
						onclick={requestDeleteSelectedRuns}
						class="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 transition-colors text-sm font-medium"
					>
						<Trash2 size={16} />
						Delete ({selectionCount})
					</button>
					<div class="w-px h-8 bg-gray-200 dark:bg-gray-700"></div>
				{:else}
					<button
						onclick={exportRuns}
						class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
						title="Export filtered runs"
					>
						<Download size={18} />
					</button>
				{/if}

				<button
					onclick={refresh}
					class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
				>
					<RefreshCw size={16} />
					Refresh
				</button>
			</div>
		</div>

		<!-- Quick Stats Bar -->
		{#if executionHistory.length > 0}
			<div class="mb-4">
				<RunQuickStats runs={filteredRuns()} />
			</div>
		{/if}

		<!-- Filters Row -->
		<div class="flex flex-wrap items-center gap-3">
			<!-- Search -->
			<div class="relative flex-1 min-w-64 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
				<input
					type="text"
					placeholder="Search by workflow name or run ID..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
				/>
			</div>

			<!-- Quick filters -->
			<CustomSelect
				options={statusOptions}
				bind:value={statusFilter}
				placeholder="All Status"
				searchable={false}
				class="w-36"
			/>

			<CustomSelect
				options={workflowOptions}
				bind:value={workflowFilter}
				placeholder="All Workflows"
				searchable={workflowOptions.length > 5}
				searchPlaceholder="Search workflows..."
				class="w-44"
			/>

			<CustomSelect
				options={dateOptions}
				bind:value={dateFilter}
				placeholder="All Time"
				searchable={false}
				class="w-40"
			/>

			<!-- Pinned filter toggle -->
			<button
				onclick={() => showPinnedOnly = !showPinnedOnly}
				class="flex items-center gap-2 px-3 py-2 rounded-lg border transition-colors text-sm {showPinnedOnly ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400' : 'border-gray-300 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800'}"
				title="Show pinned only"
			>
				<Star size={14} class={showPinnedOnly ? 'fill-current' : ''} />
				Pinned
			</button>

			<!-- Clear filters -->
			{#if hasActiveFilters}
				<button
					onclick={clearFilters}
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					<X size={14} />
					Clear ({activeFilterCount()})
				</button>
			{/if}
		</div>

		<!-- Active filter tags -->
		{#if hasActiveFilters}
			<div class="flex flex-wrap items-center gap-2 mt-3">
				{#if statusFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300">
						Status: {statusFilter}
						<button onclick={() => statusFilter = 'all'} class="hover:text-violet-900 dark:hover:text-violet-100">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if workflowFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
						Workflow: {workflowFilter}
						<button onclick={() => workflowFilter = 'all'} class="hover:text-blue-900 dark:hover:text-blue-100">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if dateFilter !== 'all'}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
						{dateOptions.find(d => d.value === dateFilter)?.label}
						<button onclick={() => dateFilter = 'all'} class="hover:text-amber-900 dark:hover:text-amber-100">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if showPinnedOnly}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
						Pinned Only
						<button onclick={() => showPinnedOnly = false} class="hover:text-amber-900 dark:hover:text-amber-100">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if searchQuery}
					<span class="inline-flex items-center gap-1 px-2 py-1 text-xs rounded-full bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
						Search: "{searchQuery}"
						<button onclick={() => searchQuery = ''} class="hover:text-gray-900 dark:hover:text-gray-100">
							<X size={12} />
						</button>
					</span>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Content based on view mode -->
	{#if viewMode === 'analytics'}
		<div class="flex-1 min-h-0">
			<RunsAnalyticsDashboard runs={filteredRuns()} totalRuns={executionHistory.length} />
		</div>
	{:else if viewMode === 'compare' && selectionCount >= 2}
		<!-- Run Comparison View -->
		<RunComparisonView
			runs={selectedRunsForComparison()}
			onBack={() => viewMode = 'table'}
		/>
	{:else if viewMode === 'cards'}
		<!-- Card View -->
		<div class="flex-1 overflow-auto p-6">
			{#if filteredRuns().length === 0}
				<div class="text-center py-16">
					<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
						<Activity size={32} class="text-violet-500" />
					</div>
					<p class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-1">
						{hasActiveFilters ? 'No matching runs' : 'No runs yet'}
					</p>
					<p class="text-sm text-gray-500">
						{hasActiveFilters ? 'Try adjusting your filters' : 'Execute a workflow to see runs here'}
					</p>
				</div>
			{:else}
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
					{#each filteredRuns() as run (run.id)}
						<RunCard
							{run}
							selected={selectedRunIds.has(run.id)}
							pinned={pinnedRunIds.has(run.id)}
							onSelect={() => selectRun(run)}
							onPin={() => togglePinRun(run.id)}
							onRerun={() => rerunWorkflow(run)}
							onDelete={() => {
								selectedRunIds = new Set([run.id]);
								requestDeleteSelectedRuns();
							}}
						/>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<!-- Table View -->
		<div class="flex-1 overflow-auto">
			<table class="w-full">
				<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 z-10">
					<tr>
						<th class="text-left px-4 py-3 w-12">
							<button
								onclick={toggleSelectAll}
								class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
								title={allSelected() ? 'Deselect all' : 'Select all'}
							>
								{#if allSelected()}
									<CheckSquare size={18} class="text-violet-500" />
								{:else if someSelected()}
									<MinusSquare size={18} class="text-violet-500" />
								{:else}
									<Square size={18} />
								{/if}
							</button>
						</th>
						<th class="text-left px-4 py-3 w-10">
							<Star size={14} class="text-gray-400" />
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('workflow_name')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Workflow
								<ArrowUpDown size={14} class={sortField === 'workflow_name' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('status')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Status
								<ArrowUpDown size={14} class={sortField === 'status' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-3 w-48">
							<span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								Timeline
							</span>
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('started_at')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Started
								<ArrowUpDown size={14} class={sortField === 'started_at' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('duration_ms')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Duration
								<ArrowUpDown size={14} class={sortField === 'duration_ms' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('tokens')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Tokens
								<ArrowUpDown size={14} class={sortField === 'tokens' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-3">
							<button
								onclick={() => toggleSort('cost')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Cost
								<ArrowUpDown size={14} class={sortField === 'cost' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="w-12"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
					{#each filteredRuns() as run (run.id)}
						{@const effectiveStatus = getEffectiveStatus(run)}
						{@const status = statusConfig[effectiveStatus] || statusConfig.pending}
						{@const StatusIcon = status.icon}
						{@const isSelected = selectedRunIds.has(run.id)}
						{@const isPinned = pinnedRunIds.has(run.id)}
						{@const isExpanded = expandedRowIds.has(run.id)}
						<tr
							onclick={() => selectRun(run)}
							class="group cursor-pointer transition-colors {isSelected ? 'bg-violet-50 dark:bg-violet-900/20' : selectedRunId === run.id ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'}"
						>
							<td class="px-4 py-3">
								<button
									onclick={(e) => toggleSelectRun(run.id, e)}
									class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
								>
									{#if isSelected}
										<CheckSquare size={18} class="text-violet-500" />
									{:else}
										<Square size={18} class="text-gray-400" />
									{/if}
								</button>
							</td>
							<td class="px-4 py-3">
								<button
									onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); }}
									class="p-1 rounded transition-colors {isPinned ? 'text-amber-500' : 'text-gray-300 dark:text-gray-600 opacity-0 group-hover:opacity-100 hover:text-amber-500'}"
									title={isPinned ? 'Unpin' : 'Pin'}
								>
									<Star size={14} class={isPinned ? 'fill-current' : ''} />
								</button>
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-col">
									<span class="font-medium text-gray-900 dark:text-gray-100 group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
										{run.workflow_name || 'Unknown Workflow'}
									</span>
									<span class="text-xs text-gray-500 dark:text-gray-500 font-mono">
										{run.id.slice(0, 12)}...
									</span>
								</div>
							</td>
							<td class="px-4 py-3">
								<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium {status.color} {status.bg}">
									<StatusIcon size={12} class={effectiveStatus === 'running' ? 'animate-spin' : ''} />
									{effectiveStatus}
								</span>
							</td>
							<td class="px-4 py-3">
								{#if Object.keys(run.node_states).length > 0}
									<RunTimelineBar nodeStates={run.node_states} totalDuration={run.duration_ms} />
								{:else}
									<span class="text-gray-400 text-xs">-</span>
								{/if}
							</td>
							<td class="px-4 py-3">
								<div class="flex flex-col">
									<span class="text-sm text-gray-900 dark:text-gray-100">
										{formatRelativeTime(run.started_at)}
									</span>
									<span class="text-xs text-gray-500">
										{formatTime(run.started_at)}
									</span>
								</div>
							</td>
							<td class="px-4 py-3">
								<span class="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1">
									<Timer size={14} class="text-gray-400" />
									{formatDuration(run.duration_ms)}
								</span>
							</td>
							<td class="px-4 py-3">
								<span class="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1">
									<Zap size={14} class="text-violet-400" />
									{formatTokens(run.metadata)}
								</span>
							</td>
							<td class="px-4 py-3">
								<span class="text-sm text-gray-900 dark:text-gray-100 flex items-center gap-1">
									<DollarSign size={14} class="text-emerald-400" />
									{formatCost(run.metadata)}
								</span>
							</td>
							<td class="px-4 py-3">
								<div class="relative flex items-center gap-1">
									<button
										onclick={(e) => toggleRowMenu(run.id, e)}
										class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
										title="Actions"
									>
										<MoreHorizontal size={16} />
									</button>
									{#if activeMenuRunId === run.id}
										<div class="absolute right-0 top-full mt-1 w-44 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
											{#if !isPinned}
												<button
													onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); closeRowMenu(); }}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
												>
													<Star size={14} />
													Pin Run
												</button>
											{:else}
												<button
													onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); closeRowMenu(); }}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
												>
													<StarOff size={14} />
													Unpin
												</button>
											{/if}
											<button
												onclick={(e) => { e.stopPropagation(); rerunWorkflow(run); }}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
											>
												<Play size={14} />
												Re-run
											</button>
											<button
												onclick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(run.id); closeRowMenu(); }}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
											>
												<Copy size={14} />
												Copy ID
											</button>
											<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>
											<button
												onclick={(e) => { e.stopPropagation(); deleteSingleRun(run.id); }}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
											>
												<Trash2 size={14} />
												Delete
											</button>
										</div>
									{/if}
									<ChevronRight size={16} class="text-gray-400 group-hover:text-violet-500 transition-colors" />
								</div>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="10" class="px-6 py-16 text-center">
								<div class="text-gray-500 dark:text-gray-400">
									{#if hasActiveFilters}
										<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-gray-200 to-gray-300 dark:from-gray-700 dark:to-gray-600 flex items-center justify-center">
											<Search size={32} class="text-gray-400" />
										</div>
										<p class="text-lg font-medium mb-1">No matching runs</p>
										<p class="text-sm mb-4">Try adjusting your filters</p>
										<button
											onclick={clearFilters}
											class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm transition-colors"
										>
											Clear Filters
										</button>
									{:else}
										<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
											<Activity size={32} class="text-violet-500" />
										</div>
										<p class="text-lg font-medium mb-1">No runs yet</p>
										<p class="text-sm">Execute a workflow to see runs here</p>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
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
