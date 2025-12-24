<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import {
		Search, Plus, Boxes, Wrench, RefreshCw, X, Upload, Download,
		LayoutList, LayoutGrid, MoreVertical, Trash2, Copy, Edit3,
		Brain, Database, Shuffle, Bot, Puzzle, Globe, Layers, Clock,
		CheckSquare, Square, MinusSquare, Code, Eye
	} from 'lucide-svelte';
	import { recipeStore, RECIPE_CATEGORIES, type Recipe, type RecipeCategory } from '$lib/stores/recipe.svelte';
	import { toolStore, TOOL_CATEGORIES, DEFAULT_TOOL_CODE, type Tool, type ToolCategory } from '$lib/stores/tool.svelte';
	import MonacoEditor from '$lib/components/editor/MonacoEditor.svelte';
	import ConfirmationModal from '$lib/components/common/ConfirmationModal.svelte';
	import RecipePreviewModal from './RecipePreviewModal.svelte';

	const dispatch = createEventDispatcher<{
		addRecipe: { recipe: Recipe };
	}>();

	// Tab state
	let activeTab = $state<'recipes' | 'tools'>('recipes');

	// View mode
	let viewMode = $state<'card' | 'list'>('card');

	// Search state
	let searchQuery = $state('');

	// Category filter
	let selectedRecipeCategory = $state<RecipeCategory | 'all'>('all');
	let selectedToolCategory = $state<ToolCategory | 'all'>('all');

	// Selection state
	let selectedIds = $state<Set<string>>(new Set());

	// Context menu state
	let contextMenuId = $state<string | null>(null);
	let contextMenuPosition = $state({ x: 0, y: 0 });

	// Modals
	let showDeleteConfirm = $state(false);
	let deleteCount = $state(0);
	let showToolEditor = $state(false);
	let editingTool = $state<Tool | null>(null);
	let previewRecipe = $state<Recipe | null>(null);

	// Tool form state
	let toolFormName = $state('');
	let toolFormDescription = $state('');
	let toolFormCategory = $state<ToolCategory>('custom');
	let toolFormCode = $state(DEFAULT_TOOL_CODE);
	let toolFormImportPath = $state('');

	// Import input ref
	let importInput: HTMLInputElement;

	// Persist view mode
	onMount(() => {
		const saved = localStorage.getItem('library-view-mode');
		if (saved === 'list' || saved === 'card') viewMode = saved;
	});

	function setViewMode(mode: 'list' | 'card') {
		viewMode = mode;
		localStorage.setItem('library-view-mode', mode);
	}

	// Category icons
	const recipeCategoryIcons: Record<RecipeCategory, typeof Brain> = {
		llm: Brain, data: Database, transform: Shuffle, agent: Bot, utility: Wrench, custom: Puzzle
	};
	const toolCategoryIcons: Record<ToolCategory, typeof Wrench> = {
		search: Search, data: Database, api: Globe, utility: Wrench, custom: Puzzle
	};

	function getCategoryColor(category: string, type: 'recipe' | 'tool'): string {
		const cats = type === 'recipe' ? RECIPE_CATEGORIES : TOOL_CATEGORIES;
		return cats.find(c => c.value === category)?.color || '#6b7280';
	}

	// Filtered items
	let filteredRecipes = $derived(() => {
		let result = [...recipeStore.recipes];
		if (selectedRecipeCategory !== 'all') {
			result = result.filter(r => r.category === selectedRecipeCategory);
		}
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(r =>
				r.name.toLowerCase().includes(q) ||
				r.description.toLowerCase().includes(q) ||
				r.tags.some(t => t.toLowerCase().includes(q))
			);
		}
		return result;
	});

	let filteredTools = $derived(() => {
		let result = [...toolStore.tools];
		if (selectedToolCategory !== 'all') {
			result = result.filter(t => t.category === selectedToolCategory);
		}
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(t =>
				t.name.toLowerCase().includes(q) ||
				t.description.toLowerCase().includes(q) ||
				t.import_path.toLowerCase().includes(q)
			);
		}
		return result;
	});

	let currentItems = $derived(activeTab === 'recipes' ? filteredRecipes() : filteredTools());
	let totalCount = $derived(activeTab === 'recipes' ? recipeStore.recipes.length : toolStore.tools.length);

	let hasActiveFilters = $derived(
		searchQuery !== '' ||
		(activeTab === 'recipes' && selectedRecipeCategory !== 'all') ||
		(activeTab === 'tools' && selectedToolCategory !== 'all')
	);

	function clearFilters() {
		searchQuery = '';
		selectedRecipeCategory = 'all';
		selectedToolCategory = 'all';
	}

	// Selection
	let selectionCount = $derived(selectedIds.size);
	let allSelected = $derived(() => currentItems.length > 0 && currentItems.every(i => selectedIds.has(i.id)));
	let someSelected = $derived(() => currentItems.some(i => selectedIds.has(i.id)) && !allSelected());

	function toggleSelectAll() {
		if (allSelected()) {
			selectedIds = new Set();
		} else {
			selectedIds = new Set(currentItems.map(i => i.id));
		}
	}

	function toggleSelect(id: string, e: Event) {
		e.stopPropagation();
		const newSet = new Set(selectedIds);
		if (newSet.has(id)) newSet.delete(id);
		else newSet.add(id);
		selectedIds = newSet;
	}

	function clearSelection() {
		selectedIds = new Set();
	}

	// Context menu
	function showContextMenu(e: MouseEvent, id: string) {
		e.preventDefault();
		e.stopPropagation();
		contextMenuId = id;
		contextMenuPosition = { x: e.clientX, y: e.clientY };
	}

	function hideContextMenu() {
		contextMenuId = null;
	}

	// Actions
	function handleCreate() {
		if (activeTab === 'tools') {
			toolFormName = '';
			toolFormDescription = '';
			toolFormCategory = 'custom';
			toolFormCode = DEFAULT_TOOL_CODE;
			toolFormImportPath = '';
			editingTool = null;
			showToolEditor = true;
		}
	}

	function handleEdit(id: string) {
		hideContextMenu();
		if (activeTab === 'tools') {
			const tool = toolStore.getTool(id);
			if (tool) {
				toolFormName = tool.name;
				toolFormDescription = tool.description;
				toolFormCategory = tool.category;
				toolFormCode = tool.code;
				toolFormImportPath = tool.import_path;
				editingTool = tool;
				showToolEditor = true;
			}
		}
	}

	function handleDuplicate(id: string) {
		hideContextMenu();
		if (activeTab === 'recipes') recipeStore.duplicateRecipe(id);
		else toolStore.duplicateTool(id);
	}

	function handleExport(id: string) {
		hideContextMenu();
		const json = activeTab === 'recipes' ? recipeStore.exportRecipe(id) : toolStore.exportTool(id);
		const item = activeTab === 'recipes' ? recipeStore.getRecipe(id) : toolStore.getTool(id);
		if (json && item) {
			const blob = new Blob([json], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${item.name.toLowerCase().replace(/\s+/g, '_')}.${activeTab === 'recipes' ? 'recipe' : 'tool'}.json`;
			a.click();
			URL.revokeObjectURL(url);
		}
	}

	function requestDelete(id?: string) {
		hideContextMenu();
		if (id) {
			selectedIds = new Set([id]);
		}
		deleteCount = selectedIds.size;
		showDeleteConfirm = true;
	}

	function confirmDelete() {
		selectedIds.forEach(id => {
			if (activeTab === 'recipes') recipeStore.deleteRecipe(id);
			else toolStore.deleteTool(id);
		});
		selectedIds = new Set();
		showDeleteConfirm = false;
		deleteCount = 0;
	}

	function cancelDelete() {
		showDeleteConfirm = false;
		deleteCount = 0;
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
				const result = activeTab === 'recipes'
					? recipeStore.importRecipe(reader.result as string)
					: toolStore.importTool(reader.result as string);
				if (!result) alert('Failed to import. Please check the file format.');
			};
			reader.readAsText(file);
		}
		input.value = '';
	}

	function saveTool() {
		if (!toolFormName.trim() || !toolFormImportPath.trim()) return;
		if (editingTool) {
			toolStore.updateTool(editingTool.id, {
				name: toolFormName,
				description: toolFormDescription,
				category: toolFormCategory,
				code: toolFormCode,
				import_path: toolFormImportPath
			});
		} else {
			toolStore.addTool({
				name: toolFormName,
				description: toolFormDescription,
				category: toolFormCategory,
				code: toolFormCode,
				import_path: toolFormImportPath
			});
		}
		showToolEditor = false;
		editingTool = null;
	}

	function handleAddRecipe(recipe: Recipe) {
		console.log('[LibraryView] handleAddRecipe called:', recipe.name, 'nodes:', recipe.nodes?.length);
		dispatch('addRecipe', { recipe });
	}

	function formatDate(dateStr: string): string {
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
		if (diffDays === 0) return 'Today';
		if (diffDays === 1) return 'Yesterday';
		if (diffDays < 7) return `${diffDays}d ago`;
		return date.toLocaleDateString();
	}

	// Auto-generate import path
	$effect(() => {
		if (!editingTool && toolFormName && !toolFormImportPath) {
			toolFormImportPath = `tools.${toolFormName.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')}`;
		}
	});
</script>

<svelte:window onclick={hideContextMenu} />

<input type="file" accept=".json" bind:this={importInput} onchange={onFileImport} class="hidden" />

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Library</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{currentItems.length} of {totalCount} {activeTab}
					{#if selectionCount > 0}
						<span class="ml-2 text-violet-600 dark:text-violet-400">• {selectionCount} selected</span>
					{/if}
				</p>
			</div>
			<div class="flex items-center gap-2">
				<!-- Tab Toggle -->
				<div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
					<button
						onclick={() => { activeTab = 'recipes'; selectedIds = new Set(); }}
						class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 {activeTab === 'recipes' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'}"
					>
						<Boxes size={16} />
						Recipes
						{#if recipeStore.recipes.length > 0}
							<span class="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-gray-600">{recipeStore.recipes.length}</span>
						{/if}
					</button>
					<button
						onclick={() => { activeTab = 'tools'; selectedIds = new Set(); }}
						class="px-3 py-1.5 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 {activeTab === 'tools' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'}"
					>
						<Wrench size={16} />
						Tools
						{#if toolStore.tools.length > 0}
							<span class="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 dark:bg-gray-600">{toolStore.tools.length}</span>
						{/if}
					</button>
				</div>

				<div class="w-px h-6 bg-gray-200 dark:bg-gray-700"></div>

				{#if selectionCount > 0}
					<button onclick={clearSelection} class="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500" title="Clear selection">
						<X size={18} />
					</button>
					<button onclick={() => requestDelete()} class="flex items-center gap-2 px-3 py-2 rounded-lg bg-red-50 dark:bg-red-900/20 hover:bg-red-100 text-red-600 text-sm font-medium">
						<Trash2 size={16} />
						Delete ({selectionCount})
					</button>
					<div class="w-px h-6 bg-gray-200 dark:bg-gray-700"></div>
				{/if}

				<button onclick={handleImport} class="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors text-sm">
					<Upload size={16} />
					Import
				</button>
				{#if activeTab === 'tools'}
					<button onclick={handleCreate} class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors text-sm">
						<Plus size={16} />
						Create Tool
					</button>
				{/if}
			</div>
		</div>

		<!-- Filters Row -->
		<div class="flex items-center justify-between gap-4">
			<div class="flex flex-wrap items-center gap-3">
				<!-- Search -->
				<div class="relative flex-1 min-w-64 max-w-md">
					<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
					<input
						type="text"
						placeholder="Search {activeTab}..."
						bind:value={searchQuery}
						class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
					/>
				</div>

				<!-- Category Filter -->
				{#if activeTab === 'recipes'}
					<div class="flex items-center gap-1">
						<button onclick={() => selectedRecipeCategory = 'all'} class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {selectedRecipeCategory === 'all' ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 hover:bg-gray-100'}">All</button>
						{#each RECIPE_CATEGORIES as cat}
							<button onclick={() => selectedRecipeCategory = cat.value} class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {selectedRecipeCategory === cat.value ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 hover:bg-gray-100'}">{cat.label}</button>
						{/each}
					</div>
				{:else}
					<div class="flex items-center gap-1">
						<button onclick={() => selectedToolCategory = 'all'} class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {selectedToolCategory === 'all' ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 hover:bg-gray-100'}">All</button>
						{#each TOOL_CATEGORIES as cat}
							<button onclick={() => selectedToolCategory = cat.value} class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {selectedToolCategory === cat.value ? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300' : 'text-gray-600 hover:bg-gray-100'}">{cat.label}</button>
						{/each}
					</div>
				{/if}

				{#if hasActiveFilters}
					<button onclick={clearFilters} class="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg">
						<X size={14} />
						Clear filters
					</button>
				{/if}
			</div>

			<!-- View Toggle -->
			<div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
				<button onclick={() => setViewMode('card')} class="p-2 rounded-md transition-colors {viewMode === 'card' ? 'bg-white dark:bg-gray-700 text-violet-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}" title="Card view">
					<LayoutGrid size={18} />
				</button>
				<button onclick={() => setViewMode('list')} class="p-2 rounded-md transition-colors {viewMode === 'list' ? 'bg-white dark:bg-gray-700 text-violet-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}" title="List view">
					<LayoutList size={18} />
				</button>
			</div>
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto p-6">
		{#if currentItems.length === 0}
			<div class="flex flex-col items-center justify-center h-full text-center">
				{#if activeTab === 'recipes'}
					<Boxes size={48} class="text-gray-300 dark:text-gray-600 mb-4" />
				{:else}
					<Wrench size={48} class="text-gray-300 dark:text-gray-600 mb-4" />
				{/if}
				{#if totalCount === 0}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No {activeTab} yet</h3>
					<p class="text-sm text-gray-500 mb-4 max-w-md">
						{#if activeTab === 'recipes'}
							Save workflow subgraphs as recipes to reuse them across workflows.
						{:else}
							Create tools to use in LLM and Agent nodes.
						{/if}
					</p>
					<div class="flex items-center gap-3">
						<button onclick={handleImport} class="px-4 py-2 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg flex items-center gap-2">
							<Upload size={16} />
							Import {activeTab === 'recipes' ? 'Recipe' : 'Tool'}
						</button>
						{#if activeTab === 'tools'}
							<button onclick={handleCreate} class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg flex items-center gap-2">
								<Plus size={16} />
								Create Tool
							</button>
						{/if}
					</div>
				{:else}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No matching {activeTab}</h3>
					<p class="text-sm text-gray-500">Try adjusting your search or filters</p>
				{/if}
			</div>
		{:else if viewMode === 'card'}
			<!-- Card View -->
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each currentItems as item (item.id)}
					{@const isRecipe = activeTab === 'recipes'}
					{@const Icon = isRecipe ? recipeCategoryIcons[(item as Recipe).category] : toolCategoryIcons[(item as Tool).category]}
					{@const color = getCategoryColor(isRecipe ? (item as Recipe).category : (item as Tool).category, isRecipe ? 'recipe' : 'tool')}
					<div
						class="group bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md transition-all overflow-hidden cursor-pointer"
						onclick={() => isRecipe ? (previewRecipe = item as Recipe) : handleEdit(item.id)}
					>
						<div class="p-4">
							<div class="flex items-start justify-between mb-3">
								<div class="flex items-center gap-3">
									<button onclick={(e) => toggleSelect(item.id, e)} class="p-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
										{#if selectedIds.has(item.id)}
											<CheckSquare size={18} class="text-violet-600" />
										{:else}
											<Square size={18} class="text-gray-400 group-hover:text-gray-500" />
										{/if}
									</button>
									<div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: {color}20">
										<Icon size={20} style="color: {color}" />
									</div>
								</div>
								<button onclick={(e) => showContextMenu(e, item.id)} class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity">
									<MoreVertical size={16} />
								</button>
							</div>
							<h3 class="font-medium text-gray-800 dark:text-gray-200 mb-1 truncate">{item.name}</h3>
							{#if item.description}
								<p class="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-2">{item.description}</p>
							{/if}
							{#if isRecipe}
								<div class="flex items-center gap-3 text-xs text-gray-400">
									<span class="flex items-center gap-1"><Layers size={12} />{(item as Recipe).nodeCount} nodes</span>
								</div>
							{:else}
								<div class="text-xs text-gray-400 font-mono truncate">{(item as Tool).import_path}</div>
							{/if}
						</div>
						<div class="px-4 py-2.5 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-xs text-gray-400">
							<span>{formatDate(item.updatedAt)}</span>
							{#if isRecipe}
								<button onclick={(e) => { e.stopPropagation(); handleAddRecipe(item as Recipe); }} class="text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1">
									<Plus size={12} />
									Add to Workflow
								</button>
							{:else}
								<button onclick={(e) => { e.stopPropagation(); handleEdit(item.id); }} class="text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1">
									<Edit3 size={12} />
									Edit
								</button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<!-- List View -->
			<table class="w-full">
				<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
					<tr>
						<th class="text-left px-4 py-3 w-10">
							<button onclick={toggleSelectAll} class="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700">
								{#if allSelected()}
									<CheckSquare size={18} class="text-violet-600" />
								{:else if someSelected()}
									<MinusSquare size={18} class="text-violet-600" />
								{:else}
									<Square size={18} class="text-gray-400" />
								{/if}
							</button>
						</th>
						<th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
						<th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Category</th>
						<th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{activeTab === 'recipes' ? 'Nodes' : 'Path'}</th>
						<th class="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Updated</th>
						<th class="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 dark:divide-gray-800">
					{#each currentItems as item (item.id)}
						{@const isRecipe = activeTab === 'recipes'}
						{@const Icon = isRecipe ? recipeCategoryIcons[(item as Recipe).category] : toolCategoryIcons[(item as Tool).category]}
						{@const color = getCategoryColor(isRecipe ? (item as Recipe).category : (item as Tool).category, isRecipe ? 'recipe' : 'tool')}
						{@const catLabel = isRecipe ? RECIPE_CATEGORIES.find(c => c.value === (item as Recipe).category)?.label : TOOL_CATEGORIES.find(c => c.value === (item as Tool).category)?.label}
						<tr class="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer" onclick={() => isRecipe ? (previewRecipe = item as Recipe) : handleEdit(item.id)}>
							<td class="px-4 py-3">
								<button onclick={(e) => toggleSelect(item.id, e)} class="p-0.5 rounded hover:bg-gray-200">
									{#if selectedIds.has(item.id)}
										<CheckSquare size={18} class="text-violet-600" />
									{:else}
										<Square size={18} class="text-gray-400" />
									{/if}
								</button>
							</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-3">
									<div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background-color: {color}20">
										<Icon size={16} style="color: {color}" />
									</div>
									<div>
										<div class="font-medium text-gray-900 dark:text-gray-100">{item.name}</div>
										{#if item.description}
											<div class="text-xs text-gray-500 truncate max-w-xs">{item.description}</div>
										{/if}
									</div>
								</div>
							</td>
							<td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{catLabel}</td>
							<td class="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">
								{#if isRecipe}
									<span class="flex items-center gap-1"><Layers size={14} class="text-violet-500" />{(item as Recipe).nodeCount}</span>
								{:else}
									<span class="font-mono text-xs">{(item as Tool).import_path}</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-sm text-gray-500">{formatDate(item.updatedAt)}</td>
							<td class="px-4 py-3 text-right">
								<div class="flex items-center justify-end gap-2">
									{#if isRecipe}
										<button onclick={(e) => { e.stopPropagation(); handleAddRecipe(item as Recipe); }} class="px-3 py-1.5 text-sm font-medium text-violet-600 hover:bg-violet-100 rounded-lg">
											<Plus size={14} class="inline mr-1" />Add
										</button>
									{:else}
										<button onclick={(e) => { e.stopPropagation(); handleEdit(item.id); }} class="px-3 py-1.5 text-sm font-medium text-violet-600 hover:bg-violet-100 rounded-lg">
											<Edit3 size={14} class="inline mr-1" />Edit
										</button>
									{/if}
									<button onclick={(e) => showContextMenu(e, item.id)} class="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
										<MoreVertical size={16} />
									</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
</div>

<!-- Context Menu -->
{#if contextMenuId}
	<div class="fixed bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 z-50 min-w-[160px]" style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px" onclick={(e) => e.stopPropagation()}>
		{#if activeTab === 'recipes'}
			<button onclick={() => { previewRecipe = recipeStore.getRecipe(contextMenuId!) ?? null; hideContextMenu(); }} class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2">
				<Eye size={14} />Preview
			</button>
		{:else}
			<button onclick={() => handleEdit(contextMenuId!)} class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2">
				<Edit3 size={14} />Edit
			</button>
		{/if}
		<button onclick={() => handleDuplicate(contextMenuId!)} class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2">
			<Copy size={14} />Duplicate
		</button>
		<button onclick={() => handleExport(contextMenuId!)} class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2">
			<Download size={14} />Export
		</button>
		<div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
		<button onclick={() => requestDelete(contextMenuId!)} class="w-full px-4 py-2 text-sm text-left text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2">
			<Trash2 size={14} />Delete
		</button>
	</div>
{/if}

<!-- Tool Editor Modal -->
{#if showToolEditor}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
		<div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col">
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{editingTool ? 'Edit Tool' : 'Create Tool'}</h3>
				<button onclick={() => { showToolEditor = false; editingTool = null; }} class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
					<X size={18} />
				</button>
			</div>
			<div class="flex-1 overflow-y-auto p-6">
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div>
						<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Name *</label>
						<input type="text" bind:value={toolFormName} placeholder="My Search Tool" class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500" />
					</div>
					<div>
						<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Category</label>
						<select bind:value={toolFormCategory} class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500">
							{#each TOOL_CATEGORIES as cat}
								<option value={cat.value}>{cat.label}</option>
							{/each}
						</select>
					</div>
				</div>
				<div class="mb-4">
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Description</label>
					<input type="text" bind:value={toolFormDescription} placeholder="A tool that searches..." class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500" />
				</div>
				<div class="mb-4">
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Import Path *</label>
					<input type="text" bind:value={toolFormImportPath} placeholder="mypackage.tools.search_tool" class="w-full px-3 py-2 text-sm font-mono rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500" />
				</div>
				<div>
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Code</label>
					<div class="h-64 border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
						<MonacoEditor bind:value={toolFormCode} language="python" theme="vs-dark" />
					</div>
				</div>
			</div>
			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-800">
				<button onclick={() => { showToolEditor = false; editingTool = null; }} class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
				<button onclick={saveTool} disabled={!toolFormName.trim() || !toolFormImportPath.trim()} class="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-300 text-white text-sm font-medium rounded-lg">
					{editingTool ? 'Save Changes' : 'Create Tool'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Recipe Preview Modal -->
{#if previewRecipe}
	<RecipePreviewModal recipe={previewRecipe} on:close={() => previewRecipe = null} on:addToWorkflow={() => { handleAddRecipe(previewRecipe!); previewRecipe = null; }} />
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmationModal
		title="Delete {activeTab === 'recipes' ? 'Recipe' : 'Tool'}{deleteCount > 1 ? 's' : ''}"
		message={`Are you sure you want to delete ${deleteCount} ${activeTab === 'recipes' ? 'recipe' : 'tool'}${deleteCount > 1 ? 's' : ''}? This cannot be undone.`}
		confirmText="Delete"
		variant="danger"
		on:confirm={confirmDelete}
		on:cancel={cancelDelete}
	/>
{/if}
