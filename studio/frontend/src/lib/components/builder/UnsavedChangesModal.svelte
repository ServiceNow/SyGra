<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { AlertTriangle, Save, Trash2, X } from 'lucide-svelte';

	const dispatch = createEventDispatcher<{
		saveDraft: void;
		discard: void;
		cancel: void;
	}>();

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			dispatch('cancel');
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div
	class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
	onclick={() => dispatch('cancel')}
	role="dialog"
	aria-modal="true"
	aria-labelledby="unsaved-changes-title"
>
	<div
		class="bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-3">
			<div class="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
				<AlertTriangle size={20} class="text-amber-600 dark:text-amber-400" />
			</div>
			<div>
				<h2 id="unsaved-changes-title" class="text-lg font-semibold text-gray-900 dark:text-gray-100">
					Unsaved Changes
				</h2>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					Your workflow has unsaved changes
				</p>
			</div>
		</div>

		<!-- Content -->
		<div class="px-6 py-4">
			<p class="text-gray-600 dark:text-gray-300">
				Would you like to save your work as a draft before leaving? You can continue editing it later.
			</p>
		</div>

		<!-- Actions -->
		<div class="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 flex items-center justify-end gap-3">
			<button
				onclick={() => dispatch('cancel')}
				class="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg font-medium transition-colors"
			>
				Cancel
			</button>
			<button
				onclick={() => dispatch('discard')}
				class="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-800 dark:text-gray-200 rounded-lg font-medium transition-colors"
			>
				Discard
			</button>
			<button
				onclick={() => dispatch('saveDraft')}
				class="flex items-center gap-2 px-4 py-2 bg-[#63DF4E] hover:bg-[#52c840] text-[#032D42] rounded-lg font-medium transition-colors"
			>
				<Save size={16} />
				Save Draft
			</button>
		</div>
	</div>
</div>
