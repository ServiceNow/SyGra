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
			{compact ? 'px-2 py-1 text-xs rounded-md border-0 bg-transparent' : 'px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface'}
			{disabled ? 'opacity-50 cursor-not-allowed' : compact ? 'hover:bg-surface-hover' : 'hover:border-info focus:ring-2 focus:ring-info focus:border-info'}
			{isOpen && !compact ? 'ring-2 ring-info border-info' : ''}"
	>
		<span class="flex-1 truncate {selectedOption ? (compact ? 'text-info font-medium' : 'text-text-primary') : 'text-text-muted'}">
			{#if selectedOption}
				<span class="flex items-center gap-2">
					{#if selectedOption.icon}
						<svelte:component this={selectedOption.icon} size={compact ? 12 : 14} class="text-text-muted" />
					{/if}
					<span>{selectedOption.label}</span>
					{#if selectedOption.subtitle && !compact}
						<span class="text-xs text-text-muted">({selectedOption.subtitle})</span>
					{/if}
				</span>
			{:else}
				{placeholder}
			{/if}
		</span>
		<ChevronDown
			size={compact ? 12 : 16}
			class="text-text-muted transition-transform {isOpen ? 'rotate-180' : ''}"
		/>
	</button>

	<!-- Dropdown Panel -->
	{#if isOpen}
		<div
			bind:this={dropdownRef}
			class="absolute z-50 mt-1 bg-surface border border-surface-border rounded-lg shadow-lg overflow-hidden {compact ? 'min-w-32' : 'w-full'}"
			style="max-height: {compact ? '200px' : '300px'};"
		>
			<!-- Search Input -->
			{#if searchable}
				<div class="p-2 border-b border-surface-border">
					<div class="relative">
						<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
						<input
							bind:this={searchInputRef}
							bind:value={searchQuery}
							onkeydown={handleKeydown}
							type="text"
							placeholder={searchPlaceholder}
							class="w-full pl-8 pr-8 py-1.5 text-sm border border-surface-border rounded-md bg-surface-secondary text-text-primary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-info focus:border-info"
						/>
						{#if searchQuery}
							<button
								onclick={() => { searchQuery = ''; searchInputRef?.focus(); }}
								class="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
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
					<div class="px-3 py-4 text-center text-sm text-text-muted">
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
								{opt.value === value ? 'bg-info-light text-info' : ''}
								{index === highlightedIndex ? 'bg-surface-hover' : 'hover:bg-surface-secondary'}"
						>
							{#if opt.icon}
								<svelte:component this={opt.icon} size={14} class="text-text-muted flex-shrink-0" />
							{/if}
							<div class="flex-1 min-w-0">
								<div class="truncate text-text-primary">
									{opt.label}
								</div>
								{#if opt.subtitle}
									<div class="truncate text-xs text-text-muted">
										{opt.subtitle}
									</div>
								{/if}
							</div>
							{#if opt.value === value}
								<Check size={14} class="text-info flex-shrink-0" />
							{/if}
						</button>
					{/each}
				{/if}
			</div>
		</div>
	{/if}
</div>
