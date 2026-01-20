<script lang="ts">
	import { useSvelteFlow } from '@xyflow/svelte';
	import type { Writable } from 'svelte/store';

	interface Props {
		trigger: Writable<number>;
	}

	let { trigger }: Props = $props();

	const { fitView } = useSvelteFlow();

	// Watch for trigger changes and call fitView
	$effect(() => {
		const value = $trigger;
		if (value > 0) {
			// Small delay to ensure nodes are rendered
			setTimeout(() => {
				fitView({ padding: 0.2, duration: 200 });
			}, 50);
		}
	});
</script>
