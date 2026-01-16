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
			iconBg: 'bg-red-100 dark:bg-red-900/30',
			iconColor: 'text-red-600 dark:text-red-400',
			buttonBg: 'bg-red-600 hover:bg-red-700',
			buttonText: 'text-white'
		},
		warning: {
			icon: AlertTriangle,
			iconBg: 'bg-amber-100 dark:bg-amber-900/30',
			iconColor: 'text-amber-600 dark:text-amber-400',
			buttonBg: 'bg-amber-600 hover:bg-amber-700',
			buttonText: 'text-white'
		},
		info: {
			icon: Check,
			iconBg: 'bg-blue-100 dark:bg-blue-900/30',
			iconColor: 'text-blue-600 dark:text-blue-400',
			buttonBg: 'bg-blue-600 hover:bg-blue-700',
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
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-3">
				<div class="p-2 rounded-lg {style.iconBg}">
					<IconComponent size={20} class={style.iconColor} />
				</div>
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
					{title}
				</h3>
			</div>
			<button
				onclick={() => dispatch('cancel')}
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 transition-colors"
			>
				<X size={18} />
			</button>
		</div>

		<!-- Content -->
		<div class="px-6 py-5">
			<p class="text-sm text-gray-600 dark:text-gray-400">
				{message}
			</p>
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end gap-3 px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-800">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
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
