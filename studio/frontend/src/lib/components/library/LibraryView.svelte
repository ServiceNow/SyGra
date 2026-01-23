<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import {
		Search, Plus, Boxes, Wrench, RefreshCw, X, Upload, Download,
		LayoutList, LayoutGrid, MoreVertical, Trash2, Copy, Edit3,
		Brain, Database, Shuffle, Bot, Puzzle, Globe, Layers, Clock,
		CheckSquare, Square, MinusSquare, Code, Eye, Library, Play
	} from 'lucide-svelte';
	import { recipeStore, RECIPE_CATEGORIES, type Recipe, type RecipeCategory } from '$lib/stores/recipe.svelte';
	import { toolStore, TOOL_CATEGORIES, DEFAULT_TOOL_CODE, type Tool, type ToolCategory } from '$lib/stores/tool.svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import ConfirmationModal from '$lib/components/common/ConfirmationModal.svelte';
	import RecipePreviewModal from './RecipePreviewModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';

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

		// Calculate position with viewport boundary detection
		const menuWidth = 160;
		const menuHeight = 200;
		const padding = 8;

		let x = e.clientX;
		let y = e.clientY;

		if (x + menuWidth + padding > window.innerWidth) {
			x = window.innerWidth - menuWidth - padding;
		}
		if (y + menuHeight + padding > window.innerHeight) {
			y = window.innerHeight - menuHeight - padding;
		}

		contextMenuPosition = { x, y };
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

<div class="h-full w-full flex flex-col bg-surface-secondary">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-[var(--border)] bg-surface-elevated px-6 py-5">
		<div class="flex items-center justify-between mb-5">
			<div class="flex items-center gap-4">
				<div class="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm bg-gradient-ai">
					<Library size={20} class="text-white" />
				</div>
				<div>
					<h1 class="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Library</h1>
					<p class="text-sm text-[var(--text-muted)]">
						{currentItems.length} of {totalCount} {activeTab}
						{#if selectionCount > 0}
							<span class="ml-2 text-info">• {selectionCount} selected</span>
						{/if}
					</p>
				</div>
			</div>
			<div class="flex items-center gap-3">
				<!-- Tab Toggle -->
				<div class="flex items-center bg-surface-tertiary rounded-xl p-1">
					<button
						onclick={() => { activeTab = 'recipes'; selectedIds = new Set(); }}
						class="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 {activeTab === 'recipes' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
					>
						<Boxes size={16} />
						Recipes
						{#if recipeStore.recipes.length > 0}
							<span class="text-xs px-1.5 py-0.5 rounded-full bg-surface-tertiary">{recipeStore.recipes.length}</span>
						{/if}
					</button>
					<button
						onclick={() => { activeTab = 'tools'; selectedIds = new Set(); }}
						class="px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center gap-2 {activeTab === 'tools' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
					>
						<Wrench size={16} />
						Tools
						{#if toolStore.tools.length > 0}
							<span class="text-xs px-1.5 py-0.5 rounded-full bg-surface-tertiary">{toolStore.tools.length}</span>
						{/if}
					</button>
				</div>

				<div class="w-px h-6 bg-[var(--border)]"></div>

				{#if selectionCount > 0}
					<button onclick={clearSelection} class="p-2.5 rounded-xl hover:bg-surface-hover text-[var(--text-muted)]" title="Clear selection">
						<X size={18} />
					</button>
					<button onclick={() => requestDelete()} class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-error-light hover:bg-error/20 text-error text-sm font-medium transition-all duration-200">
						<Trash2 size={16} />
						Delete ({selectionCount})
					</button>
					<div class="w-px h-6 bg-[var(--border)]"></div>
				{/if}

				<button onclick={handleImport} class="flex items-center gap-2 px-4 py-2.5 border border-[var(--border)] hover:bg-surface-hover hover:border-[var(--border-hover)] rounded-xl transition-all duration-200 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
					<Upload size={16} />
					Import
				</button>
				{#if activeTab === 'tools'}
					<button onclick={handleCreate} class="flex items-center gap-2 px-4 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 font-semibold shadow-sm hover:shadow-glow-accent hover:-translate-y-0.5 text-sm">
						<Plus size={16} strokeWidth={2.5} />
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
					<Search size={16} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
					<input
						type="text"
						placeholder="Search {activeTab}..."
						bind:value={searchQuery}
						class="w-full pl-10 pr-4 py-2.5 border border-[var(--border)] rounded-xl bg-surface text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)] text-sm transition-all duration-200"
					/>
				</div>

				<!-- Category Filter -->
				{#if activeTab === 'recipes'}
					<div class="flex items-center gap-1">
						<button onclick={() => selectedRecipeCategory = 'all'} class="px-3 py-2 text-xs font-medium rounded-lg transition-all duration-200 {selectedRecipeCategory === 'all' ? 'bg-info-light text-info' : 'text-[var(--text-secondary)] hover:bg-surface-hover'}">All</button>
						{#each RECIPE_CATEGORIES as cat}
							<button onclick={() => selectedRecipeCategory = cat.value} class="px-3 py-2 text-xs font-medium rounded-lg transition-all duration-200 {selectedRecipeCategory === cat.value ? 'bg-info-light text-info' : 'text-[var(--text-secondary)] hover:bg-surface-hover'}">{cat.label}</button>
						{/each}
					</div>
				{:else}
					<div class="flex items-center gap-1">
						<button onclick={() => selectedToolCategory = 'all'} class="px-3 py-2 text-xs font-medium rounded-lg transition-all duration-200 {selectedToolCategory === 'all' ? 'bg-info-light text-info' : 'text-[var(--text-secondary)] hover:bg-surface-hover'}">All</button>
						{#each TOOL_CATEGORIES as cat}
							<button onclick={() => selectedToolCategory = cat.value} class="px-3 py-2 text-xs font-medium rounded-lg transition-all duration-200 {selectedToolCategory === cat.value ? 'bg-info-light text-info' : 'text-[var(--text-secondary)] hover:bg-surface-hover'}">{cat.label}</button>
						{/each}
					</div>
				{/if}

				{#if hasActiveFilters}
					<button onclick={clearFilters} class="flex items-center gap-1.5 px-3 py-2.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-surface-hover rounded-xl transition-all duration-200">
						<X size={14} />
						Clear filters
					</button>
				{/if}
			</div>

			<!-- View Toggle -->
			<div class="flex items-center bg-surface-tertiary rounded-xl p-1">
				<button onclick={() => setViewMode('card')} class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'card' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}" title="Card view">
					<LayoutGrid size={18} />
				</button>
				<button onclick={() => setViewMode('list')} class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'list' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}" title="List view">
					<LayoutList size={18} />
				</button>
			</div>
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto">
		{#if currentItems.length === 0}
			<div class="flex flex-col items-center justify-center h-full text-center p-6">
				<div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 shadow-md bg-gradient-ai">
					{#if activeTab === 'recipes'}
						<Boxes size={28} class="text-white" />
					{:else}
						<Wrench size={28} class="text-white" />
					{/if}
				</div>
				{#if totalCount === 0}
					<h3 class="text-lg font-medium text-[var(--text-primary)] mb-1">No {activeTab} yet</h3>
					<p class="text-sm text-[var(--text-muted)] mb-5 max-w-md">
						{#if activeTab === 'recipes'}
							Save workflow subgraphs as recipes to reuse them across workflows.
						{:else}
							Create tools to use in LLM and Agent nodes.
						{/if}
					</p>
					<div class="flex items-center gap-3">
						<button onclick={handleImport} class="px-4 py-2.5 border border-[var(--border)] hover:bg-surface-hover text-[var(--text-secondary)] text-sm font-medium rounded-xl flex items-center gap-2 transition-all duration-200">
							<Upload size={16} />
							Import {activeTab === 'recipes' ? 'Recipe' : 'Tool'}
						</button>
						{#if activeTab === 'tools'}
							<button onclick={handleCreate} class="flex items-center gap-2 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 font-semibold shadow-sm hover:shadow-glow-accent hover:-translate-y-0.5 text-sm">
								<Plus size={16} strokeWidth={2.5} />
								Create Tool
							</button>
						{/if}
					</div>
				{:else}
					<h3 class="text-lg font-medium text-[var(--text-primary)] mb-1">No matching {activeTab}</h3>
					<p class="text-sm text-[var(--text-muted)]">Try adjusting your search or filters</p>
				{/if}
			</div>
		{:else if viewMode === 'card'}
			<!-- Card View -->
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 p-6">
				{#each currentItems as item (item.id)}
					{@const isRecipe = activeTab === 'recipes'}
					{@const Icon = isRecipe ? recipeCategoryIcons[(item as Recipe).category] : toolCategoryIcons[(item as Tool).category]}
					{@const color = getCategoryColor(isRecipe ? (item as Recipe).category : (item as Tool).category, isRecipe ? 'recipe' : 'tool')}
					<div
						class="group relative bg-surface-elevated border border-[var(--border)] rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 hover:shadow-card-hover hover:border-[var(--border-focus)] hover:-translate-y-1"
						onclick={() => isRecipe ? (previewRecipe = item as Recipe) : handleEdit(item.id)}
					>
						<!-- Selection checkbox -->
						<div class="absolute top-4 left-4 z-10">
							<button onclick={(e) => toggleSelect(item.id, e)} class="p-1 rounded-lg hover:bg-surface-hover transition-colors">
								{#if selectedIds.has(item.id)}
									<CheckSquare size={18} class="text-info" />
								{:else}
									<Square size={18} class="text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
								{/if}
							</button>
						</div>

						<!-- Menu button -->
						<div class="absolute top-4 right-4 z-10">
							<button onclick={(e) => { e.stopPropagation(); showContextMenu(e, item.id); }} class="p-1.5 rounded-lg hover:bg-surface-hover text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity">
								<MoreVertical size={16} />
							</button>
						</div>

						<div class="p-5">
							<!-- Icon and Name -->
							<div class="flex items-start gap-4 mb-4">
								<div class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm transition-transform duration-200 group-hover:scale-105" style="background-color: {color}20">
									<Icon size={22} style="color: {color}" />
								</div>
								<div class="flex-1 min-w-0 pt-1">
									<h3 class="font-semibold text-[var(--text-primary)] truncate group-hover:text-info transition-colors duration-200">{item.name}</h3>
									{#if item.description}
										<p class="text-sm text-[var(--text-muted)] line-clamp-2 mt-1">{item.description}</p>
									{/if}
								</div>
							</div>

							<!-- Stats -->
							<div class="flex items-center gap-4 mb-4">
								{#if isRecipe}
									<div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
										<Layers size={15} class="text-info" />
										<span>{(item as Recipe).nodeCount} nodes</span>
									</div>
								{:else}
									<div class="text-xs text-[var(--text-muted)] font-mono truncate">{(item as Tool).import_path}</div>
								{/if}
							</div>

							<!-- Action Button -->
							<button
								onclick={(e) => { e.stopPropagation(); isRecipe ? handleAddRecipe(item as Recipe) : handleEdit(item.id); }}
								class="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-info bg-info-light hover:bg-[rgba(82,184,255,0.2)] rounded-xl transition-all duration-200"
							>
								{#if isRecipe}
									<Plus size={14} />
									Add to Workflow
								{:else}
									<Edit3 size={14} />
									Edit Tool
								{/if}
							</button>
						</div>

						<!-- Footer -->
						<div class="px-5 py-3 bg-surface-secondary border-t border-[var(--border)] text-xs text-[var(--text-muted)]">
							{formatDate(item.updatedAt)}
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<!-- List View -->
			<table class="w-full">
				<thead class="sticky top-0 bg-surface-secondary border-b border-[var(--border)] z-10">
					<tr>
						<th class="text-left px-6 py-4 w-10">
							<button onclick={toggleSelectAll} class="p-0.5 rounded hover:bg-surface-hover">
								{#if allSelected()}
									<CheckSquare size={18} class="text-info" />
								{:else if someSelected()}
									<MinusSquare size={18} class="text-info" />
								{:else}
									<Square size={18} class="text-[var(--text-muted)]" />
								{/if}
							</button>
						</th>
						<th class="text-left px-6 py-4 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Name</th>
						<th class="text-left px-6 py-4 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Category</th>
						<th class="text-left px-6 py-4 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">{activeTab === 'recipes' ? 'Nodes' : 'Path'}</th>
						<th class="text-left px-6 py-4 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Updated</th>
						<th class="text-right px-6 py-4 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-[var(--border)]">
					{#each currentItems as item (item.id)}
						{@const isRecipe = activeTab === 'recipes'}
						{@const Icon = isRecipe ? recipeCategoryIcons[(item as Recipe).category] : toolCategoryIcons[(item as Tool).category]}
						{@const color = getCategoryColor(isRecipe ? (item as Recipe).category : (item as Tool).category, isRecipe ? 'recipe' : 'tool')}
						{@const catLabel = isRecipe ? RECIPE_CATEGORIES.find(c => c.value === (item as Recipe).category)?.label : TOOL_CATEGORIES.find(c => c.value === (item as Tool).category)?.label}
						<tr class="group cursor-pointer transition-all duration-200 bg-surface-elevated hover:bg-surface-hover" onclick={() => isRecipe ? (previewRecipe = item as Recipe) : handleEdit(item.id)}>
							<td class="px-6 py-4">
								<button onclick={(e) => toggleSelect(item.id, e)} class="p-0.5 rounded hover:bg-surface-hover">
									{#if selectedIds.has(item.id)}
										<CheckSquare size={18} class="text-info" />
									{:else}
										<Square size={18} class="text-[var(--text-muted)]" />
									{/if}
								</button>
							</td>
							<td class="px-6 py-4">
								<div class="flex items-center gap-4">
									<div class="w-11 h-11 rounded-xl flex items-center justify-center shadow-sm transition-transform duration-200 group-hover:scale-105" style="background-color: {color}20">
										<Icon size={20} style="color: {color}" />
									</div>
									<div class="flex flex-col">
										<span class="font-semibold text-[var(--text-primary)] group-hover:text-info transition-colors duration-200">{item.name}</span>
										{#if item.description}
											<span class="text-xs text-[var(--text-muted)] truncate max-w-xs mt-0.5">{item.description}</span>
										{/if}
									</div>
								</div>
							</td>
							<td class="px-6 py-4 text-sm text-[var(--text-secondary)]">{catLabel}</td>
							<td class="px-6 py-4 text-sm text-[var(--text-secondary)]">
								{#if isRecipe}
									<span class="inline-flex items-center gap-2"><Layers size={15} class="text-info" />{(item as Recipe).nodeCount} nodes</span>
								{:else}
									<span class="font-mono text-xs">{(item as Tool).import_path}</span>
								{/if}
							</td>
							<td class="px-6 py-4 text-sm text-[var(--text-muted)]">{formatDate(item.updatedAt)}</td>
							<td class="px-6 py-4 text-right">
								<div class="flex items-center justify-end gap-2">
									<button onclick={(e) => { e.stopPropagation(); isRecipe ? handleAddRecipe(item as Recipe) : handleEdit(item.id); }} class="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-info bg-info-light hover:bg-[rgba(82,184,255,0.2)] rounded-lg transition-all duration-200">
										{#if isRecipe}
											<Plus size={14} />Add
										{:else}
											<Edit3 size={14} />Edit
										{/if}
									</button>
									<button onclick={(e) => { e.stopPropagation(); showContextMenu(e, item.id); }} class="p-2 rounded-lg hover:bg-surface-tertiary text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all duration-200">
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
	<div class="fixed bg-surface-elevated rounded-xl shadow-dropdown border border-[var(--border)] py-1.5 z-50 min-w-[160px] animate-scale-in" style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px" onclick={(e) => e.stopPropagation()}>
		{#if activeTab === 'recipes'}
			<button onclick={() => { previewRecipe = recipeStore.getRecipe(contextMenuId!) ?? null; hideContextMenu(); }} class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150">
				<Eye size={14} />Preview
			</button>
		{:else}
			<button onclick={() => handleEdit(contextMenuId!)} class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150">
				<Edit3 size={14} />Edit
			</button>
		{/if}
		<button onclick={() => handleDuplicate(contextMenuId!)} class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150">
			<Copy size={14} />Duplicate
		</button>
		<button onclick={() => handleExport(contextMenuId!)} class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150">
			<Download size={14} />Export
		</button>
		<div class="h-px bg-[var(--border)] my-1.5 mx-2"></div>
		<button onclick={() => requestDelete(contextMenuId!)} class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-error hover:bg-error-light transition-colors duration-150">
			<Trash2 size={14} />Delete
		</button>
	</div>
{/if}

<!-- Tool Editor Modal -->
{#if showToolEditor}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in">
		<div class="bg-surface-elevated rounded-2xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col border border-[var(--border)] animate-scale-in">
			<div class="flex items-center justify-between px-6 py-4 border-b border-[var(--border)]">
				<h3 class="text-lg font-semibold text-[var(--text-primary)]">{editingTool ? 'Edit Tool' : 'Create Tool'}</h3>
				<button onclick={() => { showToolEditor = false; editingTool = null; }} class="p-1.5 rounded-xl hover:bg-surface-hover text-[var(--text-muted)]">
					<X size={18} />
				</button>
			</div>
			<!-- Form Fields -->
			<div class="flex-shrink-0 px-6 pt-6 pb-4">
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div>
						<label class="block text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Name *</label>
						<input type="text" bind:value={toolFormName} placeholder="My Search Tool" class="w-full px-4 py-2.5 text-sm rounded-xl border border-[var(--border)] bg-surface text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)]" />
					</div>
					<div class="relative z-10">
						<label class="block text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Category</label>
						<CustomSelect
							options={TOOL_CATEGORIES.map(c => ({ value: c.value, label: c.label }))}
							bind:value={toolFormCategory}
							placeholder="Select category"
							searchable={false}
						/>
					</div>
				</div>
				<div class="grid grid-cols-2 gap-4">
					<div>
						<label class="block text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Description</label>
						<input type="text" bind:value={toolFormDescription} placeholder="A tool that searches..." class="w-full px-4 py-2.5 text-sm rounded-xl border border-[var(--border)] bg-surface text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)]" />
					</div>
					<div>
						<label class="block text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Import Path *</label>
						<input type="text" bind:value={toolFormImportPath} placeholder="mypackage.tools.search_tool" class="w-full px-4 py-2.5 text-sm font-mono rounded-xl border border-[var(--border)] bg-surface text-[var(--text-primary)] focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)]" />
					</div>
				</div>
			</div>
			<!-- Code Editor -->
			<div class="flex-1 min-h-0 px-6 pb-6">
				<label class="block text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-1.5">Code</label>
				<div class="h-64 border border-[var(--border)] rounded-xl overflow-hidden">
					<MonacoEditor bind:value={toolFormCode} language="python" />
				</div>
			</div>
			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border)]">
				<button onclick={() => { showToolEditor = false; editingTool = null; }} class="px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-surface-hover rounded-xl transition-all duration-200">Cancel</button>
				<button onclick={saveTool} disabled={!toolFormName.trim() || !toolFormImportPath.trim()} class="px-4 py-2.5 text-sm font-medium bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed">
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
