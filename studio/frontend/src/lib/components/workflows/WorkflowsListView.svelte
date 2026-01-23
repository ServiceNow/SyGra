<script lang="ts">
	import { workflowStore, uiStore } from '$lib/stores/workflow.svelte';
	import { pushState } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		Search, RefreshCw, ChevronDown, ArrowUpDown, Plus,
		Layers, ArrowRight, X, Play, LayoutList, LayoutGrid,
		MoreVertical, Edit, Copy, Trash2, Pencil, FolderOpen, Workflow
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
		const url = new URL(window.location.href);
		url.searchParams.set('workflow', id);
		url.searchParams.delete('view');
		pushState(url.toString(), {});
	}

	function createNewWorkflow() {
		workflowStore.createNewWorkflow();
		uiStore.setView('builder');
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

		const fullWorkflow = await workflowStore.loadWorkflow(workflow.id);
		if (!fullWorkflow) {
			console.error('Failed to load workflow for duplication');
			return;
		}

		const newId = `new_${Date.now()}`;
		const newName = `${workflow.name} (Copy)`;

		const duplicatedWorkflow = {
			...JSON.parse(JSON.stringify(fullWorkflow)),
			id: newId,
			name: newName,
			source_path: ''
		};

		workflowStore.setCurrentWorkflow(duplicatedWorkflow);
		uiStore.setView('builder');

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

	function handleWindowClick() {
		if (openMenuId) {
			closeMenu();
		}
	}
</script>

<svelte:window onclick={handleWindowClick} />

<div class="h-full w-full flex flex-col bg-surface-secondary">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-[var(--border)] bg-surface-elevated px-6 py-5">
		<div class="flex items-center justify-between mb-5">
			<div class="flex items-center gap-4">
				<div class="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm bg-gradient-data">
					<FolderOpen size={20} class="text-white" />
				</div>
				<div>
					<h1 class="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Workflows</h1>
					<p class="text-sm text-[var(--text-muted)]">
						{filteredWorkflows().length} of {workflows.length} workflows
					</p>
				</div>
			</div>
			<div class="flex items-center gap-3">
				<button
					onclick={refresh}
					disabled={loading}
					class="flex items-center gap-2 px-4 py-2.5 border border-[var(--border)] hover:bg-surface-hover hover:border-[var(--border-hover)] rounded-xl transition-all duration-200 disabled:opacity-50 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
				>
					<RefreshCw size={16} class={loading ? 'animate-spin' : ''} />
					<span class="text-sm font-medium">Refresh</span>
				</button>
				<button
					onclick={createNewWorkflow}
					class="flex items-center gap-2 px-4 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 font-semibold shadow-sm hover:shadow-glow-accent hover:-translate-y-0.5"
				>
					<Plus size={16} strokeWidth={2.5} />
					<span class="text-sm">Create Workflow</span>
				</button>
			</div>
		</div>

		<!-- View Toggle and Filters Row -->
		<div class="flex items-center justify-between gap-4">
			<!-- Filters -->
			<div class="flex flex-wrap items-center gap-3">
				<!-- Search -->
				<div class="relative flex-1 min-w-64 max-w-md">
					<Search size={16} class="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
					<input
						type="text"
						placeholder="Search by workflow name or ID..."
						bind:value={searchQuery}
						class="w-full pl-10 pr-4 py-2.5 border border-[var(--border)] rounded-xl bg-surface text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)] text-sm transition-all duration-200"
					/>
				</div>

				<!-- Clear filters -->
				{#if hasActiveFilters}
					<button
						onclick={clearFilters}
						class="flex items-center gap-1.5 px-3 py-2.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-surface-hover rounded-xl transition-all duration-200"
					>
						<X size={14} />
						Clear filters
					</button>
				{/if}
			</div>

			<!-- View Mode Toggle -->
			<div class="flex items-center bg-surface-tertiary rounded-xl p-1">
				<button
					onclick={() => setViewMode('card')}
					class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'card' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
					title="Card view"
				>
					<LayoutGrid size={18} />
				</button>
				<button
					onclick={() => setViewMode('list')}
					class="p-2.5 rounded-lg transition-all duration-200 {viewMode === 'list' ? 'bg-surface-elevated text-info shadow-sm' : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'}"
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
				<thead class="sticky top-0 bg-surface-secondary border-b border-[var(--border)] z-10">
					<tr>
						<th class="text-left px-6 py-4">
							<button
								onclick={() => toggleSort('name')}
								class="flex items-center gap-1 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider hover:text-[var(--text-primary)] transition-colors duration-200"
							>
								Workflow
								<ArrowUpDown size={14} class={sortField === 'name' ? 'text-info' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-4">
							<button
								onclick={() => toggleSort('node_count')}
								class="flex items-center gap-1 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider hover:text-[var(--text-primary)] transition-colors duration-200"
							>
								Nodes
								<ArrowUpDown size={14} class={sortField === 'node_count' ? 'text-info' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-4">
							<button
								onclick={() => toggleSort('edge_count')}
								class="flex items-center gap-1 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider hover:text-[var(--text-primary)] transition-colors duration-200"
							>
								Edges
								<ArrowUpDown size={14} class={sortField === 'edge_count' ? 'text-info' : ''} />
							</button>
						</th>
						<th class="text-right px-6 py-4">
							<span class="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
								Actions
							</span>
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-[var(--border)]">
					{#each filteredWorkflows() as workflow, i (workflow.id)}
						<tr
							onclick={() => selectWorkflow(workflow.id)}
							class="group cursor-pointer transition-all duration-200 bg-surface-elevated hover:bg-surface-hover {currentWorkflow?.id === workflow.id ? 'ring-2 ring-inset ring-info/50' : ''}"
						>
							<td class="px-6 py-4">
								<div class="flex items-center gap-4">
									<div class="w-11 h-11 rounded-xl flex items-center justify-center shadow-sm transition-transform duration-200 group-hover:scale-105 bg-gradient-data">
										<Workflow size={20} class="text-white" />
									</div>
									<div class="flex flex-col">
										<span class="font-semibold text-[var(--text-primary)] group-hover:text-info transition-colors duration-200">
											{workflow.name}
										</span>
										<span class="text-xs text-[var(--text-muted)] font-mono mt-0.5">
											{workflow.id}
										</span>
									</div>
								</div>
							</td>
							<td class="px-6 py-4">
								<span class="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
									<Layers size={15} class="text-node-llm" />
									{workflow.node_count} nodes
								</span>
							</td>
							<td class="px-6 py-4">
								<span class="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)]">
									<ArrowRight size={15} class="text-info" />
									{workflow.edge_count} edges
								</span>
							</td>
							<td class="px-6 py-4 text-right">
								<div class="flex items-center justify-end gap-2">
									<button
										onclick={(e) => { e.stopPropagation(); selectWorkflow(workflow.id); }}
										class="inline-flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-info bg-info-light hover:bg-[rgba(82,184,255,0.2)] rounded-lg transition-all duration-200"
									>
										<Play size={14} />
										Open
									</button>
									<!-- Three-dot menu -->
									<div class="relative">
										<button
											onclick={(e) => toggleMenu(e, workflow.id)}
											class="p-2 rounded-lg hover:bg-surface-tertiary text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all duration-200"
											title="More options"
										>
											<MoreVertical size={16} />
										</button>
										{#if openMenuId === workflow.id}
											<div class="absolute right-0 top-full mt-1 w-48 bg-surface-elevated rounded-xl shadow-dropdown border border-[var(--border)] py-1.5 z-50 animate-scale-in">
												<button
													onclick={(e) => handleEditInBuilder(e, workflow.id)}
													class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
												>
													<Edit size={14} />
													Edit in Builder
												</button>
												<button
													onclick={(e) => handleDuplicate(e, workflow)}
													class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
												>
													<Copy size={14} />
													Duplicate
												</button>
												<button
													onclick={(e) => handleRename(e, workflow)}
													class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
												>
													<Pencil size={14} />
													Rename
												</button>
												<div class="h-px bg-[var(--border)] my-1.5 mx-2"></div>
												<button
													onclick={(e) => handleDelete(e, workflow)}
													class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-error hover:bg-error-light transition-colors duration-150"
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
							<td colspan="4" class="px-6 py-16 text-center">
								<div class="text-[var(--text-secondary)]">
									{#if searchQuery}
										<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
											<Search size={28} class="text-[var(--text-muted)]" />
										</div>
										<p class="text-lg font-medium text-[var(--text-primary)] mb-1">No matching workflows</p>
										<p class="text-sm text-[var(--text-muted)]">Try adjusting your search</p>
									{:else}
										<div class="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center shadow-md bg-gradient-data">
											<FolderOpen size={28} class="text-white" />
										</div>
										<p class="text-lg font-medium text-[var(--text-primary)] mb-1">No workflows yet</p>
										<p class="text-sm text-[var(--text-muted)] mb-5">Create your first workflow to get started</p>
										<button
											onclick={createNewWorkflow}
											class="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 font-semibold shadow-sm hover:shadow-glow-accent"
										>
											<Plus size={16} strokeWidth={2.5} />
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
					<div class="text-center py-16 text-[var(--text-secondary)]">
						{#if searchQuery}
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-tertiary flex items-center justify-center">
								<Search size={28} class="text-[var(--text-muted)]" />
							</div>
							<p class="text-lg font-medium text-[var(--text-primary)] mb-1">No matching workflows</p>
							<p class="text-sm text-[var(--text-muted)]">Try adjusting your search</p>
						{:else}
							<div class="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center shadow-md bg-gradient-data">
								<FolderOpen size={28} class="text-white" />
							</div>
							<p class="text-lg font-medium text-[var(--text-primary)] mb-1">No workflows yet</p>
							<p class="text-sm text-[var(--text-muted)] mb-5">Create your first workflow to get started</p>
							<button
								onclick={createNewWorkflow}
								class="inline-flex items-center gap-2 px-5 py-2.5 bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 font-semibold shadow-sm hover:shadow-glow-accent"
							>
								<Plus size={16} strokeWidth={2.5} />
								Create Workflow
							</button>
						{/if}
					</div>
				{:else}
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
						{#each filteredWorkflows() as workflow, i (workflow.id)}
							<div
								onclick={() => selectWorkflow(workflow.id)}
								class="group relative bg-surface-elevated border border-[var(--border)] rounded-2xl p-5 cursor-pointer transition-all duration-300 hover:shadow-card-hover hover:border-[var(--border-focus)] hover:-translate-y-1 {currentWorkflow?.id === workflow.id ? 'ring-2 ring-info border-info' : ''} {openMenuId === workflow.id ? 'z-10' : ''}"
							>
								<!-- Three-dot menu (top-right) -->
								<div class="absolute top-4 right-4">
									<button
										onclick={(e) => toggleMenu(e, workflow.id)}
										class="p-1.5 rounded-lg hover:bg-surface-hover text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-all duration-200 opacity-0 group-hover:opacity-100"
										title="More options"
									>
										<MoreVertical size={16} />
									</button>
									{#if openMenuId === workflow.id}
										<div class="absolute right-0 top-full mt-1 w-48 bg-surface-elevated rounded-xl shadow-dropdown border border-[var(--border)] py-1.5 z-50 animate-scale-in">
											<button
												onclick={(e) => handleEditInBuilder(e, workflow.id)}
												class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
											>
												<Edit size={14} />
												Edit in Builder
											</button>
											<button
												onclick={(e) => handleDuplicate(e, workflow)}
												class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
											>
												<Copy size={14} />
												Duplicate
											</button>
											<button
												onclick={(e) => handleRename(e, workflow)}
												class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-[var(--text-secondary)] hover:bg-surface-hover hover:text-[var(--text-primary)] transition-colors duration-150"
											>
												<Pencil size={14} />
												Rename
											</button>
											<div class="h-px bg-[var(--border)] my-1.5 mx-2"></div>
											<button
												onclick={(e) => handleDelete(e, workflow)}
												class="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-error hover:bg-error-light transition-colors duration-150"
											>
												<Trash2 size={14} />
												Delete
											</button>
										</div>
									{/if}
								</div>

								<!-- Header -->
								<div class="flex items-start gap-4 mb-5">
									<div class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md transition-transform duration-200 group-hover:scale-105 bg-gradient-data">
										<Workflow size={22} class="text-white" />
									</div>
									<div class="flex-1 min-w-0 pr-8">
										<h3 class="font-semibold text-[var(--text-primary)] truncate group-hover:text-info transition-colors duration-200">
											{workflow.name}
										</h3>
										<p class="text-xs text-[var(--text-muted)] font-mono truncate mt-1">
											{workflow.id}
										</p>
									</div>
								</div>

								<!-- Stats -->
								<div class="flex items-center gap-5 mb-5">
									<div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
										<Layers size={15} class="text-node-llm" />
										<span>{workflow.node_count} nodes</span>
									</div>
									<div class="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
										<ArrowRight size={15} class="text-info" />
										<span>{workflow.edge_count} edges</span>
									</div>
								</div>

								<!-- Action Button -->
								<button
									onclick={(e) => { e.stopPropagation(); selectWorkflow(workflow.id); }}
									class="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium text-info bg-info-light hover:bg-[rgba(82,184,255,0.2)] rounded-xl transition-all duration-200"
								>
									<Play size={14} />
									Open Workflow
								</button>

								<!-- Selected indicator -->
								{#if currentWorkflow?.id === workflow.id}
									<div class="absolute -top-1 -right-1 w-4 h-4 bg-brand-accent rounded-full border-2 border-surface-elevated"></div>
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
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50 animate-fade-in"
		onclick={cancelRename}
		role="presentation"
	>
		<div
			class="bg-surface-elevated rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6 border border-[var(--border)] animate-scale-in"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-labelledby="rename-title"
		>
			<h3 id="rename-title" class="text-lg font-semibold text-[var(--text-primary)] mb-4">
				Rename Workflow
			</h3>
			<input
				type="text"
				bind:value={renameState.newName}
				class="w-full px-4 py-3 border border-[var(--border)] rounded-xl bg-surface text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--border-focus)]/30 focus:border-[var(--border-focus)] mb-5"
				placeholder="Enter new name..."
				onkeydown={(e) => e.key === 'Enter' && confirmRename()}
			/>
			<div class="flex justify-end gap-3">
				<button
					onclick={cancelRename}
					class="px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-surface-hover rounded-xl transition-all duration-200"
				>
					Cancel
				</button>
				<button
					onclick={confirmRename}
					disabled={!renameState.newName.trim()}
					class="px-4 py-2.5 text-sm font-medium bg-brand-accent hover:bg-brand-accent-hover text-brand-primary rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
				>
					Rename
				</button>
			</div>
		</div>
	</div>
{/if}
