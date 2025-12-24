<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { X, FolderOpen, Save, AlertCircle, ChevronDown } from 'lucide-svelte';

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
	let savePath = $state('');
	let filename = $state('');
	let isLoadingConfig = $state(true);
	let isSaving = $state(false);
	let error = $state<string | null>(null);
	let defaultTasksDir = $state('');
	let subdirectories = $state<string[]>([]);
	let showDirectoryPicker = $state(false);

	// Derive filename from workflow name
	$effect(() => {
		if (workflowName && !filename) {
			// Convert workflow name to valid filename
			filename = workflowName
				.toLowerCase()
				.replace(/[^a-z0-9]+/g, '_')
				.replace(/^_|_$/g, '') + '.yaml';
		}
	});

	// Fetch default tasks-dir from backend
	onMount(async () => {
		await loadConfig();
	});

	async function loadConfig() {
		isLoadingConfig = true;
		try {
			const response = await fetch('/api/config');
			if (response.ok) {
				const config = await response.json();
				defaultTasksDir = config.tasks_dir || './tasks';
				subdirectories = config.subdirectories || [];
				// Only set savePath if it's empty (first load)
				if (!savePath) {
					savePath = defaultTasksDir;
				}
			} else {
				console.error('Config API returned:', response.status);
				if (!savePath) {
					savePath = './tasks';
					defaultTasksDir = './tasks';
				}
			}
		} catch (e) {
			console.error('Failed to fetch config:', e);
			if (!savePath) {
				savePath = './tasks';
				defaultTasksDir = './tasks';
			}
		} finally {
			isLoadingConfig = false;
		}
	}

	function selectDirectory(dir: string) {
		savePath = dir;
		showDirectoryPicker = false;
	}

	function handleClose() {
		dispatch('close');
	}

	async function handleSave() {
		if (!savePath.trim() || !filename.trim()) {
			error = 'Please provide both path and filename';
			return;
		}

		// Ensure filename ends with .yaml
		let finalFilename = filename.trim();
		if (!finalFilename.endsWith('.yaml') && !finalFilename.endsWith('.yml')) {
			finalFilename += '.yaml';
		}

		error = null;
		isSaving = true;

		try {
			dispatch('save', {
				path: savePath.trim(),
				filename: finalFilename
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
					<!-- Save Path -->
					<div>
						<label for="save-path" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
							Save Location
						</label>
						<div class="relative">
							<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 z-10">
								<FolderOpen size={18} />
							</span>
							<input
								id="save-path"
								type="text"
								bind:value={savePath}
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
									<ChevronDown size={18} class={showDirectoryPicker ? 'rotate-180 transition-transform' : 'transition-transform'} />
								</button>
							{/if}
						</div>

						<!-- Directory dropdown -->
						{#if showDirectoryPicker && subdirectories.length > 0}
							<div class="mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg max-h-48 overflow-y-auto">
								<!-- Default tasks dir -->
								<button
									type="button"
									onclick={() => selectDirectory(defaultTasksDir)}
									class="w-full px-3 py-2 text-left text-sm hover:bg-violet-50 dark:hover:bg-violet-900/20 flex items-center gap-2 border-b border-gray-100 dark:border-gray-700"
									class:bg-violet-50={savePath === defaultTasksDir}
									class:dark:bg-violet-900={savePath === defaultTasksDir}
								>
									<FolderOpen size={14} class="text-violet-500" />
									<span class="text-gray-700 dark:text-gray-300 truncate">{defaultTasksDir}</span>
									<span class="text-xs text-gray-400 ml-auto">(root)</span>
								</button>
								<!-- Subdirectories -->
								{#each subdirectories as dir}
									<button
										type="button"
										onclick={() => selectDirectory(dir)}
										class="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-gray-700 flex items-center gap-2"
										class:bg-violet-50={savePath === dir}
										class:dark:bg-violet-900={savePath === dir}
									>
										<FolderOpen size={14} class="text-gray-400" />
										<span class="text-gray-700 dark:text-gray-300 truncate">{dir}</span>
									</button>
								{/each}
							</div>
						{/if}

						{#if defaultTasksDir && !showDirectoryPicker}
							<p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
								Server tasks directory: <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">{defaultTasksDir}</code>
							</p>
						{/if}
					</div>

					<!-- Filename -->
					<div>
						<label for="filename" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
							Filename
						</label>
						<input
							id="filename"
							type="text"
							bind:value={filename}
							placeholder="my_workflow.yaml"
							class="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-colors"
						/>
						<p class="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
							Will be saved as: <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">{savePath}/{filename}</code>
						</p>
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
					disabled={isSaving || isLoadingConfig}
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
