<script lang="ts">
	import type { AddNewFieldParams } from '$lib/stores/workflow.svelte';
	import { Plus, Trash2, Type, Hash, ToggleLeft } from 'lucide-svelte';

	interface Props {
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
	}

	let { params, isEditing = false, onUpdate }: Props = $props();

	type FieldValue = { fieldName: string; value: string; valueType: 'string' | 'number' | 'boolean' };

	// Parse params
	let fields = $state<FieldValue[]>(
		params.mapping
			? Object.entries(params.mapping as Record<string, unknown>).map(([fieldName, value]) => ({
				fieldName,
				value: String(value),
				valueType: typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : 'string'
			}))
			: []
	);

	// Sync with params
	$effect(() => {
		fields = params.mapping
			? Object.entries(params.mapping as Record<string, unknown>).map(([fieldName, value]) => ({
				fieldName,
				value: String(value),
				valueType: typeof value === 'number' ? 'number' : typeof value === 'boolean' ? 'boolean' : 'string'
			}))
			: [];
	});

	function parseValue(value: string, type: 'string' | 'number' | 'boolean'): unknown {
		if (type === 'number') {
			const num = parseFloat(value);
			return isNaN(num) ? 0 : num;
		}
		if (type === 'boolean') {
			return value.toLowerCase() === 'true';
		}
		return value;
	}

	function emitUpdate() {
		const newParams: AddNewFieldParams = {
			mapping: {}
		};

		for (const { fieldName, value, valueType } of fields) {
			if (fieldName.trim()) {
				newParams.mapping[fieldName.trim()] = parseValue(value, valueType);
			}
		}

		onUpdate(newParams);
	}

	function addField() {
		fields = [...fields, { fieldName: '', value: '', valueType: 'string' }];
	}

	function removeField(index: number) {
		fields = fields.filter((_, i) => i !== index);
		emitUpdate();
	}

	function updateField(index: number, field: keyof FieldValue, value: string) {
		if (field === 'valueType') {
			fields[index].valueType = value as 'string' | 'number' | 'boolean';
		} else {
			fields[index][field] = value;
		}
		fields = [...fields];
		emitUpdate();
	}

	function getTypeIcon(type: 'string' | 'number' | 'boolean') {
		switch (type) {
			case 'string': return Type;
			case 'number': return Hash;
			case 'boolean': return ToggleLeft;
		}
	}
</script>

<div class="space-y-4">
	<!-- Fields -->
	<div>
		<div class="flex items-center justify-between mb-2">
			<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
				New Fields
			</label>
			{#if isEditing}
				<button
					onclick={addField}
					class="flex items-center gap-1 text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
				>
					<Plus size={12} />
					Add Field
				</button>
			{/if}
		</div>

		{#if fields.length > 0}
			<div class="space-y-2">
				{#each fields as field, index}
					{@const TypeIcon = getTypeIcon(field.valueType)}
					<div class="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
						{#if isEditing}
							<input
								type="text"
								value={field.fieldName}
								oninput={(e) => updateField(index, 'fieldName', e.currentTarget.value)}
								placeholder="field_name"
								class="w-28 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							/>
							<select
								value={field.valueType}
								onchange={(e) => updateField(index, 'valueType', e.currentTarget.value)}
								class="px-2 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
							>
								<option value="string">String</option>
								<option value="number">Number</option>
								<option value="boolean">Boolean</option>
							</select>
							{#if field.valueType === 'boolean'}
								<select
									value={field.value}
									onchange={(e) => updateField(index, 'value', e.currentTarget.value)}
									class="flex-1 px-2 py-1.5 text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								>
									<option value="true">true</option>
									<option value="false">false</option>
								</select>
							{:else}
								<input
									type={field.valueType === 'number' ? 'number' : 'text'}
									value={field.value}
									oninput={(e) => updateField(index, 'value', e.currentTarget.value)}
									placeholder={field.valueType === 'number' ? '0' : 'value'}
									class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
								/>
							{/if}
							<button
								onclick={() => removeField(index)}
								class="p-1 text-gray-400 hover:text-red-500 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
							>
								<Trash2 size={14} />
							</button>
						{:else}
							<div class="flex items-center gap-2 text-xs font-mono">
								<TypeIcon size={12} class="text-gray-400" />
								<span class="text-violet-600 dark:text-violet-400">{field.fieldName}</span>
								<span class="text-gray-400">=</span>
								<span class="text-gray-700 dark:text-gray-300">
									{field.valueType === 'string' ? `"${field.value}"` : field.value}
								</span>
								<span class="text-xs text-gray-400">({field.valueType})</span>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		{:else}
			<div class="text-xs text-gray-500 italic text-center py-3 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
				{#if isEditing}
					Click "Add Field" to define new fields with static values
				{:else}
					No fields defined
				{/if}
			</div>
		{/if}
	</div>
</div>
