<script lang="ts">
	import { Code, Settings, Info, ChevronDown, ChevronUp, FileCode2 } from 'lucide-svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';

	interface Props {
		modulePath: string;
		params: Record<string, unknown>;
		isEditing?: boolean;
		onUpdate: (params: Record<string, unknown>) => void;
		onModulePathChange: (modulePath: string) => void;
	}

	let { modulePath, params, isEditing = false, onUpdate, onModulePathChange }: Props = $props();

	// Mode: 'module' (reference existing class) or 'inline' (write code here)
	let mode = $state<'module' | 'inline'>('module');

	// JSON editor state
	let paramsJson = $state(JSON.stringify(params || {}, null, 2));
	let jsonError = $state<string | null>(null);

	// Python code editor state
	let pythonCode = $state(params._code as string || getDefaultPythonCode());
	let codeExpanded = $state(true);

	// Initialize mode based on existing data
	$effect(() => {
		if (params._code) {
			mode = 'inline';
			pythonCode = params._code as string;
		} else if (modulePath) {
			mode = 'module';
		}
	});

	// Sync with params
	$effect(() => {
		const { _code, ...rest } = params || {};
		paramsJson = JSON.stringify(rest || {}, null, 2);
		jsonError = null;
	});

	function getDefaultPythonCode(): string {
		return `from abc import abstractmethod
from typing import Any

from sygra.processors.data_transform import DataTransform


class MyCustomTransform(DataTransform):
    """Custom data transformation.

    Transforms a list of records by applying custom logic.
    """

    @property
    def name(self) -> str:
        return "my_custom_transform"

    def transform(
        self, data: list[dict[str, Any]], params: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply transformation to records.

        Args:
            data: List of records to transform
            params: Parameters from the transform config

        Returns:
            Transformed list of records
        """
        result = []
        for record in data:
            # Your transformation logic here
            transformed = {**record}
            result.append(transformed)
        return result
`;
	}

	function handleModulePathInput(e: Event) {
		const input = e.target as HTMLInputElement;
		onModulePathChange(input.value);
	}

	function handleParamsChange(value: string) {
		paramsJson = value;
		try {
			const parsed = JSON.parse(value);
			jsonError = null;
			if (mode === 'inline' && pythonCode) {
				onUpdate({ ...parsed, _code: pythonCode });
			} else {
				onUpdate(parsed);
			}
		} catch (e) {
			jsonError = 'Invalid JSON';
		}
	}

	function handleCodeChange(value: string) {
		pythonCode = value;
		try {
			const currentParams = JSON.parse(paramsJson);
			onUpdate({ ...currentParams, _code: value });
		} catch {
			onUpdate({ _code: value });
		}
	}

	function handleModeChange(newMode: 'module' | 'inline') {
		mode = newMode;
		if (newMode === 'inline') {
			// When switching to inline, add code to params
			try {
				const currentParams = JSON.parse(paramsJson);
				onUpdate({ ...currentParams, _code: pythonCode });
			} catch {
				onUpdate({ _code: pythonCode });
			}
			// Clear module path for inline mode
			onModulePathChange('');
		} else {
			// When switching to module, remove code from params
			try {
				const { _code, ...rest } = JSON.parse(paramsJson);
				onUpdate(rest);
			} catch {
				onUpdate({});
			}
		}
	}
</script>

<div class="space-y-4">
	<!-- Mode Selector -->
	{#if isEditing}
		<div class="flex gap-2 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
			<button
				type="button"
				onclick={() => handleModeChange('module')}
				class="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md transition-all
					{mode === 'module'
						? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
						: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
			>
				<Settings size={14} />
				Reference Module
			</button>
			<button
				type="button"
				onclick={() => handleModeChange('inline')}
				class="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md transition-all
					{mode === 'inline'
						? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
						: 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}"
			>
				<Code size={14} />
				Write Code
			</button>
		</div>
	{/if}

	{#if mode === 'module'}
		<!-- Module Reference Mode -->
		<div class="flex items-start gap-2 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm">
			<Settings size={16} class="text-gray-400 flex-shrink-0 mt-0.5" />
			<div class="text-gray-600 dark:text-gray-400">
				<p class="font-medium text-gray-800 dark:text-gray-200">Reference External Transform</p>
				<p class="text-xs mt-1">
					Specify a Python transform class from your project's module path.
				</p>
			</div>
		</div>

		<!-- Module Path -->
		<div>
			<label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
				Module Path
			</label>
			{#if isEditing}
				<input
					type="text"
					value={modulePath}
					oninput={handleModulePathInput}
					placeholder="myproject.transforms.MyTransform"
					class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-[#52B8FF] focus:border-transparent"
				/>
				<p class="text-xs text-gray-500 mt-1">
					Full Python import path to your transform class
				</p>
			{:else}
				<code class="text-sm font-mono text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded block">
					{modulePath || 'Not specified'}
				</code>
			{/if}
		</div>

		<!-- Parameters (JSON) -->
		<div>
			<div class="flex items-center justify-between mb-1">
				<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
					Parameters (JSON)
				</label>
				{#if jsonError}
					<span class="text-xs text-red-500">{jsonError}</span>
				{/if}
			</div>
			{#if isEditing}
				<div class="border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
					<MonacoEditor
						value={paramsJson}
						language="json"
						height="100px"
						fontSize={12}
						readonly={false}
						on:change={(e) => handleParamsChange(e.detail)}
					/>
				</div>
			{:else}
				<pre class="text-xs font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 p-2 rounded-lg overflow-auto max-h-24">{paramsJson}</pre>
			{/if}
		</div>
	{:else}
		<!-- Inline Code Mode -->
		<div class="flex items-start gap-2 p-3 bg-[#7661FF]/10 dark:bg-[#7661FF]/20 rounded-lg text-sm">
			<FileCode2 size={16} class="text-[#7661FF] flex-shrink-0 mt-0.5" />
			<div class="text-[#7661FF] dark:text-[#52B8FF]">
				<p class="font-medium">Inline Transform Code</p>
				<p class="text-xs mt-1 text-[#7661FF]/80 dark:text-[#BF71F2]">
					Write your DataTransform class directly. It will be saved with the workflow.
				</p>
			</div>
		</div>

		<!-- Python Code Editor -->
		<div>
			<button
				type="button"
				onclick={() => codeExpanded = !codeExpanded}
				class="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
			>
				<div class="flex items-center gap-2">
					<Code size={14} />
					<span>Python Code</span>
				</div>
				{#if codeExpanded}
					<ChevronUp size={14} />
				{:else}
					<ChevronDown size={14} />
				{/if}
			</button>

			{#if codeExpanded}
				<div class="mt-2 border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
					{#if isEditing}
						<MonacoEditor
							value={pythonCode}
							language="python"
							height="320px"
							fontSize={12}
							readonly={false}
							on:change={(e) => handleCodeChange(e.detail)}
						/>
					{:else}
						<MonacoEditor
							value={pythonCode}
							language="python"
							height="280px"
							fontSize={12}
							readonly={true}
						/>
					{/if}
				</div>
			{/if}
		</div>

		<!-- Parameters for inline mode -->
		<div>
			<div class="flex items-center justify-between mb-1">
				<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
					Runtime Parameters (JSON)
				</label>
				{#if jsonError}
					<span class="text-xs text-red-500">{jsonError}</span>
				{/if}
			</div>
			{#if isEditing}
				<div class="border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden">
					<MonacoEditor
						value={paramsJson}
						language="json"
						height="80px"
						fontSize={12}
						readonly={false}
						on:change={(e) => handleParamsChange(e.detail)}
					/>
				</div>
				<p class="text-xs text-gray-500 mt-1">
					These parameters are passed to the transform method at runtime
				</p>
			{:else}
				<pre class="text-xs font-mono text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 p-2 rounded-lg overflow-auto max-h-20">{paramsJson}</pre>
			{/if}
		</div>
	{/if}

	<!-- Help -->
	{#if isEditing}
		<div class="flex items-start gap-2 p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-xs text-blue-700 dark:text-blue-300">
			<Info size={14} class="flex-shrink-0 mt-0.5" />
			<div>
				<p class="font-medium mb-1">Transform class requirements:</p>
				<ul class="space-y-0.5 text-blue-600 dark:text-blue-400">
					<li>• Must extend <code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">DataTransform</code> from sygra.processors.data_transform</li>
					<li>• Implement <code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">name</code> property and <code class="bg-blue-100 dark:bg-blue-900/40 px-1 rounded">transform(self, data, params)</code> method</li>
					<li>• Accept a list of records and return transformed records</li>
				</ul>
			</div>
		</div>
	{/if}
</div>
