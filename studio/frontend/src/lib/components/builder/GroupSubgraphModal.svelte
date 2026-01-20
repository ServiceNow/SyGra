<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, Boxes, AlertCircle, Library } from 'lucide-svelte';
	import type { WorkflowNode, WorkflowEdge } from '$lib/stores/workflow.svelte';

	interface Props {
		selectedNodes: WorkflowNode[];
		allEdges: WorkflowEdge[];
	}

	let { selectedNodes, allEdges }: Props = $props();

	const dispatch = createEventDispatcher<{
		confirm: { name: string; description: string; saveAsRecipe: boolean };
		cancel: void;
	}>();

	let subgraphName = $state('');
	let subgraphDescription = $state('');
	let nameError = $state('');
	let saveAsRecipe = $state(false);

	// Calculate stats about the grouping
	let stats = $derived(() => {
		const nodeIds = new Set(selectedNodes.map(n => n.id));

		// Internal edges: both source and target are in selection
		const internalEdges = allEdges.filter(e =>
			nodeIds.has(e.source) && nodeIds.has(e.target)
		);

		// Incoming edges: target is in selection, source is outside
		const incomingEdges = allEdges.filter(e =>
			nodeIds.has(e.target) && !nodeIds.has(e.source)
		);

		// Outgoing edges: source is in selection, target is outside
		const outgoingEdges = allEdges.filter(e =>
			nodeIds.has(e.source) && !nodeIds.has(e.target)
		);

		return {
			nodeCount: selectedNodes.length,
			internalEdgeCount: internalEdges.length,
			incomingEdgeCount: incomingEdges.length,
			outgoingEdgeCount: outgoingEdges.length,
			incomingNodes: [...new Set(incomingEdges.map(e => e.source))],
			outgoingNodes: [...new Set(outgoingEdges.map(e => e.target))]
		};
	});

	// Validation
	let validationErrors = $derived(() => {
		const errors: string[] = [];

		// Check for START/END nodes
		const hasStart = selectedNodes.some(n => n.id === 'START');
		const hasEnd = selectedNodes.some(n => n.id === 'END');

		if (hasStart) {
			errors.push('Cannot include START node in a subgraph');
		}
		if (hasEnd) {
			errors.push('Cannot include END node in a subgraph');
		}

		// Check for DATA/OUTPUT nodes (they should connect to START/END)
		const hasData = selectedNodes.some(n => n.node_type === 'data');
		const hasOutput = selectedNodes.some(n => n.node_type === 'output');

		if (hasData) {
			errors.push('Data nodes should remain at the top level');
		}
		if (hasOutput) {
			errors.push('Output nodes should remain at the top level');
		}

		return errors;
	});

	let isValid = $derived(validationErrors().length === 0 && subgraphName.trim().length > 0);

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('cancel');
		} else if (e.key === 'Enter' && isValid) {
			handleConfirm();
		}
	}

	function handleConfirm() {
		if (!subgraphName.trim()) {
			nameError = 'Please enter a name for the subgraph';
			return;
		}
		if (!isValid) return;

		dispatch('confirm', {
			name: subgraphName.trim(),
			description: subgraphDescription.trim(),
			saveAsRecipe
		});
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div
	class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
	role="dialog"
	aria-modal="true"
	aria-labelledby="modal-title"
>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden"
		onclick={(e) => e.stopPropagation()}
		role="document"
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
			<div class="flex items-center gap-3">
				<div class="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
					<Boxes size={20} class="text-blue-500" />
				</div>
				<div>
					<h2 id="modal-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						Group as Subgraph
					</h2>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						Create a reusable subgraph from selected nodes
					</p>
				</div>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				aria-label="Close"
			>
				<X size={20} class="text-gray-500" />
			</button>
		</div>

		<!-- Content -->
		<div class="px-6 py-4 space-y-4">
			<!-- Validation Errors -->
			{#if validationErrors().length > 0}
				<div class="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
					<div class="flex items-start gap-3">
						<AlertCircle size={20} class="text-red-500 flex-shrink-0 mt-0.5" />
						<div>
							<h4 class="text-sm font-medium text-red-800 dark:text-red-200">
								Cannot create subgraph
							</h4>
							<ul class="mt-1 text-sm text-red-600 dark:text-red-300 list-disc list-inside">
								{#each validationErrors() as error}
									<li>{error}</li>
								{/each}
							</ul>
						</div>
					</div>
				</div>
			{/if}

			<!-- Subgraph Name -->
			<div>
				<label for="subgraph-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					Subgraph Name <span class="text-red-500">*</span>
				</label>
				<input
					id="subgraph-name"
					type="text"
					bind:value={subgraphName}
					placeholder="e.g., Data Processing Pipeline"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					class:border-red-500={nameError}
				/>
				{#if nameError}
					<p class="mt-1 text-sm text-red-500">{nameError}</p>
				{/if}
			</div>

			<!-- Description (optional) -->
			<div>
				<label for="subgraph-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
					Description <span class="text-gray-400">(optional)</span>
				</label>
				<textarea
					id="subgraph-description"
					bind:value={subgraphDescription}
					placeholder="What does this subgraph do?"
					rows="2"
					class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
				></textarea>
			</div>

			<!-- Grouping Preview -->
			<div class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
				<h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
					Grouping Summary
				</h4>
				<div class="grid grid-cols-2 gap-4 text-sm">
					<div>
						<span class="text-gray-500 dark:text-gray-400">Nodes to group:</span>
						<span class="ml-2 font-medium text-gray-900 dark:text-gray-100">{stats().nodeCount}</span>
					</div>
					<div>
						<span class="text-gray-500 dark:text-gray-400">Internal edges:</span>
						<span class="ml-2 font-medium text-gray-900 dark:text-gray-100">{stats().internalEdgeCount}</span>
					</div>
					<div>
						<span class="text-gray-500 dark:text-gray-400">Incoming connections:</span>
						<span class="ml-2 font-medium text-gray-900 dark:text-gray-100">{stats().incomingEdgeCount}</span>
					</div>
					<div>
						<span class="text-gray-500 dark:text-gray-400">Outgoing connections:</span>
						<span class="ml-2 font-medium text-gray-900 dark:text-gray-100">{stats().outgoingEdgeCount}</span>
					</div>
				</div>

				{#if stats().incomingNodes.length > 0 || stats().outgoingNodes.length > 0}
					<div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
						{#if stats().incomingNodes.length > 0}
							<p>← Inputs from: <span class="text-gray-700 dark:text-gray-300">{stats().incomingNodes.join(', ')}</span></p>
						{/if}
						{#if stats().outgoingNodes.length > 0}
							<p>→ Outputs to: <span class="text-gray-700 dark:text-gray-300">{stats().outgoingNodes.join(', ')}</span></p>
						{/if}
					</div>
				{/if}
			</div>

			<!-- Selected Nodes List -->
			<div>
				<h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
					Selected Nodes
				</h4>
				<div class="flex flex-wrap gap-2">
					{#each selectedNodes as node}
						<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
							{node.summary || node.id}
						</span>
					{/each}
				</div>
			</div>

			<!-- Save as Recipe Option -->
			<div class="p-4 bg-[#7661FF]/10 dark:bg-[#7661FF]/15 border border-[#7661FF]/30 dark:border-[#7661FF]/40 rounded-lg">
				<label class="flex items-start gap-3 cursor-pointer">
					<input
						type="checkbox"
						bind:checked={saveAsRecipe}
						class="mt-1 w-4 h-4 text-[#7661FF] border-gray-300 rounded focus:ring-[#52B8FF]"
					/>
					<div class="flex-1">
						<div class="flex items-center gap-2">
							<Library size={16} class="text-[#7661FF]" />
							<span class="font-medium text-gray-800 dark:text-gray-200">Save as Recipe</span>
						</div>
						<p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
							Save this subgraph to your recipe library for reuse in other workflows
						</p>
					</div>
				</label>
			</div>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
			>
				Cancel
			</button>
			<button
				onclick={handleConfirm}
				disabled={!isValid}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors disabled:cursor-not-allowed"
			>
				Create Subgraph
			</button>
		</div>
	</div>
</div>
