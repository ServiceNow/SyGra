<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toolStore, TOOL_CATEGORIES, DEFAULT_TOOL_CODE, type Tool, type ToolCategory } from '$lib/stores/tool.svelte';
	import {
		Search, Plus, Wrench, Database, Globe, Puzzle, Trash2, Copy,
		Download, Upload, MoreVertical, X, Code, Edit3, Check
	} from 'lucide-svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import ConfirmModal from '$lib/components/common/ConfirmModal.svelte';

	const dispatch = createEventDispatcher();

	// Local state
	let showCreateModal = $state(false);
	let editingTool = $state<Tool | null>(null);
	let contextMenuTool = $state<Tool | null>(null);
	let contextMenuPosition = $state({ x: 0, y: 0 });
	let importInput: HTMLInputElement;

	// Form state
	let formName = $state('');
	let formDescription = $state('');
	let formCategory = $state<ToolCategory>('custom');
	let formCode = $state(DEFAULT_TOOL_CODE);
	let formImportPath = $state('');

	// Confirmation modal
	let showDeleteConfirm = $state(false);
	let toolToDelete = $state<Tool | null>(null);

	// Category icon mapping
	const categoryIcons: Record<ToolCategory, typeof Wrench> = {
		search: Search,
		data: Database,
		api: Globe,
		utility: Wrench,
		custom: Puzzle
	};

	function getCategoryColor(category: ToolCategory): string {
		return TOOL_CATEGORIES.find(c => c.value === category)?.color || '#6b7280';
	}

	function openCreateModal() {
		formName = '';
		formDescription = '';
		formCategory = 'custom';
		formCode = DEFAULT_TOOL_CODE;
		formImportPath = '';
		editingTool = null;
		showCreateModal = true;
	}

	function openEditModal(tool: Tool) {
		formName = tool.name;
		formDescription = tool.description;
		formCategory = tool.category;
		formCode = tool.code;
		formImportPath = tool.import_path;
		editingTool = tool;
		showCreateModal = true;
		hideContextMenu();
	}

	function closeCreateModal() {
		showCreateModal = false;
		editingTool = null;
	}

	function saveTool() {
		if (!formName.trim() || !formImportPath.trim()) return;

		if (editingTool) {
			toolStore.updateTool(editingTool.id, {
				name: formName,
				description: formDescription,
				category: formCategory,
				code: formCode,
				import_path: formImportPath
			});
		} else {
			toolStore.addTool({
				name: formName,
				description: formDescription,
				category: formCategory,
				code: formCode,
				import_path: formImportPath
			});
		}
		closeCreateModal();
	}

	// Context menu
	function showContextMenu(e: MouseEvent, tool: Tool) {
		e.preventDefault();
		e.stopPropagation();
		contextMenuTool = tool;
		contextMenuPosition = { x: e.clientX, y: e.clientY };
	}

	function hideContextMenu() {
		contextMenuTool = null;
	}

	function handleDuplicate() {
		if (contextMenuTool) {
			toolStore.duplicateTool(contextMenuTool.id);
		}
		hideContextMenu();
	}

	function handleDelete() {
		if (contextMenuTool) {
			toolToDelete = contextMenuTool;
			showDeleteConfirm = true;
		}
		hideContextMenu();
	}

	function confirmDelete() {
		if (toolToDelete) {
			toolStore.deleteTool(toolToDelete.id);
		}
		toolToDelete = null;
		showDeleteConfirm = false;
	}

	function handleExport() {
		if (contextMenuTool) {
			const json = toolStore.exportTool(contextMenuTool.id);
			if (json) {
				const blob = new Blob([json], { type: 'application/json' });
				const url = URL.createObjectURL(blob);
				const a = document.createElement('a');
				a.href = url;
				a.download = `${contextMenuTool.name.toLowerCase().replace(/\s+/g, '_')}.tool.json`;
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
				const result = toolStore.importTool(reader.result as string);
				if (!result) {
					alert('Failed to import tool. Please check the file format.');
				}
			};
			reader.readAsText(file);
		}
		input.value = '';
	}

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

	// Auto-generate import path from name
	function generateImportPath(name: string): string {
		return `tools.${name.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')}`;
	}

	$effect(() => {
		if (!editingTool && formName && !formImportPath) {
			formImportPath = generateImportPath(formName);
		}
	});
</script>

<svelte:window onclick={hideContextMenu} />

<input
	type="file"
	accept=".json"
	bind:this={importInput}
	onchange={onFileImport}
	class="hidden"
/>

<div class="h-full flex flex-col">
	<!-- Header -->
	<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
		<div>
			<h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">Tools</h2>
			<p class="text-sm text-gray-500 dark:text-gray-400">Create and manage reusable tools for LLM/Agent nodes</p>
		</div>
		<div class="flex items-center gap-2">
			<button
				onclick={handleImport}
				class="px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
			>
				<Upload size={16} class="inline mr-1.5" />
				Import
			</button>
			<button
				onclick={openCreateModal}
				class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
			>
				<Plus size={16} />
				Create Tool
			</button>
		</div>
	</div>

	<!-- Search & Filters -->
	<div class="px-6 py-3 border-b border-gray-200 dark:border-gray-800">
		<div class="flex items-center gap-4">
			<div class="relative flex-1 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
				<input
					type="text"
					placeholder="Search tools..."
					bind:value={toolStore.searchQuery}
					class="w-full pl-10 pr-4 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
				/>
			</div>
			<div class="flex items-center gap-1">
				<button
					onclick={() => toolStore.selectedCategory = 'all'}
					class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
					class:bg-violet-100={toolStore.selectedCategory === 'all'}
					class:dark:bg-violet-900={toolStore.selectedCategory === 'all'}
					class:text-violet-700={toolStore.selectedCategory === 'all'}
					class:dark:text-violet-300={toolStore.selectedCategory === 'all'}
					class:text-gray-600={toolStore.selectedCategory !== 'all'}
					class:hover:bg-gray-100={toolStore.selectedCategory !== 'all'}
				>
					All
				</button>
				{#each TOOL_CATEGORIES as cat}
					<button
						onclick={() => toolStore.selectedCategory = cat.value}
						class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors"
						class:bg-violet-100={toolStore.selectedCategory === cat.value}
						class:dark:bg-violet-900={toolStore.selectedCategory === cat.value}
						class:text-violet-700={toolStore.selectedCategory === cat.value}
						class:dark:text-violet-300={toolStore.selectedCategory === cat.value}
						class:text-gray-600={toolStore.selectedCategory !== cat.value}
						class:hover:bg-gray-100={toolStore.selectedCategory !== cat.value}
					>
						{cat.label}
					</button>
				{/each}
			</div>
		</div>
	</div>

	<!-- Tool Grid -->
	<div class="flex-1 overflow-y-auto p-6">
		{#if toolStore.filteredTools.length === 0}
			<div class="flex flex-col items-center justify-center h-full text-center">
				<Wrench size={48} class="text-gray-300 dark:text-gray-600 mb-4" />
				{#if toolStore.tools.length === 0}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No tools yet</h3>
					<p class="text-sm text-gray-500 dark:text-gray-500 mb-4 max-w-md">
						Create your first tool to use in LLM and Agent nodes. Tools are Python functions decorated with @tool.
					</p>
					<button
						onclick={openCreateModal}
						class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
					>
						<Plus size={16} />
						Create Your First Tool
					</button>
				{:else}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No matching tools</h3>
					<p class="text-sm text-gray-500">Try adjusting your search or filters</p>
				{/if}
			</div>
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each toolStore.filteredTools as tool (tool.id)}
					{@const Icon = categoryIcons[tool.category]}
					<div
						class="group bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md transition-all overflow-hidden"
					>
						<div class="p-4">
							<div class="flex items-start justify-between mb-3">
								<div
									class="w-10 h-10 rounded-lg flex items-center justify-center"
									style="background-color: {getCategoryColor(tool.category)}20"
								>
									<Icon size={20} style="color: {getCategoryColor(tool.category)}" />
								</div>
								<button
									onclick={(e) => showContextMenu(e, tool)}
									class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"
								>
									<MoreVertical size={16} />
								</button>
							</div>
							<h3 class="font-medium text-gray-800 dark:text-gray-200 mb-1 truncate">
								{tool.name}
							</h3>
							{#if tool.description}
								<p class="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-2">
									{tool.description}
								</p>
							{/if}
							<div class="text-xs text-gray-400 font-mono truncate" title={tool.import_path}>
								{tool.import_path}
							</div>
						</div>
						<div class="px-4 py-2.5 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-700 flex items-center justify-between text-xs text-gray-400">
							<span>{formatDate(tool.updatedAt)}</span>
							<button
								onclick={() => openEditModal(tool)}
								class="text-violet-600 dark:text-violet-400 hover:underline flex items-center gap-1"
							>
								<Edit3 size={12} />
								Edit
							</button>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<!-- Context Menu -->
{#if contextMenuTool}
	<div
		class="fixed bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 z-50 min-w-[160px]"
		style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px"
		onclick={(e) => e.stopPropagation()}
	>
		<button
			onclick={() => openEditModal(contextMenuTool!)}
			class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
		>
			<Edit3 size={14} />
			Edit
		</button>
		<button
			onclick={handleDuplicate}
			class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
		>
			<Copy size={14} />
			Duplicate
		</button>
		<button
			onclick={handleExport}
			class="w-full px-4 py-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
		>
			<Download size={14} />
			Export
		</button>
		<div class="border-t border-gray-200 dark:border-gray-700 my-1"></div>
		<button
			onclick={handleDelete}
			class="w-full px-4 py-2 text-sm text-left text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 flex items-center gap-2"
		>
			<Trash2 size={14} />
			Delete
		</button>
	</div>
{/if}

<!-- Create/Edit Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
		<div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col">
			<!-- Modal Header -->
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
					{editingTool ? 'Edit Tool' : 'Create Tool'}
				</h3>
				<button
					onclick={closeCreateModal}
					class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Modal Body -->
			<div class="flex-1 overflow-y-auto p-6">
				<div class="grid grid-cols-2 gap-4 mb-4">
					<div>
						<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
							Name *
						</label>
						<input
							type="text"
							bind:value={formName}
							placeholder="My Search Tool"
							class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
						/>
					</div>
					<div>
						<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
							Category
						</label>
						<select
							bind:value={formCategory}
							class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
						>
							{#each TOOL_CATEGORIES as cat}
								<option value={cat.value}>{cat.label}</option>
							{/each}
						</select>
					</div>
				</div>

				<div class="mb-4">
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
						Description
					</label>
					<input
						type="text"
						bind:value={formDescription}
						placeholder="A tool that searches for information..."
						class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
					/>
				</div>

				<div class="mb-4">
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
						Import Path *
					</label>
					<input
						type="text"
						bind:value={formImportPath}
						placeholder="mypackage.tools.search_tool"
						class="w-full px-3 py-2 text-sm font-mono rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
					/>
					<p class="text-xs text-gray-400 mt-1">The Python import path where this tool will be available</p>
				</div>

				<div>
					<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">
						Code
					</label>
					<div class="h-64 border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
						<MonacoEditor
							bind:value={formCode}
							language="python"
							theme="vs-dark"
						/>
					</div>
					<p class="text-xs text-gray-400 mt-1">
						Define your tool using the <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">@tool</code> decorator from langchain
					</p>
				</div>
			</div>

			<!-- Modal Footer -->
			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-800">
				<button
					onclick={closeCreateModal}
					class="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					Cancel
				</button>
				<button
					onclick={saveTool}
					disabled={!formName.trim() || !formImportPath.trim()}
					class="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-300 disabled:dark:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
				>
					<Check size={16} />
					{editingTool ? 'Save Changes' : 'Create Tool'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm && toolToDelete}
	<ConfirmModal
		title="Delete Tool"
		message={`Are you sure you want to delete "${toolToDelete.name}"? This cannot be undone.`}
		confirmText="Delete"
		confirmClass="bg-red-600 hover:bg-red-700"
		onconfirm={confirmDelete}
		oncancel={() => { showDeleteConfirm = false; toolToDelete = null; }}
	/>
{/if}
