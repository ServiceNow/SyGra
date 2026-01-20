<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { recipeStore, RECIPE_CATEGORIES, type RecipeCategory, type RecipeInput } from '$lib/stores/recipe.svelte';
	import type { WorkflowNode, WorkflowEdge } from '$lib/stores/workflow.svelte';
	import { X, Save, Tag, FolderOpen, FileText, Brain, Database, Shuffle, Bot, Wrench, Puzzle } from 'lucide-svelte';

	interface Props {
		nodes: WorkflowNode[];
		edges: WorkflowEdge[];
		suggestedName?: string;
	}

	let { nodes, edges, suggestedName = '' }: Props = $props();

	const dispatch = createEventDispatcher<{
		close: void;
		saved: { recipeId: string };
	}>();

	// Form state
	let name = $state(suggestedName || 'My Recipe');
	let description = $state('');
	let category = $state<RecipeCategory>('custom');
	let tagsInput = $state('');
	let author = $state('');
	let isSaving = $state(false);
	let error = $state('');

	// Derived tags array
	let tags = $derived(() => {
		return tagsInput.split(',').map(t => t.trim()).filter(t => t.length > 0);
	});

	// Node type summary
	let nodeTypeSummary = $derived(() => {
		const types = new Map<string, number>();
		nodes.forEach(n => {
			types.set(n.node_type, (types.get(n.node_type) || 0) + 1);
		});
		return Array.from(types.entries()).map(([type, count]) => `${count} ${type}`).join(', ');
	});

	// Category icon mapping
	const categoryIcons: Record<RecipeCategory, typeof Brain> = {
		llm: Brain,
		data: Database,
		transform: Shuffle,
		agent: Bot,
		utility: Wrench,
		custom: Puzzle
	};

	async function handleSave() {
		if (!name.trim()) {
			error = 'Please enter a recipe name';
			return;
		}

		if (nodes.length === 0) {
			error = 'Cannot save an empty recipe';
			return;
		}

		isSaving = true;
		error = '';

		try {
			const input: RecipeInput = {
				name: name.trim(),
				description: description.trim(),
				category,
				tags: tags(),
				nodes,
				edges,
				author: author.trim() || undefined
			};

			const recipe = recipeStore.addRecipe(input);
			dispatch('saved', { recipeId: recipe.id });
			dispatch('close');
		} catch (e) {
			error = 'Failed to save recipe. Please try again.';
			console.error('Save recipe error:', e);
		} finally {
			isSaving = false;
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dispatch('close');
		} else if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
			handleSave();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('close')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-lg mx-4 flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-[#7661FF] to-[#BF71F2] flex items-center justify-center">
					<Save size={20} class="text-white" />
				</div>
				<div>
					<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
						Save as Recipe
					</h3>
					<p class="text-sm text-gray-500 dark:text-gray-400">
						Save this subgraph for reuse in other workflows
					</p>
				</div>
			</div>
			<button
				onclick={() => dispatch('close')}
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Content -->
		<div class="p-6 space-y-5">
			<!-- Preview stats -->
			<div class="flex items-center gap-4 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
				<div class="flex items-center gap-2 text-sm">
					<span class="text-gray-500 dark:text-gray-400">Nodes:</span>
					<span class="font-medium text-gray-800 dark:text-gray-200">{nodes.length}</span>
				</div>
				<div class="w-px h-4 bg-gray-300 dark:bg-gray-600"></div>
				<div class="flex items-center gap-2 text-sm">
					<span class="text-gray-500 dark:text-gray-400">Edges:</span>
					<span class="font-medium text-gray-800 dark:text-gray-200">{edges.length}</span>
				</div>
				{#if nodeTypeSummary()}
					<div class="w-px h-4 bg-gray-300 dark:bg-gray-600"></div>
					<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
						{nodeTypeSummary()}
					</div>
				{/if}
			</div>

			<!-- Name input -->
			<div class="space-y-1.5">
				<label for="recipe-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
					Name <span class="text-red-500">*</span>
				</label>
				<input
					id="recipe-name"
					type="text"
					bind:value={name}
					placeholder="Enter recipe name..."
					class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				/>
			</div>

			<!-- Description input -->
			<div class="space-y-1.5">
				<label for="recipe-description" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
					Description
				</label>
				<textarea
					id="recipe-description"
					bind:value={description}
					placeholder="Describe what this recipe does..."
					rows="3"
					class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent resize-none"
				></textarea>
			</div>

			<!-- Category selection -->
			<div class="space-y-1.5">
				<label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
					Category
				</label>
				<div class="grid grid-cols-3 gap-2">
					{#each RECIPE_CATEGORIES as cat}
						{@const Icon = categoryIcons[cat.value]}
						<button
							type="button"
							onclick={() => category = cat.value}
							class="flex items-center gap-2 px-3 py-2 rounded-lg border-2 transition-all {
								category === cat.value
									? 'border-[#7661FF] bg-[#7661FF]/10 dark:bg-[#7661FF]/15'
									: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
							}"
						>
							<Icon size={16} style="color: {cat.color}" />
							<span class="text-sm text-gray-700 dark:text-gray-300 truncate">{cat.label}</span>
						</button>
					{/each}
				</div>
			</div>

			<!-- Tags input -->
			<div class="space-y-1.5">
				<label for="recipe-tags" class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
					<Tag size={14} />
					Tags
				</label>
				<input
					id="recipe-tags"
					type="text"
					bind:value={tagsInput}
					placeholder="Enter tags separated by commas..."
					class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				/>
				{#if tags().length > 0}
					<div class="flex flex-wrap gap-1.5 mt-2">
						{#each tags() as tag}
							<span class="px-2 py-0.5 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
								{tag}
							</span>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Author input (optional) -->
			<div class="space-y-1.5">
				<label for="recipe-author" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
					Author <span class="text-gray-400">(optional)</span>
				</label>
				<input
					id="recipe-author"
					type="text"
					bind:value={author}
					placeholder="Your name..."
					class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				/>
			</div>

			<!-- Error message -->
			{#if error}
				<div class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
					<p class="text-sm text-red-600 dark:text-red-400">{error}</p>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 rounded-b-xl">
			<button
				onclick={() => dispatch('close')}
				class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
			>
				Cancel
			</button>
			<button
				onclick={handleSave}
				disabled={isSaving}
				class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#032D42] bg-[#63DF4E] hover:bg-[#63DF4E]/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
			>
				{#if isSaving}
					<span class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
				{:else}
					<Save size={16} />
				{/if}
				Save Recipe
			</button>
		</div>
	</div>
</div>
