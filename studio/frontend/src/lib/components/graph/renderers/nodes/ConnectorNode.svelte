<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Link } from 'lucide-svelte';

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
	sublabel="Connector"
	icon={Link}
	color="#06b6d4"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
/>
