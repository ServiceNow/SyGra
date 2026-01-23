<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toolStore, TOOL_CATEGORIES, DEFAULT_TOOL_CODE, type Tool, type ToolCategory } from '$lib/stores/tool.svelte';
	import {
		Search, Plus, Wrench, Database, Globe, Puzzle, Trash2, Copy,
		Download, Upload, MoreVertical, X, Code, Edit3, Check
	} from 'lucide-svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import ConfirmModal from '$lib/components/common/ConfirmModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';

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

<div class="h-full flex flex-col bg-surface-secondary">
	<!-- Header -->
	<div class="px-6 py-5 border-b bg-surface-elevated" style="border-color: var(--border);">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-xl bg-gradient-data">
					<Wrench size={18} class="text-white" />
				</div>
				<div>
					<h2 class="text-lg font-semibold" style="color: var(--text-primary);">Tools</h2>
					<p class="text-xs" style="color: var(--text-muted);">Create and manage reusable tools for LLM/Agent nodes</p>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					onclick={handleImport}
					class="flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl hover:bg-surface-hover transition-colors"
					style="color: var(--text-secondary);"
				>
					<Upload size={16} />
					Import
				</button>
				<button
					onclick={openCreateModal}
					class="btn-accent px-4 py-2.5 text-sm font-medium rounded-xl transition-colors flex items-center gap-2 shadow-md"
				>
					<Plus size={16} />
					Create Tool
				</button>
			</div>
		</div>
	</div>

	<!-- Search & Filters -->
	<div class="px-6 py-4 border-b bg-surface-elevated" style="border-color: var(--border);">
		<div class="flex items-center gap-4">
			<div class="relative flex-1 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2" style="color: var(--text-muted);" />
				<input
					type="text"
					placeholder="Search tools..."
					bind:value={toolStore.searchQuery}
					class="w-full pl-10 pr-4 py-2.5 text-sm rounded-xl bg-surface-secondary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-info/50 transition-shadow"
					style="color: var(--text-primary); border: 1px solid var(--border);"
				/>
			</div>
			<div class="flex items-center gap-2 p-1 rounded-xl bg-surface-tertiary">
				<button
					onclick={() => toolStore.selectedCategory = 'all'}
					class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all {
						toolStore.selectedCategory === 'all'
							? 'bg-surface-elevated shadow-sm'
							: 'hover:bg-surface-hover'
					}"
					style={toolStore.selectedCategory === 'all' ? 'color: var(--text-primary);' : 'color: var(--text-secondary);'}
				>
					All
				</button>
				{#each TOOL_CATEGORIES as cat}
					<button
						onclick={() => toolStore.selectedCategory = cat.value}
						class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all {
							toolStore.selectedCategory === cat.value
								? 'bg-surface-elevated shadow-sm'
								: 'hover:bg-surface-hover'
						}"
						style={toolStore.selectedCategory === cat.value ? 'color: var(--text-primary);' : 'color: var(--text-secondary);'}
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
				<div class="w-20 h-20 rounded-2xl flex items-center justify-center mb-5 bg-gradient-data shadow-lg">
					<Wrench size={32} class="text-white" />
				</div>
				{#if toolStore.tools.length === 0}
					<h3 class="text-xl font-semibold mb-2" style="color: var(--text-primary);">No tools yet</h3>
					<p class="text-sm mb-6 max-w-md" style="color: var(--text-muted);">
						Create your first tool to use in LLM and Agent nodes. Tools are Python functions decorated with @tool.
					</p>
					<button
						onclick={openCreateModal}
						class="btn-accent px-5 py-2.5 text-sm font-medium rounded-xl transition-colors flex items-center gap-2 shadow-md"
					>
						<Plus size={16} />
						Create Your First Tool
					</button>
				{:else}
					<h3 class="text-xl font-semibold mb-2" style="color: var(--text-primary);">No matching tools</h3>
					<p class="text-sm" style="color: var(--text-muted);">Try adjusting your search or filters</p>
				{/if}
			</div>
		{:else}
			<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
				{#each toolStore.filteredTools as tool (tool.id)}
					{@const Icon = categoryIcons[tool.category]}
					<div
						class="group bg-surface-elevated rounded-2xl border-2 transition-all duration-200 overflow-hidden hover:-translate-y-1 hover:shadow-card-hover"
						style="border-color: var(--border);"
					>
						<div class="p-5">
							<div class="flex items-start justify-between mb-4">
								<div
									class="w-12 h-12 rounded-xl flex items-center justify-center shadow-sm"
									style="background-color: {getCategoryColor(tool.category)}15"
								>
									<Icon size={22} style="color: {getCategoryColor(tool.category)}" />
								</div>
								<button
									onclick={(e) => showContextMenu(e, tool)}
									class="p-2 rounded-xl hover:bg-surface-hover opacity-0 group-hover:opacity-100 transition-all"
									style="color: var(--text-muted);"
								>
									<MoreVertical size={16} />
								</button>
							</div>
							<h3 class="font-semibold mb-1.5 truncate" style="color: var(--text-primary);">
								{tool.name}
							</h3>
							{#if tool.description}
								<p class="text-sm line-clamp-2 mb-3" style="color: var(--text-muted);">
									{tool.description}
								</p>
							{/if}
							<div class="text-xs font-mono truncate px-2 py-1 rounded-lg bg-surface-secondary" style="color: var(--text-muted);" title={tool.import_path}>
								{tool.import_path}
							</div>
						</div>
						<div class="px-5 py-3 bg-surface-secondary border-t flex items-center justify-between text-xs" style="border-color: var(--border); color: var(--text-muted);">
							<span>{formatDate(tool.updatedAt)}</span>
							<button
								onclick={() => openEditModal(tool)}
								class="text-info hover:underline flex items-center gap-1.5 font-medium"
							>
								<Edit3 size={13} />
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
		class="fixed bg-surface-elevated rounded-xl shadow-dropdown border py-2 z-50 min-w-[180px] animate-scale-in"
		style="left: {contextMenuPosition.x}px; top: {contextMenuPosition.y}px; border-color: var(--border);"
		onclick={(e) => e.stopPropagation()}
	>
		<button
			onclick={() => openEditModal(contextMenuTool!)}
			class="w-full px-4 py-2.5 text-sm text-left hover:bg-surface-hover flex items-center gap-2.5 transition-colors"
			style="color: var(--text-secondary);"
		>
			<Edit3 size={15} />
			Edit
		</button>
		<button
			onclick={handleDuplicate}
			class="w-full px-4 py-2.5 text-sm text-left hover:bg-surface-hover flex items-center gap-2.5 transition-colors"
			style="color: var(--text-secondary);"
		>
			<Copy size={15} />
			Duplicate
		</button>
		<button
			onclick={handleExport}
			class="w-full px-4 py-2.5 text-sm text-left hover:bg-surface-hover flex items-center gap-2.5 transition-colors"
			style="color: var(--text-secondary);"
		>
			<Download size={15} />
			Export
		</button>
		<div class="border-t my-2 mx-3" style="border-color: var(--border);"></div>
		<button
			onclick={handleDelete}
			class="w-full px-4 py-2.5 text-sm text-left text-error hover:bg-error/10 flex items-center gap-2.5 transition-colors"
		>
			<Trash2 size={15} />
			Delete
		</button>
	</div>
{/if}

<!-- Create/Edit Modal -->
{#if showCreateModal}
	<div class="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 animate-fade-in">
		<div class="bg-surface-elevated rounded-2xl shadow-2xl w-full max-w-3xl mx-4 max-h-[85vh] flex flex-col animate-scale-in" style="border: 1px solid var(--border);">
			<!-- Modal Header -->
			<div class="flex items-center justify-between px-6 py-5 border-b" style="border-color: var(--border);">
				<div class="flex items-center gap-3">
					<div class="p-2 rounded-xl bg-gradient-data">
						<Code size={18} class="text-white" />
					</div>
					<h3 class="text-lg font-semibold" style="color: var(--text-primary);">
						{editingTool ? 'Edit Tool' : 'Create Tool'}
					</h3>
				</div>
				<button
					onclick={closeCreateModal}
					class="p-2 rounded-xl hover:bg-surface-hover transition-colors"
					style="color: var(--text-muted);"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Modal Body - Form Fields (non-scrolling for dropdown to work) -->
			<div class="flex-shrink-0 px-6 pt-6 pb-4">
				<div class="grid grid-cols-2 gap-5 mb-5">
					<div>
						<label class="block text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">
							Name *
						</label>
						<input
							type="text"
							bind:value={formName}
							placeholder="My Search Tool"
							class="w-full px-4 py-2.5 text-sm rounded-xl bg-surface-secondary focus:outline-none focus:ring-2 focus:ring-info/50 transition-shadow"
							style="color: var(--text-primary); border: 1px solid var(--border);"
						/>
					</div>
					<div class="relative z-10">
						<label class="block text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">
							Category
						</label>
						<CustomSelect
							options={TOOL_CATEGORIES.map(c => ({ value: c.value, label: c.label }))}
							bind:value={formCategory}
							placeholder="Select category"
							searchable={false}
						/>
					</div>
				</div>

				<div class="grid grid-cols-2 gap-5">
					<div>
						<label class="block text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">
							Description
						</label>
						<input
							type="text"
							bind:value={formDescription}
							placeholder="A tool that searches for information..."
							class="w-full px-4 py-2.5 text-sm rounded-xl bg-surface-secondary focus:outline-none focus:ring-2 focus:ring-info/50 transition-shadow"
							style="color: var(--text-primary); border: 1px solid var(--border);"
						/>
					</div>
					<div>
						<label class="block text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">
							Import Path *
						</label>
						<input
							type="text"
							bind:value={formImportPath}
							placeholder="mypackage.tools.search_tool"
							class="w-full px-4 py-2.5 text-sm font-mono rounded-xl bg-surface-secondary focus:outline-none focus:ring-2 focus:ring-info/50 transition-shadow"
							style="color: var(--text-primary); border: 1px solid var(--border);"
						/>
					</div>
				</div>
			</div>

			<!-- Modal Body - Code Editor (scrollable if needed) -->
			<div class="flex-1 min-h-0 px-6 pb-6">
				<label class="block text-xs font-semibold uppercase tracking-wider mb-2" style="color: var(--text-muted);">
					Code
				</label>
				<div class="h-64 rounded-xl overflow-hidden" style="border: 1px solid var(--border);">
					<MonacoEditor
						bind:value={formCode}
						language="python"
					/>
				</div>
				<p class="text-xs mt-2" style="color: var(--text-muted);">
					Define your tool using the <code class="px-1.5 py-0.5 bg-surface-secondary rounded-lg font-mono">@tool</code> decorator from langchain
				</p>
			</div>

			<!-- Modal Footer -->
			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t bg-surface-secondary rounded-b-2xl" style="border-color: var(--border);">
				<button
					onclick={closeCreateModal}
					class="px-5 py-2.5 text-sm font-medium rounded-xl hover:bg-surface-hover transition-colors"
					style="color: var(--text-secondary);"
				>
					Cancel
				</button>
				<button
					onclick={saveTool}
					disabled={!formName.trim() || !formImportPath.trim()}
					class="btn-accent px-5 py-2.5 disabled:opacity-50 text-sm font-medium rounded-xl transition-colors flex items-center gap-2 shadow-md"
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
		confirmClass="bg-error hover:bg-error/90"
		onconfirm={confirmDelete}
		oncancel={() => { showDeleteConfirm = false; toolToDelete = null; }}
	/>
{/if}
