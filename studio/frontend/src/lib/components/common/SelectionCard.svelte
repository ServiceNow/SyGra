<script lang="ts">
	import { Check } from 'lucide-svelte';
	import type { Component } from 'svelte';

	interface Props {
		selected?: boolean;
		disabled?: boolean;
		compact?: boolean;
		label: string;
		description?: string;
		icon?: Component<{ size?: number; class?: string }>;
		iconColor?: string;
		onclick?: () => void;
	}

	let {
		selected = false,
		disabled = false,
		compact = false,
		label,
		description,
		icon: Icon,
		iconColor = 'text-gray-500',
		onclick
	}: Props = $props();
</script>

<button
	type="button"
	{onclick}
	{disabled}
	class="group relative flex flex-col rounded-xl border-2 transition-all duration-200 overflow-hidden text-left w-full
		{disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
		{selected
			? 'border-violet-500 shadow-lg shadow-violet-500/20 dark:shadow-violet-500/10'
			: 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-md'}"
>
	<!-- Preview Slot -->
	<div class="relative {compact ? 'h-16' : 'h-24'} bg-gradient-to-b from-gray-50 to-white dark:from-gray-800 dark:to-gray-850 p-2 overflow-hidden">
		<!-- Default preview content if no slot provided -->
		{#if Icon}
			<div class="absolute inset-0 flex items-center justify-center opacity-20">
				<Icon size={compact ? 32 : 48} class={iconColor} />
			</div>
		{/if}
		<!-- Named slot for custom preview content -->
		<slot name="preview" />
	</div>

	<!-- Label Section -->
	<div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700">
		<div class="flex items-center gap-2 min-w-0">
			{#if Icon}
				<Icon size={16} class={iconColor} />
			{/if}
			<div class="min-w-0">
				<span class="text-sm font-medium text-gray-900 dark:text-gray-100 block truncate">
					{label}
				</span>
				{#if description && !compact}
					<span class="text-xs text-gray-500 dark:text-gray-400 block truncate">
						{description}
					</span>
				{/if}
			</div>
		</div>
		{#if selected}
			<div class="w-5 h-5 rounded-full bg-violet-500 flex items-center justify-center flex-shrink-0">
				<Check size={12} class="text-white" />
			</div>
		{/if}
	</div>
</button>
