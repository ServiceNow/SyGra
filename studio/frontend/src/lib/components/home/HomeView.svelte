<script lang="ts">
	import { workflowStore, executionStore, uiStore, type Execution } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
	import {
		Plus, GitBranch, History, Play, CheckCircle2, XCircle, Clock, Loader2, ArrowRight,
		Zap, TrendingUp, TrendingDown, Activity, Layers, RefreshCw, Sparkles, Search, Timer,
		DollarSign, BarChart3, Settings, BookOpen, Cpu, Database, ArrowUpRight, Ban
	} from 'lucide-svelte';

	let workflows = $derived(workflowStore.workflows);
	let executionHistory = $derived(executionStore.executionHistory);
	let loading = $derived(workflowStore.loading);
	let searchQuery = $state('');

	// Helper to get effective status for stats
	function getEffectiveStatusForRun(run: Execution): string {
		if (run.status === 'failed' || run.status === 'cancelled') return run.status;
		if (run.node_states) {
			const hasFailedNode = Object.values(run.node_states).some(
				(state: any) => state.status === 'failed' || state.status === 'cancelled'
			);
			if (hasFailedNode) return 'failed';
		}
		return run.status;
	}

	// Stats with more detail - uses effective status
	let stats = $derived(() => {
		const completed = executionHistory.filter(e => getEffectiveStatusForRun(e) === 'completed');
		const failed = executionHistory.filter(e => getEffectiveStatusForRun(e) === 'failed' || getEffectiveStatusForRun(e) === 'cancelled').length;
		const running = executionHistory.filter(e => getEffectiveStatusForRun(e) === 'running').length;
		const total = executionHistory.length;
		const successRate = total > 0 ? Math.round((completed.length / total) * 100) : 0;

		let totalTokens = 0, totalCost = 0, totalDuration = 0;
		completed.forEach(run => {
			if (run.metadata) {
				totalTokens += run.metadata.aggregate_statistics?.tokens?.total_tokens || 0;
				totalCost += run.metadata.aggregate_statistics?.cost?.total_cost_usd || 0;
			}
			totalDuration += run.duration_ms || 0;
		});

		return {
			workflowCount: workflows.length,
			totalRuns: total,
			completedRuns: completed.length,
			failedRuns: failed,
			runningRuns: running,
			successRate,
			totalTokens,
			totalCost,
			avgDuration: completed.length > 0 ? totalDuration / completed.length : 0
		};
	});

	let recentWorkflows = $derived(workflows.slice(0, 6));
	let recentRuns = $derived(executionHistory.slice(0, 6));

	// Filtered items based on search
	let filteredWorkflows = $derived(() => {
		if (!searchQuery.trim()) return recentWorkflows;
		const q = searchQuery.toLowerCase();
		return workflows.filter(w => w.name.toLowerCase().includes(q)).slice(0, 6);
	});

	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string; label: string }> = {
		pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', label: 'Pending' },
		running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', label: 'Running' },
		completed: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-100 dark:bg-emerald-900/30', label: 'Completed' },
		failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Failed' },
		cancelled: { icon: Ban, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', label: 'Cancelled' }
	};

	function navigate(view: string, params?: Record<string, string>) {
		uiStore.setView(view as any);
		const url = new URL(window.location.href);
		url.searchParams.set('view', view);
		url.searchParams.delete('workflow');
		if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
		pushState(url.toString(), {});
	}

	function goToWorkflows() { navigate('workflows'); }
	function goToRuns() { navigate('runs'); }
	function goToModels() { navigate('models'); }
	function goToLibrary() { navigate('library'); }

	function createNewWorkflow() {
		workflowStore.createNewWorkflow();
		navigate('builder');
	}

	async function selectWorkflow(id: string) {
		await workflowStore.loadWorkflow(id);
		uiStore.setView('workflow');
		const url = new URL(window.location.href);
		url.searchParams.set('workflow', id);
		url.searchParams.delete('view');
		pushState(url.toString(), {});
	}

	function selectRun(run: Execution) {
		uiStore.setView('runs');
		uiStore.selectRun(run.id);
		navigate('runs', { run: run.id });
	}

	async function refresh() {
		await workflowStore.loadWorkflows();
		await executionStore.loadExecutionHistory();
	}

	function formatTime(date?: string): string {
		if (!date) return '-';
		const d = new Date(date);
		const now = new Date();
		const diffMs = now.getTime() - d.getTime();
		const diffMins = Math.floor(diffMs / 60000);
		const diffHours = Math.floor(diffMs / 3600000);
		const diffDays = Math.floor(diffMs / 86400000);
		if (diffMins < 1) return 'Just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffHours < 24) return `${diffHours}h ago`;
		if (diffDays < 7) return `${diffDays}d ago`;
		return d.toLocaleDateString();
	}

	function formatDuration(ms: number): string {
		if (ms < 1000) return `${ms.toFixed(0)}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		return `${Math.floor(s / 60)}m ${(s % 60).toFixed(0)}s`;
	}

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toLocaleString();
	}

	function formatCost(usd: number): string {
		if (usd < 0.01) return `<$0.01`;
		return `$${usd.toFixed(2)}`;
	}

	</script>

<div class="h-full w-full overflow-auto bg-gray-50 dark:bg-gray-900">
	<div class="max-w-7xl mx-auto px-6 py-8">
		<!-- Header -->
		<div class="flex items-center justify-between mb-8">
			<div class="flex items-center gap-4">
				<div class="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
					<Sparkles size={24} class="text-white" />
				</div>
				<div>
					<h1 class="text-2xl font-semibold text-gray-900 dark:text-gray-100 tracking-tight">
						SyGra Studio
					</h1>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						Synthetic data generation workflows
					</p>
				</div>
			</div>
			<div class="flex items-center gap-3">
				<div class="relative">
					<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
					<input
						type="text"
						bind:value={searchQuery}
						placeholder="Search workflows..."
						class="w-64 pl-9 pr-4 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500 transition-colors"
					/>
				</div>
				<button onclick={refresh} disabled={loading} class="p-2.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50">
					<RefreshCw size={18} class={loading ? 'animate-spin' : ''} />
				</button>
			</div>
		</div>

		<!-- Quick Actions Bar -->
		<div class="grid grid-cols-4 gap-4 mb-8">
			<button onclick={createNewWorkflow} class="group flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md transition-all">
				<div class="w-10 h-10 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
					<Plus size={20} class="text-violet-600 dark:text-violet-400" />
				</div>
				<div class="text-left">
					<p class="font-medium text-gray-900 dark:text-gray-100">New Workflow</p>
					<p class="text-xs text-gray-500">Create from scratch</p>
				</div>
			</button>
			<button onclick={goToWorkflows} class="group flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:border-blue-300 dark:hover:border-blue-600 hover:shadow-md transition-all">
				<div class="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
					<GitBranch size={20} class="text-blue-600 dark:text-blue-400" />
				</div>
				<div class="text-left">
					<p class="font-medium text-gray-900 dark:text-gray-100">Workflows</p>
					<p class="text-xs text-gray-500">{stats().workflowCount} available</p>
				</div>
			</button>
			<button onclick={goToRuns} class="group flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:border-emerald-300 dark:hover:border-emerald-600 hover:shadow-md transition-all">
				<div class="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
					<Activity size={20} class="text-emerald-600 dark:text-emerald-400" />
				</div>
				<div class="text-left">
					<p class="font-medium text-gray-900 dark:text-gray-100">Runs</p>
					<p class="text-xs text-gray-500">{stats().totalRuns} executions</p>
				</div>
			</button>
			<button onclick={goToLibrary} class="group flex items-center gap-3 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm hover:border-amber-300 dark:hover:border-amber-600 hover:shadow-md transition-all">
				<div class="w-10 h-10 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center group-hover:scale-110 transition-transform">
					<BookOpen size={20} class="text-amber-600 dark:text-amber-400" />
				</div>
				<div class="text-left">
					<p class="font-medium text-gray-900 dark:text-gray-100">Library</p>
					<p class="text-xs text-gray-500">Browse templates</p>
				</div>
			</button>
		</div>

		<!-- Stats Grid -->
		<div class="grid grid-cols-5 gap-4 mb-8">
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
				<div class="flex items-center justify-between mb-2">
					<span class="text-xs font-medium text-gray-500 uppercase">Success Rate</span>
					{#if stats().successRate >= 80}<TrendingUp size={14} class="text-emerald-500" />{:else}<TrendingDown size={14} class="text-red-500" />{/if}
				</div>
				<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats().successRate}%</div>
				<div class="text-xs text-gray-500 mt-1">{stats().completedRuns}/{stats().totalRuns} runs</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
				<div class="flex items-center justify-between mb-2">
					<span class="text-xs font-medium text-gray-500 uppercase">Total Tokens</span>
					<Zap size={14} class="text-violet-500" />
				</div>
				<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatNumber(stats().totalTokens)}</div>
				<div class="text-xs text-gray-500 mt-1">across all runs</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
				<div class="flex items-center justify-between mb-2">
					<span class="text-xs font-medium text-gray-500 uppercase">Total Cost</span>
					<DollarSign size={14} class="text-emerald-500" />
				</div>
				<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatCost(stats().totalCost)}</div>
				<div class="text-xs text-gray-500 mt-1">API usage</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
				<div class="flex items-center justify-between mb-2">
					<span class="text-xs font-medium text-gray-500 uppercase">Avg Duration</span>
					<Timer size={14} class="text-amber-500" />
				</div>
				<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{formatDuration(stats().avgDuration)}</div>
				<div class="text-xs text-gray-500 mt-1">per run</div>
			</div>
			<div class="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 shadow-sm">
				<div class="flex items-center justify-between mb-2">
					<span class="text-xs font-medium text-gray-500 uppercase">Running</span>
					<Loader2 size={14} class="text-blue-500 {stats().runningRuns > 0 ? 'animate-spin' : ''}" />
				</div>
				<div class="text-2xl font-bold text-gray-900 dark:text-gray-100">{stats().runningRuns}</div>
				<div class="text-xs text-gray-500 mt-1">active now</div>
			</div>
		</div>

		<!-- Main Content Grid -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
			<!-- Recent Workflows -->
			<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
				<div class="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
					<h2 class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
						<GitBranch size={18} class="text-violet-500" />
						{searchQuery ? 'Search Results' : 'Recent Workflows'}
					</h2>
					<button onclick={goToWorkflows} class="text-sm text-violet-600 dark:text-violet-400 hover:text-violet-700 flex items-center gap-1">
						View all <ArrowRight size={14} />
					</button>
				</div>
				<div class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each filteredWorkflows() as workflow (workflow.id)}
						<button onclick={() => selectWorkflow(workflow.id)} class="group w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left">
							<div class="flex items-center gap-3">
								<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
									<GitBranch size={18} class="text-white" />
								</div>
								<div>
									<p class="font-medium text-gray-900 dark:text-gray-100 group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">{workflow.name}</p>
									<div class="flex items-center gap-3 text-xs text-gray-500">
										<span class="flex items-center gap-1"><Layers size={12} />{workflow.node_count} nodes</span>
										<span>{workflow.edge_count} edges</span>
									</div>
								</div>
							</div>
							<ArrowUpRight size={16} class="text-gray-400 group-hover:text-violet-500 transition-colors" />
						</button>
					{:else}
						<div class="px-5 py-12 text-center">
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
								<Layers size={28} class="text-violet-500" />
							</div>
							<p class="font-medium text-gray-900 dark:text-gray-100 mb-1">{searchQuery ? 'No matching workflows' : 'No workflows yet'}</p>
							<p class="text-sm text-gray-500 mb-4">{searchQuery ? 'Try a different search term' : 'Create your first workflow to get started'}</p>
							{#if !searchQuery}
								<button onclick={createNewWorkflow} class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors">
									<Plus size={16} class="inline mr-1" /> Create Workflow
								</button>
							{/if}
						</div>
					{/each}
				</div>
			</div>

			<!-- Recent Activity -->
			<div class="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
				<div class="px-5 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
					<h2 class="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
						<History size={18} class="text-blue-500" />
						Recent Activity
					</h2>
					<button onclick={goToRuns} class="text-sm text-violet-600 dark:text-violet-400 hover:text-violet-700 flex items-center gap-1">
						View all <ArrowRight size={14} />
					</button>
				</div>
				<div class="divide-y divide-gray-200 dark:divide-gray-700">
					{#each recentRuns as run (run.id)}
						{@const effectiveStatus = getEffectiveStatusForRun(run)}
						{@const status = statusConfig[effectiveStatus] || statusConfig.pending}
						{@const StatusIcon = status.icon}
						<button onclick={() => selectRun(run)} class="group w-full px-5 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors text-left">
							<div class="flex items-center gap-3 flex-1 min-w-0">
								<div class="w-10 h-10 rounded-lg {status.bg} flex items-center justify-center flex-shrink-0">
									<StatusIcon size={18} class="{status.color} {effectiveStatus === 'running' ? 'animate-spin' : ''}" />
								</div>
								<div class="flex-1 min-w-0">
									<p class="font-medium text-gray-900 dark:text-gray-100 truncate">{run.workflow_name || 'Unknown'}</p>
									<div class="flex items-center gap-3 text-xs text-gray-500">
										<span>{formatTime(run.started_at)}</span>
										{#if run.duration_ms}<span class="flex items-center gap-1"><Timer size={10} />{formatDuration(run.duration_ms)}</span>{/if}
										{#if run.metadata?.aggregate_statistics?.tokens?.total_tokens}<span class="flex items-center gap-1"><Zap size={10} />{formatNumber(run.metadata.aggregate_statistics.tokens.total_tokens)}</span>{/if}
									</div>
								</div>
							</div>
							<span class="text-xs px-2.5 py-1 rounded-full font-medium {status.color} {status.bg}">{status.label}</span>
						</button>
					{:else}
						<div class="px-5 py-12 text-center">
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
								<Activity size={28} class="text-blue-500" />
							</div>
							<p class="font-medium text-gray-900 dark:text-gray-100 mb-1">No runs yet</p>
							<p class="text-sm text-gray-500">Execute a workflow to see activity here</p>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- Getting Started -->
		{#if workflows.length === 0}
			<div class="mt-8 bg-gradient-to-r from-violet-500/10 to-purple-600/10 dark:from-violet-500/20 dark:to-purple-600/20 rounded-xl p-6 border border-violet-200 dark:border-violet-800">
				<h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
					🚀 Getting Started
				</h3>
				<p class="text-gray-600 dark:text-gray-400 mb-4">
					Welcome to SyGra Studio! Here's how to get started:
				</p>
				<div class="grid grid-cols-1 md:grid-cols-3 gap-4">
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4">
						<div class="w-8 h-8 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-3">
							<span class="text-violet-600 dark:text-violet-400 font-bold">1</span>
						</div>
						<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-1">Create a Workflow</h4>
						<p class="text-sm text-gray-500 dark:text-gray-400">
							Click "Create Workflow" to build your first data generation pipeline.
						</p>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4">
						<div class="w-8 h-8 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-3">
							<span class="text-violet-600 dark:text-violet-400 font-bold">2</span>
						</div>
						<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-1">Add Nodes</h4>
						<p class="text-sm text-gray-500 dark:text-gray-400">
							Drag and drop LLM, Lambda, Sampler, and other nodes to build your workflow.
						</p>
					</div>
					<div class="bg-white dark:bg-gray-800 rounded-lg p-4">
						<div class="w-8 h-8 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-3">
							<span class="text-violet-600 dark:text-violet-400 font-bold">3</span>
						</div>
						<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-1">Execute & Monitor</h4>
						<p class="text-sm text-gray-500 dark:text-gray-400">
							Run your workflow and monitor execution progress in real-time.
						</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
