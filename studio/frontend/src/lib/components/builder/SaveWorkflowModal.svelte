<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { X, FolderOpen, Save, AlertCircle, ChevronDown, ChevronRight } from 'lucide-svelte';

	interface Props {
		workflowName: string;
		isOpen: boolean;
	}

	let { workflowName, isOpen }: Props = $props();

	const dispatch = createEventDispatcher<{
		save: { path: string; filename: string };
		close: void;
	}>();

	// State
	let tasksDir = $state('');
	let taskName = $state('');
	let isLoadingConfig = $state(true);
	let isSaving = $state(false);
	let error = $state<string | null>(null);
	let subdirectories = $state<string[]>([]);
	let showDirectoryPicker = $state(false);

	// Normalize task name: lowercase, replace spaces/special chars with underscores
	function normalizeTaskName(name: string): string {
		return name
			.toLowerCase()
			.trim()
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_+|_+$/g, '')
			.replace(/_+/g, '_');
	}

	// Derived normalized name for preview
	let normalizedName = $derived(normalizeTaskName(taskName));

	// Sync task name from workflow name when modal opens (pre-normalized)
	$effect(() => {
		if (isOpen) {
			// Show the normalized version so user sees the actual folder name that will be created
			taskName = normalizeTaskName(workflowName || '') || '';
		}
	});

	// Fetch tasks-dir from backend config
	onMount(async () => {
		await loadConfig();
	});

	async function loadConfig() {
		isLoadingConfig = true;
		try {
			const response = await fetch('/api/config');
			if (response.ok) {
				const config = await response.json();
				tasksDir = config.tasks_dir || './tasks';
				subdirectories = config.subdirectories || [];
			} else {
				console.error('Config API returned:', response.status);
				tasksDir = './tasks';
			}
		} catch (e) {
			console.error('Failed to fetch config:', e);
			tasksDir = './tasks';
		} finally {
			isLoadingConfig = false;
		}
	}

	function selectDirectory(dir: string) {
		tasksDir = dir;
		showDirectoryPicker = false;
	}

	function handleClose() {
		dispatch('close');
	}

	async function handleSave() {
		if (!tasksDir.trim() || !taskName.trim()) {
			error = 'Please provide a task name';
			return;
		}

		const normalized = normalizeTaskName(taskName);
		if (!normalized) {
			error = 'Invalid task name. Please use letters, numbers, or spaces.';
			return;
		}

		error = null;
		isSaving = true;

		try {
			dispatch('save', {
				path: tasksDir.trim(),
				filename: normalized  // Just the task name, backend handles the rest
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save workflow';
			isSaving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleClose();
		} else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
			handleSave();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<!-- Backdrop -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
		onclick={handleClose}
		role="presentation"
	>
		<!-- Modal -->
		<div
			class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
			aria-modal="true"
			aria-labelledby="save-modal-title"
		>
			<!-- Header -->
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
				<h2 id="save-modal-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					Save Workflow
				</h2>
				<button
					onclick={handleClose}
					class="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Content -->
			<div class="px-6 py-5 space-y-5">
				{#if isLoadingConfig}
					<div class="flex items-center justify-center py-8">
						<div class="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin"></div>
						<span class="ml-3 text-gray-500">Loading configuration...</span>
					</div>
				{:else}
					<!-- Task Name -->
					<div>
						<label for="task-name" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
							Task Name
						</label>
						<input
							id="task-name"
							type="text"
							bind:value={taskName}
							placeholder="my_workflow"
							class="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-colors"
						/>
					</div>

					<!-- Tasks Directory -->
					<div>
						<label for="tasks-dir" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
							Tasks Directory
						</label>
						<div class="relative">
							<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 z-10">
								<FolderOpen size={18} />
							</span>
							<input
								id="tasks-dir"
								type="text"
								bind:value={tasksDir}
								placeholder="./tasks"
								class="w-full pl-10 pr-12 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-colors"
							/>
							<!-- Directory picker button -->
							{#if subdirectories.length > 0}
								<button
									type="button"
									onclick={() => showDirectoryPicker = !showDirectoryPicker}
									class="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
									title="Browse directories"
								>
									{#if showDirectoryPicker}
										<ChevronDown size={18} />
									{:else}
										<ChevronRight size={18} />
									{/if}
								</button>
							{/if}
						</div>

						<!-- Directory dropdown -->
						{#if showDirectoryPicker && subdirectories.length > 0}
							<div class="mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-48 overflow-y-auto">
								{#each subdirectories as dir}
									<button
										type="button"
										onclick={() => selectDirectory(dir)}
										class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
										class:bg-violet-50={tasksDir === dir}
										class:dark:bg-violet-900={tasksDir === dir}
									>
										<FolderOpen size={14} class="text-gray-400" />
										<span class="text-gray-700 dark:text-gray-300 truncate">{dir}</span>
									</button>
								{/each}
							</div>
						{/if}
					</div>

					<!-- Error message -->
					{#if error}
						<div class="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
							<AlertCircle size={18} class="text-red-500 flex-shrink-0" />
							<p class="text-sm text-red-600 dark:text-red-400">{error}</p>
						</div>
					{/if}
				{/if}
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-200 dark:border-gray-700">
				<button
					onclick={handleClose}
					class="px-4 py-2 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					Cancel
				</button>
				<button
					onclick={handleSave}
					disabled={isSaving || isLoadingConfig || !normalizedName}
					class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
				>
					{#if isSaving}
						<div class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
					{:else}
						<Save size={16} />
					{/if}
					Save Workflow
				</button>
			</div>
		</div>
	</div>
{/if}
