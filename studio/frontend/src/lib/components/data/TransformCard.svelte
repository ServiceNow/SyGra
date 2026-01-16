<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		TRANSFORM_METADATA,
		getTransformShortName,
		type TransformConfig
	} from '$lib/stores/workflow.svelte';
	import {
		ChevronDown, ChevronUp, Trash2, Power, PowerOff,
		SkipForward, Combine, ArrowLeftRight, PlusCircle,
		Image, AudioLines, Grid3X3, Settings, AlertCircle, Wand2
	} from 'lucide-svelte';
	import type { Component } from 'svelte';

	// Import parameter editors
	import SkipRecordsEditor from './transforms/SkipRecordsEditor.svelte';
	import CombineRecordsEditor from './transforms/CombineRecordsEditor.svelte';
	import RenameFieldsEditor from './transforms/RenameFieldsEditor.svelte';
	import AddNewFieldEditor from './transforms/AddNewFieldEditor.svelte';
	import MediaTransformEditor from './transforms/MediaTransformEditor.svelte';
	import CartesianProductEditor from './transforms/CartesianProductEditor.svelte';
	import CustomTransformEditor from './transforms/CustomTransformEditor.svelte';

	interface Props {
		transform: TransformConfig;
		index: number;
		isEditing?: boolean;
		isExpanded?: boolean;
	}

	let { transform, index, isEditing = false, isExpanded = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		update: { transform: TransformConfig };
		remove: void;
		toggle: void;
		toggleEnabled: void;
		dragstart: { index: number };
		dragover: { index: number };
		dragend: void;
	}>();

	// Get short name for display
	let shortName = $derived(getTransformShortName(transform.transform));
	let meta = $derived(TRANSFORM_METADATA[shortName]);
	let isEnabled = $derived(transform.enabled !== false);

	// Transform type configurations with colors
	const transformTypeConfig: Record<string, {
		icon: Component<{ size?: number; class?: string }>;
		bgClass: string;
		iconClass: string;
	}> = {
		SkipRecords: { icon: SkipForward, bgClass: 'bg-rose-100 dark:bg-rose-900/30', iconClass: 'text-rose-600 dark:text-rose-400' },
		CombineRecords: { icon: Combine, bgClass: 'bg-blue-100 dark:bg-blue-900/30', iconClass: 'text-blue-600 dark:text-blue-400' },
		RenameFieldsTransform: { icon: ArrowLeftRight, bgClass: 'bg-amber-100 dark:bg-amber-900/30', iconClass: 'text-amber-600 dark:text-amber-400' },
		AddNewFieldTransform: { icon: PlusCircle, bgClass: 'bg-emerald-100 dark:bg-emerald-900/30', iconClass: 'text-emerald-600 dark:text-emerald-400' },
		CreateImageUrlTransform: { icon: Image, bgClass: 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20', iconClass: 'text-[#7661FF] dark:text-[#BF71F2]' },
		CreateAudioUrlTransform: { icon: AudioLines, bgClass: 'bg-pink-100 dark:bg-pink-900/30', iconClass: 'text-pink-600 dark:text-pink-400' },
		CartesianProductTransform: { icon: Grid3X3, bgClass: 'bg-cyan-100 dark:bg-cyan-900/30', iconClass: 'text-cyan-600 dark:text-cyan-400' }
	};

	let config = $derived(transformTypeConfig[shortName] || {
		icon: Settings,
		bgClass: 'bg-gray-100 dark:bg-gray-700',
		iconClass: 'text-gray-600 dark:text-gray-400'
	});

	let Icon = $derived(config.icon);

	// Get compact parameter summary
	function getParamsSummary(): string {
		const params = transform.params;
		if (!params || Object.keys(params).length === 0) return '';

		switch (shortName) {
			case 'SkipRecords':
				if (params.skip_type === 'count') {
					const c = params.count as { from_start?: number; from_end?: number } | undefined;
					return `${c?.from_start || 0}↑ ${c?.from_end || 0}↓`;
				}
				return params.range ? `[${params.range}]` : '';
			case 'CombineRecords':
				return `×${params.combine || 2}`;
			case 'RenameFieldsTransform':
				const mapping = params.mapping as Record<string, string> | undefined;
				return mapping ? `${Object.keys(mapping).length} fields` : '';
			case 'AddNewFieldTransform':
				const addMapping = params.mapping as Record<string, unknown> | undefined;
				return addMapping ? `+${Object.keys(addMapping).length}` : '';
			case 'CartesianProductTransform':
				const datasets = params.datasets as Array<{ alias: string }> | undefined;
				return datasets ? `${datasets.length} sets` : '';
			default:
				return Object.keys(params).length > 0 ? `${Object.keys(params).length}p` : '';
		}
	}

	function handleUpdate(newParams: Record<string, unknown>) {
		dispatch('update', { transform: { ...transform, params: newParams } });
	}

	function handleModulePathChange(modulePath: string) {
		dispatch('update', { transform: { ...transform, transform: modulePath } });
	}

	function handleDragStart(e: DragEvent) {
		if (!isEditing) return;
		e.dataTransfer?.setData('text/plain', String(index));
		dispatch('dragstart', { index });
	}

	function handleDragOver(e: DragEvent) {
		if (!isEditing) return;
		e.preventDefault();
		dispatch('dragover', { index });
	}
</script>

<div
	class="group"
	draggable={isEditing}
	ondragstart={handleDragStart}
	ondragover={handleDragOver}
	ondragend={() => dispatch('dragend')}
	role="listitem"
>
	<!-- Compact Header -->
	<div class="flex items-center gap-2 p-2 bg-white dark:bg-gray-800 rounded-lg border transition-all
		{isEnabled
			? (isExpanded
				? 'border-[#7661FF]/50 dark:border-[#7661FF]/60'
				: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600')
			: 'border-gray-200/50 dark:border-gray-700/50 opacity-50'}
		{isEditing ? 'cursor-grab active:cursor-grabbing' : ''}">

		<!-- Step number -->
		<div class="w-5 h-5 flex items-center justify-center rounded text-[10px] font-bold flex-shrink-0
			{isEnabled ? 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'}">
			{index + 1}
		</div>

		<!-- Icon -->
		<div class="flex-shrink-0 p-1 rounded-lg {isEnabled ? config.bgClass : 'bg-gray-100 dark:bg-gray-700'}">
			<Icon size={12} class={isEnabled ? config.iconClass : 'text-gray-400'} />
		</div>

		<!-- Name & Summary -->
		<button onclick={() => dispatch('toggle')} class="flex-1 text-left min-w-0 flex items-center gap-2">
			<span class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate {!isEnabled && 'line-through opacity-70'}">
				{meta?.name || shortName}
			</span>
			{#if getParamsSummary()}
				<span class="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded flex-shrink-0">
					{getParamsSummary()}
				</span>
			{/if}
		</button>

		<!-- Actions -->
		<div class="flex items-center gap-0.5 flex-shrink-0">
			{#if isEditing}
				<button
					onclick={() => dispatch('toggleEnabled')}
					class="p-1 rounded transition-colors
						{isEnabled
							? 'text-emerald-500 hover:bg-emerald-100 dark:hover:bg-emerald-900/30'
							: 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'}"
					title={isEnabled ? 'Disable' : 'Enable'}
				>
					{#if isEnabled}<Power size={12} />{:else}<PowerOff size={12} />{/if}
				</button>
				<button
					onclick={() => dispatch('remove')}
					class="p-1 rounded text-gray-400 hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
					title="Remove"
				>
					<Trash2 size={12} />
				</button>
			{/if}
			<button onclick={() => dispatch('toggle')} class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700">
				{#if isExpanded}<ChevronUp size={12} class="text-gray-400" />{:else}<ChevronDown size={12} class="text-gray-400" />{/if}
			</button>
		</div>
	</div>

	<!-- Expanded Editor -->
	{#if isExpanded}
		<div class="mt-1 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
			{#if !isEnabled}
				<div class="flex items-center gap-2 mb-3 p-2 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded text-amber-700 dark:text-amber-400 text-[10px]">
					<AlertCircle size={12} />
					<span>Disabled - will be skipped</span>
				</div>
			{/if}

			<div class="text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
				<Wand2 size={10} />
				Parameters
			</div>

			{#if shortName === 'SkipRecords'}
				<SkipRecordsEditor params={transform.params} {isEditing} onUpdate={handleUpdate} />
			{:else if shortName === 'CombineRecords'}
				<CombineRecordsEditor params={transform.params} {isEditing} onUpdate={handleUpdate} />
			{:else if shortName === 'RenameFieldsTransform'}
				<RenameFieldsEditor params={transform.params} {isEditing} onUpdate={handleUpdate} />
			{:else if shortName === 'AddNewFieldTransform'}
				<AddNewFieldEditor params={transform.params} {isEditing} onUpdate={handleUpdate} />
			{:else if shortName === 'CreateImageUrlTransform' || shortName === 'CreateAudioUrlTransform'}
				<MediaTransformEditor params={transform.params} type={shortName === 'CreateImageUrlTransform' ? 'image' : 'audio'} {isEditing} onUpdate={handleUpdate} />
			{:else if shortName === 'CartesianProductTransform'}
				<CartesianProductEditor params={transform.params} {isEditing} onUpdate={handleUpdate} />
			{:else}
				<CustomTransformEditor modulePath={transform.transform} params={transform.params} {isEditing} onUpdate={handleUpdate} onModulePathChange={handleModulePathChange} />
			{/if}
		</div>
	{/if}
</div>
