<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { pushState } from '$app/navigation';
	import { workflowStore, uiStore, executionStore } from '$lib/stores/workflow.svelte';
	import { recipeStore } from '$lib/stores/recipe.svelte';
	import { toolStore } from '$lib/stores/tool.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';
	import {
		Home, ChevronLeft, ChevronRight,
		FolderOpen, History, Plus, Library, Settings, Brain, Sparkles,
		Zap
	} from 'lucide-svelte';

	interface Props {
		onOpenSettings: () => void;
	}

	let { onOpenSettings }: Props = $props();

	let collapsed = $derived(uiStore.sidebarCollapsed);
	let workflows = $derived(workflowStore.workflows);
	let executionHistory = $derived(executionStore.executionHistory);
	let currentView = $derived(uiStore.currentView);

	// Helper to update URL after navigation
	function updateUrl(view: string) {
		const url = new URL(window.location.href);
		if (view === 'home') {
			url.searchParams.delete('view');
			url.searchParams.delete('run');
		} else {
			url.searchParams.set('view', view);
		}
		pushState(url.toString(), {});
	}

	function goToHome() {
		if (uiStore.requestNavigation('home')) {
			updateUrl('home');
		}
	}

	function goToWorkflows() {
		if (uiStore.requestNavigation('workflows')) {
			updateUrl('workflows');
		}
	}

	function goToRuns() {
		if (uiStore.requestNavigation('runs')) {
			updateUrl('runs');
		}
	}

	function goToLibrary() {
		if (uiStore.requestNavigation('library')) {
			updateUrl('library');
		}
	}

	function goToModels() {
		if (uiStore.requestNavigation('models')) {
			updateUrl('models');
		}
	}

	const DRAFT_KEY = 'sygra_workflow_draft';

	function createNewWorkflow() {
		// If already in builder with a workflow, just switch to builder view
		if (currentView === 'builder' && workflowStore.currentWorkflow) {
			return;
		}

		// Check if there's a saved draft - if so, let WorkflowBuilder restore it
		const savedDraft = localStorage.getItem(DRAFT_KEY);
		if (savedDraft) {
			try {
				const draft = JSON.parse(savedDraft);
				if (draft.workflow) {
					// There's a draft - don't create new workflow, just navigate to builder
					// WorkflowBuilder will restore the draft
					uiStore.setView('builder');
					updateUrl('builder');
					return;
				}
			} catch (e) {
				// Invalid draft, continue to create new workflow
			}
		}

		// No draft exists, create a new workflow
		workflowStore.createNewWorkflow();
		uiStore.setView('builder');
		updateUrl('builder');
	}

	function handleCollapse() {
		uiStore.toggleSidebar();
	}

	// Count running executions for badge
	let runningCount = $derived(executionHistory.filter(e => e.status === 'running').length);

	// Models count from shared store
	let modelsOnlineCount = $derived(modelsStore.onlineCount);
	let modelsTotalCount = $derived(modelsStore.totalCount);

	// Start auto-refresh on mount, cleanup on destroy
	onMount(() => {
		modelsStore.startAutoRefresh();
	});

	onDestroy(() => {
		modelsStore.stopAutoRefresh();
	});
</script>

<aside
	class="group/sidebar sidebar flex flex-col flex-shrink-0 bg-surface-elevated border-r border-[var(--border)] transition-[width] duration-300 ease-out relative h-full"
	class:w-64={!collapsed}
	class:w-[72px]={collapsed}
	class:sidebar-collapsed={collapsed}
>
	<!-- Decorative gradient accent -->
	<div class="absolute inset-y-0 left-0 w-[2px] bg-gradient-to-b from-brand-accent via-brand-secondary to-violet-500 opacity-60"></div>

	<!-- Logo/Brand Header -->
	<div class="h-16 flex items-center border-b border-[var(--border)] overflow-hidden px-3 relative flex-shrink-0">
		<div class="flex items-center gap-3 pl-1 whitespace-nowrap">
			<!-- Logo Mark -->
			<div class="relative flex-shrink-0">
				<div
					class="w-10 h-10 rounded-xl flex items-center justify-center shadow-md transition-transform duration-300 group-hover/sidebar:scale-105"
					style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);"
				>
					<div class="absolute inset-0 rounded-xl bg-gradient-to-br from-brand-accent/30 via-transparent to-violet-500/20"></div>
					<Sparkles size={20} class="text-brand-accent relative z-10" />
				</div>
				<!-- Glow effect -->
				<div class="absolute inset-0 rounded-xl bg-brand-accent/20 blur-lg opacity-0 group-hover/sidebar:opacity-60 transition-opacity duration-300"></div>
			</div>

			<!-- Brand text -->
			{#if !collapsed}
              <div class="flex flex-col animate-fade-in">
                <span class="font-display font-bold text-lg tracking-tight text-[var(--text-primary)]">
                  SyGra
                </span>
                <span class="text-2xs font-medium text-[var(--text-muted)] -mt-0.5 tracking-wide uppercase">
                  Studio
                </span>
              </div>
            {/if}
		</div>
	</div>

	<!-- Navigation -->
	<nav class="flex-1 overflow-y-auto overflow-x-hidden py-4 px-3 scrollbar-thin min-h-0">
		<!-- Create Workflow Button -->
		<div class="mb-6">
			<button
				onclick={createNewWorkflow}
				class="group/btn w-full flex items-center gap-3 py-2.5 px-3 rounded-xl bg-brand-accent text-brand-primary font-semibold transition-all duration-200 hover:bg-brand-accent-hover hover:shadow-glow-accent hover:-translate-y-0.5 active:translate-y-0 overflow-hidden"
			>
				<div class="w-8 h-8 rounded-lg bg-brand-primary/10 flex items-center justify-center flex-shrink-0 transition-transform duration-200 group-hover/btn:scale-110">
					<Plus size={18} strokeWidth={2.5} />
				</div>
				{#if !collapsed}
					<span class="text-sm whitespace-nowrap">Create Workflow</span>
				{/if}
			</button>
		</div>

		<!-- Navigation Items -->
		<div class="space-y-1.5">
			<!-- Home -->
			<button
				onclick={goToHome}
				class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
				class:nav-item-active={currentView === 'home'}
			>
				<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
					<Home size={18} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium whitespace-nowrap">Home</span>
				{/if}
			</button>

			<!-- Workflows -->
			<button
				onclick={goToWorkflows}
				class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
				class:nav-item-active={currentView === 'workflows'}
			>
				<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
					<FolderOpen size={18} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left whitespace-nowrap">Workflows</span>
					{#if workflows.length > 0}
						<span class="badge-count">
							{workflows.length}
						</span>
					{/if}
				{/if}
			</button>

			<!-- Models -->
			<button
				onclick={goToModels}
				class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
				class:nav-item-active={currentView === 'models'}
			>
				<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
					<Brain size={18} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left whitespace-nowrap">Models</span>
					{#if modelsTotalCount > 0}
						<span class="badge-count {modelsOnlineCount > 0 ? 'badge-count-success' : ''}">
							{modelsOnlineCount}/{modelsTotalCount}
						</span>
					{/if}
				{/if}
			</button>

			<!-- Runs -->
			<button
				onclick={goToRuns}
				class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
				class:nav-item-active={currentView === 'runs'}
			>
				<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200 relative">
					<History size={18} />
					{#if runningCount > 0 && collapsed}
						<span class="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-brand-secondary animate-pulse border-2 border-surface-elevated"></span>
					{/if}
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left whitespace-nowrap">Runs</span>
					<div class="flex items-center gap-1.5">
						{#if executionHistory.length > 0}
							<span class="badge-count">
								{executionHistory.length}
							</span>
						{/if}
						{#if runningCount > 0}
							<span class="flex items-center gap-1 text-2xs font-medium text-brand-secondary bg-info-light px-1.5 py-0.5 rounded-full">
								<Zap size={10} class="animate-pulse" />
								{runningCount}
							</span>
						{/if}
					</div>
				{/if}
			</button>

			<!-- Library -->
			<button
				onclick={goToLibrary}
				class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
				class:nav-item-active={currentView === 'library'}
			>
				<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
					<Library size={18} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left whitespace-nowrap">Library</span>
					{@const totalCount = recipeStore.recipes.length + toolStore.tools.length}
					{#if totalCount > 0}
						<span class="badge-count">
							{totalCount}
						</span>
					{/if}
				{/if}
			</button>
		</div>
	</nav>

	<!-- Footer -->
	<div class="border-t border-[var(--border)] p-3 space-y-1.5 flex-shrink-0">
		<!-- Settings -->
		<button
			onclick={onOpenSettings}
			class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
		>
			<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
				<Settings size={18} />
			</div>
			{#if !collapsed}
				<span class="text-sm font-medium whitespace-nowrap">Settings</span>
			{/if}
		</button>

		<!-- Collapse toggle -->
		<button
			onclick={handleCollapse}
			class="nav-item group/item w-full flex items-center gap-3 py-2.5 px-3 rounded-xl transition-all duration-200"
		>
			<div class="nav-icon w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200">
				{#if collapsed}
					<ChevronRight size={18} />
				{:else}
					<ChevronLeft size={18} />
				{/if}
			</div>
			{#if !collapsed}
				<span class="text-sm font-medium whitespace-nowrap">Collapse</span>
			{/if}
		</button>
	</div>
</aside>

<style>
	/* Sidebar collapsed state adjustments */
	.sidebar-collapsed nav {
		padding-left: 0.75rem;
		padding-right: 0.75rem;
	}

	.sidebar-collapsed nav button,
	.sidebar-collapsed .nav-item {
		justify-content: center;
		padding-left: 0;
		padding-right: 0;
	}

	.sidebar-collapsed nav .mb-6 button {
		padding: 0.625rem;
		justify-content: center;
	}

	/* Footer collapsed state */
	.sidebar-collapsed > div:last-child {
		padding-left: 0.75rem;
		padding-right: 0.75rem;
	}

	.sidebar-collapsed > div:last-child button {
		justify-content: center;
		padding-left: 0;
		padding-right: 0;
	}

	/* Navigation item base styles */
	.nav-item {
		color: var(--text-secondary);
		overflow: hidden;
	}

	.nav-item:hover {
		background-color: var(--surface-hover);
		color: var(--text-primary);
	}

	.nav-item:hover .nav-icon {
		background-color: var(--surface-tertiary);
	}

	/* Active navigation item */
	.nav-item-active {
		background: linear-gradient(135deg, var(--status-info-bg) 0%, rgba(99, 102, 241, 0.08) 100%);
		color: var(--text-link);
		border: 1px solid var(--status-info-border);
	}

	.nav-item-active .nav-icon {
		background: linear-gradient(135deg, var(--status-info) 0%, #6366f1 100%);
		color: white;
		box-shadow: 0 2px 8px rgba(14, 165, 233, 0.3);
	}

	.nav-item-active:hover {
		background: linear-gradient(135deg, var(--status-info-bg) 0%, rgba(99, 102, 241, 0.12) 100%);
	}

	/* Badge count styles */
	.badge-count {
		font-size: 0.6875rem;
		font-weight: 600;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background-color: var(--surface-tertiary);
		color: var(--text-secondary);
		border: 1px solid var(--border);
	}

	.badge-count-success {
		background-color: var(--status-success-bg);
		color: var(--status-success);
		border-color: var(--status-success-border);
	}
</style>
