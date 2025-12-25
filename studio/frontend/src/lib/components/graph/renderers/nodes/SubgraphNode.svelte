<script lang="ts">
	import { Handle, Position } from '@xyflow/svelte';
	import { Boxes, Loader2, CheckCircle2, XCircle, Clock, Bot, Zap, Database, Settings, Play, Square, Shuffle, Ungroup } from 'lucide-svelte';
	import type { NodeExecutionState } from '$lib/stores/workflow.svelte';
	import { workflowStore } from '$lib/stores/workflow.svelte';

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
			executionState?: NodeExecutionState | null;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();

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

	// Calculate bounds for inner graph
	let innerBounds = $derived(() => {
		if (!data.inner_graph?.nodes?.length) return null;

		let minX = Infinity, minY = Infinity, maxX = 0, maxY = 0;
		for (const node of data.inner_graph.nodes) {
			const w = node.size?.width || 150;
			const h = node.size?.height || 60;
			minX = Math.min(minX, node.position.x);
			minY = Math.min(minY, node.position.y);
			maxX = Math.max(maxX, node.position.x + w);
			maxY = Math.max(maxY, node.position.y + h);
		}

		return {
			width: maxX + 40,  // padding
			height: maxY + 40,
		};
	});

	// Get path for edge (simple straight line for now)
	function getEdgePath(edge: InnerEdge): string {
		const sourceNode = data.inner_graph?.nodes.find(n => n.id === edge.source);
		const targetNode = data.inner_graph?.nodes.find(n => n.id === edge.target);

		if (!sourceNode || !targetNode) return '';

		const sw = sourceNode.size?.width || 150;
		const sh = sourceNode.size?.height || 60;
		const tw = targetNode.size?.width || 150;
		const th = targetNode.size?.height || 60;

		// From right center of source to left center of target
		const x1 = sourceNode.position.x + sw;
		const y1 = sourceNode.position.y + sh / 2;
		const x2 = targetNode.position.x;
		const y2 = targetNode.position.y + th / 2;

		// Bezier curve for smooth edges
		const midX = (x1 + x2) / 2;
		return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
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
		style="min-width: {innerBounds()?.width || 300}px"
	>
		<!-- Target handle (left) - positioned outside container -->
		<Handle
			type="target"
			position={Position.Left}
			class="!w-3 !h-3 !bg-blue-400 !border-2 !border-white dark:!border-gray-800 !-left-1.5"
		/>

		<!-- Inner content wrapper to clip backgrounds to rounded corners -->
		<div class="overflow-hidden rounded-[10px]">
			<!-- Subgraph header -->
			<div class="flex items-center gap-3 px-4 py-3 bg-blue-500/10 border-b border-blue-200 dark:border-blue-800">
			<div class="w-8 h-8 rounded-lg flex items-center justify-center text-white bg-blue-500">
				<Boxes size={18} />
			</div>
			<div class="flex-1 min-w-0">
				<div class="text-sm font-semibold text-gray-800 dark:text-gray-200 truncate">
					{data.summary || data.id}
				</div>
				<div class="text-xs text-blue-600 dark:text-blue-400 truncate">
					{data.inner_graph?.name || 'Subgraph'} · {data.inner_graph?.nodes.length || 0} nodes
				</div>
			</div>

			<!-- Expand/Detach button -->
			<button
				onclick={handleExpand}
				class="p-1.5 rounded-lg bg-blue-100 hover:bg-blue-200 dark:bg-blue-900/50 dark:hover:bg-blue-800/50 text-blue-600 dark:text-blue-400 transition-colors flex-shrink-0"
				title="Detach nodes from subgraph"
			>
				<Ungroup size={16} />
			</button>

			<!-- Status indicator -->
			{#if data.executionState?.status === 'running'}
				<Loader2 size={18} class="text-blue-500 animate-spin flex-shrink-0" />
			{:else if data.executionState?.status === 'completed'}
				<CheckCircle2 size={18} class="text-green-500 flex-shrink-0" />
			{:else if data.executionState?.status === 'failed'}
				<XCircle size={18} class="text-red-500 flex-shrink-0" />
			{/if}
		</div>

		<!-- Inner graph visualization -->
		<div
			class="relative p-4 bg-gray-50 dark:bg-gray-900/50"
			style="min-height: {innerBounds()?.height || 100}px"
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
				{@const Icon = nodeIcons[innerNode.node_type] || Boxes}
				{@const color = nodeColors[innerNode.node_type] || '#6b7280'}
				{@const w = innerNode.size?.width || 150}
				{@const h = innerNode.size?.height || 60}

				<div
					class="absolute rounded-lg shadow border bg-white dark:bg-gray-800 overflow-hidden"
					style="left: {innerNode.position.x}px; top: {innerNode.position.y}px; width: {w}px; min-height: {h}px; border-color: {color}40"
				>
					<!-- Inner node header -->
					<div
						class="flex items-center gap-2 px-2 py-1.5 text-xs"
						style="background-color: {color}15"
					>
						<div
							class="w-5 h-5 rounded flex items-center justify-center text-white"
							style="background-color: {color}"
						>
							<Icon size={12} />
						</div>
						<span class="font-medium text-gray-700 dark:text-gray-300 truncate">
							{innerNode.summary || innerNode.id}
						</span>
					</div>

					<!-- Recursive subgraph indicator -->
					{#if innerNode.inner_graph && innerNode.inner_graph.nodes?.length > 0}
						<div class="px-2 py-1 text-[10px] text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30">
							↳ {innerNode.inner_graph.nodes.length} inner nodes
						</div>
					{/if}
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
					<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
						{data.subgraph_path || 'Subgraph'}
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
