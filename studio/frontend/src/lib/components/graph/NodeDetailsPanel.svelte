<script lang="ts">
	import { createEventDispatcher, onMount, tick } from 'svelte';
	import { X, Bot, Zap, Link, Play, Square, Globe, Boxes, Save, ChevronDown, ChevronRight, Code, Settings, MessageSquare, Info, GitBranch, Plus, Trash2, Edit3, GripVertical, Database, Download, Cloud, Server, HardDrive, ArrowRight, Map as MapIcon, Shuffle, Wrench, AlertCircle, Library, Eye, EyeOff, Loader2, Layers, Copy, GitCompareArrows, Thermometer, Variable, Check, Search, AlertTriangle } from 'lucide-svelte';
	import { workflowStore, type WorkflowNode, type NodeExecutionState, type PromptMessage, type NodeConfigOverride, type InnerGraph, type MultiModalContentPart } from '$lib/stores/workflow.svelte';
	import { toolStore } from '$lib/stores/tool.svelte';
	import { panelStore } from '$lib/stores/panel.svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import ConfirmModal from '$lib/components/common/ConfirmModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';
	import ToolPickerModal from '$lib/components/builder/ToolPickerModal.svelte';
	import PanelHeader from '$lib/components/panel/PanelHeader.svelte';
	import PanelTabs from '$lib/components/panel/PanelTabs.svelte';
	import DataConfigSection from '$lib/components/data/DataConfigSection.svelte';
	import PromptTextarea from '$lib/components/ui/PromptTextarea.svelte';
	import StateVariableInput from '$lib/components/ui/StateVariableInput.svelte';
	import { collectStateVariablesForNode, validateNodePrompts, type StateVariable, type PromptValidationResult } from '$lib/utils/stateVariables';
	import type { DataSourceDetails, DataSinkDetails, TransformConfig } from '$lib/stores/workflow.svelte';

	interface Props {
		node?: WorkflowNode;
		nodeState?: NodeExecutionState;
		startInEditMode?: boolean;
		// Navigation support
		showNavigation?: boolean;
		hasPrevious?: boolean;
		hasNext?: boolean;
		onPrevious?: () => void;
		onNext?: () => void;
		onDuplicate?: () => void;
	}

	let {
		node,
		nodeState,
		startInEditMode = false,
		showNavigation = false,
		hasPrevious = false,
		hasNext = false,
		onPrevious,
		onNext,
		onDuplicate
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		close: void;
		save: { nodeId: string; newId?: string; updates: Partial<WorkflowNode> };
		delete: { nodeId: string };
		navigate: string; // Navigate to another node
	}>();

	// Delete node
	let isDeleting = $state(false);
	let showDeleteConfirm = $state(false);

	function requestDeleteNode() {
		showDeleteConfirm = true;
	}

	async function confirmDeleteNode() {
		if (!node) return;

		// Capture the node ID before any reactive updates
		const nodeIdToDelete = node.id;

		isDeleting = true;
		showDeleteConfirm = false;

		// Perform the deletion - the WorkflowBuilder will auto-sync via $effect
		const success = await workflowStore.deleteNode(nodeIdToDelete);

		isDeleting = false;

		if (success) {
			// Dispatch events for parent to handle cleanup
			dispatch('delete', { nodeId: nodeIdToDelete });
			dispatch('close');
		}
	}

	function cancelDeleteNode() {
		showDeleteConfirm = false;
	}

	// Tab state
	type TabId = 'details' | 'prompt' | 'models' | 'tools' | 'code' | 'overrides' | 'settings';
	let activeTab = $state<TabId>('details');

	// Edit state
	let isEditing = $state(false);
	let isSaving = $state(false);
	let hasChanges = $state(false);

	// Track last initialized node to prevent re-initialization on save
	let lastInitializedNodeId = '';

	// Track workflow ID for data columns fetch optimization
	let lastFetchedWorkflowId = '';

	// Editable fields
	let editNodeId = $state('');
	let editSummary = $state('');
	let editDescription = $state('');
	let editModel = $state('');
	let editPrompts = $state<PromptMessage[]>([]);
	let editPreProcess = $state('');
	let editPostProcess = $state('');
	let editFunctionPath = $state('');
	let editModelParameters = $state<Record<string, any>>({});

	// Track if code was loaded from files
	let preProcessCodeLoaded = $state(false);
	let postProcessCodeLoaded = $state(false);
	let lambdaCodeLoaded = $state(false);
	let outputGeneratorCodeLoaded = $state(false);
	let dataTransformCodeLoaded = $state(false);
	let isLoadingCode = $state(false);

	// Code content for Monaco editor (for inline code editing)
	let preProcessCode = $state('');
	let postProcessCode = $state('');
	let lambdaCode = $state('');
	let branchConditionCode = $state('');

	// Data node edit state
	let editDataSourceType = $state<'hf' | 'disk' | 'servicenow'>('hf');
	let editDataRepoId = $state('');
	let editDataConfigName = $state('');
	let editDataSplit = $state('train');
	let editDataFilePath = $state('');
	let editDataTable = $state('');
	let editDataFields = $state('');
	let editDataLimit = $state<number | undefined>(undefined);
	let editDataFilters = $state('');

	// Sink edit state
	let editSinkAlias = $state('');
	let editSinkType = $state<'servicenow' | 'disk' | 'hf'>('servicenow');
	let editSinkTable = $state('');
	let editSinkOperation = $state<'insert' | 'update'>('insert');
	let editSinkFilePath = $state('');
	let editSinkRepoId = $state('');
	let editSinkSplit = $state('train');

	// Data transformations edit state (legacy - keeping for backward compatibility)
	let editTransformations = $state<Array<{ transform: string; params: string }>>([]);
	let editTransformCode = $state('');

	// Multi-source and transform pipeline state (new unified data configuration)
	let editDataSources = $state<DataSourceDetails[]>([]);
	let editIdColumn = $state<string | undefined>(undefined);
	let editSourceTransforms = $state<TransformConfig[]>([]);
	let editDataSinks = $state<DataSinkDetails[]>([]);

	// Output node edit state
	let editOutputGenerator = $state('');
	let editOutputGeneratorCode = $state('');
	let editOutputMappings = $state<Array<{ key: string; from: string; value: string; transform: string }>>([]);

	// Fetched code state (actual code from files, not stub)
	let fetchedGeneratorCode = $state('');
	let fetchedGeneratorLoading = $state(false);
	let generatorCodeExpanded = $state(false);

	// Transform function code previews (key -> code)
	let transformCodeMap = $state<Record<string, string>>({});
	let transformCodeLoading = $state<Record<string, boolean>>({});
	let transformCodeExpanded = $state<Record<string, boolean>>({});

	// Weighted sampler edit state
	let editSamplerAttributes = $state<Array<{ name: string; values: string }>>([]);

	// Tools edit state (for LLM/Agent nodes)
	let editTools = $state<string[]>([]);
	let editToolChoice = $state<'auto' | 'required' | 'none'>('auto');
	let newToolPath = $state('');
	let showAddToolInput = $state(false);
	let showToolPicker = $state(false);

	// Output keys edit state (for LLM/Agent/Lambda/Branch nodes)
	let editOutputKeys = $state<string[]>([]);
	let newOutputKeyInput = $state('');
	let outputKeyError = $state('');

	// Structured output edit state (for LLM/Agent nodes)
	let editStructuredOutputEnabled = $state(false);
	let editSchemaMode = $state<'inline' | 'class_path'>('inline');
	let editSchemaClassPath = $state('');
	let editSchemaFields = $state<Array<{
		id: string;
		name: string;
		type: 'str' | 'int' | 'float' | 'bool' | 'list' | 'dict';
		description: string;
		default: string;
		hasDefault: boolean;
	}>>([]);
	let editFallbackStrategy = $state<'instruction' | 'post_process'>('instruction');
	let editRetryOnParseError = $state(true);
	let editMaxParseRetries = $state(2);
	let showSchemaPreview = $state(false);

	// Chat history edit state (for LLM/Agent nodes)
	let editChatHistoryEnabled = $state(false);
	let editInjectSystemMessages = $state<Array<{
		id: string;
		turn: number;
		message: string;
	}>>([]);
	let newInjectTurn = $state(1);
	let newInjectMessage = $state('');

	// Multi-LLM edit state
	let editMultiLLMModels = $state<Array<{
		id: string;
		label: string;
		name: string;
		temperature: number;
		maxTokens?: number;
	}>>([]);
	let editMultiLLMPostProcess = $state('');
	let newModelLabel = $state('');
	let newModelName = $state('');

	// Per-source data preview state (for data nodes)
	interface SourcePreviewData {
		records: Record<string, unknown>[];
		total?: number | string;
		message?: string;
		source_type?: string;
	}
	let sourcePreviewData = $state<Map<number, SourcePreviewData | null>>(new Map());
	let sourcePreviewLoading = $state<Map<number, boolean>>(new Map());

	// Subgraph node_config_map edit state
	let editNodeConfigMap = $state<Record<string, NodeConfigOverride>>({});
	let expandedOverrideNodes = $state<Set<string>>(new Set());
	let overrideSearchQuery = $state('');

	// State variables panel state (for prompt autocomplete)
	let stateVariablesPanelExpanded = $state(true);
	let activePromptIndex = $state<number | null>(null);
	let variableFilter = $state('');
	let copiedVariable = $state<string | null>(null);

	// Code tab editor ref for focus management
	let codeEditorRef: { focus: () => void } | null = $state(null);

	// Filtered variables based on search
	let filteredStateVariables = $derived(() => {
		const vars = availableStateVariables();
		if (!variableFilter.trim()) return vars;
		const query = variableFilter.toLowerCase();
		const filterVars = (arr: StateVariable[]) =>
			arr.filter(v => v.name.toLowerCase().includes(query) || v.description?.toLowerCase().includes(query));
		return {
			variables: filterVars(vars.variables),
			bySource: {
				data: filterVars(vars.bySource.data),
				output: filterVars(vars.bySource.output),
				sampler: filterVars(vars.bySource.sampler),
				framework: filterVars(vars.bySource.framework)
			}
		};
	});

	// Copy variable to clipboard with feedback
	function copyVariable(variable: StateVariable) {
		const text = `{${variable.name}}`;
		navigator.clipboard.writeText(text);
		copiedVariable = variable.name;
		setTimeout(() => {
			if (copiedVariable === variable.name) {
				copiedVariable = null;
			}
		}, 1500);
	}

	// Fetch data columns when workflow is available (only on workflow change, not node save)
	$effect(() => {
		const workflow = workflowStore.currentWorkflow;
		if (workflow && workflow.data_config && workflow.id !== lastFetchedWorkflowId) {
			lastFetchedWorkflowId = workflow.id;
			// Fetch columns in the background
			workflowStore.fetchDataColumns();
		}
	});

	// Collect available state variables for this node (using fetched columns)
	let availableStateVariables = $derived(() => {
		if (!node) return { variables: [], bySource: { data: [], output: [], sampler: [], framework: [] } };
		const workflow = workflowStore.currentWorkflow;
		const fetchedColumns = workflowStore.dataColumns;
		return collectStateVariablesForNode(workflow, node.id, fetchedColumns);
	});

	// Validate prompt variables - checks if referenced variables exist
	let promptValidation = $derived(() => {
		const prompts = isEditing ? editPrompts : (node?.prompt ?? []);
		const availableVars = availableStateVariables();
		return validateNodePrompts(prompts, availableVars.variables);
	});

	// Source type options for CustomSelect
	const sourceTypeOptions = [
		{ value: 'hf', label: 'HuggingFace', icon: Cloud },
		{ value: 'disk', label: 'Local File', icon: HardDrive },
		{ value: 'servicenow', label: 'ServiceNow', icon: Globe }
	];

	const sinkTypeOptions = [
		{ value: 'disk', label: 'Local File', icon: HardDrive },
		{ value: 'hf', label: 'HuggingFace', icon: Cloud },
		{ value: 'servicenow', label: 'ServiceNow', icon: Globe }
	];

	// Schema field type options for CustomSelect
	const schemaFieldTypeOptions = [
		{ value: 'str', label: 'String', subtitle: 'Text values' },
		{ value: 'int', label: 'Integer', subtitle: 'Whole numbers' },
		{ value: 'float', label: 'Float', subtitle: 'Decimal numbers' },
		{ value: 'bool', label: 'Boolean', subtitle: 'True/False' },
		{ value: 'list', label: 'List', subtitle: 'Array of values' },
		{ value: 'dict', label: 'Dict', subtitle: 'Key-value object' }
	];

	// Fallback strategy options for CustomSelect
	const fallbackStrategyOptions = [
		{ value: 'instruction', label: 'Instruction', subtitle: 'Add schema to prompt' },
		{ value: 'post_process', label: 'Post-process', subtitle: 'Validate after generation' }
	];

	// Fetch sample data from API for a specific source
	async function fetchSourcePreview(sourceIndex: number) {
		const workflowId = workflowStore.currentWorkflow?.id;
		if (!workflowId) return;

		// Check if already loading this source
		if (sourcePreviewLoading.get(sourceIndex)) return;

		// Set loading state
		const newLoading = new Map(sourcePreviewLoading);
		newLoading.set(sourceIndex, true);
		sourcePreviewLoading = newLoading;

		// Clear previous data
		const newData = new Map(sourcePreviewData);
		newData.set(sourceIndex, null);
		sourcePreviewData = newData;

		try {
			let response: Response;

			// Check if this is a new/unsaved workflow - use direct source preview
			const isNewWorkflow = workflowId.startsWith('new_');

			if (isNewWorkflow) {
				// Get source configuration from current editing state or node data
				const sources = isEditing ? editDataSources :
					(Array.isArray(node?.data_config?.source) ? node.data_config.source :
					node?.data_config?.source ? [node.data_config.source] : []);

				const sourceConfig = sources[sourceIndex];
				if (!sourceConfig) {
					const resultData = new Map(sourcePreviewData);
					resultData.set(sourceIndex, { records: [], total: 0, message: 'Source not found at index ' + sourceIndex });
					sourcePreviewData = resultData;
					return;
				}

				// Use POST endpoint with source config directly
				response = await fetch('/api/preview-source?limit=5', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(sourceConfig)
				});
			} else {
				// Use existing workflow-based endpoint for saved workflows
				response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}/sample-data?limit=5&source_index=${sourceIndex}`);
			}

			const resultData = new Map(sourcePreviewData);
			if (response.ok) {
				resultData.set(sourceIndex, await response.json());
			} else {
				const errorText = await response.text();
				resultData.set(sourceIndex, { records: [], total: 0, message: `Error: ${errorText.substring(0, 100)}` });
			}
			sourcePreviewData = resultData;
		} catch (error) {
			const resultData = new Map(sourcePreviewData);
			resultData.set(sourceIndex, { records: [], total: 0, message: `Network error: ${error instanceof Error ? error.message : String(error)}` });
			sourcePreviewData = resultData;
		} finally {
			const finalLoading = new Map(sourcePreviewLoading);
			finalLoading.set(sourceIndex, false);
			sourcePreviewLoading = finalLoading;
		}
	}

	function refreshSourcePreview(sourceIndex: number) {
		// Clear data and re-fetch
		const newData = new Map(sourcePreviewData);
		newData.delete(sourceIndex);
		sourcePreviewData = newData;
		fetchSourcePreview(sourceIndex);
	}


	// Resizable panel state - use panel store for persistence
	let panelWidth = $state(panelStore.nodeWidth); // 640px default from store
	let isResizing = $state(false);
	let startX = $state(0);
	let startWidth = $state(0);

	function handleResizeMouseDown(e: MouseEvent) {
		isResizing = true;
		startX = e.clientX;
		startWidth = panelWidth;
		document.addEventListener('mousemove', handleResizeMouseMove);
		document.addEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = 'ew-resize';
		document.body.style.userSelect = 'none';
	}

	function handleResizeMouseMove(e: MouseEvent) {
		if (!isResizing) return;
		const diff = startX - e.clientX;
		const newWidth = Math.max(480, Math.min(1000, startWidth + diff));
		panelWidth = newWidth;
	}

	function handleResizeMouseUp() {
		isResizing = false;
		document.removeEventListener('mousemove', handleResizeMouseMove);
		document.removeEventListener('mouseup', handleResizeMouseUp);
		document.body.style.cursor = '';
		document.body.style.userSelect = '';
		// Persist width to store
		panelStore.setNodeWidth(panelWidth);
	}

	// Available models from API
	let availableModels = $derived(workflowStore.availableModels);

	// Model options for CustomSelect
	let modelOptions = $derived(
		availableModels.map(model => ({
			value: model.name,
			label: model.name,
			subtitle: model.model_type
		}))
	);

	// Prompt role options
	const roleOptions = [
		{ value: 'system', label: 'System' },
		{ value: 'user', label: 'User' },
		{ value: 'assistant', label: 'Assistant' }
	];

	// Tool choice options
	const toolChoiceOptions = [
		{ value: 'auto', label: 'Auto', subtitle: 'LLM decides when to use tools' },
		{ value: 'required', label: 'Required', subtitle: 'Must call a tool' },
		{ value: 'none', label: 'None', subtitle: 'Disable tool calling' }
	];

	const icons: Record<string, any> = {
		data: Database,
		start: Play,
		end: Square,
		output: Download,
		llm: Bot,
		agent: Bot,
		lambda: Zap,
		connector: Link,
		subgraph: Boxes,
		web_agent: Globe,
		branch: GitBranch,
		multi_llm: GitCompareArrows
	};

	const colors: Record<string, string> = {
		data: '#0ea5e9',
		start: '#22c55e',
		end: '#ef4444',
		output: '#10b981',
		llm: '#8b5cf6',
		agent: '#ec4899',
		lambda: '#f97316',
		connector: '#06b6d4',
		subgraph: '#3b82f6',
		web_agent: '#ec4899',
		branch: '#eab308',
		multi_llm: '#06b6d4'
	};

	let Icon = $derived(icons[node?.node_type ?? 'llm'] ?? Bot);
	let color = $derived(colors[node?.node_type ?? 'llm'] ?? '#8b5cf6');

	// Determine which tabs to show based on node type
	let showPromptTab = $derived(node?.node_type === 'llm' || node?.node_type === 'agent' || node?.node_type === 'multi_llm');
	let showToolsTab = $derived(node?.node_type === 'llm' || node?.node_type === 'agent');
	let showModelsTab = $derived(node?.node_type === 'multi_llm');
	// Show code tab for nodes that have code: lambda, branch, data (transforms), output (generator), or execution nodes with processors
	let showCodeTab = $derived(
		node?.node_type === 'lambda' ||
		node?.node_type === 'branch' ||
		node?.node_type === 'data' ||
		node?.node_type === 'output' ||
		node?.pre_process ||
		node?.post_process ||
		(isEditing && node?.node_type !== 'start' && node?.node_type !== 'end')
	);
	// Show overrides tab for subgraph nodes with inner_graph
	let showOverridesTab = $derived(node?.node_type === 'subgraph' && (node?.inner_graph?.nodes?.length ?? 0) > 0);
	// Inner graph nodes for override editing
	let innerGraphNodes = $derived(node?.inner_graph?.nodes ?? []);
	// Count of current overrides
	let overrideCount = $derived(Object.keys(editNodeConfigMap).length);
	// Filtered inner nodes based on search
	let filteredInnerNodes = $derived(() => {
		if (!overrideSearchQuery.trim()) return innerGraphNodes;
		const query = overrideSearchQuery.toLowerCase();
		return innerGraphNodes.filter(n =>
			n.id.toLowerCase().includes(query) ||
			(n.summary ?? '').toLowerCase().includes(query) ||
			n.node_type.toLowerCase().includes(query)
		);
	});

	// Tabs configuration for PanelTabs component
	let tabsConfig = $derived([
		{ id: 'details', label: 'Overview', icon: Info, hidden: false },
		{ id: 'prompt', label: 'Prompt', icon: MessageSquare, badge: editPrompts.length || undefined, hidden: !showPromptTab },
		{ id: 'models', label: 'Models', icon: GitCompareArrows, badge: editMultiLLMModels.length || undefined, hidden: !showModelsTab },
		{ id: 'tools', label: 'Tools', icon: Wrench, badge: editTools.length || undefined, hidden: !showToolsTab },
		{ id: 'code', label: 'Code', icon: Code, hidden: !showCodeTab },
		{ id: 'overrides', label: 'Overrides', icon: Layers, badge: overrideCount || undefined, hidden: !showOverridesTab },
		{ id: 'settings', label: 'Settings', icon: Settings, hidden: false }
	]);

	// Track when code tab is activated for auto-focus
	let codeTabJustActivated = $state(false);

	// Handle tab change
	function handleTabChange(tabId: string) {
		activeTab = tabId as TabId;
		if (node?.node_type) {
			panelStore.setLastTab(node.node_type, tabId);
		}
		// Set flag for auto-focus when switching to code tab
		if (tabId === 'code') {
			codeTabJustActivated = true;
			// Reset flag after Monaco has time to load and focus
			setTimeout(() => {
				codeTabJustActivated = false;
			}, 500);
		}
	}

	// Handle connection navigation
	function handleConnectionNavigate(event: CustomEvent<string>) {
		dispatch('navigate', event.detail);
	}

	// Get workflow nodes and edges for ConnectionPreview
	let workflowNodes = $derived(workflowStore.currentWorkflow?.nodes ?? []);
	let workflowEdges = $derived(workflowStore.currentWorkflow?.edges ?? []);

	// Execution nodes that can have pre/post processors (NOT data or output)
	const executionNodeTypes = ['llm', 'lambda', 'web_agent', 'connector', 'subgraph'];
	let canHaveProcessors = $derived(executionNodeTypes.includes(node?.node_type ?? ''));

	// Get current workflow for resolving file paths
	let currentWorkflow = $derived(workflowStore.currentWorkflow);

	// Fetch code content from backend (legacy - uses file path)
	async function fetchCodeContent(filePath: string, workflowId?: string): Promise<string | null> {
		try {
			const params = new URLSearchParams({ file_path: filePath });
			if (workflowId) {
				params.append('workflow_id', workflowId);
			}
			const response = await fetch(`/api/file-content?${params}`);
			if (response.ok) {
				const data = await response.json();
				return data.content || null;
			}
		} catch (e) {
			console.error('Failed to fetch code content:', e);
		}
		return null;
	}

	// Fetch node code directly from task_executor.py using AST-based detection
	// This is the single source of truth - no metadata copies
	async function fetchNodeCode(workflowId: string, nodeId: string, codeType: string): Promise<string | null> {
		try {
			const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}/node/${encodeURIComponent(nodeId)}/code/${encodeURIComponent(codeType)}`);
			if (response.ok) {
				const text = await response.text();
				if (!text) {
					console.log(`Empty response for ${codeType} code for node ${nodeId}`);
					return null;
				}
				try {
					const data = JSON.parse(text);
					if (data && data.found && data.code) {
						return data.code;
					}
				} catch (parseError) {
					console.error(`Failed to parse JSON for ${codeType} code for node ${nodeId}:`, text.substring(0, 100));
				}
			} else {
				console.log(`Non-OK response (${response.status}) for ${codeType} code for node ${nodeId}`);
			}
		} catch (e) {
			console.error(`Failed to fetch ${codeType} code for node ${nodeId}:`, e);
		}
		return null;
	}

	// Track code load errors for debugging
	let codeLoadError = $state<string | null>(null);

	// Load existing code from files
	async function loadExistingCode() {
		if (!node || !currentWorkflow) return;

		// Capture node info at start to handle race conditions
		const nodeId = node.id;
		const nodeType = node.node_type;
		const workflowId = currentWorkflow.id;

		isLoadingCode = true;
		codeLoadError = null;
		preProcessCodeLoaded = false;
		postProcessCodeLoaded = false;
		lambdaCodeLoaded = false;
		outputGeneratorCodeLoaded = false;
		dataTransformCodeLoaded = false;

		console.log('loadExistingCode: Starting for node', nodeId, {
			workflow_id: workflowId
		});

		try {
			// Fetch code directly from task_executor.py using AST-based detection
			// This is the single source of truth - no metadata copies

			// Fetch pre-process code
			const preContent = await fetchNodeCode(workflowId, nodeId, 'pre_process');
			// Check if node changed during await
			if (!node || node.id !== nodeId) return;
			if (preContent) {
				preProcessCode = preContent;
				preProcessCodeLoaded = true;
				console.log('pre_process loaded from task_executor.py');
			}

			// Fetch post-process code
			const postContent = await fetchNodeCode(workflowId, nodeId, 'post_process');
			if (!node || node.id !== nodeId) return;
			if (postContent) {
				postProcessCode = postContent;
				postProcessCodeLoaded = true;
				console.log('post_process loaded from task_executor.py');
			}

			// Fetch lambda function code
			if (nodeType === 'lambda') {
				const lambdaContent = await fetchNodeCode(workflowId, nodeId, 'lambda');
				if (!node || node.id !== nodeId) return;
				if (lambdaContent) {
					lambdaCode = lambdaContent;
					lambdaCodeLoaded = true;
					console.log('lambda loaded from task_executor.py');
				}
			}

			// Fetch branch condition code
			if (nodeType === 'branch') {
				const branchContent = await fetchNodeCode(workflowId, nodeId, 'branch_condition');
				if (!node || node.id !== nodeId) return;
				if (branchContent) {
					branchConditionCode = branchContent;
					console.log('branch_condition loaded from task_executor.py');
				}
			}

			// Fetch output generator code
			if (nodeType === 'output') {
				const outputContent = await fetchNodeCode(workflowId, nodeId, 'output_generator');
				if (!node || node.id !== nodeId) return;
				if (outputContent) {
					editOutputGeneratorCode = outputContent;
					fetchedGeneratorCode = outputContent;  // Also set for preview mode
					outputGeneratorCodeLoaded = true;
					console.log('output_generator loaded from task_executor.py');
				}
			}

			// Fetch data transform code
			if (nodeType === 'data') {
				const transformContent = await fetchNodeCode(workflowId, nodeId, 'data_transform');
				if (!node || node.id !== nodeId) return;
				if (transformContent) {
					editTransformCode = transformContent;
					dataTransformCodeLoaded = true;
					console.log('data_transform loaded from task_executor.py');
				}
			}
		} catch (e) {
			console.error('loadExistingCode error:', e);
			codeLoadError = e instanceof Error ? e.message : 'Unknown error loading code';
		} finally {
			isLoadingCode = false;
			console.log('loadExistingCode: Complete', { preProcessCodeLoaded, postProcessCodeLoaded, lambdaCodeLoaded, outputGeneratorCodeLoaded, dataTransformCodeLoaded });
		}
	}

	// Initialize edit state when node changes
	$effect(() => {
		if (!node) {
			lastInitializedNodeId = '';
			return;
		}

		// Skip re-initialization if we're just saving the same node (not switching nodes)
		if (node.id === lastInitializedNodeId) {
			return;
		}
		lastInitializedNodeId = node.id;

		if (node) {
			editNodeId = node.id ?? '';
			editSummary = node.summary ?? '';
			editDescription = node.description ?? '';
			editModel = node.model?.name ?? '';
			editPrompts = node.prompt ? JSON.parse(JSON.stringify(node.prompt)) : [];
			editPreProcess = node.pre_process ?? '';
			editPostProcess = node.post_process ?? '';
			editFunctionPath = node.function_path ?? '';
			editModelParameters = node.model?.parameters ? JSON.parse(JSON.stringify(node.model.parameters)) : {};
			// Initialize tools state
			editTools = node.tools ? [...node.tools] : [];
			editToolChoice = (node.tool_choice as 'auto' | 'required' | 'none') ?? 'auto';
			newToolPath = '';
			showAddToolInput = false;
			// Initialize output_keys state (normalize to array for editing)
			editOutputKeys = node.output_keys
				? (Array.isArray(node.output_keys) ? [...node.output_keys] : [node.output_keys])
				: [];
			newOutputKeyInput = '';
			outputKeyError = '';
			// Initialize structured output state
			const so = node.model?.structured_output;
			if (so) {
				editStructuredOutputEnabled = so.enabled ?? true;
				editFallbackStrategy = so.fallback_strategy ?? 'instruction';
				editRetryOnParseError = so.retry_on_parse_error ?? true;
				editMaxParseRetries = so.max_parse_retries ?? 2;
				if (typeof so.schema === 'string') {
					editSchemaMode = 'class_path';
					editSchemaClassPath = so.schema;
					editSchemaFields = [];
				} else if (so.schema && typeof so.schema === 'object') {
					editSchemaMode = 'inline';
					editSchemaClassPath = '';
					editSchemaFields = Object.entries(so.schema.fields || {}).map(
						([name, field], i) => ({
							id: `field_${i}_${Date.now()}`,
							name,
							type: field.type,
							description: field.description || '',
							default: field.default !== undefined ? String(field.default) : '',
							hasDefault: field.default !== undefined
						})
					);
				}
			} else {
				editStructuredOutputEnabled = false;
				editSchemaMode = 'inline';
				editSchemaClassPath = '';
				editSchemaFields = [];
				editFallbackStrategy = 'instruction';
				editRetryOnParseError = true;
				editMaxParseRetries = 2;
			}
			showSchemaPreview = false;
			// Initialize chat history state
			editChatHistoryEnabled = node.chat_history ?? false;
			if (node.inject_system_messages && Array.isArray(node.inject_system_messages)) {
				editInjectSystemMessages = node.inject_system_messages.map((item, i) => {
					const turn = parseInt(Object.keys(item)[0]);
					const message = Object.values(item)[0] as string;
					return { id: `inject_${i}_${Date.now()}`, turn, message };
				});
			} else {
				editInjectSystemMessages = [];
			}
			newInjectTurn = 1;
			newInjectMessage = '';

			// Initialize multi_llm models state
			if (node.models && typeof node.models === 'object') {
				editMultiLLMModels = Object.entries(node.models).map(([label, config], i) => ({
					id: `model_${i}_${Date.now()}`,
					label,
					name: config.name,
					temperature: config.parameters?.temperature as number ?? 0.7,
					maxTokens: config.parameters?.max_tokens as number | undefined
				}));
			} else {
				editMultiLLMModels = [];
			}
			editMultiLLMPostProcess = node.multi_llm_post_process ?? '';
			newModelLabel = '';
			newModelName = '';

			// Initialize node_config_map for subgraph nodes
			editNodeConfigMap = node.node_config_map ? JSON.parse(JSON.stringify(node.node_config_map)) : {};
			expandedOverrideNodes = new Set();
			overrideSearchQuery = '';
			hasChanges = false;
			// Start in edit mode if prop is set (useful in builder context)
			isEditing = startInEditMode && node.node_type !== 'start' && node.node_type !== 'end';

			// Reset code loaded flags
			preProcessCodeLoaded = false;
			postProcessCodeLoaded = false;
			lambdaCodeLoaded = false;
			outputGeneratorCodeLoaded = false;
			dataTransformCodeLoaded = false;

			// Clear per-source preview data when switching nodes
			sourcePreviewData = new Map();
			sourcePreviewLoading = new Map();

			// Generate stub code helper (used if loading fails or no file exists)
			const nodeClassName = (node.id || 'Node').replace(/-/g, '_').replace(/\s+/g, '').replace(/[^a-zA-Z0-9_]/g, '');

			const generatePreProcessStub = () => `"""Pre-processor for ${node.summary || node.id}."""
from sygra.core.graph.functions.node_processor import NodePreProcessor
from sygra.core.graph.sygra_state import SygraState


class ${nodeClassName}PreProcessor(NodePreProcessor):
    """Pre-process state before node execution."""

    def apply(self, state: SygraState) -> SygraState:
        """Modify state before node execution.

        Args:
            state: The state object containing workflow variables

        Returns:
            SygraState: The modified state object
        """
        # Example: Transform or prepare data before node execution
        # state["variable_name"] = new_value

        return state
`;

			const generatePostProcessStub = () => `"""Post-processor for ${node.summary || node.id}."""
from sygra.core.graph.functions.node_processor import NodePostProcessor
from sygra.core.graph.sygra_message import SygraMessage
from sygra.core.graph.sygra_state import SygraState


class ${nodeClassName}PostProcessor(NodePostProcessor):
    """Post-process the response after node execution."""

    def apply(self, resp: SygraMessage) -> SygraState:
        """Process the node response and return state updates.

        Args:
            resp: Response from the node (wrapped in SygraMessage)

        Returns:
            SygraState: Dictionary of state updates to apply
        """
        return {"response": resp.message.content}
`;

			const generateLambdaStub = () => `"""Lambda function for ${node.summary || node.id}."""
from sygra.core.graph.functions.lambda_function import LambdaFunction
from sygra.core.graph.sygra_state import SygraState


class ${nodeClassName}Lambda(LambdaFunction):
    """Execute custom logic on workflow state."""

    @staticmethod
    def apply(lambda_node_dict: dict, state: SygraState) -> SygraState:
        """Implement this method to apply lambda function.

        Args:
            lambda_node_dict: configuration dictionary
            state: current state of the graph

        Returns:
            SygraState: the updated state object
        """
        return state
`;

			const generateBranchStub = () => `"""Branch condition for ${node.summary || node.id}."""
from sygra.core.graph.functions.edge_condition import EdgeCondition
from sygra.core.graph.sygra_state import SygraState
from sygra.utils import constants


class ${nodeClassName}Condition(EdgeCondition):
    """Determine which branch to take based on state."""

    @staticmethod
    def apply(state: SygraState) -> str:
        """Evaluate condition and return the target branch key.

        Args:
            state: Current workflow state

        Returns:
            str: Branch key matching one of the configured edge targets
        """
        # Return branch key or constants.SYGRA_END to end workflow
        return "default"
`;

			// Generate stub functions for output generator and data transform
			const generateOutputGeneratorStub = () => {
				const outputClassName = (node.id || 'Output').replace(/-/g, '_').replace(/\s+/g, '').replace(/[^a-zA-Z0-9_]/g, '');
				return `"""Output generator for ${node.summary || node.id}."""
from typing import Any

from sygra.core.graph.sygra_state import SygraState
from sygra.processors.output_record_generator import BaseOutputGenerator


class ${outputClassName}Generator(BaseOutputGenerator):
    """Generate output records from workflow state.

    This class transforms the workflow state into the final output format.
    Override _build_record for custom logic, or add transform methods
    that can be referenced in the output_map configuration.
    """

    def _build_record(self, state: SygraState) -> dict[str, Any]:
        """Build the output record from state.

        Args:
            state: The workflow state containing all variables

        Returns:
            dict: The final output record
        """
        # Default: use parent's output_map-based logic
        # Override this method for fully custom record building
        return super()._build_record(state)

    # Example transform method (referenced in output_map via "transform" key)
    # def format_response(self, data: Any, state: SygraState) -> Any:
    #     """Transform data before including in output."""
    #     return str(data)
`;
			};

			const generateDataTransformStub = () => {
				const dataClassName = (node.id || 'Data').replace(/-/g, '_').replace(/\s+/g, '').replace(/[^a-zA-Z0-9_]/g, '');
				return `"""Data transformation for ${node.summary || node.id}."""
from typing import Any

from sygra.processors.data_transform import DataTransform


class ${dataClassName}Transform(DataTransform):
    """Transform data records during processing.

    This class processes a list of records from the data source.
    Implement the name property and transform method.
    """

    @property
    def name(self) -> str:
        """Get the unique identifier for this transformation."""
        return "${dataClassName}Transform"

    def transform(self, data: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
        """Apply transformation to a list of records.

        Args:
            data: List of dictionary records to transform
            params: Parameters controlling the transformation

        Returns:
            list[dict[str, Any]]: Transformed list of records
        """
        # Example transformations:
        #
        # Add new fields to each record:
        # for record in data:
        #     record["new_field"] = compute_value(record["existing_field"])
        #
        # Filter records:
        # data = [r for r in data if r.get("field") == "value"]
        #
        # Skip records by range:
        # skip_count = params.get("skip", 0)
        # data = data[skip_count:]

        return data
`;
			};

			// Load code from task_executor.py (single source of truth)
			// Always fetch from API - no metadata copies
			loadExistingCode().then(() => {
				// After loading, set stubs only for code that wasn't loaded
				if (!preProcessCodeLoaded) {
					preProcessCode = generatePreProcessStub();
				}
				if (!postProcessCodeLoaded) {
					postProcessCode = generatePostProcessStub();
				}
				if (!lambdaCodeLoaded && node.node_type === 'lambda') {
					lambdaCode = generateLambdaStub();
				}
				if (node.node_type === 'branch' && !branchConditionCode) {
					branchConditionCode = generateBranchStub();
				}
				if (!outputGeneratorCodeLoaded && node.node_type === 'output') {
					editOutputGeneratorCode = generateOutputGeneratorStub();
				}
				if (!dataTransformCodeLoaded && node.node_type === 'data') {
					editTransformCode = generateDataTransformStub();
				}
			});

			// Initialize data node edit state (config only, transform code loaded above)
			if (node.node_type === 'data') {
				if (node.data_config) {
					// Initialize multi-source array
					const sources = Array.isArray(node.data_config.source)
						? node.data_config.source
						: node.data_config.source
							? [node.data_config.source]
							: [];

					// Deep clone sources for editing, excluding transformations (managed separately)
					editDataSources = sources.map(s => {
						const { transformations, ...sourceWithoutTransforms } = s;
						return { ...sourceWithoutTransforms };
					});

					// Initialize id_column
					editIdColumn = node.data_config.id_column;

					// Initialize transforms from first source or separate config
					if (sources.length > 0 && sources[0].transformations) {
						editSourceTransforms = sources[0].transformations.map((t: any) => ({
							id: t.id || `transform_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
							transform: t.transform,
							params: t.params || {},
							enabled: t.enabled !== false
						}));
					} else {
						editSourceTransforms = [];
					}

					// Also initialize legacy single-source fields for backwards compatibility
					const src = sources[0];
					if (src) {
						editDataSourceType = (src.type as 'hf' | 'disk' | 'servicenow') || 'hf';
						editDataRepoId = src.repo_id ?? '';
						editDataConfigName = src.config_name ?? '';
						editDataSplit = Array.isArray(src.split) ? src.split.join(', ') : (src.split ?? 'train');
						editDataFilePath = src.file_path ?? '';
						editDataTable = src.table ?? '';
						editDataFields = src.fields?.join(', ') ?? '';
						editDataLimit = src.limit;
						editDataFilters = src.filters ? JSON.stringify(src.filters) : '';
					}
					// Initialize sinks for new DataConfigSection
					const sinkArray = Array.isArray(node.data_config.sink) ? node.data_config.sink : node.data_config.sink ? [node.data_config.sink] : [];
					editDataSinks = sinkArray.map((s: any) => ({
						type: s.type || (s.repo_id ? 'hf' : s.table ? 'servicenow' : 'disk'),
						alias: s.alias,
						file_path: s.file_path,
						repo_id: s.repo_id,
						split: s.split,
						table: s.table,
						operation: s.operation
					}));

					// Also initialize legacy single-sink fields for backwards compatibility
					const sink = sinkArray[0];
					if (sink) {
						editSinkAlias = sink.alias ?? '';
						if (sink.type === 'hf' || sink.repo_id) {
							editSinkType = 'hf';
							editSinkRepoId = sink.repo_id ?? '';
							editSinkSplit = sink.split ?? 'train';
						} else if (sink.type === 'servicenow' || sink.table) {
							editSinkType = 'servicenow';
							editSinkTable = sink.table ?? '';
							editSinkOperation = (sink.operation as 'insert' | 'update') || 'insert';
						} else {
							editSinkType = 'disk';
							editSinkFilePath = sink.file_path ?? '';
						}
					}
				} else {
					// Reset multi-source state when no config
					editDataSources = [];
					editIdColumn = undefined;
					editSourceTransforms = [];
					editDataSinks = [];
				}
			}

			// Initialize output node edit state (config only, code loaded via loadExistingCode)
			if (node.node_type === 'output') {
				// Reset state - code will be loaded by loadExistingCode()
				editOutputGeneratorCode = '';
				editOutputGenerator = '';
				editOutputMappings = [];

				// Reset fetched code state
				fetchedGeneratorCode = '';
				generatorCodeExpanded = false;
				transformCodeMap = {};
				transformCodeExpanded = {};

				// Load existing config if present (not code - that comes from task_executor.py)
				if (node.output_config) {
					editOutputGenerator = node.output_config.generator ?? '';
					const outputMap = node.output_config.output_map ?? {};
					editOutputMappings = Object.entries(outputMap).map(([key, val]: [string, any]) => ({
						key,
						from: val.from ?? '',
						value: val.value !== undefined ? JSON.stringify(val.value) : '',
						transform: val.transform ?? ''
					}));
				}
			}

			// Initialize weighted sampler edit state
			if (node.node_type === 'weighted_sampler') {
				if (node.sampler_config?.attributes) {
					editSamplerAttributes = Object.entries(node.sampler_config.attributes).map(([name, attr]: [string, any]) => ({
						name,
						values: Array.isArray(attr.values) ? attr.values.join(', ') : ''
					}));
				} else {
					editSamplerAttributes = [];
				}
			}
		}
	});

	// Load available models on mount
	onMount(() => {
		workflowStore.loadAvailableModels();
	});

	function startEditing() {
		isEditing = true;
	}

	function cancelEditing() {
		// Reset to original values
		if (node) {
			editNodeId = node.id ?? '';
			editSummary = node.summary ?? '';
			editDescription = node.description ?? '';
			editModel = node.model?.name ?? '';
			editPrompts = node.prompt ? JSON.parse(JSON.stringify(node.prompt)) : [];
			editPreProcess = node.pre_process ?? '';
			editPostProcess = node.post_process ?? '';
			editFunctionPath = node.function_path ?? '';
			editModelParameters = node.model?.parameters ? JSON.parse(JSON.stringify(node.model.parameters)) : {};
			// Reset tools state
			editTools = node.tools ? [...node.tools] : [];
			editToolChoice = (node.tool_choice as 'auto' | 'required' | 'none') ?? 'auto';
			newToolPath = '';
			showAddToolInput = false;
			// Reset output_keys state
			editOutputKeys = node.output_keys
				? (Array.isArray(node.output_keys) ? [...node.output_keys] : [node.output_keys])
				: [];
			newOutputKeyInput = '';
			outputKeyError = '';
			// Reset structured output state
			const so = node.model?.structured_output;
			if (so) {
				editStructuredOutputEnabled = so.enabled ?? true;
				editFallbackStrategy = so.fallback_strategy ?? 'instruction';
				editRetryOnParseError = so.retry_on_parse_error ?? true;
				editMaxParseRetries = so.max_parse_retries ?? 2;
				if (typeof so.schema === 'string') {
					editSchemaMode = 'class_path';
					editSchemaClassPath = so.schema;
					editSchemaFields = [];
				} else if (so.schema && typeof so.schema === 'object') {
					editSchemaMode = 'inline';
					editSchemaClassPath = '';
					editSchemaFields = Object.entries(so.schema.fields || {}).map(
						([name, field], i) => ({
							id: `field_${i}_${Date.now()}`,
							name,
							type: field.type,
							description: field.description || '',
							default: field.default !== undefined ? String(field.default) : '',
							hasDefault: field.default !== undefined
						})
					);
				}
			} else {
				editStructuredOutputEnabled = false;
				editSchemaMode = 'inline';
				editSchemaClassPath = '';
				editSchemaFields = [];
				editFallbackStrategy = 'instruction';
				editRetryOnParseError = true;
				editMaxParseRetries = 2;
			}
			showSchemaPreview = false;
			// Reset chat history state
			editChatHistoryEnabled = node.chat_history ?? false;
			if (node.inject_system_messages && Array.isArray(node.inject_system_messages)) {
				editInjectSystemMessages = node.inject_system_messages.map((item, i) => {
					const turn = parseInt(Object.keys(item)[0]);
					const message = Object.values(item)[0] as string;
					return { id: `inject_${i}_${Date.now()}`, turn, message };
				});
			} else {
				editInjectSystemMessages = [];
			}
			newInjectTurn = 1;
			newInjectMessage = '';
			// Reset multi_llm models state
			if (node.models && typeof node.models === 'object') {
				editMultiLLMModels = Object.entries(node.models).map(([label, config], i) => ({
					id: `model_${i}_${Date.now()}`,
					label,
					name: config.name,
					temperature: config.parameters?.temperature as number ?? 0.7,
					maxTokens: config.parameters?.max_tokens as number | undefined
				}));
			} else {
				editMultiLLMModels = [];
			}
			editMultiLLMPostProcess = node.multi_llm_post_process ?? '';
			newModelLabel = '';
			newModelName = '';
			// Reset node_config_map for subgraph nodes
			editNodeConfigMap = node.node_config_map ? JSON.parse(JSON.stringify(node.node_config_map)) : {};
			expandedOverrideNodes = new Set();
			overrideSearchQuery = '';
			// Reset output node state (code will be loaded by loadExistingCode below)
			if (node.node_type === 'output') {
				editOutputGenerator = node.output_config?.generator ?? '';
				editOutputGeneratorCode = ''; // Will be loaded from task_executor.py
				const outputMap = node.output_config?.output_map ?? {};
				editOutputMappings = Object.entries(outputMap).map(([key, val]: [string, any]) => ({
					key,
					from: val.from ?? '',
					value: val.value !== undefined ? JSON.stringify(val.value) : '',
					transform: val.transform ?? ''
				}));
			}
			// Reset data node state (code will be loaded by loadExistingCode below)
			if (node.node_type === 'data') {
				const source = node.data_config?.source;
				const firstSource = Array.isArray(source) ? source[0] : source;
				editDataSourceType = (firstSource?.type as 'hf' | 'disk' | 'servicenow') || 'hf';
				editDataRepoId = firstSource?.repo_id ?? '';
				editDataConfigName = firstSource?.config_name ?? '';
				editDataSplit = Array.isArray(firstSource?.split) ? firstSource.split.join(', ') : (firstSource?.split ?? 'train');
				editDataFilePath = firstSource?.file_path ?? '';
				editDataTable = firstSource?.table ?? '';
				editDataFilters = firstSource?.query ?? '';
				editTransformCode = ''; // Will be loaded from task_executor.py
			}
			// Reset all code fields by reloading from task_executor.py
			// This is the single source of truth - stubs will be generated if no code exists
			loadExistingCode();
		}
		hasChanges = false;
		isEditing = false;
	}

	async function saveChanges() {
		if (!node) return;

		isSaving = true;

		// Capture the original node ID before any async operations
		// because the node prop may become undefined after store updates
		const originalNodeId = node.id;

		const updates: Partial<WorkflowNode> & { newId?: string } = {};

		// Check if node ID changed
		if (editNodeId !== originalNodeId && editNodeId.trim()) {
			updates.newId = editNodeId.trim();
		}

		if (editSummary !== (node.summary ?? '')) {
			updates.summary = editSummary;
		}
		if (editDescription !== (node.description ?? '')) {
			updates.description = editDescription;
		}
		// Build structured output config if enabled (for LLM/Agent nodes)
		let structuredOutputConfig: import('$lib/stores/workflow.svelte').StructuredOutputConfig | undefined;
		console.log('[saveChanges] Structured output debug:', {
			node_type: node.node_type,
			editStructuredOutputEnabled,
			editSchemaMode,
			editSchemaFields,
			editSchemaClassPath
		});
		if ((node.node_type === 'llm' || node.node_type === 'agent') && editStructuredOutputEnabled) {
			if (editSchemaMode === 'class_path' && editSchemaClassPath.trim()) {
				structuredOutputConfig = {
					enabled: true,
					schema: editSchemaClassPath.trim(),
					fallback_strategy: editFallbackStrategy,
					retry_on_parse_error: editRetryOnParseError,
					max_parse_retries: editMaxParseRetries
				};
			} else if (editSchemaMode === 'inline') {
				const fields: Record<string, import('$lib/stores/workflow.svelte').SchemaFieldDefinition> = {};
				for (const f of editSchemaFields) {
					if (!f.name.trim()) continue;
					fields[f.name.trim()] = {
						type: f.type,
						...(f.description && { description: f.description }),
						...(f.hasDefault && { default: parseFieldDefault(f.default, f.type) })
					};
				}
				console.log('[saveChanges] Built fields:', fields);
				if (Object.keys(fields).length > 0) {
					structuredOutputConfig = {
						enabled: true,
						schema: { fields },
						fallback_strategy: editFallbackStrategy,
						retry_on_parse_error: editRetryOnParseError,
						max_parse_retries: editMaxParseRetries
					};
				}
			}
		}
		console.log('[saveChanges] structuredOutputConfig:', structuredOutputConfig);

		// Check if model config changed (including structured output)
		const modelChanged = editModel !== (node.model?.name ?? '') ||
			JSON.stringify(editModelParameters) !== JSON.stringify(node.model?.parameters ?? {}) ||
			JSON.stringify(structuredOutputConfig) !== JSON.stringify(node.model?.structured_output);
		console.log('[saveChanges] modelChanged:', modelChanged);

		if (modelChanged) {
			updates.model = {
				name: editModel,
				parameters: editModelParameters,
				...(structuredOutputConfig && { structured_output: structuredOutputConfig })
			};
			console.log('[saveChanges] updates.model:', updates.model);
		}
		if (JSON.stringify(editPrompts) !== JSON.stringify(node.prompt ?? [])) {
			updates.prompt = editPrompts;
		}
		if (editPreProcess !== (node.pre_process ?? '')) {
			updates.pre_process = editPreProcess;
		}
		if (editPostProcess !== (node.post_process ?? '')) {
			updates.post_process = editPostProcess;
		}
		if (editFunctionPath !== (node.function_path ?? '')) {
			updates.function_path = editFunctionPath;
		}

		// Handle tools updates for LLM/Agent nodes
		if (node.node_type === 'llm' || node.node_type === 'agent') {
			if (JSON.stringify(editTools) !== JSON.stringify(node.tools ?? [])) {
				updates.tools = editTools.length > 0 ? editTools : undefined;
			}
			if (editToolChoice !== (node.tool_choice ?? 'auto')) {
				updates.tool_choice = editToolChoice;
			}

			// Handle chat history updates
			if (editChatHistoryEnabled !== (node.chat_history ?? false)) {
				updates.chat_history = editChatHistoryEnabled || undefined;
			}

			// Convert inject_system_messages to backend format: [{3: "msg"}, {5: "msg"}]
			const newInjectMessages = editInjectSystemMessages.map(m => ({ [m.turn]: m.message }));
			const currentInjectMessages = node.inject_system_messages ?? [];
			if (JSON.stringify(newInjectMessages) !== JSON.stringify(currentInjectMessages)) {
				updates.inject_system_messages = newInjectMessages.length > 0 ? newInjectMessages : undefined;
			}
		}

		// Handle output_keys updates for LLM/Agent/Lambda/Branch/Multi-LLM nodes
		if (['llm', 'agent', 'lambda', 'branch', 'multi_llm'].includes(node.node_type)) {
			// Normalize current value to array for comparison
			const currentKeys = node.output_keys
				? (Array.isArray(node.output_keys) ? node.output_keys : [node.output_keys])
				: [];

			if (JSON.stringify(editOutputKeys) !== JSON.stringify(currentKeys)) {
				// Convert to appropriate format for saving
				if (editOutputKeys.length === 0) {
					updates.output_keys = undefined; // Use default
				} else if (editOutputKeys.length === 1) {
					updates.output_keys = editOutputKeys[0]; // Single string
				} else {
					updates.output_keys = editOutputKeys; // Array
				}
			}
		}

		// Handle multi_llm models updates
		if (node.node_type === 'multi_llm') {
			// Convert models to backend format: { label: { name, parameters } }
			const newModels: Record<string, { name: string; parameters?: Record<string, unknown> }> = {};
			for (const m of editMultiLLMModels) {
				newModels[m.label] = {
					name: m.name,
					parameters: {
						temperature: m.temperature,
						...(m.maxTokens !== undefined && { max_tokens: m.maxTokens })
					}
				};
			}
			const currentModels = node.models ?? {};
			if (JSON.stringify(newModels) !== JSON.stringify(currentModels)) {
				updates.models = Object.keys(newModels).length > 0 ? newModels : undefined;
			}

			// Handle multi_llm_post_process
			if (editMultiLLMPostProcess !== (node.multi_llm_post_process ?? '')) {
				updates.multi_llm_post_process = editMultiLLMPostProcess || undefined;
			}
		}

		// Handle data node config updates
		if (node.node_type === 'data') {
			const dataConfig: any = {};

			// Use new multi-source array if available, otherwise use legacy single source
			if (editDataSources.length > 0) {
				// Serialize transforms into the sources (strip `id` field as it's for UI only)
				const sourcesWithTransforms = editDataSources.map((src, idx) => {
					const sourceCopy = { ...src };
					// Handle transforms for primary/first source
					if (idx === 0) {
						// Get enabled transforms
						const enabledTransforms = editSourceTransforms
							.filter(t => t.enabled !== false)
							.map(t => ({
								transform: t.transform,
								params: t.params
								// Note: Don't include `id` or `enabled` - those are UI-only fields
							}));

						if (enabledTransforms.length > 0) {
							sourceCopy.transformations = enabledTransforms;
						} else {
							// Explicitly remove transformations when all are deleted/disabled
							delete sourceCopy.transformations;
						}
					}
					return sourceCopy;
				});

				// Use array for multiple sources, single object for one source
				dataConfig.source = sourcesWithTransforms.length > 1
					? sourcesWithTransforms
					: sourcesWithTransforms[0];

				// Include id_column for multi-source
				if (editIdColumn && sourcesWithTransforms.length > 1) {
					dataConfig.id_column = editIdColumn;
				}
			} else {
				// Fallback to legacy single source fields
				const source: Record<string, any> = { type: editDataSourceType };
				if (editDataSourceType === 'hf') {
					source.repo_id = editDataRepoId;
					if (editDataConfigName) source.config_name = editDataConfigName;
					source.split = editDataSplit.includes(',') ? editDataSplit.split(',').map(s => s.trim()) : editDataSplit;
				} else if (editDataSourceType === 'disk') {
					source.file_path = editDataFilePath;
				} else if (editDataSourceType === 'servicenow') {
					source.table = editDataTable;
					if (editDataFields) source.fields = editDataFields.split(',').map(s => s.trim());
					if (editDataLimit) source.limit = editDataLimit;
					if (editDataFilters) {
						try { source.filters = JSON.parse(editDataFilters); } catch {}
					}
				}
				dataConfig.source = source;
			}

			// Include sinks from new DataConfigSection state
			if (editDataSinks.length > 0) {
				dataConfig.sink = editDataSinks.map(s => {
					const sinkConfig: any = {
						type: s.type,
						alias: s.alias || undefined
					};
					if (s.type === 'disk' || s.type === 'json' || s.type === 'jsonl') {
						if (s.file_path) sinkConfig.file_path = s.file_path;
					} else if (s.type === 'hf') {
						if (s.repo_id) sinkConfig.repo_id = s.repo_id;
						if (s.split) sinkConfig.split = s.split;
					} else if (s.type === 'servicenow') {
						if (s.table) sinkConfig.table = s.table;
						if (s.operation) sinkConfig.operation = s.operation;
					}
					return sinkConfig;
				});
			}

			// Include transformation code if present (legacy support)
			if (editTransformCode && editTransformCode.trim()) {
				dataConfig._transform_code = editTransformCode;
			}

			updates.data_config = dataConfig;
		}

		// Handle output node config updates
		if (node.node_type === 'output') {
			const outputConfig: any = {};
			if (editOutputGenerator) {
				outputConfig.generator = editOutputGenerator;
			}
			// Include generator code if it exists (code can be saved even without a generator path)
			if (editOutputGeneratorCode && editOutputGeneratorCode.trim()) {
				outputConfig._generator_code = editOutputGeneratorCode;
			}
			if (editOutputMappings.length > 0) {
				outputConfig.output_map = {};
				editOutputMappings.forEach(m => {
					if (!m.key) return; // Skip mappings without a key
					const mapping: any = {};
					if (m.from) mapping.from = m.from;
					if (m.value) {
						try { mapping.value = JSON.parse(m.value); } catch { mapping.value = m.value; }
					}
					if (m.transform) mapping.transform = m.transform;
					outputConfig.output_map[m.key] = mapping;
				});
				// Remove output_map if it ended up empty (all mappings had no key)
				if (Object.keys(outputConfig.output_map).length === 0) {
					delete outputConfig.output_map;
				}
			}
			// Only set output_config if it has content
			if (Object.keys(outputConfig).length > 0) {
				updates.output_config = outputConfig;
			}
		}

		// Handle weighted sampler config updates
		if (node.node_type === 'weighted_sampler') {
			const samplerConfig: any = { attributes: {} };
			editSamplerAttributes.forEach(attr => {
				if (attr.name) {
					// Parse comma-separated values, auto-detect numbers
					const values = attr.values.split(',').map(v => {
						const trimmed = v.trim();
						const num = Number(trimmed);
						return isNaN(num) ? trimmed : num;
					});
					samplerConfig.attributes[attr.name] = { values };
				}
			});
			updates.sampler_config = samplerConfig;
		}

		// Handle subgraph node_config_map updates
		if (node.node_type === 'subgraph') {
			const originalConfigMap = node.node_config_map ?? {};
			const hasConfigMapChanges = JSON.stringify(editNodeConfigMap) !== JSON.stringify(originalConfigMap);
			if (hasConfigMapChanges) {
				// Only include if there are actual overrides, otherwise set to undefined
				updates.node_config_map = Object.keys(editNodeConfigMap).length > 0 ? editNodeConfigMap : undefined;
			}
		}

		// Save inline code fields for processor/function nodes
		// Code is written to task_executor.py (single source of truth)
		// Backend handles stub detection - stubs won't be saved
		// Send empty string to signal deletion
		if (hasChanges) {
			// Pre-processor code (for LLM/Agent nodes)
			// Send code content or empty string (signals deletion)
			updates._pre_process_code = preProcessCode?.trim() || '';

			// Post-processor code (for LLM/Agent nodes)
			updates._post_process_code = postProcessCode?.trim() || '';

			// Lambda function code
			if (node.node_type === 'lambda') {
				updates._lambda_code = lambdaCode?.trim() || '';
			}

			// Branch condition code
			if (node.node_type === 'branch') {
				updates._branch_condition_code = branchConditionCode?.trim() || '';
			}

			// Output generator code
			if (node.node_type === 'output') {
				updates._output_generator_code = editOutputGeneratorCode?.trim() || '';
			}

			// Data transform code
			if (node.node_type === 'data') {
				updates._data_transform_code = editTransformCode?.trim() || '';
			}
		}

		try {
			console.log('[saveChanges] Final updates object:', JSON.stringify(updates, null, 2));
			if (Object.keys(updates).length > 0) {
				const success = await workflowStore.updateNode(originalNodeId, updates);
				console.log('[saveChanges] updateNode result:', success);
				if (success) {
					hasChanges = false;
					isEditing = false;

					// Update fetchedGeneratorCode so preview mode shows saved content
					// (only output generator uses a separate "fetched" variable; other code types use the same variable for both)
					if (node?.node_type === 'output' && editOutputGeneratorCode) {
						fetchedGeneratorCode = editOutputGeneratorCode;
					}

					dispatch('save', { nodeId: originalNodeId, newId: updates.newId, updates });
				}
			} else {
				console.log('[saveChanges] No updates to save');
				hasChanges = false;
				isEditing = false;
			}
		} catch (error) {
			console.error('[NodeDetailsPanel] Error saving:', error);
		} finally {
			isSaving = false;
		}
	}

	// Output mapping helpers
	function addOutputMapping() {
		editOutputMappings = [...editOutputMappings, { key: '', from: '', value: '', transform: '' }];
		markChanged();
	}

	function removeOutputMapping(index: number) {
		editOutputMappings = editOutputMappings.filter((_, i) => i !== index);
		markChanged();
	}

	function updateOutputMapping(index: number, field: 'key' | 'from' | 'value' | 'transform', value: string) {
		editOutputMappings[index][field] = value;
		editOutputMappings = [...editOutputMappings];
		markChanged();
	}

	// Fetch generator class code from backend
	async function fetchGeneratorCode(generatorPath: string) {
		if (!generatorPath || !currentWorkflow) return;

		fetchedGeneratorLoading = true;
		fetchedGeneratorCode = '';

		try {
			const code = await fetchCodeContent(generatorPath, currentWorkflow.id);
			if (code) {
				fetchedGeneratorCode = code;
			}
		} finally {
			fetchedGeneratorLoading = false;
		}
	}

	// Fetch transform function code for a specific mapping
	async function fetchTransformCode(mappingKey: string, transformName: string) {
		if (!transformName || !currentWorkflow || !node?.output_config?.generator) return;

		// The transform function is a method on the generator class
		// We need to fetch it from the generator file
		const generatorPath = node.output_config.generator;

		transformCodeLoading = { ...transformCodeLoading, [mappingKey]: true };

		try {
			// Construct the path to the transform method
			// Transform methods are typically named like the transform value
			const methodPath = `${generatorPath.split('.').slice(0, -1).join('.')}.${generatorPath.split('.').pop()}.${transformName}`;

			// First try to get the method directly
			const code = await fetchCodeContent(methodPath, currentWorkflow.id);
			if (code) {
				transformCodeMap = { ...transformCodeMap, [mappingKey]: code };
			} else {
				// If that fails, try getting from the generator class file
				const generatorCode = fetchedGeneratorCode || await fetchCodeContent(generatorPath, currentWorkflow.id);
				if (generatorCode) {
					// Extract the specific method from the class
					const methodMatch = generatorCode.match(new RegExp(`(\\s*def\\s+${transformName}\\s*\\([^)]*\\):[\\s\\S]*?)(?=\\n\\s*def\\s|\\n\\s*class\\s|$)`));
					if (methodMatch) {
						transformCodeMap = { ...transformCodeMap, [mappingKey]: methodMatch[1].trim() };
					} else {
						transformCodeMap = { ...transformCodeMap, [mappingKey]: `# Method '${transformName}' not found in generator class` };
					}
				}
			}
		} finally {
			transformCodeLoading = { ...transformCodeLoading, [mappingKey]: false };
		}
	}

	// Toggle transform code preview visibility
	function toggleTransformCode(mappingKey: string, transformName: string) {
		const isCurrentlyExpanded = transformCodeExpanded[mappingKey];
		transformCodeExpanded = { ...transformCodeExpanded, [mappingKey]: !isCurrentlyExpanded };

		// Fetch code if expanding and not already loaded
		if (!isCurrentlyExpanded && !transformCodeMap[mappingKey]) {
			fetchTransformCode(mappingKey, transformName);
		}
	}

	// Sampler attribute helpers
	function addSamplerAttribute() {
		editSamplerAttributes = [...editSamplerAttributes, { name: '', values: '' }];
		markChanged();
	}

	function removeSamplerAttribute(index: number) {
		editSamplerAttributes = editSamplerAttributes.filter((_, i) => i !== index);
		markChanged();
	}

	function updateSamplerAttribute(index: number, field: 'name' | 'values', value: string) {
		editSamplerAttributes[index][field] = value;
		editSamplerAttributes = [...editSamplerAttributes];
		markChanged();
	}

	function markChanged() {
		hasChanges = true;
	}

	// Multi-source manager handlers
	function handleSourcesUpdate(e: CustomEvent<{ sources: DataSourceDetails[]; idColumn?: string }>) {
		editDataSources = e.detail.sources;
		editIdColumn = e.detail.idColumn;
		markChanged();
	}

	// Transform pipeline handlers
	function handleTransformsUpdate(e: CustomEvent<{ transforms: TransformConfig[] }>) {
		editSourceTransforms = e.detail.transforms;
		markChanged();
	}

	// Sinks handler
	function handleSinksUpdate(e: CustomEvent<{ sinks: DataSinkDetails[] }>) {
		editDataSinks = e.detail.sinks;
		markChanged();
	}

	// Source preview handlers for DataConfigSection
	function handleSourcePreviewFetch(e: CustomEvent<{ index: number }>) {
		fetchSourcePreview(e.detail.index);
	}

	function handleSourcePreviewRefresh(e: CustomEvent<{ index: number }>) {
		refreshSourcePreview(e.detail.index);
	}

	// Output keys helpers
	function addOutputKey() {
		const key = newOutputKeyInput.trim();
		if (!key) return;

		// Validate identifier pattern (must be valid Python/JS identifier)
		if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key)) {
			outputKeyError = 'Must be a valid identifier (letters, numbers, underscores, cannot start with number)';
			return;
		}

		// Check for duplicates
		if (editOutputKeys.includes(key)) {
			outputKeyError = 'Key already exists';
			return;
		}

		editOutputKeys = [...editOutputKeys, key];
		newOutputKeyInput = '';
		outputKeyError = '';
		markChanged();
	}

	function removeOutputKey(key: string) {
		editOutputKeys = editOutputKeys.filter(k => k !== key);
		markChanged();
	}

	// Structured output schema helpers
	function addSchemaField() {
		editSchemaFields = [...editSchemaFields, {
			id: `field_${Date.now()}`,
			name: '',
			type: 'str',
			description: '',
			default: '',
			hasDefault: false
		}];
		markChanged();
	}

	function removeSchemaField(id: string) {
		editSchemaFields = editSchemaFields.filter(f => f.id !== id);
		markChanged();
	}

	function updateSchemaField(id: string, field: string, value: any) {
		editSchemaFields = editSchemaFields.map(f =>
			f.id === id ? { ...f, [field]: value } : f
		);
		markChanged();
	}

	function parseFieldDefault(value: string, type: string): unknown {
		switch (type) {
			case 'int': return parseInt(value, 10) || 0;
			case 'float': return parseFloat(value) || 0.0;
			case 'bool': return value.toLowerCase() === 'true';
			case 'list':
			case 'dict':
				try { return JSON.parse(value); } catch { return type === 'list' ? [] : {}; }
			default: return value;
		}
	}

	function generateSchemaPreview(): string {
		if (editSchemaMode === 'class_path') {
			return JSON.stringify({ class_path: editSchemaClassPath }, null, 2);
		}
		const properties: Record<string, any> = {};
		const required: string[] = [];
		for (const f of editSchemaFields) {
			if (!f.name.trim()) continue;
			const typeMap: Record<string, string> = {
				str: 'string', int: 'integer', float: 'number',
				bool: 'boolean', list: 'array', dict: 'object'
			};
			properties[f.name] = {
				type: typeMap[f.type] || 'string',
				...(f.description && { description: f.description }),
				...(f.hasDefault && { default: parseFieldDefault(f.default, f.type) })
			};
			if (!f.hasDefault) required.push(f.name);
		}
		return JSON.stringify({ type: 'object', properties, required }, null, 2);
	}

	// Chat history / system message injection helpers
	function addSystemMessageInjection() {
		if (!newInjectTurn || newInjectTurn < 1 || !newInjectMessage.trim()) return;
		// Check for duplicate turn numbers
		if (editInjectSystemMessages.some(m => m.turn === newInjectTurn)) {
			return;
		}
		editInjectSystemMessages = [
			...editInjectSystemMessages,
			{ id: `inject_${Date.now()}`, turn: newInjectTurn, message: newInjectMessage.trim() }
		].sort((a, b) => a.turn - b.turn);
		// Auto-increment turn for next entry
		newInjectTurn = Math.max(...editInjectSystemMessages.map(m => m.turn), 0) + 2;
		newInjectMessage = '';
		markChanged();
	}

	function removeSystemMessageInjection(id: string) {
		editInjectSystemMessages = editInjectSystemMessages.filter(m => m.id !== id);
		markChanged();
	}

	function updateSystemMessageInjection(id: string, field: 'turn' | 'message', value: number | string) {
		editInjectSystemMessages = editInjectSystemMessages.map(m =>
			m.id === id ? { ...m, [field]: value } : m
		).sort((a, b) => a.turn - b.turn);
		markChanged();
	}

	// Multi-LLM model helpers
	function addMultiLLMModel() {
		if (!newModelLabel.trim() || !newModelName.trim()) return;
		// Check for duplicate labels
		if (editMultiLLMModels.some(m => m.label === newModelLabel.trim())) {
			return;
		}
		editMultiLLMModels = [
			...editMultiLLMModels,
			{
				id: `model_${Date.now()}`,
				label: newModelLabel.trim(),
				name: newModelName.trim(),
				temperature: 0.7
			}
		];
		// Auto-generate next label
		const nextNum = editMultiLLMModels.length + 1;
		newModelLabel = `model_${nextNum}`;
		newModelName = '';
		markChanged();
	}

	function removeMultiLLMModel(id: string) {
		editMultiLLMModels = editMultiLLMModels.filter(m => m.id !== id);
		markChanged();
	}

	function updateMultiLLMModel(id: string, field: 'label' | 'name' | 'temperature' | 'maxTokens', value: string | number | undefined) {
		editMultiLLMModels = editMultiLLMModels.map(m =>
			m.id === id ? { ...m, [field]: value } : m
		);
		markChanged();
	}

	// Node config map (subgraph override) helpers
	function toggleOverrideNode(nodeId: string) {
		const newSet = new Set(expandedOverrideNodes);
		if (newSet.has(nodeId)) {
			newSet.delete(nodeId);
		} else {
			newSet.add(nodeId);
		}
		expandedOverrideNodes = newSet;
	}

	function hasOverride(nodeId: string): boolean {
		return nodeId in editNodeConfigMap;
	}

	function addOverrideForNode(nodeId: string) {
		if (!editNodeConfigMap[nodeId]) {
			editNodeConfigMap[nodeId] = {};
			editNodeConfigMap = { ...editNodeConfigMap };
			// Auto-expand the node
			expandedOverrideNodes = new Set([...expandedOverrideNodes, nodeId]);
			markChanged();
		}
	}

	function removeOverrideForNode(nodeId: string) {
		if (editNodeConfigMap[nodeId]) {
			delete editNodeConfigMap[nodeId];
			editNodeConfigMap = { ...editNodeConfigMap };
			markChanged();
		}
	}

	function updateOverrideField(nodeId: string, field: keyof NodeConfigOverride, value: unknown) {
		if (!editNodeConfigMap[nodeId]) {
			editNodeConfigMap[nodeId] = {};
		}
		if (value === '' || value === undefined || (typeof value === 'object' && Object.keys(value as object).length === 0)) {
			delete editNodeConfigMap[nodeId][field];
		} else {
			editNodeConfigMap[nodeId][field] = value;
		}
		// Clean up empty override objects
		if (Object.keys(editNodeConfigMap[nodeId]).length === 0) {
			delete editNodeConfigMap[nodeId];
		}
		editNodeConfigMap = { ...editNodeConfigMap };
		markChanged();
	}

	function addPlaceholderMapping(nodeId: string) {
		if (!editNodeConfigMap[nodeId]) {
			editNodeConfigMap[nodeId] = {};
		}
		if (!editNodeConfigMap[nodeId].prompt_placeholder_map) {
			editNodeConfigMap[nodeId].prompt_placeholder_map = {};
		}
		const newKey = `placeholder_${Object.keys(editNodeConfigMap[nodeId].prompt_placeholder_map!).length + 1}`;
		editNodeConfigMap[nodeId].prompt_placeholder_map![newKey] = '';
		editNodeConfigMap = { ...editNodeConfigMap };
		markChanged();
	}

	function removePlaceholderMapping(nodeId: string, key: string) {
		if (editNodeConfigMap[nodeId]?.prompt_placeholder_map) {
			delete editNodeConfigMap[nodeId].prompt_placeholder_map![key];
			if (Object.keys(editNodeConfigMap[nodeId].prompt_placeholder_map!).length === 0) {
				delete editNodeConfigMap[nodeId].prompt_placeholder_map;
			}
			// Clean up empty override objects
			if (Object.keys(editNodeConfigMap[nodeId]).length === 0) {
				delete editNodeConfigMap[nodeId];
			}
			editNodeConfigMap = { ...editNodeConfigMap };
			markChanged();
		}
	}

	function updatePlaceholderMapping(nodeId: string, oldKey: string, newKey: string, value: string) {
		if (editNodeConfigMap[nodeId]?.prompt_placeholder_map) {
			if (oldKey !== newKey) {
				delete editNodeConfigMap[nodeId].prompt_placeholder_map![oldKey];
			}
			editNodeConfigMap[nodeId].prompt_placeholder_map![newKey] = value;
			editNodeConfigMap = { ...editNodeConfigMap };
			markChanged();
		}
	}

	// Get inner node icon and color
	function getInnerNodeStyle(nodeType: string): { icon: typeof Bot; color: string } {
		const iconMap: Record<string, typeof Bot> = {
			llm: Bot,
			lambda: Zap,
			subgraph: Boxes,
			data: Database,
			branch: GitBranch,
			weighted_sampler: Shuffle
		};
		const colorMap: Record<string, string> = {
			llm: '#8b5cf6',
			lambda: '#f97316',
			subgraph: '#3b82f6',
			data: '#0ea5e9',
			branch: '#eab308',
			weighted_sampler: '#a855f7'
		};
		return {
			icon: iconMap[nodeType] ?? Bot,
			color: colorMap[nodeType] ?? '#6b7280'
		};
	}

	function updatePromptContent(index: number, content: string) {
		editPrompts[index].content = content;
		markChanged();
	}

	function updatePromptRole(index: number, role: string) {
		editPrompts[index].role = role;
		editPrompts = [...editPrompts]; // Trigger reactivity
		markChanged();
	}

	function addPromptMessage(role: string) {
		editPrompts = [...editPrompts, { role, content: '' }];
		markChanged();
	}

	function removePromptMessage(index: number) {
		editPrompts = editPrompts.filter((_, i) => i !== index);
		markChanged();
	}

	// Multi-modal prompt helpers
	function isMultiModalContent(content: string | MultiModalContentPart[]): content is MultiModalContentPart[] {
		return Array.isArray(content);
	}

	function toggleMultiModal(index: number) {
		const message = editPrompts[index];
		if (isMultiModalContent(message.content)) {
			// Convert multi-modal to simple text (take first text content)
			const textPart = message.content.find(p => p.type === 'text');
			message.content = textPart?.text ?? '';
		} else {
			// Convert simple text to multi-modal
			const textContent = message.content;
			message.content = textContent ? [{ type: 'text', text: textContent }] : [];
		}
		editPrompts = [...editPrompts];
		markChanged();
	}

	function addMultiModalPart(index: number, type: 'text' | 'audio_url' | 'image_url' | 'video_url') {
		const message = editPrompts[index];
		if (!isMultiModalContent(message.content)) return;

		const newPart: MultiModalContentPart = { type };
		if (type === 'text') newPart.text = '';
		else if (type === 'audio_url') newPart.audio_url = '';
		else if (type === 'image_url') newPart.image_url = '';
		else if (type === 'video_url') newPart.video_url = '';

		message.content = [...message.content, newPart];
		editPrompts = [...editPrompts];
		markChanged();
	}

	function removeMultiModalPart(promptIndex: number, partIndex: number) {
		const message = editPrompts[promptIndex];
		if (!isMultiModalContent(message.content)) return;

		message.content = message.content.filter((_, i) => i !== partIndex);
		editPrompts = [...editPrompts];
		markChanged();
	}

	function updateMultiModalPart(promptIndex: number, partIndex: number, value: string) {
		const message = editPrompts[promptIndex];
		if (!isMultiModalContent(message.content)) return;

		const part = message.content[partIndex];
		if (part.type === 'text') part.text = value;
		else if (part.type === 'audio_url') part.audio_url = value;
		else if (part.type === 'image_url') part.image_url = value;
		else if (part.type === 'video_url') part.video_url = value;

		editPrompts = [...editPrompts];
		markChanged();
	}

	function getMultiModalPartValue(part: MultiModalContentPart): string {
		if (part.type === 'text') return part.text ?? '';
		if (part.type === 'audio_url') return part.audio_url ?? '';
		if (part.type === 'image_url') return part.image_url ?? '';
		if (part.type === 'video_url') return part.video_url ?? '';
		return '';
	}

	function getMultiModalPartLabel(type: string): string {
		switch (type) {
			case 'text': return 'Text';
			case 'audio_url': return 'Audio URL';
			case 'image_url': return 'Image URL';
			case 'video_url': return 'Video URL';
			default: return type;
		}
	}

	function updateModelParameter(key: string, value: any) {
		editModelParameters[key] = value;
		editModelParameters = { ...editModelParameters };
		markChanged();
	}

	function addModelParameter() {
		const newKey = `param_${Object.keys(editModelParameters).length + 1}`;
		editModelParameters[newKey] = '';
		editModelParameters = { ...editModelParameters };
		markChanged();
	}

	function removeModelParameter(key: string) {
		delete editModelParameters[key];
		editModelParameters = { ...editModelParameters };
		markChanged();
	}

	function renameModelParameter(oldKey: string, newKey: string) {
		if (oldKey !== newKey && newKey.trim()) {
			const value = editModelParameters[oldKey];
			delete editModelParameters[oldKey];
			editModelParameters[newKey] = value;
			editModelParameters = { ...editModelParameters };
			markChanged();
		}
	}

	function parseParameterValue(value: string): any {
		// Try to parse as JSON, fall back to string
		try {
			return JSON.parse(value);
		} catch {
			return value;
		}
	}
</script>

<aside
	class="fixed right-0 top-0 h-full border-l border-surface-border bg-surface overflow-y-auto flex flex-col shadow-xl z-50"
	style="width: {panelWidth}px;"
>
	<!-- Resize handle -->
	<div
		class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-[#52B8FF]/50 transition-colors z-20 group"
		onmousedown={handleResizeMouseDown}
		role="separator"
		aria-orientation="vertical"
	>
		<div class="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
			<GripVertical size={12} class="text-text-muted" />
		</div>
	</div>
	<!-- Header -->
	<PanelHeader
		title={node?.summary || node?.id || 'Node Details'}
		subtitle={node ? node.node_type.replace('_', ' ') : undefined}
		icon={Icon}
		iconColor={color}
		nodeId={node?.id}
		{showNavigation}
		{hasPrevious}
		{hasNext}
		onPrevious={onPrevious}
		onNext={onNext}
		{isEditing}
		{hasChanges}
		{isSaving}
		canEdit={node ? node.node_type !== 'start' && node.node_type !== 'end' : false}
		onStartEdit={startEditing}
		onCancelEdit={cancelEditing}
		onSave={saveChanges}
		showCopyId={!!node}
		showDuplicate={!!node && !!onDuplicate && node.node_type !== 'start' && node.node_type !== 'end'}
		showDelete={!!node && node.node_type !== 'start' && node.node_type !== 'end'}
		{onDuplicate}
		onDelete={requestDeleteNode}
		onClose={() => {
			cancelEditing();
			dispatch('close');
		}}
	/>

	{#if node}
		<!-- Tabs -->
		<PanelTabs
			tabs={tabsConfig}
			{activeTab}
			onTabChange={handleTabChange}
		/>

		<!-- Tab Content -->
		<div class="flex-1 min-h-0 overflow-y-auto p-4">
			<!-- Details Tab -->
			{#if activeTab === 'details'}
				<div class="space-y-4">
					<!-- Skip ID/Summary/Description for data and output nodes - they don't need these fields -->
					{#if node.node_type !== 'data' && node.node_type !== 'output'}
						<!-- Node ID (editable) -->
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Node ID
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editNodeId}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm font-mono border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info"
									placeholder="Enter node ID..."
								/>
								<p class="text-xs text-text-muted mt-1">Use lowercase with underscores (e.g., my_node_id)</p>
							{:else}
								<div class="text-sm text-text-primary font-mono bg-surface-secondary px-2 py-1.5 rounded">
									{node.id}
								</div>
							{/if}
						</div>

						<!-- Node Name (editable) -->
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Node Name
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editSummary}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info"
									placeholder="Enter node name..."
								/>
							{:else}
								<div class="text-sm text-text-primary bg-surface-secondary px-3 py-2 rounded-lg">
									{node.summary || node.id}
								</div>
							{/if}
						</div>

						<!-- Description (editable) -->
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Description
							</div>
							{#if isEditing}
								<textarea
									bind:value={editDescription}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info resize-none"
									rows="3"
									placeholder="Enter node description..."
								></textarea>
							{:else if node.description}
								<div class="text-sm text-text-secondary bg-surface-secondary px-3 py-2 rounded-lg">
									{node.description}
								</div>
							{:else}
								<div class="text-sm text-text-muted italic">
									No description
								</div>
							{/if}
						</div>
					{/if}

					<!-- Model info (for LLM and Agent nodes) -->
					{#if node.node_type === 'llm' || node.node_type === 'agent'}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Model
							</div>
							{#if isEditing}
								<CustomSelect
									options={modelOptions}
									bind:value={editModel}
									placeholder="Select a model..."
									searchPlaceholder="Search models..."
									onchange={markChanged}
								/>
							{:else}
								<div class="text-sm text-text-primary bg-surface-secondary px-3 py-2 rounded-lg">
									{node.model?.name ?? 'Not set'}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Output Keys (for LLM, Agent, Lambda, Branch nodes) -->
					{#if ['llm', 'agent', 'lambda', 'branch'].includes(node.node_type)}
						<div class="space-y-2">
							<div class="flex items-center justify-between">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider flex items-center gap-1.5">
									<Download size={12} />
									Output Keys
								</div>
								<button
									type="button"
									class="text-text-muted hover:text-text-secondary"
									title={"Output keys define the state variable name(s) where this node's output will be stored. Use {key_name} in downstream prompts to reference these values."}
								>
									<Info size={14} />
								</button>
							</div>

							<!-- Tags display -->
							<div class="flex flex-wrap gap-1.5 min-h-[28px]">
								{#if editOutputKeys.length > 0}
									{#each editOutputKeys as key}
										<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-success-light dark:bg-success/20 text-success dark:text-success border border-success-border dark:border-success/40">
											<code class="font-mono">{key}</code>
											{#if isEditing}
												<button
													type="button"
													onclick={() => removeOutputKey(key)}
													class="ml-0.5 hover:text-error transition-colors"
													title="Remove key"
												>
													<X size={12} />
												</button>
											{/if}
										</span>
									{/each}
								{:else}
									<span class="text-xs text-text-muted dark:text-text-muted italic py-1">
										No keys configured (default: "messages")
									</span>
								{/if}
							</div>

							<!-- Add input (edit mode only) -->
							{#if isEditing}
								<div class="flex gap-2">
									<input
										type="text"
										bind:value={newOutputKeyInput}
										onkeydown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addOutputKey(); } }}
										placeholder="Add output key..."
										class="flex-1 px-3 py-1.5 text-sm font-mono border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-success focus:border-success"
									/>
									<button
										type="button"
										onclick={addOutputKey}
										class="px-3 py-1.5 text-sm font-medium text-success dark:text-success bg-success-light dark:bg-success/20 border border-success-border dark:border-success/40 rounded-lg hover:bg-success/30 dark:hover:bg-success/30 transition-colors flex items-center gap-1"
									>
										<Plus size={14} />
										Add
									</button>
								</div>
								{#if outputKeyError}
									<p class="text-xs text-error flex items-center gap-1">
										<AlertCircle size={12} />
										{outputKeyError}
									</p>
								{/if}
							{/if}

							<!-- Helper text -->
							<p class="text-xs text-text-muted dark:text-text-muted">
								Use <code class="px-1 py-0.5 bg-surface-secondary rounded font-mono text-status-completed">{'{'}key_name{'}'}</code> in downstream prompts to reference output values.
							</p>
						</div>
					{/if}

					<!-- Lambda function path -->
					{#if node.node_type === 'lambda' && node.function_path}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Function Path
							</div>
							<div class="text-sm text-text-primary font-mono bg-surface-secondary px-2 py-1.5 rounded break-all">
								{node.function_path}
							</div>
						</div>
					{/if}

					<!-- Subgraph path -->
					{#if node.node_type === 'subgraph' && node.subgraph_path}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">
								Subgraph Path
							</div>
							<div class="text-sm text-text-primary font-mono bg-surface-secondary px-2 py-1.5 rounded break-all">
								{node.subgraph_path}
							</div>
						</div>
					{/if}

					<!-- Data node config -->
					{#if node.node_type === 'data'}
						{@const sources = Array.isArray(node.data_config?.source) ? node.data_config.source : node.data_config?.source ? [node.data_config.source] : []}
						{@const sinks = Array.isArray(node.data_config?.sink) ? node.data_config.sink : node.data_config?.sink ? [node.data_config.sink] : []}
						{@const displayTransforms = sources.length > 0 && sources[0]?.transformations
							? sources[0].transformations.map((t: any, i: number) => ({
								id: t.id || `t_${i}`,
								transform: t.transform,
								params: t.params || {},
								enabled: t.enabled !== false
							}))
							: []}
						{@const displaySinks = sinks.map((s: any) => ({
							type: s.type || (s.repo_id ? 'hf' : s.table ? 'servicenow' : 'disk'),
							alias: s.alias,
							file_path: s.file_path,
							repo_id: s.repo_id,
							split: s.split,
							table: s.table,
							operation: s.operation
						}))}
						<DataConfigSection
							sources={isEditing ? editDataSources : sources}
							sinks={isEditing ? editDataSinks : displaySinks}
							transforms={isEditing ? editSourceTransforms : displayTransforms}
							idColumn={isEditing ? editIdColumn : node.data_config?.id_column}
							{isEditing}
							{sourcePreviewData}
							{sourcePreviewLoading}
							on:sourcesUpdate={handleSourcesUpdate}
							on:sinksUpdate={handleSinksUpdate}
							on:transformsUpdate={handleTransformsUpdate}
							on:sourcePreviewFetch={handleSourcePreviewFetch}
							on:sourcePreviewRefresh={handleSourcePreviewRefresh}
						/>
					{/if}

					<!-- Output node config -->
					{#if node.node_type === 'output'}
						{@const outputMap = node.output_config?.output_map || {}}
						{@const outputKeys = Object.keys(outputMap)}
						<div class="space-y-4">
							{#if isEditing}
								<!-- Edit Mode: Output Mappings -->
								<div class="space-y-3 p-3 bg-surface-secondary rounded-lg border border-surface-border">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-2 text-xs font-medium text-text-secondary">
											<MapIcon size={12} />
											Output Mappings
										</div>
										<button
											onclick={addOutputMapping}
											class="flex items-center gap-1 px-2 py-1 text-xs bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#BF71F2] rounded hover:bg-[#7661FF]/25 dark:hover:bg-[#7661FF]/30 transition-colors"
										>
											<Plus size={12} />
											Add Mapping
										</button>
									</div>

									{#if editOutputMappings.length > 0}
										<div class="space-y-2 max-h-64 overflow-y-auto">
											{#each editOutputMappings as mapping, idx}
												<div class="p-3 bg-surface rounded-lg border border-surface-border">
													<div class="flex items-center justify-between mb-3">
														<span class="text-xs font-medium text-text-secondary">Mapping {idx + 1}</span>
														<button
															onclick={() => removeOutputMapping(idx)}
															class="p-1 text-text-muted hover:text-error transition-colors rounded hover:bg-surface-hover"
														>
															<Trash2 size={14} />
														</button>
													</div>
													<div class="grid grid-cols-2 gap-3 mb-3">
														<div>
															<span class="block text-xs text-text-muted mb-1.5">Output Key *</span>
															<input
																type="text"
																value={mapping.key}
																oninput={(e) => updateOutputMapping(idx, 'key', e.currentTarget.value)}
																placeholder="field_name"
																aria-label="Output key"
																class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary font-mono focus:ring-2 focus:ring-info"
															/>
														</div>
														<div>
															<span class="block text-xs text-text-muted mb-1.5">From State</span>
															<StateVariableInput
																value={mapping.from}
																variables={availableStateVariables().variables}
																placeholder="Select state variable..."
																oninput={(val) => updateOutputMapping(idx, 'from', val)}
															/>
														</div>
													</div>
													<div class="grid grid-cols-2 gap-3">
														<div>
															<span class="block text-xs text-text-muted mb-1.5">Static Value (JSON)</span>
															<input
																type="text"
																value={mapping.value}
																oninput={(e) => updateOutputMapping(idx, 'value', e.currentTarget.value)}
																placeholder="JSON value"
																aria-label="Static value"
																class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary font-mono focus:ring-2 focus:ring-info"
															/>
														</div>
														<div>
															<span class="block text-xs text-text-muted mb-1.5">Transform Function</span>
															<input
																type="text"
																value={mapping.transform}
																oninput={(e) => updateOutputMapping(idx, 'transform', e.currentTarget.value)}
																placeholder="transform_func"
																aria-label="Transform function"
																class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary font-mono focus:ring-2 focus:ring-info"
															/>
														</div>
													</div>
												</div>
											{/each}
										</div>
									{:else}
										<div class="text-sm text-text-muted italic p-4 bg-surface rounded-lg border border-dashed border-surface-border text-center">
											No output mappings. Click "Add Mapping" to configure output fields.
										</div>
									{/if}
								</div>
							{:else}
								<!-- Display Mode: Generator -->
								{#if node.output_config?.generator}
									<div class="p-3 bg-surface-secondary rounded-lg border border-surface-border">
										<div class="flex items-center gap-2 text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] mb-2">
											<Code size={12} />
											Generator Class
										</div>
										<div class="text-sm font-mono bg-surface px-3 py-2 rounded-lg text-text-secondary break-all border border-surface-border">
											{node.output_config.generator.split('.').pop()}
										</div>
										<div class="text-xs text-text-muted mt-2 break-all font-mono">
											{node.output_config.generator}
										</div>
									</div>
								{/if}

								<!-- Display Mode: Output Map -->
								{#if outputKeys.length > 0}
									<div class="p-3 bg-surface-secondary rounded-lg border border-surface-border">
										<div class="flex items-center gap-2 text-xs font-medium text-text-secondary mb-3">
											<MapIcon size={12} />
											Output Mappings ({outputKeys.length})
										</div>
										<div class="space-y-2 max-h-64 overflow-y-auto">
											{#each outputKeys as key}
												{@const mapping = outputMap[key]}
												<div class="bg-surface rounded-lg border border-surface-border overflow-hidden">
													<div class="flex items-center gap-2 p-2 text-sm">
														<span class="font-mono text-text-secondary truncate flex-shrink-0" title={key}>
															{key.length > 15 ? key.slice(0, 15) + '...' : key}
														</span>
														<ArrowRight size={12} class="text-text-muted flex-shrink-0" />
														{#if mapping.from}
															<span class="font-mono text-[#7661FF] dark:text-[#BF71F2] truncate">{mapping.from}</span>
														{:else if mapping.value !== undefined}
															<span class="px-2 py-0.5 rounded bg-success-light dark:bg-success/20 text-success dark:text-success text-xs">static</span>
														{/if}
														{#if mapping.transform}
															<button
																type="button"
																onclick={() => toggleTransformCode(key, mapping.transform)}
																class="flex items-center gap-1 px-2 py-0.5 rounded bg-warning-light dark:bg-warning/20 text-warning text-xs flex-shrink-0 hover:bg-warning/30 dark:hover:bg-warning/40 transition-colors"
																title="Click to view transform function code"
															>
																<Code size={10} />
																fn: {mapping.transform}
																{#if transformCodeLoading[key]}
																	<Loader2 size={10} class="animate-spin" />
																{:else}
																	<ChevronDown size={10} class="transition-transform {transformCodeExpanded[key] ? 'rotate-180' : ''}" />
																{/if}
															</button>
														{/if}
													</div>
													<!-- Expandable transform code preview -->
													{#if mapping.transform && transformCodeExpanded[key]}
														<div class="border-t border-surface-border">
															{#if transformCodeLoading[key]}
																<div class="flex items-center justify-center py-3 bg-surface-secondary">
																	<Loader2 size={14} class="animate-spin text-text-muted" />
																	<span class="ml-2 text-xs text-text-muted">Loading...</span>
																</div>
															{:else if transformCodeMap[key]}
																<div class="monaco-editor-wrapper">
																	<MonacoEditor
																		value={transformCodeMap[key]}
																		language="python"
																		height="150px"
																																				fontSize={11}
																		readonly={true}
																	/>
																</div>
															{:else}
																<div class="text-center py-2 text-text-muted text-xs bg-surface-secondary">
																	Transform function not found
																</div>
															{/if}
														</div>
													{/if}
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="text-sm text-text-muted italic p-4 bg-surface-secondary rounded-lg border border-surface-border text-center">
										No output mappings configured.
									</div>
								{/if}
							{/if}
						</div>
					{/if}

					<!-- Weighted sampler config -->
					{#if node.node_type === 'weighted_sampler'}
						{@const attributes = node.sampler_config?.attributes || {}}
						{@const attributeNames = Object.keys(attributes)}
						<div class="space-y-4">
							<div class="flex items-center gap-2 text-xs font-medium text-text-muted uppercase tracking-wider">
								<Shuffle size={14} />
								Sampler Attributes
							</div>

							{#if isEditing}
								<!-- Edit Mode: Attributes -->
								<div class="space-y-3 p-3 bg-[#BF71F2]/10 dark:bg-[#BF71F2]/15 rounded-lg border border-[#BF71F2]/30 dark:border-[#BF71F2]/40">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-2 text-xs font-medium text-[#BF71F2] dark:text-[#d49af7]">
											Attributes
										</div>
										<button
											onclick={addSamplerAttribute}
											class="flex items-center gap-1 px-2 py-1 text-xs bg-[#BF71F2]/20 dark:bg-[#BF71F2]/25 text-[#BF71F2] dark:text-[#d49af7] rounded hover:bg-[#BF71F2]/30 dark:hover:bg-[#BF71F2]/35 transition-colors"
										>
											<Plus size={12} />
											Add
										</button>
									</div>

									{#if editSamplerAttributes.length > 0}
										<div class="space-y-2 max-h-64 overflow-y-auto">
											{#each editSamplerAttributes as attr, idx}
												<div class="p-2 bg-surface rounded border border-surface-border">
													<div class="flex items-center justify-between mb-2">
														<span class="text-xs text-text-muted">Attribute {idx + 1}</span>
														<button
															onclick={() => removeSamplerAttribute(idx)}
															class="p-1 text-text-muted hover:text-error transition-colors"
														>
															<Trash2 size={12} />
														</button>
													</div>
													<div class="grid grid-cols-1 gap-2">
														<div>
															<span class="block text-[10px] text-text-muted mb-0.5">Name</span>
															<input
																type="text"
																value={attr.name}
																oninput={(e) => updateSamplerAttribute(idx, 'name', e.currentTarget.value)}
																placeholder="num_turns"
																aria-label="Attribute name"
																class="w-full px-2 py-1 text-xs border border-surface-border rounded bg-surface text-text-primary font-mono"
															/>
														</div>
														<div>
															<span class="block text-[10px] text-text-muted mb-0.5">Values (comma-separated)</span>
															<input
																type="text"
																value={attr.values}
																oninput={(e) => updateSamplerAttribute(idx, 'values', e.currentTarget.value)}
																placeholder="2, 3, 4, 5 or professional, casual, friendly"
																aria-label="Attribute values"
																class="w-full px-2 py-1 text-xs border border-surface-border rounded bg-surface text-text-primary font-mono"
															/>
														</div>
													</div>
												</div>
											{/each}
										</div>
									{:else}
										<div class="text-xs text-text-muted italic p-2 bg-surface rounded">
											No attributes defined. Click "Add" to create sampler attributes.
										</div>
									{/if}
								</div>
							{:else}
								<!-- Display Mode: Attributes -->
								{#if attributeNames.length > 0}
									<div>
										<div class="text-xs font-medium text-[#BF71F2] dark:text-[#d49af7] mb-2">
											Attributes ({attributeNames.length})
										</div>
										<div class="space-y-2 max-h-48 overflow-y-auto">
											{#each attributeNames as name}
												{@const attr = attributes[name]}
												<div class="p-2 bg-surface-secondary rounded-lg text-xs">
													<div class="flex items-center justify-between mb-1">
														<span class="font-mono font-medium text-text-secondary">{name}</span>
														<span class="px-1.5 py-0.5 rounded bg-[#BF71F2]/15 dark:bg-[#BF71F2]/20 text-[#BF71F2] dark:text-[#d49af7] text-[10px]">
															{attr.values?.length ?? 0} values
														</span>
													</div>
													<div class="text-text-muted truncate" title={attr.values?.join(', ')}>
														{attr.values?.slice(0, 5).join(', ')}{attr.values?.length > 5 ? '...' : ''}
													</div>
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="text-xs text-text-muted italic p-2 bg-surface-secondary rounded">No attributes configured. Click Edit to add attributes.</div>
								{/if}
							{/if}
						</div>
					{/if}

					<!-- Execution state -->
					{#if nodeState}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
								Execution Status
							</div>
							<div class="space-y-2">
								<div class="flex items-center justify-between">
									<span class="text-sm text-text-secondary">Status</span>
									<span
										class="px-2 py-0.5 rounded text-xs font-medium capitalize"
										class:bg-surface-secondary={nodeState.status === 'pending'}
										class:text-text-secondary={nodeState.status === 'pending'}
										class:bg-info-light={nodeState.status === 'running'}
										class:text-info={nodeState.status === 'running'}
										class:bg-success-light={nodeState.status === 'completed'}
										class:text-success={nodeState.status === 'completed'}
										class:bg-error-light={nodeState.status === 'failed'}
										class:text-error={nodeState.status === 'failed'}
									>
										{nodeState.status}
									</span>
								</div>
								{#if nodeState.duration_ms}
									<div class="flex items-center justify-between">
										<span class="text-sm text-text-secondary">Duration</span>
										<span class="text-sm text-text-primary">
											{nodeState.duration_ms}ms
										</span>
									</div>
								{/if}
								{#if nodeState.error}
									<div class="mt-2 p-2 bg-error-light dark:bg-error/20 rounded text-xs text-error dark:text-error">
										{nodeState.error}
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Prompt Tab -->
			{#if activeTab === 'prompt' && showPromptTab}
				<div class="space-y-4">
					<!-- State Variables Panel - Modern Redesign -->
					{#if isEditing}
						<div class="bg-surface-secondary rounded-xl border border-surface-border shadow-sm overflow-hidden">
							<!-- Header -->
							<div class="px-4 py-3 flex items-center justify-between">
								<div class="flex items-center gap-2.5">
									<div class="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-sm">
										<Variable size={14} class="text-white" />
									</div>
									<div>
										<h3 class="text-sm font-semibold text-text-primary">Variables</h3>
										<p class="text-[10px] text-text-muted">Type <kbd class="px-1 py-0.5 bg-surface rounded text-[9px] font-mono shadow-sm border border-surface-border">{'{'}</kbd> to autocomplete</p>
									</div>
								</div>
								<span class="text-xs font-medium px-2 py-1 rounded-full bg-node-llm-bg dark:bg-node-llm/30 text-node-llm dark:text-node-llm">
									{availableStateVariables().variables.length}
								</span>
							</div>

							<!-- Search Input -->
							{#if availableStateVariables().variables.length > 5}
								<div class="px-4 pb-2">
									<div class="relative">
										<Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
										<input
											type="text"
											bind:value={variableFilter}
											placeholder="Filter variables..."
											class="w-full pl-9 pr-3 py-1.5 text-xs bg-surface border border-surface-border rounded-lg focus:ring-2 focus:ring-node-llm/20 focus:border-node-llm transition-all placeholder:text-text-muted"
										/>
									</div>
								</div>
							{/if}

							<!-- Variables Content -->
							<div class="px-4 pb-4 space-y-3">
								{#if true}
								{@const vars = filteredStateVariables()}

								<!-- Data Columns -->
								{#if vars.bySource.data.length > 0}
									<div class="space-y-1.5">
										<div class="flex items-center gap-1.5">
											<Database size={12} class="text-info" />
											<span class="text-[11px] font-medium text-text-secondary">Data</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each vars.bySource.data as variable}
												<button
													onclick={() => copyVariable(variable)}
													class="group relative inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-lg transition-all duration-200
														{copiedVariable === variable.name
															? 'bg-success-light dark:bg-success/30 text-success dark:text-success ring-2 ring-success/30'
															: 'bg-surface text-info dark:text-info border border-info-border dark:border-info/30 hover:border-info dark:hover:border-info hover:shadow-sm hover:shadow-info/10 dark:hover:shadow-info/20'
														}"
													title={variable.description || `Copy {${variable.name}}`}
												>
													{#if copiedVariable === variable.name}
														<Check size={12} class="text-success dark:text-success" />
														<span>Copied!</span>
													{:else}
														<span class="text-info/60 dark:text-info/60 opacity-60 group-hover:opacity-100">{'{'}</span>
														<span>{variable.name}</span>
														<span class="text-info/60 dark:text-info/60 opacity-60 group-hover:opacity-100">{'}'}</span>
													{/if}
												</button>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Node Outputs -->
								{#if vars.bySource.output.length > 0}
									<div class="space-y-1.5">
										<div class="flex items-center gap-1.5">
											<Zap size={12} class="text-success" />
											<span class="text-[11px] font-medium text-text-secondary">Outputs</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each vars.bySource.output as variable}
												<button
													onclick={() => copyVariable(variable)}
													class="group relative inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono rounded-lg transition-all duration-200
														{copiedVariable === variable.name
															? 'bg-success-light dark:bg-success/30 text-success dark:text-success ring-2 ring-success/30'
															: 'bg-surface text-success dark:text-success border border-success-border dark:border-success/30 hover:border-success dark:hover:border-success hover:shadow-sm hover:shadow-success/10 dark:hover:shadow-success/20'
														}"
													title="{variable.description || `From ${variable.sourceNode}`}"
												>
													{#if copiedVariable === variable.name}
														<Check size={12} class="text-success dark:text-success" />
														<span>Copied!</span>
													{:else}
														<span class="text-success/60 dark:text-success/60 opacity-60 group-hover:opacity-100">{'{'}</span>
														<span>{variable.name}</span>
														<span class="text-success/60 dark:text-success/60 opacity-60 group-hover:opacity-100">{'}'}</span>
														{#if variable.sourceNode}
															<span class="ml-0.5 px-1.5 py-0.5 text-[9px] bg-success-light dark:bg-success/20 text-status-completed rounded">
																{variable.sourceNode}
															</span>
														{/if}
													{/if}
												</button>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Sampler Attributes -->
								{#if vars.bySource.sampler.length > 0}
									<div class="space-y-1.5">
										<div class="flex items-center gap-1.5">
											<Shuffle size={12} class="text-node-llm" />
											<span class="text-[11px] font-medium text-text-secondary">Sampler</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each vars.bySource.sampler as variable}
												<button
													onclick={() => copyVariable(variable)}
													class="group relative inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono rounded-lg transition-all duration-200
														{copiedVariable === variable.name
															? 'bg-success-light dark:bg-success/30 text-success dark:text-success ring-2 ring-success/30'
															: 'bg-surface text-node-llm dark:text-node-llm border border-node-llm/30 dark:border-node-llm/40 hover:border-node-llm dark:hover:border-node-llm hover:shadow-sm hover:shadow-node-llm/10 dark:hover:shadow-node-llm/20'
														}"
													title="{variable.description || `Copy {${variable.name}}`}"
												>
													{#if copiedVariable === variable.name}
														<Check size={12} class="text-success dark:text-success" />
														<span>Copied!</span>
													{:else}
														<span class="text-node-llm/60 dark:text-node-llm/60 opacity-60 group-hover:opacity-100">{'{'}</span>
														<span>{variable.name}</span>
														<span class="text-node-llm/60 dark:text-node-llm/60 opacity-60 group-hover:opacity-100">{'}'}</span>
													{/if}
												</button>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Framework Variables -->
								{#if vars.bySource.framework.length > 0}
									<div class="space-y-1.5">
										<div class="flex items-center gap-1.5">
											<Settings size={12} class="text-slate-500" />
											<span class="text-[11px] font-medium text-text-secondary">Framework</span>
										</div>
										<div class="flex flex-wrap gap-1.5">
											{#each vars.bySource.framework as variable}
												<button
													onclick={() => copyVariable(variable)}
													class="group relative inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono rounded-lg transition-all duration-200
														{copiedVariable === variable.name
															? 'bg-success-light dark:bg-success/30 text-success dark:text-success ring-2 ring-success/30'
															: 'bg-surface text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700/50 hover:border-slate-400 dark:hover:border-slate-600 hover:shadow-sm hover:shadow-slate-100 dark:hover:shadow-slate-900/20'
														}"
													title="{variable.description}"
												>
													{#if copiedVariable === variable.name}
														<Check size={12} class="text-success dark:text-success" />
														<span>Copied!</span>
													{:else}
														<span class="text-slate-400 dark:text-slate-500 opacity-60 group-hover:opacity-100">{'{'}</span>
														<span>{variable.name}</span>
														<span class="text-slate-400 dark:text-slate-500 opacity-60 group-hover:opacity-100">{'}'}</span>
													{/if}
												</button>
											{/each}
										</div>
									</div>
								{/if}

								<!-- Empty State -->
								{#if vars.variables.length === 0}
									<div class="py-4 text-center">
										{#if variableFilter}
											<p class="text-xs text-text-muted">
												No variables matching "<span class="font-medium">{variableFilter}</span>"
											</p>
										{:else}
											<div class="flex flex-col items-center gap-2">
												<div class="w-10 h-10 rounded-full bg-surface-secondary flex items-center justify-center">
													<Variable size={18} class="text-text-muted" />
												</div>
												<div>
													<p class="text-xs font-medium text-text-secondary">No variables yet</p>
													<p class="text-[10px] text-text-muted dark:text-text-muted mt-0.5">Add a data source or upstream nodes with output_keys</p>
												</div>
											</div>
										{/if}
									</div>
								{/if}
								{/if}
							</div>
						</div>
					{/if}

					<!-- Validation Warnings -->
					{#if promptValidation().errors.length > 0}
						<div class="bg-warning-light dark:bg-warning/20 border border-warning-border dark:border-warning/30 rounded-xl overflow-hidden">
							<!-- Warning Header -->
							<div class="px-4 py-3 flex items-start gap-3">
								<div class="w-8 h-8 rounded-lg bg-warning-light dark:bg-warning/30 flex items-center justify-center flex-shrink-0">
									<AlertTriangle size={16} class="text-warning" />
								</div>
								<div class="flex-1 min-w-0">
									<h4 class="text-sm font-semibold text-warning dark:text-warning">
										{promptValidation().errors.length === 1 ? 'Undefined Variable' : `${promptValidation().errors.length} Undefined Variables`}
									</h4>
									<p class="text-xs text-warning dark:text-warning mt-0.5">
										The following variables are referenced but not available in this node's context:
									</p>
								</div>
							</div>

							<!-- Error List -->
							<div class="px-4 pb-3 space-y-2">
								{#each promptValidation().invalidReferences as ref}
									<div class="flex items-center gap-2 px-3 py-2 bg-surface/50 rounded-lg border border-warning-border dark:border-warning/20">
										<code class="px-2 py-0.5 text-xs font-mono bg-warning-light dark:bg-warning/30 text-warning dark:text-warning rounded">
											{'{' + ref.name + '}'}
										</code>
										<span class="text-xs text-warning dark:text-warning">
											is not defined
										</span>
									</div>
								{/each}
							</div>

							<!-- Help Text -->
							<div class="px-4 py-2.5 bg-warning-light dark:bg-warning/20 border-t border-warning-border dark:border-warning/20">
								<p class="text-[11px] text-warning dark:text-warning">
									<strong>How to fix:</strong> Ensure the variable is either a data column, an output_key from an upstream node, or a framework variable. Check that upstream nodes are connected and have the correct output_keys configured.
								</p>
							</div>
						</div>
					{/if}

					{#if isEditing}
						{#each editPrompts as message, index}
							<div class="border border-surface-border rounded-lg overflow-hidden">
								<div class="flex items-center justify-between px-3 py-2 bg-surface-secondary border-b border-surface-border">
									<div class="flex items-center gap-2">
										<CustomSelect
											options={roleOptions}
											value={message.role}
											compact={true}
											searchable={false}
											onchange={(val) => updatePromptRole(index, val)}
										/>
										<!-- Multi-modal toggle -->
										<label class="flex items-center gap-1.5 cursor-pointer ml-2">
											<span class="text-[10px] text-text-muted">Multi-modal</span>
											<button
												type="button"
												onclick={() => toggleMultiModal(index)}
												class="relative inline-flex h-4 w-7 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none {isMultiModalContent(message.content) ? 'bg-[#7661FF]' : 'bg-surface-tertiary'}"
												role="switch"
												aria-checked={isMultiModalContent(message.content)}
											>
												<span
													class="pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {isMultiModalContent(message.content) ? 'translate-x-3' : 'translate-x-0'}"
												></span>
											</button>
										</label>
									</div>
									<button
										onclick={() => removePromptMessage(index)}
										class="text-text-muted hover:text-error p-1"
									>
										<X size={14} />
									</button>
								</div>

								{#if isMultiModalContent(message.content)}
									<!-- Multi-modal content editing -->
									<div class="p-3 space-y-2 bg-surface">
										{#each message.content as part, partIndex}
											<div class="flex items-start gap-2 p-2 bg-surface-secondary rounded-lg border border-surface-border">
												<div class="flex-shrink-0 pt-1">
													<span class="inline-block px-2 py-0.5 text-[10px] font-medium rounded bg-[#7661FF]/10 text-[#7661FF] dark:bg-[#7661FF]/20 dark:text-[#BF71F2]">
														{getMultiModalPartLabel(part.type)}
													</span>
												</div>
												<div class="flex-1">
													{#if part.type === 'text'}
														<PromptTextarea
															value={part.text ?? ''}
															variables={availableStateVariables().variables}
															rows={3}
															placeholder={'Enter text content... Type \'{\' for variable autocomplete'}
															oninput={(val) => updateMultiModalPart(index, partIndex, val)}
															class="border border-surface-border rounded"
														/>
													{:else}
														<StateVariableInput
															value={getMultiModalPartValue(part)}
															variables={availableStateVariables().variables}
															placeholder={part.type === 'audio_url' ? 'Enter audio URL or variable...' : part.type === 'image_url' ? 'Enter image URL or variable...' : 'Enter video URL or variable...'}
															oninput={(val) => updateMultiModalPart(index, partIndex, val)}
														/>
													{/if}
												</div>
												<button
													onclick={() => removeMultiModalPart(index, partIndex)}
													class="flex-shrink-0 p-1 text-text-muted hover:text-error"
												>
													<X size={12} />
												</button>
											</div>
										{/each}

										<!-- Add content part buttons -->
										<div class="flex flex-wrap gap-1.5 pt-1">
											<button
												onclick={() => addMultiModalPart(index, 'text')}
												class="px-2 py-1 text-[10px] font-medium border border-dashed border-surface-border rounded text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
											>
												+ Text
											</button>
											<button
												onclick={() => addMultiModalPart(index, 'audio_url')}
												class="px-2 py-1 text-[10px] font-medium border border-dashed border-surface-border rounded text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
											>
												+ Audio URL
											</button>
											<button
												onclick={() => addMultiModalPart(index, 'image_url')}
												class="px-2 py-1 text-[10px] font-medium border border-dashed border-surface-border rounded text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
											>
												+ Image URL
											</button>
											<button
												onclick={() => addMultiModalPart(index, 'video_url')}
												class="px-2 py-1 text-[10px] font-medium border border-dashed border-surface-border rounded text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
											>
												+ Video URL
											</button>
										</div>
									</div>
								{:else}
									<!-- Simple text content editing -->
									<PromptTextarea
										bind:value={message.content}
										variables={availableStateVariables().variables}
										rows={6}
										placeholder={'Enter prompt content... Type \'{\' for variable autocomplete'}
										oninput={(val) => { editPrompts[index].content = val; markChanged(); }}
										class="border-0 rounded-none focus:ring-0"
									/>
								{/if}
							</div>
						{/each}

						<div class="flex gap-2">
							<button
								onclick={() => addPromptMessage('system')}
								class="flex-1 px-3 py-2 text-xs font-medium border border-dashed border-surface-border rounded-lg text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
							>
								+ System
							</button>
							<button
								onclick={() => addPromptMessage('user')}
								class="flex-1 px-3 py-2 text-xs font-medium border border-dashed border-surface-border rounded-lg text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
							>
								+ User
							</button>
							<button
								onclick={() => addPromptMessage('assistant')}
								class="flex-1 px-3 py-2 text-xs font-medium border border-dashed border-surface-border rounded-lg text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
							>
								+ Assistant
							</button>
						</div>
					{:else}
						{#each node.prompt ?? [] as message}
							<div class="border border-surface-border rounded-lg overflow-hidden">
								<div class="px-3 py-2 bg-surface-secondary border-b border-surface-border flex items-center gap-2">
									<span class="text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] capitalize">
										{message.role}
									</span>
									{#if isMultiModalContent(message.content)}
										<span class="text-[10px] px-1.5 py-0.5 rounded bg-[#7661FF]/10 text-[#7661FF] dark:bg-[#7661FF]/20 dark:text-[#BF71F2]">
											Multi-modal
										</span>
									{/if}
								</div>
								<div class="px-3 py-2 text-sm text-text-secondary bg-surface">
									{#if isMultiModalContent(message.content)}
										<!-- Display multi-modal content parts -->
										<div class="space-y-2">
											{#each message.content as part}
												<div class="flex items-start gap-2 p-2 bg-surface-secondary rounded border border-surface-border">
													<span class="flex-shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-[#7661FF]/10 text-[#7661FF] dark:bg-[#7661FF]/20 dark:text-[#BF71F2]">
														{getMultiModalPartLabel(part.type)}
													</span>
													<span class="font-mono text-sm break-all">
														{getMultiModalPartValue(part)}
													</span>
												</div>
											{/each}
										</div>
									{:else}
										<div class="whitespace-pre-wrap font-mono">
											{message.content}
										</div>
									{/if}
								</div>
							</div>
						{/each}

						{#if !node.prompt?.length}
							<div class="text-center py-8 text-text-muted text-sm">
								No prompts defined for this node
							</div>
						{/if}
					{/if}

					<!-- Multi-Turn Conversations Section (for LLM/Agent nodes) -->
					{#if node.node_type === 'llm' || node.node_type === 'agent'}
						<div class="border-t border-surface-border pt-4 mt-4">
							<!-- Header with toggle -->
							<div class="flex items-center justify-between mb-3">
								<div class="flex items-center gap-2">
									<MessageSquare size={14} class="text-text-muted" />
									<span class="text-sm font-medium text-text-secondary">Multi-Turn Conversations</span>
								</div>
								{#if isEditing}
									<label class="flex items-center gap-2 cursor-pointer">
										<span class="text-xs text-text-muted">Enable</span>
										<button
											type="button"
											onclick={() => { editChatHistoryEnabled = !editChatHistoryEnabled; markChanged(); }}
											class="relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-info focus:ring-offset-2 {editChatHistoryEnabled ? 'bg-[#7661FF]' : 'bg-surface-tertiary'}"
											role="switch"
											aria-checked={editChatHistoryEnabled}
										>
											<span
												class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {editChatHistoryEnabled ? 'translate-x-4' : 'translate-x-0'}"
											></span>
										</button>
									</label>
								{:else}
									<span class="text-xs px-2 py-0.5 rounded-full {node.chat_history ? 'bg-success-light text-status-completed' : 'bg-surface-secondary text-text-muted'}">
										{node.chat_history ? 'Enabled' : 'Disabled'}
									</span>
								{/if}
							</div>

							{#if isEditing && editChatHistoryEnabled}
								<!-- Description -->
								<p class="text-xs text-text-muted mb-4">
									Track conversation history across turns. Inject system messages at specific turns to guide the conversation flow.
								</p>

								<!-- System Message Injections -->
								<div class="space-y-3">
									<div class="flex items-center justify-between">
										<span class="text-xs font-medium text-text-secondary">Turn-Based System Injections</span>
										<span class="text-xs text-text-muted px-1.5 py-0.5 bg-surface-secondary rounded">
											{editInjectSystemMessages.length} configured
										</span>
									</div>

									<!-- Existing injections -->
									{#if editInjectSystemMessages.length > 0}
										<div class="space-y-2">
											{#each editInjectSystemMessages as msg (msg.id)}
												<div class="flex items-center gap-2 group">
													<div class="flex items-center gap-1 px-2 py-1.5 bg-[#7661FF]/10 dark:bg-[#7661FF]/15 rounded-lg border border-[#7661FF]/30 dark:border-[#7661FF]/40">
														<span class="text-[10px] text-[#7661FF] dark:text-[#BF71F2] uppercase">Turn</span>
														<input
															type="number"
															value={msg.turn}
															min="1"
															onchange={(e) => updateSystemMessageInjection(msg.id, 'turn', parseInt(e.currentTarget.value) || 1)}
															class="w-10 px-1 py-0.5 text-xs font-mono text-center border-0 bg-transparent text-[#7661FF] dark:text-[#BF71F2] focus:ring-0"
														/>
													</div>
													<div class="flex-1 relative">
														<input
															type="text"
															value={msg.message}
															oninput={(e) => updateSystemMessageInjection(msg.id, 'message', e.currentTarget.value)}
															placeholder="System message content..."
															class="w-full px-3 py-1.5 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
														/>
													</div>
													<button
														onclick={() => removeSystemMessageInjection(msg.id)}
														class="p-1.5 text-text-muted hover:text-error opacity-0 group-hover:opacity-100 transition-all"
														title="Remove"
													>
														<X size={14} />
													</button>
												</div>
											{/each}
										</div>
									{/if}

									<!-- Add new injection - inline form -->
									<div class="flex items-center gap-2">
										<div class="flex items-center gap-1 px-2 py-1.5 bg-surface-secondary rounded-lg border border-dashed border-surface-border">
											<span class="text-[10px] text-text-muted uppercase">Turn</span>
											<input
												type="number"
												bind:value={newInjectTurn}
												min="1"
												class="w-10 px-1 py-0.5 text-xs font-mono text-center border-0 bg-transparent text-text-secondary focus:ring-0"
											/>
										</div>
										<div class="flex-1">
											<input
												type="text"
												bind:value={newInjectMessage}
												placeholder="Add a system message to inject at this turn..."
												onkeydown={(e) => { if (e.key === 'Enter') addSystemMessageInjection(); }}
												class="w-full px-3 py-1.5 text-sm border border-dashed border-surface-border rounded-lg bg-surface-secondary text-text-primary focus:ring-2 focus:ring-info focus:border-transparent focus:bg-surface focus:border-solid"
											/>
										</div>
										<button
											onclick={addSystemMessageInjection}
											disabled={!newInjectTurn || newInjectTurn < 1 || !newInjectMessage.trim()}
											class="px-3 py-1.5 text-xs font-medium text-[#7661FF] hover:text-[#5a4dcc] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 disabled:text-text-muted disabled:hover:bg-transparent rounded-lg transition-colors"
										>
											<Plus size={14} />
										</button>
									</div>
								</div>

							{:else if !isEditing && node.chat_history}
								<!-- View mode -->
								<p class="text-xs text-text-muted mb-3">
									Conversation history is tracked across turns.
								</p>
								{#if node.inject_system_messages && node.inject_system_messages.length > 0}
									<div class="space-y-1.5">
										{#each node.inject_system_messages as msg}
											{@const turn = Object.keys(msg)[0]}
											{@const message = Object.values(msg)[0]}
											<div class="flex items-center gap-2">
												<span class="text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] px-2 py-0.5 bg-[#7661FF]/10 dark:bg-[#7661FF]/15 rounded">
													Turn {turn}
												</span>
												<span class="text-sm text-text-secondary">{message}</span>
											</div>
										{/each}
									</div>
								{:else}
									<div class="text-xs text-text-muted italic">No turn-based injections configured</div>
								{/if}

							{:else if !isEditing}
								<p class="text-xs text-text-muted">
									Enable to track conversation history and inject messages at specific turns.
								</p>
							{/if}
						</div>
					{/if}
				</div>
			{/if}

			<!-- Models Tab (for Multi-LLM nodes) -->
			{#if activeTab === 'models' && showModelsTab}
				<div class="space-y-4">
					<!-- Models Section -->
					<div>
						<div class="flex items-center justify-between mb-3">
							<span class="text-xs font-medium text-text-muted uppercase tracking-wider">
								Parallel Models
							</span>
							{#if isEditing}
								<span class="text-xs text-text-muted px-2 py-0.5 bg-surface-secondary rounded">
									{editMultiLLMModels.length} model{editMultiLLMModels.length !== 1 ? 's' : ''}
								</span>
							{/if}
						</div>

						{#if isEditing}
							<!-- Model cards -->
							{#if editMultiLLMModels.length > 0}
								<div class="space-y-3 mb-4">
									{#each editMultiLLMModels as model (model.id)}
										<div class="p-3 bg-surface rounded-lg border border-surface-border group hover:border-info dark:hover:border-info transition-colors">
											<!-- Model Header -->
											<div class="flex items-center justify-between mb-3">
												<div class="flex items-center gap-2">
													<div class="w-7 h-7 rounded-lg bg-info-light dark:bg-info/20 flex items-center justify-center">
														<Bot size={16} class="text-info dark:text-info" />
													</div>
													<input
														type="text"
														value={model.label}
														oninput={(e) => updateMultiLLMModel(model.id, 'label', e.currentTarget.value)}
														placeholder="model_label"
														class="px-2 py-1 text-sm font-semibold border border-transparent hover:border-surface-border focus:border-info rounded bg-transparent text-text-primary w-28"
													/>
												</div>
												<button
													onclick={() => removeMultiLLMModel(model.id)}
													class="p-1.5 text-text-muted hover:text-error hover:bg-error-light dark:hover:bg-error/20 rounded-md opacity-0 group-hover:opacity-100 transition-all"
													title="Remove model"
												>
													<X size={14} />
												</button>
											</div>

											<!-- Model Selection -->
											<div class="mb-3">
												<label class="text-[10px] text-text-muted uppercase tracking-wide block mb-1">Model</label>
												<CustomSelect
													options={modelOptions}
													value={model.name}
													placeholder="Select model..."
													searchable={true}
													onchange={(val) => updateMultiLLMModel(model.id, 'name', val)}
												/>
											</div>

											<!-- Parameters -->
											<div class="grid grid-cols-2 gap-3">
												<div>
													<label class="text-[10px] text-text-muted uppercase tracking-wide block mb-1">Temperature</label>
													<input
														type="number"
														value={model.temperature}
														oninput={(e) => updateMultiLLMModel(model.id, 'temperature', parseFloat(e.currentTarget.value) || 0.7)}
														min="0"
														max="2"
														step="0.1"
														class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
													/>
												</div>
												<div>
													<label class="text-[10px] text-text-muted uppercase tracking-wide block mb-1">Max Tokens</label>
													<input
														type="number"
														value={model.maxTokens ?? ''}
														oninput={(e) => updateMultiLLMModel(model.id, 'maxTokens', e.currentTarget.value ? parseInt(e.currentTarget.value) : undefined)}
														min="1"
														placeholder="—"
														class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
													/>
												</div>
											</div>
										</div>
									{/each}
								</div>
							{:else}
								<div class="text-center py-8 text-text-muted text-sm border border-dashed border-surface-border rounded-lg mb-4">
									<Bot size={24} class="mx-auto mb-2 opacity-50" />
									No models configured.<br />Add at least two models for parallel execution.
								</div>
							{/if}

							<!-- Add new model form -->
							<div class="p-3 bg-surface-secondary rounded-lg border border-dashed border-surface-border">
								<div class="text-xs font-medium text-text-secondary mb-3">Add Model</div>
								<div class="flex items-end gap-2">
									<div class="w-28">
										<label class="text-[10px] text-text-muted uppercase tracking-wide block mb-1">Label</label>
										<input
											type="text"
											bind:value={newModelLabel}
											placeholder="model_1"
											class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
										/>
									</div>
									<div class="flex-1">
										<label class="text-[10px] text-text-muted uppercase tracking-wide block mb-1">Model</label>
										<CustomSelect
											options={modelOptions}
											bind:value={newModelName}
											placeholder="Select model..."
											searchable={true}
											onchange={(val) => { newModelName = val; }}
										/>
									</div>
									<button
										onclick={addMultiLLMModel}
										disabled={!newModelLabel.trim() || !newModelName.trim()}
										class="px-4 py-2 text-sm font-medium text-white bg-info hover:bg-info/90 disabled:bg-surface-tertiary disabled:cursor-not-allowed rounded-lg transition-colors flex items-center gap-1.5"
									>
										<Plus size={16} />
										Add
									</button>
								</div>
							</div>

						{:else}
							<!-- View mode -->
							{#if node?.models && Object.keys(node.models).length > 0}
								<div class="space-y-2">
									{#each Object.entries(node.models) as [label, config]}
										<div class="flex items-center justify-between p-3 bg-surface-secondary rounded-lg border border-surface-border">
											<div class="flex items-center gap-3">
												<div class="w-8 h-8 rounded-lg bg-info-light dark:bg-info/20 flex items-center justify-center">
													<Bot size={16} class="text-info dark:text-info" />
												</div>
												<div>
													<div class="font-medium text-sm text-text-primary">{label}</div>
													<div class="text-xs text-text-muted font-mono">{config.name}</div>
												</div>
											</div>
											{#if config.parameters?.temperature !== undefined}
												<div class="flex items-center gap-1 text-xs text-text-muted">
													<Thermometer size={12} />
													<span>{config.parameters.temperature}</span>
												</div>
											{/if}
										</div>
									{/each}
								</div>
							{:else}
								<div class="text-center py-6 text-text-muted text-sm">
									No models configured
								</div>
							{/if}
						{/if}
					</div>

					<!-- Post-processor Section -->
					<div class="border-t border-surface-border pt-4">
						<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
							Post-Processor (Optional)
						</div>
						{#if isEditing}
							<input
								type="text"
								bind:value={editMultiLLMPostProcess}
								oninput={() => markChanged()}
								placeholder="module.path.CustomPostProcessor"
								class="w-full px-3 py-2 text-sm font-mono border border-surface-border rounded-lg bg-surface text-text-primary"
							/>
							<p class="mt-1 text-xs text-text-muted">
								Custom function to aggregate responses from all models.
							</p>
						{:else}
							{#if node?.multi_llm_post_process}
								<div class="px-3 py-2 text-sm font-mono bg-surface-secondary rounded-lg text-text-secondary">
									{node.multi_llm_post_process}
								</div>
							{:else}
								<div class="text-xs text-text-muted italic">Using default aggregator</div>
							{/if}
						{/if}
					</div>

					<!-- Help Section -->
					<div class="bg-info-light dark:bg-info/20 border border-info-border dark:border-info/40 rounded-lg p-3">
						<div class="flex items-start gap-2">
							<GitCompareArrows size={16} class="text-info dark:text-info mt-0.5" />
							<div class="text-xs text-info dark:text-info">
								<strong>Multi-LLM Execution</strong>
								<p class="mt-1 text-info dark:text-info">
									All models execute in parallel with the same prompt. Use for model comparison, A/B testing, or ensemble responses.
								</p>
							</div>
						</div>
					</div>
				</div>
			{/if}

			<!-- Tools Tab -->
			{#if activeTab === 'tools' && showToolsTab}
				<div class="space-y-4">
					<!-- Tool Choice -->
					<div>
						<span class="block text-xs font-medium text-text-muted uppercase tracking-wider mb-1.5">
							Tool Choice
						</span>
						{#if isEditing}
							<CustomSelect
								options={toolChoiceOptions}
								bind:value={editToolChoice}
								placeholder="Select tool mode..."
								searchable={false}
								onchange={markChanged}
							/>
						{:else}
							<div class="px-3 py-2 text-sm bg-surface-secondary rounded-lg text-text-secondary">
								{toolChoiceOptions.find(o => o.value === editToolChoice)?.label ?? 'Auto'} — {toolChoiceOptions.find(o => o.value === editToolChoice)?.subtitle ?? ''}
							</div>
						{/if}
					</div>

					<!-- Tools Section -->
					<div>
						<div class="flex items-center justify-between mb-3">
							<span class="text-xs font-medium text-text-muted uppercase tracking-wider">
								Tools
							</span>
							{#if isEditing}
								<button
									onclick={() => { showToolPicker = true; }}
									class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 rounded-md transition-colors"
								>
									<Plus size={14} />
									Add Tool
								</button>
							{/if}
						</div>

						<!-- Tool cards -->
						{#if editTools.length > 0}
							<div class="space-y-2">
								{#each editTools as toolPath, index}
									{@const toolName = toolPath.split('.').pop() || toolPath}
									{@const modulePath = toolPath.split('.').slice(0, -1).join('.')}
									{@const libraryTool = toolStore.getToolByPath(toolPath)}
									<div class="flex items-start gap-3 p-3 bg-surface rounded-lg border border-surface-border group hover:border-[#7661FF]/50 dark:hover:border-[#7661FF]/60 transition-colors">
										<div class="w-8 h-8 rounded-md bg-[#7661FF]/15 dark:bg-[#7661FF]/20 flex items-center justify-center flex-shrink-0">
											{#if libraryTool}
												<Library size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
											{:else}
												<Wrench size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
											{/if}
										</div>
										<div class="flex-1 min-w-0">
											<div class="font-medium text-sm text-text-primary">
												{libraryTool?.name || toolName}
											</div>
											{#if libraryTool?.description}
												<div class="text-xs text-text-muted truncate">
													{libraryTool.description}
												</div>
											{:else if modulePath}
												<div class="text-xs text-text-muted font-mono truncate" title={toolPath}>
													{modulePath}
												</div>
											{/if}
										</div>
										{#if isEditing}
											<button
												onclick={() => {
													editTools = editTools.filter((_, i) => i !== index);
													markChanged();
												}}
												class="p-1.5 text-text-muted hover:text-error hover:bg-error-light dark:hover:bg-error/20 rounded-md transition-colors opacity-0 group-hover:opacity-100"
												title="Remove tool"
											>
												<X size={14} />
											</button>
										{/if}
									</div>
								{/each}
							</div>
						{:else}
							<div class="text-center py-8 border-2 border-dashed border-surface-border rounded-lg">
								<Wrench size={28} class="mx-auto mb-2 text-text-muted" />
								<p class="text-sm text-text-muted mb-1">No tools configured</p>
								{#if isEditing}
									<p class="text-xs text-text-muted dark:text-text-muted">Click "Add Tool" to select from library or enter path</p>
								{/if}
							</div>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Code Tab -->
			{#if activeTab === 'code' && showCodeTab}
				<div class="space-y-4 code-tab-content">
					<!-- Loading indicator -->
					{#if isLoadingCode}
						<div class="flex items-center gap-2 text-sm text-info bg-info-light dark:bg-info/20 px-3 py-2 rounded-lg">
							<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
							Loading code from files...
						</div>
					{/if}

					<!-- Error display -->
					{#if codeLoadError}
						<div class="text-sm text-error bg-error-light dark:bg-error/20 px-3 py-2 rounded-lg">
							⚠️ {codeLoadError}
						</div>
					{/if}

					<!-- Code loaded indicators -->
					{#if postProcessCodeLoaded || preProcessCodeLoaded || lambdaCodeLoaded}
						<div class="text-xs text-success dark:text-success bg-success-light dark:bg-success/20 px-3 py-1.5 rounded">
							✓ Loaded: {[
								preProcessCodeLoaded ? 'pre-process' : null,
								postProcessCodeLoaded ? 'post-process' : null,
								lambdaCodeLoaded ? 'lambda' : null
							].filter(Boolean).join(', ')}
						</div>
					{/if}

					<!-- Data Node: Transformation Code -->
					{#if node.node_type === 'data'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-warning uppercase tracking-wider">
									Data Transformation
								</div>
								<span class="text-xs text-text-muted">Python class</span>
							</div>
							<div class="text-xs text-text-muted mb-2">
								Transform data records during processing. This code will be saved to task_executor.py.
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:this={codeEditorRef}
									bind:value={editTransformCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									fontSize={12}
									readonly={!isEditing}
									autofocus={codeTabJustActivated}
									on:change={() => markChanged()}
									on:save={saveChanges}
								/>
							</div>
						</div>
					{/if}

					<!-- Output Node: Generator Code -->
					{#if node.node_type === 'output'}
						<div class="space-y-4">
							<!-- Generator Class Section (non-collapsible) -->
							<div>
								<div class="flex items-center justify-between mb-2">
									<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
										Generator Class
									</div>
									<span class="text-xs text-text-muted">Output transformer</span>
								</div>
								<!-- Monaco Editor - read-only when not editing -->
								<div class="monaco-editor-wrapper">
									<div class="text-xs text-text-muted mb-1">{isEditing ? 'Code Editor:' : 'Code Preview:'}</div>
									{#if isEditing}
										<MonacoEditor
											bind:this={codeEditorRef}
											bind:value={editOutputGeneratorCode}
											language="python"
											height="clamp(300px, 40vh, 500px)"
											fontSize={12}
											readonly={false}
											autofocus={codeTabJustActivated}
											on:change={() => markChanged()}
											on:save={saveChanges}
										/>
									{:else if fetchedGeneratorLoading}
										<div class="flex items-center justify-center py-8 border border-surface-border rounded-lg">
											<Loader2 size={20} class="animate-spin text-text-muted" />
											<span class="ml-2 text-sm text-text-muted">Loading code...</span>
										</div>
									{:else if fetchedGeneratorCode}
										<MonacoEditor
											value={fetchedGeneratorCode}
											language="python"
											height="clamp(300px, 40vh, 500px)"
											fontSize={12}
											readonly={true}
										/>
									{:else}
										<div class="text-center py-6 text-text-muted text-sm border border-surface-border rounded-lg">
											No generator code found. The file may not exist yet.
										</div>
									{/if}
								</div>
							</div>

							<!-- Transform Functions Section (if any mappings have transforms) -->
							{#if !isEditing && Object.entries(node.output_config?.output_map || {}).some(([_, m]) => m.transform)}
								{@const mappingsWithTransform = Object.entries(node.output_config?.output_map || {}).filter(([_, m]) => m.transform)}
								<div class="border border-surface-border rounded-lg overflow-hidden">
									<div class="p-3 bg-surface-secondary">
										<div class="flex items-center gap-2">
											<Zap size={14} class="text-warning" />
											<span class="text-sm font-medium text-text-secondary">Transform Functions</span>
											<span class="text-xs text-text-muted">({mappingsWithTransform.length})</span>
										</div>
									</div>
									<div class="divide-y divide-surface-border">
										{#each mappingsWithTransform as [key, mapping]}
											<div class="p-3">
												<button
													type="button"
													onclick={() => toggleTransformCode(key, mapping.transform)}
													class="w-full flex items-center justify-between mb-2 text-left"
												>
													<div class="flex items-center gap-2">
														<span class="text-sm font-mono text-text-secondary">{key}</span>
														<ArrowRight size={12} class="text-text-muted" />
														<span class="px-2 py-0.5 rounded bg-warning-light dark:bg-warning/20 text-warning text-xs font-mono">
															{mapping.transform}()
														</span>
													</div>
													<div class="flex items-center gap-2">
														{#if transformCodeLoading[key]}
															<Loader2 size={12} class="animate-spin text-text-muted" />
														{/if}
														<ChevronDown size={14} class="text-text-muted transition-transform {transformCodeExpanded[key] ? 'rotate-180' : ''}" />
													</div>
												</button>
												{#if transformCodeExpanded[key]}
													{#if transformCodeLoading[key]}
														<div class="flex items-center justify-center py-4">
															<Loader2 size={16} class="animate-spin text-text-muted" />
														</div>
													{:else if transformCodeMap[key]}
														<div class="monaco-editor-wrapper mt-2">
															<MonacoEditor
																value={transformCodeMap[key]}
																language="python"
																height="clamp(150px, 20vh, 250px)"
																																fontSize={11}
																readonly={true}
															/>
														</div>
													{:else}
														<div class="text-center py-3 text-text-muted text-xs">
															Transform function code not found
														</div>
													{/if}
												{/if}
											</div>
										{/each}
									</div>
								</div>
							{/if}
						</div>
					{/if}

					<!-- Lambda function (PRIMARY code for lambda nodes - shown first) -->
					{#if node.node_type === 'lambda'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-warning dark:text-warning uppercase tracking-wider">
									Lambda Function
								</div>
								<span class="text-xs text-text-muted">Primary function code</span>
							</div>
							{#if isEditing}
								<div class="mb-2">
									<span class="block text-xs text-text-muted mb-1">Function Path</span>
									<input
										type="text"
										bind:value={editFunctionPath}
										oninput={markChanged}
										aria-label="Function path"
										class="w-full px-3 py-2 text-sm font-mono border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info"
										placeholder="tasks.my_task.task_executor.my_function"
									/>
								</div>
							{:else if node.function_path}
								<div class="text-sm text-text-primary font-mono bg-surface-secondary px-3 py-2 rounded-lg break-all mb-2">
									{node.function_path}
								</div>
							{:else}
								<div class="text-sm text-text-muted italic mb-2">
									No function path defined
								</div>
							{/if}
							<div class="text-xs text-text-muted mb-2">
								{isEditing ? 'Edit the lambda function code. This will be saved to task_executor.py.' : 'Lambda function code.'}
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:this={codeEditorRef}
									bind:value={lambdaCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									fontSize={12}
									readonly={!isEditing}
									autofocus={codeTabJustActivated}
									on:change={() => markChanged()}
									on:save={saveChanges}
								/>
							</div>
						</div>
					{/if}

					<!-- Branch condition (PRIMARY code for branch nodes - shown first) -->
					{#if node.node_type === 'branch'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-warning dark:text-warning uppercase tracking-wider">
									Branch Condition
								</div>
								<span class="text-xs text-text-muted">Primary condition code</span>
							</div>
							<div class="text-xs text-text-muted mb-2">
								{isEditing ? 'Edit the condition logic that determines which path to take.' : 'Condition logic that determines which path to take. This code will be saved to task_executor.py.'}
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:value={branchConditionCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
									on:save={saveChanges}
								/>
							</div>
						</div>
					{/if}

					<!-- Pre-processor (optional hook for execution nodes) -->
					{#if canHaveProcessors && (node.pre_process || isEditing)}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
									Pre-processor
								</div>
								<span class="text-xs text-text-muted">Optional hook</span>
							</div>
							<!-- Monaco Editor - read-only when not editing -->
							<div class="mt-2 monaco-editor-wrapper">
								<div class="text-xs text-text-muted mb-1">{isEditing ? 'Code Editor:' : 'Code Preview:'}</div>
								<MonacoEditor
									bind:this={codeEditorRef}
									bind:value={preProcessCode}
									language="python"
									height="clamp(200px, 25vh, 350px)"
									fontSize={12}
									readonly={!isEditing}
									autofocus={codeTabJustActivated}
									on:change={() => markChanged()}
									on:save={saveChanges}
								/>
							</div>
						</div>
					{/if}

					<!-- Post-processor (optional hook for execution nodes) -->
					{#if canHaveProcessors && (node.post_process || isEditing)}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
									Post-processor
								</div>
								<span class="text-xs text-text-muted">Optional hook</span>
							</div>
							<!-- Monaco Editor - read-only when not editing -->
							<div class="mt-2 monaco-editor-wrapper">
								<div class="text-xs text-text-muted mb-1">{isEditing ? 'Code Editor:' : 'Code Preview:'}</div>
								<MonacoEditor
									bind:value={postProcessCode}
									language="python"
									height="clamp(200px, 25vh, 350px)"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
									on:save={saveChanges}
								/>
							</div>
						</div>
					{/if}

					{#if !canHaveProcessors && !node.pre_process && !node.post_process && node.node_type !== 'lambda' && node.node_type !== 'branch' && node.node_type !== 'data' && node.node_type !== 'output' && !isEditing}
						<div class="text-center py-8 text-text-muted text-sm">
							No code configuration for this node
						</div>
					{/if}
				</div>
			{/if}

			<!-- Overrides Tab (for subgraph nodes) -->
			{#if activeTab === 'overrides' && showOverridesTab}
				<div class="space-y-4">
					<!-- Header with search and info -->
					<div class="flex items-center justify-between gap-3">
						<div class="flex-1">
							<div class="relative">
								<input
									type="text"
									bind:value={overrideSearchQuery}
									placeholder="Search inner nodes..."
									class="w-full pl-3 pr-8 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
								/>
								{#if overrideSearchQuery}
									<button
										onclick={() => overrideSearchQuery = ''}
										class="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-gray-600"
									>
										<X size={14} />
									</button>
								{/if}
							</div>
						</div>
					</div>

					<!-- Info banner -->
					<div class="p-3 bg-info-light dark:bg-info/20 border border-info-border dark:border-info/40 rounded-lg">
						<div class="flex items-start gap-2">
							<Info size={16} class="text-info mt-0.5 flex-shrink-0" />
							<div class="text-xs text-info dark:text-info">
								<strong>Node Configuration Overrides</strong> allow you to customize inner node settings without modifying the original subgraph. Add overrides for model, placeholders, or processors.
							</div>
						</div>
					</div>

					<!-- Inner nodes list -->
					<div class="space-y-2">
						{#each filteredInnerNodes() as innerNode (innerNode.id)}
							{@const nodeStyle = getInnerNodeStyle(innerNode.node_type)}
							{@const NodeIcon = nodeStyle.icon}
							{@const isExpanded = expandedOverrideNodes.has(innerNode.id)}
							{@const nodeHasOverride = hasOverride(innerNode.id)}
							{@const override = editNodeConfigMap[innerNode.id]}

							<div
								class="rounded-lg border transition-all {nodeHasOverride ? 'border-warning-border dark:border-warning/40 bg-warning-light dark:bg-warning/10' : 'border-surface-border bg-surface'}"
							>
								<!-- Node header (collapsible) -->
								<button
									onclick={() => toggleOverrideNode(innerNode.id)}
									class="w-full flex items-center gap-3 p-3 text-left hover:bg-surface-hover/50 rounded-lg transition-colors"
								>
									<!-- Expand/collapse chevron -->
									<div class="text-text-muted transition-transform" class:rotate-90={isExpanded}>
										<ChevronRight size={16} />
									</div>

									<!-- Node icon -->
									<div
										class="w-7 h-7 rounded-md flex items-center justify-center text-white flex-shrink-0"
										style="background-color: {nodeStyle.color}"
									>
										<NodeIcon size={14} />
									</div>

									<!-- Node info -->
									<div class="flex-1 min-w-0">
										<div class="flex items-center gap-2">
											<span class="text-sm font-medium text-text-primary truncate">
												{innerNode.summary || innerNode.id}
											</span>
											{#if nodeHasOverride}
												<span class="px-1.5 py-0.5 text-xs bg-warning-light dark:bg-warning/40 text-warning dark:text-warning rounded font-medium">
													Overridden
												</span>
											{/if}
										</div>
										<div class="text-xs text-text-muted font-mono truncate">
											{innerNode.id}
										</div>
									</div>

									<!-- Quick action button -->
									{#if !nodeHasOverride && isEditing}
										<span
											role="button"
											tabindex="0"
											onclick={(e) => { e.stopPropagation(); addOverrideForNode(innerNode.id); }}
											onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); addOverrideForNode(innerNode.id); } }}
											class="px-2 py-1 text-xs font-medium text-[#7661FF] hover:text-[#5a4dcc] bg-[#7661FF]/15 hover:bg-[#7661FF]/25 dark:bg-[#7661FF]/20 dark:hover:bg-[#7661FF]/30 dark:text-[#BF71F2] rounded transition-colors cursor-pointer"
										>
											+ Add Override
										</span>
									{/if}
								</button>

								<!-- Expanded override editor -->
								{#if isExpanded}
									<div class="px-3 pb-3 pt-1 border-t border-surface-border/50">
										{#if nodeHasOverride && override}
											{#if isEditing}
												<!-- Edit mode: Override configuration form -->
												<div class="space-y-4 mt-3">
													<!-- Model Override -->
													{#if innerNode.node_type === 'llm' || innerNode.node_type === 'agent'}
														<div class="space-y-2">
															<label class="flex items-center gap-2 text-xs font-medium text-text-secondary">
																<Bot size={12} />
																Model Override
															</label>
															<input
																type="text"
																value={override.model?.name ?? ''}
																oninput={(e) => updateOverrideField(innerNode.id, 'model', e.currentTarget.value ? { name: e.currentTarget.value } : undefined)}
																placeholder="e.g., gpt-4o, claude-3-5-sonnet"
																class="w-full px-3 py-2 text-sm border border-surface-border rounded-lg bg-surface text-text-primary focus:ring-2 focus:ring-info font-mono"
															/>
														</div>
													{/if}

													<!-- Prompt Placeholder Map -->
													<div class="space-y-2">
														<div class="flex items-center justify-between">
															<label class="flex items-center gap-2 text-xs font-medium text-text-secondary">
																<Copy size={12} />
																Placeholder Mappings
															</label>
															<button
																onclick={() => addPlaceholderMapping(innerNode.id)}
																class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-[#7661FF] hover:text-[#5a4dcc] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 rounded transition-colors"
															>
																<Plus size={12} />
																Add
															</button>
														</div>

														{#if override.prompt_placeholder_map && Object.keys(override.prompt_placeholder_map).length > 0}
															<div class="space-y-2">
																{#each Object.entries(override.prompt_placeholder_map) as [key, value]}
																	<div class="flex items-center gap-2">
																		<input
																			type="text"
																			value={key}
																			onblur={(e) => {
																				const newKey = e.currentTarget.value;
																				if (newKey && newKey !== key) {
																					updatePlaceholderMapping(innerNode.id, key, newKey, value);
																				}
																			}}
																			placeholder="placeholder_name"
																			class="flex-1 px-2 py-1.5 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
																		/>
																		<ArrowRight size={14} class="text-text-muted flex-shrink-0" />
																		<input
																			type="text"
																			value={value}
																			oninput={(e) => updatePlaceholderMapping(innerNode.id, key, key, e.currentTarget.value)}
																			placeholder="mapped_value"
																			class="flex-1 px-2 py-1.5 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
																		/>
																		<button
																			onclick={() => removePlaceholderMapping(innerNode.id, key)}
																			class="p-1 text-text-muted hover:text-error transition-colors"
																		>
																			<Trash2 size={14} />
																		</button>
																	</div>
																{/each}
															</div>
														{:else}
															<div class="text-xs text-text-muted italic py-2">
																No placeholder mappings. Click "Add" to create one.
															</div>
														{/if}
													</div>

													<!-- Pre/Post Process Overrides -->
													{#if innerNode.node_type !== 'data' && innerNode.node_type !== 'output'}
														<div class="grid grid-cols-2 gap-3">
															<div class="space-y-2">
																<label class="flex items-center gap-2 text-xs font-medium text-text-secondary">
																	<Code size={12} />
																	Pre-process
																</label>
																<input
																	type="text"
																	value={override.pre_process ?? ''}
																	oninput={(e) => updateOverrideField(innerNode.id, 'pre_process', e.currentTarget.value || undefined)}
																	placeholder="path.to.pre_processor"
																	class="w-full px-2 py-1.5 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
																/>
															</div>
															<div class="space-y-2">
																<label class="flex items-center gap-2 text-xs font-medium text-text-secondary">
																	<Code size={12} />
																	Post-process
																</label>
																<input
																	type="text"
																	value={override.post_process ?? ''}
																	oninput={(e) => updateOverrideField(innerNode.id, 'post_process', e.currentTarget.value || undefined)}
																	placeholder="path.to.post_processor"
																	class="w-full px-2 py-1.5 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
																/>
															</div>
														</div>
													{/if}

													<!-- Remove override button -->
													<div class="pt-2 border-t border-surface-border">
														<button
															onclick={() => removeOverrideForNode(innerNode.id)}
															class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-error hover:text-error hover:bg-error-light dark:hover:bg-error/20 rounded transition-colors"
														>
															<Trash2 size={12} />
															Remove Override
														</button>
													</div>
												</div>
											{:else}
												<!-- View mode: Display current overrides -->
												<div class="space-y-3 mt-3">
													{#if override.model}
														<div class="flex items-start gap-2">
															<Bot size={14} class="text-text-muted mt-0.5" />
															<div>
																<div class="text-xs text-text-muted">Model</div>
																<div class="text-sm font-mono text-text-primary">{override.model.name}</div>
															</div>
														</div>
													{/if}

													{#if override.prompt_placeholder_map && Object.keys(override.prompt_placeholder_map).length > 0}
														<div class="flex items-start gap-2">
															<Copy size={14} class="text-text-muted mt-0.5" />
															<div class="flex-1">
																<div class="text-xs text-text-muted mb-1">Placeholder Mappings</div>
																<div class="space-y-1">
																	{#each Object.entries(override.prompt_placeholder_map) as [key, value]}
																		<div class="flex items-center gap-2 text-xs">
																			<code class="px-1.5 py-0.5 bg-surface-secondary rounded text-[#7661FF] dark:text-[#BF71F2]">{key}</code>
																			<ArrowRight size={12} class="text-text-muted" />
																			<code class="px-1.5 py-0.5 bg-surface-secondary rounded text-text-secondary">{value}</code>
																		</div>
																	{/each}
																</div>
															</div>
														</div>
													{/if}

													{#if override.pre_process}
														<div class="flex items-start gap-2">
															<Code size={14} class="text-text-muted mt-0.5" />
															<div>
																<div class="text-xs text-text-muted">Pre-process</div>
																<div class="text-xs font-mono text-text-primary">{override.pre_process}</div>
															</div>
														</div>
													{/if}

													{#if override.post_process}
														<div class="flex items-start gap-2">
															<Code size={14} class="text-text-muted mt-0.5" />
															<div>
																<div class="text-xs text-text-muted">Post-process</div>
																<div class="text-xs font-mono text-text-primary">{override.post_process}</div>
															</div>
														</div>
													{/if}

													{#if !override.model && !override.prompt_placeholder_map && !override.pre_process && !override.post_process}
														<div class="text-xs text-text-muted italic">
															Override exists but no specific configurations set.
														</div>
													{/if}
												</div>
											{/if}
										{:else}
											<!-- No override - show add prompt -->
											<div class="py-4 text-center">
												{#if isEditing}
													<button
														onclick={() => addOverrideForNode(innerNode.id)}
														class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#7661FF] hover:text-[#5a4dcc] bg-[#7661FF]/15 hover:bg-[#7661FF]/25 dark:bg-[#7661FF]/20 dark:hover:bg-[#7661FF]/30 dark:text-[#BF71F2] rounded-lg transition-colors"
													>
														<Plus size={16} />
														Add Configuration Override
													</button>
												{:else}
													<div class="text-xs text-text-muted">
														No overrides configured for this node.
														<br />
														<span class="text-text-muted">Click Edit to add overrides.</span>
													</div>
												{/if}
											</div>
										{/if}
									</div>
								{/if}
							</div>
						{/each}

						{#if filteredInnerNodes().length === 0}
							<div class="text-center py-8 text-text-muted text-sm">
								{#if overrideSearchQuery}
									No inner nodes match "{overrideSearchQuery}"
								{:else}
									No inner nodes available
								{/if}
							</div>
						{/if}
					</div>

					<!-- Summary footer -->
					{#if overrideCount > 0}
						<div class="p-3 bg-warning-light dark:bg-warning/20 border border-warning-border dark:border-warning/40 rounded-lg">
							<div class="flex items-center gap-2 text-xs text-warning dark:text-warning">
								<Wrench size={14} />
								<span><strong>{overrideCount}</strong> node{overrideCount !== 1 ? 's' : ''} with configuration overrides</span>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			<!-- Settings Tab -->
			{#if activeTab === 'settings'}
				<div class="space-y-4">
					<!-- Node Configuration Overview -->
					<div class="p-3 bg-surface-secondary rounded-lg border border-surface-border">
						<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
							Configuration Overview
						</div>
						<div class="grid grid-cols-2 gap-2 text-xs">
							<div class="flex justify-between p-2 bg-surface rounded">
								<span class="text-text-muted">Node Type</span>
								<span class="font-medium text-text-primary">{node.node_type}</span>
							</div>
							<div class="flex justify-between p-2 bg-surface rounded">
								<span class="text-text-muted">Node ID</span>
								<span class="font-mono text-text-primary truncate max-w-[120px]" title={node.id}>{node.id}</span>
							</div>
							{#if node.model?.name}
								<div class="flex justify-between p-2 bg-surface rounded">
									<span class="text-text-muted">Model</span>
									<span class="font-medium text-[#7661FF] dark:text-[#BF71F2]">{node.model.name}</span>
								</div>
							{/if}
							{#if node.model?.provider}
								<div class="flex justify-between p-2 bg-surface rounded">
									<span class="text-text-muted">Provider</span>
									<span class="text-text-primary">{node.model.provider}</span>
								</div>
							{/if}
							{#if node.tools && node.tools.length > 0}
								<div class="flex justify-between p-2 bg-surface rounded">
									<span class="text-text-muted">Tools</span>
									<span class="text-text-primary">{node.tools.length} configured</span>
								</div>
							{/if}
							{#if node.tool_choice}
								<div class="flex justify-between p-2 bg-surface rounded">
									<span class="text-text-muted">Tool Choice</span>
									<span class="text-text-primary">{node.tool_choice}</span>
								</div>
							{/if}
							{#if node.pre_process}
								<div class="flex justify-between p-2 bg-surface rounded col-span-2">
									<span class="text-text-muted">Pre-processor</span>
									<span class="font-mono text-xs text-text-primary truncate max-w-[200px]" title={node.pre_process}>{node.pre_process}</span>
								</div>
							{/if}
							{#if node.post_process}
								<div class="flex justify-between p-2 bg-surface rounded col-span-2">
									<span class="text-text-muted">Post-processor</span>
									<span class="font-mono text-xs text-text-primary truncate max-w-[200px]" title={node.post_process}>{node.post_process}</span>
								</div>
							{/if}
							{#if node.function_path}
								<div class="flex justify-between p-2 bg-surface rounded col-span-2">
									<span class="text-text-muted">Function Path</span>
									<span class="font-mono text-xs text-text-primary truncate max-w-[200px]" title={node.function_path}>{node.function_path}</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Execution State (if available) -->
					{#if nodeState}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
								Execution State
							</div>
							<div class="p-3 rounded-lg border {nodeState.status === 'completed' ? 'bg-success-light dark:bg-success/20 border-success-border dark:border-success/40' : nodeState.status === 'error' ? 'bg-error-light dark:bg-error/20 border-error-border dark:border-error/40' : nodeState.status === 'running' ? 'bg-info-light dark:bg-info/20 border-info-border dark:border-info/40' : 'bg-surface-secondary border-surface-border'}">
								<div class="flex items-center justify-between mb-2">
									<span class="text-xs font-medium {nodeState.status === 'completed' ? 'text-success dark:text-success' : nodeState.status === 'error' ? 'text-error dark:text-error' : nodeState.status === 'running' ? 'text-info dark:text-info' : 'text-text-secondary'}">
										{nodeState.status?.toUpperCase() ?? 'UNKNOWN'}
									</span>
									{#if nodeState.duration_ms}
										<span class="text-xs text-text-muted">{nodeState.duration_ms}ms</span>
									{/if}
								</div>
								{#if nodeState.error}
									<div class="text-xs text-error font-mono bg-error-light dark:bg-error/20 p-2 rounded mt-2">
										{nodeState.error}
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Model Parameters (for LLM nodes) -->
					{#if node.node_type === 'llm'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
									Model Parameters
								</div>
								{#if isEditing}
									<button
										onclick={addModelParameter}
										class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-[#7661FF] hover:text-[#5a4dcc] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 rounded transition-colors"
									>
										<Plus size={12} />
										Add
									</button>
								{/if}
							</div>

							{#if isEditing}
								<div class="space-y-2">
									{#each Object.entries(editModelParameters) as [key, value]}
										<div class="flex items-center gap-2 p-2 bg-surface-secondary rounded-lg">
											<input
												type="text"
												value={key}
												onblur={(e) => renameModelParameter(key, e.currentTarget.value)}
												class="flex-1 px-2 py-1 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
												placeholder="Parameter name"
											/>
											<input
												type="text"
												value={typeof value === 'object' ? JSON.stringify(value) : String(value)}
												oninput={(e) => updateModelParameter(key, parseParameterValue(e.currentTarget.value))}
												class="flex-1 px-2 py-1 text-xs font-mono border border-surface-border rounded bg-surface text-text-primary"
												placeholder="Value"
											/>
											<button
												onclick={() => removeModelParameter(key)}
												class="p-1 text-text-muted hover:text-error transition-colors"
											>
												<Trash2 size={14} />
											</button>
										</div>
									{/each}

									{#if Object.keys(editModelParameters).length === 0}
										<div class="text-center py-4 text-text-muted text-sm border border-dashed border-surface-border rounded-lg">
											No parameters. Click "Add" to add one.
										</div>
									{/if}
								</div>

								<!-- Common parameters quick-add -->
								<div class="mt-3 pt-3 border-t border-surface-border">
									<div class="text-xs text-text-muted mb-2">Quick add common parameters:</div>
									<div class="flex flex-wrap gap-1">
										{#each ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty'] as param}
											{#if !editModelParameters[param]}
												<button
													onclick={() => { editModelParameters[param] = param === 'temperature' ? 0.7 : param === 'max_tokens' ? 1024 : 0; editModelParameters = {...editModelParameters}; markChanged(); }}
													class="px-2 py-0.5 text-xs bg-surface-secondary hover:bg-surface-hover rounded text-text-secondary transition-colors"
												>
													+ {param}
												</button>
											{/if}
										{/each}
									</div>
								</div>
							{:else}
								<div class="space-y-2">
									{#each Object.entries(node.model?.parameters ?? {}) as [key, value]}
										<div class="flex items-center justify-between text-sm p-2 bg-surface-secondary rounded">
											<span class="text-text-secondary font-medium">{key}</span>
											<span class="font-mono text-text-primary">
												{typeof value === 'object' ? JSON.stringify(value) : value}
											</span>
										</div>
									{/each}

									{#if !node.model?.parameters || Object.keys(node.model.parameters).length === 0}
										<div class="text-center py-4 text-text-muted text-sm">
											No parameters configured
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Structured Output (for LLM/Agent nodes) -->
					{#if node.node_type === 'llm' || node.node_type === 'agent'}
						<div class="border-t border-surface-border pt-4 mt-4">
							<div class="flex items-center justify-between mb-3">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider flex items-center gap-1.5">
									<Code size={12} />
									Structured Output
								</div>
								{#if isEditing}
									<label class="flex items-center gap-2 cursor-pointer">
										<input
											type="checkbox"
											bind:checked={editStructuredOutputEnabled}
											onchange={() => markChanged()}
											class="w-4 h-4 text-[#7661FF] border-surface-border rounded focus:ring-info"
										/>
										<span class="text-xs text-text-secondary">Enable</span>
									</label>
								{:else}
									<span class="text-xs px-2 py-0.5 rounded {node.model?.structured_output?.enabled ? 'bg-success-light text-status-completed' : 'bg-surface-secondary text-text-muted'}">
										{node.model?.structured_output?.enabled ? 'Enabled' : 'Disabled'}
									</span>
								{/if}
							</div>

							{#if isEditing && editStructuredOutputEnabled}
								<!-- Schema Mode Toggle -->
								<div class="mb-4">
									<span class="text-xs font-medium text-text-muted uppercase tracking-wider block mb-2">
										Schema Type
									</span>
									<div class="inline-flex rounded-lg border border-surface-border p-1 bg-surface-secondary">
										<button
											type="button"
											onclick={() => { editSchemaMode = 'inline'; markChanged(); }}
											class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {editSchemaMode === 'inline' ? 'bg-surface text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}"
										>
											Inline Schema
										</button>
										<button
											type="button"
											onclick={() => { editSchemaMode = 'class_path'; markChanged(); }}
											class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors {editSchemaMode === 'class_path' ? 'bg-surface text-text-primary shadow-sm' : 'text-text-muted hover:text-text-secondary'}"
										>
											Class Path
										</button>
									</div>
								</div>

								{#if editSchemaMode === 'inline'}
									<!-- Inline Schema Fields -->
									<div class="mb-4">
										<div class="flex items-center justify-between mb-3">
											<span class="text-xs font-medium text-text-muted uppercase tracking-wider">
												Output Fields
											</span>
											<button
												onclick={addSchemaField}
												class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 rounded-md transition-colors"
											>
												<Plus size={14} />
												Add Field
											</button>
										</div>

										{#if editSchemaFields.length === 0}
											<div class="text-center py-8 border-2 border-dashed border-surface-border rounded-lg">
												<Code size={28} class="mx-auto mb-2 text-text-muted" />
												<p class="text-sm text-text-muted mb-1">No fields defined</p>
												<p class="text-xs text-text-muted dark:text-text-muted">Click "Add Field" to define output schema</p>
											</div>
										{:else}
											<div class="space-y-2">
												{#each editSchemaFields as field (field.id)}
													<div class="flex items-start gap-3 p-3 bg-surface rounded-lg border border-surface-border group hover:border-[#7661FF]/50 dark:hover:border-[#7661FF]/60 transition-colors">
														<!-- Type Icon -->
														<div class="w-8 h-8 rounded-md bg-[#7661FF]/15 dark:bg-[#7661FF]/20 flex items-center justify-center flex-shrink-0">
															<Code size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
														</div>
														<!-- Field Content -->
														<div class="flex-1 min-w-0 space-y-2">
															<!-- Name & Type Row -->
															<div class="flex items-center gap-2">
																<input
																	type="text"
																	value={field.name}
																	oninput={(e) => updateSchemaField(field.id, 'name', e.currentTarget.value)}
																	placeholder="field_name"
																	class="flex-1 px-2 py-1.5 text-sm font-mono border border-surface-border rounded-md bg-surface-secondary text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
																/>
																<div class="w-24">
																	<CustomSelect
																		options={schemaFieldTypeOptions}
																		value={field.type}
																		compact={true}
																		searchable={false}
																		onchange={(val) => updateSchemaField(field.id, 'type', val)}
																	/>
																</div>
															</div>
															<!-- Description -->
															<input
																type="text"
																value={field.description}
																oninput={(e) => updateSchemaField(field.id, 'description', e.currentTarget.value)}
																placeholder="Field description (optional)"
																class="w-full px-2 py-1.5 text-xs border border-surface-border rounded-md bg-surface-secondary text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
															/>
															<!-- Default Value -->
															<div class="flex items-center gap-2">
																<label class="flex items-center gap-1.5 cursor-pointer">
																	<input
																		type="checkbox"
																		checked={field.hasDefault}
																		onchange={(e) => updateSchemaField(field.id, 'hasDefault', e.currentTarget.checked)}
																		class="w-3.5 h-3.5 text-[#7661FF] border-surface-border rounded focus:ring-info"
																	/>
																	<span class="text-xs text-text-muted">Default value</span>
																</label>
																{#if field.hasDefault}
																	<input
																		type="text"
																		value={field.default}
																		oninput={(e) => updateSchemaField(field.id, 'default', e.currentTarget.value)}
																		placeholder="Enter default"
																		class="flex-1 px-2 py-1 text-xs font-mono border border-surface-border rounded-md bg-surface-secondary text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
																	/>
																{/if}
															</div>
														</div>
														<!-- Delete Button -->
														<button
															onclick={() => removeSchemaField(field.id)}
															class="p-1.5 text-text-muted hover:text-error hover:bg-error-light dark:hover:bg-error/20 rounded-md transition-colors opacity-0 group-hover:opacity-100"
															title="Remove field"
														>
															<X size={14} />
														</button>
													</div>
												{/each}
											</div>
										{/if}
									</div>
								{:else}
									<!-- Class Path Input -->
									<div class="mb-4">
										<span class="text-xs font-medium text-text-muted uppercase tracking-wider block mb-2">
											Class Path
										</span>
										<div class="flex items-start gap-3 p-3 bg-surface rounded-lg border border-surface-border">
											<div class="w-8 h-8 rounded-md bg-[#7661FF]/15 dark:bg-[#7661FF]/20 flex items-center justify-center flex-shrink-0">
												<Code size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
											</div>
											<div class="flex-1 min-w-0 space-y-2">
												<input
													type="text"
													bind:value={editSchemaClassPath}
													oninput={() => markChanged()}
													placeholder="module.path.ClassName"
													class="w-full px-2 py-1.5 text-sm font-mono border border-surface-border rounded-md bg-surface-secondary text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
												/>
												<p class="text-xs text-text-muted dark:text-text-muted">
													e.g., sygra.core.models.structured_output.schemas_factory.SimpleResponse
												</p>
											</div>
										</div>
									</div>
								{/if}

								<!-- Schema Preview Button -->
								<div class="mb-4">
									<button
										onclick={() => showSchemaPreview = !showSchemaPreview}
										class="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] hover:bg-[#7661FF]/10 dark:hover:bg-[#7661FF]/15 rounded-md transition-colors"
									>
										{#if showSchemaPreview}
											<EyeOff size={14} />
											Hide Preview
										{:else}
											<Eye size={14} />
											Preview JSON Schema
										{/if}
									</button>
									{#if showSchemaPreview}
										<pre class="mt-2 p-3 text-xs font-mono bg-brand-primary text-brand-accent rounded-lg overflow-auto max-h-48 border border-surface-border">{generateSchemaPreview()}</pre>
									{/if}
								</div>

								<!-- Advanced Options (collapsible) -->
								<details class="group border border-surface-border rounded-lg overflow-hidden">
									<summary class="flex items-center gap-2 cursor-pointer px-3 py-2.5 text-xs font-medium text-text-secondary hover:bg-surface-hover transition-colors">
										<ChevronRight size={14} class="transition-transform group-open:rotate-90" />
										Advanced Options
									</summary>
									<div class="px-3 pb-3 pt-2 space-y-3 bg-surface-secondary/50 border-t border-surface-border">
										<!-- Fallback Strategy -->
										<div>
											<label class="text-xs text-text-muted block mb-1.5">Fallback Strategy</label>
											<CustomSelect
												options={fallbackStrategyOptions}
												bind:value={editFallbackStrategy}
												searchable={false}
												onchange={markChanged}
											/>
										</div>
										<!-- Retry on Parse Error -->
										<div class="flex items-center justify-between py-1">
											<label class="text-xs text-text-secondary">Retry on Parse Error</label>
											<input
												type="checkbox"
												bind:checked={editRetryOnParseError}
												onchange={() => markChanged()}
												class="w-4 h-4 text-[#7661FF] border-surface-border rounded focus:ring-info"
											/>
										</div>
										<!-- Max Retries -->
										<div class="flex items-center justify-between py-1">
											<label class="text-xs text-text-secondary">Max Parse Retries</label>
											<input
												type="number"
												bind:value={editMaxParseRetries}
												oninput={() => markChanged()}
												min="0"
												max="10"
												class="w-16 px-2 py-1 text-xs border border-surface-border rounded-md bg-surface text-text-primary focus:ring-2 focus:ring-info focus:border-transparent"
											/>
										</div>
									</div>
								</details>
							{:else if !isEditing && node.model?.structured_output?.enabled}
								<!-- View Mode - Show configured schema -->
								<div class="space-y-3">
									{#if typeof node.model.structured_output.schema === 'string'}
										<div class="flex items-start gap-3 p-3 bg-surface rounded-lg border border-surface-border">
											<div class="w-8 h-8 rounded-md bg-[#7661FF]/15 dark:bg-[#7661FF]/20 flex items-center justify-center flex-shrink-0">
												<Code size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
											</div>
											<div class="flex-1 min-w-0">
												<div class="text-xs text-text-muted mb-1">Class Path</div>
												<div class="font-mono text-sm text-text-primary break-all">{node.model.structured_output.schema}</div>
											</div>
										</div>
									{:else if node.model.structured_output.schema?.fields}
										<div class="space-y-2">
											<span class="text-xs font-medium text-text-muted uppercase tracking-wider">
												Output Fields
											</span>
											<div class="space-y-2">
												{#each Object.entries(node.model.structured_output.schema.fields) as [fieldName, fieldDef]}
													<div class="flex items-start gap-3 p-3 bg-surface rounded-lg border border-surface-border">
														<div class="w-8 h-8 rounded-md bg-[#7661FF]/15 dark:bg-[#7661FF]/20 flex items-center justify-center flex-shrink-0">
															<Code size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
														</div>
														<div class="flex-1 min-w-0">
															<div class="flex items-center gap-2 mb-1">
																<span class="font-mono text-sm font-medium text-text-primary">{fieldName}</span>
																<span class="px-1.5 py-0.5 text-xs rounded bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#BF71F2]">{fieldDef.type}</span>
															</div>
															{#if fieldDef.description}
																<div class="text-xs text-text-muted">{fieldDef.description}</div>
															{/if}
															{#if fieldDef.default !== undefined}
																<div class="text-xs text-text-muted dark:text-text-muted mt-1">
																	Default: <span class="font-mono">{JSON.stringify(fieldDef.default)}</span>
																</div>
															{/if}
														</div>
													</div>
												{/each}
											</div>
										</div>
									{/if}
									{#if node.model.structured_output.fallback_strategy}
										<div class="flex items-center gap-2 p-2 bg-surface-secondary rounded-lg text-xs">
											<span class="text-text-muted">Fallback Strategy:</span>
											<span class="font-medium text-text-secondary capitalize">{node.model.structured_output.fallback_strategy}</span>
										</div>
									{/if}
								</div>
							{:else if !isEditing}
								<div class="text-center py-6 text-text-muted dark:text-text-muted text-sm">
									Structured output not configured
								</div>
							{/if}
						</div>
					{/if}

					<!-- Data Source Config (for data nodes) -->
					{#if node.node_type === 'data' && node.data_source}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
								Data Source Configuration
							</div>
							<div class="space-y-2 text-xs">
								{#if node.data_source.source_type}
									<div class="flex justify-between p-2 bg-surface-secondary rounded">
										<span class="text-text-muted">Source Type</span>
										<span class="font-medium text-text-primary">{node.data_source.source_type}</span>
									</div>
								{/if}
								{#if node.data_source.repo_id}
									<div class="flex justify-between p-2 bg-surface-secondary rounded">
										<span class="text-text-muted">Repository</span>
										<span class="font-mono text-text-primary">{node.data_source.repo_id}</span>
									</div>
								{/if}
								{#if node.data_source.file_path}
									<div class="flex justify-between p-2 bg-surface-secondary rounded">
										<span class="text-text-muted">File Path</span>
										<span class="font-mono text-text-primary">{node.data_source.file_path}</span>
									</div>
								{/if}
								{#if node.data_source.split}
									<div class="flex justify-between p-2 bg-surface-secondary rounded">
										<span class="text-text-muted">Split</span>
										<span class="text-text-primary">{node.data_source.split}</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Subgraph Config -->
					{#if node.node_type === 'subgraph' && node.subgraph}
						<div>
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">
								Subgraph Configuration
							</div>
							<div class="space-y-2 text-xs">
								<div class="flex justify-between p-2 bg-surface-secondary rounded">
									<span class="text-text-muted">Subgraph Path</span>
									<span class="font-mono text-text-primary truncate max-w-[200px]" title={node.subgraph}>{node.subgraph}</span>
								</div>
								{#if node.node_config_map && Object.keys(node.node_config_map).length > 0}
									<div class="flex justify-between p-2 bg-surface-secondary rounded">
										<span class="text-text-muted">Overrides</span>
										<span class="text-text-primary">{Object.keys(node.node_config_map).length} nodes</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Metadata (expandable JSON) -->
					{#if node.metadata && Object.keys(node.metadata).length > 0}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
									Metadata
								</div>
								<span class="text-xs text-text-muted">{Object.keys(node.metadata).length} fields</span>
							</div>
							<details class="group">
								<summary class="cursor-pointer text-xs text-[#7661FF] dark:text-[#BF71F2] hover:text-[#5a4dcc] dark:hover:text-[#d49af7]">
									View full metadata
								</summary>
								<div class="mt-2 text-sm font-mono bg-surface-secondary px-3 py-2 rounded-lg overflow-x-auto max-h-64">
									<pre class="text-text-primary text-xs">{JSON.stringify(node.metadata, null, 2)}</pre>
								</div>
							</details>
						</div>
					{/if}

					<!-- Full Node Configuration (expandable) -->
					<div>
						<div class="flex items-center justify-between mb-2">
							<div class="text-xs font-medium text-text-muted uppercase tracking-wider">
								Full Configuration
							</div>
						</div>
						<details class="group">
							<summary class="cursor-pointer text-xs text-[#7661FF] dark:text-[#BF71F2] hover:text-[#5a4dcc] dark:hover:text-[#d49af7]">
								View raw node configuration (JSON)
							</summary>
							<div class="mt-2 text-sm font-mono bg-brand-primary px-3 py-2 rounded-lg overflow-x-auto max-h-80">
								<pre class="text-success text-xs">{JSON.stringify(node, null, 2)}</pre>
							</div>
						</details>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</aside>

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmModal
		title="Delete Node"
		message={`Are you sure you want to delete "${node?.summary || node?.id}"? This will also remove all connected edges. This action cannot be undone.`}
		confirmText="Delete"
		cancelText="Cancel"
		variant="danger"
		on:confirm={confirmDeleteNode}
		on:cancel={cancelDeleteNode}
	/>
{/if}

<!-- Tool Picker Modal -->
{#if showToolPicker}
	<ToolPickerModal
		existingTools={editTools}
		on:select={(e) => {
			const { importPath } = e.detail;
			if (importPath && !editTools.includes(importPath)) {
				editTools = [...editTools, importPath];
				markChanged();
			}
			showToolPicker = false;
		}}
		on:cancel={() => showToolPicker = false}
	/>
{/if}
