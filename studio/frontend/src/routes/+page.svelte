<script lang="ts">
	import { tick } from 'svelte';
	import { workflowStore, executionStore, uiStore, type Execution } from '$lib/stores/workflow.svelte';
	import SygraFlow from '$lib/components/graph/SygraFlow.svelte';
	import NodeDetailsPanel from '$lib/components/graph/NodeDetailsPanel.svelte';
	import EdgeDetailsPanel from '$lib/components/graph/EdgeDetailsPanel.svelte';
	import ExecutionPanel from '$lib/components/execution/ExecutionPanel.svelte';
	import ResultsModal from '$lib/components/execution/ResultsModal.svelte';
	import RunWorkflowModal from '$lib/components/execution/RunWorkflowModal.svelte';
	import RunsListView from '$lib/components/runs/RunsListViewEnhanced.svelte';
	import RunDetailsView from '$lib/components/runs/RunDetailsViewEnhanced.svelte';
	import WorkflowsListView from '$lib/components/workflows/WorkflowsListView.svelte';
	import HomeView from '$lib/components/home/HomeView.svelte';
	import WorkflowBuilder from '$lib/components/builder/WorkflowBuilder.svelte';
	import LibraryView from '$lib/components/library/LibraryView.svelte';
	import ModelsView from '$lib/components/models/ModelsView.svelte';
	import WorkflowCodePanel from '$lib/components/code/WorkflowCodePanel.svelte';
	import UnsavedChangesModal from '$lib/components/builder/UnsavedChangesModal.svelte';
	import { Play, StopCircle, LayoutGrid } from 'lucide-svelte';

	let currentWorkflow = $derived(workflowStore.currentWorkflow);
	let currentExecution = $derived(executionStore.currentExecution);
	let selectedNodeId = $derived(uiStore.selectedNodeId);
	let showResultsModal = $derived(uiStore.showResultsModal);
	let currentView = $derived(uiStore.currentView);
	let selectedRunId = $derived(uiStore.selectedRunId);
	let executionHistory = $derived(executionStore.executionHistory);

	// Get selected run from history
	let selectedRun = $derived<Execution | undefined>(
		selectedRunId ? executionHistory.find(e => e.id === selectedRunId) : undefined
	);

	let showRunModal = $derived(uiStore.showRunModal);
	let codePanelCollapsed = $state(true);  // Start collapsed by default
	let sygraFlowRef = $state<{ applyAutoLayout: () => Promise<void> } | undefined>(undefined);
	let selectedEdge = $state<{
		id: string;
		source: string;
		target: string;
		label?: string;
		isConditional: boolean;
		condition?: { condition_path: string; path_map: Record<string, string> };
	} | null>(null);

	// Reference to WorkflowBuilder for direct store updates and draft management
	let workflowBuilderRef = $state<{
		updateEdgeInStore: (edgeId: string, data: { label?: string; is_conditional?: boolean }) => void;
		removeEdgeFromStore: (edgeId: string) => void;
		syncEdgesFromStore: () => void;
		syncNodesFromStore: () => void;
		getHasChanges: () => boolean;
		saveDraftNow: () => void;
		clearDraftNow: () => void;
	} | undefined>(undefined);

	// Show unsaved changes modal when pending navigation exists
	let pendingNavigation = $derived(uiStore.pendingNavigation);
	let showUnsavedChangesModal = $derived(pendingNavigation !== null);

	function handleNodeSelect(event: CustomEvent<string>) {
		const nodeId = event.detail;
		console.log('Page received nodeSelect:', nodeId);
		// Convert empty string to null for proper deselection
		uiStore.selectNode(nodeId || null);
		// Only clear edge selection if a node is actually being selected
		if (nodeId) {
			selectedEdge = null;
		}
	}

	function handleEdgeSelect(event: CustomEvent<{
		id: string;
		source: string;
		target: string;
		label?: string;
		isConditional: boolean;
		condition?: { condition_path: string; path_map: Record<string, string> };
	} | null>) {
		console.log('Page received edgeSelect:', event.detail);
		selectedEdge = event.detail;
	}

	function openRunModal() {
		uiStore.openRunModal();
	}

	function closeRunModal() {
		uiStore.closeRunModal();
	}

	async function handleRun(event: CustomEvent<import('$lib/stores/workflow.svelte').ExecutionOptions>) {
		if (!currentWorkflow) return;
		closeRunModal();

		try {
			await executionStore.startExecution(currentWorkflow.id, event.detail);
		} catch (e) {
			console.error('Execution failed:', e);
		}
	}

	function handleCancel() {
		executionStore.cancelExecution();
	}

	// Builder handlers
	function handleBuilderNodeSelect(event: CustomEvent<string>) {
		const nodeId = event.detail;
		uiStore.selectNode(nodeId || null);
		if (nodeId) {
			selectedEdge = null;
		}
	}

	function handleBuilderEdgeSelect(event: CustomEvent<{ id: string; source: string; target: string } | null>) {
		if (event.detail) {
			uiStore.selectNode(null);
			const { id: svelteFlowId, source, target } = event.detail;

			// Try to find edge in our store by various methods
			let edgeData = workflowStore.currentWorkflow?.edges.find(e => e.id === svelteFlowId);

			// If not found, try stripping xy-edge__ prefix
			if (!edgeData && svelteFlowId.startsWith('xy-edge__')) {
				const strippedId = svelteFlowId.replace('xy-edge__', '');
				edgeData = workflowStore.currentWorkflow?.edges.find(e => e.id === strippedId);
			}

			// If still not found, try by source-target
			if (!edgeData) {
				edgeData = workflowStore.currentWorkflow?.edges.find(e => e.source === source && e.target === target);
			}

			// Use the actual store edge's ID for future operations
			selectedEdge = {
				id: edgeData?.id ?? svelteFlowId,  // Use store's ID if found
				source: source,
				target: target,
				label: edgeData?.label,
				isConditional: edgeData?.is_conditional ?? false,
				condition: edgeData?.condition
			};
		} else {
			selectedEdge = null;
		}
	}

	function handleBuilderSave() {
		// Clear draft after successful save
		if (workflowBuilderRef) {
			workflowBuilderRef.clearDraftNow();
		}
		// Switch to workflow view after save
		uiStore.setView('workflow');
	}

	function handleBuilderCancel() {
		// Use uiStore navigation guard to check for unsaved changes
		if (!uiStore.requestNavigation('workflow')) {
			// Navigation was blocked, modal will show automatically
			return;
		}
		// Clear the new workflow and go back
		workflowStore.clearCurrentWorkflow();
	}

	// Unsaved changes handlers
	function handleSaveDraft() {
		if (workflowBuilderRef) {
			workflowBuilderRef.saveDraftNow();
		}
		// DON'T clear workflow - user might want to add recipes from library and come back
		// The workflow stays in memory while navigating to other views
		uiStore.confirmPendingNavigation();
	}

	function handleDiscardChanges() {
		// Clear the draft
		if (workflowBuilderRef) {
			workflowBuilderRef.clearDraftNow();
		}
		// Clear workflow since user is discarding changes
		workflowStore.clearCurrentWorkflow();
		uiStore.confirmPendingNavigation();
	}

	function handleCancelNavigation() {
		uiStore.clearPendingNavigation();
	}

	function handleBuilderEdgeUpdate(event: CustomEvent<{ edgeId: string; data: Partial<import('$lib/stores/workflow.svelte').WorkflowEdge> }>) {
		const { edgeId, data } = event.detail;

		// Sync all edges from workflow store to SvelteFlow store
		// This ensures the visual graph reflects the updated data
		if (workflowBuilderRef) {
			workflowBuilderRef.syncEdgesFromStore();
		}

		// Read the updated edge directly from the store to ensure we get latest values
		const latestEdge = workflowStore.currentWorkflow?.edges.find(e => e.id === edgeId);

		// Refresh selectedEdge to show updated data in the panel
		if (selectedEdge && latestEdge) {
			// Force refresh by creating a completely new object
			selectedEdge = {
				id: selectedEdge.id,
				source: selectedEdge.source,
				target: selectedEdge.target,
				label: latestEdge.label,
				isConditional: latestEdge.is_conditional,
				condition: latestEdge.condition
			};
		}
	}

	function handleBuilderEdgeDelete(event: CustomEvent<string>) {
		const edgeId = event.detail;

		// Remove from SvelteFlow store directly via WorkflowBuilder reference
		if (workflowBuilderRef) {
			workflowBuilderRef.removeEdgeFromStore(edgeId);
		}

		// Clear selection
		selectedEdge = null;
	}

	function handleBuilderNodeSave(event: CustomEvent<{ nodeId: string; newId?: string; updates: Partial<import('$lib/stores/workflow.svelte').WorkflowNode> }>) {
		// Sync nodes from workflow store to SvelteFlow store
		if (workflowBuilderRef) {
			workflowBuilderRef.syncNodesFromStore();
			// Also sync edges in case the node ID changed and affected edge references
			workflowBuilderRef.syncEdgesFromStore();
		}

		// If node ID was changed, update the selection to the new ID
		if (event.detail.newId) {
			uiStore.selectNode(event.detail.newId);
		}
	}

	function handleBuilderNodeDelete(event: CustomEvent<{ nodeId: string }>) {
		// SvelteFlow sync is now automatic via $effect in WorkflowBuilder
		// Just clear the selection
		uiStore.selectNode(null);
	}
</script>

{#if currentView === 'builder'}
	<!-- Workflow Builder View -->
	<div class="flex-1 flex h-full overflow-hidden relative">
		<div class="flex-1 relative">
			<WorkflowBuilder
				bind:this={workflowBuilderRef}
				on:nodeSelect={handleBuilderNodeSelect}
				on:edgeSelect={handleBuilderEdgeSelect}
				on:save={handleBuilderSave}
				on:cancel={handleBuilderCancel}
			/>
		</div>

		<!-- Right panel for editing selected node/edge -->
		{#if selectedNodeId && currentWorkflow}
			{@const selectedNode = currentWorkflow.nodes.find(n => n.id === selectedNodeId)}
			{#if selectedNode}
				<NodeDetailsPanel
					node={selectedNode}
					startInEditMode={true}
					on:close={() => uiStore.selectNode(null)}
					on:save={handleBuilderNodeSave}
					on:delete={handleBuilderNodeDelete}
				/>
			{/if}
		{:else if selectedEdge && currentWorkflow}
			<EdgeDetailsPanel
				edge={selectedEdge}
				sourceNode={currentWorkflow.nodes.find(n => n.id === selectedEdge.source)}
				targetNode={currentWorkflow.nodes.find(n => n.id === selectedEdge.target)}
				editable={true}
				on:close={() => selectedEdge = null}
				on:update={handleBuilderEdgeUpdate}
				on:delete={handleBuilderEdgeDelete}
			/>
		{/if}
	</div>
{:else if currentView === 'home'}
	<!-- Home Dashboard View -->
	<div class="flex-1 w-full h-full">
		<HomeView />
	</div>
{:else if currentView === 'runs'}
	<!-- Runs View -->
	<div class="flex-1 w-full h-full">
		{#if selectedRun}
			<!-- Run Details View -->
			<RunDetailsView execution={selectedRun} />
		{:else}
			<!-- Runs List View -->
			<RunsListView />
		{/if}
	</div>
{:else if currentView === 'workflows'}
	<!-- Workflows List View -->
	<div class="flex-1 w-full h-full">
		<WorkflowsListView />
	</div>
{:else if currentView === 'library'}
	<!-- Library View (Recipes & Tools) -->
	<div class="flex-1 w-full h-full">
		<LibraryView
			on:addRecipe={async (e) => {
				const recipe = e.detail.recipe;
				console.log('[Add to Workflow] Recipe:', recipe.name, 'Nodes:', recipe.nodes?.length, 'Edges:', recipe.edges?.length);

				// Validate recipe has nodes
				if (!recipe.nodes || recipe.nodes.length === 0) {
					console.error('[Add to Workflow] Recipe has no nodes!');
					return;
				}

				// Check if we have an existing workflow to append to
				const existingWorkflow = workflowStore.currentWorkflow;
				if (!existingWorkflow) {
					console.log('[Add to Workflow] Creating new workflow...');
					workflowStore.createNewWorkflow();
				} else {
					console.log('[Add to Workflow] Appending to existing workflow:', existingWorkflow.name, 'with', existingWorkflow.nodes.length, 'nodes');
				}

				// Add recipe nodes and edges to the current workflow as a subgraph
				const result = workflowStore.addRecipeToWorkflow(recipe.nodes, recipe.edges, undefined, recipe.name);
				console.log('[Add to Workflow] Added subgraph, result:', result);

				// Switch to builder to see the result
				uiStore.setView('builder');
				console.log('[Add to Workflow] Switched to builder view');

				// Wait for the DOM to update (WorkflowBuilder needs to mount)
				await tick();
				await tick(); // Double tick to ensure full render cycle

				// Sync the builder after it has mounted
				if (workflowBuilderRef) {
					workflowBuilderRef.syncNodesFromStore();
					workflowBuilderRef.syncEdgesFromStore();
					console.log('[Add to Workflow] Synced builder');
				} else {
					console.log('[Add to Workflow] No builder ref yet, relying on $effect');
				}
			}}
		/>
	</div>
{:else if currentView === 'models'}
	<!-- Models View -->
	<div class="flex-1 w-full h-full">
		<ModelsView />
	</div>
{:else}
	<!-- Workflow View -->
	<div class="flex-1 flex flex-col h-full">
		<!-- Header -->
		<header class="h-14 flex items-center justify-between px-6 border-b border-gray-200 dark:border-gray-800 bg-surface flex-shrink-0">
			<div class="flex items-center gap-4">
				{#if currentWorkflow}
					<h1 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
						{currentWorkflow.name}
					</h1>
					<span class="text-sm text-gray-500">
						{currentWorkflow.nodes.length} nodes · {currentWorkflow.edges.length} edges
					</span>
				{:else}
					<h1 class="text-lg font-semibold text-gray-500">
						Select a workflow to get started
					</h1>
				{/if}
			</div>

			<div class="flex items-center gap-2">
				{#if currentWorkflow}
					<button
						onclick={() => sygraFlowRef?.applyAutoLayout()}
						title="Auto-arrange nodes using DAG layout"
						class="flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
					>
						<LayoutGrid size={16} />
						Auto Layout
					</button>
				{/if}
				{#if currentExecution?.status === 'running' || currentExecution?.status === 'pending'}
					<button
						onclick={handleCancel}
						class="flex items-center gap-2 px-4 py-2 bg-red-100 hover:bg-red-200 dark:bg-red-900/30 dark:hover:bg-red-900/50 rounded-lg text-red-700 dark:text-red-400 text-sm font-medium transition-colors"
					>
						<StopCircle size={16} />
						Cancel
					</button>
				{:else if currentWorkflow}
					<button
						onclick={openRunModal}
						class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-white text-sm font-medium transition-colors"
					>
						<Play size={16} />
						Run Workflow
					</button>
				{/if}
			</div>
		</header>

		<!-- Main content area -->
		<div class="flex-1 flex flex-col overflow-hidden">
			<!-- Graph and details panels -->
			<div class="flex-1 flex overflow-hidden relative min-h-0">
				<!-- Graph canvas -->
				<div class="flex-1 relative">
					{#if currentWorkflow}
						<SygraFlow
							bind:this={sygraFlowRef}
							workflow={currentWorkflow}
							execution={currentExecution}
							on:nodeSelect={handleNodeSelect}
							on:edgeSelect={handleEdgeSelect}
						/>
					{:else}
						<div class="h-full flex items-center justify-center">
							<div class="text-center">
								<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
									<Play size={32} class="text-violet-500" />
								</div>
								<h2 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
									No workflow selected
								</h2>
								<p class="text-sm text-gray-500">
									Choose a workflow from the sidebar to visualize and run it
								</p>
							</div>
						</div>
					{/if}
				</div>

				<!-- Node details panel -->
				{#if selectedNodeId && currentWorkflow}
					<NodeDetailsPanel
						node={currentWorkflow.nodes.find(n => n.id === selectedNodeId)}
						nodeState={currentExecution?.node_states[selectedNodeId]}
						on:close={() => uiStore.selectNode(null)}
					/>
				{/if}

				<!-- Edge details panel -->
				{#if selectedEdge && currentWorkflow}
					{@const edge = selectedEdge}
					<EdgeDetailsPanel
						edge={edge}
						sourceNode={currentWorkflow.nodes.find(n => n.id === edge.source)}
						targetNode={currentWorkflow.nodes.find(n => n.id === edge.target)}
						on:close={() => selectedEdge = null}
					/>
				{/if}
			</div>

			<!-- Code Panel (YAML and Python code) - always visible at bottom -->
			{#if currentWorkflow}
				<WorkflowCodePanel
					workflowId={currentWorkflow.id}
					bind:isCollapsed={codePanelCollapsed}
					on:close={() => codePanelCollapsed = true}
				/>
			{/if}
		</div>

		<!-- Execution status bar -->
		{#if currentExecution}
			<ExecutionPanel execution={currentExecution} />
		{/if}
	</div>

	<!-- Modals -->
	{#if showRunModal && currentWorkflow}
		<RunWorkflowModal
			workflowName={currentWorkflow.name}
			workflowId={currentWorkflow.id}
			dataConfig={currentWorkflow.data_config}
			nodeCount={currentWorkflow.nodes?.length ?? 0}
			on:run={handleRun}
			on:close={closeRunModal}
		/>
	{/if}

	{#if showResultsModal && currentExecution}
		<ResultsModal
			execution={currentExecution}
			on:close={() => uiStore.closeResultsModal()}
		/>
	{/if}
{/if}

<!-- Global dark overlay when right sidebar is open (covers entire viewport including left sidebar) -->
{#if (selectedNodeId || selectedEdge) && (currentView === 'builder' || (currentView === 'workflow' && currentWorkflow))}
	<button
		class="fixed inset-0 bg-black/20 dark:bg-black/40 transition-opacity duration-200 cursor-default z-30"
		onclick={() => { uiStore.selectNode(null); selectedEdge = null; }}
		aria-label="Close panel"
	></button>
{/if}

<!-- Unsaved Changes Modal -->
{#if showUnsavedChangesModal}
	<UnsavedChangesModal
		on:saveDraft={handleSaveDraft}
		on:discard={handleDiscardChanges}
		on:cancel={handleCancelNavigation}
	/>
{/if}
