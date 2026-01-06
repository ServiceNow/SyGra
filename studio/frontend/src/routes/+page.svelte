<script lang="ts">
	import { tick } from 'svelte';
	import { workflowStore, executionStore, uiStore, type Execution } from '$lib/stores/workflow.svelte';
	// Keep lightweight/always-needed imports static
	import UnsavedChangesModal from '$lib/components/builder/UnsavedChangesModal.svelte';
	// WorkflowBuilder needs static import for proper drag-drop functionality
	import WorkflowBuilder from '$lib/components/builder/WorkflowBuilder.svelte';
	import { Play, StopCircle, LayoutGrid, Loader2 } from 'lucide-svelte';

	// Dynamic component types
	type SvelteComponent = typeof import('svelte').SvelteComponent;

	// Lazy-loaded component references
	let SygraFlow: SvelteComponent | null = $state(null);
	let NodeDetailsPanel: SvelteComponent | null = $state(null);
	let EdgeDetailsPanel: SvelteComponent | null = $state(null);
	let ExecutionPanel: SvelteComponent | null = $state(null);
	let ResultsModal: SvelteComponent | null = $state(null);
	let RunWorkflowModal: SvelteComponent | null = $state(null);
	let RunsListView: SvelteComponent | null = $state(null);
	let RunDetailsView: SvelteComponent | null = $state(null);
	let WorkflowsListView: SvelteComponent | null = $state(null);
	let HomeView: SvelteComponent | null = $state(null);
	let LibraryView: SvelteComponent | null = $state(null);
	let ModelsView: SvelteComponent | null = $state(null);
	let WorkflowCodePanel: SvelteComponent | null = $state(null);

	// Loading state for views
	let viewLoading = $state(false);

	// Load components based on current view
	async function loadComponentsForView(view: string) {
		viewLoading = true;
		try {
			switch (view) {
				case 'home':
					if (!HomeView) {
						HomeView = (await import('$lib/components/home/HomeView.svelte')).default;
					}
					break;
				case 'runs':
					if (!RunsListView) {
						RunsListView = (await import('$lib/components/runs/RunsListViewEnhanced.svelte')).default;
					}
					if (!RunDetailsView) {
						RunDetailsView = (await import('$lib/components/runs/RunDetailsViewEnhanced.svelte')).default;
					}
					break;
				case 'workflows':
					if (!WorkflowsListView) {
						WorkflowsListView = (await import('$lib/components/workflows/WorkflowsListView.svelte')).default;
					}
					break;
				case 'library':
					if (!LibraryView) {
						LibraryView = (await import('$lib/components/library/LibraryView.svelte')).default;
					}
					break;
				case 'models':
					if (!ModelsView) {
						ModelsView = (await import('$lib/components/models/ModelsView.svelte')).default;
					}
					break;
				case 'builder':
					// WorkflowBuilder is statically imported for proper drag-drop functionality
					if (!NodeDetailsPanel) {
						NodeDetailsPanel = (await import('$lib/components/graph/NodeDetailsPanel.svelte')).default;
					}
					if (!EdgeDetailsPanel) {
						EdgeDetailsPanel = (await import('$lib/components/graph/EdgeDetailsPanel.svelte')).default;
					}
					if (!WorkflowCodePanel) {
						WorkflowCodePanel = (await import('$lib/components/code/WorkflowCodePanel.svelte')).default;
					}
					break;
				case 'workflow':
				default:
					// Workflow view components
					if (!SygraFlow) {
						SygraFlow = (await import('$lib/components/graph/SygraFlow.svelte')).default;
					}
					if (!NodeDetailsPanel) {
						NodeDetailsPanel = (await import('$lib/components/graph/NodeDetailsPanel.svelte')).default;
					}
					if (!EdgeDetailsPanel) {
						EdgeDetailsPanel = (await import('$lib/components/graph/EdgeDetailsPanel.svelte')).default;
					}
					if (!ExecutionPanel) {
						ExecutionPanel = (await import('$lib/components/execution/ExecutionPanel.svelte')).default;
					}
					if (!ResultsModal) {
						ResultsModal = (await import('$lib/components/execution/ResultsModal.svelte')).default;
					}
					if (!RunWorkflowModal) {
						RunWorkflowModal = (await import('$lib/components/execution/RunWorkflowModal.svelte')).default;
					}
					if (!WorkflowCodePanel) {
						WorkflowCodePanel = (await import('$lib/components/code/WorkflowCodePanel.svelte')).default;
					}
					break;
			}
		} finally {
			viewLoading = false;
		}
	}

	// React to view changes and load components
	$effect(() => {
		const view = uiStore.currentView;
		loadComponentsForView(view);
	});

	// Read version to force re-evaluation when workflow is updated
	let _version = $derived(workflowStore.workflowVersion);
	let currentWorkflow = $derived.by(() => {
		// Depend on version to force re-evaluation on updates
		const _v = workflowStore.workflowVersion;
		return workflowStore.currentWorkflow;
	});

	// Track workflow ID to detect workflow switches
	let previousWorkflowId = $state<string | null>(null);

	// Clear execution state when switching to a different workflow
	$effect(() => {
		const currentId = currentWorkflow?.id ?? null;
		if (previousWorkflowId !== null && currentId !== previousWorkflowId) {
			// Workflow changed - clear the execution state
			executionStore.clearExecution();
		}
		previousWorkflowId = currentId;
	});

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

	// Node navigation - get sorted list of node IDs for prev/next navigation
	let sortedNodeIds = $derived(() => {
		if (!currentWorkflow) return [];
		// Sort nodes by position (top to bottom, left to right)
		return [...currentWorkflow.nodes]
			.sort((a, b) => {
				const posA = a.position || { x: 0, y: 0 };
				const posB = b.position || { x: 0, y: 0 };
				// Primary sort by Y (top to bottom), secondary by X (left to right)
				if (Math.abs(posA.y - posB.y) > 50) return posA.y - posB.y;
				return posA.x - posB.x;
			})
			.map(n => n.id);
	});

	// Navigation state for selected node
	let selectedNodeIndex = $derived(() => {
		if (!selectedNodeId) return -1;
		return sortedNodeIds().indexOf(selectedNodeId);
	});

	let hasPreviousNode = $derived(() => selectedNodeIndex() > 0);
	let hasNextNode = $derived(() => {
		const ids = sortedNodeIds();
		return selectedNodeIndex() >= 0 && selectedNodeIndex() < ids.length - 1;
	});
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

	// Reference to WorkflowCodePanel for refreshing after UI changes
	let codePanelRef = $state<{
		refresh: () => void;
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
		console.log('[handleBuilderNodeSave] Called with:', event.detail);

		// Sync nodes from workflow store to SvelteFlow store
		if (workflowBuilderRef) {
			console.log('[handleBuilderNodeSave] Calling syncNodesFromStore...');
			workflowBuilderRef.syncNodesFromStore();
			// Also sync edges in case the node ID changed and affected edge references
			workflowBuilderRef.syncEdgesFromStore();
		} else {
			console.warn('[handleBuilderNodeSave] workflowBuilderRef is undefined!');
		}

		// Refresh the code panel to show updated YAML
		if (codePanelRef) {
			console.log('[handleBuilderNodeSave] Refreshing code panel...');
			codePanelRef.refresh();
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

	// Node navigation handlers
	function handleNavigateToPreviousNode() {
		const ids = sortedNodeIds();
		const currentIndex = selectedNodeIndex();
		if (currentIndex > 0) {
			uiStore.selectNode(ids[currentIndex - 1]);
		}
	}

	function handleNavigateToNextNode() {
		const ids = sortedNodeIds();
		const currentIndex = selectedNodeIndex();
		if (currentIndex >= 0 && currentIndex < ids.length - 1) {
			uiStore.selectNode(ids[currentIndex + 1]);
		}
	}

	function handleNavigateToNode(event: CustomEvent<string>) {
		const nodeId = event.detail;
		uiStore.selectNode(nodeId);
		selectedEdge = null;
	}

	function handleDuplicateNode(event: CustomEvent<string>) {
		const nodeId = event.detail;
		const node = currentWorkflow?.nodes.find(n => n.id === nodeId);
		if (!node || !currentWorkflow) return;

		// Generate incremental ID for the duplicate node
		const nodeType = node.node_type;
		const existingIds = currentWorkflow.nodes
			.filter(n => n.id.startsWith(`${nodeType}_`))
			.map(n => {
				const match = n.id.match(new RegExp(`^${nodeType}_(\\d+)$`));
				return match ? parseInt(match[1], 10) : 0;
			});
		const nextNum = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1;
		const newId = `${nodeType}_${nextNum}`;

		const newNode = {
			...structuredClone(node),
			id: newId,
			summary: `${node.summary} (Copy)`,
			position: node.position ? {
				x: node.position.x + 100,
				y: node.position.y + 50
			} : undefined
		};

		// Add the duplicated node to the workflow
		workflowStore.updateNode(newId, newNode);

		// Sync the builder UI
		if (workflowBuilderRef) {
			workflowBuilderRef.syncNodesFromStore();
		}

		// Select the new node
		uiStore.selectNode(newId);
	}

	// Handle YAML saved in code panel - reload workflow and sync visual UI
	async function handleYamlSaved() {
		console.log('[handleYamlSaved] YAML saved, reloading workflow...');
		// Reload workflow from backend to get updated data
		await workflowStore.reloadCurrentWorkflow();
		// Sync the visual UI
		if (workflowBuilderRef) {
			workflowBuilderRef.syncNodesFromStore();
			workflowBuilderRef.syncEdgesFromStore();
		}
	}
</script>

<!-- Loading spinner component -->
{#snippet loadingSpinner()}
	<div class="flex-1 flex items-center justify-center">
		<div class="flex flex-col items-center gap-3">
			<Loader2 size={32} class="animate-spin text-[#52B8FF]" />
			<span class="text-sm text-gray-500">Loading...</span>
		</div>
	</div>
{/snippet}

{#if currentView === 'builder'}
	<!-- Workflow Builder View -->
	<div class="flex-1 flex flex-col h-full overflow-hidden">
		<!-- Main builder area -->
		<div class="flex-1 flex overflow-hidden relative min-h-0">
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
			{#if selectedNodeId && currentWorkflow && NodeDetailsPanel}
				{@const selectedNode = currentWorkflow.nodes.find(n => n.id === selectedNodeId)}
				{#if selectedNode}
					<svelte:component
						this={NodeDetailsPanel}
						node={selectedNode}
						startInEditMode={true}
						showNavigation={true}
						hasPrevious={hasPreviousNode()}
						hasNext={hasNextNode()}
						onPrevious={handleNavigateToPreviousNode}
						onNext={handleNavigateToNextNode}
						onDuplicate={() => handleDuplicateNode({ detail: selectedNodeId } as CustomEvent<string>)}
						on:close={() => uiStore.selectNode(null)}
						on:save={handleBuilderNodeSave}
						on:delete={handleBuilderNodeDelete}
						on:navigate={handleNavigateToNode}
					/>
				{/if}
			{:else if selectedEdge && currentWorkflow && EdgeDetailsPanel}
				<svelte:component
					this={EdgeDetailsPanel}
					edge={selectedEdge}
					sourceNode={currentWorkflow.nodes.find(n => n.id === selectedEdge.source)}
					targetNode={currentWorkflow.nodes.find(n => n.id === selectedEdge.target)}
					editable={true}
					on:close={() => selectedEdge = null}
					on:update={handleBuilderEdgeUpdate}
					on:delete={handleBuilderEdgeDelete}
					on:navigate={handleNavigateToNode}
				/>
			{/if}
		</div>

		<!-- Code Panel (YAML and Python code) for builder view -->
		{#if currentWorkflow && !currentWorkflow.id.startsWith('new_') && WorkflowCodePanel}
			<svelte:component
				this={WorkflowCodePanel}
				bind:this={codePanelRef}
				workflowId={currentWorkflow.id}
				bind:isCollapsed={codePanelCollapsed}
				on:close={() => codePanelCollapsed = true}
				on:yamlSaved={handleYamlSaved}
			/>
		{/if}
	</div>
{:else if currentView === 'home'}
	<!-- Home Dashboard View -->
	<div class="flex-1 w-full h-full">
		{#if HomeView}
			<svelte:component this={HomeView} />
		{:else}
			{@render loadingSpinner()}
		{/if}
	</div>
{:else if currentView === 'runs'}
	<!-- Runs View -->
	<div class="flex-1 w-full h-full">
		{#if selectedRun && RunDetailsView}
			<!-- Run Details View -->
			<svelte:component this={RunDetailsView} execution={selectedRun} />
		{:else if RunsListView}
			<!-- Runs List View -->
			<svelte:component this={RunsListView} />
		{:else}
			{@render loadingSpinner()}
		{/if}
	</div>
{:else if currentView === 'workflows'}
	<!-- Workflows List View -->
	<div class="flex-1 w-full h-full">
		{#if WorkflowsListView}
			<svelte:component this={WorkflowsListView} />
		{:else}
			{@render loadingSpinner()}
		{/if}
	</div>
{:else if currentView === 'library'}
	<!-- Library View (Recipes & Tools) -->
	<div class="flex-1 w-full h-full">
		{#if LibraryView}
			<svelte:component
				this={LibraryView}
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
		{:else}
			{@render loadingSpinner()}
		{/if}
	</div>
{:else if currentView === 'models'}
	<!-- Models View -->
	<div class="flex-1 w-full h-full">
		{#if ModelsView}
			<svelte:component this={ModelsView} />
		{:else}
			{@render loadingSpinner()}
		{/if}
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
						class="flex items-center gap-2 px-4 py-2 bg-[#63DF4E] hover:bg-[#4BC93A] rounded-lg text-[#032D42] text-sm font-semibold transition-colors"
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
					{#if currentWorkflow && SygraFlow}
						<svelte:component
							this={SygraFlow}
							bind:this={sygraFlowRef}
							workflow={currentWorkflow}
							execution={currentExecution}
							on:nodeSelect={handleNodeSelect}
							on:edgeSelect={handleEdgeSelect}
						/>
					{:else if currentWorkflow && !SygraFlow}
						{@render loadingSpinner()}
					{:else}
						<div class="h-full flex items-center justify-center">
							<div class="text-center">
								<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#032D42]/20 to-[#52B8FF]/20 flex items-center justify-center">
									<Play size={32} class="text-[#52B8FF]" />
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
				{#if selectedNodeId && currentWorkflow && NodeDetailsPanel}
					<svelte:component
						this={NodeDetailsPanel}
						node={currentWorkflow.nodes.find(n => n.id === selectedNodeId)}
						nodeState={currentExecution?.node_states[selectedNodeId]}
						showNavigation={true}
						hasPrevious={hasPreviousNode()}
						hasNext={hasNextNode()}
						onPrevious={handleNavigateToPreviousNode}
						onNext={handleNavigateToNextNode}
						on:close={() => uiStore.selectNode(null)}
						on:navigate={handleNavigateToNode}
					/>
				{/if}

				<!-- Edge details panel -->
				{#if selectedEdge && currentWorkflow && EdgeDetailsPanel}
					{@const edge = selectedEdge}
					<svelte:component
						this={EdgeDetailsPanel}
						edge={edge}
						sourceNode={currentWorkflow.nodes.find(n => n.id === edge.source)}
						targetNode={currentWorkflow.nodes.find(n => n.id === edge.target)}
						on:close={() => selectedEdge = null}
						on:navigate={handleNavigateToNode}
					/>
				{/if}
			</div>

			<!-- Code Panel (YAML and Python code) - always visible at bottom -->
			{#if currentWorkflow && WorkflowCodePanel}
				<svelte:component
					this={WorkflowCodePanel}
					bind:this={codePanelRef}
					workflowId={currentWorkflow.id}
					bind:isCollapsed={codePanelCollapsed}
					on:close={() => codePanelCollapsed = true}
					on:yamlSaved={handleYamlSaved}
				/>
			{/if}
		</div>

		<!-- Execution status bar -->
		{#if currentExecution && ExecutionPanel}
			<svelte:component this={ExecutionPanel} execution={currentExecution} />
		{/if}
	</div>

	<!-- Modals -->
	{#if showRunModal && currentWorkflow && RunWorkflowModal}
		<svelte:component
			this={RunWorkflowModal}
			workflowName={currentWorkflow.name}
			workflowId={currentWorkflow.id}
			dataConfig={currentWorkflow.data_config}
			nodeCount={currentWorkflow.nodes?.length ?? 0}
			on:run={handleRun}
			on:close={closeRunModal}
		/>
	{/if}

	{#if showResultsModal && currentExecution && ResultsModal}
		<svelte:component
			this={ResultsModal}
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
