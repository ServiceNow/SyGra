<script lang="ts">
	import { onMount } from 'svelte';
	import {
		X, Settings, Plus, Trash2, Eye, EyeOff, RefreshCw, Save,
		AlertCircle, CheckCircle, Key, FileText, Copy, Check,
		Sun, Moon, Monitor, Palette, Sliders, Info
	} from 'lucide-svelte';
	import { themeStore } from '$lib/stores/theme.svelte';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	// Tab state
	type TabId = 'general' | 'appearance' | 'environment';
	let activeTab = $state<TabId>('general');

	const tabs = [
		{ id: 'general' as TabId, label: 'General', icon: Sliders },
		{ id: 'appearance' as TabId, label: 'Appearance', icon: Palette },
		{ id: 'environment' as TabId, label: 'Environment', icon: Key }
	];

	interface EnvVar {
		key: string;
		value: string;
		masked_value: string;
		is_sensitive: boolean;
	}

	let envVars = $state<EnvVar[]>([]);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let success = $state<string | null>(null);
	let envFile = $state('');

	// New variable form
	let newKey = $state('');
	let newValue = $state('');
	let showNewForm = $state(false);

	// Track which values are revealed
	let revealedKeys = $state<Set<string>>(new Set());

	// Track copied keys
	let copiedKey = $state<string | null>(null);

	// Theme
	let currentTheme = $derived(themeStore.theme);
	let isDark = $derived(themeStore.isDark);

	onMount(() => {
		loadEnvVars();
	});

	async function loadEnvVars() {
		loading = true;
		error = null;
		try {
			const response = await fetch('/api/settings/env');
			if (!response.ok) throw new Error('Failed to load environment variables');
			const data = await response.json();
			envVars = data.variables;
			envFile = data.env_file;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	async function addVariable() {
		if (!newKey.trim()) {
			error = 'Variable name is required';
			return;
		}

		saving = true;
		error = null;
		try {
			const response = await fetch('/api/settings/env', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ key: newKey.trim(), value: newValue })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to add variable');
			}

			success = `Variable '${newKey}' added successfully`;
			newKey = '';
			newValue = '';
			showNewForm = false;
			await loadEnvVars();

			setTimeout(() => success = null, 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			saving = false;
		}
	}

	async function updateVariable(key: string, value: string) {
		saving = true;
		error = null;
		try {
			const response = await fetch('/api/settings/env', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ key, value })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to update variable');
			}

			success = `Variable '${key}' updated`;
			await loadEnvVars();

			setTimeout(() => success = null, 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			saving = false;
		}
	}

	async function deleteVariable(key: string) {
		if (!confirm(`Are you sure you want to delete '${key}'?`)) return;

		saving = true;
		error = null;
		try {
			const response = await fetch(`/api/settings/env/${encodeURIComponent(key)}`, {
				method: 'DELETE'
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to delete variable');
			}

			success = `Variable '${key}' deleted`;
			await loadEnvVars();

			setTimeout(() => success = null, 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			saving = false;
		}
	}

	async function reloadFromFiles() {
		loading = true;
		error = null;
		try {
			const response = await fetch('/api/settings/env/reload', {
				method: 'POST'
			});

			if (!response.ok) throw new Error('Failed to reload');

			const data = await response.json();
			success = `Reloaded ${data.count} variables from .env files`;
			await loadEnvVars();

			setTimeout(() => success = null, 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	function toggleReveal(key: string) {
		const newSet = new Set(revealedKeys);
		if (newSet.has(key)) {
			newSet.delete(key);
		} else {
			newSet.add(key);
		}
		revealedKeys = newSet;
	}

	async function copyToClipboard(text: string, key: string) {
		try {
			await navigator.clipboard.writeText(text);
			copiedKey = key;
			setTimeout(() => copiedKey = null, 2000);
		} catch (e) {
			error = 'Failed to copy to clipboard';
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onclose();
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- Backdrop -->
<div
	class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
	onclick={(e) => e.target === e.currentTarget && onclose()}
	role="dialog"
	aria-modal="true"
>
	<!-- Modal -->
	<div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl h-[80vh] flex flex-col overflow-hidden">
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
			<div class="flex items-center gap-3">
				<div class="p-2 bg-violet-100 dark:bg-violet-900/30 rounded-lg">
					<Settings size={20} class="text-violet-600 dark:text-violet-400" />
				</div>
				<div>
					<h2 class="text-lg font-semibold text-gray-900 dark:text-gray-100">Settings</h2>
					<p class="text-sm text-gray-500">Configure your SyGra Studio preferences</p>
				</div>
			</div>
			<button
				onclick={onclose}
				class="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
			>
				<X size={20} class="text-gray-500" />
			</button>
		</div>

		<!-- Content with vertical tabs -->
		<div class="flex-1 flex overflow-hidden">
			<!-- Left sidebar - Tabs -->
			<div class="w-52 border-r border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3 flex flex-col gap-1">
				{#each tabs as tab}
					<button
						onclick={() => activeTab = tab.id}
						class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors w-full
							{activeTab === tab.id
								? 'bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300'
								: 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}"
					>
						<svelte:component this={tab.icon} size={18} />
						<span class="text-sm font-medium">{tab.label}</span>
					</button>
				{/each}
			</div>

			<!-- Right panel - Content -->
			<div class="flex-1 overflow-y-auto p-6">
				<!-- Alerts -->
				{#if error}
					<div class="mb-4 flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
						<AlertCircle size={16} />
						{error}
						<button onclick={() => error = null} class="ml-auto">
							<X size={14} />
						</button>
					</div>
				{/if}

				{#if success}
					<div class="mb-4 flex items-center gap-2 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-400 text-sm">
						<CheckCircle size={16} />
						{success}
					</div>
				{/if}

				<!-- General Tab -->
				{#if activeTab === 'general'}
					<div class="space-y-6">
						<div>
							<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">General Settings</h3>

							<div class="space-y-4">
								<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
									<div class="flex items-center gap-3 mb-2">
										<Info size={18} class="text-violet-500" />
										<h4 class="font-medium text-gray-900 dark:text-gray-100">About SyGra Studio</h4>
									</div>
									<p class="text-sm text-gray-600 dark:text-gray-400">
										SyGra Studio is a visual workflow builder and execution environment for SyGra pipelines.
									</p>
									<div class="mt-3 text-xs text-gray-500">
										<div>Version: 1.0.0</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Appearance Tab -->
				{#if activeTab === 'appearance'}
					<div class="space-y-6">
						<div>
							<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Appearance</h3>

							<div class="space-y-4">
								<div>
									<label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
										Theme
									</label>
									<div class="grid grid-cols-3 gap-3">
										<button
											onclick={() => themeStore.setTheme('light')}
											class="flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors
												{currentTheme === 'light'
													? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
													: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
										>
											<div class="w-12 h-12 rounded-lg bg-white border border-gray-200 flex items-center justify-center shadow-sm">
												<Sun size={24} class="text-amber-500" />
											</div>
											<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Light</span>
										</button>

										<button
											onclick={() => themeStore.setTheme('dark')}
											class="flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors
												{currentTheme === 'dark'
													? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
													: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
										>
											<div class="w-12 h-12 rounded-lg bg-gray-900 border border-gray-700 flex items-center justify-center shadow-sm">
												<Moon size={24} class="text-blue-400" />
											</div>
											<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Dark</span>
										</button>

										<button
											onclick={() => themeStore.setTheme('system')}
											class="flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors
												{currentTheme === 'system'
													? 'border-violet-500 bg-violet-50 dark:bg-violet-900/20'
													: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'}"
										>
											<div class="w-12 h-12 rounded-lg bg-gradient-to-br from-white to-gray-900 border border-gray-300 flex items-center justify-center shadow-sm">
												<Monitor size={24} class="text-gray-600" />
											</div>
											<span class="text-sm font-medium text-gray-700 dark:text-gray-300">System</span>
										</button>
									</div>
									<p class="mt-3 text-xs text-gray-500">
										{#if currentTheme === 'system'}
											Using system preference ({isDark ? 'dark' : 'light'} mode detected)
										{:else}
											Using {currentTheme} mode
										{/if}
									</p>
								</div>
							</div>
						</div>
					</div>
				{/if}

				<!-- Environment Variables Tab -->
				{#if activeTab === 'environment'}
					<div class="space-y-4">
						<div class="flex items-center justify-between">
							<div>
								<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">Environment Variables</h3>
								<p class="text-sm text-gray-500 mt-1">Manage variables used during workflow execution</p>
							</div>
							<div class="flex items-center gap-2">
								<button
									onclick={reloadFromFiles}
									disabled={loading}
									class="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors disabled:opacity-50"
									title="Reload from .env files"
								>
									<RefreshCw size={14} class={loading ? 'animate-spin' : ''} />
									Reload
								</button>
								<button
									onclick={() => showNewForm = !showNewForm}
									class="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
								>
									<Plus size={14} />
									Add Variable
								</button>
							</div>
						</div>

						<!-- Env file path info -->
						<div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50 px-3 py-2 rounded-lg">
							<FileText size={12} />
							<span class="font-mono truncate">{envFile}</span>
						</div>

						<!-- New Variable Form -->
						{#if showNewForm}
							<div class="p-4 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg space-y-3">
								<div class="grid grid-cols-2 gap-3">
									<div>
										<label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
											Variable Name
										</label>
										<input
											type="text"
											bind:value={newKey}
											placeholder="MY_VARIABLE"
											class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-violet-500 focus:border-violet-500 font-mono"
										/>
									</div>
									<div>
										<label class="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
											Value
										</label>
										<input
											type="text"
											bind:value={newValue}
											placeholder="value"
											class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
										/>
									</div>
								</div>
								<div class="flex justify-end gap-2">
									<button
										onclick={() => { showNewForm = false; newKey = ''; newValue = ''; }}
										class="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
									>
										Cancel
									</button>
									<button
										onclick={addVariable}
										disabled={saving || !newKey.trim()}
										class="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 text-white rounded-lg transition-colors"
									>
										{#if saving}
											<RefreshCw size={14} class="animate-spin" />
										{:else}
											<Save size={14} />
										{/if}
										Add
									</button>
								</div>
							</div>
						{/if}

						<!-- Variables List -->
						{#if loading && envVars.length === 0}
							<div class="flex items-center justify-center py-12 text-gray-500">
								<RefreshCw size={20} class="animate-spin mr-2" />
								Loading...
							</div>
						{:else if envVars.length === 0}
							<div class="text-center py-12 text-gray-500">
								<Key size={32} class="mx-auto mb-3 opacity-50" />
								<p>No environment variables configured</p>
								<p class="text-sm mt-1">Click "Add Variable" to create one</p>
							</div>
						{:else}
							<div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
								<table class="w-full">
									<thead>
										<tr class="bg-gray-50 dark:bg-gray-800 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
											<th class="px-4 py-3">Variable</th>
											<th class="px-4 py-3">Value</th>
											<th class="px-4 py-3 w-24">Actions</th>
										</tr>
									</thead>
									<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
										{#each envVars as envVar}
											<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
												<td class="px-4 py-3">
													<div class="flex items-center gap-2">
														{#if envVar.is_sensitive}
															<Key size={14} class="text-amber-500" title="Sensitive" />
														{/if}
														<span class="font-mono text-sm text-gray-900 dark:text-gray-100">
															{envVar.key}
														</span>
													</div>
												</td>
												<td class="px-4 py-3">
													<div class="flex items-center gap-2">
														<input
															type={revealedKeys.has(envVar.key) ? 'text' : 'password'}
															value={revealedKeys.has(envVar.key) ? envVar.value : envVar.masked_value}
															onchange={(e) => updateVariable(envVar.key, e.currentTarget.value)}
															class="flex-1 px-2 py-1 text-sm font-mono border border-transparent hover:border-gray-300 dark:hover:border-gray-600 focus:border-violet-500 rounded bg-transparent text-gray-800 dark:text-gray-200 focus:outline-none focus:ring-1 focus:ring-violet-500"
														/>
														<button
															onclick={() => toggleReveal(envVar.key)}
															class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
															title={revealedKeys.has(envVar.key) ? 'Hide' : 'Reveal'}
														>
															{#if revealedKeys.has(envVar.key)}
																<EyeOff size={14} />
															{:else}
																<Eye size={14} />
															{/if}
														</button>
														<button
															onclick={() => copyToClipboard(envVar.value, envVar.key)}
															class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
															title="Copy value"
														>
															{#if copiedKey === envVar.key}
																<Check size={14} class="text-green-500" />
															{:else}
																<Copy size={14} />
															{/if}
														</button>
													</div>
												</td>
												<td class="px-4 py-3">
													<button
														onclick={() => deleteVariable(envVar.key)}
														class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
														title="Delete"
													>
														<Trash2 size={14} />
													</button>
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
			<button
				onclick={onclose}
				class="px-4 py-2 text-sm font-medium bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
			>
				Done
			</button>
		</div>
	</div>
</div>
