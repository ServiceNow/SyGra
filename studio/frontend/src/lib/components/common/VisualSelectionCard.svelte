<script lang="ts">
	import { Check } from 'lucide-svelte';
	import type { Component, Snippet } from 'svelte';

	interface Props {
		selected?: boolean;
		disabled?: boolean;
		size?: 'xs' | 'sm' | 'md' | 'lg';
		label: string;
		description?: string;
		icon?: Component<{ size?: number; class?: string }>;
		iconBgClass?: string;
		iconClass?: string;
		previewBgClass?: string;
		onclick?: () => void;
		preview?: Snippet;
	}

	let {
		selected = false,
		disabled = false,
		size = 'md',
		label,
		description,
		icon: Icon,
		iconBgClass = 'bg-gray-100 dark:bg-gray-700',
		iconClass = 'text-gray-500 dark:text-gray-400',
		previewBgClass = 'bg-gradient-to-b from-gray-50 to-white dark:from-gray-800 dark:to-gray-900',
		onclick,
		preview
	}: Props = $props();

	const sizeClasses = {
		xs: { preview: 'h-10', icon: 20, labelIcon: 10, padding: 'p-1.5', labelText: 'text-[11px]', border: 'border', radius: 'rounded-lg' },
		sm: { preview: 'h-14', icon: 28, labelIcon: 12, padding: 'p-2', labelText: 'text-xs', border: 'border-2', radius: 'rounded-xl' },
		md: { preview: 'h-20', icon: 36, labelIcon: 14, padding: 'p-3', labelText: 'text-sm', border: 'border-2', radius: 'rounded-xl' },
		lg: { preview: 'h-28', icon: 48, labelIcon: 16, padding: 'p-4', labelText: 'text-sm', border: 'border-2', radius: 'rounded-xl' }
	};

	let sizeConfig = $derived(sizeClasses[size]);
</script>

<button
	type="button"
	{onclick}
	{disabled}
	class="group relative flex flex-col {sizeConfig.radius} {sizeConfig.border} transition-all duration-200 overflow-hidden text-left w-full
		{disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
		{selected
			? 'border-violet-500 shadow-lg shadow-violet-500/20 dark:shadow-violet-500/10 ring-1 ring-violet-500/30'
			: 'border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md'}"
>
	<!-- Preview Area -->
	<div class="relative {sizeConfig.preview} {previewBgClass} overflow-hidden">
		<!-- Subtle grid pattern background -->
		<div class="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
			style="background-image: radial-gradient(circle, currentColor 1px, transparent 1px); background-size: 12px 12px;">
		</div>

		<!-- Custom preview content -->
		{#if preview}
			{@render preview()}
		{:else if Icon}
			<!-- Default: centered icon -->
			<div class="absolute inset-0 flex items-center justify-center">
				<div class="{size === 'xs' ? 'p-1.5 rounded-lg' : size === 'sm' ? 'p-2 rounded-lg' : 'p-3 rounded-xl'} {iconBgClass} shadow-sm transition-transform duration-200 group-hover:scale-105">
					<Icon size={sizeConfig.icon} class={iconClass} />
				</div>
			</div>
		{/if}

		<!-- Selected indicator glow -->
		{#if selected}
			<div class="absolute inset-0 bg-violet-500/5 dark:bg-violet-400/10"></div>
		{/if}
	</div>

	<!-- Label Section -->
	<div class="flex items-center justify-between {sizeConfig.padding} bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700/50">
		<div class="flex items-center gap-1.5 min-w-0 flex-1">
			{#if Icon}
				<Icon size={sizeConfig.labelIcon} class="{selected ? 'text-violet-500' : iconClass} transition-colors flex-shrink-0" />
			{/if}
			<div class="min-w-0 flex-1">
				<span class="{sizeConfig.labelText} font-medium {selected ? 'text-violet-700 dark:text-violet-300' : 'text-gray-900 dark:text-gray-100'} block truncate transition-colors">
					{label}
				</span>
				{#if description && size !== 'sm' && size !== 'xs'}
					<span class="text-xs text-gray-500 dark:text-gray-400 block truncate mt-0.5">
						{description}
					</span>
				{/if}
			</div>
		</div>

		<!-- Checkmark -->
		{#if selected}
			<div class="{size === 'xs' ? 'w-4 h-4' : 'w-5 h-5'} rounded-full bg-violet-500 flex items-center justify-center flex-shrink-0 shadow-sm">
				<Check size={size === 'xs' ? 10 : 12} class="text-white" strokeWidth={3} />
			</div>
		{:else}
			<div class="{size === 'xs' ? 'w-4 h-4' : 'w-5 h-5'} rounded-full border-2 border-gray-200 dark:border-gray-600 flex-shrink-0 group-hover:border-violet-300 dark:group-hover:border-violet-500 transition-colors"></div>
		{/if}
	</div>
</button>
