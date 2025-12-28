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

	// Corner radius for trapezoidal arc edges
	const CORNER_RADIUS = 12;

	/**
	 * Create a trapezoidal arc path that goes over/under intermediate nodes.
	 * Uses straight lines with rounded corners for a clean, circuit-diagram style.
	 *
	 * Path structure:
	 * - Start point → diagonal to apex → horizontal at apex → diagonal to end
	 * - Rounded corners at the transition points
	 *
	 * @param sx - Source X coordinate
	 * @param sy - Source Y coordinate
	 * @param tx - Target X coordinate
	 * @param ty - Target Y coordinate
	 * @param apexY - Y coordinate of the horizontal apex segment
	 * @param direction - 'top' (apex above) or 'bottom' (apex below)
	 */
	function getTrapezoidalArcPath(
		sx: number,
		sy: number,
		tx: number,
		ty: number,
		apexY: number,
		direction: 'top' | 'bottom'
	): [string, number, number] {
		const dx = tx - sx;
		const radius = CORNER_RADIUS;

		// Calculate diagonal offset - how far horizontally before reaching apex
		// Use a proportion of the total distance for balanced appearance
		const diagonalOffset = Math.min(Math.abs(dx) * 0.15, 50);

		// Key points for the trapezoid
		// P1: First corner (where diagonal meets horizontal)
		// P2: Second corner (where horizontal meets diagonal)
		const p1x = sx + diagonalOffset;
		const p2x = tx - diagonalOffset;

		// Ensure p1x < p2x (horizontal segment exists)
		const minHorizontalLength = radius * 2 + 10;
		let actualP1x = p1x;
		let actualP2x = p2x;

		if (actualP2x - actualP1x < minHorizontalLength) {
			// Not enough room for horizontal segment, adjust
			const midX = (sx + tx) / 2;
			actualP1x = midX - minHorizontalLength / 2;
			actualP2x = midX + minHorizontalLength / 2;
		}

		// Direction multiplier (1 for top/up, -1 for bottom/down)
		const dirMult = direction === 'top' ? -1 : 1;

		// For top arc: apex is above (lower Y), so we go "up"
		// For bottom arc: apex is below (higher Y), so we go "down"

		// Calculate approach vectors for smooth corners
		// From source to P1
		const d1x = actualP1x - sx;
		const d1y = apexY - sy;
		const d1len = Math.sqrt(d1x * d1x + d1y * d1y);
		const d1nx = d1x / d1len; // normalized
		const d1ny = d1y / d1len;

		// From P2 to target
		const d2x = tx - actualP2x;
		const d2y = ty - apexY;
		const d2len = Math.sqrt(d2x * d2x + d2y * d2y);
		const d2nx = d2x / d2len;
		const d2ny = d2y / d2len;

		// Points before and after corners (for rounded corners)
		// Corner 1: transition from diagonal to horizontal
		const c1_before_x = actualP1x - d1nx * radius;
		const c1_before_y = apexY - d1ny * radius;
		const c1_after_x = actualP1x + radius;
		const c1_after_y = apexY;

		// Corner 2: transition from horizontal to diagonal
		const c2_before_x = actualP2x - radius;
		const c2_before_y = apexY;
		const c2_after_x = actualP2x + d2nx * radius;
		const c2_after_y = apexY + d2ny * radius;

		// Build SVG path with quadratic bezier corners
		const path = [
			`M ${sx} ${sy}`,
			// Diagonal to first corner approach
			`L ${c1_before_x} ${c1_before_y}`,
			// Rounded corner 1 (quadratic bezier)
			`Q ${actualP1x} ${apexY} ${c1_after_x} ${c1_after_y}`,
			// Horizontal segment at apex
			`L ${c2_before_x} ${c2_before_y}`,
			// Rounded corner 2 (quadratic bezier)
			`Q ${actualP2x} ${apexY} ${c2_after_x} ${c2_after_y}`,
			// Diagonal to target
			`L ${tx} ${ty}`
		].join(' ');

		// Label position: center of horizontal segment
		const labelX = (actualP1x + actualP2x) / 2;
		const labelY = apexY + (direction === 'top' ? -12 : 12);

		return [path, labelX, labelY];
	}

	// Determine which path to use
	$: isArcEdge = data?.isArcEdge ?? false;
	$: arcApexY = data?.arcApexY ?? sourceY;
	$: arcDirection = data?.arcDirection ?? 'top';

	// Calculate edge path - use trapezoidal arc for skip edges, bezier for normal edges
	$: [edgePath, labelX, labelY] = isArcEdge
		? getTrapezoidalArcPath(sourceX, sourceY, targetX, targetY, arcApexY, arcDirection)
		: getBezierPath({
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
