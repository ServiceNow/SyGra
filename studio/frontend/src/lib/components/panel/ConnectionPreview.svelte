<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ArrowLeft, ArrowRight, Bot, Zap, Database, Boxes, Play, Square, Globe, GitBranch, Download, Shuffle } from 'lucide-svelte';
	import type { WorkflowNode, WorkflowEdge } from '$lib/stores/workflow.svelte';

	interface Props {
		nodeId: string;
		nodes: WorkflowNode[];
		edges: WorkflowEdge[];
	}

	let { nodeId, nodes, edges }: Props = $props();

	const dispatch = createEventDispatcher<{
		navigate: string;
	}>();

	// Node type to icon mapping
	const nodeIcons: Record<string, any> = {
		llm: Bot,
		agent: Bot,
		lambda: Zap,
		data: Database,
		subgraph: Boxes,
		start: Play,
		end: Square,
		output: Download,
		web_agent: Globe,
		branch: GitBranch,
		weighted_sampler: Shuffle
	};

	// Node type to color mapping
	const nodeColors: Record<string, string> = {
		llm: '#8b5cf6',
		agent: '#ec4899',
		lambda: '#f97316',
		data: '#0ea5e9',
		subgraph: '#3b82f6',
		start: '#22c55e',
		end: '#ef4444',
		output: '#10b981',
		web_agent: '#ec4899',
		branch: '#eab308',
		weighted_sampler: '#a855f7'
	};

	// Find incoming connections (edges where this node is the target)
	let incomingConnections = $derived(() => {
		const incoming = edges.filter(e => e.target === nodeId);
		return incoming.map(edge => {
			const sourceNode = nodes.find(n => n.id === edge.source);
			return {
				edgeId: edge.id,
				nodeId: edge.source,
				nodeName: sourceNode?.summary || edge.source,
				nodeType: sourceNode?.node_type || 'unknown',
				label: edge.label
			};
		});
	});

	// Find outgoing connections (edges where this node is the source)
	let outgoingConnections = $derived(() => {
		const outgoing = edges.filter(e => e.source === nodeId);
		return outgoing.map(edge => {
			const targetNode = nodes.find(n => n.id === edge.target);
			return {
				edgeId: edge.id,
				nodeId: edge.target,
				nodeName: targetNode?.summary || edge.target,
				nodeType: targetNode?.node_type || 'unknown',
				label: edge.label
			};
		});
	});

	function handleNodeClick(targetNodeId: string) {
		dispatch('navigate', targetNodeId);
	}

	function getIcon(nodeType: string) {
		return nodeIcons[nodeType] || Boxes;
	}

	function getColor(nodeType: string) {
		return nodeColors[nodeType] || '#6b7280';
	}
</script>

<div class="space-y-3">
	<!-- Incoming connections -->
	<div>
		<div class="flex items-center gap-2 mb-2">
			<ArrowLeft size={12} class="text-gray-400" />
			<span class="text-xs font-medium text-gray-500 dark:text-gray-400">
				Inputs ({incomingConnections().length})
			</span>
		</div>

		{#if incomingConnections().length === 0}
			<div class="text-xs text-gray-400 dark:text-gray-500 italic pl-5">
				No incoming connections
			</div>
		{:else}
			<div class="flex flex-wrap gap-1.5 pl-5">
				{#each incomingConnections() as conn}
					{@const Icon = getIcon(conn.nodeType)}
					{@const color = getColor(conn.nodeType)}
					<button
						onclick={() => handleNodeClick(conn.nodeId)}
						class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-all border hover:shadow-sm cursor-pointer group"
						style="background-color: {color}10; border-color: {color}30; color: {color}"
						title="Go to {conn.nodeName}"
					>
						<span
							class="w-4 h-4 rounded flex items-center justify-center text-white flex-shrink-0"
							style="background-color: {color}"
						>
							<Icon size={10} />
						</span>
						<span class="truncate max-w-[120px] group-hover:underline">
							{conn.nodeName}
						</span>
						{#if conn.label}
							<span class="text-[10px] px-1 py-0.5 rounded bg-white/50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400">
								{conn.label}
							</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Outgoing connections -->
	<div>
		<div class="flex items-center gap-2 mb-2">
			<ArrowRight size={12} class="text-gray-400" />
			<span class="text-xs font-medium text-gray-500 dark:text-gray-400">
				Outputs ({outgoingConnections().length})
			</span>
		</div>

		{#if outgoingConnections().length === 0}
			<div class="text-xs text-gray-400 dark:text-gray-500 italic pl-5">
				No outgoing connections
			</div>
		{:else}
			<div class="flex flex-wrap gap-1.5 pl-5">
				{#each outgoingConnections() as conn}
					{@const Icon = getIcon(conn.nodeType)}
					{@const color = getColor(conn.nodeType)}
					<button
						onclick={() => handleNodeClick(conn.nodeId)}
						class="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs font-medium transition-all border hover:shadow-sm cursor-pointer group"
						style="background-color: {color}10; border-color: {color}30; color: {color}"
						title="Go to {conn.nodeName}"
					>
						<span
							class="w-4 h-4 rounded flex items-center justify-center text-white flex-shrink-0"
							style="background-color: {color}"
						>
							<Icon size={10} />
						</span>
						<span class="truncate max-w-[120px] group-hover:underline">
							{conn.nodeName}
						</span>
						{#if conn.label}
							<span class="text-[10px] px-1 py-0.5 rounded bg-white/50 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400">
								{conn.label}
							</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
