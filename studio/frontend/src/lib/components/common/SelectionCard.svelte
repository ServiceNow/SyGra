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
			? 'border-info shadow-lg shadow-info/20'
			: 'border-surface-border hover:border-info/50 hover:shadow-md'}"
>
	<!-- Preview Slot -->
	<div class="relative {compact ? 'h-16' : 'h-24'} bg-gradient-to-b from-surface-secondary to-surface p-2 overflow-hidden">
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
	<div class="flex items-center justify-between p-3 bg-surface border-t border-surface-border">
		<div class="flex items-center gap-2 min-w-0">
			{#if Icon}
				<Icon size={16} class={iconColor} />
			{/if}
			<div class="min-w-0">
				<span class="text-sm font-medium text-text-primary block truncate">
					{label}
				</span>
				{#if description && !compact}
					<span class="text-xs text-text-muted block truncate">
						{description}
					</span>
				{/if}
			</div>
		</div>
		{#if selected}
			<div class="w-5 h-5 rounded-full bg-info flex items-center justify-center flex-shrink-0">
				<Check size={12} class="text-white" />
			</div>
		{/if}
	</div>
</button>
