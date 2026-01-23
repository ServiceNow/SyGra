<script lang="ts">
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
		ConnectionLineType,
		Position,
		MarkerType
	} from '@xyflow/svelte';
	import { writable } from 'svelte/store';
	import { workflowStore, type Execution, type Workflow, type NodeExecutionState } from '$lib/stores/workflow.svelte';
	import { onMount, tick } from 'svelte';
	import { autoLayout } from '$lib/utils/layoutUtils';
	import {
		CheckCircle2, XCircle, Clock, Loader2, Ban, AlertTriangle,
		GitBranch, Timer, ChevronRight, Activity, LayoutGrid,
		Map as MapIcon, EyeOff
	} from 'lucide-svelte';

	// Reuse the same node components as SygraFlow for consistency
	import StartNode from '$lib/components/graph/renderers/nodes/StartNode.svelte';
	import EndNode from '$lib/components/graph/renderers/nodes/EndNode.svelte';
	import LLMNode from '$lib/components/graph/renderers/nodes/LLMNode.svelte';
	import LambdaNode from '$lib/components/graph/renderers/nodes/LambdaNode.svelte';
	import SubgraphNode from '$lib/components/graph/renderers/nodes/SubgraphNode.svelte';
	import DataNode from '$lib/components/graph/renderers/nodes/DataNode.svelte';
	import OutputNode from '$lib/components/graph/renderers/nodes/OutputNode.svelte';
	import WeightedSamplerNode from '$lib/components/graph/renderers/nodes/WeightedSamplerNode.svelte';
	import AgentNode from '$lib/components/graph/renderers/nodes/AgentNode.svelte';

	// Reuse edge component
	import SygraEdge from '$lib/components/graph/renderers/edges/SygraEdge.svelte';

	// FitView helper (must be inside SvelteFlow to use useSvelteFlow hook)
	import FitViewHelper from '$lib/components/graph/FitViewHelper.svelte';

	import '@xyflow/svelte/dist/style.css';

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	// Workflow loading state
	let workflow = $state<Workflow | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	// Dark mode detection
	let isDarkMode = $state(false);

	// Selected node in timeline
	let selectedNodeId = $state<string | null>(null);

	// Minimap visibility state
	let showMinimap = $state(true);

	// Node type mapping - same as SygraFlow
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

	// Node colors for MiniMap (same as SygraFlow)
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

	// Status configuration using design tokens
	const statusConfig: Record<string, { icon: typeof Clock; color: string; bgColor: string; textColor: string }> = {
		pending: { icon: Clock, color: 'bg-surface-tertiary', bgColor: 'bg-surface-secondary', textColor: 'text-text-muted' },
		running: { icon: Loader2, color: 'bg-info-light', bgColor: 'bg-info-light', textColor: 'text-info' },
		completed: { icon: CheckCircle2, color: 'bg-success-light', bgColor: 'bg-success-light', textColor: 'text-success' },
		failed: { icon: XCircle, color: 'bg-error-light', bgColor: 'bg-error-light', textColor: 'text-error' },
		cancelled: { icon: Ban, color: 'bg-warning-light', bgColor: 'bg-warning-light', textColor: 'text-warning' },
		skipped: { icon: AlertTriangle, color: 'bg-warning-light', bgColor: 'bg-warning-light', textColor: 'text-warning' }
	};

	// Create Svelte stores for SvelteFlow
	const nodes = writable<Node[]>([]);
	const edges = writable<Edge[]>([]);

	// Store to trigger fitView - increment to trigger
	const fitViewTrigger = writable(0);

	// Track if we've triggered initial fitView
	let hasTriggeredInitialFitView = false;

	// Load workflow data
	onMount(async () => {
		isDarkMode = document.documentElement.classList.contains('dark');

		const observer = new MutationObserver(() => {
			isDarkMode = document.documentElement.classList.contains('dark');
		});
		observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

		if (execution.workflow_id) {
			try {
				const response = await fetch(`/api/workflows/${execution.workflow_id}`);
				if (response.ok) {
					workflow = await response.json();
				} else {
					error = 'Failed to load workflow structure';
				}
			} catch (e) {
				error = 'Failed to load workflow';
				console.error('Failed to load workflow:', e);
			}
		}
		loading = false;

		return () => observer.disconnect();
	});

	// Check if any node is running
	let hasRunningNode = $derived(() => {
		return Object.values(execution.node_states).some(s => s.status === 'running');
	});

	// Get effective status for a node
	function getEffectiveStatus(nodeId: string): string {
		const nodeState = execution.node_states[nodeId];
		if (!nodeState) return 'pending';

		if (nodeState.status === 'completed' || nodeState.status === 'failed' || nodeState.status === 'cancelled') {
			return nodeState.status;
		}

		// Check if any previous node failed
		let hasPreviousFailed = false;
		for (const [, state] of Object.entries(execution.node_states)) {
			if (state.status === 'failed' || state.status === 'cancelled') {
				hasPreviousFailed = true;
				break;
			}
		}

		if (hasPreviousFailed && nodeState.status === 'pending') {
			return 'skipped';
		}

		return nodeState.status;
	}

	// Convert workflow to SvelteFlow nodes/edges with execution state
	$effect(() => {
		if (!workflow) return;

		// Apply auto layout synchronously
		const layoutResult = autoLayout(workflow.nodes, workflow.edges);

		// Create nodes with execution state - using same structure as SygraFlow
		const flowNodes: Node[] = layoutResult.nodes.map(node => ({
			id: node.id,
			type: node.node_type,
			position: node.position,
			data: {
				...node,
				executionState: execution.node_states[node.id] ?? null,
				isCurrentNode: execution.current_node === node.id,
				nodeType: node.node_type,
				hasRunningNode: hasRunningNode()
			},
			sourcePosition: Position.Right,
			targetPosition: Position.Left,
			selectable: true,
			draggable: false
		}));

		// Create edges with execution-aware styling (use original workflow edges)
		const flowEdges: Edge[] = workflow.edges.map(edge => {
			const sourceState = execution.node_states[edge.source];
			const targetState = execution.node_states[edge.target];

			const isActive = sourceState?.status === 'completed' && targetState?.status === 'running';

			return {
				id: edge.id,
				source: edge.source,
				target: edge.target,
				type: 'sygra',
				selectable: false,
				animated: isActive,
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
			};
		});

		nodes.set(flowNodes);
		edges.set(flowEdges);

		// Trigger fitView only on initial load
		if (!hasTriggeredInitialFitView) {
			hasTriggeredInitialFitView = true;
			tick().then(() => {
				fitViewTrigger.update(n => n + 1);
			});
		}
	});

	// Timeline nodes (filtered and ordered)
	let timelineNodes = $derived(() => {
		const skipTypes = ['data', 'output'];
		return Object.entries(execution.node_states)
			.filter(([id]) => !skipTypes.some(t => id.toLowerCase().includes(t)))
			.map(([id, state]) => {
				const effectiveStatus = getEffectiveStatus(id);
				const config = statusConfig[effectiveStatus] || statusConfig.pending;
				return {
					id,
					status: effectiveStatus,
					duration_ms: state.duration_ms,
					started_at: state.started_at,
					...config
				};
			});
	});

	// Statistics
	let stats = $derived(() => {
		const states = Object.values(execution.node_states);
		return {
			total: states.length,
			completed: states.filter(s => s.status === 'completed').length,
			failed: states.filter(s => s.status === 'failed' || s.status === 'cancelled').length,
			running: states.filter(s => s.status === 'running').length
		};
	});

	// Total duration for percentage calculations
	let totalDuration = $derived(() => {
		return execution.duration_ms || timelineNodes().reduce((sum, n) => sum + (n.duration_ms || 0), 0) || 1;
	});

	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		const s = ms / 1000;
		if (s < 60) return `${s.toFixed(1)}s`;
		const m = Math.floor(s / 60);
		return `${m}m ${Math.floor(s % 60)}s`;
	}

	function handleNodeClick(nodeId: string) {
		selectedNodeId = selectedNodeId === nodeId ? null : nodeId;
	}

	function handleAutoLayout() {
		if (!workflow) return;

		const result = autoLayout(workflow.nodes, workflow.edges);

		// Update nodes with new positions
		nodes.update(currentNodes =>
			currentNodes.map(node => {
				const layoutedNode = result.nodes.find(n => n.id === node.id);
				return layoutedNode ? { ...node, position: layoutedNode.position } : node;
			})
		);
	}
</script>

<div class="flex h-full">
	<!-- Main graph area -->
	<div class="flex-1 relative bg-surface-secondary">
		{#if loading}
			<div class="flex items-center justify-center h-full">
				<div class="flex items-center gap-3 text-text-muted">
					<Loader2 size={24} class="animate-spin" />
					<span>Loading execution graph...</span>
				</div>
			</div>
		{:else if error}
			<div class="flex items-center justify-center h-full">
				<div class="flex flex-col items-center gap-3 text-text-muted">
					<AlertTriangle size={48} class="text-warning" />
					<span>{error}</span>
				</div>
			</div>
		{:else if !workflow}
			<div class="flex items-center justify-center h-full">
				<div class="flex flex-col items-center gap-3 text-text-muted">
					<GitBranch size={48} class="opacity-50" />
					<span>No workflow data available</span>
				</div>
			</div>
		{:else}
			<SvelteFlow
				nodes={nodes}
				edges={edges}
				nodeTypes={nodeTypes}
				edgeTypes={edgeTypes}
				fitView
				fitViewOptions={{ padding: 0.2 }}
				connectionLineType={ConnectionLineType.SmoothStep}
				defaultEdgeOptions={{ type: 'sygra', animated: false }}
				nodesDraggable={false}
				nodesConnectable={false}
				elementsSelectable={true}
				panOnDrag={true}
				zoomOnScroll={true}
				on:nodeclick={(e) => handleNodeClick(e.detail.node.id)}
			>
				<!-- FitView helper - responds to fitViewTrigger changes -->
				<FitViewHelper trigger={fitViewTrigger} />

				<!-- Auto Layout button -->
				<Panel position="top-left" class="!m-3">
					<button
						onclick={handleAutoLayout}
						title="Auto-arrange nodes using DAG layout"
						class="flex items-center gap-2 px-3 py-2 bg-surface-elevated text-text-secondary hover:bg-surface-hover rounded-lg shadow-md border border-[var(--border)] transition-colors text-sm font-medium"
					>
						<LayoutGrid size={16} />
						Auto Layout
					</button>
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
							class="flex items-center justify-center w-6 h-6 bg-surface-elevated border border-[var(--border)] rounded shadow-sm hover:bg-surface-hover transition-colors"
							title={showMinimap ? 'Hide minimap' : 'Show minimap'}
						>
							{#if showMinimap}
								<EyeOff size={12} class="text-text-muted" />
							{:else}
								<MapIcon size={12} class="text-text-muted" />
							{/if}
						</button>

						<!-- Minimap -->
						{#if showMinimap}
							<div class="rounded-lg overflow-hidden border border-[var(--border)] shadow-sm">
								<MiniMap
									width={140}
									height={90}
									nodeColor={(node) => nodeColors[node.type ?? 'llm'] ?? '#6b7280'}
									bgColor={isDarkMode ? '#1e293b' : '#ffffff'}
									maskColor={isDarkMode ? 'rgba(30, 41, 59, 0.6)' : 'rgba(240, 240, 240, 0.6)'}
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
	</div>

	<!-- Timeline sidebar -->
	<div class="w-72 flex-shrink-0 border-l border-[var(--border)] bg-surface-elevated flex flex-col">
		<!-- Header with stats -->
		<div class="p-4 border-b border-[var(--border)]">
			<h3 class="text-sm font-semibold text-text-secondary flex items-center gap-2 mb-3">
				<Activity size={16} class="text-node-llm" />
				Execution Timeline
			</h3>
			<div class="flex items-center gap-3 text-xs">
				<span class="flex items-center gap-1 text-success">
					<CheckCircle2 size={12} />
					{stats().completed}
				</span>
				{#if stats().failed > 0}
					<span class="flex items-center gap-1 text-error">
						<XCircle size={12} />
						{stats().failed}
					</span>
				{/if}
				{#if stats().running > 0}
					<span class="flex items-center gap-1 text-info">
						<Loader2 size={12} class="animate-spin" />
						{stats().running}
					</span>
				{/if}
				<span class="text-text-muted ml-auto">
					{stats().completed + stats().failed}/{stats().total}
				</span>
			</div>
		</div>

		<!-- Timeline list -->
		<div class="flex-1 overflow-y-auto p-3 space-y-1">
			{#each timelineNodes() as node (node.id)}
				{@const Icon = node.icon}
				{@const widthPct = Math.min(Math.max((node.duration_ms || 0) / totalDuration() * 100, 8), 100)}
				<button
					class="w-full text-left p-2 rounded-lg transition-all {selectedNodeId === node.id ? 'bg-info-light ring-1 ring-info' : 'hover:bg-surface-hover'}"
					onclick={() => handleNodeClick(node.id)}
				>
					<div class="flex items-center gap-2 mb-1">
						<Icon size={14} class="{node.textColor} {node.status === 'running' ? 'animate-spin' : ''}" />
						<span class="text-sm font-medium text-text-primary truncate flex-1" title={node.id}>
							{node.id}
						</span>
						{#if node.duration_ms}
							<span class="text-xs text-text-muted flex items-center gap-1">
								<Timer size={10} />
								{formatDuration(node.duration_ms)}
							</span>
						{/if}
					</div>
					<!-- Duration bar -->
					<div class="h-1.5 bg-surface-tertiary rounded-full overflow-hidden">
						<div
							class="h-full rounded-full transition-all duration-300 {node.status === 'completed' ? 'bg-success' : node.status === 'failed' || node.status === 'cancelled' ? 'bg-error' : node.status === 'running' ? 'bg-info animate-pulse' : 'bg-surface-border'}"
							style="width: {widthPct}%"
						></div>
					</div>
				</button>
			{/each}

			{#if timelineNodes().length === 0}
				<div class="text-center py-8 text-text-muted">
					<Clock size={32} class="mx-auto mb-2 opacity-50" />
					<p class="text-sm">No execution data</p>
				</div>
			{/if}
		</div>

		<!-- Footer with total duration -->
		{#if execution.duration_ms}
			<div class="p-3 border-t border-[var(--border)] bg-surface-secondary">
				<div class="flex items-center justify-between text-sm">
					<span class="text-text-secondary">Total Duration</span>
					<span class="font-semibold text-text-primary">
						{formatDuration(execution.duration_ms)}
					</span>
				</div>
			</div>
		{/if}
	</div>
</div>
