<script lang="ts">
	import type { SkipRecordsParams } from '$lib/stores/workflow.svelte';
	import { Info } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, isEditing = false, onUpdate }: Props = $props();

	// Parse params as SkipRecordsParams
	let skipType = $state<'range' | 'count'>((params.skip_type as 'range' | 'count') || 'count');
	let range = $state((params.range as string) || '[:10],[-10:]');
	let fromStart = $state((params.count as { from_start?: number })?.from_start || 0);
	let fromEnd = $state((params.count as { from_end?: number })?.from_end || 0);

	// Sync local state with params
	$effect(() => {
		skipType = (params.skip_type as 'range' | 'count') || 'count';
		range = (params.range as string) || '[:10],[-10:]';
		const count = params.count as { from_start?: number; from_end?: number } | undefined;
		fromStart = count?.from_start || 0;
		fromEnd = count?.from_end || 0;
	});

	function emitUpdate() {
		const newParams: SkipRecordsParams = {
			skip_type: skipType,
		};

		if (skipType === 'range') {
			newParams.range = range;
		} else {
			newParams.count = {
				from_start: fromStart,
				from_end: fromEnd
			};
		}

		onUpdate(newParams);
	}

	function handleSkipTypeChange(type: 'range' | 'count') {
		skipType = type;
		emitUpdate();
	}
</script>

<div class="space-y-4">
	<!-- Skip Type Selection -->
	<div>
		<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">Skip Type</label>
		{#if isEditing}
			<div class="flex gap-2">
				<button
					onclick={() => handleSkipTypeChange('count')}
					class="flex-1 px-3 py-2 text-sm rounded-lg border transition-all
						{skipType === 'count'
							? 'bg-violet-50 dark:bg-violet-900/30 border-violet-300 dark:border-violet-600 text-violet-700 dark:text-violet-300'
							: 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'}"
				>
					By Count
				</button>
				<button
					onclick={() => handleSkipTypeChange('range')}
					class="flex-1 px-3 py-2 text-sm rounded-lg border transition-all
						{skipType === 'range'
							? 'bg-violet-50 dark:bg-violet-900/30 border-violet-300 dark:border-violet-600 text-violet-700 dark:text-violet-300'
							: 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'}"
				>
					By Range
				</button>
			</div>
		{:else}
			<div class="text-sm text-gray-800 dark:text-gray-200 capitalize">
				{skipType === 'count' ? 'By Count' : 'By Range'}
			</div>
		{/if}
	</div>

	{#if skipType === 'count'}
		<!-- Count Mode -->
		<div class="grid grid-cols-2 gap-4">
			<div>
				<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
					Skip from Start
				</label>
				{#if isEditing}
					<input
						type="number"
						bind:value={fromStart}
						onchange={emitUpdate}
						min="0"
						class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
					/>
				{:else}
					<div class="text-sm font-mono text-gray-800 dark:text-gray-200">
						{fromStart} records
					</div>
				{/if}
			</div>
			<div>
				<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
					Skip from End
				</label>
				{#if isEditing}
					<input
						type="number"
						bind:value={fromEnd}
						onchange={emitUpdate}
						min="0"
						class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
					/>
				{:else}
					<div class="text-sm font-mono text-gray-800 dark:text-gray-200">
						{fromEnd} records
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<!-- Range Mode -->
		<div>
			<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
				Range Pattern
			</label>
			{#if isEditing}
				<input
					type="text"
					bind:value={range}
					onchange={emitUpdate}
					placeholder="[:10],[-10:]"
					class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
				/>
				<div class="mt-2 flex items-start gap-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-xs text-blue-700 dark:text-blue-300">
					<Info size={14} class="flex-shrink-0 mt-0.5" />
					<div>
						<p class="font-medium mb-1">Range syntax (Python-like):</p>
						<ul class="space-y-0.5 text-blue-600 dark:text-blue-400">
							<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">[:10]</code> - Skip first 10 records</li>
							<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">[-10:]</code> - Skip last 10 records</li>
							<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">[5:15]</code> - Skip records 5-14</li>
							<li>Combine with comma: <code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">[:10],[-10:]</code></li>
						</ul>
					</div>
				</div>
			{:else}
				<code class="text-sm font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">
					{range}
				</code>
			{/if}
		</div>
	{/if}
</div>
