<script lang="ts">
	import { createEventDispatcher, onMount, onDestroy, tick } from 'svelte';
	import {
		SvelteFlow,
		Controls,
		Background,
		MiniMap,
		Panel,
		type Node,
		type Edge,
		type NodeTypes,
		type EdgeTypes,
		type Connection,
		ConnectionLineType,
		Position,
		MarkerType,
		SelectionMode
	} from '@xyflow/svelte';
	import { writable, get } from 'svelte/store';
	import { workflowStore, uiStore, NODE_TYPES, NODE_CATEGORIES, type Workflow, type WorkflowNode } from '$lib/stores/workflow.svelte';
	import {
		Play, Square, Bot, Zap, Boxes, GitBranch, Shuffle,
		Save, X, Database, Download, GripVertical, LayoutGrid, Group,
		Search, ChevronDown, ChevronRight, Sparkles, FilePlus2, Trash2, MousePointerClick,
		Map as MapIcon, EyeOff
	} from 'lucide-svelte';

	// Node components
	import StartNode from '../graph/renderers/nodes/StartNode.svelte';
	import EndNode from '../graph/renderers/nodes/EndNode.svelte';
	import LLMNode from '../graph/renderers/nodes/LLMNode.svelte';
	import LambdaNode from '../graph/renderers/nodes/LambdaNode.svelte';
	import SubgraphNode from '../graph/renderers/nodes/SubgraphNode.svelte';
	import DataNode from '../graph/renderers/nodes/DataNode.svelte';
	import OutputNode from '../graph/renderers/nodes/OutputNode.svelte';
	import WeightedSamplerNode from '../graph/renderers/nodes/WeightedSamplerNode.svelte';
	import AgentNode from '../graph/renderers/nodes/AgentNode.svelte';

	// Edge component
	import SygraEdge from '../graph/renderers/edges/SygraEdge.svelte';

	// Modals
	import GroupSubgraphModal from './GroupSubgraphModal.svelte';
	import SaveRecipeModal from './SaveRecipeModal.svelte';
	import RecipePickerModal from './RecipePickerModal.svelte';
	import SaveWorkflowModal from './SaveWorkflowModal.svelte';

	// FitView helper (must be inside SvelteFlow to use useSvelteFlow hook)
	import FitViewHelper from '../graph/FitViewHelper.svelte';

	// Recipe store
	import { recipeStore, type Recipe } from '$lib/stores/recipe.svelte';

	// Import SvelteFlow styles
	import '@xyflow/svelte/dist/style.css';

	const dispatch = createEventDispatcher<{
		nodeSelect: string;
		edgeSelect: { id: string; source: string; target: string } | null;
		save: void;
		cancel: void;
	}>();

	let workflow = $derived(workflowStore.currentWorkflow);

	// Edit state
	let workflowName = $state('Untitled Workflow');
	let workflowDescription = $state('');
	let isSaving = $state(false);
	let hasChanges = $state(true);
	let showSaveModal = $state(false);
	let lastAutoSave = $state<Date | null>(null);
	let autoSaveInterval: ReturnType<typeof setInterval> | null = null;
	const AUTOSAVE_INTERVAL = 30000; // 30 seconds
	const DRAFT_KEY = 'sygra_workflow_draft';

	// Dragging state
	let draggedNodeType = $state<string | null>(null);

	// Multi-selection state
	let selectedNodeIds = $state<string[]>([]);
	let selectedEdgeIds = $state<string[]>([]);
	let showGroupModal = $state(false);

	// Recipe modal state
	let showRecipeModal = $state(false);
	let recipeNodes = $state<WorkflowNode[]>([]);
	let recipeEdges = $state<{ id: string; source: string; target: string; label?: string; is_conditional: boolean }[]>([]);
	let recipeSuggestedName = $state('');

	// Minimap visibility state
	let showMinimap = $state(true);

	// Recipe picker for subgraph nodes
	let showRecipePicker = $state(false);
	let recipePickerPosition = $state({ x: 0, y: 0 });

	// Reset confirmation state
	let showResetConfirm = $state(false);

	// Dark mode detection
	let isDarkMode = $state(false);

	// Track modifier keys at click time (use plain variable for synchronous access)
	let lastClickHadModifier = false;
	let canvasRef: HTMLDivElement | null = null;

	// Handler to capture modifier state on pointerdown (before SvelteFlow processes)
	function handleCanvasPointerDown(e: PointerEvent | MouseEvent) {
		lastClickHadModifier = e.metaKey || e.ctrlKey;
	}

	// Set up capture phase listener for pointer events
	onMount(() => {
		const setupListener = () => {
			if (canvasRef) {
				canvasRef.addEventListener('pointerdown', handleCanvasPointerDown, true);
			}
		};
		// Small delay to ensure ref is bound
		setTimeout(setupListener, 0);

		return () => {
			if (canvasRef) {
				canvasRef.removeEventListener('pointerdown', handleCanvasPointerDown, true);
			}
		};
	});

	$effect(() => {
		// Check initial dark mode state
		isDarkMode = document.documentElement.classList.contains('dark');

		// Watch for dark mode changes
		const observer = new MutationObserver(() => {
			isDarkMode = document.documentElement.classList.contains('dark');
		});
		observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

		return () => observer.disconnect();
	});

	// Sync hasChanges with uiStore for navigation guard
	$effect(() => {
		uiStore.setBuilderHasChanges(hasChanges);
	});

	// Track if we've initialized from draft
	let draftRestored = $state(false);

	// Auto-save to localStorage (drafts) and restore on mount
	$effect(() => {
		// Start auto-save interval
		autoSaveInterval = setInterval(() => {
			if (hasChanges && workflow) {
				saveDraft();
			}
		}, AUTOSAVE_INTERVAL);

		// Restore existing draft on mount (only once)
		// The builder is for creating NEW workflows, so we should restore drafts
		if (!draftRestored) {
			const savedDraft = localStorage.getItem(DRAFT_KEY);
			if (savedDraft) {
				try {
					const draft = JSON.parse(savedDraft);
					if (draft.workflow) {
						// Restore draft if:
						// 1. No workflow is loaded, OR
						// 2. Current workflow is NOT a draft (user was viewing an existing workflow
						//    and returned to builder - their draft should be restored)
						// Do NOT restore if current workflow IS a draft (e.g., recipe was just added)
						const isCurrentWorkflowDraft = workflow?.id?.startsWith('new_');
						const shouldRestore = !workflow || !isCurrentWorkflowDraft;

						if (shouldRestore) {
							workflowStore.setCurrentWorkflow(draft.workflow);
							workflowName = draft.workflow.name || 'Untitled Workflow';
							workflowDescription = draft.workflow.description || '';
							hasChanges = true;
						}
					}
				} catch (e) {
					console.error('Failed to parse draft:', e);
				}
			}
			draftRestored = true;
		}

		return () => {
			if (autoSaveInterval) {
				clearInterval(autoSaveInterval);
			}
		};
	});

	// Save draft to localStorage
	function saveDraft() {
		if (!workflow) return;

		const draft = {
			workflow: {
				...workflow,
				name: workflowName,
				description: workflowDescription
			},
			savedAt: new Date().toISOString()
		};

		try {
			localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
			lastAutoSave = new Date();
		} catch (e) {
			console.error('Failed to save draft:', e);
		}
	}

	// Clear draft after successful save
	function clearDraft() {
		localStorage.removeItem(DRAFT_KEY);
		lastAutoSave = null;
	}

	// Initialize from workflow
	$effect(() => {
		if (workflow) {
			workflowName = workflow.name;
			workflowDescription = workflow.description || '';
		}
	});

	// Node type mapping
	const nodeTypes = {
		data: DataNode,
		start: StartNode,
		end: EndNode,
		output: OutputNode,
		llm: LLMNode,
		lambda: LambdaNode,
		subgraph: SubgraphNode,
		weighted_sampler: WeightedSamplerNode,
		agent: AgentNode
	} as unknown as NodeTypes;

	const edgeTypes = {
		sygra: SygraEdge
	} as unknown as EdgeTypes;

	// Node icons
	const nodeIcons: Record<string, any> = {
		data: Database,
		start: Play,
		end: Square,
		output: Download,
		llm: Bot,
		lambda: Zap,
		subgraph: Boxes,
		weighted_sampler: Shuffle,
		agent: Sparkles
	};

	// Search and category state for palette
	let paletteSearch = $state('');
	let expandedCategories = $state<Set<string>>(new Set(['flow', 'ai', 'data', 'processing']));

	// Filter nodes based on search
	let filteredNodeTypes = $derived(() => {
		if (!paletteSearch.trim()) return NODE_TYPES;
		const search = paletteSearch.toLowerCase();
		return NODE_TYPES.filter(n =>
			n.label.toLowerCase().includes(search) ||
			n.description.toLowerCase().includes(search) ||
			n.type.toLowerCase().includes(search)
		);
	});

	// Group filtered nodes by category
	let groupedNodeTypes = $derived(() => {
		const filtered = filteredNodeTypes();
		const groups: Record<string, typeof NODE_TYPES[number][]> = {};
		for (const cat of NODE_CATEGORIES) {
			const nodes = filtered.filter(n => n.category === cat.id);
			if (nodes.length > 0) {
				groups[cat.id] = nodes;
			}
		}
		return groups;
	});

	function toggleCategory(catId: string) {
		const newSet = new Set(expandedCategories);
		if (newSet.has(catId)) {
			newSet.delete(catId);
		} else {
			newSet.add(catId);
		}
		expandedCategories = newSet;
	}

	// Create Svelte stores for SvelteFlow
	const nodes = writable<Node[]>([]);
	const edges = writable<Edge[]>([]);

	// Store to trigger fitView - increment to trigger
	const fitViewTrigger = writable(0);

	// Track workflow ID to detect when we need to re-sync
	let lastWorkflowId = $state<string | null>(null);

	// Helper to convert workflow nodes to SvelteFlow nodes
	function workflowNodesToFlowNodes(workflowNodes: WorkflowNode[]): Node[] {
		return workflowNodes.map(node => ({
			id: node.id,
			type: node.node_type,
			position: node.position,
			// Add _version to force SvelteFlow to detect data changes
			data: { ...node, _version: Date.now() },
			sourcePosition: Position.Right,
			targetPosition: Position.Left,
			selectable: true,
			draggable: true
		}));
	}

	// Helper to convert workflow edges to SvelteFlow edges
	function workflowEdgesToFlowEdges(workflowEdges: typeof workflow.edges): Edge[] {
		return workflowEdges.map(edge => ({
			id: edge.id,
			source: edge.source,
			target: edge.target,
			type: 'sygra',
			selectable: true,
			markerEnd: {
				type: MarkerType.ArrowClosed,
				width: 12,
				height: 12,
				color: edge.is_conditional ? '#f59e0b' : '#6b7280'
			},
			data: {
				label: edge.label,
				isConditional: edge.is_conditional
			}
		}));
	}

	// Track workflow nodes/edges count to detect deletions and additions
	let lastNodesCount = $state(0);
	let lastEdgesCount = $state(0);
	let lastWorkflowVersion = $state(0);

	// Sync from workflow to stores when workflow changes (ID, nodes count, or edges count)
	$effect(() => {
		if (workflow) {
			const isNewWorkflow = workflow.id !== lastWorkflowId;
			const nodesChanged = workflow.nodes.length !== lastNodesCount;
			const edgesChanged = workflow.edges.length !== lastEdgesCount;

			if (isNewWorkflow || nodesChanged || edgesChanged) {
				lastWorkflowId = workflow.id;
				lastNodesCount = workflow.nodes.length;
				lastEdgesCount = workflow.edges.length;
				nodes.set(workflowNodesToFlowNodes(workflow.nodes));
				edges.set(workflowEdgesToFlowEdges(workflow.edges));

				// Trigger fitView when a new workflow is loaded
				if (isNewWorkflow) {
					tick().then(() => {
						fitViewTrigger.update(n => n + 1);
					});
				}
			}
		}
	});

	// Also sync when workflowVersion changes (node data updates like model changes)
	$effect(() => {
		const currentVersion = workflowStore.workflowVersion;
		// Read directly from store to ensure we get the latest data
		const currentWf = workflowStore.currentWorkflow;
		if (currentVersion > lastWorkflowVersion && currentWf) {
			lastWorkflowVersion = currentVersion;
			// Sync nodes when version changes (handles data updates within nodes)
			nodes.set(workflowNodesToFlowNodes(currentWf.nodes));
			edges.set(workflowEdgesToFlowEdges(currentWf.edges));
		}
	});

	// Force sync edges from workflow store to SvelteFlow
	export function syncEdgesFromStore() {
		// Read directly from store to ensure we get the latest data
		const currentWf = workflowStore.currentWorkflow;
		if (currentWf) {
			edges.set(workflowEdgesToFlowEdges(currentWf.edges));
		}
	}

	// Force sync nodes from workflow store to SvelteFlow
	export function syncNodesFromStore() {
		// Read directly from store to ensure we get the latest data
		const currentWf = workflowStore.currentWorkflow;
		if (currentWf) {
			nodes.set(workflowNodesToFlowNodes(currentWf.nodes));
		}
	}

	// Update a specific edge in SvelteFlow store
	export function updateEdgeInStore(edgeId: string, data: { label?: string; is_conditional?: boolean }) {
		edges.update(currentEdges => {
			return currentEdges.map(edge => {
				if (edge.id === edgeId) {
					return {
						...edge,
						markerEnd: {
							type: MarkerType.ArrowClosed,
							width: 12,
							height: 12,
							color: data.is_conditional ? '#f59e0b' : '#6b7280'
						},
						data: {
							...edge.data,
							label: data.label,
							isConditional: data.is_conditional
						}
					};
				}
				return edge;
			});
		});
	}

	// Remove an edge from SvelteFlow store
	export function removeEdgeFromStore(edgeId: string) {
		edges.update(currentEdges => currentEdges.filter(e => e.id !== edgeId));
	}

	// Draft management exports
	export function getHasChanges(): boolean {
		return hasChanges;
	}

	export function saveDraftNow(): void {
		saveDraft();
	}

	export function clearDraftNow(): void {
		clearDraft();
	}

	export interface DraftInfo {
		name: string;
		savedAt: Date;
		nodeCount: number;
		workflow: Workflow;
	}

	export function getDraftInfo(): DraftInfo | null {
		const savedDraft = localStorage.getItem(DRAFT_KEY);
		if (!savedDraft) return null;

		try {
			const draft = JSON.parse(savedDraft);
			if (draft.workflow) {
				return {
					name: draft.workflow.name || 'Untitled Workflow',
					savedAt: new Date(draft.savedAt),
					nodeCount: draft.workflow.nodes?.length || 0,
					workflow: draft.workflow
				};
			}
		} catch (e) {
			console.error('Failed to parse draft:', e);
		}
		return null;
	}

	export function restoreDraft(): boolean {
		const draftInfo = getDraftInfo();
		if (!draftInfo) return false;

		// Set the workflow in the store
		workflowStore.setCurrentWorkflow(draftInfo.workflow);

		// Update local state
		workflowName = draftInfo.workflow.name || 'Untitled Workflow';
		workflowDescription = draftInfo.workflow.description || '';
		hasChanges = true;

		// Sync to SvelteFlow
		syncNodesFromStore();
		syncEdgesFromStore();

		return true;
	}

	export function startFresh(): void {
		// Clear any existing draft
		clearDraft();

		// Create a new blank workflow with just Start and End nodes
		workflowStore.createNewWorkflow();

		// Reset local state
		workflowName = 'Untitled Workflow';
		workflowDescription = '';
		hasChanges = true;

		// Sync to SvelteFlow
		syncNodesFromStore();
		syncEdgesFromStore();
	}

	// Handle drag start from palette
	function handleDragStart(e: DragEvent, nodeType: string) {
		if (e.dataTransfer) {
			e.dataTransfer.setData('application/sygra-node', nodeType);
			e.dataTransfer.effectAllowed = 'copy';
		}
		draggedNodeType = nodeType;
	}

	function handleDragEnd() {
		draggedNodeType = null;
	}

	// Handle drop on canvas
	function handleDrop(e: DragEvent) {
		e.preventDefault();
		const nodeType = e.dataTransfer?.getData('application/sygra-node');

		if (nodeType && workflow) {
			// Calculate position relative to the flow container
			const flowBounds = (e.currentTarget as HTMLElement).getBoundingClientRect();
			const position = {
				x: e.clientX - flowBounds.left - 75, // Center the node
				y: e.clientY - flowBounds.top - 30
			};

			// For subgraph nodes, show recipe picker first
			if (nodeType === 'subgraph') {
				recipePickerPosition = position;
				showRecipePicker = true;
				draggedNodeType = null;
				return;
			}

			addNodeAtPosition(nodeType, position);
		}
		draggedNodeType = null;
	}

	// Add a node at a specific position
	function addNodeAtPosition(nodeType: string, position: { x: number; y: number }) {
		workflowStore.pushUndo();
		const newNode = workflowStore.addNode(nodeType, position);
		if (newNode) {
			// Also add to SvelteFlow nodes store directly
			nodes.update(n => [...n, {
				id: newNode.id,
				type: newNode.node_type,
				position: newNode.position,
				data: { ...newNode },
				sourcePosition: Position.Right,
				targetPosition: Position.Left,
				selectable: true,
				draggable: true
			}]);
			hasChanges = true;
			// Don't auto-select the node on drop - only on click
			// dispatch('nodeSelect', newNode.id);
		}
		return newNode;
	}

	// Handle recipe selection for subgraph
	function handleRecipeSelect(event: CustomEvent<{ recipe: Recipe | null; position: { x: number; y: number } }>) {
		const { recipe, position } = event.detail;
		showRecipePicker = false;

		workflowStore.pushUndo();
		if (recipe) {
			// Add recipe as a subgraph node at the drop position
			workflowStore.addRecipeToWorkflow(recipe.nodes, recipe.edges, position, recipe.name);
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
		} else {
			// Create an empty subgraph node
			addNodeAtPosition('subgraph', position);
		}
	}

	// Handle expanding/detaching a subgraph
	function handleExpandSubgraph(event: CustomEvent<{ nodeId: string }>) {
		const { nodeId } = event.detail;
		workflowStore.pushUndo();
		const result = workflowStore.expandSubgraph(nodeId);
		if (result) {
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'copy';
		}
	}

	// Handle node position changes
	function handleNodeDragStop(event: CustomEvent<{ nodes: Node[] }>) {
		const movedNodes = event.detail.nodes;
		movedNodes.forEach(node => {
			workflowStore.updateNodePosition(node.id, node.position);
		});
		hasChanges = true;
	}

	// Validate connection based on node types
	function validateConnection(sourceId: string, targetId: string): { valid: boolean; message?: string } {
		const sourceNode = workflow?.nodes.find(n => n.id === sourceId);
		const targetNode = workflow?.nodes.find(n => n.id === targetId);

		if (!sourceNode || !targetNode) return { valid: true };

		// Rule 1: Only Data nodes can connect TO Start nodes
		if (targetNode.node_type === 'start' && sourceNode.node_type !== 'data') {
			return { valid: false, message: 'Only Data nodes can connect to Start nodes' };
		}

		// Rule 2: Data nodes can ONLY connect to Start nodes
		if (sourceNode.node_type === 'data' && targetNode.node_type !== 'start') {
			return { valid: false, message: 'Data nodes can only connect to Start nodes' };
		}

		// Rule 3: Output nodes cannot have outgoing connections
		if (sourceNode.node_type === 'output') {
			return { valid: false, message: 'Output nodes cannot have outgoing connections' };
		}

		// Rule 4: Only End nodes can connect to Output nodes
		if (targetNode.node_type === 'output' && sourceNode.node_type !== 'end') {
			return { valid: false, message: 'Only End nodes can connect to Output nodes' };
		}

		return { valid: true };
	}

	// Handle new connections - this is a callback prop, not an event
	function handleConnect(connection: Connection) {
		if (connection.source && connection.target) {
			// Validate the connection
			const validation = validateConnection(connection.source, connection.target);
			if (!validation.valid) {
				console.warn('Invalid connection:', validation.message);
				// Could add a toast notification here
				return;
			}

			workflowStore.pushUndo();
			const newEdge = workflowStore.addEdge(connection.source, connection.target);
			if (newEdge) {
				// Also add to SvelteFlow edges store directly
				edges.update(e => [...e, {
					id: newEdge.id,
					source: newEdge.source,
					target: newEdge.target,
					type: 'sygra',
					selectable: true,
					markerEnd: {
						type: MarkerType.ArrowClosed,
						width: 12,
						height: 12,
						color: '#6b7280'
					},
					data: {
						label: newEdge.label,
						isConditional: newEdge.is_conditional
					}
				}]);
				hasChanges = true;
			}
		}
	}

	// Get selected nodes data for the modal
	let selectedNodesData = $derived(() => {
		if (!workflow) return [];
		return workflow.nodes.filter(n => selectedNodeIds.includes(n.id));
	});

	// Check if grouping is possible (2+ nodes selected, not START/END/data/output)
	let canGroupNodes = $derived(() => {
		if (selectedNodeIds.length < 2) return false;
		const invalidIds = selectedNodeIds.filter(id => {
			const node = workflow?.nodes.find(n => n.id === id);
			return !node || id === 'START' || id === 'END' ||
				   node.node_type === 'data' || node.node_type === 'output';
		});
		return invalidIds.length === 0;
	});

	// Flag to prevent subscription from overwriting manual selection
	let isManualSelection = false;

	// Track selection by subscribing to nodes store (for Shift+drag selection)
	$effect(() => {
		const unsubscribe = nodes.subscribe(currentNodes => {
			// Skip if we're doing manual Cmd/Ctrl+Click selection
			if (isManualSelection) return;

			const newSelectedIds = currentNodes
				.filter(n => n.selected)
				.map(n => n.id);

			// Only update if the selection actually changed
			if (JSON.stringify(newSelectedIds) !== JSON.stringify(selectedNodeIds)) {
				selectedNodeIds = newSelectedIds;
			}
		});

		return unsubscribe;
	});

	// Handle node click - supports Cmd/Ctrl+Click for multi-select
	function handleNodeClick(event: CustomEvent<{ node: Node; event: MouseEvent }>) {
		const nodeId = event.detail.node.id;
		const mouseEvent = event.detail.event;

		// Check multiple sources for modifier keys
		const eventHasModifier = mouseEvent?.metaKey || mouseEvent?.ctrlKey;
		const isMultiSelect = lastClickHadModifier || eventHasModifier;

		// Clear edge selection when clicking nodes
		selectedEdgeIds = [];
		dispatch('edgeSelect', null);

		// Cmd/Ctrl+Click for toggle multi-select (no sidebar)
		if (isMultiSelect) {
			// Set flag to prevent subscription from overwriting our selection
			isManualSelection = true;

			// Add to selection, or toggle-remove only if 2+ nodes already selected
			if (selectedNodeIds.includes(nodeId)) {
				// Only allow removal if we have 2+ nodes (preserve at least one)
				if (selectedNodeIds.length >= 2) {
					selectedNodeIds = selectedNodeIds.filter(id => id !== nodeId);
				}
			} else {
				selectedNodeIds = [...selectedNodeIds, nodeId];
			}

			// Update SvelteFlow selection visual
			const newSelectedIds = [...selectedNodeIds];
			nodes.update(ns => ns.map(n => ({
				...n,
				selected: newSelectedIds.includes(n.id)
			})));

			// Don't open sidebar when Cmd/Ctrl+clicking
			dispatch('nodeSelect', '');
		} else {
			// Normal click - single select and open sidebar
			// Reset manual selection mode
			isManualSelection = false;
			selectedNodeIds = [nodeId];
			nodes.update(ns => ns.map(n => ({
				...n,
				selected: n.id === nodeId
			})));
			dispatch('nodeSelect', nodeId);
		}
	}

	// Handle edge click - supports Cmd/Ctrl+Click for multi-select
	function handleEdgeClick(event: CustomEvent<{ edge: Edge; event: MouseEvent }>) {
		const edge = event.detail.edge;
		const mouseEvent = event.detail.event;

		// Check multiple sources for modifier keys
		const eventHasModifier = mouseEvent?.metaKey || mouseEvent?.ctrlKey;
		const isMultiSelect = lastClickHadModifier || eventHasModifier;

		// Clear node selection when clicking edges
		selectedNodeIds = [];
		nodes.update(ns => ns.map(n => ({ ...n, selected: false })));
		dispatch('nodeSelect', '');

		// Cmd/Ctrl+Click for toggle multi-select (no sidebar)
		if (isMultiSelect) {
			// Toggle selection
			if (selectedEdgeIds.includes(edge.id)) {
				selectedEdgeIds = selectedEdgeIds.filter(id => id !== edge.id);
			} else {
				selectedEdgeIds = [...selectedEdgeIds, edge.id];
			}
			// Update SvelteFlow edge selection visual
			edges.update(es => es.map(e => ({
				...e,
				selected: selectedEdgeIds.includes(e.id)
			})));
			// Don't open sidebar when Cmd/Ctrl+clicking
			dispatch('edgeSelect', null);
		} else {
			// Normal click - single select and open sidebar
			selectedEdgeIds = [edge.id];
			edges.update(es => es.map(e => ({
				...e,
				selected: e.id === edge.id
			})));
			dispatch('edgeSelect', {
				id: edge.id,
				source: edge.source,
				target: edge.target
			});
		}
	}

	// Handle pane click (deselect all)
	function handlePaneClick() {
		// Reset manual selection mode
		isManualSelection = false;
		dispatch('nodeSelect', '');
		dispatch('edgeSelect', null);
		selectedNodeIds = [];
		selectedEdgeIds = [];
		// Clear SvelteFlow selections
		nodes.update(ns => ns.map(n => ({ ...n, selected: false })));
		edges.update(es => es.map(e => ({ ...e, selected: false })));
	}

	// Handle keyboard shortcuts
	function handleKeydown(e: KeyboardEvent) {
		// Delete/Backspace to delete selected items
		if (e.key === 'Delete' || e.key === 'Backspace') {
			// Don't delete if typing in an input field
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
				return;
			}
			e.preventDefault();
			handleDeleteSelected();
			return;
		}

		// Cmd/Ctrl + Z to undo (but not when in input fields - let browser handle native undo)
		if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
				return; // Let browser handle native text undo
			}
			e.preventDefault();
			handleUndo();
			return;
		}

		// Cmd/Ctrl + Shift + Z or Cmd/Ctrl + Y to redo (but not when in input fields)
		if ((e.metaKey || e.ctrlKey) && ((e.key === 'z' && e.shiftKey) || e.key === 'y')) {
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
				return; // Let browser handle native text redo
			}
			e.preventDefault();
			handleRedo();
			return;
		}

		// Cmd/Ctrl + S to save draft
		if ((e.metaKey || e.ctrlKey) && e.key === 's') {
			e.preventDefault();
			if (hasChanges && workflow) {
				saveDraft();
				// Show brief visual feedback
				const toast = document.createElement('div');
				toast.className = 'fixed bottom-4 right-4 px-4 py-2 bg-green-600 text-white rounded-lg shadow-lg z-50 animate-fade-in';
				toast.textContent = '✓ Draft saved';
				document.body.appendChild(toast);
				setTimeout(() => toast.remove(), 2000);
			}
			return;
		}

		// Cmd/Ctrl + G to group selected nodes
		if ((e.metaKey || e.ctrlKey) && e.key === 'g' && canGroupNodes()) {
			e.preventDefault();
			showGroupModal = true;
		}

		// Escape to clear selection
		if (e.key === 'Escape') {
			handlePaneClick();
		}
	}

	// Delete selected nodes and edges
	async function handleDeleteSelected() {
		const nodesToDelete = selectedNodeIds.filter(id => id !== 'START' && id !== 'END');
		const edgesToDelete = selectedEdgeIds;

		if (nodesToDelete.length === 0 && edgesToDelete.length === 0) return;

		// Filter out protected nodes (START, END)
		const protectedNodes = selectedNodeIds.filter(id => id === 'START' || id === 'END');
		if (protectedNodes.length > 0) {
			showToast('Cannot delete START or END nodes');
		}

		workflowStore.pushUndo();

		// Delete edges first (async)
		for (const edgeId of edgesToDelete) {
			await workflowStore.removeEdge(edgeId);
		}

		// Delete nodes (async - this will also remove connected edges)
		for (const nodeId of nodesToDelete) {
			await workflowStore.deleteNode(nodeId);
		}

		// Clear selection
		selectedNodeIds = [];
		selectedEdgeIds = [];
		dispatch('nodeSelect', '');
		dispatch('edgeSelect', null);

		// Sync UI
		syncNodesFromStore();
		syncEdgesFromStore();
		hasChanges = true;

		const deletedCount = nodesToDelete.length + edgesToDelete.length;
		if (deletedCount > 0) {
			showToast(`Deleted ${deletedCount} item${deletedCount > 1 ? 's' : ''}`);
		}
	}

	// Undo action
	function handleUndo() {
		if (workflowStore.undo()) {
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
			showToast('↶ Undo');
		}
	}

	// Redo action
	function handleRedo() {
		if (workflowStore.redo()) {
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
			showToast('↷ Redo');
		}
	}

	// Show brief toast notification
	function showToast(message: string) {
		const toast = document.createElement('div');
		toast.className = 'fixed bottom-4 right-4 px-4 py-2 bg-gray-800 text-white rounded-lg shadow-lg z-50';
		toast.textContent = message;
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 1500);
	}

	// Handle group confirm from modal
	function handleGroupConfirm(event: CustomEvent<{ name: string; description: string; saveAsRecipe: boolean }>) {
		const { name, description, saveAsRecipe } = event.detail;

		// Get the nodes and edges BEFORE grouping (for recipe)
		const nodesToSave = workflow?.nodes.filter(n => selectedNodeIds.includes(n.id)) || [];
		const nodeIds = new Set(selectedNodeIds);
		const edgesToSave = workflow?.edges.filter(e =>
			nodeIds.has(e.source) && nodeIds.has(e.target)
		) || [];

		workflowStore.pushUndo();
		const newSubgraph = workflowStore.groupNodesAsSubgraph(selectedNodeIds, name, description);

		if (newSubgraph) {
			// Sync the SvelteFlow stores
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
			selectedNodeIds = [];
			dispatch('nodeSelect', newSubgraph.id);

			// If user wants to save as recipe, open the recipe modal
			if (saveAsRecipe && nodesToSave.length > 0) {
				recipeNodes = nodesToSave;
				recipeEdges = edgesToSave;
				recipeSuggestedName = name;
				showRecipeModal = true;
			}
		}

		showGroupModal = false;
	}

	// Handle recipe saved
	function handleRecipeSaved(event: CustomEvent<{ recipeId: string }>) {
		showRecipeModal = false;
		recipeNodes = [];
		recipeEdges = [];
		recipeSuggestedName = '';
	}

	// Save workflow with path (called from modal)
	async function handleSaveWithPath(event: CustomEvent<{ path: string; filename: string }>) {
		const { path, filename } = event.detail;
		isSaving = true;
		showSaveModal = false;

		try {
			// Use the normalized task name from the modal as the workflow name
			// This ensures the backend creates the directory with the correct name
			const success = await workflowStore.saveWorkflow({
				name: filename,  // Use the normalized task name
				description: workflowDescription,
				savePath: path,
				filename: filename
			});

			if (success) {
				// Update the workflow name in the header to match saved name
				workflowName = filename;
				hasChanges = false;
				clearDraft();
				dispatch('save');
			}
		} catch (e) {
			console.error('Failed to save workflow:', e);
		} finally {
			isSaving = false;
		}
	}

	// Cancel and go back
	function handleCancel() {
		dispatch('cancel');
	}

	// Apply auto-layout to arrange nodes nicely
	async function handleAutoLayout() {
		try {
			const { autoLayout, layoutAllInnerGraphs } = await import('$lib/utils/layoutUtils');
			const currentWf = workflowStore.currentWorkflow;
			if (!currentWf) return;

			// First, recursively layout all inner graphs to get proper sizes
			const nodesWithInnerLayouts = layoutAllInnerGraphs(currentWf.nodes);

			// Then apply the main layout with accurate subgraph sizes
			const result = autoLayout(nodesWithInnerLayouts, currentWf.edges);

			// Update workflow store with new positions and inner graph layouts
			result.nodes.forEach(node => {
				workflowStore.updateNodePosition(node.id, node.position);
				// Also update inner_graph if it was laid out
				if (node.inner_graph) {
					const existingNode = currentWf.nodes.find(n => n.id === node.id);
					if (existingNode) {
						existingNode.inner_graph = node.inner_graph;
						existingNode.size = node.size;
					}
				}
			});

			// Sync SvelteFlow nodes and edges
			syncNodesFromStore();
			syncEdgesFromStore();
			hasChanges = true;
		} catch (e) {
			console.error('Auto-layout failed:', e);
		}
	}

	// Handle new/reset workflow
	function handleNewWorkflow() {
		if (hasChanges) {
			// Show confirmation if there are unsaved changes
			showResetConfirm = true;
		} else {
			// No changes, reset directly
			resetCanvas();
		}
	}

	function resetCanvas() {
		// Clear the draft
		clearDraft();
		// Create a new blank workflow
		workflowStore.createNewWorkflow();
		// Reset local state
		workflowName = 'Untitled Workflow';
		workflowDescription = '';
		hasChanges = true;
		draftRestored = false;
		// Sync to SvelteFlow
		syncNodesFromStore();
		syncEdgesFromStore();
	}

	function handleResetConfirm() {
		showResetConfirm = false;
		resetCanvas();
	}

	function handleResetCancel() {
		showResetConfirm = false;
	}

	// Handle subgraph expansion from SubgraphNode component
	function handleSubgraphExpanded(event: Event) {
		// The SubgraphNode already calls expandSubgraph which modifies state
		// We just need to sync the UI here
		syncNodesFromStore();
		syncEdgesFromStore();
		hasChanges = true;
	}

	// Setup event listener for subgraph expansion
	onMount(() => {
		window.addEventListener('subgraph-expanded', handleSubgraphExpanded);
	});

	onDestroy(() => {
		window.removeEventListener('subgraph-expanded', handleSubgraphExpanded);
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex flex-col h-full bg-gray-50 dark:bg-gray-900">
	<!-- Header -->
	<div class="flex items-center justify-between px-4 py-3 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-2">
				<div class="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
					<GitBranch size={16} class="text-white" />
				</div>
				<input
					type="text"
					bind:value={workflowName}
					placeholder="Untitled Workflow"
					class="text-lg font-semibold bg-transparent border border-gray-300 dark:border-gray-600 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-lg px-3 py-1.5 text-gray-900 dark:text-gray-100 min-w-[200px] transition-colors"
				/>
			</div>
			{#if hasChanges}
				<span class="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
					Unsaved changes
				</span>
			{/if}
			{#if lastAutoSave}
				<span class="text-xs text-gray-400 dark:text-gray-500">
					Draft saved {lastAutoSave.toLocaleTimeString()}
				</span>
			{/if}
		</div>

		<div class="flex items-center gap-2">
			<!-- New/Reset button - only shows when canvas has more than just Start/End nodes -->
			{#if workflow && (workflow.nodes.length > 2 || workflow.edges.length > 0)}
				<button
					onclick={handleNewWorkflow}
					title="Start a new blank workflow"
					class="flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					<FilePlus2 size={16} />
					New
				</button>
				<div class="w-px h-6 bg-gray-200 dark:bg-gray-600"></div>
			{/if}
			<!-- Group as Subgraph button - shows when 2+ valid nodes selected -->
			{#if selectedNodeIds.length >= 2}
				<button
					onclick={() => showGroupModal = true}
					disabled={!canGroupNodes()}
					title={canGroupNodes() ? `Group ${selectedNodeIds.length} nodes as subgraph (⌘G)` : 'Cannot group: includes START, END, Data, or Output nodes'}
					class="flex items-center gap-2 px-3 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-lg transition-colors disabled:cursor-not-allowed"
				>
					<Group size={16} />
					Group ({selectedNodeIds.length})
				</button>
				<div class="w-px h-6 bg-gray-200 dark:bg-gray-600"></div>
			{/if}
			<button
				onclick={handleAutoLayout}
				title="Auto-arrange nodes using DAG layout"
				class="flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
			>
				<LayoutGrid size={16} />
				Auto Layout
			</button>
			<div class="w-px h-6 bg-gray-200 dark:bg-gray-600"></div>
			<button
				onclick={handleCancel}
				class="flex items-center gap-2 px-3 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
			>
				<X size={16} />
				Cancel
			</button>
			<button
				onclick={() => showSaveModal = true}
				disabled={isSaving}
				class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
			>
				{#if isSaving}
					<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
				{:else}
					<Save size={16} />
				{/if}
				Save Workflow
			</button>
		</div>
	</div>

	<div class="flex flex-1 overflow-hidden">
		<!-- Node Palette -->
		<div class="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 overflow-y-auto">
			<div class="p-4">
				<!-- Search Box -->
				<div class="relative mb-4">
					<Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
					<input
						type="text"
						bind:value={paletteSearch}
						placeholder="Search nodes..."
						class="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
					/>
					{#if paletteSearch}
						<button
							onclick={() => paletteSearch = ''}
							class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
						>
							<X size={12} />
						</button>
					{/if}
				</div>

				<!-- Categorized Nodes -->
				<div class="space-y-3" role="listbox" aria-label="Node types">
					{#each NODE_CATEGORIES as category}
						{@const categoryNodes = groupedNodeTypes()[category.id]}
						{#if categoryNodes && categoryNodes.length > 0}
							<div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
								<!-- Category Header -->
								<button
									onclick={() => toggleCategory(category.id)}
									class="w-full flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
								>
									<span class="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wider">
										{category.label}
									</span>
									<div class="flex items-center gap-2">
										<span class="text-xs text-gray-400">{categoryNodes.length}</span>
										{#if expandedCategories.has(category.id)}
											<ChevronDown size={14} class="text-gray-400" />
										{:else}
											<ChevronRight size={14} class="text-gray-400" />
										{/if}
									</div>
								</button>

								<!-- Category Nodes -->
								{#if expandedCategories.has(category.id)}
									<div class="p-2 space-y-1.5">
										{#each categoryNodes as nodeType}
											{@const Icon = nodeIcons[nodeType.type]}
											<div
												draggable="true"
												ondragstart={(e) => handleDragStart(e, nodeType.type)}
												ondragend={handleDragEnd}
												role="option"
												aria-selected={draggedNodeType === nodeType.type}
												tabindex="0"
												class="flex items-center gap-2.5 p-2 rounded-lg border border-dashed border-gray-200 dark:border-gray-600 hover:border-violet-400 dark:hover:border-violet-500 cursor-grab active:cursor-grabbing transition-colors group"
												class:border-violet-500={draggedNodeType === nodeType.type}
												class:bg-violet-50={draggedNodeType === nodeType.type}
												class:dark:bg-violet-900={draggedNodeType === nodeType.type}
											>
												<div
													class="w-8 h-8 rounded-md flex items-center justify-center flex-shrink-0"
													style="background-color: {nodeType.color}20"
												>
													<Icon size={16} style="color: {nodeType.color}" />
												</div>
												<div class="flex-1 min-w-0">
													<div class="font-medium text-sm text-gray-900 dark:text-gray-100">
														{nodeType.label}
													</div>
													<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
														{nodeType.description}
													</div>
												</div>
												<GripVertical size={12} class="text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
											</div>
										{/each}
									</div>
								{/if}
							</div>
						{/if}
					{/each}
				</div>

				<!-- No results message -->
				{#if paletteSearch && filteredNodeTypes().length === 0}
					<div class="text-center py-8 text-gray-500 dark:text-gray-400">
						<Search size={24} class="mx-auto mb-2 opacity-50" />
						<p class="text-sm">No nodes match "{paletteSearch}"</p>
					</div>
				{/if}

				<!-- Tips -->
				<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
					<h3 class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
						Tips
					</h3>
					<div class="text-xs text-gray-500 dark:text-gray-400 space-y-1.5">
						<p>• Connect by dragging handle to handle</p>
						<p>• <strong>⌘/Ctrl+Click</strong> to multi-select</p>
						<p>• <strong>Delete/Backspace</strong> to delete selected</p>
						<p>• <strong>⌘G</strong> to group as subgraph</p>
						<p>• <strong>⌘Z</strong> to undo</p>
					</div>
				</div>
			</div>
		</div>

		<!-- Canvas -->
		<div
			bind:this={canvasRef}
			class="flex-1 relative"
			ondrop={handleDrop}
			ondragover={handleDragOver}
			role="application"
			aria-label="Workflow canvas"
		>
			{#if workflow}
				<SvelteFlow
					nodes={nodes}
					edges={edges}
					{nodeTypes}
					{edgeTypes}
					fitView
					fitViewOptions={{ padding: 0.5, maxZoom: 0.7 }}
					connectionLineType={ConnectionLineType.SmoothStep}
					defaultEdgeOptions={{
						type: 'sygra',
						animated: false
					}}
					nodesDraggable={true}
					nodesConnectable={true}
					elementsSelectable={true}
					selectionOnDrag={false}
					selectionMode={SelectionMode.Partial}
					multiSelectionKey="Shift"
					panOnDrag={true}
					panOnScroll={false}
					zoomOnScroll={true}
					on:nodeclick={handleNodeClick}
					on:edgeclick={handleEdgeClick}
					on:paneclick={handlePaneClick}
					on:nodedragstop={handleNodeDragStop}
					onconnect={handleConnect}
				>
					<!-- FitView helper - responds to fitViewTrigger changes -->
					<FitViewHelper trigger={fitViewTrigger} />

					<Controls position="bottom-right" />
					<Background
							gap={20}
							size={1}
							bgColor={isDarkMode ? '#1e293b' : '#f9fafb'}
							patternColor={isDarkMode ? '#334155' : '#e5e7eb'}
						/>
					<!-- Minimap with toggle button -->
					<Panel position="bottom-left" class="!m-0 !p-0">
						<div class="flex flex-col items-start gap-1 m-2">
							<!-- Toggle button -->
							<button
								onclick={() => showMinimap = !showMinimap}
								class="flex items-center justify-center w-7 h-7 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
								title={showMinimap ? 'Hide minimap' : 'Show minimap'}
							>
								{#if showMinimap}
									<EyeOff size={14} class="text-gray-500 dark:text-gray-400" />
								{:else}
									<MapIcon size={14} class="text-gray-500 dark:text-gray-400" />
								{/if}
							</button>

							<!-- Minimap -->
							{#if showMinimap}
								<div class="rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700 shadow-sm">
									<MiniMap
										width={180}
										height={120}
										nodeColor={(node) => {
											const nodeType = NODE_TYPES.find(t => t.type === node.type);
											return nodeType?.color ?? '#6b7280';
										}}
										bgColor={isDarkMode ? '#1e293b' : '#ffffff'}
										maskColor={isDarkMode ? 'rgba(30, 41, 59, 0.6)' : 'rgba(240, 240, 240, 0.6)'}
										maskStrokeColor={isDarkMode ? '#475569' : '#cbd5e1'}
										maskStrokeWidth={1}
										pannable={true}
										zoomable={true}
										class="!relative !m-0"
									/>
								</div>
							{/if}
						</div>
					</Panel>
				</SvelteFlow>
			{/if}

			<!-- Drop indicator overlay -->
			{#if draggedNodeType}
				<div class="absolute inset-0 pointer-events-none border-4 border-dashed border-violet-400 dark:border-violet-500 bg-violet-50/20 dark:bg-violet-900/20 rounded-lg m-2 flex items-center justify-center">
					<div class="bg-white dark:bg-gray-800 px-4 py-2 rounded-lg shadow-lg text-sm font-medium text-violet-600 dark:text-violet-400">
						Drop to add {NODE_TYPES.find(t => t.type === draggedNodeType)?.label} node
					</div>
				</div>
			{/if}

			<!-- Selection indicator - only show for multi-select (2+ nodes or any edges via Cmd/Ctrl+Click) -->
			{#if selectedNodeIds.length >= 2 || selectedEdgeIds.length > 0}
				{@const totalSelected = selectedNodeIds.length + selectedEdgeIds.length}
				{@const canDelete = selectedNodeIds.filter(id => id !== 'START' && id !== 'END').length > 0 || selectedEdgeIds.length > 0}
				<div class="absolute top-4 left-1/2 transform -translate-x-1/2 bg-gray-800 dark:bg-gray-700 text-white px-4 py-2 rounded-lg shadow-lg text-sm font-medium flex items-center gap-3 z-10">
					<div class="flex items-center gap-2">
						<MousePointerClick size={16} />
						{#if selectedNodeIds.length > 0 && selectedEdgeIds.length > 0}
							{selectedNodeIds.length} nodes, {selectedEdgeIds.length} edges
						{:else if selectedNodeIds.length > 0}
							{selectedNodeIds.length} nodes selected
						{:else}
							{selectedEdgeIds.length} edge{selectedEdgeIds.length > 1 ? 's' : ''} selected
						{/if}
					</div>
					<div class="h-4 w-px bg-gray-600"></div>
					{#if selectedNodeIds.length >= 2 && canGroupNodes()}
						<button
							onclick={() => showGroupModal = true}
							class="flex items-center gap-1 text-blue-300 hover:text-blue-200 transition-colors"
						>
							<Group size={14} />
							<span>⌘G</span>
						</button>
						<div class="h-4 w-px bg-gray-600"></div>
					{/if}
					{#if canDelete}
						<button
							onclick={handleDeleteSelected}
							class="flex items-center gap-1 text-red-400 hover:text-red-300 transition-colors"
						>
							<Trash2 size={14} />
							<span>Delete</span>
						</button>
					{/if}
					<span class="text-gray-400 text-xs">Esc to clear</span>
				</div>
			{/if}
		</div>
	</div>
</div>

<!-- Group as Subgraph Modal -->
{#if showGroupModal && workflow}
	<GroupSubgraphModal
		selectedNodes={selectedNodesData()}
		allEdges={workflow.edges}
		on:confirm={handleGroupConfirm}
		on:cancel={() => showGroupModal = false}
	/>
{/if}

<!-- Save as Recipe Modal -->
{#if showRecipeModal}
	<SaveRecipeModal
		nodes={recipeNodes}
		edges={recipeEdges}
		suggestedName={recipeSuggestedName}
		on:saved={handleRecipeSaved}
		on:close={() => {
			showRecipeModal = false;
			recipeNodes = [];
			recipeEdges = [];
			recipeSuggestedName = '';
		}}
	/>
{/if}

<!-- Recipe Picker for Subgraph -->
{#if showRecipePicker}
	<RecipePickerModal
		position={recipePickerPosition}
		on:select={handleRecipeSelect}
		on:cancel={() => showRecipePicker = false}
	/>
{/if}

<!-- Save Workflow Modal -->
<SaveWorkflowModal
	{workflowName}
	isOpen={showSaveModal}
	on:save={handleSaveWithPath}
	on:close={() => showSaveModal = false}
/>

<!-- Reset Confirmation Modal -->
{#if showResetConfirm}
	<div
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
		onclick={handleResetCancel}
		role="dialog"
		aria-modal="true"
	>
		<div
			class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					Start New Workflow?
				</h2>
			</div>
			<div class="px-6 py-4">
				<p class="text-gray-600 dark:text-gray-300">
					You have unsaved changes. Starting a new workflow will discard your current work.
				</p>
			</div>
			<div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 flex justify-end gap-3">
				<button
					onclick={handleResetCancel}
					class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					Cancel
				</button>
				<button
					onclick={handleResetConfirm}
					class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
				>
					Discard & Start New
				</button>
			</div>
		</div>
	</div>
{/if}
