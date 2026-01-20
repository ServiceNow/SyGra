<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		type TransformConfig,
		TRANSFORM_MODULES,
		getTransformDisplayName
	} from '$lib/stores/workflow.svelte';
	import TransformCard from './TransformCard.svelte';
	import TransformSelector from './TransformSelector.svelte';
	import { Plus, ChevronDown, ChevronUp, Wand2 } from 'lucide-svelte';

	interface Props {
		transforms: TransformConfig[];
		isEditing?: boolean;
	}

	let { transforms = [], isEditing = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		update: { transforms: TransformConfig[] };
	}>();

	// Local state
	let showSelector = $state(false);
	let expandedIndex = $state<number | null>(null);
	let dragOverIndex = $state<number | null>(null);
	let draggedIndex = $state<number | null>(null);
	let isExpanded = $state(true);

	function generateId(): string {
		return `transform_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
	}

	function handleSelectTransform(e: CustomEvent<{ type: string; modulePath: string }>) {
		const { type, modulePath } = e.detail;
		const newTransform: TransformConfig = {
			id: generateId(),
			transform: type === 'custom' ? '' : modulePath,
			params: getDefaultParams(type),
			enabled: true
		};

		const newTransforms = [...transforms, newTransform];
		dispatch('update', { transforms: newTransforms });
		expandedIndex = newTransforms.length - 1;
		showSelector = false;
	}

	function getDefaultParams(type: string): Record<string, unknown> {
		switch (type) {
			case 'SkipRecords': return { skip_type: 'count', count: { from_start: 0, from_end: 0 } };
			case 'CombineRecords': return { combine: 2, shift: 1 };
			case 'RenameFieldsTransform': return { mapping: {}, overwrite: false };
			case 'AddNewFieldTransform': return { mapping: {} };
			case 'CartesianProductTransform': return { datasets: [] };
			default: return {};
		}
	}

	function handleUpdateTransform(index: number, updatedTransform: TransformConfig) {
		const newTransforms = [...transforms];
		newTransforms[index] = updatedTransform;
		dispatch('update', { transforms: newTransforms });
	}

	function handleRemoveTransform(index: number) {
		const newTransforms = transforms.filter((_, i) => i !== index);
		dispatch('update', { transforms: newTransforms });
		if (expandedIndex === index) expandedIndex = null;
		else if (expandedIndex !== null && expandedIndex > index) expandedIndex--;
	}

	function handleToggleTransform(index: number) {
		expandedIndex = expandedIndex === index ? null : index;
	}

	function handleToggleEnabled(index: number) {
		const newTransforms = [...transforms];
		newTransforms[index] = {
			...newTransforms[index],
			enabled: newTransforms[index].enabled === false ? true : false
		};
		dispatch('update', { transforms: newTransforms });
	}

	function handleDragStart(index: number) { draggedIndex = index; }
	function handleDragOver(index: number) {
		if (draggedIndex !== null && draggedIndex !== index) dragOverIndex = index;
	}
	function handleDragEnd() {
		if (draggedIndex !== null && dragOverIndex !== null && draggedIndex !== dragOverIndex) {
			const newTransforms = [...transforms];
			const [removed] = newTransforms.splice(draggedIndex, 1);
			newTransforms.splice(dragOverIndex, 0, removed);
			dispatch('update', { transforms: newTransforms });
			if (expandedIndex === draggedIndex) expandedIndex = dragOverIndex;
		}
		draggedIndex = null;
		dragOverIndex = null;
	}

	let enabledCount = $derived(transforms.filter(t => t.enabled !== false).length);
</script>

<div class="border border-gray-200 dark:border-gray-700 rounded-xl bg-white dark:bg-gray-900 overflow-hidden">
	<!-- Header -->
	<div
		role="button"
		tabindex="0"
		onclick={() => isExpanded = !isExpanded}
		onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') isExpanded = !isExpanded; }}
		class="flex items-center justify-between px-3 py-2.5 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors cursor-pointer"
	>
		<div class="flex items-center gap-2">
			<div class="p-1.5 rounded-lg bg-[#7661FF]/15 dark:bg-[#7661FF]/20">
				<Wand2 size={14} class="text-[#7661FF] dark:text-[#BF71F2]" />
			</div>
			<div>
				<div class="text-sm font-medium text-gray-900 dark:text-gray-100">Transforms</div>
				<div class="text-[10px] text-gray-500 dark:text-gray-400">
					{#if transforms.length === 0}
						None
					{:else}
						{enabledCount}/{transforms.length} active
					{/if}
				</div>
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if isEditing && isExpanded}
				<button
					onclick={(e) => { e.stopPropagation(); showSelector = true; }}
					class="flex items-center gap-1 px-2 py-1 text-[10px] font-medium text-[#7661FF] dark:text-[#52B8FF] bg-[#7661FF]/15 dark:bg-[#7661FF]/20 hover:bg-[#7661FF]/25 dark:hover:bg-[#7661FF]/30 rounded transition-colors"
				>
					<Plus size={12} />
					Add
				</button>
			{/if}
			<div class="text-gray-400">
				{#if isExpanded}<ChevronUp size={16} />{:else}<ChevronDown size={16} />{/if}
			</div>
		</div>
	</div>

	{#if isExpanded}
		<div class="p-3 border-t border-gray-100 dark:border-gray-800">
			{#if transforms.length === 0}
				<div class="text-center py-6">
					<Wand2 size={24} class="mx-auto mb-2 text-gray-300 dark:text-gray-600" />
					<p class="text-xs text-gray-500 dark:text-gray-400 mb-3">No transforms configured</p>
					{#if isEditing}
						<button
							onclick={() => showSelector = true}
							class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#63DF4E] hover:bg-[#63DF4E]/90 text-[#032D42] rounded-lg transition-colors"
						>
							<Plus size={14} />
							Add Transform
						</button>
					{/if}
				</div>
			{:else}
				<div class="space-y-1.5" role="list">
					{#each transforms as transform, index (transform.id)}
						{#if dragOverIndex === index && draggedIndex !== null && draggedIndex !== index}
							<div class="h-0.5 bg-[#7661FF] rounded-full mx-2"></div>
						{/if}
						<TransformCard
							{transform}
							{index}
							{isEditing}
							isExpanded={expandedIndex === index}
							on:update={(e) => handleUpdateTransform(index, e.detail.transform)}
							on:remove={() => handleRemoveTransform(index)}
							on:toggle={() => handleToggleTransform(index)}
							on:toggleEnabled={() => handleToggleEnabled(index)}
							on:dragstart={(e) => handleDragStart(e.detail.index)}
							on:dragover={(e) => handleDragOver(e.detail.index)}
							on:dragend={handleDragEnd}
						/>
					{/each}
				</div>

				{#if isEditing}
					<button
						onclick={() => showSelector = true}
						class="w-full mt-3 flex items-center justify-center gap-1.5 px-3 py-2 text-xs text-gray-500 dark:text-gray-400 hover:text-[#7661FF] dark:hover:text-[#52B8FF] bg-gray-50 dark:bg-gray-800 hover:bg-[#7661FF]/5 dark:hover:bg-[#7661FF]/10 border border-dashed border-gray-300 dark:border-gray-600 hover:border-[#7661FF] dark:hover:border-[#7661FF] rounded-lg transition-all"
					>
						<Plus size={14} />
						Add Transform
					</button>
				{/if}
			{/if}
		</div>
	{/if}
</div>

<TransformSelector open={showSelector} on:select={handleSelectTransform} on:close={() => showSelector = false} />
