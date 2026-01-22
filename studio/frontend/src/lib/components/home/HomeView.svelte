<script lang="ts">
	import { workflowStore, executionStore, uiStore, type Execution } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
	import {
		Plus, History, CheckCircle2, XCircle, Clock, Loader2, ArrowRight,
		Zap, TrendingUp, TrendingDown, Activity, Layers, RefreshCw, Sparkles, Search, Timer,
		DollarSign, ArrowUpRight, Ban, FolderOpen, Library, Brain, Workflow, Play
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

	let recentWorkflows = $derived(workflows.slice(0, 5));
	let recentRuns = $derived(executionHistory.slice(0, 5));

	// Filtered items based on search
	let filteredWorkflows = $derived(() => {
		if (!searchQuery.trim()) return recentWorkflows;
		const q = searchQuery.toLowerCase();
		return workflows.filter(w => w.name.toLowerCase().includes(q)).slice(0, 5);
	});

	const statusConfig: Record<string, { icon: typeof Clock; color: string; bg: string; label: string; border: string }> = {
		pending: { icon: Clock, color: 'text-text-muted', bg: 'bg-surface-tertiary', border: 'border-[var(--border)]', label: 'Pending' },
		running: { icon: Loader2, color: 'text-info', bg: 'bg-info-light', border: 'border-info-border', label: 'Running' },
		completed: { icon: CheckCircle2, color: 'text-success', bg: 'bg-success-light', border: 'border-success-border', label: 'Completed' },
		failed: { icon: XCircle, color: 'text-error', bg: 'bg-error-light', border: 'border-error-border', label: 'Failed' },
		cancelled: { icon: Ban, color: 'text-warning', bg: 'bg-warning-light', border: 'border-warning-border', label: 'Cancelled' }
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

<div class="h-full w-full overflow-auto bg-surface-secondary">
	<!-- Hero section with gradient mesh background -->
	<div class="relative overflow-hidden">
		<!-- Background decoration -->
		<div class="absolute inset-0 bg-gradient-hero pointer-events-none"></div>
		<div class="absolute top-0 right-0 w-96 h-96 bg-gradient-to-br from-brand-accent/10 via-transparent to-transparent rounded-full blur-3xl"></div>
		<div class="absolute bottom-0 left-1/4 w-64 h-64 bg-gradient-to-tr from-indigo-500/10 via-transparent to-transparent rounded-full blur-3xl"></div>

		<div class="relative max-w-7xl mx-auto px-6 pt-8 pb-6">
			<!-- Header -->
			<div class="flex items-center justify-between mb-8">
				<div class="flex items-center gap-5">
					<!-- Animated Logo -->
					<div class="relative group">
						<div
							class="w-14 h-14 rounded-2xl flex items-center justify-center shadow-lg transition-all duration-300 group-hover:scale-105 group-hover:shadow-xl"
							style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);"
						>
							<div class="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-accent/30 via-transparent to-violet-500/20"></div>
							<Sparkles size={26} class="text-brand-accent relative z-10 transition-transform duration-300 group-hover:rotate-12" />
						</div>
						<div class="absolute inset-0 rounded-2xl bg-brand-accent/25 blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
					</div>
					<div>
						<h1 class="text-3xl font-bold tracking-tighter">
							<span class="text-[var(--text-primary)]">SyGra</span>
							<span class="text-[var(--text-muted)] font-normal ml-1.5">Studio</span>
						</h1>
						<p class="text-sm text-[var(--text-secondary)] mt-0.5">
							Synthetic data generation workflows
						</p>
					</div>
				</div>
				<div class="flex items-center gap-3">
					<div class="relative">
						<Search size={16} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
						<input
							type="text"
							bind:value={searchQuery}
							placeholder="Search workflows..."
							class="w-72 pl-10 pr-4 py-2.5 bg-surface border border-[var(--border)] rounded-xl text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)] transition-all duration-200"
						/>
					</div>
					<button
						onclick={refresh}
						disabled={loading}
						class="p-2.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-surface-hover rounded-xl transition-all duration-200 disabled:opacity-50"
					>
						<RefreshCw size={18} class={loading ? 'animate-spin' : ''} />
					</button>
				</div>
			</div>

			<!-- Quick Actions -->
			<div class="grid grid-cols-4 gap-4 mb-8">
				<!-- Create New -->
				<button
					onclick={createNewWorkflow}
					class="group relative overflow-hidden flex items-center gap-4 p-5 bg-brand-accent rounded-2xl shadow-md hover:shadow-glow-accent transition-all duration-300 hover:-translate-y-1"
				>
					<div class="absolute inset-0 bg-gradient-to-r from-white/0 via-white/10 to-white/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-700"></div>
					<div class="w-12 h-12 rounded-xl bg-brand-primary/15 flex items-center justify-center transition-transform duration-200 group-hover:scale-110">
						<Plus size={24} class="text-brand-primary" strokeWidth={2.5} />
					</div>
					<div class="text-left relative z-10">
						<p class="font-semibold text-brand-primary">New Workflow</p>
						<p class="text-xs text-brand-primary/70 mt-0.5">Create from scratch</p>
					</div>
				</button>

				<!-- Workflows -->
				<button
					onclick={goToWorkflows}
					class="group flex items-center gap-4 p-5 bg-surface-elevated rounded-2xl border border-[var(--border)] shadow-card hover:shadow-card-hover hover:border-[var(--border-focus)] transition-all duration-300 hover:-translate-y-1"
				>
					<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-transform duration-200 group-hover:scale-110 shadow-sm bg-gradient-data">
						<FolderOpen size={22} class="text-white" />
					</div>
					<div class="text-left">
						<p class="font-semibold text-[var(--text-primary)]">Workflows</p>
						<p class="text-xs text-[var(--text-muted)] mt-0.5">{stats().workflowCount} available</p>
					</div>
				</button>

				<!-- Runs -->
				<button
					onclick={goToRuns}
					class="group flex items-center gap-4 p-5 bg-surface-elevated rounded-2xl border border-[var(--border)] shadow-card hover:shadow-card-hover hover:border-[var(--border-focus)] transition-all duration-300 hover:-translate-y-1"
				>
					<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-transform duration-200 group-hover:scale-110 shadow-sm bg-gradient-brand">
						<History size={22} class="text-white" />
					</div>
					<div class="text-left">
						<p class="font-semibold text-[var(--text-primary)]">Runs</p>
						<p class="text-xs text-[var(--text-muted)] mt-0.5">{stats().totalRuns} executions</p>
					</div>
				</button>

				<!-- Library -->
				<button
					onclick={goToLibrary}
					class="group flex items-center gap-4 p-5 bg-surface-elevated rounded-2xl border border-[var(--border)] shadow-card hover:shadow-card-hover hover:border-[var(--border-focus)] transition-all duration-300 hover:-translate-y-1"
				>
					<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-transform duration-200 group-hover:scale-110 shadow-sm bg-gradient-ai">
						<Library size={22} class="text-white" />
					</div>
					<div class="text-left">
						<p class="font-semibold text-[var(--text-primary)]">Library</p>
						<p class="text-xs text-[var(--text-muted)] mt-0.5">Browse templates</p>
					</div>
				</button>
			</div>
		</div>
	</div>

	<!-- Main Content -->
	<div class="max-w-7xl mx-auto px-6 pb-8">
		<!-- Stats Grid -->
		<div class="grid grid-cols-5 gap-4 mb-8">
			<!-- Success Rate -->
			<div class="stat-card group">
				<div class="flex items-center justify-between mb-3">
					<span class="text-2xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Success Rate</span>
					<div class="stat-icon {stats().successRate >= 80 ? 'bg-success-light' : 'bg-error-light'}">
						{#if stats().successRate >= 80}
							<TrendingUp size={14} class="text-success" />
						{:else}
							<TrendingDown size={14} class="text-error" />
						{/if}
					</div>
				</div>
				<div class="text-3xl font-bold text-[var(--text-primary)] tracking-tight">{stats().successRate}<span class="text-lg text-[var(--text-muted)]">%</span></div>
				<div class="text-xs text-[var(--text-muted)] mt-1">{stats().completedRuns} of {stats().totalRuns} runs</div>
				<!-- Progress bar -->
				<div class="mt-3 h-1.5 bg-surface-tertiary rounded-full overflow-hidden">
					<div
						class="h-full rounded-full transition-all duration-500 {stats().successRate >= 80 ? 'bg-success' : 'bg-error'}"
						style="width: {stats().successRate}%"
					></div>
				</div>
			</div>

			<!-- Total Tokens -->
			<div class="stat-card group">
				<div class="flex items-center justify-between mb-3">
					<span class="text-2xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Total Tokens</span>
					<div class="stat-icon bg-node-llm-bg">
						<Zap size={14} class="text-node-llm" />
					</div>
				</div>
				<div class="text-3xl font-bold text-[var(--text-primary)] tracking-tight">{formatNumber(stats().totalTokens)}</div>
				<div class="text-xs text-[var(--text-muted)] mt-1">across all runs</div>
			</div>

			<!-- Total Cost -->
			<div class="stat-card group">
				<div class="flex items-center justify-between mb-3">
					<span class="text-2xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Total Cost</span>
					<div class="stat-icon bg-success-light">
						<DollarSign size={14} class="text-success" />
					</div>
				</div>
				<div class="text-3xl font-bold text-[var(--text-primary)] tracking-tight">{formatCost(stats().totalCost)}</div>
				<div class="text-xs text-[var(--text-muted)] mt-1">API usage</div>
			</div>

			<!-- Avg Duration -->
			<div class="stat-card group">
				<div class="flex items-center justify-between mb-3">
					<span class="text-2xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Avg Duration</span>
					<div class="stat-icon bg-warning-light">
						<Timer size={14} class="text-warning" />
					</div>
				</div>
				<div class="text-3xl font-bold text-[var(--text-primary)] tracking-tight">{formatDuration(stats().avgDuration)}</div>
				<div class="text-xs text-[var(--text-muted)] mt-1">per run</div>
			</div>

			<!-- Running -->
			<div class="stat-card group {stats().runningRuns > 0 ? 'ring-2 ring-info-border' : ''}">
				<div class="flex items-center justify-between mb-3">
					<span class="text-2xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Running</span>
					<div class="stat-icon bg-info-light">
						<Loader2 size={14} class="text-info {stats().runningRuns > 0 ? 'animate-spin' : ''}" />
					</div>
				</div>
				<div class="text-3xl font-bold text-[var(--text-primary)] tracking-tight">{stats().runningRuns}</div>
				<div class="text-xs text-[var(--text-muted)] mt-1">active now</div>
				{#if stats().runningRuns > 0}
					<div class="mt-3 h-1.5 bg-info-light rounded-full overflow-hidden">
						<div class="h-full bg-info rounded-full animate-pulse w-full"></div>
					</div>
				{/if}
			</div>
		</div>

		<!-- Main Content Grid -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
			<!-- Recent Workflows -->
			<div class="content-card">
				<div class="card-header">
					<div class="flex items-center gap-2.5">
						<div class="w-8 h-8 rounded-lg bg-info-light flex items-center justify-center">
							<FolderOpen size={16} class="text-info" />
						</div>
						<h2 class="font-semibold text-[var(--text-primary)]">
							{searchQuery ? 'Search Results' : 'Recent Workflows'}
						</h2>
					</div>
					<button
						onclick={goToWorkflows}
						class="text-sm text-[var(--text-link)] hover:text-[var(--text-primary)] flex items-center gap-1 transition-colors duration-200"
					>
						View all <ArrowRight size={14} />
					</button>
				</div>
				<div class="card-content divide-y divide-[var(--border)]">
					{#each filteredWorkflows() as workflow, i (workflow.id)}
						<button
							onclick={() => selectWorkflow(workflow.id)}
							class="group w-full px-5 py-4 flex items-center justify-between hover:bg-surface-hover transition-all duration-200 text-left"
						>
							<div class="flex items-center gap-3.5">
								<div class="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm transition-transform duration-200 group-hover:scale-105 bg-gradient-data">
									<Workflow size={18} class="text-white" />
								</div>
								<div>
									<p class="font-medium text-[var(--text-primary)] group-hover:text-[var(--text-link)] transition-colors duration-200">{workflow.name}</p>
									<div class="flex items-center gap-3 text-xs text-[var(--text-muted)] mt-0.5">
										<span class="flex items-center gap-1"><Layers size={11} />{workflow.node_count} nodes</span>
										<span>{workflow.edge_count} edges</span>
									</div>
								</div>
							</div>
							<div class="flex items-center gap-2">
								<span class="opacity-0 group-hover:opacity-100 transition-opacity duration-200 text-xs text-[var(--text-muted)]">Open</span>
								<ArrowUpRight size={16} class="text-[var(--text-muted)] group-hover:text-[var(--text-link)] transition-colors duration-200" />
							</div>
						</button>
					{:else}
						<div class="px-5 py-16 text-center">
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center shadow-md bg-gradient-data">
								<FolderOpen size={28} class="text-white" />
							</div>
							<p class="font-medium text-[var(--text-primary)] mb-1">{searchQuery ? 'No matching workflows' : 'No workflows yet'}</p>
							<p class="text-sm text-[var(--text-muted)] mb-5">{searchQuery ? 'Try a different search term' : 'Create your first workflow to get started'}</p>
							{#if !searchQuery}
								<button
									onclick={createNewWorkflow}
									class="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary text-sm font-semibold rounded-xl transition-all duration-200 shadow-sm hover:shadow-glow-accent hover:-translate-y-0.5"
								>
									<Plus size={16} /> Create Workflow
								</button>
							{/if}
						</div>
					{/each}
				</div>
			</div>

			<!-- Recent Activity -->
			<div class="content-card">
				<div class="card-header">
					<div class="flex items-center gap-2.5">
						<div class="w-8 h-8 rounded-lg bg-success-light flex items-center justify-center">
							<Activity size={16} class="text-success" />
						</div>
						<h2 class="font-semibold text-[var(--text-primary)]">Recent Activity</h2>
					</div>
					<button
						onclick={goToRuns}
						class="text-sm text-[var(--text-link)] hover:text-[var(--text-primary)] flex items-center gap-1 transition-colors duration-200"
					>
						View all <ArrowRight size={14} />
					</button>
				</div>
				<div class="card-content divide-y divide-[var(--border)]">
					{#each recentRuns as run, i (run.id)}
						{@const effectiveStatus = getEffectiveStatusForRun(run)}
						{@const status = statusConfig[effectiveStatus] || statusConfig.pending}
						{@const StatusIcon = status.icon}
						<button
							onclick={() => selectRun(run)}
							class="group w-full px-5 py-4 flex items-center justify-between hover:bg-surface-hover transition-all duration-200 text-left"
						>
							<div class="flex items-center gap-3.5 flex-1 min-w-0">
								<div class="w-10 h-10 rounded-xl {status.bg} border {status.border} flex items-center justify-center flex-shrink-0 transition-transform duration-200 group-hover:scale-105">
									<StatusIcon size={18} class="{status.color} {effectiveStatus === 'running' ? 'animate-spin' : ''}" />
								</div>
								<div class="flex-1 min-w-0">
									<p class="font-medium text-[var(--text-primary)] truncate group-hover:text-[var(--text-link)] transition-colors duration-200">{run.workflow_name || 'Unknown'}</p>
									<div class="flex items-center gap-3 text-xs text-[var(--text-muted)] mt-0.5">
										<span>{formatTime(run.started_at)}</span>
										{#if run.duration_ms}
											<span class="flex items-center gap-1"><Timer size={10} />{formatDuration(run.duration_ms)}</span>
										{/if}
										{#if run.metadata?.aggregate_statistics?.tokens?.total_tokens}
											<span class="flex items-center gap-1"><Zap size={10} />{formatNumber(run.metadata.aggregate_statistics.tokens.total_tokens)}</span>
										{/if}
									</div>
								</div>
							</div>
							<span class="text-xs px-2.5 py-1.5 rounded-full font-medium {status.color} {status.bg} border {status.border} whitespace-nowrap">{status.label}</span>
						</button>
					{:else}
						<div class="px-5 py-16 text-center">
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-success-light border border-success-border flex items-center justify-center">
								<Activity size={28} class="text-success" />
							</div>
							<p class="font-medium text-[var(--text-primary)] mb-1">No runs yet</p>
							<p class="text-sm text-[var(--text-muted)]">Execute a workflow to see activity here</p>
						</div>
					{/each}
				</div>
			</div>
		</div>

		<!-- Getting Started -->
		{#if workflows.length === 0}
			<div class="mt-8 bg-surface-elevated rounded-2xl border border-[var(--border)] shadow-card overflow-hidden">
				<div class="p-8">
					<div class="flex items-center gap-4 mb-5">
						<div class="w-12 h-12 rounded-xl flex items-center justify-center shadow-md" style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);">
							<Sparkles size={22} class="text-brand-accent" />
						</div>
						<div>
							<h3 class="text-xl font-bold text-[var(--text-primary)]">Getting Started</h3>
							<p class="text-sm text-[var(--text-secondary)]">Create your first synthetic data workflow</p>
						</div>
					</div>

					<div class="grid grid-cols-1 md:grid-cols-3 gap-5">
						<div class="step-card">
							<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-accent/20 to-brand-accent/10 flex items-center justify-center mb-4">
								<span class="text-brand-accent font-bold text-lg">1</span>
							</div>
							<h4 class="font-semibold text-[var(--text-primary)] mb-2">Create a Workflow</h4>
							<p class="text-sm text-[var(--text-muted)]">
								Click "New Workflow" to build your first data generation pipeline.
							</p>
						</div>
						<div class="step-card">
							<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-node-llm/20 to-node-llm/10 flex items-center justify-center mb-4">
								<span class="text-node-llm font-bold text-lg">2</span>
							</div>
							<h4 class="font-semibold text-[var(--text-primary)] mb-2">Add Nodes</h4>
							<p class="text-sm text-[var(--text-muted)]">
								Drag and drop LLM, Lambda, Sampler, and other nodes to build your workflow.
							</p>
						</div>
						<div class="step-card">
							<div class="w-10 h-10 rounded-xl bg-gradient-to-br from-info/20 to-info/10 flex items-center justify-center mb-4">
								<span class="text-info font-bold text-lg">3</span>
							</div>
							<h4 class="font-semibold text-[var(--text-primary)] mb-2">Execute & Monitor</h4>
							<p class="text-sm text-[var(--text-muted)]">
								Run your workflow and monitor execution progress in real-time.
							</p>
						</div>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.stat-card {
		background-color: var(--surface-elevated);
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 1.25rem;
		transition: all 0.2s ease;
	}

	.stat-card:hover {
		border-color: var(--border-hover);
		box-shadow: var(--shadow-md);
	}

	.stat-icon {
		width: 28px;
		height: 28px;
		border-radius: 8px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.content-card {
		background-color: var(--surface-elevated);
		border: 1px solid var(--border);
		border-radius: 16px;
		overflow: hidden;
		box-shadow: var(--shadow-card);
	}

	.card-header {
		padding: 1rem 1.25rem;
		border-bottom: 1px solid var(--border);
		display: flex;
		align-items: center;
		justify-content: space-between;
		background-color: var(--surface-secondary);
	}

	.card-content {
		max-height: 400px;
		overflow-y: auto;
	}

	.step-card {
		background-color: var(--surface-secondary);
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 1.5rem;
		transition: all 0.2s ease;
	}

	.step-card:hover {
		border-color: var(--border-hover);
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
	}
</style>
