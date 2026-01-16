<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Globe } from 'lucide-svelte';

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
	label={data.summary || data.id}
	sublabel="Web Agent"
	icon={Globe}
	color="#ec4899"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
/>
