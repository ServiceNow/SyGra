<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { ArrowLeft, ArrowRight, Bot, Zap, Database, Boxes, Play, Square, Globe, GitBranch, Download, Shuffle, GitCompareArrows, Link2 } from 'lucide-svelte';
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
		weighted_sampler: Shuffle,
		multi_llm: GitCompareArrows
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
		weighted_sampler: '#a855f7',
		multi_llm: '#06b6d4'
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

	let totalConnections = $derived(incomingConnections().length + outgoingConnections().length);

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

{#if totalConnections === 0}
	<!-- Empty state - compact -->
	<div class="flex items-center gap-2 py-1 text-xs text-gray-400 dark:text-gray-500">
		<Link2 size={12} />
		<span class="italic">No connections</span>
	</div>
{:else}
	<!-- Compact inline layout -->
	<div class="flex flex-col gap-2">
		<!-- Inputs row -->
		{#if incomingConnections().length > 0}
			<div class="flex items-center gap-2 flex-wrap">
				<div class="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">
					<ArrowLeft size={10} />
					<span class="font-medium">From</span>
				</div>
				{#each incomingConnections() as conn}
					{@const Icon = getIcon(conn.nodeType)}
					{@const color = getColor(conn.nodeType)}
					<button
						onclick={() => handleNodeClick(conn.nodeId)}
						class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition-all hover:opacity-80 cursor-pointer"
						style="background-color: {color}15; color: {color}"
						title="Go to {conn.nodeName}"
					>
						<span
							class="w-3.5 h-3.5 rounded flex items-center justify-center text-white flex-shrink-0"
							style="background-color: {color}"
						>
							<Icon size={8} />
						</span>
						<span class="truncate max-w-[100px]">{conn.nodeName}</span>
						{#if conn.label}
							<span class="text-[9px] opacity-70">({conn.label})</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}

		<!-- Outputs row -->
		{#if outgoingConnections().length > 0}
			<div class="flex items-center gap-2 flex-wrap">
				<div class="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500 flex-shrink-0">
					<ArrowRight size={10} />
					<span class="font-medium">To</span>
				</div>
				{#each outgoingConnections() as conn}
					{@const Icon = getIcon(conn.nodeType)}
					{@const color = getColor(conn.nodeType)}
					<button
						onclick={() => handleNodeClick(conn.nodeId)}
						class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium transition-all hover:opacity-80 cursor-pointer"
						style="background-color: {color}15; color: {color}"
						title="Go to {conn.nodeName}"
					>
						<span
							class="w-3.5 h-3.5 rounded flex items-center justify-center text-white flex-shrink-0"
							style="background-color: {color}"
						>
							<Icon size={8} />
						</span>
						<span class="truncate max-w-[100px]">{conn.nodeName}</span>
						{#if conn.label}
							<span class="text-[9px] opacity-70">({conn.label})</span>
						{/if}
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}
