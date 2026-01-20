<script lang="ts">
	interface Props {
		bounds: { x: number; y: number; width: number; height: number } | null;
		isDarkMode?: boolean;
	}

	let { bounds, isDarkMode = false }: Props = $props();

	// Colors based on theme (fill is very subtle, stroke more visible)
	let fillColor = $derived(isDarkMode ? 'rgba(34, 197, 94, 0.025)' : 'rgba(34, 197, 94, 0.02)');
	let strokeColor = $derived(isDarkMode ? 'rgba(74, 222, 128, 0.45)' : 'rgba(34, 197, 94, 0.4)');
	let textColor = $derived(isDarkMode ? 'rgba(74, 222, 128, 0.55)' : 'rgba(34, 197, 94, 0.55)');
</script>

<!--
	This component renders inside ViewportPortal - positioned in flow coordinates.
-->
{#if bounds}
	<div
		class="pointer-events-none"
		style="
			position: absolute;
			transform: translate({bounds.x}px, {bounds.y}px);
			width: {bounds.width}px;
			height: {bounds.height}px;
			border: 2.5px dashed {strokeColor};
			border-radius: 16px;
			background: {fillColor};
		"
	>
		<span
			class="absolute top-2.5 left-3.5 text-xs font-medium select-none"
			style="color: {textColor};"
		>
			Workflow
		</span>
	</div>
{/if}
