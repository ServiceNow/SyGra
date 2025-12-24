<script lang="ts">
	import '../styles/global.css';
	import '@xyflow/svelte/dist/base.css';
	import Sidebar from '$lib/components/sidebar/Sidebar.svelte';
	import SettingsModal from '$lib/components/settings/SettingsModal.svelte';
	import { workflowStore, executionStore, uiStore } from '$lib/stores/workflow.svelte';
	import { themeStore } from '$lib/stores/theme.svelte';
	import { onMount, onDestroy } from 'svelte';

	let { children } = $props();
	let showSettingsModal = $state(false);

	// Handle URL-based navigation (used for initial load and popstate)
	async function handleUrlNavigation() {
		const url = new URL(window.location.href);
		const view = url.searchParams.get('view');
		const workflowId = url.searchParams.get('workflow');
		const runId = url.searchParams.get('run');

		if (view === 'runs') {
			uiStore.setView('runs');
			workflowStore.clearCurrentWorkflow();
			// Restore selected run if present
			if (runId) {
				uiStore.selectRun(runId);
			} else {
				uiStore.clearSelectedRun();
			}
		} else if (view === 'workflows') {
			uiStore.setView('workflows');
			workflowStore.clearCurrentWorkflow();
		} else if (view === 'builder') {
			uiStore.setView('builder');
		} else if (view === 'library') {
			// Library view - preserve workflow so recipes can be added to it
			uiStore.setView('library');
		} else if (view === 'models') {
			// Models view - preserve workflow
			uiStore.setView('models');
		} else if (workflowId) {
			uiStore.setView('workflow');
			await workflowStore.loadWorkflow(workflowId);
		} else {
			// Default to home dashboard
			uiStore.setView('home');
			workflowStore.clearCurrentWorkflow();
		}
	}

	// Handle browser back/forward buttons
	function handlePopState() {
		handleUrlNavigation();
	}

	onMount(async () => {
		// Initialize theme from localStorage/system preference
		themeStore.init();

		// Load workflows on mount
		await workflowStore.loadWorkflows();

		// Restore view and selection from URL
		await handleUrlNavigation();

		// Load execution history and resume any running executions
		await executionStore.loadExecutionHistory();
		executionStore.resumeRunningExecution();

		// Listen for browser back/forward navigation
		window.addEventListener('popstate', handlePopState);
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('popstate', handlePopState);
		}
	});

	function openSettings() {
		showSettingsModal = true;
	}
</script>

<div class="h-screen flex overflow-hidden">
	<!-- Sidebar -->
	<Sidebar onOpenSettings={openSettings} />

	<!-- Main content -->
	<main class="flex-1 flex flex-col overflow-hidden">
		{@render children()}
	</main>
</div>

<!-- Settings Modal (global, accessible from any page) -->
{#if showSettingsModal}
	<SettingsModal onclose={() => showSettingsModal = false} />
{/if}
