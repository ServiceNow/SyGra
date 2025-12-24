<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { X, ArrowRight, GitBranch, Link, Code, GripVertical, Edit2, Save, Trash2, Plus, ChevronUp, ChevronDown, Check } from 'lucide-svelte';
	import { workflowStore, type WorkflowNode, type EdgeCondition, type WorkflowEdge } from '$lib/stores/workflow.svelte';
	import MonacoEditor from '$lib/components/editor/MonacoEditor.svelte';
	import ConfirmModal from '$lib/components/common/ConfirmModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';

	interface EdgeData {
		id: string;
		source: string;
		target: string;
		label?: string;
		isConditional: boolean;
		condition?: EdgeCondition;
	}

	interface Props {
		edge: EdgeData;
		sourceNode?: WorkflowNode;
		targetNode?: WorkflowNode;
		editable?: boolean;
	}

	let { edge, sourceNode, targetNode, editable = false }: Props = $props();

	const dispatch = createEventDispatcher<{
		close: void;
		update: { edgeId: string; data: Partial<WorkflowEdge> };
		delete: string;
	}>();

	const nodeTypeColors: Record<string, string> = {
		start: '#22c55e',
		end: '#ef4444',
		llm: '#8b5cf6',
		lambda: '#f97316',
		connector: '#06b6d4',
		subgraph: '#3b82f6',
		web_agent: '#ec4899',
		branch: '#eab308'
	};

	// Edit state
	let isEditing = $state(false);
	let editLabel = $state('');
	let editIsConditional = $state(false);
	let editConditionPath = $state('');
	let editPathMap = $state<Array<{ key: string; value: string }>>([]);
	let editConditionCode = $state('');
	let showCodeEditor = $state(false);
	let showDeleteConfirm = $state(false);

	// Default condition code template
	const defaultConditionCode = `def evaluate_condition(state: dict) -> str:
    """
    Evaluate the condition and return the branch to take.

    Args:
        state: The current workflow state dictionary

    Returns:
        str: The branch label (e.g., 'true', 'false', 'success', 'error')
    """
    # Example: Check if a value exists in state
    if state.get('result', {}).get('success'):
        return 'true'
    return 'false'
`;

	// Initialize edit state from edge
	$effect(() => {
		editLabel = edge.label || '';
		editIsConditional = edge.isConditional;
		editConditionPath = edge.condition?.condition_path || '';
		editPathMap = edge.condition?.path_map
			? Object.entries(edge.condition.path_map).map(([key, value]) => ({ key, value }))
			: [];
		editConditionCode = defaultConditionCode;
		showCodeEditor = false;
	});

	function startEditing() {
		isEditing = true;
	}

	function cancelEditing() {
		// Reset to original values
		editLabel = edge.label || '';
		editIsConditional = edge.isConditional;
		editConditionPath = edge.condition?.condition_path || '';
		editPathMap = edge.condition?.path_map
			? Object.entries(edge.condition.path_map).map(([key, value]) => ({ key, value }))
			: [];
		isEditing = false;
	}

	function saveEditing() {
		const pathMapObj: Record<string, string> = {};
		editPathMap.forEach(({ key, value }) => {
			if (key.trim() && value.trim()) {
				pathMapObj[key.trim()] = value.trim();
			}
		});

		const updatedEdgeData: Partial<WorkflowEdge> = {
			label: editLabel.trim() || undefined,
			is_conditional: editIsConditional,
			condition: editIsConditional && (editConditionPath.trim() || Object.keys(pathMapObj).length > 0)
				? {
					condition_path: editConditionPath.trim(),
					path_map: pathMapObj
				}
				: undefined
		};

		// Update via store
		const success = workflowStore.updateEdge(edge.id, updatedEdgeData);

		if (success) {
			// Dispatch event with edge ID and data for SvelteFlow sync
			dispatch('update', { edgeId: edge.id, data: updatedEdgeData });
			isEditing = false;
		}
	}

	function addPathMapping() {
		editPathMap = [...editPathMap, { key: '', value: '' }];
	}

	function removePathMapping(index: number) {
		editPathMap = editPathMap.filter((_, i) => i !== index);
	}

	function requestDeleteEdge() {
		showDeleteConfirm = true;
	}

	function confirmDeleteEdge() {
		workflowStore.removeEdge(edge.id);
		dispatch('delete', edge.id);
		showDeleteConfirm = false;
		dispatch('close');
	}

	function cancelDeleteEdge() {
		showDeleteConfirm = false;
	}

	// Get all workflow nodes for path mapping dropdowns
	let workflowNodes = $derived(workflowStore.currentWorkflow?.nodes || []);

	// Node options for CustomSelect
	let nodeOptions = $derived(workflowNodes.map(node => ({
		value: node.id,
		label: node.summary || node.id
	})));

	// Helper to get node info by ID
	function getNodeInfo(nodeId: string): { name: string; type: string; color: string } {
		const node = workflowNodes.find(n => n.id === nodeId);
		return {
			name: node?.summary || nodeId,
			type: node?.node_type || 'unknown',
			color: nodeTypeColors[node?.node_type ?? 'llm'] || '#9ca3af'
		};
	}

	// Resizable panel state
	let panelWidth = $state(360);
	let isResizing = $state(false);
	let startX = $state(0);
	let startWidth = $state(0);

	function handleMouseDown(e: MouseEvent) {
		isResizing = true;
		startX = e.clientX;
		startWidth = panelWidth;
		document.addEventListener('mousemove', handleMouseMove);
		document.addEventListener('mouseup', handleMouseUp);
		document.body.style.cursor = 'ew-resize';
		document.body.style.userSelect = 'none';
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isResizing) return;
		const diff = startX - e.clientX;
		const newWidth = Math.max(320, Math.min(600, startWidth + diff));
		panelWidth = newWidth;
	}

	function handleMouseUp() {
		isResizing = false;
		document.removeEventListener('mousemove', handleMouseMove);
		document.removeEventListener('mouseup', handleMouseUp);
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
	}
</script>

<aside
	class="fixed right-0 top-0 h-full border-l border-gray-200 dark:border-gray-800 bg-surface overflow-y-auto flex flex-col shadow-xl z-50"
	style="width: {panelWidth}px;"
>
	<!-- Resize handle -->
	<div
		class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-violet-500/50 transition-colors z-20 group"
		onmousedown={handleMouseDown}
		role="separator"
		aria-orientation="vertical"
	>
		<div class="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
			<GripVertical size={12} class="text-gray-400" />
		</div>
	</div>
	<!-- Header -->
	<div class="sticky top-0 bg-surface border-b border-gray-200 dark:border-gray-800 px-4 py-3 flex items-center justify-between z-10">
		<div class="flex items-center gap-2">
			<div
				class="w-8 h-8 rounded-lg flex items-center justify-center text-white"
				style="background-color: {(isEditing ? editIsConditional : edge.isConditional) ? '#f59e0b' : '#9ca3af'}"
			>
				{#if isEditing ? editIsConditional : edge.isConditional}
					<GitBranch size={18} />
				{:else}
					<Link size={18} />
				{/if}
			</div>
			<div>
				<h2 class="text-sm font-semibold text-gray-800 dark:text-gray-200">
					{(isEditing ? editIsConditional : edge.isConditional) ? 'Conditional Edge' : 'Edge Connection'}
				</h2>
				{#if !isEditing && edge.label}
					<span class="text-xs text-amber-600 dark:text-amber-400 font-medium">
						{edge.label}
					</span>
				{/if}
			</div>
		</div>
		<div class="flex items-center gap-1">
			{#if editable}
				{#if isEditing}
					<button
						onclick={cancelEditing}
						class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
						title="Cancel"
					>
						<X size={16} />
					</button>
					<button
						onclick={saveEditing}
						class="p-1.5 rounded-lg text-violet-600 hover:text-violet-700 dark:text-violet-400 hover:bg-violet-100 dark:hover:bg-violet-900/30 transition-colors"
						title="Save changes"
					>
						<Save size={16} />
					</button>
				{:else}
					<button
						onclick={startEditing}
						class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 hover:text-violet-600 dark:hover:text-violet-400 transition-colors"
						title="Edit edge"
					>
						<Edit2 size={16} />
					</button>
					<button
						onclick={requestDeleteEdge}
						class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
						title="Delete edge"
					>
						<Trash2 size={16} />
					</button>
				{/if}
			{/if}
			<button
				onclick={() => dispatch('close')}
				class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
				title="Close"
			>
				<X size={18} />
			</button>
		</div>
	</div>

	<!-- Content -->
	<div class="flex-1 p-4 space-y-4">
		{#if isEditing}
			<!-- EDIT MODE -->

			<!-- Edge Type Toggle -->
			<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
				<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-3">
					<Link size={12} />
					Edge Type
				</div>
				<div class="flex gap-2">
					<button
						onclick={() => editIsConditional = false}
						class="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border transition-all {!editIsConditional
							? 'border-violet-500 bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 shadow-sm'
							: 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-500 hover:border-gray-300 dark:hover:border-gray-600'}"
					>
						{#if !editIsConditional}
							<Check size={14} class="text-violet-600 dark:text-violet-400" />
						{/if}
						<Link size={16} />
						<span class="text-sm font-medium">Sequential</span>
					</button>
					<button
						onclick={() => editIsConditional = true}
						class="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border transition-all {editIsConditional
							? 'border-violet-500 bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 shadow-sm'
							: 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-500 hover:border-gray-300 dark:hover:border-gray-600'}"
					>
						{#if editIsConditional}
							<Check size={14} class="text-violet-600 dark:text-violet-400" />
						{/if}
						<GitBranch size={16} />
						<span class="text-sm font-medium">Conditional</span>
					</button>
				</div>
			</div>

			<!-- Edge Label -->
			<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
				<span class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
					Edge Label
				</span>
				<input
					type="text"
					bind:value={editLabel}
					placeholder="e.g., true, success, route_a"
					aria-label="Edge label"
					class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 text-sm focus:ring-2 focus:ring-violet-500 focus:border-transparent"
				/>
				<p class="mt-2 text-xs text-gray-500">
					Label shown on the edge, used for routing in conditional branches
				</p>
			</div>

			<!-- Conditional Edge Settings -->
			{#if editIsConditional}
				<!-- Condition Path -->
				<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
						<Code size={12} />
						Condition Function Path
					</div>
					<input
						type="text"
						bind:value={editConditionPath}
						placeholder="e.g., my_module.evaluate_condition"
						aria-label="Condition function path"
						class="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 text-sm font-mono focus:ring-2 focus:ring-violet-500 focus:border-transparent"
					/>
					<p class="mt-2 text-xs text-gray-500">
						Python module path to the function that evaluates the condition
					</p>

					<!-- Collapsible Code Editor -->
					<button
						onclick={() => showCodeEditor = !showCodeEditor}
						class="mt-3 flex items-center gap-2 text-xs font-medium text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300"
					>
						<Code size={14} />
						{showCodeEditor ? 'Hide Code Template' : 'Show Code Template'}
						{#if showCodeEditor}
							<ChevronUp size={14} />
						{:else}
							<ChevronDown size={14} />
						{/if}
					</button>

					{#if showCodeEditor}
						<div class="mt-2 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
							<MonacoEditor
								bind:value={editConditionCode}
								language="python"
								height="200px"
								theme="vs-dark"
								fontSize={12}
							/>
						</div>
						<p class="mt-2 text-xs text-gray-500">
							Template for the condition function. Copy and use in your module.
						</p>
					{/if}
				</div>

				<!-- Path Map -->
				<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex items-center justify-between mb-3">
						<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
							<GitBranch size={12} />
							Branch Path Mappings
						</div>
						<button
							onclick={addPathMapping}
							class="flex items-center gap-1 px-2 py-1 text-xs bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 rounded hover:bg-violet-200 dark:hover:bg-violet-800/50 transition-colors"
						>
							<Plus size={12} />
							Add Mapping
						</button>
					</div>

					{#if editPathMap.length === 0}
						<div class="text-sm text-gray-500 italic p-4 bg-white dark:bg-gray-900 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-center">
							No path mappings. Click "Add Mapping" to route to different nodes.
						</div>
					{:else}
						<div class="space-y-2">
							{#each editPathMap as mapping, index}
								<div class="p-2 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
									<div class="flex items-center gap-2">
										<input
											type="text"
											bind:value={mapping.key}
											placeholder="Condition value"
											aria-label="Condition value"
											class="flex-1 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 text-sm font-mono focus:ring-2 focus:ring-violet-500 focus:border-transparent"
										/>
										<ArrowRight size={16} class="text-gray-400 flex-shrink-0" />
										<div class="flex-1">
											<CustomSelect
												options={nodeOptions}
												value={mapping.value}
												placeholder="Select target node"
												onChange={(val) => mapping.value = val}
											/>
										</div>
										<button
											onclick={() => removePathMapping(index)}
											class="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-600 dark:hover:text-red-400 transition-colors"
										>
											<Trash2 size={14} />
										</button>
									</div>
								</div>
							{/each}
						</div>
					{/if}
					<p class="mt-2 text-xs text-gray-500">
						Map condition return values to target nodes. Example: "true" → NodeA, "false" → NodeB
					</p>
				</div>
			{/if}

			<!-- Connection (read-only) -->
			<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
				<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-3">
					<ArrowRight size={12} />
					Connection
				</div>
				<div class="flex items-center gap-3 p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<div
								class="w-3 h-3 rounded-full flex-shrink-0"
								style="background-color: {nodeTypeColors[sourceNode?.node_type ?? 'llm']}"
							></div>
							<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
								{sourceNode?.summary ?? edge.source}
							</span>
						</div>
						<div class="text-xs text-gray-500 mt-0.5 ml-5 capitalize">
							{sourceNode?.node_type ?? 'unknown'}
						</div>
					</div>
					<ArrowRight size={18} class="text-violet-500 flex-shrink-0" />
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<div
								class="w-3 h-3 rounded-full flex-shrink-0"
								style="background-color: {nodeTypeColors[targetNode?.node_type ?? 'llm']}"
							></div>
							<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
								{targetNode?.summary ?? edge.target}
							</span>
						</div>
						<div class="text-xs text-gray-500 mt-0.5 ml-5 capitalize">
							{targetNode?.node_type ?? 'unknown'}
						</div>
					</div>
				</div>
			</div>

		{:else}
			<!-- DISPLAY MODE -->

			<!-- Edge Type -->
			<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
				<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
					<Link size={12} />
					Edge Type
				</div>
				<div class="flex items-center gap-2">
					<span
						class="px-3 py-1.5 rounded-lg text-sm font-medium {edge.isConditional
							? 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300'
							: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'}"
					>
						{#if edge.isConditional}
							<GitBranch size={14} class="inline -mt-0.5 mr-1" />
						{:else}
							<Link size={14} class="inline -mt-0.5 mr-1" />
						{/if}
						{edge.isConditional ? 'Conditional' : 'Sequential'}
					</span>
				</div>
			</div>

			<!-- Connection -->
			<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
				<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-3">
					<ArrowRight size={12} />
					Connection
				</div>
				<div class="flex items-center gap-3 p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<div
								class="w-3 h-3 rounded-full flex-shrink-0"
								style="background-color: {nodeTypeColors[sourceNode?.node_type ?? 'llm']}"
							></div>
							<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
								{sourceNode?.summary ?? edge.source}
							</span>
						</div>
						<div class="text-xs text-gray-500 mt-0.5 ml-5 capitalize">
							{sourceNode?.node_type ?? 'unknown'}
						</div>
					</div>
					<ArrowRight size={18} class="text-violet-500 flex-shrink-0" />
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<div
								class="w-3 h-3 rounded-full flex-shrink-0"
								style="background-color: {nodeTypeColors[targetNode?.node_type ?? 'llm']}"
							></div>
							<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
								{targetNode?.summary ?? edge.target}
							</span>
						</div>
						<div class="text-xs text-gray-500 mt-0.5 ml-5 capitalize">
							{targetNode?.node_type ?? 'unknown'}
						</div>
					</div>
				</div>
			</div>

			<!-- Edge Label -->
			{#if edge.label}
				<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
						<Code size={12} />
						Branch Label
					</div>
					<div class="px-3 py-2 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-700 rounded-lg">
						<span class="text-sm font-mono text-violet-700 dark:text-violet-300">
							{edge.label}
						</span>
					</div>
				</div>
			{/if}

			<!-- Condition Code -->
			{#if edge.condition?.condition_path}
				<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
						<Code size={12} />
						Condition Function
					</div>
					<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-white dark:bg-gray-900 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 break-all">
						{edge.condition.condition_path}
					</div>
				</div>
			{/if}

			<!-- Path Map -->
			{#if edge.condition?.path_map && Object.keys(edge.condition.path_map).length > 0}
				<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
					<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-3">
						<GitBranch size={12} />
						Branch Routing ({Object.keys(edge.condition.path_map).length} paths)
					</div>
					<div class="space-y-2">
						{#each Object.entries(edge.condition.path_map) as [key, targetId]}
							{@const targetInfo = getNodeInfo(targetId)}
							<div class="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
								<div class="flex items-center">
									<!-- Condition Key -->
									<div class="px-3 py-2.5 bg-violet-50 dark:bg-violet-900/30 border-r border-gray-200 dark:border-gray-700">
										<span class="font-mono text-sm font-medium text-violet-700 dark:text-violet-300">"{key}"</span>
									</div>
									<!-- Arrow -->
									<div class="px-2">
										<ArrowRight size={16} class="text-violet-500" />
									</div>
									<!-- Target Node -->
									<div class="flex-1 px-3 py-2.5 flex items-center gap-2 min-w-0">
										<div
											class="w-3 h-3 rounded-full flex-shrink-0"
											style="background-color: {targetInfo.color}"
										></div>
										<div class="min-w-0">
											<div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
												{targetInfo.name}
											</div>
											<div class="text-xs text-gray-500 capitalize">
												{targetInfo.type}
											</div>
										</div>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Info for conditional edges -->
			{#if edge.isConditional}
				<div class="p-3 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-700 rounded-lg">
					<div class="flex items-start gap-2">
						<GitBranch size={16} class="text-violet-600 dark:text-violet-400 mt-0.5 flex-shrink-0" />
						<div class="text-xs text-violet-700 dark:text-violet-300">
							<strong>Conditional Edge:</strong> This connection is only followed when the condition function returns a value matching this edge's label.
						</div>
					</div>
				</div>
			{/if}

			<!-- Edit Prompt for editable mode -->
			{#if editable && !edge.isConditional}
				<div class="p-3 bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
					<div class="flex items-start gap-2">
						<Edit2 size={16} class="text-gray-500 dark:text-gray-400 mt-0.5 flex-shrink-0" />
						<div class="text-xs text-gray-600 dark:text-gray-400">
							Click the <strong>Edit</strong> button above to configure this edge as conditional and define routing paths.
						</div>
					</div>
				</div>
			{/if}
		{/if}
	</div>
</aside>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmModal
		title="Delete Edge"
		message="Are you sure you want to delete this edge? This action cannot be undone."
		confirmText="Delete"
		cancelText="Cancel"
		variant="danger"
		on:confirm={confirmDeleteEdge}
		on:cancel={cancelDeleteEdge}
	/>
{/if}
