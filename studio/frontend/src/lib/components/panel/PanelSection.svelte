<script lang="ts">
	import { ChevronDown, ChevronRight } from 'lucide-svelte';
	import type { Snippet, Component } from 'svelte';

	interface Props {
		title: string;
		icon?: Component;
		badge?: string | number;
		defaultOpen?: boolean;
		collapsible?: boolean;
		variant?: 'default' | 'compact';
		children: Snippet;
	}

	let {
		title,
		icon: Icon,
		badge,
		defaultOpen = true,
		collapsible = true,
		variant = 'default',
		children
	}: Props = $props();

	let isOpen = $state(defaultOpen);

	function toggle() {
		if (collapsible) {
			isOpen = !isOpen;
		}
	}

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			toggle();
		}
	}
</script>

<div class="border-b border-gray-100 dark:border-gray-800 last:border-b-0">
	<!-- Section Header -->
	{#if collapsible}
		<button
			onclick={toggle}
			onkeydown={handleKeyDown}
			class="w-full flex items-center justify-between gap-2 px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group"
			aria-expanded={isOpen}
		>
			<div class="flex items-center gap-2 min-w-0">
				{#if Icon}
					<Icon size={14} class="text-gray-400 dark:text-gray-500 flex-shrink-0" />
				{/if}
				<span class="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide truncate">
					{title}
				</span>
				{#if badge !== undefined && badge !== null}
					<span class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 flex-shrink-0">
						{badge}
					</span>
				{/if}
			</div>
			<div class="flex-shrink-0 text-gray-400 dark:text-gray-500 transition-transform duration-200 {isOpen ? 'rotate-0' : '-rotate-90'}">
				<ChevronDown size={14} />
			</div>
		</button>
	{:else}
		<div class="flex items-center gap-2 px-4 py-3">
			{#if Icon}
				<Icon size={14} class="text-gray-400 dark:text-gray-500 flex-shrink-0" />
			{/if}
			<span class="text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide truncate">
				{title}
			</span>
			{#if badge !== undefined && badge !== null}
				<span class="px-1.5 py-0.5 text-[10px] font-medium rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 flex-shrink-0">
					{badge}
				</span>
			{/if}
		</div>
	{/if}

	<!-- Section Content -->
	{#if isOpen || !collapsible}
		<div
			class="overflow-hidden transition-all duration-200 ease-out {variant === 'compact' ? 'px-4 pb-3' : 'px-4 pb-4'}"
		>
			{@render children()}
		</div>
	{/if}
</div>
