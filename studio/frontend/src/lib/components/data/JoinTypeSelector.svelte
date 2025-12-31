<script lang="ts">
	import { Check, Database, Link, Repeat, Shuffle, Grid3X3, Layers } from 'lucide-svelte';
	import type { JoinType } from '$lib/stores/workflow.svelte';
	import { JOIN_TYPE_METADATA } from '$lib/stores/workflow.svelte';
	import type { Component } from 'svelte';

	interface Props {
		value: JoinType;
		excludePrimary?: boolean;
		compact?: boolean;
		onchange?: (type: JoinType) => void;
	}

	let { value = $bindable(), excludePrimary = false, compact = false, onchange }: Props = $props();

	// Map icon names to components
	const iconMap: Record<string, Component<{ size?: number; class?: string }>> = {
		database: Database,
		link: Link,
		repeat: Repeat,
		shuffle: Shuffle,
		grid: Grid3X3,
		layers: Layers
	};

	// Join type configurations with visual colors
	const joinConfigs: Record<JoinType, { color: string; bgClass: string; iconClass: string }> = {
		primary: { color: 'amber', bgClass: 'bg-amber-100 dark:bg-amber-900/40', iconClass: 'text-amber-600 dark:text-amber-400' },
		column: { color: 'violet', bgClass: 'bg-violet-100 dark:bg-violet-900/40', iconClass: 'text-violet-600 dark:text-violet-400' },
		sequential: { color: 'blue', bgClass: 'bg-blue-100 dark:bg-blue-900/40', iconClass: 'text-blue-600 dark:text-blue-400' },
		random: { color: 'pink', bgClass: 'bg-pink-100 dark:bg-pink-900/40', iconClass: 'text-pink-600 dark:text-pink-400' },
		cross: { color: 'emerald', bgClass: 'bg-emerald-100 dark:bg-emerald-900/40', iconClass: 'text-emerald-600 dark:text-emerald-400' },
		vstack: { color: 'orange', bgClass: 'bg-orange-100 dark:bg-orange-900/40', iconClass: 'text-orange-600 dark:text-orange-400' }
	};

	let joinTypes = $derived(
		(Object.entries(JOIN_TYPE_METADATA) as [JoinType, typeof JOIN_TYPE_METADATA[JoinType]][])
			.filter(([key]) => !excludePrimary || key !== 'primary')
			.map(([key, meta]) => ({
				value: key,
				...meta,
				icon: iconMap[meta.icon] || Database,
				config: joinConfigs[key]
			}))
	);

	function selectType(type: JoinType) {
		value = type;
		onchange?.(type);
	}
</script>

<div class="grid {compact ? 'grid-cols-3 gap-2' : 'grid-cols-2 gap-3'}">
	{#each joinTypes as jt}
		{@const Icon = jt.icon}
		{@const isSelected = value === jt.value}
		<button
			type="button"
			onclick={() => selectType(jt.value)}
			class="group relative flex flex-col rounded-xl border-2 transition-all duration-200 overflow-hidden text-left
				{isSelected
					? 'border-violet-500 shadow-lg shadow-violet-500/20 dark:shadow-violet-500/10 ring-1 ring-violet-500/30'
					: 'border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md'}"
		>
			<!-- Visual Diagram Preview -->
			<div class="relative {compact ? 'h-14' : 'h-20'} bg-gradient-to-b from-gray-50 to-white dark:from-gray-800 dark:to-gray-900 overflow-hidden">
				<!-- Subtle grid background -->
				<div class="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
					style="background-image: radial-gradient(circle, currentColor 1px, transparent 1px); background-size: 8px 8px;">
				</div>

				<!-- Join Type Diagram -->
				<div class="absolute inset-0 flex items-center justify-center p-2">
					{#if jt.value === 'primary'}
						<!-- Primary: Single table -->
						<div class="flex flex-col items-center gap-1">
							<div class="flex gap-0.5">
								<div class="w-10 h-1.5 rounded-sm bg-amber-400"></div>
							</div>
							<div class="flex gap-0.5">
								<div class="w-10 h-1.5 rounded-sm bg-amber-300"></div>
							</div>
							<div class="flex gap-0.5">
								<div class="w-10 h-1.5 rounded-sm bg-amber-400"></div>
							</div>
						</div>
					{:else if jt.value === 'column'}
						<!-- Column Join: Two tables with matching rows -->
						<div class="flex items-center gap-2">
							<div class="flex flex-col gap-0.5">
								<div class="w-6 h-1.5 rounded-sm bg-violet-400"></div>
								<div class="w-6 h-1.5 rounded-sm bg-violet-300"></div>
								<div class="w-6 h-1.5 rounded-sm bg-violet-400"></div>
							</div>
							<div class="flex flex-col justify-center">
								<Link size={10} class="text-violet-500" />
							</div>
							<div class="flex flex-col gap-0.5">
								<div class="w-6 h-1.5 rounded-sm bg-violet-300"></div>
								<div class="w-6 h-1.5 rounded-sm bg-violet-400"></div>
								<div class="w-6 h-1.5 rounded-sm bg-violet-300"></div>
							</div>
						</div>
					{:else if jt.value === 'sequential'}
						<!-- Sequential: Cycling repeat -->
						<div class="flex items-center gap-1">
							<div class="flex flex-col gap-0.5">
								<div class="w-5 h-1 rounded-sm bg-blue-400"></div>
								<div class="w-5 h-1 rounded-sm bg-blue-300"></div>
								<div class="w-5 h-1 rounded-sm bg-blue-400"></div>
								<div class="w-5 h-1 rounded-sm bg-blue-300"></div>
							</div>
							<Repeat size={10} class="text-blue-500" />
							<div class="flex flex-col gap-0.5">
								<div class="w-4 h-1 rounded-sm bg-blue-500"></div>
								<div class="w-4 h-1 rounded-sm bg-blue-400"></div>
							</div>
						</div>
					{:else if jt.value === 'random'}
						<!-- Random: Shuffled -->
						<div class="flex items-center gap-1">
							<div class="flex flex-col gap-0.5">
								<div class="w-5 h-1 rounded-sm bg-pink-400"></div>
								<div class="w-5 h-1 rounded-sm bg-pink-300"></div>
								<div class="w-5 h-1 rounded-sm bg-pink-400"></div>
							</div>
							<Shuffle size={10} class="text-pink-500" />
							<div class="flex flex-col gap-0.5">
								<div class="w-4 h-1 rounded-sm bg-pink-300"></div>
								<div class="w-4 h-1 rounded-sm bg-pink-500"></div>
								<div class="w-4 h-1 rounded-sm bg-pink-400"></div>
							</div>
						</div>
					{:else if jt.value === 'cross'}
						<!-- Cross: Grid pattern -->
						<div class="grid grid-cols-3 gap-0.5">
							{#each Array(9) as _, i}
								<div class="w-2 h-2 rounded-sm {i % 2 === 0 ? 'bg-emerald-400' : 'bg-emerald-300'}"></div>
							{/each}
						</div>
					{:else if jt.value === 'vstack'}
						<!-- Vertical Stack: Stacked tables -->
						<div class="flex flex-col gap-1">
							<div class="flex gap-0.5">
								<div class="w-8 h-1 rounded-sm bg-orange-400"></div>
							</div>
							<div class="flex gap-0.5">
								<div class="w-8 h-1 rounded-sm bg-orange-300"></div>
							</div>
							<div class="w-full h-px bg-gray-300 dark:bg-gray-600"></div>
							<div class="flex gap-0.5">
								<div class="w-8 h-1 rounded-sm bg-orange-500"></div>
							</div>
							<div class="flex gap-0.5">
								<div class="w-8 h-1 rounded-sm bg-orange-400"></div>
							</div>
						</div>
					{/if}
				</div>

				<!-- Selected glow -->
				{#if isSelected}
					<div class="absolute inset-0 bg-violet-500/5 dark:bg-violet-400/10"></div>
				{/if}
			</div>

			<!-- Label Section -->
			<div class="flex items-center justify-between {compact ? 'p-2' : 'p-3'} bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700/50">
				<div class="flex items-center gap-2 min-w-0 flex-1">
					<Icon size={compact ? 12 : 14} class="{isSelected ? 'text-violet-500' : jt.config.iconClass} transition-colors" />
					<div class="min-w-0 flex-1">
						<span class="text-sm font-medium {isSelected ? 'text-violet-700 dark:text-violet-300' : 'text-gray-900 dark:text-gray-100'} block truncate transition-colors">
							{jt.name}
						</span>
						{#if !compact}
							<span class="text-xs text-gray-500 dark:text-gray-400 block truncate mt-0.5">
								{jt.description}
							</span>
						{/if}
					</div>
				</div>

				<!-- Checkmark -->
				{#if isSelected}
					<div class="w-4 h-4 rounded-full bg-violet-500 flex items-center justify-center flex-shrink-0 shadow-sm">
						<Check size={10} class="text-white" strokeWidth={3} />
					</div>
				{:else}
					<div class="w-4 h-4 rounded-full border-2 border-gray-200 dark:border-gray-600 flex-shrink-0 group-hover:border-violet-300 dark:group-hover:border-violet-500 transition-colors"></div>
				{/if}
			</div>
		</button>
	{/each}
</div>
