<script lang="ts">
	import type { CartesianProductParams } from '$lib/stores/workflow.svelte';
	import { Plus, Trash2, Grid3X3, Info } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, isEditing = false, onUpdate }: Props = $props();

	// Parse params
	let datasets = $state<Array<{ alias: string; prefix: string }>>(
		(params.datasets as Array<{ alias: string; prefix: string }>) || []
	);

	// Sync with params
	$effect(() => {
		datasets = (params.datasets as Array<{ alias: string; prefix: string }>) || [];
	});

	function emitUpdate() {
		const newParams: CartesianProductParams = {
			datasets: datasets.filter(d => d.alias.trim() && d.prefix.trim())
		};
		onUpdate(newParams);
	}

	function addDataset() {
		datasets = [...datasets, { alias: '', prefix: '' }];
	}

	function removeDataset(index: number) {
		datasets = datasets.filter((_, i) => i !== index);
		emitUpdate();
	}

	function updateDataset(index: number, field: 'alias' | 'prefix', value: string) {
		datasets[index][field] = value;
		datasets = [...datasets];
		emitUpdate();
	}
</script>

<div class="space-y-4">
	<!-- Info Section -->
	<div class="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
		<Grid3X3 size={16} class="text-blue-500 flex-shrink-0 mt-0.5" />
		<div class="text-blue-700 dark:text-blue-300">
			<p class="font-medium">Cartesian Product Transform</p>
			<p class="text-xs mt-1 text-blue-600 dark:text-blue-400">
				Creates M x N combinations from horizontally stacked data. Define dataset groups by their column prefix and assign aliases for the output columns.
			</p>
		</div>
	</div>

	<!-- Dataset Groups -->
	<div>
		<div class="flex items-center justify-between mb-2">
			<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
				Dataset Groups
			</label>
			{#if isEditing}
				<button
					onclick={addDataset}
					class="flex items-center gap-1 text-xs text-[#032D42] dark:text-[#52B8FF] hover:text-[#7661FF] dark:hover:text-[#BF71F2]"
				>
					<Plus size={12} />
					Add Group
				</button>
			{/if}
		</div>

		{#if datasets.length > 0}
			<div class="space-y-2">
				{#each datasets as dataset, index}
					<div class="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
						{#if isEditing}
							<div class="flex items-start gap-3">
								<div class="flex-1 space-y-2">
									<div>
										<label class="block text-xs text-gray-500 mb-1">Column Prefix</label>
										<input
											type="text"
											value={dataset.prefix}
											oninput={(e) => updateDataset(index, 'prefix', e.currentTarget.value)}
											placeholder="a_"
											class="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
										/>
									</div>
									<div>
										<label class="block text-xs text-gray-500 mb-1">Output Alias</label>
										<input
											type="text"
											value={dataset.alias}
											oninput={(e) => updateDataset(index, 'alias', e.currentTarget.value)}
											placeholder="user"
											class="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
										/>
									</div>
								</div>
								<button
									onclick={() => removeDataset(index)}
									class="p-1 text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
								>
									<Trash2 size={14} />
								</button>
							</div>
							{#if dataset.prefix && dataset.alias}
								<div class="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 text-xs text-gray-500">
									<span class="font-mono text-gray-600 dark:text-gray-400">{dataset.prefix}col1</span>
									<span class="mx-1">→</span>
									<span class="font-mono text-[#7661FF] dark:text-[#BF71F2]">{dataset.alias}_col1</span>
								</div>
							{/if}
						{:else}
							<div class="flex items-center justify-between">
								<div class="text-xs">
									<span class="text-gray-500">Prefix:</span>
									<code class="ml-1 px-1 bg-gray-100 dark:bg-gray-700 rounded text-gray-800 dark:text-gray-200">{dataset.prefix}</code>
								</div>
								<div class="text-xs">
									<span class="text-gray-500">Alias:</span>
									<code class="ml-1 px-1 bg-[#7661FF]/15 dark:bg-[#7661FF]/20 rounded text-[#7661FF] dark:text-[#52B8FF]">{dataset.alias}</code>
								</div>
							</div>
						{/if}
					</div>
				{/each}
			</div>

			{#if datasets.length >= 2}
				<div class="mt-3 p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-xs text-amber-700 dark:text-amber-400 flex items-start gap-2">
					<Info size={14} class="flex-shrink-0 mt-0.5" />
					<span>
						Will generate {datasets.length > 2 ? 'multiple' : ''} combinations from {datasets.map(d => d.alias || '?').join(' × ')} datasets
					</span>
				</div>
			{/if}
		{:else}
			<div class="text-xs text-gray-500 italic text-center py-4 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
				{#if isEditing}
					Add at least 2 dataset groups to create cartesian products
				{:else}
					No dataset groups defined
				{/if}
			</div>
		{/if}
	</div>

	{#if isEditing}
		<div class="flex items-start gap-2 p-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs text-gray-600 dark:text-gray-400">
			<Info size={14} class="flex-shrink-0 mt-0.5" />
			<div>
				<p class="font-medium mb-1">Example:</p>
				<p>Input columns: <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">a_col1, a_col2, b_col1, b_col2</code></p>
				<p>With prefixes <code class="text-[#7661FF]">a_</code> → <code class="text-[#7661FF]">user</code> and <code class="text-[#7661FF]">b_</code> → <code class="text-[#7661FF]">product</code></p>
				<p>Output: <code class="bg-gray-200 dark:bg-gray-700 px-1 rounded">user_col1, user_col2, product_col1, product_col2</code> with M×N rows</p>
			</div>
		</div>
	{/if}
</div>
