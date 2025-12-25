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

	// Edge component
	import SygraEdge from './renderers/edges/SygraEdge.svelte';

	// Workflow boundary visualization
	import WorkflowBoundary from './WorkflowBoundary.svelte';

	// FitView helper (must be inside SvelteFlow to use useSvelteFlow hook)
	import FitViewHelper from './FitViewHelper.svelte';

	// Import SvelteFlow styles
	import '@xyflow/svelte/dist/style.css';

	interface Props {
		workflow: Workflow;
		execution?: Execution | null;
	}

	let { workflow, execution = null }: Props = $props();

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
		agent: AgentNode
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
		agent: '#ec4899'
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

	// Node types that are part of the main workflow (inside the boundary)
	// Excludes: 'data' (input), 'output' (result), and 'tool' which stay outside
	const workflowNodeTypes = new Set([
		'start', 'end', 'llm', 'lambda', 'subgraph',
		'weighted_sampler', 'connector', 'web_agent', 'agent'
	]);

	// Estimated node dimensions for bounding box calculation (based on NodeWrapper styles)
	// These heights account for: header (~56px) + optional content + potential duration display
	// Overestimated slightly to ensure proper margins around the workflow boundary
	const nodeDimensions: Record<string, { width: number; height: number }> = {
		start: { width: 160, height: 70 },
		end: { width: 160, height: 70 },
		llm: { width: 240, height: 90 },
		lambda: { width: 220, height: 85 },
		subgraph: { width: 260, height: 100 },
		weighted_sampler: { width: 240, height: 90 },
		connector: { width: 180, height: 70 },
		web_agent: { width: 220, height: 85 },
		agent: { width: 240, height: 90 },
		data: { width: 200, height: 80 },
		output: { width: 200, height: 80 }
	};

	// Derive bounding box for workflow nodes (excluding data and output)
	const workflowBounds = derived(nodes, ($nodes) => {
		const workflowNodes = $nodes.filter(n => workflowNodeTypes.has(n.type || ''));

		if (workflowNodes.length === 0) return null;

		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

		workflowNodes.forEach(node => {
			const dims = nodeDimensions[node.type || 'llm'] || { width: 180, height: 70 };
			const x = node.position.x;
			const y = node.position.y;

			minX = Math.min(minX, x);
			minY = Math.min(minY, y);
			maxX = Math.max(maxX, x + dims.width);
			maxY = Math.max(maxY, y + dims.height);
		});

		// Add padding around the boundary
		// Use asymmetric padding to account for node rendering differences
		const paddingLeft = 25;
		const paddingRight = 45;  // Extra padding on right side
		const paddingTop = 25;
		const paddingBottom = 40;  // Extra padding on bottom to match visual appearance of other sides

		return {
			x: minX - paddingLeft,
			y: minY - paddingTop,
			width: (maxX - minX) + paddingLeft + paddingRight,
			height: (maxY - minY) + paddingTop + paddingBottom
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
			import('$lib/utils/layoutUtils').then(({ autoLayout }) => {
				const result = autoLayout(workflow.nodes, workflow.edges);

				// Reset position cache with layouted positions
				nodePositions = new Map();
				result.nodes.forEach(node => {
					nodePositions.set(node.id, node.position);
				});

				// Full node sync with layouted positions
				nodes.set(result.nodes.map(node => ({
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
				})));

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

				nodes.set(workflow.nodes.map(node => ({
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
				})));

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
			// Also sync edges
			edges.set(currentWf.edges.map(edge => ({
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
					condition: edge.condition
				}
			})));
		}
	});

	// Export function to apply auto-layout
	export async function applyAutoLayout() {
		console.log('applyAutoLayout called');
		try {
			const { autoLayout } = await import('$lib/utils/layoutUtils');

			// Get current node data from store for layout calculation
			const currentNodes = get(nodes);
			const workflowNodes = currentNodes.map(n => ({
				id: n.id,
				node_type: n.type || 'llm',
				position: n.position,
				summary: n.data?.summary || n.id,
				description: n.data?.description || '',
				config: n.data?.config || {}
			}));

			const result = autoLayout(workflowNodes as any, workflow.edges);

			console.log('Auto-layout result:', result);

			// Update position cache
			nodePositions = new Map();
			result.nodes.forEach(node => {
				nodePositions.set(node.id, node.position);
			});

			// Update nodes with new positions
			nodes.update(currentNodes =>
				currentNodes.map(node => {
					const newPosition = nodePositions.get(node.id);
					console.log(`Node ${node.id}: old=${JSON.stringify(node.position)}, new=${JSON.stringify(newPosition)}`);
					return newPosition ? { ...node, position: newPosition } : node;
				})
			);
		} catch (e) {
			console.error('Auto-layout failed:', e);
		}
	}

	// Sync edges - only on workflow change, not execution state
	$effect(() => {
		if (workflow.id === lastWorkflowId || !lastWorkflowId) {
			edges.set(workflow.edges.map(edge => ({
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
					condition: edge.condition
				}
			})));
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

		<Controls position="bottom-right" />
		<Background
			gap={20}
			size={1}
			bgColor={isDarkMode ? '#1e293b' : '#f9fafb'}
			patternColor={isDarkMode ? '#334155' : '#e5e7eb'}
		/>
		<MiniMap
			position="bottom-left"
			width={200}
			height={150}
			nodeColor={(node) => nodeColors[node.type ?? 'llm'] ?? '#6b7280'}
			bgColor={isDarkMode ? '#1e293b' : '#ffffff'}
			maskColor={isDarkMode ? 'rgba(30, 41, 59, 0.6)' : 'rgba(240, 240, 240, 0.6)'}
			maskStrokeColor={isDarkMode ? '#475569' : '#cbd5e1'}
			maskStrokeWidth={1}
			pannable={true}
			zoomable={true}
		/>
	</SvelteFlow>
</div>
