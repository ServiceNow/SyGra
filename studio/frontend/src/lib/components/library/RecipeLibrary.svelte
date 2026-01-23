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

<div class="h-full flex flex-col bg-surface-secondary">
	<!-- Header -->
	<div class="px-5 py-4 border-b bg-surface-elevated" style="border-color: var(--border);">
		<div class="flex items-center justify-between mb-4">
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-xl bg-gradient-ai">
					<Library size={18} class="text-white" />
				</div>
				<div>
					<h2 class="text-lg font-semibold" style="color: var(--text-primary);">Recipe Library</h2>
					<p class="text-xs" style="color: var(--text-muted);">Reusable workflow patterns</p>
				</div>
				{#if selectionCount > 0}
					<span class="ml-2 px-2.5 py-1 text-xs font-medium rounded-full bg-info/10 text-info">
						{selectionCount} selected
					</span>
				{/if}
			</div>
			<div class="flex items-center gap-2">
				{#if selectionCount > 0}
					<button
						onclick={clearSelection}
						class="p-2 rounded-xl hover:bg-surface-hover transition-colors"
						style="color: var(--text-muted);"
						title="Clear selection"
					>
						<X size={18} />
					</button>
					<button
						onclick={exportSelectedRecipes}
						class="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface-secondary hover:bg-surface-hover transition-colors text-sm font-medium"
						style="color: var(--text-secondary);"
						title="Export selected"
					>
						<Download size={16} />
						<span>Export</span>
					</button>
					<button
						onclick={requestDeleteSelectedRecipes}
						class="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-error/10 hover:bg-error/15 text-error transition-colors text-sm font-medium"
						title="Delete selected"
					>
						<Trash2 size={16} />
						<span>Delete ({selectionCount})</span>
					</button>
					<div class="w-px h-6 bg-surface-border"></div>
				{/if}
				<button
					onclick={handleImport}
					class="p-2.5 rounded-xl hover:bg-surface-hover transition-colors"
					style="color: var(--text-muted);"
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
					class="flex items-center gap-1.5 px-3 py-2 rounded-xl hover:bg-surface-hover transition-colors text-sm"
					style="color: var(--text-muted);"
					title={allSelected() ? 'Deselect all' : 'Select all'}
				>
					{#if allSelected()}
						<CheckSquare size={16} class="text-info" />
					{:else if someSelected()}
						<MinusSquare size={16} class="text-info" />
					{:else}
						<Square size={16} />
					{/if}
					<span class="text-xs font-medium">All</span>
				</button>
			{/if}

			<!-- Search -->
			<div class="relative flex-1">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2" style="color: var(--text-muted);" />
				<input
					type="text"
					placeholder="Search recipes..."
					bind:value={recipeStore.searchQuery}
					class="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl bg-surface-secondary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-info/50 transition-shadow"
					style="color: var(--text-primary); border: 1px solid var(--border);"
				/>
			</div>
		</div>

		<!-- Category filter -->
		<div class="mt-4">
			<button
				onclick={() => showCategoryFilter = !showCategoryFilter}
				class="flex items-center gap-2 text-sm hover:opacity-80 transition-opacity"
				style="color: var(--text-secondary);"
			>
				<Filter size={14} />
				<span class="font-medium">
					{recipeStore.selectedCategory === 'all'
						? 'All Categories'
						: RECIPE_CATEGORIES.find(c => c.value === recipeStore.selectedCategory)?.label}
				</span>
				<ChevronDown size={14} class="transition-transform {showCategoryFilter ? 'rotate-180' : ''}" />
			</button>

			{#if showCategoryFilter}
				<div class="mt-3 flex flex-wrap gap-2">
					<button
						onclick={() => { recipeStore.selectedCategory = 'all'; showCategoryFilter = false; }}
						class="px-3 py-1.5 text-xs font-medium rounded-xl transition-all {
							recipeStore.selectedCategory === 'all'
								? 'bg-info/15 text-info'
								: 'bg-surface-secondary hover:bg-surface-hover'
						}"
						style={recipeStore.selectedCategory !== 'all' ? 'color: var(--text-secondary);' : ''}
					>
						All
					</button>
					{#each RECIPE_CATEGORIES as cat}
						<button
							onclick={() => { recipeStore.selectedCategory = cat.value; showCategoryFilter = false; }}
							class="px-3 py-1.5 text-xs font-medium rounded-xl transition-all {
								recipeStore.selectedCategory === cat.value
									? 'bg-info/15 text-info'
									: 'bg-surface-secondary hover:bg-surface-hover'
							}"
							style={recipeStore.selectedCategory !== cat.value ? 'color: var(--text-secondary);' : ''}
						>
							{cat.label}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<!-- Recipe list -->
	<div class="flex-1 overflow-y-auto p-4">
		{#if recipeStore.filteredRecipes.length === 0}
			<div class="text-center py-16">
				<div class="w-20 h-20 mx-auto mb-5 rounded-2xl bg-gradient-ai flex items-center justify-center shadow-lg">
					<Library size={32} class="text-white" />
				</div>
				<h3 class="text-xl font-semibold mb-2" style="color: var(--text-primary);">No recipes yet</h3>
				<p class="text-sm max-w-sm mx-auto" style="color: var(--text-muted);">
					{#if recipeStore.searchQuery || recipeStore.selectedCategory !== 'all'}
						No recipes match your search. Try adjusting your filters.
					{:else}
						Create a subgraph in the workflow builder and save it as a recipe to reuse later.
					{/if}
				</p>
			</div>
		{:else}
			<div class="space-y-3">
				{#each recipeStore.filteredRecipes as recipe (recipe.id)}
					{@const Icon = categoryIcons[recipe.category]}
					{@const isSelected = selectedRecipeIds.has(recipe.id)}
					<div
						class="group relative p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer hover:-translate-y-0.5 {
							isSelected
								? 'border-info bg-info/5 shadow-md'
								: 'bg-surface-elevated hover:shadow-card-hover'
						}"
						style={!isSelected ? 'border-color: var(--border);' : ''}
						onclick={() => handleAddRecipe(recipe)}
					>
						<!-- Category indicator -->
						<div
							class="absolute left-0 top-3 bottom-3 w-1 rounded-full"
							style="background-color: {getCategoryColor(recipe.category)}"
						></div>

						<div class="flex items-start gap-3 pl-3">
							<!-- Checkbox (z-10 to be above overlay) -->
							<button
								onclick={(e) => toggleSelectRecipe(recipe.id, e)}
								class="relative z-10 p-1 rounded-lg hover:bg-surface-hover transition-colors flex-shrink-0"
							>
								{#if isSelected}
									<CheckSquare size={18} class="text-info" />
								{:else}
									<Square size={18} class="opacity-40 group-hover:opacity-70" style="color: var(--text-muted);" />
								{/if}
							</button>

							<!-- Icon -->
							<div
								class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
								style="background-color: {getCategoryColor(recipe.category)}15"
							>
								<Icon size={18} style="color: {getCategoryColor(recipe.category)}" />
							</div>

							<!-- Content -->
							<div class="flex-1 min-w-0">
								<div class="flex items-center justify-between">
									<h4 class="font-semibold truncate" style="color: var(--text-primary);">
										{recipe.name}
									</h4>
									<button
										onclick={(e) => { e.stopPropagation(); showContextMenu(e, recipe); }}
										class="relative z-10 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-surface-hover transition-all"
										style="color: var(--text-muted);"
									>
										<MoreVertical size={14} />
									</button>
								</div>

								{#if recipe.description}
									<p class="text-xs mt-1 line-clamp-2" style="color: var(--text-muted);">
										{recipe.description}
									</p>
								{/if}

								<div class="flex items-center gap-4 mt-2.5 text-xs" style="color: var(--text-muted);">
									<span class="flex items-center gap-1.5">
										<Layers size={12} />
										{recipe.nodeCount} nodes
									</span>
									<span class="flex items-center gap-1.5">
										<Clock size={12} />
										{formatDate(recipe.updatedAt)}
									</span>
								</div>

								{#if recipe.tags.length > 0}
									<div class="flex flex-wrap gap-1.5 mt-2.5">
										{#each recipe.tags.slice(0, 3) as tag}
											<span class="px-2 py-0.5 text-[10px] font-medium rounded-lg bg-surface-secondary" style="color: var(--text-muted);">
												{tag}
											</span>
										{/each}
										{#if recipe.tags.length > 3}
											<span class="text-[10px]" style="color: var(--text-muted);">+{recipe.tags.length - 3}</span>
										{/if}
									</div>
								{/if}
							</div>
						</div>

						<!-- Action buttons overlay -->
						<div class="absolute inset-0 flex items-center justify-center gap-3 opacity-0 group-hover:opacity-100 bg-surface-elevated/95 backdrop-blur-sm rounded-xl transition-all duration-200">
							<button
								onclick={(e) => { e.stopPropagation(); previewRecipe = recipe; }}
								class="flex items-center gap-2 px-4 py-2 rounded-xl bg-brand-primary hover:bg-brand-primary/90 text-white text-sm font-medium transition-colors shadow-md"
							>
								<Eye size={15} />
								Preview
							</button>
							<button
								onclick={(e) => { e.stopPropagation(); handleAddRecipe(recipe); }}
								class="btn-accent flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors shadow-md"
							>
								<Plus size={15} />
								Add
							</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Stats footer -->
	<div class="px-5 py-3 border-t bg-surface-elevated" style="border-color: var(--border);">
		<div class="flex items-center justify-between text-xs" style="color: var(--text-muted);">
			<span class="font-medium">{recipeStore.recipes.length} recipes in library</span>
			{#if recipeStore.filteredRecipes.length !== recipeStore.recipes.length}
				<span>{recipeStore.filteredRecipes.length} shown</span>
			{/if}
		</div>
	</div>
</div>

<!-- Context menu -->
{#if contextMenuRecipe}
	<div
		class="fixed z-50 min-w-[180px] py-2 bg-surface-elevated rounded-xl shadow-dropdown border animate-scale-in"
		style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px; border-color: var(--border);"
		onclick={(e) => e.stopPropagation()}
	>
		<button
			onclick={() => { previewRecipe = contextMenuRecipe; hideContextMenu(); }}
			class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors hover:bg-surface-hover"
			style="color: var(--text-secondary);"
		>
			<Eye size={15} />
			View Graph
		</button>
		<button
			onclick={handleDuplicate}
			class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors hover:bg-surface-hover"
			style="color: var(--text-secondary);"
		>
			<Copy size={15} />
			Duplicate
		</button>
		<button
			onclick={handleExport}
			class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors hover:bg-surface-hover"
			style="color: var(--text-secondary);"
		>
			<Download size={15} />
			Export
		</button>
		<div class="my-2 mx-3 border-t" style="border-color: var(--border);"></div>
		<button
			onclick={handleDelete}
			class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-error transition-colors hover:bg-error/10"
		>
			<Trash2 size={15} />
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
