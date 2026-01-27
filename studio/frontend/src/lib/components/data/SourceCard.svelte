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

	// Source type configurations using design tokens
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
			color: 'warning',
			bgClass: 'bg-warning-light',
			iconClass: 'text-warning'
		},
		servicenow: {
			icon: Server,
			label: 'ServiceNow',
			color: 'success',
			bgClass: 'bg-success-light',
			iconClass: 'text-success'
		},
		disk: {
			icon: HardDrive,
			label: 'Local File',
			color: 'info',
			bgClass: 'bg-info-light',
			iconClass: 'text-info'
		},
		memory: {
			icon: MemoryStick,
			label: 'In Memory',
			color: 'node-agent',
			bgClass: 'bg-node-agent-bg',
			iconClass: 'text-node-agent'
		}
	};

	let config = $derived(sourceTypeConfig[source.type || ''] || {
		icon: Database,
		label: 'Unknown',
		color: 'muted',
		bgClass: 'bg-surface-tertiary',
		iconClass: 'text-text-muted'
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
	<div class="bg-surface-elevated rounded-lg border transition-all overflow-hidden
		{isPrimary
			? 'border-warning'
			: (showPreview ? 'border-info' : 'border-surface-border hover:border-[var(--border-hover)]')}">

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
						<Crown size={10} class="text-warning flex-shrink-0" />
					{/if}

					<!-- Alias or type label -->
					<span class="text-xs font-medium text-text-primary truncate">
						{#if showAlias && source.alias}
							{source.alias}
						{:else}
							{config.label}
						{/if}
					</span>

					<!-- Type badge (only if showing alias) -->
					{#if showAlias && source.alias}
						<span class="text-[10px] text-text-muted">
							{config.label}
						</span>
					{/if}
				</div>

				<!-- Detail line -->
				<div class="text-[10px] text-text-secondary font-mono truncate">
					{getSourceDetail()}
				</div>
			</div>

			<!-- Badges -->
			{#if secondaryBadges.length > 0}
				<div class="flex items-center gap-1 flex-shrink-0">
					{#each secondaryBadges.slice(0, 2) as badge}
						<span class="text-[9px] px-1 py-0.5 bg-surface-tertiary text-text-secondary rounded">
							{badge}
						</span>
					{/each}
				</div>
			{/if}

			<!-- Join info badge -->
			{#if showJoinInfo && !isPrimary && source.join_type && source.join_type !== 'primary'}
				<div class="flex-shrink-0 flex items-center gap-1 px-1.5 py-0.5 bg-[#7661FF]/10 dark:bg-[#7661FF]/15 rounded text-[10px] text-[#7661FF] dark:text-[#52B8FF]">
					<Link size={9} />
					<span>{source.primary_key || 'key'}={source.join_key || 'key'}</span>
				</div>
			{/if}

			<!-- Edit Actions (only in edit mode) -->
			{#if isEditing}
				<div class="flex items-center gap-0.5 flex-shrink-0">
					{#if !isPrimary}
						<button
							onclick={() => dispatch('makePrimary')}
							class="p-1 rounded hover:bg-warning-light text-text-muted hover:text-warning transition-colors"
							title="Make primary"
						>
							<Crown size={12} />
						</button>
					{/if}
					<button
						onclick={() => dispatch('edit')}
						class="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text-secondary transition-colors"
						title="Edit"
					>
						<Edit3 size={12} />
					</button>
					{#if !isPrimary}
						<button
							onclick={() => dispatch('remove')}
							class="p-1 rounded hover:bg-error-light text-text-muted hover:text-error transition-colors"
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
							? 'bg-info-light text-info font-medium'
							: 'text-text-muted hover:text-info bg-surface-tertiary hover:bg-info-light'}"
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
