<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { toolStore, TOOL_CATEGORIES, type Tool, type ToolCategory } from '$lib/stores/tool.svelte';
	import {
		X, Search, Plus, Wrench, Database, Globe, Puzzle, Library,
		Code, ExternalLink
	} from 'lucide-svelte';

	interface Props {
		existingTools?: string[];
	}

	let { existingTools = [] }: Props = $props();

	const dispatch = createEventDispatcher<{
		select: { tool: Tool | null; importPath: string };
		cancel: void;
	}>();

	let searchQuery = $state('');
	let activeTab = $state<'library' | 'manual'>('library');
	let manualPath = $state('');

	// Category icon mapping
	const categoryIcons: Record<ToolCategory, typeof Wrench> = {
		search: Search,
		data: Database,
		api: Globe,
		utility: Wrench,
		custom: Puzzle
	};

	// Get category color
	function getCategoryColor(category: ToolCategory): string {
		return TOOL_CATEGORIES.find(c => c.value === category)?.color || '#6b7280';
	}

	// Filter tools by search and exclude already added
	let filteredTools = $derived(() => {
		let filtered = toolStore.tools.filter(t => !existingTools.includes(t.import_path));

		if (searchQuery.trim()) {
			const query = searchQuery.toLowerCase();
			filtered = filtered.filter(t =>
				t.name.toLowerCase().includes(query) ||
				t.description.toLowerCase().includes(query) ||
				t.import_path.toLowerCase().includes(query)
			);
		}
		return filtered;
	});

	function handleSelectTool(tool: Tool) {
		dispatch('select', { tool, importPath: tool.import_path });
	}

	function handleManualAdd() {
		if (manualPath.trim()) {
			dispatch('select', { tool: null, importPath: manualPath.trim() });
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('cancel');
		}
		if (e.key === 'Enter' && activeTab === 'manual' && manualPath.trim()) {
			handleManualAdd();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('cancel')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md mx-4 max-h-[70vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="w-9 h-9 rounded-lg bg-[#7661FF]/10 flex items-center justify-center">
					<Wrench size={18} class="text-[#7661FF]" />
				</div>
				<div>
					<h3 class="text-base font-semibold text-gray-800 dark:text-gray-200">
						Add Tool
					</h3>
					<p class="text-xs text-gray-500 dark:text-gray-400">
						Select from library or enter path
					</p>
				</div>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
			>
				<X size={18} />
			</button>
		</div>

		<!-- Tabs -->
		<div class="flex border-b border-gray-200 dark:border-gray-800">
			<button
				onclick={() => activeTab = 'library'}
				class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors"
				class:text-[#7661FF]={activeTab === 'library'}
				class:dark:text-[#52B8FF]={activeTab === 'library'}
				class:border-b-2={activeTab === 'library'}
				class:border-[#7661FF]={activeTab === 'library'}
				class:text-gray-500={activeTab !== 'library'}
				class:hover:text-gray-700={activeTab !== 'library'}
			>
				<span class="flex items-center justify-center gap-2">
					<Library size={14} />
					Library
					{#if toolStore.tools.length > 0}
						<span class="text-xs px-1.5 py-0.5 rounded-full bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]">
							{toolStore.tools.length}
						</span>
					{/if}
				</span>
			</button>
			<button
				onclick={() => activeTab = 'manual'}
				class="flex-1 px-4 py-2.5 text-sm font-medium transition-colors"
				class:text-[#7661FF]={activeTab === 'manual'}
				class:dark:text-[#52B8FF]={activeTab === 'manual'}
				class:border-b-2={activeTab === 'manual'}
				class:border-[#7661FF]={activeTab === 'manual'}
				class:text-gray-500={activeTab !== 'manual'}
				class:hover:text-gray-700={activeTab !== 'manual'}
			>
				<span class="flex items-center justify-center gap-2">
					<Code size={14} />
					Manual Path
				</span>
			</button>
		</div>

		<!-- Content -->
		{#if activeTab === 'library'}
			<!-- Library Tab -->
			{#if toolStore.tools.length > 0}
				<!-- Search -->
				<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
					<div class="relative">
						<Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
						<input
							type="text"
							placeholder="Search tools..."
							bind:value={searchQuery}
							class="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
						/>
					</div>
				</div>

				<!-- Tool List -->
				<div class="flex-1 overflow-y-auto p-3">
					{#if filteredTools().length === 0}
						<div class="text-center py-8 text-gray-500 dark:text-gray-400">
							<p class="text-sm">No tools match your search</p>
						</div>
					{:else}
						<div class="space-y-2">
							{#each filteredTools() as tool (tool.id)}
								{@const Icon = categoryIcons[tool.category]}
								<button
									onclick={() => handleSelectTool(tool)}
									class="w-full flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-[#52B8FF] dark:hover:border-[#7661FF] hover:bg-[#7661FF]/5 dark:hover:bg-[#7661FF]/10 transition-all text-left"
								>
									<div
										class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
										style="background-color: {getCategoryColor(tool.category)}20"
									>
										<Icon size={14} style="color: {getCategoryColor(tool.category)}" />
									</div>
									<div class="flex-1 min-w-0">
										<div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
											{tool.name}
										</div>
										{#if tool.description}
											<div class="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
												{tool.description}
											</div>
										{/if}
										<div class="text-xs text-gray-400 dark:text-gray-500 font-mono truncate mt-1">
											{tool.import_path}
										</div>
									</div>
								</button>
							{/each}
						</div>
					{/if}
				</div>
			{:else}
				<!-- No tools message -->
				<div class="flex-1 flex items-center justify-center p-6">
					<div class="text-center">
						<Wrench size={32} class="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
						<p class="text-sm text-gray-500 dark:text-gray-400">
							No tools in library yet
						</p>
						<p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
							Create tools in the Library to reuse them
						</p>
						<button
							onclick={() => activeTab = 'manual'}
							class="mt-4 text-sm text-[#032D42] dark:text-[#52B8FF] hover:underline"
						>
							Or enter a manual path →
						</button>
					</div>
				</div>
			{/if}
		{:else}
			<!-- Manual Tab -->
			<div class="flex-1 p-4">
				<div class="space-y-4">
					<div>
						<label class="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2">
							Import Path
						</label>
						<input
							type="text"
							placeholder="package.module.tool_function"
							bind:value={manualPath}
							class="w-full px-3 py-2.5 text-sm font-mono rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
						/>
					</div>

					<div class="text-xs text-gray-500 dark:text-gray-400 space-y-2">
						<p>Enter the Python import path to a tool:</p>
						<ul class="list-disc list-inside space-y-1 text-gray-400">
							<li><code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">package.module.tool_function</code></li>
							<li><code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">package.module.ToolClass</code></li>
							<li><code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">package.module</code> (all tools)</li>
						</ul>
						<p class="mt-2">
							Functions must be decorated with <code class="px-1 py-0.5 bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF] rounded">@tool</code>
						</p>
					</div>

					<button
						onclick={handleManualAdd}
						disabled={!manualPath.trim()}
						class="w-full mt-4 px-4 py-2.5 bg-[#63DF4E] hover:bg-[#63DF4E]/90 disabled:bg-gray-300 disabled:dark:bg-gray-700 text-[#032D42] text-sm font-medium rounded-lg transition-colors"
					>
						Add Tool
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
