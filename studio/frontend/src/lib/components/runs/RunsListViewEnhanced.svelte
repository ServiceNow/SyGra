<script lang="ts">
	import { executionStore, uiStore, workflowStore, type Execution } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
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
		await executionStore.loadExecutionHistory(undefined, 50, true);
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

<div class="h-full w-full flex flex-col bg-surface-primary">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-surface-border px-6 py-5">
		<div class="flex items-center justify-between mb-5">
			<div class="flex items-center gap-4">
				<!-- Animated Icon -->
				<div class="relative">
					<div class="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-accent/20 to-emerald-500/10 flex items-center justify-center group-hover:scale-105 transition-transform">
						<Activity size={24} class="text-brand-accent" />
					</div>
					{#if executionHistory.some(r => r.status === 'running')}
						<div class="absolute -top-1 -right-1 w-3 h-3 bg-status-running rounded-full animate-pulse"></div>
					{/if}
				</div>
				<div>
					<h1 class="text-2xl font-display font-bold text-text-primary">Runs</h1>
					<p class="text-sm text-text-muted">
						{filteredRuns().length} of {executionHistory.length} runs
						{#if selectionCount > 0}
							<span class="ml-2 text-brand-accent font-medium">• {selectionCount} selected</span>
						{/if}
					</p>
				</div>
			</div>

			<div class="flex items-center gap-3">
				<!-- View Mode Toggle -->
				<div class="flex items-center bg-surface-secondary rounded-xl p-1 shadow-sm">
					<button
						onclick={() => setViewMode('table')}
						class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'table' ? 'bg-surface-primary text-brand-accent shadow-md' : 'text-text-muted hover:text-text-primary hover:bg-surface-tertiary'}"
						title="Table view"
					>
						<Table size={16} />
					</button>
					<button
						onclick={() => setViewMode('cards')}
						class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'cards' ? 'bg-surface-primary text-brand-accent shadow-md' : 'text-text-muted hover:text-text-primary hover:bg-surface-tertiary'}"
						title="Card view"
					>
						<LayoutGrid size={16} />
					</button>
					<button
						onclick={() => setViewMode('analytics')}
						class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'analytics' ? 'bg-surface-primary text-brand-accent shadow-md' : 'text-text-muted hover:text-text-primary hover:bg-surface-tertiary'}"
						title="Analytics"
					>
						<BarChart3 size={16} />
					</button>
					{#if selectionCount >= 2}
						<button
							onclick={() => setViewMode('compare')}
							class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'compare' ? 'bg-surface-primary text-brand-accent shadow-md' : 'text-text-muted hover:text-text-primary hover:bg-surface-tertiary'}"
							title="Compare {selectionCount} runs"
						>
							<GitCompare size={16} />
						</button>
					{/if}
				</div>

				<div class="w-px h-8 bg-surface-border"></div>

				{#if selectionCount > 0}
					<button
						onclick={clearSelection}
						class="p-2.5 rounded-xl hover:bg-surface-secondary text-text-muted transition-all duration-200"
						title="Clear selection"
					>
						<X size={18} />
					</button>
					<button
						onclick={exportRuns}
						class="flex items-center gap-2 px-3.5 py-2.5 rounded-xl hover:bg-surface-secondary text-text-secondary transition-all duration-200 text-sm font-medium"
						title="Export selected runs"
					>
						<Download size={16} />
					</button>
					<button
						onclick={requestDeleteSelectedRuns}
						class="flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-status-failed/10 hover:bg-status-failed/20 text-status-failed transition-all duration-200 text-sm font-semibold"
					>
						<Trash2 size={16} />
						Delete ({selectionCount})
					</button>
					<div class="w-px h-8 bg-surface-border"></div>
				{:else}
					<button
						onclick={exportRuns}
						class="p-2.5 rounded-xl hover:bg-surface-secondary text-text-muted transition-all duration-200"
						title="Export filtered runs"
					>
						<Download size={18} />
					</button>
				{/if}

				<button
					onclick={refresh}
					class="flex items-center gap-2 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent/90 text-white rounded-xl transition-all duration-200 font-semibold shadow-md hover:shadow-lg hover:-translate-y-0.5"
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
				<Search size={16} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" />
				<input
					type="text"
					placeholder="Search by workflow name or run ID..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-2.5 border border-surface-border rounded-xl bg-surface-primary text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-brand-accent/30 focus:border-brand-accent text-sm transition-all duration-200"
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
				class="flex items-center gap-2 px-3.5 py-2.5 rounded-xl border transition-all duration-200 text-sm font-medium {showPinnedOnly ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 shadow-sm' : 'border-surface-border text-text-secondary hover:bg-surface-secondary hover:border-surface-border'}"
				title="Show pinned only"
			>
				<Star size={14} class={showPinnedOnly ? 'fill-current' : ''} />
				Pinned
			</button>

			<!-- Clear filters -->
			{#if hasActiveFilters}
				<button
					onclick={clearFilters}
					class="flex items-center gap-1.5 px-3.5 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary rounded-xl transition-all duration-200 font-medium"
				>
					<X size={14} />
					Clear ({activeFilterCount()})
				</button>
			{/if}
		</div>

		<!-- Active filter tags -->
		{#if hasActiveFilters}
			<div class="flex flex-wrap items-center gap-2 mt-4">
				{#if statusFilter !== 'all'}
					<span class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-brand-accent/10 text-brand-accent border border-brand-accent/20">
						Status: {statusFilter}
						<button onclick={() => statusFilter = 'all'} class="hover:text-brand-accent/70 transition-colors">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if workflowFilter !== 'all'}
					<span class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
						Workflow: {workflowFilter}
						<button onclick={() => workflowFilter = 'all'} class="hover:text-blue-800 dark:hover:text-blue-200 transition-colors">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if dateFilter !== 'all'}
					<span class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
						{dateOptions.find(d => d.value === dateFilter)?.label}
						<button onclick={() => dateFilter = 'all'} class="hover:text-amber-800 dark:hover:text-amber-200 transition-colors">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if showPinnedOnly}
					<span class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
						Pinned Only
						<button onclick={() => showPinnedOnly = false} class="hover:text-amber-800 dark:hover:text-amber-200 transition-colors">
							<X size={12} />
						</button>
					</span>
				{/if}
				{#if searchQuery}
					<span class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-full bg-surface-tertiary text-text-secondary border border-surface-border">
						Search: "{searchQuery}"
						<button onclick={() => searchQuery = ''} class="hover:text-text-primary transition-colors">
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
				<div class="text-center py-20">
					<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-brand-accent/20 to-emerald-500/10 flex items-center justify-center shadow-lg">
						<Activity size={36} class="text-brand-accent" />
					</div>
					<p class="text-xl font-display font-semibold text-text-primary mb-2">
						{hasActiveFilters ? 'No matching runs' : 'No runs yet'}
					</p>
					<p class="text-sm text-text-muted max-w-sm mx-auto">
						{hasActiveFilters ? 'Try adjusting your filters to find what you\'re looking for' : 'Execute a workflow to see your runs appear here'}
					</p>
					{#if hasActiveFilters}
						<button
							onclick={clearFilters}
							class="mt-6 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent/90 text-white rounded-xl transition-all duration-200 font-semibold shadow-md hover:shadow-lg"
						>
							Clear Filters
						</button>
					{/if}
				</div>
			{:else}
				<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
					{#each filteredRuns() as run, i (run.id)}
						<div class="animate-slide-up" style="animation-delay: {Math.min(i * 50, 300)}ms">
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
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{:else}
		<!-- Table View -->
		<div class="flex-1 overflow-auto">
			<table class="w-full">
				<thead class="sticky top-0 bg-surface-secondary/95 backdrop-blur-sm border-b border-surface-border z-10">
					<tr>
						<th class="text-left px-4 py-4 w-12">
							<button
								onclick={toggleSelectAll}
								class="p-1.5 rounded-lg hover:bg-surface-tertiary text-text-muted transition-all duration-200"
								title={allSelected() ? 'Deselect all' : 'Select all'}
							>
								{#if allSelected()}
									<CheckSquare size={18} class="text-brand-accent" />
								{:else if someSelected()}
									<MinusSquare size={18} class="text-brand-accent" />
								{:else}
									<Square size={18} />
								{/if}
							</button>
						</th>
						<th class="text-left px-4 py-4 w-10">
							<Star size={14} class="text-text-muted" />
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('workflow_name')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Workflow
								<ArrowUpDown size={14} class={sortField === 'workflow_name' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('status')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Status
								<ArrowUpDown size={14} class={sortField === 'status' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-4 w-48">
							<span class="text-xs font-semibold text-text-muted uppercase tracking-wider">
								Timeline
							</span>
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('started_at')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Started
								<ArrowUpDown size={14} class={sortField === 'started_at' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('duration_ms')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Duration
								<ArrowUpDown size={14} class={sortField === 'duration_ms' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('tokens')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Tokens
								<ArrowUpDown size={14} class={sortField === 'tokens' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="text-left px-4 py-4">
							<button
								onclick={() => toggleSort('cost')}
								class="flex items-center gap-1.5 text-xs font-semibold text-text-muted uppercase tracking-wider hover:text-text-primary transition-colors"
							>
								Cost
								<ArrowUpDown size={14} class={sortField === 'cost' ? 'text-brand-accent' : ''} />
							</button>
						</th>
						<th class="w-12"></th>
					</tr>
				</thead>
				<tbody class="divide-y divide-surface-border/50">
					{#each filteredRuns() as run (run.id)}
						{@const effectiveStatus = getEffectiveStatus(run)}
						{@const status = statusConfig[effectiveStatus] || statusConfig.pending}
						{@const StatusIcon = status.icon}
						{@const isSelected = selectedRunIds.has(run.id)}
						{@const isPinned = pinnedRunIds.has(run.id)}
						{@const isExpanded = expandedRowIds.has(run.id)}
						<tr
							onclick={() => selectRun(run)}
							class="group cursor-pointer transition-all duration-200 {isSelected ? 'bg-brand-accent/10' : selectedRunId === run.id ? 'bg-brand-accent/5 border-l-2 border-l-brand-accent' : 'hover:bg-surface-secondary'}"
						>
							<td class="px-4 py-4">
								<button
									onclick={(e) => toggleSelectRun(run.id, e)}
									class="p-1.5 rounded-lg hover:bg-surface-tertiary transition-all duration-200"
								>
									{#if isSelected}
										<CheckSquare size={18} class="text-brand-accent" />
									{:else}
										<Square size={18} class="text-text-muted" />
									{/if}
								</button>
							</td>
							<td class="px-4 py-4">
								<button
									onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); }}
									class="p-1.5 rounded-lg transition-all duration-200 {isPinned ? 'text-amber-500' : 'text-text-muted/30 opacity-0 group-hover:opacity-100 hover:text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/20'}"
									title={isPinned ? 'Unpin' : 'Pin'}
								>
									<Star size={14} class={isPinned ? 'fill-current' : ''} />
								</button>
							</td>
							<td class="px-4 py-4">
								<div class="flex flex-col">
									<span class="font-semibold text-text-primary group-hover:text-brand-accent transition-colors">
										{run.workflow_name || 'Unknown Workflow'}
									</span>
									<span class="text-xs text-text-muted font-mono">
										{run.id.slice(0, 12)}...
									</span>
								</div>
							</td>
							<td class="px-4 py-4">
								<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border
									{effectiveStatus === 'completed' ? 'bg-status-completed/10 text-status-completed border-status-completed/20' : ''}
									{effectiveStatus === 'running' ? 'bg-status-running/10 text-status-running border-status-running/20' : ''}
									{effectiveStatus === 'failed' ? 'bg-status-failed/10 text-status-failed border-status-failed/20' : ''}
									{effectiveStatus === 'cancelled' ? 'bg-status-cancelled/10 text-status-cancelled border-status-cancelled/20' : ''}
									{effectiveStatus === 'pending' ? 'bg-status-pending/10 text-status-pending border-status-pending/20' : ''}
								">
									<StatusIcon size={12} class={effectiveStatus === 'running' ? 'animate-spin' : ''} />
									{effectiveStatus}
								</span>
							</td>
							<td class="px-4 py-4">
								{#if Object.keys(run.node_states).length > 0}
									<RunTimelineBar nodeStates={run.node_states} totalDuration={run.duration_ms} />
								{:else}
									<span class="text-text-muted text-xs">-</span>
								{/if}
							</td>
							<td class="px-4 py-4">
								<div class="flex flex-col">
									<span class="text-sm font-medium text-text-primary">
										{formatRelativeTime(run.started_at)}
									</span>
									<span class="text-xs text-text-muted">
										{formatTime(run.started_at)}
									</span>
								</div>
							</td>
							<td class="px-4 py-4">
								<span class="text-sm text-text-primary flex items-center gap-1.5">
									<Timer size={14} class="text-text-muted" />
									{formatDuration(run.duration_ms)}
								</span>
							</td>
							<td class="px-4 py-4">
								<span class="text-sm text-text-primary flex items-center gap-1.5">
									<Zap size={14} class="text-brand-accent" />
									{formatTokens(run.metadata)}
								</span>
							</td>
							<td class="px-4 py-4">
								<span class="text-sm text-text-primary flex items-center gap-1.5">
									<DollarSign size={14} class="text-status-completed" />
									{formatCost(run.metadata)}
								</span>
							</td>
							<td class="px-4 py-4">
								<div class="relative flex items-center gap-1">
									<button
										onclick={(e) => toggleRowMenu(run.id, e)}
										class="p-2 text-text-muted hover:text-text-primary hover:bg-surface-tertiary rounded-lg transition-all duration-200 opacity-0 group-hover:opacity-100"
										title="Actions"
									>
										<MoreHorizontal size={16} />
									</button>
									{#if activeMenuRunId === run.id}
										<div class="absolute right-0 top-full mt-1 w-48 bg-surface-primary rounded-xl shadow-elevation-3 border border-surface-border py-1.5 z-50 animate-scale-in origin-top-right">
											{#if !isPinned}
												<button
													onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); closeRowMenu(); }}
													class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
												>
													<Star size={14} />
													Pin Run
												</button>
											{:else}
												<button
													onclick={(e) => { e.stopPropagation(); togglePinRun(run.id); closeRowMenu(); }}
													class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
												>
													<StarOff size={14} />
													Unpin
												</button>
											{/if}
											<button
												onclick={(e) => { e.stopPropagation(); rerunWorkflow(run); }}
												class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
											>
												<Play size={14} />
												Re-run
											</button>
											<button
												onclick={(e) => { e.stopPropagation(); navigator.clipboard.writeText(run.id); closeRowMenu(); }}
												class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-text-secondary hover:text-text-primary hover:bg-surface-secondary transition-colors"
											>
												<Copy size={14} />
												Copy ID
											</button>
											<div class="h-px bg-surface-border my-1.5 mx-3"></div>
											<button
												onclick={(e) => { e.stopPropagation(); deleteSingleRun(run.id); }}
												class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-status-failed hover:bg-status-failed/10 transition-colors"
											>
												<Trash2 size={14} />
												Delete
											</button>
										</div>
									{/if}
									<ChevronRight size={16} class="text-text-muted group-hover:text-brand-accent transition-colors" />
								</div>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="10" class="px-6 py-20 text-center">
								<div>
									{#if hasActiveFilters}
										<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-surface-tertiary to-surface-secondary flex items-center justify-center shadow-lg">
											<Search size={36} class="text-text-muted" />
										</div>
										<p class="text-xl font-display font-semibold text-text-primary mb-2">No matching runs</p>
										<p class="text-sm text-text-muted mb-6 max-w-sm mx-auto">Try adjusting your filters to find what you're looking for</p>
										<button
											onclick={clearFilters}
											class="px-5 py-2.5 bg-brand-accent hover:bg-brand-accent/90 text-white rounded-xl text-sm transition-all duration-200 font-semibold shadow-md hover:shadow-lg"
										>
											Clear Filters
										</button>
									{:else}
										<div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-brand-accent/20 to-emerald-500/10 flex items-center justify-center shadow-lg">
											<Activity size={36} class="text-brand-accent" />
										</div>
										<p class="text-xl font-display font-semibold text-text-primary mb-2">No runs yet</p>
										<p class="text-sm text-text-muted max-w-sm mx-auto">Execute a workflow to see your runs appear here</p>
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
