<script lang="ts">
	interface Props {
		data: number[];
		color?: string;
		height?: number;
		width?: number;
		showDot?: boolean;
	}

	let { data, color = '#8b5cf6', height = 24, width = 60, showDot = true }: Props = $props();

	let points = $derived(() => {
		if (data.length === 0) return '';
		const max = Math.max(...data, 1);
		const min = Math.min(...data, 0);
		const range = max - min || 1;

		const stepX = width / Math.max(data.length - 1, 1);
		return data.map((v, i) => {
			const x = i * stepX;
			const y = height - ((v - min) / range) * (height - 4) - 2;
			return `${x},${y}`;
		}).join(' ');
	});

	let lastPoint = $derived(() => {
		if (data.length === 0) return null;
		const max = Math.max(...data, 1);
		const min = Math.min(...data, 0);
		const range = max - min || 1;
		const v = data[data.length - 1];
		return {
			x: width,
			y: height - ((v - min) / range) * (height - 4) - 2
		};
	});
</script>

<svg {width} {height} class="overflow-visible">
	{#if data.length > 1}
		<polyline
			points={points()}
			fill="none"
			stroke={color}
			stroke-width="1.5"
			stroke-linecap="round"
			stroke-linejoin="round"
		/>
		{#if showDot && lastPoint()}
			<circle
				cx={lastPoint()?.x}
				cy={lastPoint()?.y}
				r="2.5"
				fill={color}
			/>
		{/if}
	{:else if data.length === 1}
		<circle
			cx={width / 2}
			cy={height / 2}
			r="3"
			fill={color}
		/>
	{/if}
</svg>
