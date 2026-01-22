<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		TRANSFORM_METADATA,
		TRANSFORM_MODULES,
		type TransformType
	} from '$lib/stores/workflow.svelte';
	import {
		X, SkipForward, Combine, ArrowLeftRight, PlusCircle,
		Image, AudioLines, Grid3X3, Settings, Check, Wand2,
		Layers, FileEdit, Sparkles, Code
	} from 'lucide-svelte';
	import type { Component } from 'svelte';

	interface Props {
		open?: boolean;
	}

	let { open = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		select: { type: TransformType; modulePath: string };
		close: void;
	}>();

	// Transform type configurations with colors and icons
	const transformConfigs: Record<string, {
		icon: Component<{ size?: number; class?: string }>;
		color: string;
		bgClass: string;
		iconClass: string;
		borderHover: string;
	}> = {
		SkipRecords: {
			icon: SkipForward,
			color: 'rose',
			bgClass: 'bg-rose-100 dark:bg-rose-900/30',
			iconClass: 'text-rose-600 dark:text-rose-400',
			borderHover: 'hover:border-rose-300 dark:hover:border-rose-600'
		},
		CombineRecords: {
			icon: Combine,
			color: 'blue',
			bgClass: 'bg-blue-100 dark:bg-blue-900/30',
			iconClass: 'text-blue-600 dark:text-blue-400',
			borderHover: 'hover:border-blue-300 dark:hover:border-blue-600'
		},
		RenameFieldsTransform: {
			icon: ArrowLeftRight,
			color: 'amber',
			bgClass: 'bg-amber-100 dark:bg-amber-900/30',
			iconClass: 'text-amber-600 dark:text-amber-400',
			borderHover: 'hover:border-amber-300 dark:hover:border-amber-600'
		},
		AddNewFieldTransform: {
			icon: PlusCircle,
			color: 'emerald',
			bgClass: 'bg-emerald-100 dark:bg-emerald-900/30',
			iconClass: 'text-emerald-600 dark:text-emerald-400',
			borderHover: 'hover:border-emerald-300 dark:hover:border-emerald-600'
		},
		CreateImageUrlTransform: {
			icon: Image,
			color: 'indigo',
			bgClass: 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20',
			iconClass: 'text-[#7661FF] dark:text-[#BF71F2]',
			borderHover: 'hover:border-[#52B8FF] dark:hover:border-[#7661FF]'
		},
		CreateAudioUrlTransform: {
			icon: AudioLines,
			color: 'pink',
			bgClass: 'bg-pink-100 dark:bg-pink-900/30',
			iconClass: 'text-pink-600 dark:text-pink-400',
			borderHover: 'hover:border-pink-300 dark:hover:border-pink-600'
		},
		CartesianProductTransform: {
			icon: Grid3X3,
			color: 'cyan',
			bgClass: 'bg-cyan-100 dark:bg-cyan-900/30',
			iconClass: 'text-cyan-600 dark:text-cyan-400',
			borderHover: 'hover:border-cyan-300 dark:hover:border-cyan-600'
		}
	};

	// Group transforms by category with icons
	const categories = [
		{
			id: 'record',
			name: 'Record Manipulation',
			description: 'Skip, combine, or filter records',
			icon: Layers,
			iconClass: 'text-rose-500',
			bgClass: 'bg-rose-100 dark:bg-rose-900/30',
			transforms: ['SkipRecords', 'CombineRecords']
		},
		{
			id: 'field',
			name: 'Field Operations',
			description: 'Add, rename, or modify fields',
			icon: FileEdit,
			iconClass: 'text-amber-500',
			bgClass: 'bg-amber-100 dark:bg-amber-900/30',
			transforms: ['RenameFieldsTransform', 'AddNewFieldTransform']
		},
		{
			id: 'media',
			name: 'Media Transforms',
			description: 'Convert media to data URLs',
			icon: Image,
			iconClass: 'text-[#7661FF]',
			bgClass: 'bg-[#7661FF]/15 dark:bg-[#7661FF]/20',
			transforms: ['CreateImageUrlTransform', 'CreateAudioUrlTransform']
		},
		{
			id: 'advanced',
			name: 'Advanced',
			description: 'Complex data transformations',
			icon: Sparkles,
			iconClass: 'text-cyan-500',
			bgClass: 'bg-cyan-100 dark:bg-cyan-900/30',
			transforms: ['CartesianProductTransform']
		}
	];

	function selectTransform(type: string) {
		const modulePath = TRANSFORM_MODULES[type] || type;
		dispatch('select', { type: type as TransformType, modulePath });
	}

	function handleClose() {
		dispatch('close');
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
		onclick={handleBackdropClick}
		role="dialog"
		aria-modal="true"
		aria-labelledby="transform-selector-title"
	>
		<!-- Modal -->
		<div class="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
			<!-- Header -->
			<div class="flex items-center justify-between px-6 py-5 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-gray-50 to-white dark:from-gray-800 dark:to-gray-900">
				<div class="flex items-center gap-4">
					<div class="p-2.5 rounded-xl bg-gradient-to-br from-[#7661FF]/20 to-[#BF71F2]/20 dark:from-[#7661FF]/30 dark:to-[#BF71F2]/30 shadow-sm">
						<Wand2 size={22} class="text-[#7661FF] dark:text-[#BF71F2]" />
					</div>
					<div>
						<h2 id="transform-selector-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
							Add Transform
						</h2>
						<p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
							Select a transformation to add to your pipeline
						</p>
					</div>
				</div>
				<button
					onclick={handleClose}
					class="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors"
				>
					<X size={20} />
				</button>
			</div>

			<!-- Transform Categories -->
			<div class="flex-1 overflow-y-auto p-6 space-y-6">
				{#each categories as category}
					{@const CategoryIcon = category.icon}
					<div>
						<!-- Category Header -->
						<div class="flex items-center gap-3 mb-3">
							<div class="p-1.5 rounded-lg {category.bgClass}">
								<CategoryIcon size={14} class={category.iconClass} />
							</div>
							<div>
								<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
									{category.name}
								</h3>
								<p class="text-xs text-gray-500 dark:text-gray-400">{category.description}</p>
							</div>
						</div>

						<!-- Transform Cards Grid -->
						<div class="grid grid-cols-2 gap-3">
							{#each category.transforms as transformType}
								{@const meta = TRANSFORM_METADATA[transformType]}
								{@const config = transformConfigs[transformType]}
								{@const Icon = config?.icon || Settings}
								<button
									onclick={() => selectTransform(transformType)}
									class="group relative flex flex-col rounded-xl border-2 border-gray-200 dark:border-gray-700 {config?.borderHover || 'hover:border-[#52B8FF]'} hover:shadow-lg transition-all duration-200 overflow-hidden text-left"
								>
									<!-- Visual Preview Area -->
									<div class="relative h-16 bg-gradient-to-b from-gray-50 to-white dark:from-gray-800 dark:to-gray-900 overflow-hidden">
										<!-- Background pattern -->
										<div class="absolute inset-0 opacity-[0.03] dark:opacity-[0.05]"
											style="background-image: radial-gradient(circle, currentColor 1px, transparent 1px); background-size: 8px 8px;">
										</div>

										<!-- Mini diagram based on transform type -->
										<div class="absolute inset-0 flex items-center justify-center">
											{#if transformType === 'SkipRecords'}
												<div class="flex items-center gap-1">
													<div class="space-y-0.5">
														<div class="w-6 h-1 rounded bg-rose-300"></div>
														<div class="w-6 h-1 rounded bg-rose-200 opacity-50"></div>
														<div class="w-6 h-1 rounded bg-rose-300"></div>
													</div>
													<SkipForward size={14} class="text-rose-400 mx-1" />
													<div class="space-y-0.5">
														<div class="w-6 h-1 rounded bg-rose-400"></div>
														<div class="w-6 h-1 rounded bg-rose-400"></div>
													</div>
												</div>
											{:else if transformType === 'CombineRecords'}
												<div class="flex items-center gap-1">
													<div class="space-y-0.5">
														<div class="w-4 h-1 rounded bg-blue-300"></div>
														<div class="w-4 h-1 rounded bg-blue-400"></div>
													</div>
													<Combine size={14} class="text-blue-400 mx-1" />
													<div class="w-6 h-2 rounded bg-blue-400"></div>
												</div>
											{:else if transformType === 'RenameFieldsTransform'}
												<div class="flex items-center gap-2">
													<div class="px-1.5 py-0.5 bg-amber-200 rounded text-[8px] font-mono text-amber-700">old</div>
													<ArrowLeftRight size={12} class="text-amber-400" />
													<div class="px-1.5 py-0.5 bg-amber-300 rounded text-[8px] font-mono text-amber-800">new</div>
												</div>
											{:else if transformType === 'AddNewFieldTransform'}
												<div class="flex items-center gap-1">
													<div class="space-y-0.5">
														<div class="w-5 h-1 rounded bg-emerald-300"></div>
														<div class="w-5 h-1 rounded bg-emerald-300"></div>
													</div>
													<PlusCircle size={12} class="text-emerald-500" />
													<div class="space-y-0.5">
														<div class="w-7 h-1 rounded bg-emerald-400"></div>
														<div class="w-7 h-1 rounded bg-emerald-400"></div>
													</div>
												</div>
											{:else if transformType === 'CreateImageUrlTransform'}
												<div class="flex items-center gap-2">
													<div class="w-6 h-6 rounded bg-[#7661FF]/20 flex items-center justify-center">
														<Image size={12} class="text-[#7661FF]" />
													</div>
													<ArrowLeftRight size={10} class="text-[#7661FF]/60" />
													<div class="px-1 py-0.5 bg-[#7661FF]/30 rounded text-[7px] font-mono text-[#7661FF]">data:...</div>
												</div>
											{:else if transformType === 'CreateAudioUrlTransform'}
												<div class="flex items-center gap-2">
													<div class="w-6 h-6 rounded bg-pink-200 flex items-center justify-center">
														<AudioLines size={12} class="text-pink-500" />
													</div>
													<ArrowLeftRight size={10} class="text-pink-400" />
													<div class="px-1 py-0.5 bg-pink-300 rounded text-[7px] font-mono text-pink-700">data:...</div>
												</div>
											{:else if transformType === 'CartesianProductTransform'}
												<div class="grid grid-cols-3 gap-0.5">
													{#each Array(9) as _, i}
														<div class="w-2 h-2 rounded-sm {i % 2 === 0 ? 'bg-cyan-400' : 'bg-cyan-300'}"></div>
													{/each}
												</div>
											{:else}
												<div class="p-2 rounded-lg {config?.bgClass || 'bg-gray-100'}">
													<Icon size={20} class={config?.iconClass || 'text-gray-500'} />
												</div>
											{/if}
										</div>
									</div>

									<!-- Label Section -->
									<div class="flex items-center justify-between p-3 bg-white dark:bg-gray-800 border-t border-gray-100 dark:border-gray-700/50">
										<div class="flex items-center gap-2 min-w-0">
											<div class="p-1.5 rounded-lg {config?.bgClass || 'bg-gray-100'} group-hover:scale-105 transition-transform">
												<Icon size={12} class={config?.iconClass || 'text-gray-500'} />
											</div>
											<div class="min-w-0">
												<div class="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
													{meta?.name || transformType}
												</div>
												<div class="text-[10px] text-gray-500 dark:text-gray-400 truncate">
													{meta?.description || 'Transform data'}
												</div>
											</div>
										</div>
									</div>
								</button>
							{/each}
						</div>
					</div>
				{/each}

				<!-- Custom Transform Option -->
				<div>
					<div class="flex items-center gap-3 mb-3">
						<div class="p-1.5 rounded-lg bg-gray-100 dark:bg-gray-800">
							<Code size={14} class="text-gray-500 dark:text-gray-400" />
						</div>
						<div>
							<h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								Custom Transform
							</h3>
							<p class="text-xs text-gray-500 dark:text-gray-400">Use your own transform class</p>
						</div>
					</div>

					<button
						onclick={() => selectTransform('custom')}
						class="w-full flex items-center gap-4 p-4 rounded-xl border-2 border-dashed border-gray-300 dark:border-gray-600 hover:border-[#7661FF] dark:hover:border-[#7661FF] hover:bg-[#7661FF]/5 dark:hover:bg-[#7661FF]/10 transition-all group"
					>
						<div class="p-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 group-hover:bg-[#7661FF]/15 dark:group-hover:bg-[#7661FF]/20 transition-colors">
							<Settings size={20} class="text-gray-400 group-hover:text-[#7661FF] transition-colors" />
						</div>
						<div class="flex-1 text-left">
							<div class="font-medium text-gray-700 dark:text-gray-300 group-hover:text-[#7661FF] dark:group-hover:text-[#52B8FF]">
								Custom Transform Module
							</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								Specify a custom module path for your own transform implementation
							</div>
						</div>
						<div class="px-3 py-1.5 rounded-lg text-xs font-medium text-gray-500 bg-gray-100 dark:bg-gray-800 group-hover:text-[#7661FF] group-hover:bg-[#7661FF]/15 dark:group-hover:bg-[#7661FF]/20 transition-colors">
							Advanced
						</div>
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
