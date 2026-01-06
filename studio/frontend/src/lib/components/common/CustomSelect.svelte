<script lang="ts">
	import { ChevronDown, Search, Check, X } from 'lucide-svelte';
	import { onMount } from 'svelte';

	interface Option {
		value: string;
		label: string;
		subtitle?: string;
		icon?: any;
	}

	interface Props {
		options: Option[];
		value: string;
		placeholder?: string;
		searchable?: boolean;
		searchPlaceholder?: string;
		disabled?: boolean;
		compact?: boolean;
		class?: string;
		onchange?: (value: string) => void;
	}

	let {
		options,
		value = $bindable(),
		placeholder = 'Select...',
		searchable = true,
		searchPlaceholder = 'Search...',
		disabled = false,
		compact = false,
		class: className = '',
		onchange
	}: Props = $props();

	let isOpen = $state(false);
	let searchQuery = $state('');
	let highlightedIndex = $state(0);
	let containerRef: HTMLDivElement;
	let searchInputRef: HTMLInputElement;
	let dropdownRef: HTMLDivElement;

	// Filter options based on search
	let filteredOptions = $derived(
		searchQuery
			? options.filter(opt =>
				opt.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
				(opt.subtitle?.toLowerCase().includes(searchQuery.toLowerCase()))
			)
			: options
	);

	// Get selected option
	let selectedOption = $derived(options.find(opt => opt.value === value));

	// Reset highlighted index when filtered options change
	$effect(() => {
		if (filteredOptions.length > 0) {
			highlightedIndex = 0;
		}
	});

	function toggle() {
		if (disabled) return;
		isOpen = !isOpen;
		if (isOpen) {
			searchQuery = '';
			highlightedIndex = 0;
			// Focus search input after opening
			setTimeout(() => searchInputRef?.focus(), 50);
		}
	}

	function selectOption(opt: Option) {
		value = opt.value;
		isOpen = false;
		searchQuery = '';
		onchange?.(opt.value);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!isOpen) {
			if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
				e.preventDefault();
				isOpen = true;
				setTimeout(() => searchInputRef?.focus(), 50);
			}
			return;
		}

		switch (e.key) {
			case 'Escape':
				e.preventDefault();
				isOpen = false;
				break;
			case 'ArrowDown':
				e.preventDefault();
				highlightedIndex = Math.min(highlightedIndex + 1, filteredOptions.length - 1);
				scrollToHighlighted();
				break;
			case 'ArrowUp':
				e.preventDefault();
				highlightedIndex = Math.max(highlightedIndex - 1, 0);
				scrollToHighlighted();
				break;
			case 'Enter':
				e.preventDefault();
				if (filteredOptions[highlightedIndex]) {
					selectOption(filteredOptions[highlightedIndex]);
				}
				break;
		}
	}

	function scrollToHighlighted() {
		const element = dropdownRef?.querySelector(`[data-index="${highlightedIndex}"]`);
		element?.scrollIntoView({ block: 'nearest' });
	}

	// Click outside handler
	function handleClickOutside(e: MouseEvent) {
		if (containerRef && !containerRef.contains(e.target as Node)) {
			isOpen = false;
		}
	}

	onMount(() => {
		document.addEventListener('click', handleClickOutside);
		return () => {
			document.removeEventListener('click', handleClickOutside);
		};
	});
</script>

<div
	bind:this={containerRef}
	class="relative {className}"
>
	<!-- Trigger Button -->
	<button
		type="button"
		onclick={toggle}
		onkeydown={handleKeydown}
		disabled={disabled}
		class="w-full flex items-center justify-between gap-2 text-left transition-all
			{compact ? 'px-2 py-1 text-xs rounded-md border-0 bg-transparent' : 'px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800'}
			{disabled ? 'opacity-50 cursor-not-allowed' : compact ? 'hover:bg-gray-100 dark:hover:bg-gray-700' : 'hover:border-[#52B8FF] dark:hover:border-[#7661FF] focus:ring-2 focus:ring-[#52B8FF] focus:border-[#52B8FF]'}
			{isOpen && !compact ? 'ring-2 ring-[#52B8FF] border-[#52B8FF]' : ''}"
	>
		<span class="flex-1 truncate {selectedOption ? (compact ? 'text-[#7661FF] dark:text-[#BF71F2] font-medium' : 'text-gray-800 dark:text-gray-200') : 'text-gray-500 dark:text-gray-400'}">
			{#if selectedOption}
				<span class="flex items-center gap-2">
					{#if selectedOption.icon}
						<svelte:component this={selectedOption.icon} size={compact ? 12 : 14} class="text-gray-500" />
					{/if}
					<span>{selectedOption.label}</span>
					{#if selectedOption.subtitle && !compact}
						<span class="text-xs text-gray-500">({selectedOption.subtitle})</span>
					{/if}
				</span>
			{:else}
				{placeholder}
			{/if}
		</span>
		<ChevronDown
			size={compact ? 12 : 16}
			class="text-gray-400 transition-transform {isOpen ? 'rotate-180' : ''}"
		/>
	</button>

	<!-- Dropdown Panel -->
	{#if isOpen}
		<div
			bind:this={dropdownRef}
			class="absolute z-50 mt-1 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden {compact ? 'min-w-32' : 'w-full'}"
			style="max-height: {compact ? '200px' : '300px'};"
		>
			<!-- Search Input -->
			{#if searchable}
				<div class="p-2 border-b border-gray-200 dark:border-gray-700">
					<div class="relative">
						<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
						<input
							bind:this={searchInputRef}
							bind:value={searchQuery}
							onkeydown={handleKeydown}
							type="text"
							placeholder={searchPlaceholder}
							class="w-full pl-8 pr-8 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-900 text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-[#52B8FF] focus:border-[#52B8FF]"
						/>
						{#if searchQuery}
							<button
								onclick={() => { searchQuery = ''; searchInputRef?.focus(); }}
								class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
							>
								<X size={14} />
							</button>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Options List -->
			<div class="overflow-y-auto" style="max-height: 240px;">
				{#if filteredOptions.length === 0}
					<div class="px-3 py-4 text-center text-sm text-gray-500">
						No options found
					</div>
				{:else}
					{#each filteredOptions as opt, index}
						<button
							type="button"
							data-index={index}
							onclick={() => selectOption(opt)}
							onmouseenter={() => highlightedIndex = index}
							class="w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors
								{opt.value === value ? 'bg-[#7661FF]/10 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]' : ''}
								{index === highlightedIndex ? 'bg-gray-100 dark:bg-gray-700' : 'hover:bg-gray-50 dark:hover:bg-gray-700/50'}"
						>
							{#if opt.icon}
								<svelte:component this={opt.icon} size={14} class="text-gray-500 flex-shrink-0" />
							{/if}
							<div class="flex-1 min-w-0">
								<div class="truncate text-gray-800 dark:text-gray-200">
									{opt.label}
								</div>
								{#if opt.subtitle}
									<div class="truncate text-xs text-gray-500 dark:text-gray-400">
										{opt.subtitle}
									</div>
								{/if}
							</div>
							{#if opt.value === value}
								<Check size={14} class="text-[#7661FF] dark:text-[#BF71F2] flex-shrink-0" />
							{/if}
						</button>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>
