<script lang="ts">
	import { workflowStore, uiStore } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		Search, RefreshCw, GitBranch, ChevronDown, ArrowUpDown, Plus,
		Clock, Layers, ArrowRight, Calendar, X, Play, LayoutList, LayoutGrid,
		MoreVertical, Edit, Copy, Trash2, ExternalLink, Pencil, FolderOpen
	} from 'lucide-svelte';
	import ConfirmationModal from '$lib/components/common/ConfirmationModal.svelte';

	let workflows = $derived(workflowStore.workflows);
	let currentWorkflow = $derived(workflowStore.currentWorkflow);
	let loading = $derived(workflowStore.loading);

	// Dropdown menu state
	let openMenuId = $state<string | null>(null);

	// Delete confirmation state
	let deleteConfirmation = $state<{ show: boolean; workflow: { id: string; name: string } | null }>({
		show: false,
		workflow: null
	});

	// Rename state
	let renameState = $state<{ show: boolean; workflow: { id: string; name: string } | null; newName: string }>({
		show: false,
		workflow: null,
		newName: ''
	});

	// View mode: list or card (default: card)
	let viewMode = $state<'list' | 'card'>('card');

	// Persist view mode to localStorage
	onMount(() => {
		const saved = localStorage.getItem('workflows-view-mode');
		if (saved === 'list' || saved === 'card') {
			viewMode = saved;
		}
	});

	function setViewMode(mode: 'list' | 'card') {
		viewMode = mode;
		localStorage.setItem('workflows-view-mode', mode);
	}

	// Filters
	let searchQuery = $state('');
	let sortField = $state<'name' | 'node_count' | 'edge_count'>('name');
	let sortDirection = $state<'asc' | 'desc'>('asc');

	// Check if any filter is active
	let hasActiveFilters = $derived(searchQuery !== '');

	// Filtered and sorted workflows
	let filteredWorkflows = $derived(() => {
		let result = [...workflows];

		// Filter by search
		if (searchQuery) {
			const query = searchQuery.toLowerCase();
			result = result.filter(w =>
				w.name.toLowerCase().includes(query) ||
				w.id.toLowerCase().includes(query)
			);
		}

		// Sort
		result.sort((a, b) => {
			let comparison = 0;
			switch (sortField) {
				case 'name':
					comparison = a.name.localeCompare(b.name);
					break;
				case 'node_count':
					comparison = a.node_count - b.node_count;
					break;
				case 'edge_count':
					comparison = a.edge_count - b.edge_count;
					break;
			}
			return sortDirection === 'asc' ? comparison : -comparison;
		});

		return result;
	});

	function toggleSort(field: typeof sortField) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function clearFilters() {
		searchQuery = '';
	}

	async function refresh() {
		await workflowStore.loadWorkflows();
	}

	async function selectWorkflow(id: string) {
		await workflowStore.loadWorkflow(id);
		uiStore.setView('workflow');
		// Update URL
		const url = new URL(window.location.href);
		url.searchParams.set('workflow', id);
		url.searchParams.delete('view');
		pushState(url.toString(), {});
	}

	function createNewWorkflow() {
		workflowStore.createNewWorkflow();
		uiStore.setView('builder');
		// Update URL
		const url = new URL(window.location.href);
		url.searchParams.set('view', 'builder');
		url.searchParams.delete('workflow');
		pushState(url.toString(), {});
	}

	// Menu actions
	function toggleMenu(e: MouseEvent, workflowId: string) {
		e.stopPropagation();
		openMenuId = openMenuId === workflowId ? null : workflowId;
	}

	function closeMenu() {
		openMenuId = null;
	}

	function handleEditInBuilder(e: MouseEvent, workflowId: string) {
		e.stopPropagation();
		closeMenu();
		workflowStore.loadWorkflow(workflowId).then(() => {
			uiStore.setView('builder');
			const url = new URL(window.location.href);
			url.searchParams.set('view', 'builder');
			url.searchParams.set('workflow', workflowId);
			pushState(url.toString(), {});
		});
	}

	async function handleDuplicate(e: MouseEvent, workflow: { id: string; name: string }) {
		e.stopPropagation();
		closeMenu();

		// Load the full workflow data
		const fullWorkflow = await workflowStore.loadWorkflow(workflow.id);
		if (!fullWorkflow) {
			console.error('Failed to load workflow for duplication');
			return;
		}

		// Create a duplicate with new ID and modified name
		const newId = `new_${Date.now()}`;
		const newName = `${workflow.name} (Copy)`;

		// Deep clone the workflow data
		const duplicatedWorkflow = {
			...JSON.parse(JSON.stringify(fullWorkflow)),
			id: newId,
			name: newName,
			source_path: '' // Clear source path since it's a new workflow
		};

		// Update node IDs to avoid conflicts (optional, but cleaner)
		// Keep START and END as-is, but we could rename others if needed

		// Set as current workflow and open in builder
		workflowStore.setCurrentWorkflow(duplicatedWorkflow);
		uiStore.setView('builder');

		// Update URL
		const url = new URL(window.location.href);
		url.searchParams.set('view', 'builder');
		url.searchParams.delete('workflow');
		pushState(url.toString(), {});
	}

	function handleRename(e: MouseEvent, workflow: { id: string; name: string }) {
		e.stopPropagation();
		closeMenu();
		renameState = { show: true, workflow, newName: workflow.name };
	}

	async function confirmRename() {
		if (renameState.workflow && renameState.newName.trim()) {
			const success = await workflowStore.renameWorkflow(renameState.workflow.id, renameState.newName.trim());
			if (!success) {
				alert(`Failed to rename workflow: ${workflowStore.error || 'Unknown error'}`);
			}
		}
		renameState = { show: false, workflow: null, newName: '' };
	}

	function cancelRename() {
		renameState = { show: false, workflow: null, newName: '' };
	}

	function handleDelete(e: MouseEvent, workflow: { id: string; name: string }) {
		e.stopPropagation();
		closeMenu();
		deleteConfirmation = { show: true, workflow };
	}

	async function confirmDelete() {
		if (deleteConfirmation.workflow) {
			const success = await workflowStore.deleteWorkflow(deleteConfirmation.workflow.id);
			if (!success) {
				alert(`Failed to delete workflow: ${workflowStore.error || 'Unknown error'}`);
			}
		}
		deleteConfirmation = { show: false, workflow: null };
	}

	function cancelDelete() {
		deleteConfirmation = { show: false, workflow: null };
	}

	// Close menu when clicking outside
	function handleWindowClick() {
		if (openMenuId) {
			closeMenu();
		}
	}
</script>

<svelte:window onclick={handleWindowClick} />

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Workflows</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{filteredWorkflows().length} of {workflows.length} workflows
				</p>
			</div>
			<div class="flex items-center gap-3">
				<button
					onclick={refresh}
					disabled={loading}
					class="flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
				>
					<RefreshCw size={16} class={loading ? 'animate-spin' : ''} />
					Refresh
				</button>
				<button
					onclick={createNewWorkflow}
					class="flex items-center gap-2 px-4 py-2 bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-lg transition-colors font-medium"
				>
					<Plus size={16} />
					Create Workflow
				</button>
			</div>
		</div>

		<!-- View Toggle and Filters Row -->
		<div class="flex items-center justify-between gap-4">
			<!-- Filters -->
		<div class="flex flex-wrap items-center gap-3">
			<!-- Search -->
			<div class="relative flex-1 min-w-64 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
				<input
					type="text"
					placeholder="Search by workflow name or ID..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] text-sm"
				/>
			</div>

			<!-- Clear filters -->
			{#if hasActiveFilters}
				<button
					onclick={clearFilters}
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					<X size={14} />
					Clear filters
				</button>
			{/if}
		</div>

			<!-- View Mode Toggle -->
			<div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
				<button
					onclick={() => setViewMode('card')}
					class="p-2 rounded-md transition-colors {viewMode === 'card' ? 'bg-white dark:bg-gray-700 text-[#7661FF] dark:text-[#52B8FF] shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
					title="Card view"
				>
					<LayoutGrid size={18} />
				</button>
				<button
					onclick={() => setViewMode('list')}
					class="p-2 rounded-md transition-colors {viewMode === 'list' ? 'bg-white dark:bg-gray-700 text-[#7661FF] dark:text-[#52B8FF] shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
					title="List view"
				>
					<LayoutList size={18} />
				</button>
			</div>
		</div>
	</div>

	<!-- Content Area -->
	<div class="flex-1 overflow-auto">
		{#if viewMode === 'list'}
			<!-- List View -->
			<table class="w-full">
				<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
					<tr>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('name')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Workflow
								<ArrowUpDown size={14} class={sortField === 'name' ? 'text-[#7661FF]' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('node_count')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Nodes
								<ArrowUpDown size={14} class={sortField === 'node_count' ? 'text-[#7661FF]' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('edge_count')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Edges
								<ArrowUpDown size={14} class={sortField === 'edge_count' ? 'text-[#7661FF]' : ''} />
							</button>
						</th>
						<th class="text-right px-6 py-3">
							<span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								Actions
							</span>
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 dark:divide-gray-800">
					{#each filteredWorkflows() as workflow (workflow.id)}
						<tr
							onclick={() => selectWorkflow(workflow.id)}
							class="cursor-pointer transition-colors {currentWorkflow?.id === workflow.id ? 'bg-[#032D42]/10 dark:bg-[#52B8FF]/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800'}"
						>
							<td class="px-6 py-4">
								<div class="flex items-center gap-3">
									<div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background: radial-gradient(ellipse at 70% 20%, rgba(191, 113, 242, 0.6) 0%, transparent 60%), #7661FF;">
										<FolderOpen size={20} class="text-white" />
									</div>
									<div class="flex flex-col">
										<span class="font-medium text-gray-900 dark:text-gray-100">
											{workflow.name}
										</span>
										<span class="text-xs text-gray-500 dark:text-gray-500 font-mono">
											{workflow.id}
										</span>
									</div>
								</div>
							</td>
							<td class="px-6 py-4">
								<span class="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
									<Layers size={14} class="text-[#032D42] dark:text-[#52B8FF]" />
									{workflow.node_count} nodes
								</span>
							</td>
							<td class="px-6 py-4">
								<span class="inline-flex items-center gap-1.5 text-sm text-gray-700 dark:text-gray-300">
									<ArrowRight size={14} class="text-blue-500" />
									{workflow.edge_count} edges
								</span>
							</td>
							<td class="px-6 py-4 text-right">
								<div class="flex items-center justify-end gap-2">
									<button
										onclick={(e) => { e.stopPropagation(); selectWorkflow(workflow.id); }}
										class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-[#032D42] dark:text-[#52B8FF] hover:bg-[#032D42]/10 dark:hover:bg-[#52B8FF]/20 rounded-lg transition-colors"
									>
										<Play size={14} />
										Open
									</button>
									<!-- Three-dot menu -->
									<div class="relative">
										<button
											onclick={(e) => toggleMenu(e, workflow.id)}
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
											title="More options"
										>
											<MoreVertical size={16} />
										</button>
										{#if openMenuId === workflow.id}
											<div class="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
												<button
													onclick={(e) => handleEditInBuilder(e, workflow.id)}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
												>
													<Edit size={14} />
													Edit in Builder
												</button>
												<button
													onclick={(e) => handleDuplicate(e, workflow)}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
												>
													<Copy size={14} />
													Duplicate
												</button>
												<button
													onclick={(e) => handleRename(e, workflow)}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
												>
													<Pencil size={14} />
													Rename
												</button>
												<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>
												<button
													onclick={(e) => handleDelete(e, workflow)}
													class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
												>
													<Trash2 size={14} />
													Delete
												</button>
											</div>
										{/if}
									</div>
								</div>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="4" class="px-6 py-12 text-center">
								<div class="text-gray-500 dark:text-gray-400">
									{#if searchQuery}
										<p class="text-lg font-medium mb-1">No matching workflows</p>
										<p class="text-sm">Try adjusting your search</p>
									{:else}
										<div class="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style="background: radial-gradient(ellipse at 70% 20%, rgba(191, 113, 242, 0.6) 0%, transparent 60%), #7661FF;">
											<FolderOpen size={32} class="text-white" />
										</div>
										<p class="text-lg font-medium mb-1">No workflows yet</p>
										<p class="text-sm mb-4">Create your first workflow to get started</p>
										<button
											onclick={createNewWorkflow}
											class="inline-flex items-center gap-2 px-4 py-2 bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-lg transition-colors font-medium"
										>
											<Plus size={16} />
											Create Workflow
										</button>
									{/if}
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<!-- Card View -->
			<div class="p-6">
				{#if filteredWorkflows().length === 0}
					<div class="text-center py-12 text-gray-500 dark:text-gray-400">
						{#if searchQuery}
							<p class="text-lg font-medium mb-1">No matching workflows</p>
							<p class="text-sm">Try adjusting your search</p>
						{:else}
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style="background: radial-gradient(ellipse at 70% 20%, rgba(191, 113, 242, 0.6) 0%, transparent 60%), #7661FF;">
								<FolderOpen size={32} class="text-white" />
							</div>
							<p class="text-lg font-medium mb-1">No workflows yet</p>
							<p class="text-sm mb-4">Create your first workflow to get started</p>
							<button
								onclick={createNewWorkflow}
								class="inline-flex items-center gap-2 px-4 py-2 bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-lg transition-colors font-medium"
							>
								<Plus size={16} />
								Create Workflow
							</button>
						{/if}
					</div>
				{:else}
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
						{#each filteredWorkflows() as workflow (workflow.id)}
							<div
								onclick={() => selectWorkflow(workflow.id)}
								class="group relative bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 cursor-pointer transition-all hover:shadow-lg hover:border-[#7661FF]/50 dark:hover:border-[#52B8FF] {currentWorkflow?.id === workflow.id ? 'ring-2 ring-[#7661FF] border-[#7661FF]' : ''}"
							>
								<!-- Three-dot menu (top-right) -->
								<div class="absolute top-3 right-3">
									<button
										onclick={(e) => toggleMenu(e, workflow.id)}
										class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors opacity-0 group-hover:opacity-100"
										title="More options"
									>
										<MoreVertical size={16} />
									</button>
									{#if openMenuId === workflow.id}
										<div class="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 z-50">
											<button
												onclick={(e) => handleEditInBuilder(e, workflow.id)}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
											>
												<Edit size={14} />
												Edit in Builder
											</button>
											<button
												onclick={(e) => handleDuplicate(e, workflow)}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
											>
												<Copy size={14} />
												Duplicate
											</button>
											<button
												onclick={(e) => handleRename(e, workflow)}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
											>
												<Pencil size={14} />
												Rename
											</button>
											<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>
											<button
												onclick={(e) => handleDelete(e, workflow)}
												class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
											>
												<Trash2 size={14} />
												Delete
											</button>
										</div>
									{/if}
								</div>

								<!-- Header -->
								<div class="flex items-start gap-3 mb-4">
									<div class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md" style="background: radial-gradient(ellipse at 70% 20%, rgba(191, 113, 242, 0.6) 0%, transparent 60%), #7661FF;">
										<FolderOpen size={24} class="text-white" />
									</div>
									<div class="flex-1 min-w-0 pr-6">
										<h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate group-hover:text-[#032D42] dark:group-hover:text-[#52B8FF] transition-colors">
											{workflow.name}
										</h3>
										<p class="text-xs text-gray-500 dark:text-gray-500 font-mono truncate mt-0.5">
											{workflow.id}
										</p>
									</div>
								</div>

								<!-- Stats -->
								<div class="flex items-center gap-4 mb-4">
									<div class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
										<Layers size={14} class="text-[#032D42] dark:text-[#52B8FF]" />
										<span>{workflow.node_count} nodes</span>
									</div>
									<div class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
										<ArrowRight size={14} class="text-[#52B8FF]" />
										<span>{workflow.edge_count} edges</span>
									</div>
								</div>

								<!-- Action Button -->
								<button
									onclick={(e) => { e.stopPropagation(); selectWorkflow(workflow.id); }}
									class="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-[#032D42] dark:text-[#52B8FF] bg-[#032D42]/10 dark:bg-[#52B8FF]/20 hover:bg-[#032D42]/20 dark:hover:bg-[#52B8FF]/30 rounded-lg transition-colors"
								>
									<Play size={14} />
									Open Workflow
								</button>

								<!-- Selected indicator -->
								{#if currentWorkflow?.id === workflow.id}
									<div class="absolute -top-1 -right-1 w-4 h-4 bg-[#63DF4E] rounded-full border-2 border-white dark:border-gray-800"></div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

<!-- Delete Confirmation Modal -->
{#if deleteConfirmation.show && deleteConfirmation.workflow}
	<ConfirmationModal
		title="Delete Workflow"
		message="Are you sure you want to delete '{deleteConfirmation.workflow.name}'? This action cannot be undone."
		confirmText="Delete"
		cancelText="Cancel"
		variant="danger"
		icon="trash"
		on:confirm={confirmDelete}
		on:cancel={cancelDelete}
	/>
{/if}

<!-- Rename Modal -->
{#if renameState.show && renameState.workflow}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
		onclick={cancelRename}
		role="presentation"
	>
		<div
			class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 p-6"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-labelledby="rename-title"
		>
			<h3 id="rename-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
				Rename Workflow
			</h3>
			<input
				type="text"
				bind:value={renameState.newName}
				class="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] mb-4"
				placeholder="Enter new name..."
				onkeydown={(e) => e.key === 'Enter' && confirmRename()}
			/>
			<div class="flex justify-end gap-3">
				<button
					onclick={cancelRename}
					class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					Cancel
				</button>
				<button
					onclick={confirmRename}
					disabled={!renameState.newName.trim()}
					class="px-4 py-2 text-sm font-medium bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				>
					Rename
				</button>
			</div>
		</div>
	</div>
{/if}
