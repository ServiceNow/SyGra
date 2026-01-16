<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { Boxes, Loader2, CheckCircle2, XCircle, Clock, Bot, Zap, Database, Settings, Play, Square, Shuffle, Ungroup, Wrench } from 'lucide-svelte';
	import type { NodeExecutionState, NodeConfigOverride } from '$lib/stores/workflow.svelte';
	import { workflowStore } from '$lib/stores/workflow.svelte';
	import { getInnerEdgePath } from '$lib/utils/layoutUtils';

	interface InnerNode {
		id: string;
		node_type: string;
		summary?: string;
		position: { x: number; y: number };
		size?: { width: number; height: number };
		inner_graph?: InnerGraph;
	}

	interface InnerEdge {
		id: string;
		source: string;
		target: string;
	}

	interface InnerGraph {
		name: string;
		nodes: InnerNode[];
		edges: InnerEdge[];
	}

	interface Props {
		data: {
			id: string;
			summary: string;
			subgraph_path?: string;
			inner_graph?: InnerGraph;
			node_config_map?: Record<string, NodeConfigOverride>;  // Override configs for inner nodes
			size?: { width: number; height: number };
			executionState?: NodeExecutionState | null;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

	// Check if node_config_map has any overrides
	let hasOverrides = $derived(data.node_config_map && Object.keys(data.node_config_map).length > 0);
	let overrideCount = $derived(data.node_config_map ? Object.keys(data.node_config_map).length : 0);

	// Node type to icon mapping
	const nodeIcons: Record<string, any> = {
		llm: Bot,
		lambda: Zap,
		subgraph: Boxes,
		data: Database,
		output: Settings,
		start: Play,
		end: Square,
		weighted_sampler: Shuffle,
	};

	// Node type to color mapping
	const nodeColors: Record<string, string> = {
		llm: '#8b5cf6',
		lambda: '#f97316',
		subgraph: '#3b82f6',
		data: '#0ea5e9',
		output: '#10b981',
		start: '#22c55e',
		end: '#ef4444',
		weighted_sampler: '#a855f7',
	};

	// Constants for inner node rendering
	const INNER_PADDING = 12; // Padding around inner content
	const NODE_WIDTH = 140;
	const NODE_HEIGHT = 44;

	// Calculate bounds of inner graph content (finds min/max to normalize positions)
	let innerBounds = $derived(() => {
		if (!data.inner_graph?.nodes?.length) {
			return { minX: 0, minY: 0, width: 200, height: 80 };
		}

		let minX = Infinity, minY = Infinity;
		let maxX = 0, maxY = 0;

		for (const node of data.inner_graph.nodes) {
			const w = node.size?.width || NODE_WIDTH;
			const h = node.size?.height || NODE_HEIGHT;
			const x = node.position?.x || 0;
			const y = node.position?.y || 0;

			minX = Math.min(minX, x);
			minY = Math.min(minY, y);
			maxX = Math.max(maxX, x + w);
			maxY = Math.max(maxY, y + h);
		}

		// Handle edge case
		if (minX === Infinity) minX = 0;
		if (minY === Infinity) minY = 0;

		// Content dimensions = extent of nodes
		const contentWidth = maxX - minX;
		const contentHeight = maxY - minY;

		return {
			minX,
			minY,
			width: Math.max(200, contentWidth + INNER_PADDING * 2),
			height: Math.max(60, contentHeight + INNER_PADDING * 2)
		};
	});

	// Get path for edge with smooth bezier curves (matching main canvas style)
	function getEdgePath(edge: InnerEdge): string {
		const sourceNode = data.inner_graph?.nodes.find(n => n.id === edge.source);
		const targetNode = data.inner_graph?.nodes.find(n => n.id === edge.target);

		if (!sourceNode || !targetNode) return '';

		const bounds = innerBounds();
		const sw = sourceNode.size?.width || NODE_WIDTH;
		const sh = sourceNode.size?.height || NODE_HEIGHT;
		const tw = targetNode.size?.width || NODE_WIDTH;
		const th = targetNode.size?.height || NODE_HEIGHT;

		// Normalize positions (subtract minX/minY) then add padding
		const sx = (sourceNode.position?.x || 0) - bounds.minX + INNER_PADDING;
		const sy = (sourceNode.position?.y || 0) - bounds.minY + INNER_PADDING;
		const tx = (targetNode.position?.x || 0) - bounds.minX + INNER_PADDING;
		const ty = (targetNode.position?.y || 0) - bounds.minY + INNER_PADDING;

		// From right center of source to left center of target
		const x1 = sx + sw;
		const y1 = sy + sh / 2;
		const x2 = tx;
		const y2 = ty + th / 2;

		// Use the utility function for smooth bezier curves
		return getInnerEdgePath(x1, y1, x2, y2);
	}

	let hasInnerGraph = $derived(data.inner_graph && data.inner_graph.nodes && data.inner_graph.nodes.length > 0);

	// Expand/detach the subgraph into individual nodes
	function handleExpand(e: MouseEvent) {
		e.stopPropagation();
		e.preventDefault();

		workflowStore.pushUndo();
		const result = workflowStore.expandSubgraph(data.id);
		if (result) {
			// Dispatch custom event to notify WorkflowBuilder to sync
			window.dispatchEvent(new CustomEvent('subgraph-expanded', {
				detail: { nodeId: data.id, result }
			}));
		}
	}
</script>

{#if hasInnerGraph}
	<!-- Expanded subgraph with inner visualization -->
	<div
		class="relative rounded-xl shadow-lg border-2 bg-white dark:bg-gray-800 transition-all"
		class:border-blue-500={data.executionState?.status === 'running'}
		class:border-green-500={data.executionState?.status === 'completed'}
		class:border-red-500={data.executionState?.status === 'failed'}
		class:border-blue-300={!data.executionState}
		class:dark:border-blue-600={!data.executionState}
		style="width: {innerBounds().width}px"
	>
		<!-- Target handle (left) - positioned outside container -->
		<Handle
			type="target"
			position={Position.Left}
			class="!w-3 !h-3 !bg-blue-400 !border-2 !border-white dark:!border-gray-800 !-left-1.5"
		/>

		<!-- Inner content wrapper to clip backgrounds to rounded corners -->
		<div class="overflow-hidden rounded-[10px]">
			<!-- Subgraph header - compact -->
			<div class="flex items-center gap-2 px-2 py-1.5 bg-blue-500/10 border-b border-blue-200 dark:border-blue-800">
			<div class="w-6 h-6 rounded flex items-center justify-center text-white bg-blue-500 flex-shrink-0">
				<Boxes size={14} />
			</div>
			<div class="flex-1 min-w-0">
				<div class="text-xs font-semibold text-gray-800 dark:text-gray-200 truncate">
					{data.summary || data.id}
				</div>
				<div class="text-[10px] text-blue-600 dark:text-blue-400 truncate flex items-center gap-1">
					<span>{data.inner_graph?.nodes.length || 0} nodes</span>
					{#if hasOverrides}
						<span class="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300" title="Node configuration overrides">
							<Wrench size={8} />
							<span>{overrideCount}</span>
						</span>
					{/if}
				</div>
			</div>

			<!-- Expand/Detach button -->
			<button
				onclick={handleExpand}
				class="p-1 rounded bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/50 dark:hover:bg-blue-800/50 text-blue-600 dark:text-blue-400 transition-colors flex-shrink-0"
				title="Detach nodes from subgraph"
			>
				<Ungroup size={12} />
			</button>

			<!-- Status indicator -->
			{#if data.executionState?.status === 'running'}
				<Loader2 size={14} class="text-blue-500 animate-spin flex-shrink-0" />
			{:else if data.executionState?.status === 'completed'}
				<CheckCircle2 size={14} class="text-green-500 flex-shrink-0" />
			{:else if data.executionState?.status === 'failed'}
				<XCircle size={14} class="text-red-500 flex-shrink-0" />
			{/if}
		</div>

		<!-- Inner graph visualization -->
		<div
			class="relative bg-gray-50 dark:bg-gray-900/50"
			style="height: {innerBounds().height}px"
		>
			<!-- SVG for edges -->
			<svg
				class="absolute inset-0 pointer-events-none"
				style="width: 100%; height: 100%"
			>
				<defs>
					<marker
						id="arrowhead-{data.id}"
						markerWidth="8"
						markerHeight="6"
						refX="8"
						refY="3"
						orient="auto"
					>
						<polygon points="0 0, 8 3, 0 6" fill="#9ca3af" />
					</marker>
				</defs>
				{#each data.inner_graph?.edges || [] as edge}
					<path
						d={getEdgePath(edge)}
						stroke="#9ca3af"
						stroke-width="2"
						fill="none"
						marker-end="url(#arrowhead-{data.id})"
					/>
				{/each}
			</svg>

			<!-- Inner nodes -->
			{#each data.inner_graph?.nodes || [] as innerNode}
				{@const bounds = innerBounds()}
				{@const Icon = nodeIcons[innerNode.node_type] || Boxes}
				{@const color = nodeColors[innerNode.node_type] || '#6b7280'}
				{@const w = innerNode.size?.width || NODE_WIDTH}
				{@const h = innerNode.size?.height || NODE_HEIGHT}
				{@const x = (innerNode.position?.x || 0) - bounds.minX + INNER_PADDING}
				{@const y = (innerNode.position?.y || 0) - bounds.minY + INNER_PADDING}

				<div
					class="absolute rounded-md shadow-sm border bg-white dark:bg-gray-800 overflow-hidden"
					style="left: {x}px; top: {y}px; width: {w}px; height: {h}px; border-color: {color}40"
				>
					<!-- Inner node header - compact -->
					<div
						class="flex items-center gap-1.5 px-1.5 py-1 text-xs h-full"
						style="background-color: {color}10"
					>
						<div
							class="w-4 h-4 rounded flex items-center justify-center text-white flex-shrink-0"
							style="background-color: {color}"
						>
							<Icon size={10} />
						</div>
						<span class="font-medium text-gray-700 dark:text-gray-300 truncate text-[11px]">
							{innerNode.summary || innerNode.id}
						</span>
						{#if innerNode.inner_graph && innerNode.inner_graph.nodes?.length > 0}
							<span class="text-[9px] text-blue-500 ml-auto">+{innerNode.inner_graph.nodes.length}</span>
						{/if}
					</div>
				</div>
			{/each}
		</div>

		<!-- Duration display -->
			{#if data.executionState?.duration_ms}
				<div class="px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-500">
					Duration: {data.executionState.duration_ms}ms
				</div>
			{/if}
		</div>
		<!-- End inner content wrapper -->

		<!-- Source handle (right) -->
		<Handle
			type="source"
			position={Position.Right}
			class="!w-3 !h-3 !bg-blue-400 !border-2 !border-white dark:!border-gray-800"
		/>
	</div>
{:else}
	<!-- Collapsed subgraph (no inner graph loaded) -->
	<div
		class="relative rounded-xl shadow-lg border-2 bg-white dark:bg-gray-800 transition-all min-w-[180px]"
		class:border-blue-500={data.executionState?.status === 'running'}
		class:border-green-500={data.executionState?.status === 'completed'}
		class:border-red-500={data.executionState?.status === 'failed'}
		class:border-gray-200={!data.executionState}
		class:dark:border-gray-700={!data.executionState}
	>
		<!-- Target handle (left) -->
		<Handle
			type="target"
			position={Position.Left}
			class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500 !border-2 !border-white dark:!border-gray-800"
		/>

		<!-- Inner content wrapper to clip backgrounds to rounded corners -->
		<div class="overflow-hidden rounded-[10px]">
			<!-- Node header -->
			<div class="flex items-center gap-3 px-4 py-3 bg-blue-500/10">
				<div class="w-8 h-8 rounded-lg flex items-center justify-center text-white bg-blue-500">
					<Boxes size={18} />
				</div>
				<div class="flex-1 min-w-0">
					<div class="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">
						{data.summary || data.id}
					</div>
					<div class="text-xs text-gray-500 dark:text-gray-400 truncate flex items-center gap-1">
						<span>{data.subgraph_path || 'Subgraph'}</span>
						{#if hasOverrides}
							<span class="inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300" title="Node configuration overrides">
								<Wrench size={10} />
								<span>{overrideCount}</span>
							</span>
						{/if}
					</div>
				</div>

				<!-- Status indicator -->
				{#if data.executionState?.status === 'running'}
					<Loader2 size={18} class="text-blue-500 animate-spin flex-shrink-0" />
				{:else if data.executionState?.status === 'completed'}
					<CheckCircle2 size={18} class="text-green-500 flex-shrink-0" />
				{:else if data.executionState?.status === 'failed'}
					<XCircle size={18} class="text-red-500 flex-shrink-0" />
				{/if}
			</div>

			<!-- Duration display -->
			{#if data.executionState?.duration_ms}
				<div class="px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-xs text-gray-500">
					Duration: {data.executionState.duration_ms}ms
				</div>
			{/if}
		</div>
		<!-- End inner content wrapper -->

		<!-- Source handle (right) -->
		<Handle
			type="source"
			position={Position.Right}
			class="!w-3 !h-3 !bg-gray-400 dark:!bg-gray-500 !border-2 !border-white dark:!border-gray-800"
		/>
	</div>
{/if}
