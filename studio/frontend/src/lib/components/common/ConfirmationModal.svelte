<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, AlertTriangle, Trash2, Info } from 'lucide-svelte';

	interface Props {
		title: string;
		message: string;
		confirmText?: string;
		cancelText?: string;
		variant?: 'danger' | 'warning' | 'info';
		icon?: 'trash' | 'warning' | 'info';
	}

	let {
		title,
		message,
		confirmText = 'Confirm',
		cancelText = 'Cancel',
		variant = 'danger',
		icon = 'warning'
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		confirm: void;
		cancel: void;
	}>();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('cancel');
		}
	}

	// Variant styles
	const variantStyles = {
		danger: {
			iconBg: 'bg-red-100 dark:bg-red-900/30',
			iconColor: 'text-red-600 dark:text-red-400',
			buttonBg: 'bg-red-600 hover:bg-red-700',
			buttonText: 'text-white'
		},
		warning: {
			iconBg: 'bg-amber-100 dark:bg-amber-900/30',
			iconColor: 'text-amber-600 dark:text-amber-400',
			buttonBg: 'bg-amber-600 hover:bg-amber-700',
			buttonText: 'text-white'
		},
		info: {
			iconBg: 'bg-blue-100 dark:bg-blue-900/30',
			iconColor: 'text-blue-600 dark:text-blue-400',
			buttonBg: 'bg-blue-600 hover:bg-blue-700',
			buttonText: 'text-white'
		}
	};

	const IconComponent = icon === 'trash' ? Trash2 : icon === 'info' ? Info : AlertTriangle;
	const styles = variantStyles[variant];
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
	onclick={() => dispatch('cancel')}
	role="presentation"
>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
		onclick={(e) => e.stopPropagation()}
		role="dialog"
		aria-modal="true"
		aria-labelledby="confirmation-title"
	>
		<!-- Header -->
		<div class="flex items-start gap-4 p-6 pb-4">
			<div class="w-12 h-12 rounded-full {styles.iconBg} flex items-center justify-center flex-shrink-0">
				<IconComponent size={24} class={styles.iconColor} />
			</div>
			<div class="flex-1 min-w-0 pt-1">
				<h3 id="confirmation-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					{title}
				</h3>
				<p class="mt-2 text-sm text-gray-600 dark:text-gray-400">
					{message}
				</p>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 transition-colors flex-shrink-0"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-gray-800/50">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
			>
				{cancelText}
			</button>
			<button
				onclick={() => dispatch('confirm')}
				class="px-4 py-2 text-sm font-medium {styles.buttonBg} {styles.buttonText} rounded-lg transition-colors"
			>
				{confirmText}
			</button>
		</div>
	</div>
</div>
