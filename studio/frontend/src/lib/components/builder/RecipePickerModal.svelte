<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { recipeStore, RECIPE_CATEGORIES, type Recipe, type RecipeCategory } from '$lib/stores/recipe.svelte';
	import {
		X, Search, Plus, Library, Brain, Database, Shuffle, Bot, Wrench, Puzzle,
		Layers, Clock, Boxes
	} from 'lucide-svelte';

	interface Props {
		position: { x: number; y: number };
	}

	let { position }: Props = $props();

	const dispatch = createEventDispatcher<{
		select: { recipe: Recipe | null; position: { x: number; y: number } };
		cancel: void;
	}>();

	let searchQuery = $state('');

	// Category icon mapping
	const categoryIcons: Record<RecipeCategory, typeof Brain> = {
		llm: Brain,
		data: Database,
		transform: Shuffle,
		agent: Bot,
		utility: Wrench,
		custom: Puzzle
	};

	// Get category color
	function getCategoryColor(category: RecipeCategory): string {
		return RECIPE_CATEGORIES.find(c => c.value === category)?.color || '#6b7280';
	}

	// Filter recipes by search
	let filteredRecipes = $derived(() => {
		if (!searchQuery.trim()) return recipeStore.recipes;
		const query = searchQuery.toLowerCase();
		return recipeStore.recipes.filter(r =>
			r.name.toLowerCase().includes(query) ||
			r.description.toLowerCase().includes(query) ||
			r.tags.some(t => t.toLowerCase().includes(query))
		);
	});

	function handleSelectRecipe(recipe: Recipe) {
		dispatch('select', { recipe, position });
	}

	function handleCreateEmpty() {
		dispatch('select', { recipe: null, position });
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('cancel');
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('cancel')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md mx-4 max-h-[70vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
					<Boxes size={18} class="text-blue-500" />
				</div>
				<div>
					<h3 class="text-base font-semibold text-gray-800 dark:text-gray-200">
						Add Subgraph
					</h3>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						Create from recipe or start empty
					</p>
				</div>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
			>
				<X size={18} />
			</button>
		</div>

		<!-- Create Empty Option -->
		<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
			<button
				onclick={handleCreateEmpty}
				class="w-full flex items-center gap-3 p-3 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all"
			>
				<div class="w-8 h-8 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
					<Plus size={16} class="text-gray-500" />
				</div>
				<div class="text-left">
					<div class="text-sm font-medium text-gray-800 dark:text-gray-200">
						Create Empty Subgraph
					</div>
					<div class="text-xs text-gray-500 dark:text-gray-400">
						Start with a blank subgraph
					</div>
				</div>
			</button>
		</div>

		<!-- Recipe Search -->
		{#if recipeStore.recipes.length > 0}
			<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
				<div class="relative">
					<Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
					<input
						type="text"
						placeholder="Search recipes..."
						bind:value={searchQuery}
						class="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
					/>
				</div>
			</div>

			<!-- Recipe List -->
			<div class="flex-1 overflow-y-auto p-3">
				{#if filteredRecipes().length === 0}
					<div class="text-center py-8 text-gray-500 dark:text-gray-400">
						<p class="text-sm">No recipes match your search</p>
					</div>
				{:else}
					<div class="space-y-2">
						{#each filteredRecipes() as recipe (recipe.id)}
							{@const Icon = categoryIcons[recipe.category]}
							<button
								onclick={() => handleSelectRecipe(recipe)}
								class="w-full flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all text-left"
							>
								<div
									class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
									style="background-color: {getCategoryColor(recipe.category)}20"
								>
									<Icon size={14} style="color: {getCategoryColor(recipe.category)}" />
								</div>
								<div class="flex-1 min-w-0">
									<div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
										{recipe.name}
									</div>
									{#if recipe.description}
										<div class="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
											{recipe.description}
										</div>
									{/if}
									<div class="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
										<span class="flex items-center gap-1">
											<Layers size={10} />
											{recipe.nodeCount} nodes
										</span>
									</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>
		{:else}
			<!-- No recipes message -->
			<div class="flex-1 flex items-center justify-center p-6">
				<div class="text-center">
					<Library size={32} class="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
					<p class="text-sm text-gray-500 dark:text-gray-400">
						No recipes in library yet
					</p>
					<p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
						Save subgraphs as recipes to reuse them
					</p>
				</div>
			</div>
		{/if}
	</div>
</div>
