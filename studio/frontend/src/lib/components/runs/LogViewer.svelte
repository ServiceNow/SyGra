<script lang="ts">
	import { Search, Download, Copy, Check, ChevronUp, ChevronDown, X, Filter } from 'lucide-svelte';

	interface Props {
		logs: string[];
		title?: string;
	}

	let { logs, title = 'Logs' }: Props = $props();

	let searchQuery = $state('');
	let caseSensitive = $state(false);
	let showLineNumbers = $state(true);
	let autoScroll = $state(true);
	let copied = $state(false);
	let currentMatchIndex = $state(0);

	let logContainer: HTMLDivElement;

	// Filter logs based on search
	let filteredLogs = $derived(() => {
		if (!searchQuery) return logs.map((log, i) => ({ line: i + 1, text: log, matches: false }));

		const query = caseSensitive ? searchQuery : searchQuery.toLowerCase();
		return logs.map((log, i) => {
			const text = caseSensitive ? log : log.toLowerCase();
			const matches = text.includes(query);
			return { line: i + 1, text: log, matches };
		});
	});

	// Get matching line indices
	let matchingLines = $derived(() => {
		return filteredLogs().filter(l => l.matches).map(l => l.line);
	});

	let matchCount = $derived(matchingLines().length);

	// Navigate to next/previous match
	function goToNextMatch() {
		if (matchCount === 0) return;
		currentMatchIndex = (currentMatchIndex + 1) % matchCount;
		scrollToMatch();
	}

	function goToPrevMatch() {
		if (matchCount === 0) return;
		currentMatchIndex = (currentMatchIndex - 1 + matchCount) % matchCount;
		scrollToMatch();
	}

	function scrollToMatch() {
		const lineNum = matchingLines()[currentMatchIndex];
		const lineEl = document.querySelector(`[data-line="${lineNum}"]`);
		lineEl?.scrollIntoView({ behavior: 'smooth', block: 'center' });
	}

	async function copyLogs() {
		await navigator.clipboard.writeText(logs.join('\n'));
		copied = true;
		setTimeout(() => copied = false, 2000);
	}

	function downloadLogs() {
		const blob = new Blob([logs.join('\n')], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
		a.click();
		URL.revokeObjectURL(url);
	}

	function highlightText(text: string, query: string): string {
		if (!query) return text;
		const searchTerm = caseSensitive ? query : query.toLowerCase();
		const textToSearch = caseSensitive ? text : text.toLowerCase();
		const index = textToSearch.indexOf(searchTerm);
		if (index === -1) return text;

		const before = text.slice(0, index);
		const match = text.slice(index, index + query.length);
		const after = text.slice(index + query.length);
		return `${before}<mark class="bg-warning text-brand-primary px-0.5 rounded">${match}</mark>${after}`;
	}

	// Auto scroll to bottom when new logs arrive
	$effect(() => {
		if (autoScroll && logContainer && logs.length > 0) {
			logContainer.scrollTop = logContainer.scrollHeight;
		}
	});
</script>

<div class="flex flex-col h-full bg-gray-900 rounded-xl overflow-hidden">
	<!-- Toolbar -->
	<div class="flex-shrink-0 flex items-center justify-between gap-3 px-4 py-2 bg-gray-800 border-b border-gray-700">
		<div class="flex items-center gap-2">
			<span class="text-sm font-medium text-gray-300">{title}</span>
			<span class="text-xs text-gray-500">{logs.length} lines</span>
		</div>

		<!-- Search -->
		<div class="flex items-center gap-2 flex-1 max-w-md">
			<div class="relative flex-1">
				<Search size={14} class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" />
				<input
					type="text"
					placeholder="Search logs..."
					bind:value={searchQuery}
					class="w-full pl-8 pr-8 py-1.5 text-sm bg-gray-700 border border-gray-600 rounded text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-info"
				/>
				{#if searchQuery}
					<button
						onclick={() => searchQuery = ''}
						class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
					>
						<X size={14} />
					</button>
				{/if}
			</div>

			{#if searchQuery && matchCount > 0}
				<div class="flex items-center gap-1 text-xs text-gray-400">
					<span>{currentMatchIndex + 1}/{matchCount}</span>
					<button onclick={goToPrevMatch} class="p-1 hover:bg-gray-700 rounded" title="Previous match">
						<ChevronUp size={14} />
					</button>
					<button onclick={goToNextMatch} class="p-1 hover:bg-gray-700 rounded" title="Next match">
						<ChevronDown size={14} />
					</button>
				</div>
			{/if}
		</div>

		<!-- Actions -->
		<div class="flex items-center gap-1">
			<button
				onclick={() => caseSensitive = !caseSensitive}
				class="px-2 py-1 text-xs rounded transition-colors {caseSensitive ? 'bg-info text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-gray-300'}"
				title="Case sensitive"
			>
				Aa
			</button>
			<button
				onclick={() => showLineNumbers = !showLineNumbers}
				class="px-2 py-1 text-xs rounded transition-colors {showLineNumbers ? 'bg-info text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-gray-300'}"
				title="Toggle line numbers"
			>
				#
			</button>
			<div class="w-px h-4 bg-gray-600 mx-1"></div>
			<button
				onclick={copyLogs}
				class="p-1.5 text-gray-400 hover:text-gray-300 hover:bg-gray-700 rounded transition-colors"
				title="Copy all"
			>
				{#if copied}
					<Check size={14} class="text-success" />
				{:else}
					<Copy size={14} />
				{/if}
			</button>
			<button
				onclick={downloadLogs}
				class="p-1.5 text-gray-400 hover:text-gray-300 hover:bg-gray-700 rounded transition-colors"
				title="Download logs"
			>
				<Download size={14} />
			</button>
		</div>
	</div>

	<!-- Log content -->
	<div
		bind:this={logContainer}
		class="flex-1 overflow-auto font-mono text-sm"
	>
		{#if logs.length === 0}
			<div class="flex items-center justify-center h-full text-gray-500">
				No logs captured
			</div>
		{:else}
			<div class="p-2">
				{#each filteredLogs() as log}
					<div
						data-line={log.line}
						class="flex hover:bg-gray-800 rounded px-2 py-0.5 {log.matches && searchQuery ? 'bg-warning/20' : ''}"
					>
						{#if showLineNumbers}
							<span class="text-gray-600 select-none w-12 flex-shrink-0 text-right pr-4">{log.line}</span>
						{/if}
						<span class="text-gray-300 whitespace-pre-wrap break-all">
							{#if searchQuery && log.matches}
								{@html highlightText(log.text, searchQuery)}
							{:else}
								{log.text}
							{/if}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>
