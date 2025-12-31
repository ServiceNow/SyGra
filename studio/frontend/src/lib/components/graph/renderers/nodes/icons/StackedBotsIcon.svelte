<script lang="ts">
	import { Bot } from 'lucide-svelte';

	interface Props {
		size?: number;
		class?: string;
	}

	let { size = 18, class: className = '' }: Props = $props();
</script>

<div class="relative inline-flex items-center justify-center {className}" style="width: {size}px; height: {size}px;">
	<!-- Back bot (slightly offset) -->
	<div class="absolute" style="top: -2px; left: -2px; opacity: 0.6;">
		<Bot size={size * 0.75} />
	</div>
	<!-- Front bot -->
	<div class="absolute" style="bottom: -2px; right: -2px;">
		<Bot size={size * 0.75} />
	</div>
</div>
