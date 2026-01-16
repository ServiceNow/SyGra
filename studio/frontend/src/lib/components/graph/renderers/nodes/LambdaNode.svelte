<script lang="ts">
	import NodeWrapper from './NodeWrapper.svelte';
	import { Zap } from 'lucide-svelte';

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
	sublabel="Lambda Function"
	icon={Zap}
	color="#f97316"
	executionState={data.executionState}
	isCurrentNode={data.isCurrentNode}
	nodeType="lambda"
	hasRunningNode={data.hasRunningNode}
/>
