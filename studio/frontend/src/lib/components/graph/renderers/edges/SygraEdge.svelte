<script lang="ts">
	import { BaseEdge, getBezierPath, type EdgeProps } from '@xyflow/svelte';

	// Define props explicitly for Svelte 4 compatibility
	export let id: string;
	export let sourceX: number;
	export let sourceY: number;
	export let targetX: number;
	export let targetY: number;
	export let sourcePosition: any;
	export let targetPosition: any;
	export let data: any = {};
	export let markerEnd: string | undefined = undefined;
	export let selected: boolean = false;

	$: [edgePath, labelX, labelY] = getBezierPath({
		sourceX,
		sourceY,
		sourcePosition,
		targetX,
		targetY,
		targetPosition
	});

	$: isConditional = data?.isConditional ?? false;
	$: strokeColor = isConditional ? '#f59e0b' : '#6b7280';
	$: strokeWidth = selected ? 2.5 : 1.5;
	$: strokeDasharray = isConditional ? '5,5' : 'none';
</script>

<BaseEdge
	{id}
	path={edgePath}
	{markerEnd}
	interactionWidth={20}
	style="stroke: {strokeColor}; stroke-width: {strokeWidth}; stroke-dasharray: {strokeDasharray};"
/>

{#if data?.label}
	<foreignObject
		width={120}
		height={32}
		x={labelX - 60}
		y={labelY - 16}
		class="pointer-events-none"
	>
		<div class="flex items-center justify-center h-full">
			<span
				class="px-2 py-1 rounded text-xs font-medium shadow-sm border {isConditional
					? 'bg-amber-50 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-700'
					: 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-700'}"
			>
				{data.label}
			</span>
		</div>
	</foreignObject>
{/if}
