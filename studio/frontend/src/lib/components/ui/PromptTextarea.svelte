<script lang="ts">
	import { tick } from 'svelte';
	import { Database, Zap, Shuffle, Settings, ChevronRight } from 'lucide-svelte';
	import type { StateVariable } from '$lib/utils/stateVariables';
	import { filterVariables } from '$lib/utils/stateVariables';

	interface Props {
		value: string;
		variables: StateVariable[];
		placeholder?: string;
		rows?: number;
		class?: string;
		oninput?: (value: string) => void;
		onchange?: (value: string) => void;
	}

	let {
		value = $bindable(),
		variables,
		placeholder = 'Enter prompt content...',
		rows = 6,
		class: className = '',
		oninput,
		onchange
	}: Props = $props();

	let textareaRef: HTMLTextAreaElement | undefined = $state();
	let dropdownRef: HTMLDivElement | undefined = $state();
	let showAutocomplete = $state(false);
	let autocompletePosition = $state({ top: 0, left: 0 });
	let searchQuery = $state('');
	let selectedIndex = $state(0);
	let bracePosition = $state(0);

	// Filter variables based on search query
	let filteredVariables = $derived(filterVariables(variables, searchQuery));

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
			default: return ChevronRight;
		}
	}

	function getCursorCoordinates(): { top: number; left: number } {
		if (!textareaRef) return { top: 0, left: 0 };

		// Create a mirror element to calculate cursor position
		const mirror = document.createElement('div');
		const computed = getComputedStyle(textareaRef);

		// Copy relevant styles
		const stylesToCopy = [
			'fontFamily', 'fontSize', 'fontWeight', 'fontStyle',
			'letterSpacing', 'textTransform', 'wordSpacing',
			'textIndent', 'whiteSpace', 'wordWrap', 'wordBreak',
			'padding', 'paddingLeft', 'paddingRight', 'paddingTop', 'paddingBottom',
			'border', 'borderLeft', 'borderRight', 'borderTop', 'borderBottom',
			'boxSizing', 'lineHeight'
		];

		stylesToCopy.forEach(prop => {
			mirror.style[prop as any] = computed[prop as any];
		});

		mirror.style.position = 'absolute';
		mirror.style.visibility = 'hidden';
		mirror.style.whiteSpace = 'pre-wrap';
		mirror.style.width = `${textareaRef.offsetWidth}px`;
		mirror.style.overflow = 'hidden';

		// Get text up to cursor
		const textBeforeCursor = value.substring(0, textareaRef.selectionStart);
		mirror.textContent = textBeforeCursor;

		// Add a span to mark cursor position
		const cursorSpan = document.createElement('span');
		cursorSpan.textContent = '|';
		mirror.appendChild(cursorSpan);

		document.body.appendChild(mirror);

		// Get position
		const rect = textareaRef.getBoundingClientRect();
		const spanRect = cursorSpan.getBoundingClientRect();
		const mirrorRect = mirror.getBoundingClientRect();

		// Calculate relative position
		const relativeTop = spanRect.top - mirrorRect.top;
		const relativeLeft = spanRect.left - mirrorRect.left;

		document.body.removeChild(mirror);

		// Adjust for scroll and add offset
		const scrollTop = textareaRef.scrollTop;

		return {
			top: rect.top + relativeTop - scrollTop + 24,
			left: Math.min(rect.left + relativeLeft, window.innerWidth - 320)
		};
	}

	function openAutocomplete() {
		if (!textareaRef) return;
		bracePosition = textareaRef.selectionStart;
		searchQuery = '';
		selectedIndex = 0;
		autocompletePosition = getCursorCoordinates();
		showAutocomplete = true;
	}

	function closeAutocomplete() {
		showAutocomplete = false;
		searchQuery = '';
		selectedIndex = 0;
	}

	function selectVariable(variable: StateVariable) {
		if (!textareaRef) return;

		// The { was already typed and is included in `before` (bracePosition is after the {)
		// We just need to add the variable name and closing }
		const before = value.substring(0, bracePosition);
		const after = value.substring(textareaRef.selectionStart);

		value = before + variable.name + '}' + after;

		// Move cursor after the inserted variable (+1 for the closing })
		const newCursorPos = bracePosition + variable.name.length + 1;

		tick().then(() => {
			if (textareaRef) {
				textareaRef.selectionStart = newCursorPos;
				textareaRef.selectionEnd = newCursorPos;
				textareaRef.focus();
			}
		});

		oninput?.(value);
		closeAutocomplete();
	}

	function handleKeyDown(event: KeyboardEvent) {
		if (event.key === '{' && !showAutocomplete) {
			// Don't prevent default - let { be typed
			// Open autocomplete after a tick so the { is in the value
			setTimeout(() => {
				openAutocomplete();
			}, 0);
			return;
		}

		if (!showAutocomplete) return;

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
				closeAutocomplete();
				break;
			case '}':
				closeAutocomplete();
				break;
			case 'Backspace':
				if (searchQuery.length > 0) {
					searchQuery = searchQuery.slice(0, -1);
					selectedIndex = 0;
				} else {
					// User deleted the opening brace
					closeAutocomplete();
				}
				break;
			default:
				// Add to search query if it's a printable character
				if (event.key.length === 1 && !event.ctrlKey && !event.metaKey) {
					searchQuery += event.key;
					selectedIndex = 0;
				}
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
		const target = event.target as HTMLTextAreaElement;
		value = target.value;

		// Check if we should close autocomplete
		if (showAutocomplete && textareaRef) {
			const cursorPos = textareaRef.selectionStart;
			const textBeforeCursor = value.substring(0, cursorPos);
			const lastBracePos = textBeforeCursor.lastIndexOf('{');

			if (lastBracePos === -1 || textBeforeCursor.substring(lastBracePos).includes('}')) {
				closeAutocomplete();
			}
		}

		oninput?.(value);
	}

	function handleChange(event: Event) {
		const target = event.target as HTMLTextAreaElement;
		onchange?.(target.value);
	}

	function handleBlur(event: FocusEvent) {
		// Don't close if clicking inside dropdown
		const relatedTarget = event.relatedTarget as HTMLElement;
		if (relatedTarget && dropdownRef?.contains(relatedTarget)) {
			return;
		}
		// Small delay to allow click events on dropdown items
		setTimeout(() => {
			if (showAutocomplete) {
				closeAutocomplete();
			}
		}, 150);
	}
</script>

<div class="relative">
	<textarea
		bind:this={textareaRef}
		{value}
		{placeholder}
		{rows}
		class="w-full px-3 py-2 text-sm bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 border border-gray-300 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent resize-none font-mono {className}"
		onkeydown={handleKeyDown}
		oninput={handleInput}
		onchange={handleChange}
		onblur={handleBlur}
	></textarea>

	{#if showAutocomplete && filteredVariables.length > 0}
		<div
			bind:this={dropdownRef}
			class="fixed z-[9999] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-xl overflow-hidden"
			style="top: {autocompletePosition.top}px; left: {autocompletePosition.left}px; min-width: 280px; max-width: 380px; max-height: 280px;"
		>
			<!-- Search indicator -->
			{#if searchQuery}
				<div class="px-3 py-1.5 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
					<span class="text-xs text-gray-500 dark:text-gray-400">Filter: </span>
					<span class="text-xs font-mono text-gray-700 dark:text-gray-300">{searchQuery}</span>
				</div>
			{/if}

			<!-- Variables list -->
			<div class="overflow-y-auto max-h-[220px]">
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
	{/if}
</div>
