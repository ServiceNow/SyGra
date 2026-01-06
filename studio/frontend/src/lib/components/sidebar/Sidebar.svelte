<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { pushState } from '$app/navigation';
	import { workflowStore, uiStore, executionStore } from '$lib/stores/workflow.svelte';
	import { recipeStore } from '$lib/stores/recipe.svelte';
	import { toolStore } from '$lib/stores/tool.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';
	import {
		Home, ChevronLeft, ChevronRight,
		FolderOpen, History, Plus, Library, Settings, Brain, Sparkles
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
	class="flex flex-col border-r border-gray-200 dark:border-[#0A4D6E] bg-white dark:bg-[#032D42] transition-all duration-300"
	class:w-64={!collapsed}
	class:w-16={collapsed}
>
	<!-- Logo/Brand -->
	<div class="h-14 flex items-center border-b border-gray-200 dark:border-[#0A4D6E] overflow-hidden px-2">
		<div class="w-12 h-12 shrink-0 flex items-center justify-center">
			<!-- Logo with Green + Purple gradient (ServiceNow brand style) -->
			<div
				class="w-9 h-9 rounded-xl flex items-center justify-center shadow-md"
				style="background: radial-gradient(ellipse at 20% 10%, rgba(99, 223, 78, 0.4) 0%, transparent 50%), radial-gradient(ellipse at 80% 90%, rgba(191, 113, 242, 0.35) 0%, transparent 50%), #032D42;"
			>
				<Sparkles size={20} class="text-[#63DF4E]" />
			</div>
		</div>
		{#if !collapsed}
			<span class="font-semibold text-lg whitespace-nowrap">
				<span class="text-[#032D42] dark:text-white tracking-tight">SyGra</span>
				<span class="text-gray-400 dark:text-gray-500 font-normal text-sm ml-0.5">Studio</span>
			</span>
		{/if}
	</div>

	<!-- Navigation -->
	<nav class="flex-1 overflow-y-auto overflow-x-hidden p-2">
		<!-- Create Workflow Button - Primary Action with Wasabi Green accent -->
		<div class="mb-4 overflow-hidden">
			<button
				onclick={createNewWorkflow}
				class="w-full flex items-center py-2.5 rounded-lg bg-[#63DF4E] hover:bg-[#4BC93A] text-[#032D42] font-semibold transition-all shadow-sm hover:shadow-md"
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<Plus size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm whitespace-nowrap pr-3">Create Workflow</span>
				{/if}
			</button>
		</div>

		<!-- Home navigation item -->
		<div class="mb-4">
			<button
				onclick={goToHome}
				class="w-full flex items-center py-2 rounded-lg transition-colors"
				class:bg-[#e8f4f8]={currentView === 'home'}
				class:dark:bg-[#064565]={currentView === 'home'}
				class:text-[#032D42]={currentView === 'home'}
				class:dark:text-[#52B8FF]={currentView === 'home'}
				class:text-gray-600={currentView !== 'home'}
				class:dark:text-gray-400={currentView !== 'home'}
				class:hover:bg-gray-100={currentView !== 'home'}
				class:dark:hover:bg-[#064565]={currentView !== 'home'}
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<Home size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium">Home</span>
				{/if}
			</button>
		</div>

		<!-- Workflows navigation item -->
		<div class="mb-4">
			<button
				onclick={goToWorkflows}
				class="w-full flex items-center py-2 rounded-lg transition-colors"
				class:bg-[#e8f4f8]={currentView === 'workflows'}
				class:dark:bg-[#064565]={currentView === 'workflows'}
				class:text-[#032D42]={currentView === 'workflows'}
				class:dark:text-[#52B8FF]={currentView === 'workflows'}
				class:text-gray-600={currentView !== 'workflows'}
				class:dark:text-gray-400={currentView !== 'workflows'}
				class:hover:bg-gray-100={currentView !== 'workflows'}
				class:dark:hover:bg-[#064565]={currentView !== 'workflows'}
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<FolderOpen size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left">Workflows</span>
					{#if workflows.length > 0}
						<span class="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-[#0A4D6E] text-gray-600 dark:text-gray-300 mr-3">
							{workflows.length}
						</span>
					{/if}
				{/if}
			</button>
		</div>

		<!-- Models navigation item -->
		<div class="mb-4">
			<button
				onclick={goToModels}
				class="w-full flex items-center py-2 rounded-lg transition-colors"
				class:bg-[#e8f4f8]={currentView === 'models'}
				class:dark:bg-[#064565]={currentView === 'models'}
				class:text-[#032D42]={currentView === 'models'}
				class:dark:text-[#52B8FF]={currentView === 'models'}
				class:text-gray-600={currentView !== 'models'}
				class:dark:text-gray-400={currentView !== 'models'}
				class:hover:bg-gray-100={currentView !== 'models'}
				class:dark:hover:bg-[#064565]={currentView !== 'models'}
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<Brain size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left">Models</span>
					{#if modelsTotalCount > 0}
						<span class="text-xs px-2 py-0.5 rounded-full mr-3 {modelsOnlineCount > 0 ? 'bg-[#63DF4E]/20 text-[#4BC93A] dark:text-[#63DF4E]' : 'bg-gray-200 dark:bg-[#0A4D6E] text-gray-600 dark:text-gray-300'}">
							{modelsOnlineCount}/{modelsTotalCount}
						</span>
					{/if}
				{/if}
			</button>
		</div>

		<!-- Runs navigation item -->
		<div class="mb-4">
			<button
				onclick={goToRuns}
				class="w-full flex items-center py-2 rounded-lg transition-colors"
				class:bg-[#e8f4f8]={currentView === 'runs'}
				class:dark:bg-[#064565]={currentView === 'runs'}
				class:text-[#032D42]={currentView === 'runs'}
				class:dark:text-[#52B8FF]={currentView === 'runs'}
				class:text-gray-600={currentView !== 'runs'}
				class:dark:text-gray-400={currentView !== 'runs'}
				class:hover:bg-gray-100={currentView !== 'runs'}
				class:dark:hover:bg-[#064565]={currentView !== 'runs'}
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<History size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left">Runs</span>
					{#if executionHistory.length > 0}
						<span class="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-[#0A4D6E] text-gray-600 dark:text-gray-300 {runningCount === 0 ? 'mr-3' : ''}">
							{executionHistory.length}
						</span>
					{/if}
					{#if runningCount > 0}
						<span class="w-2 h-2 rounded-full bg-[#52B8FF] animate-pulse ml-1.5 mr-3" title="{runningCount} running"></span>
					{/if}
				{/if}
			</button>
		</div>

		<!-- Library navigation item -->
		<div class="mb-4">
			<button
				onclick={goToLibrary}
				class="w-full flex items-center py-2 rounded-lg transition-colors"
				class:bg-[#e8f4f8]={currentView === 'library'}
				class:dark:bg-[#064565]={currentView === 'library'}
				class:text-[#032D42]={currentView === 'library'}
				class:dark:text-[#52B8FF]={currentView === 'library'}
				class:text-gray-600={currentView !== 'library'}
				class:dark:text-gray-400={currentView !== 'library'}
				class:hover:bg-gray-100={currentView !== 'library'}
				class:dark:hover:bg-[#064565]={currentView !== 'library'}
			>
				<div class="w-12 shrink-0 flex items-center justify-center">
					<Library size={20} />
				</div>
				{#if !collapsed}
					<span class="text-sm font-medium flex-1 text-left">Library</span>
					{@const totalCount = recipeStore.recipes.length + toolStore.tools.length}
					{#if totalCount > 0}
						<span class="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-[#0A4D6E] text-gray-600 dark:text-gray-300 mr-3">
							{totalCount}
						</span>
					{/if}
				{/if}
			</button>
		</div>
	</nav>

	<!-- Footer -->
	<div class="border-t border-gray-200 dark:border-[#0A4D6E] p-2">
		<!-- Settings -->
		<button
			onclick={onOpenSettings}
			class="w-full flex items-center py-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#064565] transition-colors"
		>
			<div class="w-12 shrink-0 flex items-center justify-center">
				<Settings size={20} />
			</div>
			{#if !collapsed}
				<span class="text-sm font-medium">Settings</span>
			{/if}
		</button>

		<!-- Collapse toggle -->
		<button
			onclick={handleCollapse}
			class="w-full flex items-center py-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-[#064565] transition-colors"
		>
			<div class="w-12 shrink-0 flex items-center justify-center">
				{#if collapsed}
					<ChevronRight size={20} />
				{:else}
					<ChevronLeft size={20} />
				{/if}
			</div>
			{#if !collapsed}
				<span class="text-sm font-medium">Collapse</span>
			{/if}
		</button>
	</div>
</aside>
