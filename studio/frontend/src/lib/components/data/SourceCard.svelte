<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DataSourceDetails, JoinType } from '$lib/stores/workflow.svelte';
	import { JOIN_TYPE_METADATA } from '$lib/stores/workflow.svelte';
	import {
		Database, Cloud, Server, HardDrive, MemoryStick,
		Edit3, Trash2, Link, Crown, Zap, Filter, Hash,
		Eye, ChevronDown, ChevronUp
	} from 'lucide-svelte';
	import type { Component } from 'svelte';
	import SourcePreview from './SourcePreview.svelte';

	interface PreviewData {
		records: Record<string, unknown>[];
		total?: number | string;
		message?: string;
		source_type?: string;
	}

	interface Props {
		source: DataSourceDetails;
		index: number;
		isEditing?: boolean;
		isPrimary?: boolean;
		showJoinInfo?: boolean;
		showAlias?: boolean;
		previewData?: PreviewData | null;
		previewLoading?: boolean;
		showPreviewToggle?: boolean;
	}

	let {
		source,
		index,
		isEditing = false,
		isPrimary = false,
		showJoinInfo = true,
		showAlias = true,
		previewData = null,
		previewLoading = false,
		showPreviewToggle = true
	}: Props = $props();

	// Local state for preview expansion
	let showPreview = $state(false);

	const dispatch = createEventDispatcher<{
		edit: void;
		remove: void;
		makePrimary: void;
		previewFetch: { index: number };
		previewRefresh: { index: number };
	}>();

	function handlePreviewToggle() {
		showPreview = !showPreview;
		// Auto-fetch when opening preview if no data
		if (showPreview && !previewData && !previewLoading) {
			dispatch('previewFetch', { index });
		}
	}

	function handlePreviewFetch(e: CustomEvent<{ index: number }>) {
		dispatch('previewFetch', e.detail);
	}

	function handlePreviewRefresh(e: CustomEvent<{ index: number }>) {
		dispatch('previewRefresh', e.detail);
	}

	// Source type configurations
	const sourceTypeConfig: Record<string, {
		icon: Component<{ size?: number; class?: string }>;
		label: string;
		color: string;
		bgClass: string;
		iconClass: string;
	}> = {
		hf: {
			icon: Cloud,
			label: 'HuggingFace',
			color: 'amber',
			bgClass: 'bg-amber-100 dark:bg-amber-900/30',
			iconClass: 'text-amber-600 dark:text-amber-400'
		},
		servicenow: {
			icon: Server,
			label: 'ServiceNow',
			color: 'emerald',
			bgClass: 'bg-emerald-100 dark:bg-emerald-900/30',
			iconClass: 'text-emerald-600 dark:text-emerald-400'
		},
		disk: {
			icon: HardDrive,
			label: 'Local File',
			color: 'blue',
			bgClass: 'bg-blue-100 dark:bg-blue-900/30',
			iconClass: 'text-blue-600 dark:text-blue-400'
		},
		memory: {
			icon: MemoryStick,
			label: 'In Memory',
			color: 'purple',
			bgClass: 'bg-purple-100 dark:bg-purple-900/30',
			iconClass: 'text-purple-600 dark:text-purple-400'
		}
	};

	let config = $derived(sourceTypeConfig[source.type || ''] || {
		icon: Database,
		label: 'Unknown',
		color: 'gray',
		bgClass: 'bg-gray-100 dark:bg-gray-800',
		iconClass: 'text-gray-500 dark:text-gray-400'
	});

	let Icon = $derived(config.icon);

	// Get source detail string
	function getSourceDetail(): string {
		switch (source.type) {
			case 'hf':
				return source.repo_id || 'No dataset specified';
			case 'servicenow':
				return source.table || 'No table specified';
			case 'disk':
				return source.file_path?.split('/').pop() || 'No file specified';
			case 'memory':
				const count = source.data?.length || 0;
				return `${count} record${count !== 1 ? 's' : ''}`;
			default:
				return 'Configure source';
		}
	}

	// Get additional details (compact)
	function getSecondaryBadges(): string[] {
		const badges: string[] = [];
		if (source.type === 'hf' && source.split) {
			badges.push(Array.isArray(source.split) ? source.split.join('/') : source.split);
		}
		if (source.type === 'disk' && source.file_format) {
			badges.push(source.file_format.toUpperCase());
		}
		if (source.streaming) badges.push('Stream');
		if (source.transformations?.length) badges.push(`${source.transformations.length}T`);
		if (source.limit) badges.push(`≤${source.limit}`);
		return badges;
	}

	let secondaryBadges = $derived(getSecondaryBadges());
</script>

<div class="group relative">
	<div class="bg-white dark:bg-gray-800 rounded-lg border transition-all overflow-hidden
		{isPrimary
			? 'border-amber-300 dark:border-amber-600'
			: (showPreview ? 'border-blue-300 dark:border-blue-600' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600')}">

		<!-- Header Row -->
		<div class="flex items-center gap-2 p-2">
			<!-- Icon -->
			<div class="flex-shrink-0 p-1.5 rounded-lg {config.bgClass}">
				<Icon size={14} class={config.iconClass} />
			</div>

			<!-- Content -->
			<div class="flex-1 min-w-0">
				<div class="flex items-center gap-1.5">
					<!-- Primary badge -->
					{#if isPrimary}
						<Crown size={10} class="text-amber-500 flex-shrink-0" />
					{/if}

					<!-- Alias or type label -->
					<span class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
						{#if showAlias && source.alias}
							{source.alias}
						{:else}
							{config.label}
						{/if}
					</span>

					<!-- Type badge (only if showing alias) -->
					{#if showAlias && source.alias}
						<span class="text-[10px] text-gray-400 dark:text-gray-500">
							{config.label}
						</span>
					{/if}
				</div>

				<!-- Detail line -->
				<div class="text-[10px] text-gray-500 dark:text-gray-400 font-mono truncate">
					{getSourceDetail()}
				</div>
			</div>

			<!-- Badges -->
			{#if secondaryBadges.length > 0}
				<div class="flex items-center gap-1 flex-shrink-0">
					{#each secondaryBadges.slice(0, 2) as badge}
						<span class="text-[9px] px-1 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">
							{badge}
						</span>
					{/each}
				</div>
			{/if}

			<!-- Join info badge -->
			{#if showJoinInfo && !isPrimary && source.join_type && source.join_type !== 'primary'}
				<div class="flex-shrink-0 flex items-center gap-1 px-1.5 py-0.5 bg-violet-50 dark:bg-violet-900/20 rounded text-[10px] text-violet-600 dark:text-violet-400">
					<Link size={9} />
					<span>{source.primary_key || 'key'}={source.join_key || 'key'}</span>
				</div>
			{/if}

			<!-- Edit Actions (only in edit mode) -->
			{#if isEditing}
				<div class="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
					{#if !isPrimary}
						<button
							onclick={() => dispatch('makePrimary')}
							class="p-1 rounded hover:bg-amber-100 dark:hover:bg-amber-900/30 text-gray-400 hover:text-amber-600 transition-colors"
							title="Make primary"
						>
							<Crown size={12} />
						</button>
					{/if}
					<button
						onclick={() => dispatch('edit')}
						class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 transition-colors"
						title="Edit"
					>
						<Edit3 size={12} />
					</button>
					{#if !isPrimary}
						<button
							onclick={() => dispatch('remove')}
							class="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-colors"
							title="Remove"
						>
							<Trash2 size={12} />
						</button>
					{/if}
				</div>
			{/if}

			<!-- Preview Toggle (always available when source is configured) -->
			{#if showPreviewToggle && source.type}
				<button
					onclick={handlePreviewToggle}
					class="flex items-center gap-1.5 px-2 py-1 text-xs rounded-md transition-colors flex-shrink-0
						{showPreview
							? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 font-medium'
							: 'text-gray-500 hover:text-blue-600 bg-gray-100 dark:bg-gray-700 hover:bg-blue-50 dark:hover:bg-blue-900/20'}"
					title={showPreview ? 'Hide preview' : 'Show preview'}
				>
					<Eye size={14} />
					<span>Preview</span>
					{#if showPreview}
						<ChevronUp size={12} />
					{:else}
						<ChevronDown size={12} />
					{/if}
				</button>
			{/if}
		</div>

		<!-- Expandable Preview Section -->
		{#if showPreview}
			<SourcePreview
				data={previewData}
				loading={previewLoading}
				sourceIndex={index}
				sourceAlias={source.alias}
				on:fetch={handlePreviewFetch}
				on:refresh={handlePreviewRefresh}
			/>
		{/if}
	</div>
</div>
