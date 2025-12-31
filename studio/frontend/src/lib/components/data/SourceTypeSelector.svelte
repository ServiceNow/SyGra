<script lang="ts">
	import { Cloud, HardDrive, Server, MemoryStick, FileJson, Database, Table2, Box } from 'lucide-svelte';
	import VisualSelectionCard from '../common/VisualSelectionCard.svelte';

	type SourceType = 'hf' | 'disk' | 'servicenow' | 'memory';

	interface Props {
		value: SourceType;
		onchange?: (type: SourceType) => void;
	}

	let { value = $bindable(), onchange }: Props = $props();

	const sourceTypes: Array<{
		value: SourceType;
		label: string;
		description: string;
		icon: typeof Cloud;
		iconBgClass: string;
		iconClass: string;
		previewColor: string;
	}> = [
		{
			value: 'hf',
			label: 'HuggingFace',
			description: 'Load from HuggingFace Hub',
			icon: Cloud,
			iconBgClass: 'bg-amber-100 dark:bg-amber-900/40',
			iconClass: 'text-amber-600 dark:text-amber-400',
			previewColor: 'amber'
		},
		{
			value: 'disk',
			label: 'Local File',
			description: 'JSON, CSV, Parquet files',
			icon: HardDrive,
			iconBgClass: 'bg-blue-100 dark:bg-blue-900/40',
			iconClass: 'text-blue-600 dark:text-blue-400',
			previewColor: 'blue'
		},
		{
			value: 'servicenow',
			label: 'ServiceNow',
			description: 'Query ServiceNow tables',
			icon: Server,
			iconBgClass: 'bg-emerald-100 dark:bg-emerald-900/40',
			iconClass: 'text-emerald-600 dark:text-emerald-400',
			previewColor: 'emerald'
		},
		{
			value: 'memory',
			label: 'In Memory',
			description: 'Inline or runtime data',
			icon: MemoryStick,
			iconBgClass: 'bg-purple-100 dark:bg-purple-900/40',
			iconClass: 'text-purple-600 dark:text-purple-400',
			previewColor: 'purple'
		}
	];

	function selectType(type: SourceType) {
		value = type;
		onchange?.(type);
	}
</script>

<div class="grid grid-cols-2 gap-2">
	{#each sourceTypes as st}
		{@const Icon = st.icon}
		<VisualSelectionCard
			selected={value === st.value}
			label={st.label}
			icon={Icon}
			iconBgClass={st.iconBgClass}
			iconClass={st.iconClass}
			size="sm"
			onclick={() => selectType(st.value)}
		/>
	{/each}
</div>
