<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { X, Bot, Zap, Link, Play, Square, Globe, Boxes, Save, ChevronDown, ChevronRight, Code, Settings, MessageSquare, Info, GitBranch, Plus, Trash2, Edit3, GripVertical, Database, Download, Cloud, Server, HardDrive, ArrowRight, Map, Shuffle, Wrench, AlertCircle, Library, Eye, EyeOff, Loader2, Layers, Copy } from 'lucide-svelte';
	import { workflowStore, type WorkflowNode, type NodeExecutionState, type PromptMessage, type NodeConfigOverride, type InnerGraph } from '$lib/stores/workflow.svelte';
	import { toolStore } from '$lib/stores/tool.svelte';
	import { panelStore } from '$lib/stores/panel.svelte';
	import MonacoEditor from '$lib/components/editor/LazyMonacoEditor.svelte';
	import ConfirmModal from '$lib/components/common/ConfirmModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';
	import ToolPickerModal from '$lib/components/builder/ToolPickerModal.svelte';
	import PanelHeader from '$lib/components/panel/PanelHeader.svelte';
	import PanelTabs from '$lib/components/panel/PanelTabs.svelte';
	import PanelSection from '$lib/components/panel/PanelSection.svelte';
	import ConnectionPreview from '$lib/components/panel/ConnectionPreview.svelte';

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
	type TabId = 'details' | 'prompt' | 'tools' | 'code' | 'overrides' | 'settings';
	let activeTab = $state<TabId>('details');

	// Edit state
	let isEditing = $state(false);
	let isSaving = $state(false);
	let hasChanges = $state(false);

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

	// Data transformations edit state
	let editTransformations = $state<Array<{ transform: string; params: string }>>([]);
	let editTransformCode = $state('');

	// Output node edit state
	let editOutputGenerator = $state('');
	let editOutputGeneratorCode = $state('');
	let editOutputMappings = $state<Array<{ key: string; from: string; value: string; transform: string }>>([]);

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

	// Data preview state (for data nodes)
	let showDataPreview = $state(false);
	let dataPreviewLoading = $state(false);
	let dataPreviewData = $state<{ records: unknown[]; total: number | string | null; message: string | null } | null>(null);
	let expandedPreviewRows = $state<Set<number>>(new Set());

	// Subgraph node_config_map edit state
	let editNodeConfigMap = $state<Record<string, NodeConfigOverride>>({});
	let expandedOverrideNodes = $state<Set<string>>(new Set());
	let overrideSearchQuery = $state('');

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

	// Fetch sample data from API for data node preview
	async function fetchDataPreview() {
		const workflowId = workflowStore.currentWorkflow?.id;
		if (!workflowId || dataPreviewLoading) return;

		dataPreviewLoading = true;
		dataPreviewData = null;

		try {
			const response = await fetch(`/api/workflows/${encodeURIComponent(workflowId)}/sample-data?limit=5`);
			if (response.ok) {
				dataPreviewData = await response.json();
			} else {
				const errorText = await response.text();
				dataPreviewData = { records: [], total: 0, message: `Error: ${errorText.substring(0, 100)}` };
			}
		} catch (error) {
			dataPreviewData = { records: [], total: 0, message: `Network error: ${error instanceof Error ? error.message : String(error)}` };
		} finally {
			dataPreviewLoading = false;
		}
	}

	function togglePreviewRowExpand(index: number) {
		if (expandedPreviewRows.has(index)) {
			expandedPreviewRows.delete(index);
			expandedPreviewRows = new Set(expandedPreviewRows);
		} else {
			expandedPreviewRows.add(index);
			expandedPreviewRows = new Set(expandedPreviewRows);
		}
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
		branch: GitBranch
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
		branch: '#eab308'
	};

	let Icon = $derived(icons[node?.node_type ?? 'llm'] ?? Bot);
	let color = $derived(colors[node?.node_type ?? 'llm'] ?? '#8b5cf6');

	// Determine which tabs to show based on node type
	let showPromptTab = $derived(node?.node_type === 'llm' || node?.node_type === 'agent');
	let showToolsTab = $derived(node?.node_type === 'llm' || node?.node_type === 'agent');
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
		{ id: 'tools', label: 'Tools', icon: Wrench, badge: editTools.length || undefined, hidden: !showToolsTab },
		{ id: 'code', label: 'Code', icon: Code, hidden: !showCodeTab },
		{ id: 'overrides', label: 'Overrides', icon: Layers, badge: overrideCount || undefined, hidden: !showOverridesTab },
		{ id: 'settings', label: 'Settings', icon: Settings, hidden: false }
	]);

	// Handle tab change
	function handleTabChange(tabId: string) {
		activeTab = tabId as TabId;
		if (node?.node_type) {
			panelStore.setLastTab(node.node_type, tabId);
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

	// Fetch code content from backend
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

	// Track code load errors for debugging
	let codeLoadError = $state<string | null>(null);

	// Load existing code from files
	async function loadExistingCode() {
		if (!node || !currentWorkflow) return;

		isLoadingCode = true;
		codeLoadError = null;
		preProcessCodeLoaded = false;
		postProcessCodeLoaded = false;
		lambdaCodeLoaded = false;

		console.log('loadExistingCode: Starting for node', node.id, {
			pre_process: node.pre_process,
			post_process: node.post_process,
			function_path: node.function_path,
			workflow_id: currentWorkflow.id
		});

		try {
			// Fetch pre-process code if path exists
			if (node.pre_process) {
				console.log('Fetching pre_process:', node.pre_process);
				const content = await fetchCodeContent(node.pre_process, currentWorkflow.id);
				console.log('pre_process result:', content ? 'loaded' : 'failed');
				if (content) {
					preProcessCode = content;
					preProcessCodeLoaded = true;
				}
			}

			// Fetch post-process code if path exists
			if (node.post_process) {
				console.log('Fetching post_process:', node.post_process);
				const content = await fetchCodeContent(node.post_process, currentWorkflow.id);
				console.log('post_process result:', content ? `loaded (${content.length} chars)` : 'failed');
				if (content) {
					postProcessCode = content;
					postProcessCodeLoaded = true;
				} else {
					codeLoadError = `Failed to load post_process from ${node.post_process}`;
				}
			}

			// Fetch lambda function code if path exists
			if (node.function_path && node.node_type === 'lambda') {
				console.log('Fetching function_path:', node.function_path);
				const content = await fetchCodeContent(node.function_path, currentWorkflow.id);
				console.log('function_path result:', content ? 'loaded' : 'failed');
				if (content) {
					lambdaCode = content;
					lambdaCodeLoaded = true;
				}
			}
		} catch (e) {
			console.error('loadExistingCode error:', e);
			codeLoadError = e instanceof Error ? e.message : 'Unknown error loading code';
		} finally {
			isLoadingCode = false;
			console.log('loadExistingCode: Complete', { preProcessCodeLoaded, postProcessCodeLoaded, lambdaCodeLoaded });
		}
	}

	// Initialize edit state when node changes
	$effect(() => {
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
from typing import Any
from sygra.core.graph.sygra_state import SygraState


def ${nodeClassName}_function(state: SygraState) -> Any:
    """Execute custom logic on workflow state.

    Args:
        state: Current workflow state containing all variables

    Returns:
        Any: Result to be stored in state
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

			// Try to load existing code from files first, use stubs as fallback
			if (node.pre_process || node.post_process || node.function_path) {
				loadExistingCode().then(() => {
					// After loading, set stubs only for code that wasn't loaded
					if (!preProcessCodeLoaded) {
						preProcessCode = generatePreProcessStub();
					}
					if (!postProcessCodeLoaded) {
						postProcessCode = generatePostProcessStub();
					}
					if (!lambdaCodeLoaded) {
						lambdaCode = generateLambdaStub();
					}
				});
			} else {
				// No code paths configured, use stubs immediately
				preProcessCode = generatePreProcessStub();
				postProcessCode = generatePostProcessStub();
				lambdaCode = generateLambdaStub();
			}

			// Always set branch stub (loaded separately if needed)
			branchConditionCode = generateBranchStub();

			// Initialize data node edit state
			if (node.node_type === 'data') {
				// Always set default transformation stub code
				const dataClassName = (node.id || 'Data').replace(/-/g, '_').replace(/\s+/g, '').replace(/[^a-zA-Z0-9_]/g, '');
				editTransformCode = `"""Data transformation for ${node.summary || node.id}."""
from typing import Any, Dict


class ${dataClassName}Transform:
    """Transform data records during processing.

    This class is called for each record in the data source.
    Implement the transform method to modify records.
    """

    def __init__(self, **params):
        """Initialize with optional parameters from config."""
        self.params = params

    def transform(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single data record.

        Args:
            record: Input data record from source

        Returns:
            Dict[str, Any]: Transformed record
        """
        # Example transformations:
        #
        # Add new fields:
        # record["new_field"] = compute_value(record["existing_field"])
        #
        # Rename fields:
        # record["new_name"] = record.pop("old_name", None)
        #
        # Filter fields:
        # return {k: v for k, v in record.items() if k in ["field1", "field2"]}
        #
        # Type conversions:
        # record["count"] = int(record.get("count", 0))

        return record
`;

				// Also load existing config if present
				if (node.data_config) {
					const src = Array.isArray(node.data_config.source) ? node.data_config.source[0] : node.data_config.source;
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
					const sink = Array.isArray(node.data_config.sink) ? node.data_config.sink[0] : node.data_config.sink;
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
				}
			}

			// Initialize output node edit state - always set stub code
			if (node.node_type === 'output') {
				// Always set default generator stub code
				const outputClassName = (node.id || 'Output').replace(/-/g, '_').replace(/\s+/g, '').replace(/[^a-zA-Z0-9_]/g, '');
				editOutputGeneratorCode = `"""Output generator for ${node.summary || node.id}."""
from typing import Any, Dict, List
from sygra.core.graph.sygra_state import SygraState
from sygra.processors.output_record_generator import BaseOutputGenerator
from sygra.utils import utils


class ${outputClassName}OutputGenerator(BaseOutputGenerator):
    """Generate output records from workflow state.

    Inherits from BaseOutputGenerator which handles output_map resolution.
    Define custom transform methods referenced in output_map config.
    """

    def generate(self, state: SygraState) -> Dict[str, Any]:
        """Generate the final output record.

        Args:
            state: Current workflow state with all variables

        Returns:
            Dict[str, Any]: The final output record
        """
        # Default: Use parent class to resolve output_map
        return super().generate(state)

    # Custom transform methods (referenced in output_map "transform" field)
    # The method name must match the transform name in config

    def build_conversation(self, data: Any, state: SygraState) -> List[Dict]:
        """Example transform: Convert messages to chat format.

        Args:
            data: The data from 'from' or 'value' in output_map
            state: Current workflow state

        Returns:
            Transformed data
        """
        # Example: Convert LangChain messages to chat format
        # chat_messages = utils.convert_messages_from_langchain_to_chat_format(data)
        # chat_messages.insert(0, {"role": "user", "content": state["question"]})
        # return chat_messages

        return data

    def format_output(self, data: Any, state: SygraState) -> str:
        """Example transform: Format data as string.

        Args:
            data: The data to format
            state: Current workflow state

        Returns:
            Formatted string
        """
        return str(data)
`;

				// Also load existing config if present
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
			// Reset node_config_map for subgraph nodes
			editNodeConfigMap = node.node_config_map ? JSON.parse(JSON.stringify(node.node_config_map)) : {};
			expandedOverrideNodes = new Set();
			overrideSearchQuery = '';
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
		if (editModel !== (node.model?.name ?? '') || JSON.stringify(editModelParameters) !== JSON.stringify(node.model?.parameters ?? {})) {
			updates.model = { name: editModel, parameters: editModelParameters };
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
		}

		// Handle output_keys updates for LLM/Agent/Lambda/Branch nodes
		if (['llm', 'agent', 'lambda', 'branch'].includes(node.node_type)) {
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

		// Handle data node config updates
		if (node.node_type === 'data') {
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

			const dataConfig: any = { source };

			// Include sink if configured based on type
			const hasSinkConfig = editSinkType === 'disk' ? editSinkFilePath :
				editSinkType === 'hf' ? editSinkRepoId :
				editSinkType === 'servicenow' ? editSinkTable : false;

			if (hasSinkConfig || editSinkAlias) {
				const sinkConfig: any = {
					alias: editSinkAlias || undefined,
					type: editSinkType
				};

				if (editSinkType === 'disk') {
					sinkConfig.file_path = editSinkFilePath;
				} else if (editSinkType === 'hf') {
					sinkConfig.repo_id = editSinkRepoId;
					if (editSinkSplit) sinkConfig.split = editSinkSplit;
				} else if (editSinkType === 'servicenow') {
					sinkConfig.table = editSinkTable;
					sinkConfig.operation = editSinkOperation;
				}

				dataConfig.sink = [sinkConfig];
			}

			// Include transformation code if present
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
			// Include generator code if present
			if (editOutputGeneratorCode && editOutputGeneratorCode.trim()) {
				outputConfig._generator_code = editOutputGeneratorCode;
			}
			if (editOutputMappings.length > 0) {
				outputConfig.output_map = {};
				editOutputMappings.forEach(m => {
					const mapping: any = {};
					if (m.from) mapping.from = m.from;
					if (m.value) {
						try { mapping.value = JSON.parse(m.value); } catch { mapping.value = m.value; }
					}
					if (m.transform) mapping.transform = m.transform;
					outputConfig.output_map[m.key] = mapping;
				});
			}
			updates.output_config = outputConfig;
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

		if (Object.keys(updates).length > 0) {
			const success = await workflowStore.updateNode(originalNodeId, updates);
			if (success) {
				hasChanges = false;
				isEditing = false;
				// Dispatch save event for parent to sync SvelteFlow
				// Include newId if the node ID was changed so parent can update selection
				console.log('[NodeDetailsPanel] Dispatching save event for node:', originalNodeId);
				dispatch('save', { nodeId: originalNodeId, newId: updates.newId, updates });
			} else {
				console.error('[NodeDetailsPanel] updateNode returned false');
			}
		} else {
			console.log('[NodeDetailsPanel] No updates to save');
			hasChanges = false;
			isEditing = false;
		}

		isSaving = false;
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
	class="fixed right-0 top-0 h-full border-l border-gray-200 dark:border-gray-800 bg-surface overflow-y-auto flex flex-col shadow-xl z-50"
	style="width: {panelWidth}px;"
>
	<!-- Resize handle -->
	<div
		class="absolute left-0 top-0 bottom-0 w-1 cursor-ew-resize hover:bg-violet-500/50 transition-colors z-20 group"
		onmousedown={handleResizeMouseDown}
		role="separator"
		aria-orientation="vertical"
	>
		<div class="absolute left-0 top-1/2 -translate-y-1/2 -translate-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
			<GripVertical size={12} class="text-gray-400" />
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
		showDelete={!!node && node.node_type !== 'start' && node.node_type !== 'end' && !isEditing}
		{onDuplicate}
		onDelete={requestDeleteNode}
		onClose={() => dispatch('close')}
	/>

	{#if node}
		<!-- Tabs -->
		<PanelTabs
			tabs={tabsConfig}
			{activeTab}
			onTabChange={handleTabChange}
		/>

		<!-- Tab Content -->
		<div class="flex-1 overflow-y-auto p-4">
			<!-- Details Tab -->
			{#if activeTab === 'details'}
				<div class="space-y-4">
					<!-- Skip ID/Summary/Description for data nodes - they don't need these fields -->
					{#if node.node_type !== 'data'}
						<!-- Node ID (editable) -->
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
								Node ID
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editNodeId}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
									placeholder="Enter node ID..."
								/>
								<p class="text-xs text-gray-400 mt-1">Use lowercase with underscores (e.g., my_node_id)</p>
							{:else}
								<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1.5 rounded">
									{node.id}
								</div>
							{/if}
						</div>

						<!-- Summary (editable) -->
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
								Summary
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editSummary}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
									placeholder="Enter node summary..."
								/>
							{:else}
								<div class="text-sm text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg">
									{node.summary || node.id}
								</div>
							{/if}
						</div>

						<!-- Description (editable) -->
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
								Description
							</div>
							{#if isEditing}
								<textarea
									bind:value={editDescription}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 resize-none"
									rows="3"
									placeholder="Enter node description..."
								></textarea>
							{:else if node.description}
								<div class="text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg">
									{node.description}
								</div>
							{:else}
								<div class="text-sm text-gray-400 italic">
									No description
								</div>
							{/if}
						</div>
					{/if}

					<!-- Connections section -->
					<PanelSection title="Connections" icon={ArrowRight} defaultOpen={true} collapsible={true}>
						<ConnectionPreview
							nodeId={node.id}
							nodes={workflowNodes}
							edges={workflowEdges}
							on:navigate={handleConnectionNavigate}
						/>
					</PanelSection>

					<!-- Model info (for LLM nodes) -->
					{#if node.node_type === 'llm'}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
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
								<div class="text-sm text-gray-800 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg">
									{node.model?.name ?? 'Not set'}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Output Keys (for LLM, Agent, Lambda, Branch nodes) -->
					{#if ['llm', 'agent', 'lambda', 'branch'].includes(node.node_type)}
						<div class="space-y-2">
							<div class="flex items-center justify-between">
								<div class="text-xs font-medium text-gray-500 uppercase tracking-wider flex items-center gap-1.5">
									<Download size={12} />
									Output Keys
								</div>
								<button
									type="button"
									class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
									title={"Output keys define the state variable name(s) where this node's output will be stored. Use {key_name} in downstream prompts to reference these values."}
								>
									<Info size={14} />
								</button>
							</div>

							<!-- Tags display -->
							<div class="flex flex-wrap gap-1.5 min-h-[28px]">
								{#if editOutputKeys.length > 0}
									{#each editOutputKeys as key}
										<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
											<code class="font-mono">{key}</code>
											{#if isEditing}
												<button
													type="button"
													onclick={() => removeOutputKey(key)}
													class="ml-0.5 hover:text-red-500 transition-colors"
													title="Remove key"
												>
													<X size={12} />
												</button>
											{/if}
										</span>
									{/each}
								{:else}
									<span class="text-xs text-gray-400 dark:text-gray-500 italic py-1">
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
										class="flex-1 px-3 py-1.5 text-sm font-mono border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
									/>
									<button
										type="button"
										onclick={addOutputKey}
										class="px-3 py-1.5 text-sm font-medium text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800 rounded-lg hover:bg-emerald-200 dark:hover:bg-emerald-900/50 transition-colors flex items-center gap-1"
									>
										<Plus size={14} />
										Add
									</button>
								</div>
								{#if outputKeyError}
									<p class="text-xs text-red-500 flex items-center gap-1">
										<AlertCircle size={12} />
										{outputKeyError}
									</p>
								{/if}
							{/if}

							<!-- Helper text -->
							<p class="text-xs text-gray-400 dark:text-gray-500">
								Use <code class="px-1 py-0.5 bg-gray-100 dark:bg-gray-800 rounded font-mono text-emerald-600 dark:text-emerald-400">{'{'}key_name{'}'}</code> in downstream prompts to reference output values.
							</p>
						</div>
					{/if}

					<!-- Lambda function path -->
					{#if node.node_type === 'lambda' && node.function_path}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
								Function Path
							</div>
							<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1.5 rounded break-all">
								{node.function_path}
							</div>
						</div>
					{/if}

					<!-- Subgraph path -->
					{#if node.node_type === 'subgraph' && node.subgraph_path}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
								Subgraph Path
							</div>
							<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1.5 rounded break-all">
								{node.subgraph_path}
							</div>
						</div>
					{/if}

					<!-- Data node config -->
					{#if node.node_type === 'data'}
						{@const sources = Array.isArray(node.data_config?.source) ? node.data_config.source : node.data_config?.source ? [node.data_config.source] : []}
						{@const sinks = Array.isArray(node.data_config?.sink) ? node.data_config.sink : node.data_config?.sink ? [node.data_config.sink] : []}
						<div class="space-y-4">
							<div class="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
								<Database size={14} />
								Data Configuration
							</div>

							{#if isEditing}
								<!-- Edit Mode: Source Configuration -->
								<div class="space-y-3 p-3 bg-violet-50 dark:bg-violet-900/20 rounded-lg border border-violet-200 dark:border-violet-800">
									<div class="flex items-center gap-2 text-xs font-medium text-violet-700 dark:text-violet-300">
										<Cloud size={12} />
										Source
									</div>

									<!-- Source Type Selector -->
									<div>
										<span class="block text-xs text-gray-500 mb-1.5">Type</span>
										<CustomSelect
											options={sourceTypeOptions}
											bind:value={editDataSourceType}
											placeholder="Select source type..."
											onchange={markChanged}
										/>
									</div>

									<!-- HuggingFace Fields -->
									{#if editDataSourceType === 'hf'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Repository ID *</span>
											<input
												type="text"
												bind:value={editDataRepoId}
												oninput={markChanged}
												placeholder="username/dataset-name"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div class="grid grid-cols-2 gap-3">
											<div>
												<span class="block text-xs text-gray-500 mb-1.5">Config</span>
												<input
													type="text"
													bind:value={editDataConfigName}
													oninput={markChanged}
													placeholder="default"
													class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
												/>
											</div>
											<div>
												<span class="block text-xs text-gray-500 mb-1.5">Split</span>
												<input
													type="text"
													bind:value={editDataSplit}
													oninput={markChanged}
													placeholder="train"
													class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
												/>
											</div>
										</div>
									{/if}

									<!-- Local File Fields -->
									{#if editDataSourceType === 'disk'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">File Path *</span>
											<input
												type="text"
												bind:value={editDataFilePath}
												oninput={markChanged}
												placeholder="/path/to/file.jsonl"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
									{/if}

									<!-- ServiceNow Fields -->
									{#if editDataSourceType === 'servicenow'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Table *</span>
											<input
												type="text"
												bind:value={editDataTable}
												oninput={markChanged}
												placeholder="incident"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Fields (comma-separated)</span>
											<input
												type="text"
												bind:value={editDataFields}
												oninput={markChanged}
												placeholder="sys_id, number, short_description"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div class="grid grid-cols-2 gap-3">
											<div>
												<span class="block text-xs text-gray-500 mb-1.5">Limit</span>
												<input
													type="number"
													bind:value={editDataLimit}
													oninput={markChanged}
													placeholder="1000"
													class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
												/>
											</div>
											<div>
												<span class="block text-xs text-gray-500 mb-1.5">Filters (JSON)</span>
												<input
													type="text"
													bind:value={editDataFilters}
													oninput={markChanged}
													placeholder="JSON filters"
													class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
												/>
											</div>
										</div>
									{/if}
								</div>

								<!-- Edit Mode: Sink Configuration -->
								<div class="space-y-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
									<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
										<Server size={12} />
										Sink (Optional)
									</div>

									<div class="grid grid-cols-2 gap-3">
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Alias</span>
											<input
												type="text"
												bind:value={editSinkAlias}
												oninput={markChanged}
												placeholder="output_sink"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Type</span>
											<CustomSelect
												options={sinkTypeOptions}
												bind:value={editSinkType}
												placeholder="Select sink type..."
												onchange={markChanged}
											/>
										</div>
									</div>

									<!-- Disk Sink Fields -->
									{#if editSinkType === 'disk'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">File Path *</span>
											<input
												type="text"
												bind:value={editSinkFilePath}
												oninput={markChanged}
												placeholder="output/data.jsonl"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
									{/if}

									<!-- HuggingFace Sink Fields -->
									{#if editSinkType === 'hf'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Repository ID *</span>
											<input
												type="text"
												bind:value={editSinkRepoId}
												oninput={markChanged}
												placeholder="username/dataset-name"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Split</span>
											<input
												type="text"
												bind:value={editSinkSplit}
												oninput={markChanged}
												placeholder="train"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
											/>
										</div>
									{/if}

									<!-- ServiceNow Sink Fields -->
									{#if editSinkType === 'servicenow'}
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Table *</span>
											<input
												type="text"
												bind:value={editSinkTable}
												oninput={markChanged}
												placeholder="u_output_table"
												class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
											/>
										</div>
										<div>
											<span class="block text-xs text-gray-500 mb-1.5">Operation</span>
											<CustomSelect
												options={[
													{ value: 'insert', label: 'Insert' },
													{ value: 'update', label: 'Update' }
												]}
												bind:value={editSinkOperation}
												placeholder="Select operation..."
												onchange={markChanged}
											/>
										</div>
									{/if}
								</div>

							{:else}
								<!-- Display Mode: Sources -->
								{#if sources.length > 0}
									<div>
										<div class="text-xs font-medium text-violet-600 dark:text-violet-400 mb-2">Sources ({sources.length})</div>
										{#each sources as src, idx}
											<div class="mb-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-xs border border-gray-200 dark:border-gray-700">
												<div class="flex items-center justify-between mb-2">
													<span class="font-medium text-gray-700 dark:text-gray-300">{src.alias || `Source ${idx + 1}`}</span>
													<span class="px-2 py-0.5 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400 text-[10px] font-medium">
														{src.type || 'unknown'}
													</span>
												</div>
												{#if src.type === 'hf'}
													<div class="text-gray-500">Repo: <span class="text-gray-700 dark:text-gray-300 font-mono">{src.repo_id || 'N/A'}</span></div>
													{#if src.split}<div class="text-gray-500">Split: <span class="text-gray-700 dark:text-gray-300">{Array.isArray(src.split) ? src.split.join(', ') : src.split}</span></div>{/if}
												{:else if src.type === 'servicenow'}
													<div class="text-gray-500">Table: <span class="text-gray-700 dark:text-gray-300 font-mono">{src.table || 'N/A'}</span></div>
													{#if src.limit}<div class="text-gray-500">Limit: <span class="text-gray-700 dark:text-gray-300">{src.limit}</span></div>{/if}
												{:else if src.type === 'disk'}
													<div class="text-gray-500">File: <span class="text-gray-700 dark:text-gray-300 font-mono break-all">{src.file_path || 'N/A'}</span></div>
												{/if}
												{#if src.join_type && src.join_type !== 'primary'}
													<div class="text-gray-500">Join: <span class="text-amber-600 dark:text-amber-400">{src.join_type}</span></div>
												{/if}
											</div>
										{/each}
									</div>
								{:else}
									<div class="text-xs text-gray-400 italic p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">No sources configured. Click Edit to add a source.</div>
								{/if}

								<!-- Display Mode: Sinks -->
								{#if sinks.length > 0}
									<div>
										<div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">Sinks ({sinks.length})</div>
										{#each sinks as sink, idx}
											<div class="mb-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg text-xs border border-gray-200 dark:border-gray-700">
												<div class="flex items-center justify-between mb-2">
													<span class="font-medium text-gray-700 dark:text-gray-300">{sink.alias || `Sink ${idx + 1}`}</span>
													<span class="px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-[10px] font-medium">
														{sink.operation || 'write'}
													</span>
												</div>
												{#if sink.type === 'servicenow'}
													<div class="text-gray-500">Table: <span class="text-gray-700 dark:text-gray-300 font-mono">{sink.table || 'N/A'}</span></div>
												{:else}
													<div class="text-gray-500">Type: <span class="text-gray-700 dark:text-gray-300">{sink.type || 'N/A'}</span></div>
												{/if}
											</div>
										{/each}
									</div>
								{/if}

								<!-- Sample Data Preview (only show when sources exist) -->
								{#if sources.length > 0}
									<div class="pt-2 border-t border-gray-200 dark:border-gray-700">
										<button
											onclick={() => { showDataPreview = !showDataPreview; if (!dataPreviewData && showDataPreview) fetchDataPreview(); }}
											class="flex items-center gap-2 text-xs font-medium text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300 transition-colors"
										>
											{#if showDataPreview}
												<EyeOff size={14} />
												Hide Sample Data
											{:else}
												<Eye size={14} />
												Preview Sample Data
											{/if}
										</button>

									{#if showDataPreview}
										<div class="mt-3 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
											{#if dataPreviewLoading}
												<div class="p-4 flex items-center justify-center gap-2 text-gray-500">
													<Loader2 size={16} class="animate-spin" />
													<span class="text-sm">Loading sample data...</span>
												</div>
											{:else if dataPreviewData?.message}
												<div class="p-3 bg-yellow-50 dark:bg-yellow-900/20 border-b border-yellow-200 dark:border-yellow-800">
													<span class="text-xs text-yellow-700 dark:text-yellow-300">{dataPreviewData.message}</span>
												</div>
											{:else if dataPreviewData?.records && dataPreviewData.records.length > 0}
												{@const columns = Object.keys(dataPreviewData.records[0] || {})}
												<!-- Header -->
												<div class="bg-gray-50 dark:bg-gray-800 px-3 py-2 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
													<div class="flex items-center gap-2">
														<Database size={12} class="text-gray-400" />
														<span class="text-xs font-medium text-gray-600 dark:text-gray-300">
															{columns.length} columns
														</span>
													</div>
													<span class="text-xs text-gray-500 dark:text-gray-400">
														{#if typeof dataPreviewData.total === 'number'}
															{dataPreviewData.records.length} of {dataPreviewData.total.toLocaleString()} rows
														{:else}
															{dataPreviewData.records.length} rows
														{/if}
													</span>
												</div>
												<!-- Table -->
												<div class="overflow-auto max-h-64">
													<table class="w-full text-xs">
														<thead class="sticky top-0 bg-gray-100 dark:bg-gray-800 z-10">
															<tr>
																<th class="px-2 py-1.5 text-left font-medium text-gray-500 dark:text-gray-400 border-b border-r border-gray-200 dark:border-gray-700 w-8">#</th>
																{#each columns as col}
																	<th class="px-2 py-1.5 text-left font-medium text-gray-600 dark:text-gray-300 border-b border-r border-gray-200 dark:border-gray-700 whitespace-nowrap max-w-xs">
																		{col}
																	</th>
																{/each}
															</tr>
														</thead>
														<tbody class="divide-y divide-gray-100 dark:divide-gray-800">
															{#each dataPreviewData.records as record, i}
																<tr
																	class="hover:bg-violet-50 dark:hover:bg-violet-900/20 cursor-pointer transition-colors {expandedPreviewRows.has(i) ? 'bg-violet-50 dark:bg-violet-900/20' : ''}"
																	onclick={() => togglePreviewRowExpand(i)}
																>
																	<td class="px-2 py-1.5 text-gray-400 border-r border-gray-100 dark:border-gray-800 font-mono">
																		<span class="inline-flex items-center gap-1">
																			<span class="text-gray-300 dark:text-gray-600 transition-transform {expandedPreviewRows.has(i) ? 'rotate-90' : ''}">▶</span>
																			{i + 1}
																		</span>
																	</td>
																	{#each columns as col}
																		{@const value = record[col]}
																		<td class="px-2 py-1.5 border-r border-gray-100 dark:border-gray-800 max-w-xs">
																			{#if value === null || value === undefined}
																				<span class="text-gray-300 dark:text-gray-600 italic">null</span>
																			{:else if typeof value === 'boolean'}
																				<span class="px-1.5 py-0.5 rounded text-xs font-medium {value ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
																					{value}
																				</span>
																			{:else if typeof value === 'number'}
																				<span class="font-mono text-violet-600 dark:text-violet-400">{value}</span>
																			{:else if typeof value === 'object'}
																				<span class="text-gray-500 dark:text-gray-400 font-mono truncate block max-w-[200px]">
																					{JSON.stringify(value).slice(0, 50)}{JSON.stringify(value).length > 50 ? '...' : ''}
																				</span>
																			{:else}
																				<span class="text-gray-700 dark:text-gray-300 truncate block max-w-[200px]">
																					{String(value).slice(0, 80)}{String(value).length > 80 ? '...' : ''}
																				</span>
																			{/if}
																		</td>
																	{/each}
																</tr>
																<!-- Expanded row detail -->
																{#if expandedPreviewRows.has(i)}
																	<tr class="bg-gray-50 dark:bg-gray-800/70">
																		<td colspan={columns.length + 1} class="p-0">
																			<div class="p-3 space-y-2 border-l-4 border-violet-400 dark:border-violet-500 ml-2">
																				{#each columns as col}
																					{@const value = record[col]}
																					<div class="flex gap-3">
																						<span class="text-xs font-semibold text-gray-500 dark:text-gray-400 min-w-[100px] flex-shrink-0 pt-0.5">
																							{col}
																						</span>
																						<div class="flex-1 min-w-0">
																							{#if value === null || value === undefined}
																								<span class="text-xs text-gray-300 dark:text-gray-600 italic">null</span>
																							{:else if typeof value === 'boolean'}
																								<span class="px-1.5 py-0.5 rounded text-xs font-medium {value ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'}">
																									{value}
																								</span>
																							{:else if typeof value === 'number'}
																								<span class="text-xs font-mono text-violet-600 dark:text-violet-400">{value}</span>
																							{:else if typeof value === 'object'}
																								<pre class="text-xs font-mono text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-40 overflow-auto">{JSON.stringify(value, null, 2)}</pre>
																							{:else}
																								<div class="text-xs text-gray-700 dark:text-gray-300 whitespace-pre-wrap break-words bg-white dark:bg-gray-900 p-2 rounded border border-gray-200 dark:border-gray-700 max-h-40 overflow-auto">
																									{String(value)}
																								</div>
																							{/if}
																						</div>
																					</div>
																				{/each}
																			</div>
																		</td>
																	</tr>
																{/if}
															{/each}
														</tbody>
													</table>
												</div>
											{:else if !dataPreviewLoading}
												<button
													onclick={fetchDataPreview}
													class="w-full p-4 text-center text-sm text-gray-500 hover:text-violet-600 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
												>
													Click to load sample data
												</button>
											{/if}
										</div>
									{/if}
									</div>
								{/if}
							{/if}
						</div>
					{/if}

					<!-- Output node config -->
					{#if node.node_type === 'output'}
						{@const outputMap = node.output_config?.output_map || {}}
						{@const outputKeys = Object.keys(outputMap)}
						<div class="space-y-4">
							{#if isEditing}
								<!-- Edit Mode: Output Mappings -->
								<div class="space-y-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
											<Map size={12} />
											Output Mappings
										</div>
										<button
											onclick={addOutputMapping}
											class="flex items-center gap-1 px-2 py-1 text-xs bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 rounded hover:bg-violet-200 dark:hover:bg-violet-800/50 transition-colors"
										>
											<Plus size={12} />
											Add Mapping
										</button>
									</div>

									{#if editOutputMappings.length > 0}
										<div class="space-y-2 max-h-64 overflow-y-auto">
											{#each editOutputMappings as mapping, idx}
												<div class="p-3 bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700">
													<div class="flex items-center justify-between mb-3">
														<span class="text-xs font-medium text-gray-600 dark:text-gray-400">Mapping {idx + 1}</span>
														<button
															onclick={() => removeOutputMapping(idx)}
															class="p-1 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-gray-100 dark:hover:bg-gray-800"
														>
															<Trash2 size={14} />
														</button>
													</div>
													<div class="grid grid-cols-2 gap-3 mb-3">
														<div>
															<span class="block text-xs text-gray-500 mb-1.5">Output Key *</span>
															<input
																type="text"
																value={mapping.key}
																oninput={(e) => updateOutputMapping(idx, 'key', e.currentTarget.value)}
																placeholder="field_name"
																aria-label="Output key"
																class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
															/>
														</div>
														<div>
															<span class="block text-xs text-gray-500 mb-1.5">From State</span>
															<input
																type="text"
																value={mapping.from}
																oninput={(e) => updateOutputMapping(idx, 'from', e.currentTarget.value)}
																placeholder="state_variable"
																aria-label="From state"
																class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
															/>
														</div>
													</div>
													<div class="grid grid-cols-2 gap-3">
														<div>
															<span class="block text-xs text-gray-500 mb-1.5">Static Value (JSON)</span>
															<input
																type="text"
																value={mapping.value}
																oninput={(e) => updateOutputMapping(idx, 'value', e.currentTarget.value)}
																placeholder="JSON value"
																aria-label="Static value"
																class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
															/>
														</div>
														<div>
															<span class="block text-xs text-gray-500 mb-1.5">Transform Function</span>
															<input
																type="text"
																value={mapping.transform}
																oninput={(e) => updateOutputMapping(idx, 'transform', e.currentTarget.value)}
																placeholder="transform_func"
																aria-label="Transform function"
																class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 font-mono focus:ring-2 focus:ring-violet-500"
															/>
														</div>
													</div>
												</div>
											{/each}
										</div>
									{:else}
										<div class="text-sm text-gray-500 italic p-4 bg-white dark:bg-gray-900 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 text-center">
											No output mappings. Click "Add Mapping" to configure output fields.
										</div>
									{/if}
								</div>
							{:else}
								<!-- Display Mode: Generator -->
								{#if node.output_config?.generator}
									<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
										<div class="flex items-center gap-2 text-xs font-medium text-violet-600 dark:text-violet-400 mb-2">
											<Code size={12} />
											Generator Class
										</div>
										<div class="text-sm font-mono bg-white dark:bg-gray-900 px-3 py-2 rounded-lg text-gray-700 dark:text-gray-300 break-all border border-gray-200 dark:border-gray-700">
											{node.output_config.generator.split('.').pop()}
										</div>
										<div class="text-xs text-gray-400 mt-2 break-all font-mono">
											{node.output_config.generator}
										</div>
									</div>
								{/if}

								<!-- Display Mode: Output Map -->
								{#if outputKeys.length > 0}
									<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
										<div class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400 mb-3">
											<Map size={12} />
											Output Mappings ({outputKeys.length})
										</div>
										<div class="space-y-2 max-h-48 overflow-y-auto">
											{#each outputKeys as key}
												{@const mapping = outputMap[key]}
												<div class="flex items-center gap-2 p-2 bg-white dark:bg-gray-900 rounded-lg text-sm border border-gray-200 dark:border-gray-700">
													<span class="font-mono text-gray-700 dark:text-gray-300 truncate flex-shrink-0" title={key}>
														{key.length > 15 ? key.slice(0, 15) + '...' : key}
													</span>
													<ArrowRight size={12} class="text-gray-400 flex-shrink-0" />
													{#if mapping.from}
														<span class="font-mono text-violet-600 dark:text-violet-400 truncate">{mapping.from}</span>
													{:else if mapping.value !== undefined}
														<span class="px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400 text-xs">static</span>
													{/if}
													{#if mapping.transform}
														<span class="px-2 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400 text-xs flex-shrink-0">
															fn: {mapping.transform}
														</span>
													{/if}
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="text-sm text-gray-500 italic p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700 text-center">
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
							<div class="flex items-center gap-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
								<Shuffle size={14} />
								Sampler Attributes
							</div>

							{#if isEditing}
								<!-- Edit Mode: Attributes -->
								<div class="space-y-3 p-3 bg-purple-50 dark:bg-purple-900/20 rounded-lg border border-purple-200 dark:border-purple-800">
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-2 text-xs font-medium text-purple-700 dark:text-purple-300">
											Attributes
										</div>
										<button
											onclick={addSamplerAttribute}
											class="flex items-center gap-1 px-2 py-1 text-xs bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-300 rounded hover:bg-purple-200 dark:hover:bg-purple-700 transition-colors"
										>
											<Plus size={12} />
											Add
										</button>
									</div>

									{#if editSamplerAttributes.length > 0}
										<div class="space-y-2 max-h-64 overflow-y-auto">
											{#each editSamplerAttributes as attr, idx}
												<div class="p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
													<div class="flex items-center justify-between mb-2">
														<span class="text-xs text-gray-500">Attribute {idx + 1}</span>
														<button
															onclick={() => removeSamplerAttribute(idx)}
															class="p-1 text-gray-400 hover:text-red-500 transition-colors"
														>
															<Trash2 size={12} />
														</button>
													</div>
													<div class="grid grid-cols-1 gap-2">
														<div>
															<span class="block text-[10px] text-gray-500 mb-0.5">Name</span>
															<input
																type="text"
																value={attr.name}
																oninput={(e) => updateSamplerAttribute(idx, 'name', e.currentTarget.value)}
																placeholder="num_turns"
																aria-label="Attribute name"
																class="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 font-mono"
															/>
														</div>
														<div>
															<span class="block text-[10px] text-gray-500 mb-0.5">Values (comma-separated)</span>
															<input
																type="text"
																value={attr.values}
																oninput={(e) => updateSamplerAttribute(idx, 'values', e.currentTarget.value)}
																placeholder="2, 3, 4, 5 or professional, casual, friendly"
																aria-label="Attribute values"
																class="w-full px-2 py-1 text-xs border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 font-mono"
															/>
														</div>
													</div>
												</div>
											{/each}
										</div>
									{:else}
										<div class="text-xs text-gray-400 italic p-2 bg-white dark:bg-gray-800 rounded">
											No attributes defined. Click "Add" to create sampler attributes.
										</div>
									{/if}
								</div>
							{:else}
								<!-- Display Mode: Attributes -->
								{#if attributeNames.length > 0}
									<div>
										<div class="text-xs font-medium text-purple-600 dark:text-purple-400 mb-2">
											Attributes ({attributeNames.length})
										</div>
										<div class="space-y-2 max-h-48 overflow-y-auto">
											{#each attributeNames as name}
												{@const attr = attributes[name]}
												<div class="p-2 bg-gray-50 dark:bg-gray-800 rounded-lg text-xs">
													<div class="flex items-center justify-between mb-1">
														<span class="font-mono font-medium text-gray-700 dark:text-gray-300">{name}</span>
														<span class="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 text-[10px]">
															{attr.values?.length ?? 0} values
														</span>
													</div>
													<div class="text-gray-500 truncate" title={attr.values?.join(', ')}>
														{attr.values?.slice(0, 5).join(', ')}{attr.values?.length > 5 ? '...' : ''}
													</div>
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="text-xs text-gray-400 italic p-2 bg-gray-50 dark:bg-gray-800 rounded">No attributes configured. Click Edit to add attributes.</div>
								{/if}
							{/if}
						</div>
					{/if}

					<!-- Execution state -->
					{#if nodeState}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
								Execution Status
							</div>
							<div class="space-y-2">
								<div class="flex items-center justify-between">
									<span class="text-sm text-gray-600 dark:text-gray-400">Status</span>
									<span
										class="px-2 py-0.5 rounded text-xs font-medium capitalize"
										class:bg-gray-100={nodeState.status === 'pending'}
										class:text-gray-700={nodeState.status === 'pending'}
										class:bg-blue-100={nodeState.status === 'running'}
										class:text-blue-700={nodeState.status === 'running'}
										class:bg-green-100={nodeState.status === 'completed'}
										class:text-green-700={nodeState.status === 'completed'}
										class:bg-red-100={nodeState.status === 'failed'}
										class:text-red-700={nodeState.status === 'failed'}
									>
										{nodeState.status}
									</span>
								</div>
								{#if nodeState.duration_ms}
									<div class="flex items-center justify-between">
										<span class="text-sm text-gray-600 dark:text-gray-400">Duration</span>
										<span class="text-sm text-gray-800 dark:text-gray-200">
											{nodeState.duration_ms}ms
										</span>
									</div>
								{/if}
								{#if nodeState.error}
									<div class="mt-2 p-2 bg-red-50 dark:bg-red-900/20 rounded text-xs text-red-700 dark:text-red-400">
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
					{#if isEditing}
						{#each editPrompts as message, index}
							<div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
								<div class="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
									<CustomSelect
										options={roleOptions}
										value={message.role}
										compact={true}
										searchable={false}
										onchange={(val) => updatePromptRole(index, val)}
									/>
									<button
										onclick={() => removePromptMessage(index)}
										class="text-gray-400 hover:text-red-500 p-1"
									>
										<X size={14} />
									</button>
								</div>
								<textarea
									value={message.content}
									oninput={(e) => updatePromptContent(index, e.currentTarget.value)}
									class="w-full px-3 py-2 text-sm bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-200 border-0 focus:ring-0 resize-none font-mono"
									rows="6"
									placeholder="Enter prompt content..."
								></textarea>
							</div>
						{/each}

						<div class="flex gap-2">
							<button
								onclick={() => addPromptMessage('system')}
								class="flex-1 px-3 py-2 text-xs font-medium border border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
							>
								+ System
							</button>
							<button
								onclick={() => addPromptMessage('user')}
								class="flex-1 px-3 py-2 text-xs font-medium border border-dashed border-gray-300 dark:border-gray-700 rounded-lg text-gray-500 hover:text-gray-700 hover:border-gray-400 transition-colors"
							>
								+ User
							</button>
						</div>
					{:else}
						{#each node.prompt ?? [] as message}
							<div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
								<div class="px-3 py-2 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
									<span class="text-xs font-medium text-violet-600 dark:text-violet-400 capitalize">
										{message.role}
									</span>
								</div>
								<div class="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap font-mono bg-white dark:bg-gray-900">
									{message.content}
								</div>
							</div>
						{/each}

						{#if !node.prompt?.length}
							<div class="text-center py-8 text-gray-500 text-sm">
								No prompts defined for this node
							</div>
						{/if}
					{/if}
				</div>
			{/if}

			<!-- Tools Tab -->
			{#if activeTab === 'tools' && showToolsTab}
				<div class="space-y-4">
					<!-- Tool Choice -->
					<div>
						<span class="block text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-1.5">
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
							<div class="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-800 rounded-lg text-gray-700 dark:text-gray-300">
								{toolChoiceOptions.find(o => o.value === editToolChoice)?.label ?? 'Auto'} — {toolChoiceOptions.find(o => o.value === editToolChoice)?.subtitle ?? ''}
							</div>
						{/if}
					</div>

					<!-- Tools Section -->
					<div>
						<div class="flex items-center justify-between mb-3">
							<span class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
								Tools
							</span>
							{#if isEditing}
								<button
									onclick={() => { showToolPicker = true; }}
									class="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-violet-600 dark:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-md transition-colors"
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
									<div class="flex items-start gap-3 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 group hover:border-violet-300 dark:hover:border-violet-700 transition-colors">
										<div class="w-8 h-8 rounded-md bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center flex-shrink-0">
											{#if libraryTool}
												<Library size={16} class="text-violet-600 dark:text-violet-400" />
											{:else}
												<Wrench size={16} class="text-violet-600 dark:text-violet-400" />
											{/if}
										</div>
										<div class="flex-1 min-w-0">
											<div class="font-medium text-sm text-gray-800 dark:text-gray-200">
												{libraryTool?.name || toolName}
											</div>
											{#if libraryTool?.description}
												<div class="text-xs text-gray-500 dark:text-gray-400 truncate">
													{libraryTool.description}
												</div>
											{:else if modulePath}
												<div class="text-xs text-gray-500 dark:text-gray-400 font-mono truncate" title={toolPath}>
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
												class="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors opacity-0 group-hover:opacity-100"
												title="Remove tool"
											>
												<X size={14} />
											</button>
										{/if}
									</div>
								{/each}
							</div>
						{:else}
							<div class="text-center py-8 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-lg">
								<Wrench size={28} class="mx-auto mb-2 text-gray-300 dark:text-gray-600" />
								<p class="text-sm text-gray-500 dark:text-gray-400 mb-1">No tools configured</p>
								{#if isEditing}
									<p class="text-xs text-gray-400 dark:text-gray-500">Click "Add Tool" to select from library or enter path</p>
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
						<div class="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 px-3 py-2 rounded-lg">
							<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
								<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
								<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
							</svg>
							Loading code from files...
						</div>
					{/if}

					<!-- Error display -->
					{#if codeLoadError}
						<div class="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-3 py-2 rounded-lg">
							⚠️ {codeLoadError}
						</div>
					{/if}

					<!-- Code loaded indicators -->
					{#if postProcessCodeLoaded || preProcessCodeLoaded || lambdaCodeLoaded}
						<div class="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-3 py-1.5 rounded">
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
								<div class="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase tracking-wider">
									Data Transformation
								</div>
								<span class="text-xs text-gray-400">Python class</span>
							</div>
							<div class="text-xs text-gray-500 mb-2">
								Transform data records during processing. This code will be saved to task_executor.py.
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:value={editTransformCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					<!-- Output Node: Generator Code -->
					{#if node.node_type === 'output'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-purple-600 dark:text-purple-400 uppercase tracking-wider">
									Output Generator
								</div>
								<span class="text-xs text-gray-400">Python class</span>
							</div>
							{#if isEditing}
								<div class="mb-2">
									<span class="block text-xs text-gray-500 mb-1">Generator Class Path</span>
									<input
										type="text"
										bind:value={editOutputGenerator}
										oninput={markChanged}
										aria-label="Generator class path"
										class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
										placeholder="tasks.my_task.task_executor.MyOutputGenerator"
									/>
								</div>
							{:else if node.output_config?.generator}
								<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg break-all mb-2">
									{node.output_config.generator}
								</div>
							{/if}
							<div class="text-xs text-gray-500 mb-2">
								Generate output records from workflow state. This code will be saved to task_executor.py.
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:value={editOutputGeneratorCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					<!-- Pre-processor (only for execution nodes) -->
					{#if canHaveProcessors && (node.pre_process || isEditing)}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-gray-500 uppercase tracking-wider">
									Pre-processor
								</div>
								<span class="text-xs text-gray-400">Python module path</span>
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editPreProcess}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 mb-2"
									placeholder="module.path.ClassName"
								/>
							{:else}
								<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg break-all mb-2">
									{node.pre_process}
								</div>
							{/if}
							<!-- Monaco Editor - read-only when not editing -->
							<div class="mt-2 monaco-editor-wrapper">
								<div class="text-xs text-gray-500 mb-1">{isEditing ? 'Code Editor:' : 'Code Preview:'}</div>
								<MonacoEditor
									bind:value={preProcessCode}
									language="python"
									height="clamp(200px, 25vh, 350px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					<!-- Post-processor (only for execution nodes) -->
					{#if canHaveProcessors && (node.post_process || isEditing)}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-gray-500 uppercase tracking-wider">
									Post-processor
								</div>
								<span class="text-xs text-gray-400">Python module path</span>
							</div>
							{#if isEditing}
								<input
									type="text"
									bind:value={editPostProcess}
									oninput={markChanged}
									class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 mb-2"
									placeholder="module.path.ClassName"
								/>
							{:else}
								<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg break-all mb-2">
									{node.post_process}
								</div>
							{/if}
							<!-- Monaco Editor - read-only when not editing -->
							<div class="mt-2 monaco-editor-wrapper">
								<div class="text-xs text-gray-500 mb-1">{isEditing ? 'Code Editor:' : 'Code Preview:'}</div>
								<MonacoEditor
									bind:value={postProcessCode}
									language="python"
									height="clamp(200px, 25vh, 350px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					<!-- Lambda function -->
					{#if node.node_type === 'lambda'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-orange-600 dark:text-orange-400 uppercase tracking-wider">
									Lambda Function
								</div>
								<span class="text-xs text-gray-400">Python function</span>
							</div>
							{#if isEditing}
								<div class="mb-2">
									<span class="block text-xs text-gray-500 mb-1">Function Path</span>
									<input
										type="text"
										bind:value={editFunctionPath}
										oninput={markChanged}
										aria-label="Function path"
										class="w-full px-3 py-2 text-sm font-mono border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
										placeholder="tasks.my_task.task_executor.my_function"
									/>
								</div>
							{:else if node.function_path}
								<div class="text-sm text-gray-800 dark:text-gray-200 font-mono bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg break-all mb-2">
									{node.function_path}
								</div>
							{:else}
								<div class="text-sm text-gray-500 italic mb-2">
									No function path defined
								</div>
							{/if}
							<div class="text-xs text-gray-500 mb-2">
								{isEditing ? 'Edit the lambda function code. This will be saved to task_executor.py.' : 'Lambda function code.'}
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:value={lambdaCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					<!-- Branch condition (for branch nodes) -->
					{#if node.node_type === 'branch'}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-yellow-600 dark:text-yellow-400 uppercase tracking-wider">
									Branch Condition
								</div>
								<span class="text-xs text-gray-400">Python function</span>
							</div>
							<div class="text-xs text-gray-500 mb-2">
								{isEditing ? 'Edit the condition logic that determines which path to take.' : 'Condition logic that determines which path to take. This code will be saved to task_executor.py.'}
							</div>
							<div class="monaco-editor-wrapper">
								<MonacoEditor
									bind:value={branchConditionCode}
									language="python"
									height="clamp(250px, 35vh, 450px)"
									theme="vs-dark"
									fontSize={12}
									readonly={!isEditing}
									on:change={() => markChanged()}
								/>
							</div>
						</div>
					{/if}

					{#if !canHaveProcessors && !node.pre_process && !node.post_process && node.node_type !== 'lambda' && node.node_type !== 'branch' && node.node_type !== 'data' && node.node_type !== 'output' && !isEditing}
						<div class="text-center py-8 text-gray-500 text-sm">
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
									class="w-full pl-3 pr-8 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 focus:border-transparent"
								/>
								{#if overrideSearchQuery}
									<button
										onclick={() => overrideSearchQuery = ''}
										class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
									>
										<X size={14} />
									</button>
								{/if}
							</div>
						</div>
					</div>

					<!-- Info banner -->
					<div class="p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
						<div class="flex items-start gap-2">
							<Info size={16} class="text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
							<div class="text-xs text-blue-700 dark:text-blue-300">
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
								class="rounded-lg border transition-all {nodeHasOverride ? 'border-amber-300 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/10' : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'}"
							>
								<!-- Node header (collapsible) -->
								<button
									onclick={() => toggleOverrideNode(innerNode.id)}
									class="w-full flex items-center gap-3 p-3 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-lg transition-colors"
								>
									<!-- Expand/collapse chevron -->
									<div class="text-gray-400 transition-transform" class:rotate-90={isExpanded}>
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
											<span class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
												{innerNode.summary || innerNode.id}
											</span>
											{#if nodeHasOverride}
												<span class="px-1.5 py-0.5 text-xs bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200 rounded font-medium">
													Overridden
												</span>
											{/if}
										</div>
										<div class="text-xs text-gray-500 font-mono truncate">
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
											class="px-2 py-1 text-xs font-medium text-violet-600 hover:text-violet-700 bg-violet-100 hover:bg-violet-200 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 dark:text-violet-400 rounded transition-colors cursor-pointer"
										>
											+ Add Override
										</span>
									{/if}
								</button>

								<!-- Expanded override editor -->
								{#if isExpanded}
									<div class="px-3 pb-3 pt-1 border-t border-gray-100 dark:border-gray-700/50">
										{#if nodeHasOverride && override}
											{#if isEditing}
												<!-- Edit mode: Override configuration form -->
												<div class="space-y-4 mt-3">
													<!-- Model Override -->
													{#if innerNode.node_type === 'llm' || innerNode.node_type === 'agent'}
														<div class="space-y-2">
															<label class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
																<Bot size={12} />
																Model Override
															</label>
															<input
																type="text"
																value={override.model?.name ?? ''}
																oninput={(e) => updateOverrideField(innerNode.id, 'model', e.currentTarget.value ? { name: e.currentTarget.value } : undefined)}
																placeholder="e.g., gpt-4o, claude-3-5-sonnet"
																class="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
															/>
														</div>
													{/if}

													<!-- Prompt Placeholder Map -->
													<div class="space-y-2">
														<div class="flex items-center justify-between">
															<label class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
																<Copy size={12} />
																Placeholder Mappings
															</label>
															<button
																onclick={() => addPlaceholderMapping(innerNode.id)}
																class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-violet-600 hover:text-violet-700 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded transition-colors"
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
																			class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
																		/>
																		<ArrowRight size={14} class="text-gray-400 flex-shrink-0" />
																		<input
																			type="text"
																			value={value}
																			oninput={(e) => updatePlaceholderMapping(innerNode.id, key, key, e.currentTarget.value)}
																			placeholder="mapped_value"
																			class="flex-1 px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
																		/>
																		<button
																			onclick={() => removePlaceholderMapping(innerNode.id, key)}
																			class="p-1 text-gray-400 hover:text-red-500 transition-colors"
																		>
																			<Trash2 size={14} />
																		</button>
																	</div>
																{/each}
															</div>
														{:else}
															<div class="text-xs text-gray-400 italic py-2">
																No placeholder mappings. Click "Add" to create one.
															</div>
														{/if}
													</div>

													<!-- Pre/Post Process Overrides -->
													{#if innerNode.node_type !== 'data' && innerNode.node_type !== 'output'}
														<div class="grid grid-cols-2 gap-3">
															<div class="space-y-2">
																<label class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
																	<Code size={12} />
																	Pre-process
																</label>
																<input
																	type="text"
																	value={override.pre_process ?? ''}
																	oninput={(e) => updateOverrideField(innerNode.id, 'pre_process', e.currentTarget.value || undefined)}
																	placeholder="path.to.pre_processor"
																	class="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
																/>
															</div>
															<div class="space-y-2">
																<label class="flex items-center gap-2 text-xs font-medium text-gray-600 dark:text-gray-400">
																	<Code size={12} />
																	Post-process
																</label>
																<input
																	type="text"
																	value={override.post_process ?? ''}
																	oninput={(e) => updateOverrideField(innerNode.id, 'post_process', e.currentTarget.value || undefined)}
																	placeholder="path.to.post_processor"
																	class="w-full px-2 py-1.5 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
																/>
															</div>
														</div>
													{/if}

													<!-- Remove override button -->
													<div class="pt-2 border-t border-gray-200 dark:border-gray-700">
														<button
															onclick={() => removeOverrideForNode(innerNode.id)}
															class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
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
															<Bot size={14} class="text-gray-400 mt-0.5" />
															<div>
																<div class="text-xs text-gray-500">Model</div>
																<div class="text-sm font-mono text-gray-800 dark:text-gray-200">{override.model.name}</div>
															</div>
														</div>
													{/if}

													{#if override.prompt_placeholder_map && Object.keys(override.prompt_placeholder_map).length > 0}
														<div class="flex items-start gap-2">
															<Copy size={14} class="text-gray-400 mt-0.5" />
															<div class="flex-1">
																<div class="text-xs text-gray-500 mb-1">Placeholder Mappings</div>
																<div class="space-y-1">
																	{#each Object.entries(override.prompt_placeholder_map) as [key, value]}
																		<div class="flex items-center gap-2 text-xs">
																			<code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-violet-600 dark:text-violet-400">{key}</code>
																			<ArrowRight size={12} class="text-gray-400" />
																			<code class="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-gray-700 dark:text-gray-300">{value}</code>
																		</div>
																	{/each}
																</div>
															</div>
														</div>
													{/if}

													{#if override.pre_process}
														<div class="flex items-start gap-2">
															<Code size={14} class="text-gray-400 mt-0.5" />
															<div>
																<div class="text-xs text-gray-500">Pre-process</div>
																<div class="text-xs font-mono text-gray-800 dark:text-gray-200">{override.pre_process}</div>
															</div>
														</div>
													{/if}

													{#if override.post_process}
														<div class="flex items-start gap-2">
															<Code size={14} class="text-gray-400 mt-0.5" />
															<div>
																<div class="text-xs text-gray-500">Post-process</div>
																<div class="text-xs font-mono text-gray-800 dark:text-gray-200">{override.post_process}</div>
															</div>
														</div>
													{/if}

													{#if !override.model && !override.prompt_placeholder_map && !override.pre_process && !override.post_process}
														<div class="text-xs text-gray-400 italic">
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
														class="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-violet-600 hover:text-violet-700 bg-violet-100 hover:bg-violet-200 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 dark:text-violet-400 rounded-lg transition-colors"
													>
														<Plus size={16} />
														Add Configuration Override
													</button>
												{:else}
													<div class="text-xs text-gray-400">
														No overrides configured for this node.
														<br />
														<span class="text-gray-500">Click Edit to add overrides.</span>
													</div>
												{/if}
											</div>
										{/if}
									</div>
								{/if}
							</div>
						{/each}

						{#if filteredInnerNodes().length === 0}
							<div class="text-center py-8 text-gray-500 text-sm">
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
						<div class="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
							<div class="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300">
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
					<div class="p-3 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
						<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
							Configuration Overview
						</div>
						<div class="grid grid-cols-2 gap-2 text-xs">
							<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
								<span class="text-gray-500">Node Type</span>
								<span class="font-medium text-gray-800 dark:text-gray-200">{node.node_type}</span>
							</div>
							<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
								<span class="text-gray-500">Node ID</span>
								<span class="font-mono text-gray-800 dark:text-gray-200 truncate max-w-[120px]" title={node.id}>{node.id}</span>
							</div>
							{#if node.model?.name}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
									<span class="text-gray-500">Model</span>
									<span class="font-medium text-violet-600 dark:text-violet-400">{node.model.name}</span>
								</div>
							{/if}
							{#if node.model?.provider}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
									<span class="text-gray-500">Provider</span>
									<span class="text-gray-800 dark:text-gray-200">{node.model.provider}</span>
								</div>
							{/if}
							{#if node.tools && node.tools.length > 0}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
									<span class="text-gray-500">Tools</span>
									<span class="text-gray-800 dark:text-gray-200">{node.tools.length} configured</span>
								</div>
							{/if}
							{#if node.tool_choice}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded">
									<span class="text-gray-500">Tool Choice</span>
									<span class="text-gray-800 dark:text-gray-200">{node.tool_choice}</span>
								</div>
							{/if}
							{#if node.pre_process}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded col-span-2">
									<span class="text-gray-500">Pre-processor</span>
									<span class="font-mono text-xs text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={node.pre_process}>{node.pre_process}</span>
								</div>
							{/if}
							{#if node.post_process}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded col-span-2">
									<span class="text-gray-500">Post-processor</span>
									<span class="font-mono text-xs text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={node.post_process}>{node.post_process}</span>
								</div>
							{/if}
							{#if node.function_path}
								<div class="flex justify-between p-2 bg-white dark:bg-gray-900 rounded col-span-2">
									<span class="text-gray-500">Function Path</span>
									<span class="font-mono text-xs text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={node.function_path}>{node.function_path}</span>
								</div>
							{/if}
						</div>
					</div>

					<!-- Execution State (if available) -->
					{#if nodeState}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
								Execution State
							</div>
							<div class="p-3 rounded-lg border {nodeState.status === 'completed' ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : nodeState.status === 'error' ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' : nodeState.status === 'running' ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800' : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700'}">
								<div class="flex items-center justify-between mb-2">
									<span class="text-xs font-medium {nodeState.status === 'completed' ? 'text-green-700 dark:text-green-400' : nodeState.status === 'error' ? 'text-red-700 dark:text-red-400' : nodeState.status === 'running' ? 'text-blue-700 dark:text-blue-400' : 'text-gray-600 dark:text-gray-400'}">
										{nodeState.status?.toUpperCase() ?? 'UNKNOWN'}
									</span>
									{#if nodeState.duration_ms}
										<span class="text-xs text-gray-500">{nodeState.duration_ms}ms</span>
									{/if}
								</div>
								{#if nodeState.error}
									<div class="text-xs text-red-600 dark:text-red-400 font-mono bg-red-100 dark:bg-red-900/30 p-2 rounded mt-2">
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
								<div class="text-xs font-medium text-gray-500 uppercase tracking-wider">
									Model Parameters
								</div>
								{#if isEditing}
									<button
										onclick={addModelParameter}
										class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-violet-600 hover:text-violet-700 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded transition-colors"
									>
										<Plus size={12} />
										Add
									</button>
								{/if}
							</div>

							{#if isEditing}
								<div class="space-y-2">
									{#each Object.entries(editModelParameters) as [key, value]}
										<div class="flex items-center gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
											<input
												type="text"
												value={key}
												onblur={(e) => renameModelParameter(key, e.currentTarget.value)}
												class="flex-1 px-2 py-1 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
												placeholder="Parameter name"
											/>
											<input
												type="text"
												value={typeof value === 'object' ? JSON.stringify(value) : String(value)}
												oninput={(e) => updateModelParameter(key, parseParameterValue(e.currentTarget.value))}
												class="flex-1 px-2 py-1 text-xs font-mono border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200"
												placeholder="Value"
											/>
											<button
												onclick={() => removeModelParameter(key)}
												class="p-1 text-gray-400 hover:text-red-500 transition-colors"
											>
												<Trash2 size={14} />
											</button>
										</div>
									{/each}

									{#if Object.keys(editModelParameters).length === 0}
										<div class="text-center py-4 text-gray-400 text-sm border border-dashed border-gray-300 dark:border-gray-700 rounded-lg">
											No parameters. Click "Add" to add one.
										</div>
									{/if}
								</div>

								<!-- Common parameters quick-add -->
								<div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
									<div class="text-xs text-gray-500 mb-2">Quick add common parameters:</div>
									<div class="flex flex-wrap gap-1">
										{#each ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty'] as param}
											{#if !editModelParameters[param]}
												<button
													onclick={() => { editModelParameters[param] = param === 'temperature' ? 0.7 : param === 'max_tokens' ? 1024 : 0; editModelParameters = {...editModelParameters}; markChanged(); }}
													class="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded text-gray-600 dark:text-gray-400 transition-colors"
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
										<div class="flex items-center justify-between text-sm p-2 bg-gray-50 dark:bg-gray-800 rounded">
											<span class="text-gray-600 dark:text-gray-400 font-medium">{key}</span>
											<span class="font-mono text-gray-800 dark:text-gray-200">
												{typeof value === 'object' ? JSON.stringify(value) : value}
											</span>
										</div>
									{/each}

									{#if !node.model?.parameters || Object.keys(node.model.parameters).length === 0}
										<div class="text-center py-4 text-gray-400 text-sm">
											No parameters configured
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/if}

					<!-- Data Source Config (for data nodes) -->
					{#if node.node_type === 'data' && node.data_source}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
								Data Source Configuration
							</div>
							<div class="space-y-2 text-xs">
								{#if node.data_source.source_type}
									<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
										<span class="text-gray-500">Source Type</span>
										<span class="font-medium text-gray-800 dark:text-gray-200">{node.data_source.source_type}</span>
									</div>
								{/if}
								{#if node.data_source.repo_id}
									<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
										<span class="text-gray-500">Repository</span>
										<span class="font-mono text-gray-800 dark:text-gray-200">{node.data_source.repo_id}</span>
									</div>
								{/if}
								{#if node.data_source.file_path}
									<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
										<span class="text-gray-500">File Path</span>
										<span class="font-mono text-gray-800 dark:text-gray-200">{node.data_source.file_path}</span>
									</div>
								{/if}
								{#if node.data_source.split}
									<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
										<span class="text-gray-500">Split</span>
										<span class="text-gray-800 dark:text-gray-200">{node.data_source.split}</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Subgraph Config -->
					{#if node.node_type === 'subgraph' && node.subgraph}
						<div>
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
								Subgraph Configuration
							</div>
							<div class="space-y-2 text-xs">
								<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
									<span class="text-gray-500">Subgraph Path</span>
									<span class="font-mono text-gray-800 dark:text-gray-200 truncate max-w-[200px]" title={node.subgraph}>{node.subgraph}</span>
								</div>
								{#if node.node_config_map && Object.keys(node.node_config_map).length > 0}
									<div class="flex justify-between p-2 bg-gray-50 dark:bg-gray-800 rounded">
										<span class="text-gray-500">Overrides</span>
										<span class="text-gray-800 dark:text-gray-200">{Object.keys(node.node_config_map).length} nodes</span>
									</div>
								{/if}
							</div>
						</div>
					{/if}

					<!-- Metadata (expandable JSON) -->
					{#if node.metadata && Object.keys(node.metadata).length > 0}
						<div>
							<div class="flex items-center justify-between mb-2">
								<div class="text-xs font-medium text-gray-500 uppercase tracking-wider">
									Metadata
								</div>
								<span class="text-xs text-gray-400">{Object.keys(node.metadata).length} fields</span>
							</div>
							<details class="group">
								<summary class="cursor-pointer text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300">
									View full metadata
								</summary>
								<div class="mt-2 text-sm font-mono bg-gray-100 dark:bg-gray-800 px-3 py-2 rounded-lg overflow-x-auto max-h-64">
									<pre class="text-gray-800 dark:text-gray-200 text-xs">{JSON.stringify(node.metadata, null, 2)}</pre>
								</div>
							</details>
						</div>
					{/if}

					<!-- Full Node Configuration (expandable) -->
					<div>
						<div class="flex items-center justify-between mb-2">
							<div class="text-xs font-medium text-gray-500 uppercase tracking-wider">
								Full Configuration
							</div>
						</div>
						<details class="group">
							<summary class="cursor-pointer text-xs text-violet-600 dark:text-violet-400 hover:text-violet-700 dark:hover:text-violet-300">
								View raw node configuration (JSON)
							</summary>
							<div class="mt-2 text-sm font-mono bg-gray-900 dark:bg-gray-950 px-3 py-2 rounded-lg overflow-x-auto max-h-80">
								<pre class="text-green-400 text-xs">{JSON.stringify(node, null, 2)}</pre>
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
