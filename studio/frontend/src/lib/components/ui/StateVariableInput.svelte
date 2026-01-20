<script lang="ts">
	import { tick } from 'svelte';
	import { Database, Zap, Shuffle, Settings, ChevronDown, X } from 'lucide-svelte';
	import type { StateVariable } from '$lib/utils/stateVariables';
	import { filterVariables } from '$lib/utils/stateVariables';

	interface Props {
		value: string;
		variables: StateVariable[];
		placeholder?: string;
		class?: string;
		oninput?: (value: string) => void;
		onchange?: (value: string) => void;
	}

	let {
		value = $bindable(),
		variables,
		placeholder = 'Select or type a variable...',
		class: className = '',
		oninput,
		onchange
	}: Props = $props();

	let inputRef: HTMLInputElement | undefined = $state();
	let dropdownRef: HTMLDivElement | undefined = $state();
	let containerRef: HTMLDivElement | undefined = $state();
	let showDropdown = $state(false);
	let searchQuery = $state('');
	let selectedIndex = $state(0);

	// Filter variables based on search query (use input value as query when dropdown is open)
	let filteredVariables = $derived(filterVariables(variables, searchQuery || value));

	// Group variables by source for display
	function getGroupedVariables() {
		const groups: { source: string; label: string; icon: typeof Database; color: string; variables: StateVariable[] }[] = [];

		const dataVars = filteredVariables.filter(v => v.source === 'data');
		const outputVars = filteredVariables.filter(v => v.source === 'output');
		const samplerVars = filteredVariables.filter(v => v.source === 'sampler');
		const frameworkVars = filteredVariables.filter(v => v.source === 'framework');

		if (dataVars.length > 0) {
			groups.push({ source: 'data', label: 'Data Columns', icon: Database, color: 'text-blue-500', variables: dataVars });
		}
		if (outputVars.length > 0) {
			groups.push({ source: 'output', label: 'Node Outputs', icon: Zap, color: 'text-green-500', variables: outputVars });
		}
		if (samplerVars.length > 0) {
			groups.push({ source: 'sampler', label: 'Sampler', icon: Shuffle, color: 'text-purple-500', variables: samplerVars });
		}
		if (frameworkVars.length > 0) {
			groups.push({ source: 'framework', label: 'Framework', icon: Settings, color: 'text-gray-500', variables: frameworkVars });
		}

		return groups;
	}

	function getSourceColor(source: string) {
		switch (source) {
			case 'data': return 'text-blue-500';
			case 'output': return 'text-green-500';
			case 'sampler': return 'text-purple-500';
			case 'framework': return 'text-gray-500';
			default: return 'text-gray-500';
		}
	}

	function getSourceIcon(source: string) {
		switch (source) {
			case 'data': return Database;
			case 'output': return Zap;
			case 'sampler': return Shuffle;
			case 'framework': return Settings;
			default: return Database;
		}
	}

	function openDropdown() {
		searchQuery = '';
		selectedIndex = 0;
		showDropdown = true;
	}

	function closeDropdown() {
		showDropdown = false;
		searchQuery = '';
		selectedIndex = 0;
	}

	function selectVariable(variable: StateVariable) {
		value = variable.name;
		oninput?.(value);
		onchange?.(value);
		closeDropdown();
		// Keep focus on input
		tick().then(() => inputRef?.focus());
	}

	function handleKeyDown(event: KeyboardEvent) {
		if (!showDropdown) {
			if (event.key === 'ArrowDown' || event.key === 'Enter') {
				event.preventDefault();
				openDropdown();
			}
			return;
		}

		switch (event.key) {
			case 'ArrowDown':
				event.preventDefault();
				selectedIndex = Math.min(selectedIndex + 1, filteredVariables.length - 1);
				scrollToSelected();
				break;
			case 'ArrowUp':
				event.preventDefault();
				selectedIndex = Math.max(selectedIndex - 1, 0);
				scrollToSelected();
				break;
			case 'Enter':
			case 'Tab':
				if (filteredVariables[selectedIndex]) {
					event.preventDefault();
					selectVariable(filteredVariables[selectedIndex]);
				}
				break;
			case 'Escape':
				event.preventDefault();
				closeDropdown();
				break;
		}
	}

	function scrollToSelected() {
		if (dropdownRef) {
			const selectedEl = dropdownRef.querySelector(`[data-index="${selectedIndex}"]`);
			if (selectedEl) {
				selectedEl.scrollIntoView({ block: 'nearest' });
			}
		}
	}

	function handleInput(event: Event) {
		const target = event.target as HTMLInputElement;
		value = target.value;
		searchQuery = target.value;
		selectedIndex = 0;

		if (!showDropdown && target.value) {
			openDropdown();
		}

		oninput?.(value);
	}

	function handleFocus() {
		openDropdown();
	}

	function handleBlur(event: FocusEvent) {
		// Don't close if clicking inside dropdown
		const relatedTarget = event.relatedTarget as HTMLElement;
		if (relatedTarget && containerRef?.contains(relatedTarget)) {
			return;
		}
		// Small delay to allow click events on dropdown items
		setTimeout(() => {
			if (showDropdown) {
				closeDropdown();
			}
		}, 150);
	}

	function clearValue() {
		value = '';
		oninput?.('');
		onchange?.('');
		inputRef?.focus();
	}

	function toggleDropdown() {
		if (showDropdown) {
			closeDropdown();
		} else {
			openDropdown();
			inputRef?.focus();
		}
	}
</script>

<div bind:this={containerRef} class="relative {className}">
	<div class="flex items-center">
		<div class="relative flex-1">
			<input
				bind:this={inputRef}
				type="text"
				{value}
				{placeholder}
				class="w-full px-3 py-2 pr-16 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				onkeydown={handleKeyDown}
				oninput={handleInput}
				onfocus={handleFocus}
				onblur={handleBlur}
			/>
			<div class="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
				{#if value}
					<button
						type="button"
						onclick={clearValue}
						class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
						title="Clear"
					>
						<X size={14} />
					</button>
				{/if}
				<button
					type="button"
					onclick={toggleDropdown}
					class="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded transition-colors"
					title="Show variables"
				>
					<ChevronDown size={14} class="transition-transform {showDropdown ? 'rotate-180' : ''}" />
				</button>
			</div>
		</div>
	</div>

	{#if showDropdown && filteredVariables.length > 0}
		<div
			bind:this={dropdownRef}
			class="absolute z-50 mt-1 w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl overflow-hidden"
			style="max-height: 280px;"
		>
			<!-- Variables list -->
			<div class="overflow-y-auto max-h-[240px]">
				{#each getGroupedVariables() as group}
					<div class="py-0.5">
						<!-- Group header -->
						<div class="px-3 py-1 text-[10px] font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider bg-gray-50 dark:bg-gray-900/50 flex items-center gap-1.5 sticky top-0">
							<svelte:component this={group.icon} size={10} class={group.color} />
							{group.label}
						</div>
						<!-- Variables in group -->
						{#each group.variables as variable}
							{@const globalIdx = filteredVariables.indexOf(variable)}
							<button
								type="button"
								data-index={globalIdx}
								class="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors {globalIdx === selectedIndex ? 'bg-blue-50 dark:bg-blue-900/30' : ''}"
								onclick={() => selectVariable(variable)}
								onmouseenter={() => selectedIndex = globalIdx}
							>
								<span class="{getSourceColor(variable.source)}">
									<svelte:component this={getSourceIcon(variable.source)} size={12} />
								</span>
								<div class="flex-1 min-w-0">
									<div class="font-mono text-sm text-gray-800 dark:text-gray-200 truncate">
										{variable.name}
									</div>
									{#if variable.description}
										<div class="text-[10px] text-gray-500 dark:text-gray-400 truncate">
											{variable.description}
										</div>
									{/if}
								</div>
								{#if variable.sourceNode && variable.sourceNode !== 'DATA'}
									<span class="text-[10px] px-1 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-gray-500 dark:text-gray-400 shrink-0">
										{variable.sourceNode}
									</span>
								{/if}
							</button>
						{/each}
					</div>
				{/each}
			</div>

			<!-- Footer hint -->
			<div class="px-2 py-1 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 text-[10px] text-gray-500 dark:text-gray-400 flex items-center gap-3">
				<span class="inline-flex items-center gap-1">
					<kbd class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">↑↓</kbd> navigate
				</span>
				<span class="inline-flex items-center gap-1">
					<kbd class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">Enter</kbd> select
				</span>
				<span class="inline-flex items-center gap-1">
					<kbd class="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">Esc</kbd> close
				</span>
			</div>
		</div>
	{:else if showDropdown && filteredVariables.length === 0}
		<div
			class="absolute z-50 mt-1 w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden"
		>
			<div class="px-3 py-4 text-center text-sm text-gray-500 dark:text-gray-400">
				No matching variables found
			</div>
		</div>
	{/if}
</div>
