<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import {
		SvelteFlow,
		Background,
		type Node,
		type Edge,
		type NodeTypes,
		Position,
		MarkerType
	} from '@xyflow/svelte';
	import { writable } from 'svelte/store';
	import type { Recipe } from '$lib/stores/recipe.svelte';
	import { X, Plus, Clock, Layers, Tag, User } from 'lucide-svelte';

	import StartNode from '../graph/renderers/nodes/StartNode.svelte';
	import EndNode from '../graph/renderers/nodes/EndNode.svelte';
	import LLMNode from '../graph/renderers/nodes/LLMNode.svelte';
	import LambdaNode from '../graph/renderers/nodes/LambdaNode.svelte';
	import SubgraphNode from '../graph/renderers/nodes/SubgraphNode.svelte';
	import DataNode from '../graph/renderers/nodes/DataNode.svelte';
	import OutputNode from '../graph/renderers/nodes/OutputNode.svelte';
	import WeightedSamplerNode from '../graph/renderers/nodes/WeightedSamplerNode.svelte';

	import '@xyflow/svelte/dist/style.css';

	interface Props {
		recipe: Recipe;
	}

	let { recipe }: Props = $props();

	const dispatch = createEventDispatcher<{
		close: void;
		addToWorkflow: { recipe: Recipe };
	}>();

	// Node type components
	const nodeTypes: NodeTypes = {
		start: StartNode,
		end: EndNode,
		llm: LLMNode,
		lambda: LambdaNode,
		subgraph: SubgraphNode,
		data: DataNode,
		output: OutputNode,
		weighted_sampler: WeightedSamplerNode
	};

	// Create stores for SvelteFlow
	const flowNodes = writable<Node[]>([]);
	const flowEdges = writable<Edge[]>([]);

	// Initialize stores on mount and when recipe changes
	$effect(() => {
		// Convert recipe nodes to SvelteFlow format
		const nodes: Node[] = recipe.nodes.map(node => ({
			id: node.id,
			type: node.node_type,
			position: node.position || { x: 0, y: 0 },
			data: {
				label: node.summary || node.id,
				summary: node.summary,
				description: node.description,
				node_type: node.node_type,
				model: node.model,
				prompt: node.prompt,
				pre_process: node.pre_process,
				post_process: node.post_process,
				function_path: node.function_path,
				subgraph_path: node.subgraph_path,
				inner_graph: node.inner_graph,
				data_config: node.data_config,
				output_config: node.output_config,
				sampler_config: node.sampler_config
			},
			sourcePosition: Position.Right,
			targetPosition: Position.Left
		}));

		// Convert recipe edges to SvelteFlow format
		const edges: Edge[] = recipe.edges.map(edge => ({
			id: edge.id,
			source: edge.source,
			target: edge.target,
			label: edge.label,
			type: 'smoothstep',
			animated: false,
			markerEnd: { type: MarkerType.ArrowClosed }
		}));

		flowNodes.set(nodes);
		flowEdges.set(edges);
	});

	// Dark mode detection
	let isDarkMode = $state(false);
	$effect(() => {
		isDarkMode = document.documentElement.classList.contains('dark');
		const observer = new MutationObserver(() => {
			isDarkMode = document.documentElement.classList.contains('dark');
		});
		observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => observer.disconnect();
	});

	function formatDate(dateStr: string): string {
		return new Date(dateStr).toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric'
		});
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('close');
		}
	}

	function handleAddToWorkflow() {
		dispatch('addToWorkflow', { recipe });
		dispatch('close');
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div
	class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
	onclick={() => dispatch('close')}
	onkeydown={(e) => e.key === 'Escape' && dispatch('close')}
	role="button"
	tabindex="-1"
>
	<div
		class="bg-surface rounded-xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-surface-border">
			<div>
				<h3 class="text-lg font-semibold text-text-primary">
					{recipe.name}
				</h3>
				{#if recipe.description}
					<p class="text-sm text-text-muted mt-0.5">
						{recipe.description}
					</p>
				{/if}
			</div>
			<button
				onclick={() => dispatch('close')}
				class="p-1.5 rounded-lg hover:bg-surface-hover text-text-muted transition-colors"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Recipe Info -->
		<div class="px-6 py-3 border-b border-surface-border bg-surface-secondary">
			<div class="flex flex-wrap items-center gap-4 text-sm">
				<div class="flex items-center gap-1.5 text-text-secondary">
					<Layers size={14} />
					<span>{recipe.nodeCount} nodes</span>
				</div>
				<div class="flex items-center gap-1.5 text-text-secondary">
					<Clock size={14} />
					<span>Updated {formatDate(recipe.updatedAt)}</span>
				</div>
				{#if recipe.author}
					<div class="flex items-center gap-1.5 text-text-secondary">
						<User size={14} />
						<span>{recipe.author}</span>
					</div>
				{/if}
				{#if recipe.tags.length > 0}
					<div class="flex items-center gap-1.5">
						<Tag size={14} class="text-text-muted" />
						{#each recipe.tags as tag}
							<span class="px-2 py-0.5 text-xs rounded-full bg-surface-tertiary text-text-secondary">
								{tag}
							</span>
						{/each}
					</div>
				{/if}
			</div>
		</div>

		<!-- Graph Preview -->
		<div class="h-[400px] relative bg-surface-secondary">
			<SvelteFlow
				nodes={flowNodes}
				edges={flowEdges}
				{nodeTypes}
				fitView
				fitViewOptions={{ padding: 0.3 }}
				nodesDraggable={false}
				nodesConnectable={false}
				elementsSelectable={false}
				panOnDrag={true}
				zoomOnScroll={true}
				colorMode={isDarkMode ? 'dark' : 'light'}
				style="width: 100%; height: 100%;"
			>
				<Background
					bgColor={isDarkMode ? '#111827' : '#f9fafb'}
					patternColor={isDarkMode ? '#374151' : '#e5e7eb'}
				/>
			</SvelteFlow>

			<!-- Overlay hint -->
			<div class="absolute bottom-4 left-4 text-xs text-text-muted bg-surface/80 px-2 py-1 rounded">
				Scroll to zoom • Drag to pan
			</div>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-between px-6 py-4 border-t border-surface-border bg-surface-secondary rounded-b-xl">
			<div class="text-sm text-text-muted">
				Node types: {recipe.nodeTypes.join(', ')}
			</div>
			<div class="flex items-center gap-3">
				<button
					onclick={() => dispatch('close')}
					class="px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-hover rounded-lg transition-colors"
				>
					Close
				</button>
				<button
					onclick={handleAddToWorkflow}
					class="btn-accent flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors"
				>
					<Plus size={16} />
					Add to Workflow
				</button>
			</div>
		</div>
	</div>
</div>
