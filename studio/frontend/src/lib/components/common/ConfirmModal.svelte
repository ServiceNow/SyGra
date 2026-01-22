<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, AlertTriangle, Trash2, Check } from 'lucide-svelte';

	interface Props {
		title?: string;
		message: string;
		confirmText?: string;
		cancelText?: string;
		variant?: 'danger' | 'warning' | 'info';
	}

	let {
		title = 'Confirm Action',
		message,
		confirmText = 'Confirm',
		cancelText = 'Cancel',
		variant = 'danger'
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		confirm: void;
		cancel: void;
	}>();

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dispatch('cancel');
		}
	}

	const variantStyles = {
		danger: {
			icon: Trash2,
			iconBg: 'bg-error-light',
			iconColor: 'text-error',
			buttonBg: 'bg-error hover:bg-error/90',
			buttonText: 'text-white'
		},
		warning: {
			icon: AlertTriangle,
			iconBg: 'bg-warning-light',
			iconColor: 'text-warning',
			buttonBg: 'bg-warning hover:bg-warning/90',
			buttonText: 'text-white'
		},
		info: {
			icon: Check,
			iconBg: 'bg-info-light',
			iconColor: 'text-info',
			buttonBg: 'bg-info hover:bg-info/90',
			buttonText: 'text-white'
		}
	};

	const style = variantStyles[variant];
	const IconComponent = style.icon;
</script>

<svelte:window onkeydown={handleKeydown} />

<div
	class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
	onclick={() => dispatch('cancel')}
>
	<div
		class="bg-surface rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-surface-border">
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg {style.iconBg}">
					<IconComponent size={20} class={style.iconColor} />
				</div>
				<h3 class="text-lg font-semibold text-text-primary">
					{title}
				</h3>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1.5 rounded-lg hover:bg-surface-hover text-text-muted transition-colors"
			>
				<X size={18} />
			</button>
		</div>

		<!-- Content -->
		<div class="px-6 py-5">
			<p class="text-sm text-text-secondary">
				{message}
			</p>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 bg-surface-secondary border-t border-surface-border">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-sm font-medium text-text-secondary bg-surface border border-surface-border rounded-lg hover:bg-surface-hover transition-colors"
			>
				{cancelText}
			</button>
			<button
				onclick={() => dispatch('confirm')}
				class="px-4 py-2 text-sm font-medium {style.buttonText} {style.buttonBg} rounded-lg transition-colors"
			>
				{confirmText}
			</button>
		</div>
	</div>
</div>
