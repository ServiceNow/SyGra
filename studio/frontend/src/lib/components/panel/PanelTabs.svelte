<script lang="ts">
	import type { Component } from 'svelte';

	interface Tab {
		id: string;
		label: string;
		icon?: Component;
		badge?: number | string;
		hidden?: boolean;
	}

	interface Props {
		tabs: Tab[];
		activeTab: string;
		onTabChange: (tabId: string) => void;
	}

	let { tabs, activeTab, onTabChange }: Props = $props();

	// Filter visible tabs
	let visibleTabs = $derived(tabs.filter(tab => !tab.hidden));

	function handleKeyDown(event: KeyboardEvent, index: number) {
		const enabledTabs = visibleTabs;
		let newIndex = index;

		switch (event.key) {
			case 'ArrowLeft':
				event.preventDefault();
				newIndex = index === 0 ? enabledTabs.length - 1 : index - 1;
				break;
			case 'ArrowRight':
				event.preventDefault();
				newIndex = index === enabledTabs.length - 1 ? 0 : index + 1;
				break;
			case 'Home':
				event.preventDefault();
				newIndex = 0;
				break;
			case 'End':
				event.preventDefault();
				newIndex = enabledTabs.length - 1;
				break;
			default:
				return;
		}

		onTabChange(enabledTabs[newIndex].id);
	}
</script>

<div class="px-4 py-2 border-b border-gray-200 dark:border-gray-800">
	<div
		class="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-xl"
		role="tablist"
		aria-label="Panel tabs"
	>
		{#each visibleTabs as tab, index (tab.id)}
			{@const isActive = activeTab === tab.id}
			{@const Icon = tab.icon}
			<button
				onclick={() => onTabChange(tab.id)}
				onkeydown={(e) => handleKeyDown(e, index)}
				role="tab"
				aria-selected={isActive}
				aria-controls={`panel-${tab.id}`}
				tabindex={isActive ? 0 : -1}
				class="flex items-center justify-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg transition-all flex-1 min-w-0 {isActive
					? 'bg-white dark:bg-gray-900 text-violet-700 dark:text-violet-300 shadow-sm'
					: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'}"
			>
				{#if Icon}
					<Icon size={14} class="flex-shrink-0 {isActive ? 'text-violet-600 dark:text-violet-400' : ''}" />
				{/if}
				<span class="truncate">{tab.label}</span>
				{#if tab.badge !== undefined && tab.badge !== null && tab.badge !== 0}
					<span
						class="flex-shrink-0 px-1.5 py-0.5 text-[10px] font-semibold rounded-full {isActive
							? 'bg-violet-100 dark:bg-violet-900/50 text-violet-700 dark:text-violet-300'
							: 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400'}"
					>
						{tab.badge}
					</span>
				{/if}
			</button>
		{/each}
	</div>
</div>
