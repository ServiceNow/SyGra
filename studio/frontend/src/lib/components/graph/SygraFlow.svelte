<script lang="ts">
	import {
		SvelteFlow,
		Controls,
		Background,
		MiniMap,
		Panel,
		ViewportPortal,
		type Node,
		type Edge,
		type NodeTypes,
		type EdgeTypes,
		ConnectionLineType,
		Position,
		MarkerType
	} from '@xyflow/svelte';
	import { writable, get, derived } from 'svelte/store';
	import { createEventDispatcher, tick } from 'svelte';
	import { workflowStore, type Workflow, type Execution } from '$lib/stores/workflow.svelte';
	import { Map as MapIcon, EyeOff } from 'lucide-svelte';

	// Node components
	import StartNode from './renderers/nodes/StartNode.svelte';
	import EndNode from './renderers/nodes/EndNode.svelte';
	import LLMNode from './renderers/nodes/LLMNode.svelte';
	import LambdaNode from './renderers/nodes/LambdaNode.svelte';
	import SubgraphNode from './renderers/nodes/SubgraphNode.svelte';
	import DataNode from './renderers/nodes/DataNode.svelte';
	import OutputNode from './renderers/nodes/OutputNode.svelte';
	import WeightedSamplerNode from './renderers/nodes/WeightedSamplerNode.svelte';
	import AgentNode from './renderers/nodes/AgentNode.svelte';
	import MultiLLMNode from './renderers/nodes/MultiLLMNode.svelte';

	// Edge component
	import SygraEdge from './renderers/edges/SygraEdge.svelte';

	// Workflow boundary visualization
	import WorkflowBoundary from './WorkflowBoundary.svelte';

	// FitView helper (must be inside SvelteFlow to use useSvelteFlow hook)
	import FitViewHelper from './FitViewHelper.svelte';

	// Export helper (must be inside SvelteFlow to use useSvelteFlow hook)
	import ExportHelper from './ExportHelper.svelte';

	// Import SvelteFlow styles
	import '@xyflow/svelte/dist/style.css';

	interface Props {
		workflow: Workflow;
		execution?: Execution | null;
	}

	let { workflow, execution = null }: Props = $props();

	// Minimap visibility state
	let showMinimap = $state(true);

	const dispatch = createEventDispatcher<{
		nodeSelect: string;
		edgeSelect: {
			id: string;
			source: string;
			target: string;
			label?: string;
			isConditional: boolean;
			condition?: { condition_path: string; path_map: Record<string, string> };
		} | null;
	}>();

	// Node type mapping - use 'unknown' to bypass Svelte 5 vs 4 type incompatibility
	const nodeTypes = {
		data: DataNode,
		start: StartNode,
		end: EndNode,
		output: OutputNode,
		llm: LLMNode,
		lambda: LambdaNode,
		subgraph: SubgraphNode,
		weighted_sampler: WeightedSamplerNode,
		agent: AgentNode,
		multi_llm: MultiLLMNode
	} as unknown as NodeTypes;

	const edgeTypes = {
		sygra: SygraEdge
	} as unknown as EdgeTypes;

	// Node colors for MiniMap
	const nodeColors: Record<string, string> = {
		data: '#0ea5e9',
		start: '#22c55e',
		end: '#ef4444',
		output: '#10b981',
		llm: '#8b5cf6',
		lambda: '#f97316',
		subgraph: '#3b82f6',
		weighted_sampler: '#8b5cf6',
		agent: '#ec4899',
		multi_llm: '#06b6d4'
	};

	// Dark mode detection
	let isDarkMode = $state(false);

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

	// Helper to extract edge data with proper types
	function getEdgeSelectData(edge: Edge) {
		const data = edge.data as {
			label?: string;
			isConditional?: boolean;
			condition?: { condition_path: string; path_map: Record<string, string> };
		} | undefined;

		return {
			id: edge.id,
			source: edge.source,
			target: edge.target,
			label: data?.label,
			isConditional: data?.isConditional ?? false,
			condition: data?.condition
		};
	}

	// Create Svelte stores for SvelteFlow (it requires stores, not runes)
	const nodes = writable<Node[]>([]);
	const edges = writable<Edge[]>([]);

	// Store to trigger fitView - increment to trigger
	const fitViewTrigger = writable(0);

	// Node types that should be EXCLUDED from the main workflow boundary
	// These nodes visually sit outside the green dotted box: data (input), output (result), tool
	// All other node types are automatically included in the boundary
	const excludedFromBoundary = new Set(['data', 'output', 'tool']);

	// Helper function to check if a node type should be inside the workflow boundary
	function isWorkflowNode(nodeType: string | undefined): boolean {
		if (!nodeType) return false;
		return !excludedFromBoundary.has(nodeType);
	}

	// Estimated node dimensions for bounding box calculation (fallback before DOM measurement)
	// NodeWrapper has min-w-[180px], so actual nodes can be wider based on content
	// Default dimensions used when a node type isn't explicitly listed
	const DEFAULT_NODE_DIMS = { width: 220, height: 100 };

	const nodeDimensions: Record<string, { width: number; height: number }> = {
		start: { width: 140, height: 60 },
		end: { width: 140, height: 60 },
		llm: { width: 240, height: 120 },
		multi_llm: { width: 240, height: 140 },  // Slightly taller for model list
		lambda: { width: 220, height: 100 },
		subgraph: { width: 200, height: 100 },
		weighted_sampler: { width: 240, height: 100 },
		connector: { width: 180, height: 70 },
		web_agent: { width: 220, height: 100 },
		agent: { width: 240, height: 120 },
		data: { width: 200, height: 90 },
		output: { width: 200, height: 90 }
	};

	// Constants matching SubgraphNode.svelte and layoutUtils.ts
	const INNER_PADDING = 12;
	const HEADER_HEIGHT = 44;
	const INNER_NODE_WIDTH = 140;
	const INNER_NODE_HEIGHT = 44;

	// Arc edge constants
	const ARC_PADDING = 60; // Padding from the nearest node for arc edges
	const MIN_ARC_DISTANCE = 200; // Minimum horizontal distance to consider arc edges

	/**
	 * Get node dimensions (width and height), using measured if available.
	 */
	function getNodeDims(node: Node): { width: number; height: number } {
		const measured = (node as any).measured;
		if (measured?.width && measured?.height) {
			return { width: measured.width, height: measured.height };
		}
		return nodeDimensions[node.type || 'llm'] || DEFAULT_NODE_DIMS;
	}

	/**
	 * Arc edge data returned from calculation
	 */
	interface ArcEdgeData {
		arcApexY: number;           // Y coordinate of the arc apex (horizontal segment)
		arcDirection: 'top' | 'bottom';  // Direction the arc goes
		blockingNodes: string[];    // IDs of nodes that triggered the arc
	}

	/**
	 * Calculate arc edge data for conditional edges that skip over intermediate nodes.
	 * Determines optimal direction (top or bottom) based on available space.
	 *
	 * Algorithm:
	 * 1. Only apply to conditional edges (semantic "skip" edges)
	 * 2. Only consider edges with significant horizontal distance
	 * 3. Find nodes in the horizontal path between source and target
	 * 4. Calculate clearance for both top and bottom directions
	 * 5. Choose direction with less deviation from edge's natural Y
	 */
	function calculateArcEdgeData(
		sourceId: string,
		targetId: string,
		allNodes: Node[],
		isConditional: boolean = false
	): ArcEdgeData | null {
		// Only apply arcs to conditional edges - these are semantic "skip" connections
		if (!isConditional) return null;

		const sourceNode = allNodes.find(n => n.id === sourceId);
		const targetNode = allNodes.find(n => n.id === targetId);

		if (!sourceNode || !targetNode) return null;

		const sourceDims = getNodeDims(sourceNode);
		const targetDims = getNodeDims(targetNode);

		// Edge connection points (right side of source, left side of target)
		const edgeStartX = sourceNode.position.x + sourceDims.width;
		const edgeStartY = sourceNode.position.y + sourceDims.height / 2;
		const edgeEndX = targetNode.position.x;
		const edgeEndY = targetNode.position.y + targetDims.height / 2;

		// Only consider left-to-right edges for arcing
		if (edgeEndX <= edgeStartX) return null;

		// Only consider edges with significant horizontal distance
		const horizontalDistance = edgeEndX - edgeStartX;
		if (horizontalDistance < MIN_ARC_DISTANCE) return null;

		// Find ALL nodes that are horizontally between source and target
		// These are nodes we need to arc over/under
		const nodesInRange: Node[] = [];

		for (const node of allNodes) {
			if (node.id === sourceId || node.id === targetId) continue;

			const dims = getNodeDims(node);
			const nodeLeft = node.position.x;
			const nodeRight = node.position.x + dims.width;

			// Check if node's horizontal range overlaps with the edge's range
			const horizontallyInRange = nodeRight > edgeStartX && nodeLeft < edgeEndX;

			if (horizontallyInRange) {
				nodesInRange.push(node);
			}
		}

		// If no nodes in range, no arc needed
		if (nodesInRange.length === 0) return null;

		// Calculate bounds for all nodes (for top/bottom clearance)
		let globalMinY = Infinity;  // Top of all nodes
		let globalMaxY = -Infinity; // Bottom of all nodes

		for (const node of allNodes) {
			if (node.id === sourceId || node.id === targetId) continue;
			const dims = getNodeDims(node);
			globalMinY = Math.min(globalMinY, node.position.y);
			globalMaxY = Math.max(globalMaxY, node.position.y + dims.height);
		}

		// Include source and target in bounds
		globalMinY = Math.min(globalMinY, sourceNode.position.y, targetNode.position.y);
		globalMaxY = Math.max(
			globalMaxY,
			sourceNode.position.y + sourceDims.height,
			targetNode.position.y + targetDims.height
		);

		// Calculate apex positions for top and bottom arcs
		const topApexY = globalMinY - ARC_PADDING;
		const bottomApexY = globalMaxY + ARC_PADDING;

		// Edge's natural Y (midpoint between source and target connection points)
		const edgeMidY = (edgeStartY + edgeEndY) / 2;

		// Calculate deviation for each direction
		const topDeviation = Math.abs(edgeMidY - topApexY);
		const bottomDeviation = Math.abs(bottomApexY - edgeMidY);

		// Choose direction with less deviation (more natural path)
		const arcDirection: 'top' | 'bottom' = topDeviation <= bottomDeviation ? 'top' : 'bottom';
		const arcApexY = arcDirection === 'top' ? topApexY : bottomApexY;

		return {
			arcApexY,
			arcDirection,
			blockingNodes: nodesInRange.map(n => n.id)
		};
	}

	// Derive bounding box for workflow nodes (excluding data and output) AND arc edges
	const workflowBounds = derived([nodes, edges], ([$nodes, $edges]) => {
		const workflowNodes = $nodes.filter(n => isWorkflowNode(n.type));

		if (workflowNodes.length === 0) return null;

		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

		workflowNodes.forEach(node => {
			// Use measured dimensions from SvelteFlow if available (actual rendered size)
			// Fall back to estimated dimensions from nodeDimensions map
			const measured = (node as any).measured;
			let dims = nodeDimensions[node.type || 'llm'] || DEFAULT_NODE_DIMS;

			if (measured?.width && measured?.height) {
				// Use actual measured dimensions from DOM
				dims = { width: measured.width, height: measured.height };
			} else if (node.type === 'subgraph' && node.data) {
				// For subgraphs without measured dims, calculate from inner graph
				const nodeData = node.data as { size?: { width: number; height: number }; inner_graph?: { nodes: unknown[] } };
				if (nodeData.size?.width && nodeData.size?.height) {
					dims = { width: nodeData.size.width, height: nodeData.size.height };
				} else if (nodeData.inner_graph?.nodes?.length) {
					// Calculate from inner graph with proper normalization
					const innerNodes = nodeData.inner_graph.nodes as Array<{ position?: { x: number; y: number }; size?: { width: number; height: number } }>;
					let innerMinX = Infinity, innerMinY = Infinity;
					let innerMaxX = 0, innerMaxY = 0;
					innerNodes.forEach(innerNode => {
						const ix = innerNode.position?.x || 0;
						const iy = innerNode.position?.y || 0;
						const iw = innerNode.size?.width || INNER_NODE_WIDTH;
						const ih = innerNode.size?.height || INNER_NODE_HEIGHT;
						innerMinX = Math.min(innerMinX, ix);
						innerMinY = Math.min(innerMinY, iy);
						innerMaxX = Math.max(innerMaxX, ix + iw);
						innerMaxY = Math.max(innerMaxY, iy + ih);
					});
					// Normalize: content extent = (max - min)
					if (innerMinX === Infinity) innerMinX = 0;
					if (innerMinY === Infinity) innerMinY = 0;
					const contentWidth = innerMaxX - innerMinX;
					const contentHeight = innerMaxY - innerMinY;
					dims = {
						width: Math.max(200, contentWidth + INNER_PADDING * 2),
						height: Math.max(60, contentHeight + INNER_PADDING * 2) + HEADER_HEIGHT
					};
				}
			}

			const x = node.position.x;
			const y = node.position.y;

			minX = Math.min(minX, x);
			minY = Math.min(minY, y);
			maxX = Math.max(maxX, x + dims.width);
			maxY = Math.max(maxY, y + dims.height);
		});

		// Include arc edge apex points in the boundary calculation
		// This ensures the dotted boundary encompasses the arc paths
		$edges.forEach(edge => {
			const edgeData = edge.data as { isArcEdge?: boolean; arcApexY?: number; arcDirection?: string } | undefined;
			if (edgeData?.isArcEdge && edgeData.arcApexY !== undefined) {
				// Extend bounds to include arc apex with some margin
				const arcMargin = 16; // Margin around the arc path
				if (edgeData.arcDirection === 'top') {
					// Top arc - extends above (lower Y)
					minY = Math.min(minY, edgeData.arcApexY - arcMargin);
				} else {
					// Bottom arc - extends below (higher Y)
					maxY = Math.max(maxY, edgeData.arcApexY + arcMargin);
				}
			}
		});

		// Add padding around the boundary
		const padding = 24;

		return {
			x: minX - padding,
			y: minY - padding,
			width: (maxX - minX) + (padding * 2),
			height: (maxY - minY) + (padding * 2)
		};
	});

	// Track workflow ID to know when we need a full resync
	let lastWorkflowId = '';
	let lastWorkflowVersion = 0;

	// Track node positions locally to preserve user arrangements
	let nodePositions = new Map<string, { x: number; y: number }>();

	// Check if any node is currently running (for muting other nodes)
	let hasRunningNode = $derived(() => {
		if (!execution?.node_states) return false;
		return Object.values(execution.node_states).some(s => s.status === 'running');
	});

	// Full sync when workflow changes (new workflow loaded)
	$effect(() => {
		if (workflow.id !== lastWorkflowId) {
			lastWorkflowId = workflow.id;

			// Apply auto-layout for better initial positioning
			import('$lib/utils/layoutUtils').then(({ autoLayout, layoutAllInnerGraphs }) => {
				// First layout all inner graphs to get proper subgraph sizes
				const nodesWithInnerLayouts = layoutAllInnerGraphs(workflow.nodes);

				// Then apply the main layout with accurate subgraph sizes
				const result = autoLayout(nodesWithInnerLayouts, workflow.edges);

				// Reset position cache with layouted positions
				nodePositions = new Map();
				result.nodes.forEach(node => {
					nodePositions.set(node.id, node.position);
				});

				// Full node sync with layouted positions (including inner_graph and size)
				const layoutedNodes = result.nodes.map(node => ({
					id: node.id,
					type: node.node_type,
					position: nodePositions.get(node.id) || node.position,
					data: {
						...node,
						executionState: execution?.node_states[node.id] ?? null,
						isCurrentNode: execution?.current_node === node.id,
						nodeType: node.node_type,
						hasRunningNode: hasRunningNode()
					},
					sourcePosition: Position.Right,
					targetPosition: Position.Left,
					selectable: true,
					draggable: true
				}));
				nodes.set(layoutedNodes);

				// Sync edges with arc data AFTER nodes are positioned
				edges.set(workflow.edges.map(edge => {
					const arcData = calculateArcEdgeData(edge.source, edge.target, layoutedNodes, edge.is_conditional);
					return {
						id: edge.id,
						source: edge.source,
						target: edge.target,
						type: 'sygra',
						selectable: true,
						animated: false,
						markerEnd: {
							type: MarkerType.ArrowClosed,
							width: 12,
							height: 12,
							color: edge.is_conditional ? '#f59e0b' : '#6b7280'
						},
						data: {
							label: edge.label,
							isConditional: edge.is_conditional,
							condition: edge.condition,
							arcApexY: arcData?.arcApexY,
							arcDirection: arcData?.arcDirection,
							isArcEdge: !!arcData
						}
					};
				}));

				// Trigger fitView after nodes are loaded
				tick().then(() => {
					fitViewTrigger.update(n => n + 1);
				});
			}).catch(() => {
				// Fallback to original positions if layout fails
				nodePositions = new Map();
				workflow.nodes.forEach(node => {
					nodePositions.set(node.id, node.position);
				});

				const fallbackNodes = workflow.nodes.map(node => ({
					id: node.id,
					type: node.node_type,
					position: nodePositions.get(node.id) || node.position,
					data: {
						...node,
						executionState: execution?.node_states[node.id] ?? null,
						isCurrentNode: execution?.current_node === node.id,
						nodeType: node.node_type,
						hasRunningNode: hasRunningNode()
					},
					sourcePosition: Position.Right,
					targetPosition: Position.Left,
					selectable: true,
					draggable: true
				}));
				nodes.set(fallbackNodes);

				// Sync edges with arc data
				edges.set(workflow.edges.map(edge => {
					const arcData = calculateArcEdgeData(edge.source, edge.target, fallbackNodes, edge.is_conditional);
					return {
						id: edge.id,
						source: edge.source,
						target: edge.target,
						type: 'sygra',
						selectable: true,
						animated: false,
						markerEnd: {
							type: MarkerType.ArrowClosed,
							width: 12,
							height: 12,
							color: edge.is_conditional ? '#f59e0b' : '#6b7280'
						},
						data: {
							label: edge.label,
							isConditional: edge.is_conditional,
							condition: edge.condition,
							arcApexY: arcData?.arcApexY,
							arcDirection: arcData?.arcDirection,
							isArcEdge: !!arcData
						}
					};
				}));

				// Trigger fitView after nodes are loaded
				tick().then(() => {
					fitViewTrigger.update(n => n + 1);
				});
			});
		}
	});

	// Update only execution state data, preserve positions
	$effect(() => {
		if (lastWorkflowId === workflow.id && execution) {
			nodes.update(currentNodes =>
				currentNodes.map(node => ({
					...node,
					// Preserve current position, don't reset from workflow
					data: {
						...node.data,
						executionState: execution?.node_states[node.id] ?? null,
						isCurrentNode: execution?.current_node === node.id,
						hasRunningNode: hasRunningNode()
					}
				}))
			);
		}
	});

	// Also sync when workflowVersion changes (node data updates like model changes)
	$effect(() => {
		const currentVersion = workflowStore.workflowVersion;
		// Read directly from store to ensure we get the latest data
		const currentWf = workflowStore.currentWorkflow;
		if (currentVersion > lastWorkflowVersion && currentWf && lastWorkflowId === currentWf.id) {
			console.log('[SygraFlow] Version changed:', lastWorkflowVersion, '->', currentVersion, 'syncing nodes/edges...');
			lastWorkflowVersion = currentVersion;
			// Sync node data when version changes (handles data updates within nodes)
			// Preserve positions from nodePositions map
			nodes.update(currentNodes =>
				currentWf.nodes.map(workflowNode => {
					const existingNode = currentNodes.find(n => n.id === workflowNode.id);
					return {
						id: workflowNode.id,
						type: workflowNode.node_type,
						position: nodePositions.get(workflowNode.id) || existingNode?.position || workflowNode.position,
						data: {
							...workflowNode,
							executionState: execution?.node_states[workflowNode.id] ?? null,
							isCurrentNode: execution?.current_node === workflowNode.id,
							nodeType: workflowNode.node_type,
							hasRunningNode: hasRunningNode(),
							_version: Date.now()  // Force re-render
						},
						sourcePosition: Position.Right,
						targetPosition: Position.Left,
						selectable: true,
						draggable: true
					};
				})
			);
			// Also sync edges with arc data
			const currentNodes = get(nodes);
			edges.set(currentWf.edges.map(edge => {
				const arcData = calculateArcEdgeData(edge.source, edge.target, currentNodes, edge.is_conditional);
				return {
					id: edge.id,
					source: edge.source,
					target: edge.target,
					type: 'sygra',
					selectable: true,
					animated: execution?.status === 'running' &&
						(execution.node_states[edge.source]?.status === 'completed' &&
						 execution.node_states[edge.target]?.status === 'running'),
					markerEnd: {
						type: MarkerType.ArrowClosed,
						width: 16,
						height: 16,
						color: edge.is_conditional ? '#f59e0b' : '#6b7280'
					},
					data: {
						label: edge.label,
						isConditional: edge.is_conditional,
						condition: edge.condition,
						arcApexY: arcData?.arcApexY,
						arcDirection: arcData?.arcDirection,
						isArcEdge: !!arcData
					}
				};
			}));
		}
	});

	// Export function to apply auto-layout
	export async function applyAutoLayout() {
		console.log('applyAutoLayout called');
		try {
			const { autoLayout, layoutAllInnerGraphs } = await import('$lib/utils/layoutUtils');

			// Get current node data from store for layout calculation
			const currentNodes = get(nodes);
			const workflowNodes = currentNodes.map(n => ({
				id: n.id,
				node_type: n.type || 'llm',
				position: n.position,
				summary: n.data?.summary || n.id,
				description: n.data?.description || '',
				config: n.data?.config || {},
				inner_graph: n.data?.inner_graph,
				size: n.data?.size
			}));

			// First layout all inner graphs to get proper subgraph sizes
			const nodesWithInnerLayouts = layoutAllInnerGraphs(workflowNodes as any);

			// Then apply the main layout with accurate subgraph sizes
			const result = autoLayout(nodesWithInnerLayouts, workflow.edges);

			console.log('Auto-layout result:', result);

			// Update position cache
			nodePositions = new Map();
			result.nodes.forEach(node => {
				nodePositions.set(node.id, node.position);
			});

			// Update nodes with new positions and inner graph data
			nodes.update(currentNodes =>
				currentNodes.map(node => {
					const newPosition = nodePositions.get(node.id);
					const layoutedNode = result.nodes.find(n => n.id === node.id);
					console.log(`Node ${node.id}: old=${JSON.stringify(node.position)}, new=${JSON.stringify(newPosition)}`);

					if (newPosition) {
						return {
							...node,
							position: newPosition,
							data: {
								...node.data,
								inner_graph: layoutedNode?.inner_graph || node.data?.inner_graph,
								size: layoutedNode?.size || node.data?.size
							}
						};
					}
					return node;
				})
			);
		} catch (e) {
			console.error('Auto-layout failed:', e);
		}
	}

	// Sync edges - only on workflow change, not execution state
	$effect(() => {
		if (workflow.id === lastWorkflowId || !lastWorkflowId) {
			const currentNodes = get(nodes);
			edges.set(workflow.edges.map(edge => {
				// Calculate arc data for conditional edges that skip over intermediate nodes
				const arcData = calculateArcEdgeData(edge.source, edge.target, currentNodes, edge.is_conditional);

				return {
					id: edge.id,
					source: edge.source,
					target: edge.target,
					type: 'sygra',
					selectable: true,
					animated: execution?.status === 'running' &&
						(execution.node_states[edge.source]?.status === 'completed' &&
						 execution.node_states[edge.target]?.status === 'running'),
					markerEnd: {
						type: MarkerType.ArrowClosed,
						width: 12,
						height: 12,
						color: edge.is_conditional ? '#f59e0b' : '#6b7280'
					},
					data: {
						label: edge.label,
						isConditional: edge.is_conditional,
						condition: edge.condition,
						// Arc edge data for skip connections
						arcApexY: arcData?.arcApexY,
						arcDirection: arcData?.arcDirection,
						isArcEdge: !!arcData
					}
				};
			}));
		}
	});

</script>

<div class="w-full h-full bg-gray-50 dark:bg-gray-900">
	<SvelteFlow
		nodes={nodes}
		edges={edges}
		{nodeTypes}
		{edgeTypes}
		fitView
		fitViewOptions={{ padding: 0.2 }}
		connectionLineType={ConnectionLineType.SmoothStep}
		defaultEdgeOptions={{
			type: 'sygra',
			animated: false
		}}
		nodesDraggable={true}
		nodesConnectable={false}
		elementsSelectable={true}
		on:nodeclick={(event) => {
			console.log('SvelteFlow on:nodeclick fired:', event.detail.node);
			dispatch('nodeSelect', event.detail.node.id);
			dispatch('edgeSelect', null);
		}}
		on:edgeclick={(event) => {
			console.log('SvelteFlow on:edgeclick fired:', event.detail);
			const edge = event.detail.edge;
			if (edge) {
				console.log('Edge data:', edge.data);
				// Dispatch nodeSelect FIRST to clear node, then edgeSelect
				dispatch('nodeSelect', '');
				dispatch('edgeSelect', getEdgeSelectData(edge));
			}
		}}
		on:paneclick={() => {
			console.log('SvelteFlow on:paneclick fired');
			dispatch('nodeSelect', '');
			dispatch('edgeSelect', null);
		}}
	>
		<!-- Workflow boundary visualization (behind nodes, in viewport coordinates) -->
		<ViewportPortal>
			<WorkflowBoundary bounds={$workflowBounds} {isDarkMode} />
		</ViewportPortal>

		<!-- FitView helper - responds to fitViewTrigger changes -->
		<FitViewHelper trigger={fitViewTrigger} />

		<!-- Export button -->
		<Panel position="top-right" class="!m-2 !p-0">
			<ExportHelper workflowName={workflow.name} />
		</Panel>

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
							nodeColor={(node) => nodeColors[node.type ?? 'llm'] ?? '#6b7280'}
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
</div>
