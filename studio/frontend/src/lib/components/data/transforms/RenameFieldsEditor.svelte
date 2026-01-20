<script lang="ts">
	import type { RenameFieldsParams } from '$lib/stores/workflow.svelte';
	import { Plus, Trash2, ArrowRight } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, isEditing = false, onUpdate }: Props = $props();

	// Parse params
	let mappings = $state<Array<{ oldName: string; newName: string }>>(
		params.mapping
			? Object.entries(params.mapping as Record<string, string>).map(([oldName, newName]) => ({ oldName, newName }))
			: []
	);
	let overwrite = $state((params.overwrite as boolean) ?? false);

	// Sync with params
	$effect(() => {
		mappings = params.mapping
			? Object.entries(params.mapping as Record<string, string>).map(([oldName, newName]) => ({ oldName, newName }))
			: [];
		overwrite = (params.overwrite as boolean) ?? false;
	});

	function emitUpdate() {
		const newParams: RenameFieldsParams = {
			mapping: {},
			overwrite
		};

		for (const { oldName, newName } of mappings) {
			if (oldName.trim() && newName.trim()) {
				newParams.mapping[oldName.trim()] = newName.trim();
			}
		}

		onUpdate(newParams);
	}

	function addMapping() {
		mappings = [...mappings, { oldName: '', newName: '' }];
	}

	function removeMapping(index: number) {
		mappings = mappings.filter((_, i) => i !== index);
		emitUpdate();
	}

	function updateMapping(index: number, field: 'oldName' | 'newName', value: string) {
		mappings[index][field] = value;
		mappings = [...mappings];
		emitUpdate();
	}
</script>

<div class="space-y-4">
	<!-- Field Mappings -->
	<div>
		<div class="flex items-center justify-between mb-2">
			<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
				Field Mappings
			</label>
			{#if isEditing}
				<button
					onclick={addMapping}
					class="flex items-center gap-1 text-xs text-[#032D42] dark:text-[#52B8FF] hover:text-[#7661FF] dark:hover:text-[#BF71F2]"
				>
					<Plus size={12} />
					Add Mapping
				</button>
			{/if}
		</div>

		{#if mappings.length > 0}
			<div class="space-y-2">
				{#each mappings as mapping, index}
					<div class="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
						{#if isEditing}
							<input
								type="text"
								value={mapping.oldName}
								oninput={(e) => updateMapping(index, 'oldName', e.currentTarget.value)}
								placeholder="old_field"
								class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							/>
							<ArrowRight size={14} class="text-gray-400 flex-shrink-0" />
							<input
								type="text"
								value={mapping.newName}
								oninput={(e) => updateMapping(index, 'newName', e.currentTarget.value)}
								placeholder="new_field"
								class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							/>
							<button
								onclick={() => removeMapping(index)}
								class="p-1 text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
							>
								<Trash2 size={14} />
							</button>
						{:else}
							<code class="text-xs font-mono flex items-center gap-2">
								<span class="text-gray-600 dark:text-gray-400">{mapping.oldName}</span>
								<ArrowRight size={12} class="text-gray-400" />
								<span class="text-[#7661FF] dark:text-[#BF71F2]">{mapping.newName}</span>
							</code>
						{/if}
					</div>
				{/each}
			</div>
		{:else}
			<div class="text-xs text-gray-500 italic text-center py-3 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
				{#if isEditing}
					Click "Add Mapping" to define field renames
				{:else}
					No field mappings defined
				{/if}
			</div>
		{/if}
	</div>

	<!-- Overwrite Option -->
	<div>
		{#if isEditing}
			<label class="flex items-center gap-2 cursor-pointer">
				<input
					type="checkbox"
					bind:checked={overwrite}
					onchange={emitUpdate}
					class="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-[#63DF4E] focus:ring-[#52B8FF] dark:focus:ring-[#52B8FF]"
				/>
				<span class="text-sm text-gray-700 dark:text-gray-300">
					Overwrite existing fields
				</span>
			</label>
			<p class="text-xs text-gray-500 mt-1 ml-6">
				If enabled, will overwrite if the new field name already exists
			</p>
		{:else if overwrite}
			<div class="text-xs text-gray-600 dark:text-gray-400">
				Overwrite mode: <span class="text-[#7661FF] dark:text-[#BF71F2]">enabled</span>
			</div>
		{/if}
	</div>
</div>
