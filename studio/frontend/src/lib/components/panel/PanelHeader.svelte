<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, ChevronLeft, ChevronRight, Copy, Trash2, Edit3, Save, Loader2, Files } from 'lucide-svelte';

	interface Action {
		id: string;
		icon: any;
		label: string;
		onClick: () => void;
		disabled?: boolean;
		loading?: boolean;
		variant?: 'default' | 'danger' | 'primary';
		hidden?: boolean;
	}

	interface Props {
		title: string;
		subtitle?: string;
		icon: any;
		iconColor?: string;
		nodeId?: string;
		// Navigation
		showNavigation?: boolean;
		hasPrevious?: boolean;
		hasNext?: boolean;
		onPrevious?: () => void;
		onNext?: () => void;
		// Edit mode
		isEditing?: boolean;
		hasChanges?: boolean;
		isSaving?: boolean;
		canEdit?: boolean;
		onStartEdit?: () => void;
		onCancelEdit?: () => void;
		onSave?: () => void;
		// Quick actions
		showCopyId?: boolean;
		showDuplicate?: boolean;
		showDelete?: boolean;
		onCopyId?: () => void;
		onDuplicate?: () => void;
		onDelete?: () => void;
		// Close
		onClose: () => void;
	}

	let {
		title,
		subtitle,
		icon: Icon,
		iconColor = '#8b5cf6',
		nodeId,
		showNavigation = false,
		hasPrevious = false,
		hasNext = false,
		onPrevious,
		onNext,
		isEditing = false,
		hasChanges = false,
		isSaving = false,
		canEdit = true,
		onStartEdit,
		onCancelEdit,
		onSave,
		showCopyId = true,
		showDuplicate = false,
		showDelete = false,
		onCopyId,
		onDuplicate,
		onDelete,
		onClose
	}: Props = $props();

	const dispatch = createEventDispatcher();

	let showCopiedToast = $state(false);

	async function handleCopyId() {
		if (nodeId && onCopyId) {
			onCopyId();
		} else if (nodeId) {
			await navigator.clipboard.writeText(nodeId);
		}
		showCopiedToast = true;
		setTimeout(() => {
			showCopiedToast = false;
		}, 2000);
	}
</script>

<div class="sticky top-0 bg-surface z-10">
	<!-- Gradient accent bar -->
	<div
		class="h-1 w-full"
		style="background: linear-gradient(90deg, {iconColor}, {iconColor}88)"
	></div>

	<!-- Main header content -->
	<div class="px-4 py-3 border-b border-gray-200 dark:border-gray-800">
		<!-- Top row: Icon, Title, Navigation, Close -->
		<div class="flex items-center justify-between gap-3">
			<div class="flex items-center gap-3 min-w-0 flex-1">
				<!-- Icon -->
				<div
					class="w-10 h-10 rounded-xl flex items-center justify-center text-white flex-shrink-0 shadow-sm"
					style="background-color: {iconColor}"
				>
					<Icon size={20} />
				</div>

				<!-- Title and subtitle -->
				<div class="min-w-0 flex-1">
					<h3 class="font-semibold text-gray-900 dark:text-gray-100 text-base truncate">
						{title}
					</h3>
					{#if subtitle}
						<div class="text-xs text-gray-500 dark:text-gray-400 truncate flex items-center gap-1.5">
							<span>{subtitle}</span>
							{#if nodeId}
								<span class="text-gray-300 dark:text-gray-600">•</span>
								<code class="text-gray-400 dark:text-gray-500 font-mono text-[10px]">{nodeId}</code>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<!-- Right side: Navigation + Close -->
			<div class="flex items-center gap-1 flex-shrink-0">
				{#if showNavigation}
					<div class="flex items-center gap-0.5 mr-2">
						<button
							onclick={onPrevious}
							disabled={!hasPrevious}
							class="p-1.5 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
							title="Previous node ([)"
						>
							<ChevronLeft size={18} />
						</button>
						<button
							onclick={onNext}
							disabled={!hasNext}
							class="p-1.5 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
							title="Next node (])"
						>
							<ChevronRight size={18} />
						</button>
					</div>
				{/if}

				<button
					onclick={onClose}
					class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
					title="Close (Escape)"
				>
					<X size={20} />
				</button>
			</div>
		</div>

		<!-- Action bar -->
		<div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
			<!-- Left: Quick actions -->
			<div class="flex items-center gap-1">
				{#if showCopyId && nodeId}
					<button
						onclick={handleCopyId}
						class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-800 dark:hover:text-gray-200"
						title="Copy node ID"
					>
						<Copy size={12} />
						<span>Copy ID</span>
					</button>
				{/if}

				{#if showDuplicate && onDuplicate}
					<button
						onclick={onDuplicate}
						class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 hover:text-gray-800 dark:hover:text-gray-200"
						title="Duplicate node (Cmd+D)"
					>
						<Files size={12} />
						<span>Duplicate</span>
					</button>
				{/if}

				{#if showDelete && onDelete}
					<button
						onclick={onDelete}
						class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors bg-gray-100 dark:bg-gray-800 text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-700 dark:hover:text-red-300"
						title="Delete node"
					>
						<Trash2 size={12} />
						<span>Delete</span>
					</button>
				{/if}
			</div>

			<!-- Right: Edit/Save actions -->
			<div class="flex items-center gap-1">
				{#if canEdit}
					{#if isEditing}
						<button
							onclick={onCancelEdit}
							class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
							title="Cancel editing"
						>
							<X size={12} />
							<span>Cancel</span>
						</button>
						<button
							onclick={onSave}
							disabled={!hasChanges || isSaving}
							class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
							title="Save changes (Cmd+S)"
						>
							{#if isSaving}
								<Loader2 size={12} class="animate-spin" />
								<span>Saving...</span>
							{:else}
								<Save size={12} />
								<span>Save</span>
							{/if}
						</button>
					{:else}
						<button
							onclick={onStartEdit}
							class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-800/50"
							title="Edit node (Cmd+E)"
						>
							<Edit3 size={12} />
							<span>Edit</span>
						</button>
					{/if}
				{/if}
			</div>
		</div>
	</div>

	<!-- Copied toast -->
	{#if showCopiedToast}
		<div class="absolute top-14 left-1/2 -translate-x-1/2 px-3 py-1.5 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-xs font-medium rounded-lg shadow-lg animate-fade-in">
			Copied to clipboard!
		</div>
	{/if}
</div>

<style>
	@keyframes fade-in {
		from {
			opacity: 0;
			transform: translateX(-50%) translateY(-4px);
		}
		to {
			opacity: 1;
			transform: translateX(-50%) translateY(0);
		}
	}

	.animate-fade-in {
		animation: fade-in 0.2s ease-out;
	}
</style>
