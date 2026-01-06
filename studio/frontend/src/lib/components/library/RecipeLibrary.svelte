<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { recipeStore, RECIPE_CATEGORIES, type Recipe, type RecipeCategory } from '$lib/stores/recipe.svelte';
	import {
		Search, Filter, MoreVertical, Trash2, Copy, Download, Upload,
		Brain, Database, Shuffle, Bot, Wrench, Puzzle, Plus, Library,
		ChevronDown, Clock, Layers, Eye, CheckSquare, Square, MinusSquare, X
	} from 'lucide-svelte';
	import RecipePreviewModal from './RecipePreviewModal.svelte';
	import ConfirmationModal from '../common/ConfirmationModal.svelte';

	const dispatch = createEventDispatcher<{
		addRecipe: { recipe: Recipe };
		close: void;
	}>();

	// Local state
	let showCategoryFilter = $state(false);
	let contextMenuRecipe = $state<Recipe | null>(null);
	let contextMenuPosition = $state({ x: 0, y: 0 });
	let importInput: HTMLInputElement;
	let previewRecipe = $state<Recipe | null>(null);

	// Selection state
	let selectedRecipeIds = $state<Set<string>>(new Set());

	// Confirmation modal state
	let showDeleteConfirm = $state(false);
	let deleteCount = $state(0);

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

	// Handle adding recipe to workflow
	function handleAddRecipe(recipe: Recipe) {
		dispatch('addRecipe', { recipe });
	}

	// Context menu actions
	function showContextMenu(e: MouseEvent, recipe: Recipe) {
		e.preventDefault();
		e.stopPropagation();
		contextMenuRecipe = recipe;
		contextMenuPosition = { x: e.clientX, y: e.clientY };
	}

	function hideContextMenu() {
		contextMenuRecipe = null;
	}

	function handleDuplicate() {
		if (contextMenuRecipe) {
			recipeStore.duplicateRecipe(contextMenuRecipe.id);
		}
		hideContextMenu();
	}

	function handleDelete() {
		if (contextMenuRecipe && confirm(`Delete "${contextMenuRecipe.name}"? This cannot be undone.`)) {
			recipeStore.deleteRecipe(contextMenuRecipe.id);
		}
		hideContextMenu();
	}

	function handleExport() {
		if (contextMenuRecipe) {
			const json = recipeStore.exportRecipe(contextMenuRecipe.id);
			if (json) {
				const blob = new Blob([json], { type: 'application/json' });
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = `${contextMenuRecipe.name.toLowerCase().replace(/\s+/g, '_')}.recipe.json`;
				a.click();
				URL.revokeObjectURL(url);
			}
		}
		hideContextMenu();
	}

	function handleImport() {
		importInput?.click();
	}

	function onFileImport(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (file) {
			const reader = new FileReader();
			reader.onload = () => {
				const result = recipeStore.importRecipe(reader.result as string);
				if (result) {
					console.log('Recipe imported:', result.name);
				} else {
					alert('Failed to import recipe. Please check the file format.');
				}
			};
			reader.readAsText(file);
		}
		input.value = '';
	}

	// Format date
	function formatDate(dateStr: string): string {
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

		if (diffDays === 0) return 'Today';
		if (diffDays === 1) return 'Yesterday';
		if (diffDays < 7) return `${diffDays} days ago`;
		return date.toLocaleDateString();
	}

	// Selection helpers
	let allSelected = $derived(() => {
		const recipes = recipeStore.filteredRecipes;
		return recipes.length > 0 && recipes.every(r => selectedRecipeIds.has(r.id));
	});

	let someSelected = $derived(() => {
		const recipes = recipeStore.filteredRecipes;
		return recipes.some(r => selectedRecipeIds.has(r.id)) && !allSelected();
	});

	let selectionCount = $derived(selectedRecipeIds.size);

	function toggleSelectAll() {
		const recipes = recipeStore.filteredRecipes;
		if (allSelected()) {
			selectedRecipeIds = new Set();
		} else {
			selectedRecipeIds = new Set(recipes.map(r => r.id));
		}
	}

	function toggleSelectRecipe(recipeId: string, e: Event) {
		e.stopPropagation();
		const newSet = new Set(selectedRecipeIds);
		if (newSet.has(recipeId)) {
			newSet.delete(recipeId);
		} else {
			newSet.add(recipeId);
		}
		selectedRecipeIds = newSet;
	}

	function clearSelection() {
		selectedRecipeIds = new Set();
	}

	function requestDeleteSelectedRecipes() {
		if (selectedRecipeIds.size === 0) return;
		deleteCount = selectedRecipeIds.size;
		showDeleteConfirm = true;
	}

	function confirmDeleteRecipes() {
		selectedRecipeIds.forEach(id => {
			recipeStore.deleteRecipe(id);
		});
		selectedRecipeIds = new Set();
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	function cancelDeleteRecipes() {
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	function exportSelectedRecipes() {
		if (selectedRecipeIds.size === 0) return;
		const recipes = recipeStore.recipes.filter(r => selectedRecipeIds.has(r.id));
		const exportData = JSON.stringify(recipes, null, 2);
		const blob = new Blob([exportData], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `recipes_export_${new Date().toISOString().split('T')[0]}.json`;
		a.click();
		URL.revokeObjectURL(url);
	}
</script>

<svelte:window onclick={hideContextMenu} />

<div class="h-full flex flex-col">
	<!-- Header -->
	<div class="p-4 border-b border-gray-200 dark:border-gray-700">
		<div class="flex items-center justify-between mb-3">
			<div class="flex items-center gap-2">
				<Library size={20} class="text-[#7661FF]" />
				<h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">Recipe Library</h2>
				{#if selectionCount > 0}
					<span class="ml-2 px-2 py-0.5 text-xs rounded-full bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#BF71F2]">
						{selectionCount} selected
					</span>
				{/if}
			</div>
			<div class="flex items-center gap-2">
				{#if selectionCount > 0}
					<button
						onclick={clearSelection}
						class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
						title="Clear selection"
					>
						<X size={18} />
					</button>
					<button
						onclick={exportSelectedRecipes}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors text-sm font-medium"
						title="Export selected"
					>
						<Download size={16} />
						<span>Export</span>
					</button>
					<button
						onclick={requestDeleteSelectedRecipes}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 transition-colors text-sm font-medium"
						title="Delete selected"
					>
						<Trash2 size={16} />
						<span>Delete ({selectionCount})</span>
					</button>
					<div class="w-px h-6 bg-gray-300 dark:bg-gray-600"></div>
				{/if}
				<button
					onclick={handleImport}
					class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 transition-colors"
					title="Import recipe"
				>
					<Upload size={18} />
				</button>
				<input
					bind:this={importInput}
					type="file"
					accept=".json"
					class="hidden"
					onchange={onFileImport}
				/>
			</div>
		</div>

		<!-- Select All and Search Row -->
		<div class="flex items-center gap-3">
			<!-- Select All -->
			{#if recipeStore.filteredRecipes.length > 0}
				<button
					onclick={toggleSelectAll}
					class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors text-sm"
					title={allSelected() ? 'Deselect all' : 'Select all'}
				>
					{#if allSelected()}
						<CheckSquare size={16} class="text-[#7661FF]" />
					{:else if someSelected()}
						<MinusSquare size={16} class="text-[#7661FF]" />
					{:else}
						<Square size={16} />
					{/if}
					<span class="text-xs">All</span>
				</button>
			{/if}

			<!-- Search -->
			<div class="relative flex-1">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
				<input
					type="text"
					placeholder="Search recipes..."
					bind:value={recipeStore.searchQuery}
					class="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				/>
			</div>
		</div>

		<!-- Category filter -->
		<div class="mt-3">
			<button
				onclick={() => showCategoryFilter = !showCategoryFilter}
				class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
			>
				<Filter size={14} />
				<span>
					{recipeStore.selectedCategory === 'all'
						? 'All Categories'
						: RECIPE_CATEGORIES.find(c => c.value === recipeStore.selectedCategory)?.label}
				</span>
				<ChevronDown size={14} class="transition-transform {showCategoryFilter ? 'rotate-180' : ''}" />
			</button>

			{#if showCategoryFilter}
				<div class="mt-2 flex flex-wrap gap-1.5">
					<button
						onclick={() => { recipeStore.selectedCategory = 'all'; showCategoryFilter = false; }}
						class="px-2 py-1 text-xs rounded-full transition-colors {
							recipeStore.selectedCategory === 'all'
								? 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]'
								: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
						}"
					>
						All
					</button>
					{#each RECIPE_CATEGORIES as cat}
						<button
							onclick={() => { recipeStore.selectedCategory = cat.value; showCategoryFilter = false; }}
							class="px-2 py-1 text-xs rounded-full transition-colors {
								recipeStore.selectedCategory === cat.value
									? 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]'
									: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
							}"
						>
							{cat.label}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<!-- Recipe list -->
	<div class="flex-1 overflow-y-auto p-3">
		{#if recipeStore.filteredRecipes.length === 0}
			<div class="text-center py-12">
				<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#7661FF]/20 to-[#BF71F2]/20 flex items-center justify-center">
					<Library size={28} class="text-[#7661FF]" />
				</div>
				<h3 class="text-lg font-medium text-gray-800 dark:text-gray-200 mb-2">No recipes yet</h3>
				<p class="text-sm text-gray-500 dark:text-gray-400 max-w-xs mx-auto">
					{#if recipeStore.searchQuery || recipeStore.selectedCategory !== 'all'}
						No recipes match your search. Try adjusting your filters.
					{:else}
						Create a subgraph in the workflow builder and save it as a recipe to reuse later.
					{/if}
				</p>
			</div>
		{:else}
			<div class="space-y-2">
				{#each recipeStore.filteredRecipes as recipe (recipe.id)}
					{@const Icon = categoryIcons[recipe.category]}
					{@const isSelected = selectedRecipeIds.has(recipe.id)}
					<div
						class="group relative p-3 rounded-lg border transition-all cursor-pointer {
							isSelected
								? 'border-[#7661FF] dark:border-[#BF71F2] bg-[#7661FF]/10 dark:bg-[#7661FF]/20'
								: 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-[#52B8FF] dark:hover:border-[#7661FF] hover:shadow-md'
						}"
						onclick={() => handleAddRecipe(recipe)}
					>
						<!-- Category indicator -->
						<div
							class="absolute left-0 top-0 bottom-0 w-1 rounded-l-lg"
							style="background-color: {getCategoryColor(recipe.category)}"
						></div>

						<div class="flex items-start gap-3 pl-2">
							<!-- Checkbox (z-10 to be above overlay) -->
							<button
								onclick={(e) => toggleSelectRecipe(recipe.id, e)}
								class="relative z-10 p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex-shrink-0 mt-0.5"
							>
								{#if isSelected}
									<CheckSquare size={18} class="text-[#7661FF]" />
								{:else}
									<Square size={18} class="text-gray-400 group-hover:text-gray-500" />
								{/if}
							</button>

							<!-- Icon -->
							<div
								class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
								style="background-color: {getCategoryColor(recipe.category)}20"
							>
								<Icon size={16} style="color: {getCategoryColor(recipe.category)}" />
							</div>

							<!-- Content -->
							<div class="flex-1 min-w-0">
								<div class="flex items-center justify-between">
									<h4 class="font-medium text-gray-800 dark:text-gray-200 truncate">
										{recipe.name}
									</h4>
									<button
										onclick={(e) => { e.stopPropagation(); showContextMenu(e, recipe); }}
										class="relative z-10 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 transition-all"
									>
										<MoreVertical size={14} />
									</button>
								</div>

								{#if recipe.description}
									<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
										{recipe.description}
									</p>
								{/if}

								<div class="flex items-center gap-3 mt-2 text-xs text-gray-400">
									<span class="flex items-center gap-1">
										<Layers size={12} />
										{recipe.nodeCount} nodes
									</span>
									<span class="flex items-center gap-1">
										<Clock size={12} />
										{formatDate(recipe.updatedAt)}
									</span>
								</div>

								{#if recipe.tags.length > 0}
									<div class="flex flex-wrap gap-1 mt-2">
										{#each recipe.tags.slice(0, 3) as tag}
											<span class="px-1.5 py-0.5 text-[10px] rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
												{tag}
											</span>
										{/each}
										{#if recipe.tags.length > 3}
											<span class="text-[10px] text-gray-400">+{recipe.tags.length - 3}</span>
										{/if}
									</div>
								{/if}
							</div>
						</div>

						<!-- Action buttons overlay -->
						<div class="absolute inset-0 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 bg-white/90 dark:bg-gray-800/90 rounded-lg transition-opacity">
							<button
								onclick={(e) => { e.stopPropagation(); previewRecipe = recipe; }}
								class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-600 hover:bg-gray-700 text-white text-sm font-medium transition-colors"
							>
								<Eye size={14} />
								Preview
							</button>
							<button
								onclick={(e) => { e.stopPropagation(); handleAddRecipe(recipe); }}
								class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#63DF4E] hover:bg-[#63DF4E]/90 text-[#032D42] text-sm font-medium transition-colors"
							>
								<Plus size={14} />
								Add
							</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Stats footer -->
	<div class="p-3 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
		<div class="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
			<span>{recipeStore.recipes.length} recipes in library</span>
			{#if recipeStore.filteredRecipes.length !== recipeStore.recipes.length}
				<span>{recipeStore.filteredRecipes.length} shown</span>
			{/if}
		</div>
	</div>
</div>

<!-- Context menu -->
{#if contextMenuRecipe}
	<div
		class="fixed z-50 min-w-[160px] py-1 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700"
		style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px;"
		onclick={(e) => e.stopPropagation()}
	>
		<button
			onclick={() => { previewRecipe = contextMenuRecipe; hideContextMenu(); }}
			class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
		>
			<Eye size={14} />
			View Graph
		</button>
		<button
			onclick={handleDuplicate}
			class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
		>
			<Copy size={14} />
			Duplicate
		</button>
		<button
			onclick={handleExport}
			class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
		>
			<Download size={14} />
			Export
		</button>
		<div class="my-1 border-t border-gray-200 dark:border-gray-700"></div>
		<button
			onclick={handleDelete}
			class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
		>
			<Trash2 size={14} />
			Delete
		</button>
	</div>
{/if}

<!-- Recipe Preview Modal -->
{#if previewRecipe}
	<RecipePreviewModal
		recipe={previewRecipe}
		on:close={() => previewRecipe = null}
		on:addToWorkflow={(e) => {
			handleAddRecipe(e.detail.recipe);
			previewRecipe = null;
		}}
	/>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmationModal
		title="Delete {deleteCount} Recipe{deleteCount > 1 ? 's' : ''}"
		message="Are you sure you want to delete {deleteCount} selected recipe{deleteCount > 1 ? 's' : ''}? This action cannot be undone."
		confirmText="Delete"
		cancelText="Cancel"
		variant="danger"
		icon="trash"
		on:confirm={confirmDeleteRecipes}
		on:cancel={cancelDeleteRecipes}
	/>
{/if}
