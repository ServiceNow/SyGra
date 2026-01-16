<script lang="ts">
	import { Music, ImageIcon, FileQuestion } from 'lucide-svelte';
	import AudioPlayer from './AudioPlayer.svelte';
	import {
		isAudio,
		isImage,
		detectMediaType,
		getMediaDisplayName,
		filePathToApiUrl,
		truncateDataUrl,
		isDataUrl
	} from '$lib/utils/mediaUtils';

	interface Props {
		value: unknown;
		fieldName?: string;
		workflowId?: string;
		compact?: boolean;
		maxImageHeight?: string;
		showLabel?: boolean;
	}

	let {
		value,
		fieldName = '',
		workflowId = '',
		compact = false,
		maxImageHeight = '200px',
		showLabel = false
	}: Props = $props();

	// Determine media type and prepare source URL
	// Now handles both string values and audio objects { src, type }
	let mediaType = $derived(detectMediaType(value));
	let mediaUrl = $derived(filePathToApiUrl(value, workflowId));
	let displayName = $derived(getMediaDisplayName(value));

	// Image state
	let imageLoaded = $state(false);
	let imageError = $state(false);
	let showFullImage = $state(false);

	function handleImageLoad() {
		imageLoaded = true;
		imageError = false;
	}

	function handleImageError() {
		imageLoaded = false;
		imageError = true;
	}

	function toggleFullImage() {
		showFullImage = !showFullImage;
	}
</script>

{#if mediaType === 'audio'}
	<!-- Audio content -->
	<div class="flex flex-col gap-1">
		{#if showLabel && fieldName}
			<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
				<Music size={12} />
				<span>{fieldName}</span>
			</div>
		{/if}
		<AudioPlayer
			src={mediaUrl}
			title={displayName}
			{compact}
			showDownload={!compact}
		/>
	</div>
{:else if mediaType === 'image'}
	<!-- Image content -->
	<div class="flex flex-col gap-1">
		{#if showLabel && fieldName}
			<div class="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
				<ImageIcon size={12} />
				<span>{fieldName}</span>
			</div>
		{/if}

		{#if imageError}
			<div class="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
				<FileQuestion size={16} class="text-gray-400" />
				<span class="text-xs text-gray-500 dark:text-gray-400">Failed to load image</span>
			</div>
		{:else}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<img
				src={mediaUrl}
				alt={displayName}
				class="rounded-lg border border-gray-200 dark:border-gray-700 object-contain cursor-pointer hover:opacity-90 transition-opacity"
				style="max-height: {compact ? '80px' : maxImageHeight}; max-width: 100%;"
				onload={handleImageLoad}
				onerror={handleImageError}
				onclick={toggleFullImage}
			/>
		{/if}
	</div>

	<!-- Full image modal -->
	{#if showFullImage}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
			onclick={toggleFullImage}
		>
			<img
				src={mediaUrl}
				alt={displayName}
				class="max-w-full max-h-full object-contain rounded-lg"
			/>
		</div>
	{/if}
{:else}
	<!-- Unknown/text content - just display as text -->
	{#if typeof value === 'string'}
		{#if isDataUrl(value)}
			<!-- Truncate data URLs for display -->
			<span class="text-sm text-gray-600 dark:text-gray-400 font-mono">
				{truncateDataUrl(value, 60)}
			</span>
		{:else}
			<span class="text-sm text-gray-900 dark:text-gray-100">
				{value}
			</span>
		{/if}
	{:else if value === null || value === undefined}
		<span class="text-sm text-gray-400 dark:text-gray-500 italic">null</span>
	{:else if typeof value === 'boolean'}
		<span class="px-2 py-0.5 rounded text-xs font-medium {value ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'}">
			{value ? 'true' : 'false'}
		</span>
	{:else if typeof value === 'number'}
		<span class="text-sm font-mono text-gray-900 dark:text-gray-100">
			{value.toLocaleString()}
		</span>
	{:else if typeof value === 'object'}
		<pre class="text-xs bg-gray-100 dark:bg-gray-800 p-2 rounded overflow-x-auto max-w-full">
			{JSON.stringify(value, null, 2)}
		</pre>
	{:else}
		<span class="text-sm text-gray-900 dark:text-gray-100">{String(value)}</span>
	{/if}
{/if}
