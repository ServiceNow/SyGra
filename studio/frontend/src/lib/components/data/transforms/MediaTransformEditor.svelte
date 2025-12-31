<script lang="ts">
	import { Plus, Trash2, ArrowRight, Image, AudioLines, Info } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		type: 'image' | 'audio';
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, type, isEditing = false, onUpdate }: Props = $props();

	// Parse output_fields for audio transform
	let outputFields = $state<Array<{ input: string; output: string }>>(
		params.output_fields
			? Object.entries(params.output_fields as Record<string, string>).map(([input, output]) => ({ input, output }))
			: []
	);

	// Sync with params
	$effect(() => {
		outputFields = params.output_fields
			? Object.entries(params.output_fields as Record<string, string>).map(([input, output]) => ({ input, output }))
			: [];
	});

	function emitUpdate() {
		const newParams: Record<string, unknown> = {};

		if (outputFields.length > 0) {
			newParams.output_fields = {};
			for (const { input, output } of outputFields) {
				if (input.trim() && output.trim()) {
					(newParams.output_fields as Record<string, string>)[input.trim()] = output.trim();
				}
			}
		}

		onUpdate(newParams);
	}

	function addOutputField() {
		outputFields = [...outputFields, { input: '', output: '' }];
	}

	function removeOutputField(index: number) {
		outputFields = outputFields.filter((_, i) => i !== index);
		emitUpdate();
	}

	function updateOutputField(index: number, field: 'input' | 'output', value: string) {
		outputFields[index][field] = value;
		outputFields = [...outputFields];
		emitUpdate();
	}

	let MediaIcon = $derived(type === 'image' ? Image : AudioLines);
</script>

<div class="space-y-4">
	<!-- Info Section -->
	<div class="flex items-start gap-2 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-sm">
		<MediaIcon size={16} class="text-blue-500 flex-shrink-0 mt-0.5" />
		<div class="text-blue-700 dark:text-blue-300">
			{#if type === 'image'}
				<p class="font-medium">Image to URL Transform</p>
				<p class="text-xs mt-1 text-blue-600 dark:text-blue-400">
					Automatically detects image fields and converts them to base64 data URLs with proper MIME types.
				</p>
			{:else}
				<p class="font-medium">Audio to URL Transform</p>
				<p class="text-xs mt-1 text-blue-600 dark:text-blue-400">
					Converts audio data to base64 data URLs. Supports MP3, OGG, FLAC, AAC, M4A, AIFF, WAV formats.
				</p>
			{/if}
		</div>
	</div>

	{#if type === 'audio'}
		<!-- Output Field Mapping (Audio only) -->
		<div>
			<div class="flex items-center justify-between mb-2">
				<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
					Output Field Mapping (Optional)
				</label>
				{#if isEditing}
					<button
						onclick={addOutputField}
						class="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
					>
						<Plus size={12} />
						Add Mapping
					</button>
				{/if}
			</div>

			{#if outputFields.length > 0}
				<div class="space-y-2">
					{#each outputFields as mapping, index}
						<div class="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
							{#if isEditing}
								<input
									type="text"
									value={mapping.input}
									oninput={(e) => updateOutputField(index, 'input', e.currentTarget.value)}
									placeholder="input_field"
									class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
								<ArrowRight size={14} class="text-gray-400 flex-shrink-0" />
								<input
									type="text"
									value={mapping.output}
									oninput={(e) => updateOutputField(index, 'output', e.currentTarget.value)}
									placeholder="output_field"
									class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
								<button
									onclick={() => removeOutputField(index)}
									class="p-1 text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
								>
									<Trash2 size={14} />
								</button>
							{:else}
								<code class="text-xs font-mono flex items-center gap-2">
									<span class="text-gray-600 dark:text-gray-400">{mapping.input}</span>
									<ArrowRight size={12} class="text-gray-400" />
									<span class="text-violet-600 dark:text-violet-400">{mapping.output}</span>
								</code>
							{/if}
						</div>
					{/each}
				</div>
			{:else}
				<div class="text-xs text-gray-500 italic p-2 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
					{#if isEditing}
						No custom output field mappings. Output fields will use the same name as input fields.
					{:else}
						Using default field names
					{/if}
				</div>
			{/if}
		</div>
	{:else}
		<!-- Image transform has no parameters -->
		<div class="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-xs text-gray-600 dark:text-gray-400">
			<Info size={14} />
			This transform automatically processes all image fields with no additional configuration needed.
		</div>
	{/if}
</div>
