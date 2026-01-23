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
			iconBg: 'bg-error-light',
			iconColor: 'text-error',
			buttonBg: 'bg-error hover:bg-error/90',
			buttonText: 'text-white'
		},
		warning: {
			iconBg: 'bg-warning-light',
			iconColor: 'text-warning',
			buttonBg: 'bg-warning hover:bg-warning/90',
			buttonText: 'text-white'
		},
		info: {
			iconBg: 'bg-info-light',
			iconColor: 'text-info',
			buttonBg: 'bg-info hover:bg-info/90',
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
		class="bg-surface rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
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
				<h3 id="confirmation-title" class="text-lg font-semibold text-text-primary">
					{title}
				</h3>
				<p class="mt-2 text-sm text-text-secondary">
					{message}
				</p>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1 rounded-lg hover:bg-surface-hover text-text-muted transition-colors flex-shrink-0"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 bg-surface-secondary">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-hover rounded-lg transition-colors"
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
