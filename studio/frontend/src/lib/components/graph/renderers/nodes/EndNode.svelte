<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Square } from 'lucide-svelte';

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
	label={data.summary || 'End'}
	icon={Square}
	color="#ef4444"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	showSourceHandle={true}
/>
