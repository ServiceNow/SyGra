<script lang="ts">
	import type { CombineRecordsParams } from '$lib/stores/workflow.svelte';
	import { Plus, Trash2, Info } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, isEditing = false, onUpdate }: Props = $props();

	// Parse params
	let combine = $state((params.combine as number) || 2);
	let shift = $state((params.shift as number) || 1);
	let skipFromBeginning = $state((params.skip as { from_beginning?: number })?.from_beginning || 0);
	let skipFromEnd = $state((params.skip as { from_end?: number })?.from_end || 0);

	// Join column rules as array for easier editing
	let joinColumns = $state<Array<{ column: string; pattern: string }>>(
		params.join_column
			? Object.entries(params.join_column as Record<string, string>).map(([column, pattern]) => ({ column, pattern }))
			: []
	);

	// Sync with params
	$effect(() => {
		combine = (params.combine as number) || 2;
		shift = (params.shift as number) || 1;
		const skip = params.skip as { from_beginning?: number; from_end?: number } | undefined;
		skipFromBeginning = skip?.from_beginning || 0;
		skipFromEnd = skip?.from_end || 0;
		joinColumns = params.join_column
			? Object.entries(params.join_column as Record<string, string>).map(([column, pattern]) => ({ column, pattern }))
			: [];
	});

	function emitUpdate() {
		const newParams: CombineRecordsParams = {
			combine,
			shift
		};

		if (skipFromBeginning > 0 || skipFromEnd > 0) {
			newParams.skip = {
				from_beginning: skipFromBeginning || undefined,
				from_end: skipFromEnd || undefined
			};
		}

		if (joinColumns.length > 0) {
			newParams.join_column = {};
			for (const { column, pattern } of joinColumns) {
				if (column.trim()) {
					newParams.join_column[column.trim()] = pattern;
				}
			}
		}

		onUpdate(newParams);
	}

	function addJoinColumn() {
		joinColumns = [...joinColumns, { column: '', pattern: '$1\\n\\n$2' }];
	}

	function removeJoinColumn(index: number) {
		joinColumns = joinColumns.filter((_, i) => i !== index);
		emitUpdate();
	}

	function updateJoinColumn(index: number, field: 'column' | 'pattern', value: string) {
		joinColumns[index][field] = value;
		joinColumns = [...joinColumns];
		emitUpdate();
	}
</script>

<div class="space-y-4">
	<!-- Basic Settings -->
	<div class="grid grid-cols-2 gap-4">
		<div>
			<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
				Combine Records
			</label>
			{#if isEditing}
				<input
					type="number"
					bind:value={combine}
					onchange={emitUpdate}
					min="2"
					class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
				/>
				<p class="text-xs text-gray-500 mt-1">Records to merge</p>
			{:else}
				<div class="text-sm font-mono text-gray-800 dark:text-gray-200">
					{combine} records
				</div>
			{/if}
		</div>
		<div>
			<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
				Shift (Stride)
			</label>
			{#if isEditing}
				<input
					type="number"
					bind:value={shift}
					onchange={emitUpdate}
					min="1"
					class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
				/>
				<p class="text-xs text-gray-500 mt-1">Move forward by</p>
			{:else}
				<div class="text-sm font-mono text-gray-800 dark:text-gray-200">
					{shift}
				</div>
			{/if}
		</div>
	</div>

	<!-- Skip Settings -->
	<div>
		<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
			Skip Records (Optional)
		</label>
		<div class="grid grid-cols-2 gap-4">
			<div>
				{#if isEditing}
					<input
						type="number"
						bind:value={skipFromBeginning}
						onchange={emitUpdate}
						min="0"
						placeholder="0"
						class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
					/>
					<p class="text-xs text-gray-500 mt-1">From beginning</p>
				{:else if skipFromBeginning > 0}
					<div class="text-sm text-gray-800 dark:text-gray-200">
						Skip {skipFromBeginning} from start
					</div>
				{/if}
			</div>
			<div>
				{#if isEditing}
					<input
						type="number"
						bind:value={skipFromEnd}
						onchange={emitUpdate}
						min="0"
						placeholder="0"
						class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
					/>
					<p class="text-xs text-gray-500 mt-1">From end</p>
				{:else if skipFromEnd > 0}
					<div class="text-sm text-gray-800 dark:text-gray-200">
						Skip {skipFromEnd} from end
					</div>
				{/if}
			</div>
		</div>
	</div>

	<!-- Join Column Rules -->
	<div>
		<div class="flex items-center justify-between mb-2">
			<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
				Join Column Rules
			</label>
			{#if isEditing}
				<button
					onclick={addJoinColumn}
					class="flex items-center gap-1 text-xs text-[#032D42] dark:text-[#52B8FF] hover:text-[#7661FF] dark:hover:text-[#BF71F2]"
				>
					<Plus size={12} />
					Add Rule
				</button>
			{/if}
		</div>

		{#if joinColumns.length > 0}
			<div class="space-y-2">
				{#each joinColumns as rule, index}
					<div class="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
						{#if isEditing}
							<input
								type="text"
								value={rule.column}
								oninput={(e) => updateJoinColumn(index, 'column', e.currentTarget.value)}
								placeholder="column_name"
								class="w-28 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							/>
							<input
								type="text"
								value={rule.pattern}
								oninput={(e) => updateJoinColumn(index, 'pattern', e.currentTarget.value)}
								placeholder="$1\n\n$2"
								class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							/>
							<button
								onclick={() => removeJoinColumn(index)}
								class="p-1 text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
							>
								<Trash2 size={14} />
							</button>
						{:else}
							<code class="text-xs font-mono">
								<span class="text-[#7661FF] dark:text-[#BF71F2]">{rule.column}</span>:
								<span class="text-gray-600 dark:text-gray-400">{rule.pattern}</span>
							</code>
						{/if}
					</div>
				{/each}
			</div>
		{:else if !isEditing}
			<div class="text-xs text-gray-500 italic">No join rules defined (uses default merge)</div>
		{/if}

		{#if isEditing}
			<div class="mt-2 flex items-start gap-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-xs text-blue-700 dark:text-blue-300">
				<Info size={14} class="flex-shrink-0 mt-0.5" />
				<div>
					<p class="font-medium mb-1">Pattern syntax:</p>
					<ul class="space-y-0.5 text-blue-600 dark:text-blue-400">
						<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">$1</code> - First record's value</li>
						<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">$2</code> - Second record's value</li>
						<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">$1\n\n$2</code> - Join with newlines</li>
						<li><code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">$1-$2</code> - Join with dash</li>
					</ul>
				</div>
			</div>
		{/if}
	</div>
</div>
