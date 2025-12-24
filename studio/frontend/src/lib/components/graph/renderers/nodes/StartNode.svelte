<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Play } from 'lucide-svelte';

	interface Props {
		data: {
			id: string;
			summary: string;
			executionState?: any;
			isCurrentNode?: boolean;
		};
	}

	let { data }: Props = $props();
</script>

<NodeWrapper
	id={data.id}
	label={data.summary || 'Start'}
	icon={Play}
	color="#22c55e"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	showTargetHandle={true}
/>
