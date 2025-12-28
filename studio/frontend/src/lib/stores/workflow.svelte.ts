/**
 * Workflow Store - Global state management using Svelte 5 Runes
 *
 * Manages workflows, executions, and UI state for the SyGra Workflow Studio.
 */

import { layoutInnerGraph, calculateSubgraphDimensions, layoutAllInnerGraphs } from '$lib/utils/layoutUtils';

const API_BASE = '/api';

// Types
export interface WorkflowSummary {
	id: string;
	name: string;
	source_path: string;
	node_count: number;
	edge_count: number;
}

export interface ModelConfig {
	name: string;
	provider?: string;
	parameters?: Record<string, unknown>;
}

export interface PromptMessage {
	role: string;
	content: string;
}

// Weighted sampler attribute configuration
export interface SamplerAttribute {
	values: (string | number)[];
	weights?: number[];
}

export interface SamplerConfig {
	attributes: Record<string, SamplerAttribute>;
}

// Inner graph structure for expanded subgraphs
export interface InnerGraph {
	name: string;
	nodes: WorkflowNode[];
	edges: WorkflowEdge[];
}

// Node configuration override for subgraph inner nodes
export interface NodeConfigOverride {
	model?: ModelConfig;
	prompt?: PromptMessage[];
	pre_process?: string;
	post_process?: string;
	prompt_placeholder_map?: Record<string, string>;
	[key: string]: unknown;
}

export interface WorkflowNode {
	id: string;
	node_type: 'data' | 'start' | 'end' | 'output' | 'llm' | 'agent' | 'lambda' | 'subgraph' | 'branch' | 'weighted_sampler';
	summary: string;
	description?: string;
	model?: ModelConfig;
	prompt?: PromptMessage[];
	pre_process?: string;
	post_process?: string;
	function_path?: string;
	subgraph_path?: string;
	inner_graph?: InnerGraph;  // Expanded subgraph contents
	node_config_map?: Record<string, NodeConfigOverride>;  // Override configs for inner nodes (subgraph only)
	position: { x: number; y: number };
	size?: { width: number; height: number };
	metadata?: Record<string, unknown>;
	// Data source specific fields
	data_config?: DataSourceConfig;
	// Output specific fields
	output_config?: OutputConfig;
	// Weighted sampler specific fields
	sampler_config?: SamplerConfig;
	// Tool calling fields (for LLM/Agent nodes)
	tools?: string[];
	tool_choice?: 'auto' | 'required' | 'none';
	// Output keys - state variable name(s) for this node's output
	output_keys?: string | string[];
}

export interface AvailableModel {
	name: string;
	model_type: string;
	model: string;
	parameters: Record<string, unknown>;
	output_type?: string;
	input_type?: string;
}

export interface EdgeCondition {
	condition_path: string;
	path_map: Record<string, string>;
}

export interface WorkflowEdge {
	id: string;
	source: string;
	target: string;
	label?: string;
	is_conditional: boolean;
	condition?: EdgeCondition;
}

// Data source configuration types (matches SyGra YAML structure)
export interface DataSourceDetails {
	type: 'hf' | 'disk' | 'servicenow';
	// HuggingFace
	repo_id?: string;
	config_name?: string;
	split?: string | string[];
	streaming?: boolean;
	// Disk/File
	file_path?: string;
	file_format?: string;
	encoding?: string;
	// ServiceNow
	table?: string;
	query?: string;
	fields?: string[];
	filters?: Record<string, unknown>;
	limit?: number;
	batch_size?: number;
	order_by?: string;
	// Transformations
	transformations?: Array<{
		transform: string;
		params?: Record<string, unknown>;
	}>;
}

export interface DataSinkDetails {
	type: 'hf' | 'disk' | 'servicenow' | 'json' | 'jsonl';
	alias?: string;
	// HuggingFace
	repo_id?: string;
	split?: string;
	// Disk/File
	file_path?: string;
	// ServiceNow
	table?: string;
	operation?: 'insert' | 'update';
}

export interface DataSourceConfig {
	source?: DataSourceDetails | DataSourceDetails[];
	sink?: DataSinkDetails | DataSinkDetails[];
	// Internal fields for code storage (stripped before save to YAML)
	_transform_code?: string;
}

export interface OutputConfig {
	type?: 'hf' | 'json' | 'jsonl' | 'csv' | 'parquet' | 'servicenow';
	file_path?: string;
	filename?: string;
	repo_id?: string;
	table?: string;
	generator?: string;
	output_map?: Record<string, { from?: string; value?: unknown; transform?: string }>;
	// Internal fields for code storage (stripped before save to YAML)
	_generator_code?: string;
}

export interface Workflow {
	id: string;
	name: string;
	description?: string;
	source_path: string;
	nodes: WorkflowNode[];
	edges: WorkflowEdge[];
	data_config?: DataSourceConfig;
	output_config?: OutputConfig;
	schema_config?: Record<string, unknown>;
	state_variables?: string[];
}

// Execution options matching main.py CLI arguments
export interface ExecutionOptions {
	inputData: Record<string, unknown>;
	startIndex: number;
	numRecords: number;
	batchSize: number;
	checkpointInterval: number;
	runName: string;
	outputWithTs: boolean;
	outputDir: string;
	debug: boolean;
	resume: boolean | null;
	quality: boolean;
	disableMetadata: boolean;
	runArgs: Record<string, unknown>;
}

export interface NodeExecutionState {
	status: 'pending' | 'running' | 'completed' | 'failed';
	started_at?: string;
	completed_at?: string;
	duration_ms?: number;
	error?: string;
}

export interface Execution {
	id: string;
	workflow_id: string;
	workflow_name: string;
	status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
	current_node?: string;
	started_at?: string;
	completed_at?: string;
	duration_ms?: number;
	input_data: Record<string, unknown>;
	output_data?: unknown;
	output_file?: string;
	metadata_file?: string;
	metadata?: ExecutionMetadata;
	node_states: Record<string, NodeExecutionState>;
	error?: string;
	logs: string[];
}

// Rich metadata from SyGra execution
export interface ExecutionMetadata {
	metadata_version: string;
	generated_at: string;
	execution: {
		task_name: string;
		run_name: string;
		output_dir: string;
		batch_size: number;
		checkpoint_interval: number;
		resumable?: boolean;
		debug: boolean;
		environment: {
			python_version: string;
			sygra_version: string;
		};
		git?: {
			commit_hash: string;
			branch: string;
			is_dirty: boolean;
		};
		timing: {
			start_time: string;
			end_time: string;
			duration_seconds: number;
		};
	};
	dataset: {
		source_type: string;
		source_path: string;
		num_records_processed: number;
		start_index: number;
		dataset_version: string;
		dataset_hash: string;
	};
	aggregate_statistics: {
		records: {
			total_processed: number;
			total_failed: number;
			success_rate: number;
		};
		tokens: {
			total_prompt_tokens: number;
			total_completion_tokens: number;
			total_tokens: number;
		};
		requests: {
			total_requests: number;
			total_retries: number;
			total_failures: number;
			retry_rate: number;
			failure_rate: number;
		};
		cost: {
			total_cost_usd: number;
			average_cost_per_record: number;
		};
	};
	models: Record<string, ModelMetrics>;
	nodes: Record<string, NodeMetrics>;
}

export interface ModelMetrics {
	model_name: string;
	model_type: string;
	model_url: string;
	token_statistics: {
		total_prompt_tokens: number;
		total_completion_tokens: number;
		total_tokens: number;
		avg_prompt_tokens: number;
		avg_completion_tokens: number;
		avg_total_tokens: number;
	};
	performance: {
		total_requests: number;
		total_retries: number;
		total_failures: number;
		failure_rate: number;
		total_latency_seconds: number;
		average_latency_seconds: number;
		tokens_per_second: number;
		latency_statistics: LatencyStats;
	};
	cost: {
		total_cost_usd: number;
		average_cost_per_request: number;
	};
	response_code_distribution: Record<string, number>;
	parameters: Record<string, unknown>;
}

export interface NodeMetrics {
	node_name: string;
	node_type: string;
	model_name?: string;
	total_executions: number;
	total_failures: number;
	failure_rate: number;
	total_latency_seconds: number;
	average_latency_seconds: number;
	latency_statistics: LatencyStats;
	token_statistics?: {
		total_prompt_tokens: number;
		total_completion_tokens: number;
		total_tokens: number;
		avg_prompt_tokens: number;
		avg_completion_tokens: number;
		avg_total_tokens: number;
	};
}

export interface LatencyStats {
	min: number;
	max: number;
	mean: number;
	median: number;
	std_dev: number;
	p50: number;
	p95: number;
	p99: number;
}

// Workflow Store
function createWorkflowStore() {
	let workflows = $state<WorkflowSummary[]>([]);
	let currentWorkflow = $state<Workflow | null>(null);
	let availableModels = $state<AvailableModel[]>([]);
	let loading = $state(false);

	// Version counter to force reactivity updates
	let workflowVersion = $state(0);

	// Undo/Redo state
	const MAX_UNDO_STACK = 50;
	const UNDO_THROTTLE_MS = 100; // Minimum time between undo states
	let undoStack = $state<Array<{ nodes: WorkflowNode[]; edges: WorkflowEdge[] }>>([]);
	let redoStack = $state<Array<{ nodes: WorkflowNode[]; edges: WorkflowEdge[] }>>([]);
	let lastUndoTime = 0;

	// Push current state to undo stack (call before making changes)
	function pushUndoState() {
		if (!currentWorkflow) return;

		// Throttle rapid undo state creation
		const now = Date.now();
		if (now - lastUndoTime < UNDO_THROTTLE_MS) {
			return; // Skip this state - too soon after the last one
		}
		lastUndoTime = now;

		// Deep clone current state using JSON (structuredClone can't handle some Svelte internals)
		const snapshot = {
			nodes: JSON.parse(JSON.stringify(currentWorkflow.nodes)),
			edges: JSON.parse(JSON.stringify(currentWorkflow.edges))
		};

		undoStack = [...undoStack.slice(-MAX_UNDO_STACK + 1), snapshot];
		// Clear redo stack when new action is taken
		redoStack = [];
	}
	let error = $state<string | null>(null);

	return {
		get workflows() { return workflows; },
		get currentWorkflow() { return currentWorkflow; },
		get workflowVersion() { return workflowVersion; },
		get availableModels() { return availableModels; },
		get loading() { return loading; },
		get error() { return error; },
		get canUndo() { return undoStack.length > 0; },
		get canRedo() { return redoStack.length > 0; },

		// Push state for undo (call before changes)
		pushUndo() {
			pushUndoState();
		},

		// Undo last action
		undo(): boolean {
			if (!currentWorkflow || undoStack.length === 0) return false;

			// Save current state to redo stack
			const currentSnapshot = {
				nodes: JSON.parse(JSON.stringify(currentWorkflow.nodes)),
				edges: JSON.parse(JSON.stringify(currentWorkflow.edges))
			};
			redoStack = [...redoStack, currentSnapshot];

			// Pop from undo stack and apply
			const previousState = undoStack[undoStack.length - 1];
			undoStack = undoStack.slice(0, -1);

			currentWorkflow = {
				...currentWorkflow,
				nodes: previousState.nodes,
				edges: previousState.edges
			};

			return true;
		},

		// Redo last undone action
		redo(): boolean {
			if (!currentWorkflow || redoStack.length === 0) return false;

			// Save current state to undo stack
			const currentSnapshot = {
				nodes: JSON.parse(JSON.stringify(currentWorkflow.nodes)),
				edges: JSON.parse(JSON.stringify(currentWorkflow.edges))
			};
			undoStack = [...undoStack, currentSnapshot];

			// Pop from redo stack and apply
			const nextState = redoStack[redoStack.length - 1];
			redoStack = redoStack.slice(0, -1);

			currentWorkflow = {
				...currentWorkflow,
				nodes: nextState.nodes,
				edges: nextState.edges
			};

			return true;
		},

		// Clear undo/redo history
		clearUndoHistory() {
			undoStack = [];
			redoStack = [];
		},

		async loadWorkflows() {
			loading = true;
			error = null;
			try {
				const response = await fetch(`${API_BASE}/workflows`);
				if (!response.ok) throw new Error('Failed to load workflows');
				workflows = await response.json();
			} catch (e) {
				error = e instanceof Error ? e.message : 'Unknown error';
			} finally {
				loading = false;
			}
		},

		async deleteWorkflow(id: string): Promise<boolean> {
			loading = true;
			error = null;
			try {
				const response = await fetch(`${API_BASE}/workflows/${id}`, {
					method: 'DELETE'
				});
				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || 'Failed to delete workflow');
				}
				// Remove from local list
				workflows = workflows.filter(w => w.id !== id);
				// Clear current workflow if it was the deleted one
				if (currentWorkflow?.id === id) {
					currentWorkflow = null;
				}
				return true;
			} catch (e) {
				error = e instanceof Error ? e.message : 'Unknown error';
				return false;
			} finally {
				loading = false;
			}
		},

		async renameWorkflow(id: string, newName: string): Promise<boolean> {
			loading = true;
			error = null;
			try {
				const response = await fetch(`${API_BASE}/workflows/${id}/rename`, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ name: newName })
				});
				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || 'Failed to rename workflow');
				}
				// Update in local list
				workflows = workflows.map(w => w.id === id ? { ...w, name: newName } : w);
				// Update current workflow if it's the renamed one
				if (currentWorkflow?.id === id) {
					currentWorkflow = { ...currentWorkflow, name: newName };
				}
				return true;
			} catch (e) {
				error = e instanceof Error ? e.message : 'Unknown error';
				return false;
			} finally {
				loading = false;
			}
		},

		async loadWorkflow(id: string): Promise<Workflow | null> {
			loading = true;
			error = null;
			try {
				const response = await fetch(`${API_BASE}/workflows/${id}`);
				if (!response.ok) throw new Error('Failed to load workflow');
				currentWorkflow = await response.json();
				workflowVersion++;
				return currentWorkflow;
			} catch (e) {
				error = e instanceof Error ? e.message : 'Unknown error';
				return null;
			} finally {
				loading = false;
			}
		},

		// Reload the current workflow from the backend (useful after YAML edits)
		async reloadCurrentWorkflow(): Promise<Workflow | null> {
			if (!currentWorkflow) return null;
			const id = currentWorkflow.id;
			if (id.startsWith('new_')) return currentWorkflow; // Can't reload new workflows

			try {
				const response = await fetch(`${API_BASE}/workflows/${id}`);
				if (!response.ok) throw new Error('Failed to reload workflow');
				const newWorkflow = await response.json();
				currentWorkflow = newWorkflow;
				workflowVersion++;
				return currentWorkflow;
			} catch (e) {
				console.error('[reloadCurrentWorkflow] Error:', e);
				error = e instanceof Error ? e.message : 'Unknown error';
				return null;
			}
		},

		async loadAvailableModels() {
			try {
				const response = await fetch(`${API_BASE}/models`);
				if (!response.ok) throw new Error('Failed to load models');
				const data = await response.json();
				availableModels = data.models || [];
			} catch (e) {
				console.error('Failed to load models:', e);
				availableModels = [];
			}
		},

		async updateNode(nodeId: string, nodeData: Partial<WorkflowNode> & { newId?: string }) {
			if (!currentWorkflow) {
				console.error('updateNode: No current workflow');
				return false;
			}

			// Extract newId if present (for renaming)
			const { newId, ...restNodeData } = nodeData;

			// Check if this is a new workflow (not yet saved to backend)
			const isNewWorkflow = currentWorkflow.id.startsWith('new_');

			// For new workflows, only update local state
			if (isNewWorkflow) {
				const nodeIndex = currentWorkflow.nodes.findIndex(n => n.id === nodeId);
				if (nodeIndex !== -1) {
					const finalId = newId || nodeId;

					// Create a new node object with updated data
					const updatedNode: WorkflowNode = {
						...currentWorkflow.nodes[nodeIndex],
						...restNodeData,
						id: finalId
					};

					// Create a new nodes array without mutating the original
					const newNodes = [
						...currentWorkflow.nodes.slice(0, nodeIndex),
						updatedNode,
						...currentWorkflow.nodes.slice(nodeIndex + 1)
					];

					// If ID changed, update all edges referencing this node
					if (newId && newId !== nodeId) {
						const updatedEdges = currentWorkflow.edges.map(edge => ({
							...edge,
							source: edge.source === nodeId ? newId : edge.source,
							target: edge.target === nodeId ? newId : edge.target
						}));
						currentWorkflow = {
							...currentWorkflow,
							nodes: newNodes,
							edges: updatedEdges
						};
					} else {
						currentWorkflow = {
							...currentWorkflow,
							nodes: newNodes
						};
					}

					// Increment version to force dependent $derived values to update
					workflowVersion++;
				}
				return true;
			}

			// For existing workflows, call the API
			try {
				// Include newId in the API request if present
				const apiData = newId ? { ...restNodeData, new_id: newId } : restNodeData;

				const response = await fetch(
					`${API_BASE}/workflows/${currentWorkflow.id}/nodes/${nodeId}`,
					{
						method: 'PUT',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify(apiData)
					}
				);

				if (!response.ok) {
					const errorData = await response.json();
					throw new Error(errorData.detail || 'Failed to update node');
				}

				const result = await response.json();

				// Update local state - create completely new arrays to ensure Svelte 5 reactivity
				const nodeIndex = currentWorkflow.nodes.findIndex(n => n.id === nodeId);
				if (nodeIndex !== -1) {
					const finalId = newId || nodeId;

					// Use API response data if available, otherwise fall back to sent data
					const apiNodeData = result.node || {};

					// Create a new node object with updated data (don't mutate existing)
					// Merge: existing node -> sent data -> API response data (most authoritative)
					const updatedNode: WorkflowNode = {
						...currentWorkflow.nodes[nodeIndex],
						...restNodeData,
						...(apiNodeData.model ? { model: apiNodeData.model } : {}),
						...(apiNodeData.summary !== undefined ? { summary: apiNodeData.summary } : {}),
						...(apiNodeData.description !== undefined ? { description: apiNodeData.description } : {}),
						...(apiNodeData.prompt !== undefined ? { prompt: apiNodeData.prompt } : {}),
						...(apiNodeData.pre_process !== undefined ? { pre_process: apiNodeData.pre_process } : {}),
						...(apiNodeData.post_process !== undefined ? { post_process: apiNodeData.post_process } : {}),
						...(apiNodeData.function_path !== undefined ? { function_path: apiNodeData.function_path } : {}),
						id: finalId
					};

					// Create a new nodes array without mutating the original
					const newNodes = [
						...currentWorkflow.nodes.slice(0, nodeIndex),
						updatedNode,
						...currentWorkflow.nodes.slice(nodeIndex + 1)
					];

					// If ID changed, update all edges referencing this node
					let updatedWorkflow: Workflow;
					if (newId && newId !== nodeId) {
						const updatedEdges = currentWorkflow.edges.map(edge => ({
							...edge,
							source: edge.source === nodeId ? newId : edge.source,
							target: edge.target === nodeId ? newId : edge.target
						}));
						updatedWorkflow = {
							...currentWorkflow,
							nodes: newNodes,
							edges: updatedEdges
						};
					} else {
						// Assign new workflow object with new nodes array
						updatedWorkflow = {
							...currentWorkflow,
							nodes: newNodes
						};
					}

					// Use spread to create new reference and trigger Svelte 5 reactivity
					currentWorkflow = { ...updatedWorkflow };

					// Increment version to force dependent $derived values to update
					workflowVersion++;
				}

				return true;
			} catch (e) {
				console.error('updateNode error:', e);
				error = e instanceof Error ? e.message : 'Unknown error';
				return false;
			}
		},

		async updateDataConfig(dataConfig: DataSourceConfig) {
			if (!currentWorkflow) {
				console.error('updateDataConfig: No current workflow');
				return false;
			}

			// Check if this is a new workflow (not yet saved to backend)
			const isNewWorkflow = currentWorkflow.id.startsWith('new_');

			// For new workflows, only update local state
			if (isNewWorkflow) {
				currentWorkflow = {
					...currentWorkflow,
					data_config: dataConfig
				};
				return true;
			}

			// For existing workflows, call the API
			try {
				const response = await fetch(
					`${API_BASE}/workflows/${currentWorkflow.id}/data-config`,
					{
						method: 'PUT',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify(dataConfig)
					}
				);

				if (!response.ok) {
					const errorData = await response.json();
					throw new Error(errorData.detail || 'Failed to update data config');
				}

				const _result = await response.json();

				// Update local state
				currentWorkflow = {
					...currentWorkflow,
					data_config: dataConfig
				};

				return true;
			} catch (e) {
				console.error('updateDataConfig error:', e);
				error = e instanceof Error ? e.message : 'Unknown error';
				return false;
			}
		},

		clearCurrentWorkflow() {
			currentWorkflow = null;
		},

		// Set a workflow directly (useful for duplicating)
		setCurrentWorkflow(workflow: Workflow) {
			currentWorkflow = workflow;
		},

		// Create a new empty workflow for the builder
		createNewWorkflow(name: string = 'New Workflow') {
			const id = `new_${Date.now()}`;
			currentWorkflow = {
				id,
				name,
				description: '',
				source_path: '',
				nodes: [
					{
						id: 'START',
						node_type: 'start',
						summary: 'Start',
						position: { x: 150, y: 300 }
					},
					{
						id: 'END',
						node_type: 'end',
						summary: 'End',
						position: { x: 900, y: 300 }
					}
				],
				edges: []
			};
			return currentWorkflow;
		},

		// Add a node to the current workflow
		addNode(nodeType: WorkflowNode['node_type'], position: { x: number; y: number }) {
			if (!currentWorkflow) return null;

			// Generate incremental ID: find the highest existing number for this node type
			const existingIds = currentWorkflow.nodes
				.filter(n => n.id.startsWith(`${nodeType}_`))
				.map(n => {
					const match = n.id.match(new RegExp(`^${nodeType}_(\\d+)$`));
					return match ? parseInt(match[1], 10) : 0;
				});
			const nextNum = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1;
			const id = `${nodeType}_${nextNum}`;

			const newNode: WorkflowNode = {
				id,
				node_type: nodeType,
				summary: nodeType.charAt(0).toUpperCase() + nodeType.slice(1),
				position
			};

			// Add default properties based on node type
			if (nodeType === 'llm') {
				newNode.model = { name: 'gpt-4o-mini', parameters: { temperature: 0.7 } };
				newNode.prompt = [{ role: 'system', content: '' }];
			} else if (nodeType === 'lambda') {
				newNode.function_path = '';
			}

			currentWorkflow = {
				...currentWorkflow,
				nodes: [...currentWorkflow.nodes, newNode]
			};

			return newNode;
		},

		// Add an edge to the current workflow
		addEdge(source: string, target: string, isConditional: boolean = false) {
			if (!currentWorkflow) return null;

			const id = `${source}-${target}`;
			// Check if edge already exists
			if (currentWorkflow.edges.some(e => e.id === id)) {
				return null;
			}

			const newEdge: WorkflowEdge = {
				id,
				source,
				target,
				is_conditional: isConditional
			};

			currentWorkflow = {
				...currentWorkflow,
				edges: [...currentWorkflow.edges, newEdge]
			};

			return newEdge;
		},

		// Add recipe as a subgraph node to the current workflow
		addRecipeToWorkflow(
			nodes: WorkflowNode[],
			edges: WorkflowEdge[],
			offsetPosition?: { x: number; y: number },
			recipeName?: string
		): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } | null {
			if (!currentWorkflow) return null;

			// Generate incremental subgraph ID
			const existingSubgraphIds = currentWorkflow.nodes
				.filter(n => n.id.startsWith('subgraph_'))
				.map(n => {
					const match = n.id.match(/^subgraph_(\d+)$/);
					return match ? parseInt(match[1], 10) : 0;
				});
			const nextSubgraphNum = existingSubgraphIds.length > 0 ? Math.max(...existingSubgraphIds) + 1 : 1;
			const offset = offsetPosition || { x: 400, y: 200 };

			// Normalize inner node positions to start from (0, 0)
			let minX = Infinity, minY = Infinity;
			for (const node of nodes) {
				minX = Math.min(minX, node.position.x);
				minY = Math.min(minY, node.position.y);
			}

			const innerNodes: WorkflowNode[] = nodes.map(node => ({
				...node,
				position: {
					x: node.position.x - minX + 20,  // Add padding
					y: node.position.y - minY + 20
				}
			}));

			// Create a single subgraph node containing the recipe
			const subgraphNode: WorkflowNode = {
				id: `subgraph_${nextSubgraphNum}`,
				node_type: 'subgraph',
				summary: recipeName || 'Imported Subgraph',
				position: offset,
				inner_graph: {
					name: recipeName || 'Subgraph',
					nodes: innerNodes,
					edges: edges
				}
			};

			currentWorkflow = {
				...currentWorkflow,
				nodes: [...currentWorkflow.nodes, subgraphNode],
				edges: currentWorkflow.edges
			};

			return { nodes: [subgraphNode], edges: [] };
		},

		// Expand a subgraph node into its inner nodes (detach from subgraph)
		expandSubgraph(subgraphNodeId: string): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } | null {
			if (!currentWorkflow) return null;

			const subgraphNode = currentWorkflow.nodes.find(n => n.id === subgraphNodeId);
			if (!subgraphNode || subgraphNode.node_type !== 'subgraph' || !subgraphNode.inner_graph) {
				return null;
			}

			const idMap = new Map<string, string>();
			const innerGraph = subgraphNode.inner_graph;

			// Track the next available ID for each node type
			const typeCounters = new Map<string, number>();

			// Initialize counters based on existing nodes in the workflow
			for (const existingNode of currentWorkflow.nodes) {
				const nodeType = existingNode.node_type;
				const match = existingNode.id.match(new RegExp(`^${nodeType}_(\\d+)$`));
				if (match) {
					const num = parseInt(match[1], 10);
					const current = typeCounters.get(nodeType) || 0;
					typeCounters.set(nodeType, Math.max(current, num));
				}
			}

			// Create new nodes with incremental IDs and offset by subgraph position
			const newNodes: WorkflowNode[] = innerGraph.nodes.map((node) => {
				const nodeType = node.node_type;
				const nextNum = (typeCounters.get(nodeType) || 0) + 1;
				typeCounters.set(nodeType, nextNum);
				const newId = `${nodeType}_${nextNum}`;
				idMap.set(node.id, newId);

				return {
					...node,
					id: newId,
					position: {
						x: node.position.x + subgraphNode.position.x,
						y: node.position.y + subgraphNode.position.y
					}
				};
			});

			// Create new edges with remapped IDs
			const newEdges: WorkflowEdge[] = innerGraph.edges
				.filter(edge => idMap.has(edge.source) && idMap.has(edge.target))
				.map(edge => ({
					...edge,
					id: `${idMap.get(edge.source)}-${idMap.get(edge.target)}`,
					source: idMap.get(edge.source)!,
					target: idMap.get(edge.target)!
				}));

			// Find edges connected to the subgraph node to reconnect
			const incomingEdges = currentWorkflow.edges.filter(e => e.target === subgraphNodeId);
			const outgoingEdges = currentWorkflow.edges.filter(e => e.source === subgraphNodeId);

			// Remove the subgraph node and its edges
			const remainingNodes = currentWorkflow.nodes.filter(n => n.id !== subgraphNodeId);
			const remainingEdges = currentWorkflow.edges.filter(
				e => e.source !== subgraphNodeId && e.target !== subgraphNodeId
			);

			currentWorkflow = {
				...currentWorkflow,
				nodes: [...remainingNodes, ...newNodes],
				edges: [...remainingEdges, ...newEdges]
			};

			return { nodes: newNodes, edges: newEdges };
		},

		// Remove a node from the current workflow
		removeNode(nodeId: string) {
			if (!currentWorkflow) return;
			if (nodeId === 'START' || nodeId === 'END') return; // Can't remove start/end

			currentWorkflow = {
				...currentWorkflow,
				nodes: currentWorkflow.nodes.filter(n => n.id !== nodeId),
				edges: currentWorkflow.edges.filter(e => e.source !== nodeId && e.target !== nodeId)
			};
		},

		// Delete a node (async version with return value)
		async deleteNode(nodeId: string): Promise<boolean> {
			if (!currentWorkflow) return false;
			if (nodeId === 'START' || nodeId === 'END') return false; // Can't remove start/end

			// Check if this is a new workflow (not yet saved to backend)
			const isNewWorkflow = currentWorkflow.id.startsWith('new_');

			try {
				// For existing workflows, call the API to persist changes
				if (!isNewWorkflow) {
					const response = await fetch(`${API_BASE}/workflows/${currentWorkflow.id}/nodes/${nodeId}`, {
						method: 'DELETE'
					});
					if (!response.ok) {
						const errorData = await response.json().catch(() => ({}));
						throw new Error(errorData.detail || 'Failed to delete node');
					}
					// Reload workflow from backend to get consistent state
					const reloadResponse = await fetch(`${API_BASE}/workflows/${currentWorkflow.id}`);
					if (reloadResponse.ok) {
						currentWorkflow = await reloadResponse.json();
						workflowVersion++;
						return true;
					}
				}

				// For new workflows or as fallback, update local state
				currentWorkflow = {
					...currentWorkflow,
					nodes: currentWorkflow.nodes.filter(n => n.id !== nodeId),
					edges: currentWorkflow.edges.filter(e => e.source !== nodeId && e.target !== nodeId)
				};
				workflowVersion++;
				return true;
			} catch (e) {
				console.error('Failed to delete node:', e);
				return false;
			}
		},

		// Remove an edge from the current workflow
		async removeEdge(edgeId: string): Promise<boolean> {
			if (!currentWorkflow) return false;

			// Try to find the edge with various ID formats
			let edgeToRemove = currentWorkflow.edges.find(e => e.id === edgeId);

			// If not found, try stripping xy-edge__ prefix
			if (!edgeToRemove && edgeId.startsWith('xy-edge__')) {
				const strippedId = edgeId.replace('xy-edge__', '');
				edgeToRemove = currentWorkflow.edges.find(e => e.id === strippedId);
			}

			// If still not found, try source-target lookup
			if (!edgeToRemove) {
				const idPart = edgeId.replace('xy-edge__', '');
				const lastDash = idPart.lastIndexOf('-');
				if (lastDash > 0) {
					const source = idPart.substring(0, lastDash);
					const target = idPart.substring(lastDash + 1);
					edgeToRemove = currentWorkflow.edges.find(e => e.source === source && e.target === target);
				}
			}

			if (!edgeToRemove) return false;

			// Check if this is a new workflow (not yet saved to backend)
			const isNewWorkflow = currentWorkflow.id.startsWith('new_');

			try {
				// For existing workflows, call the API to persist changes
				if (!isNewWorkflow) {
					// Use source-target format for edge ID
					const apiEdgeId = `${edgeToRemove.source}-${edgeToRemove.target}`;
					const response = await fetch(`${API_BASE}/workflows/${currentWorkflow.id}/edges/${apiEdgeId}`, {
						method: 'DELETE'
					});
					if (!response.ok) {
						const errorData = await response.json().catch(() => ({}));
						throw new Error(errorData.detail || 'Failed to delete edge');
					}
					// Reload workflow from backend to get consistent state
					const reloadResponse = await fetch(`${API_BASE}/workflows/${currentWorkflow.id}`);
					if (reloadResponse.ok) {
						currentWorkflow = await reloadResponse.json();
						workflowVersion++;
						return true;
					}
				}

				// For new workflows or as fallback, update local state
				currentWorkflow = {
					...currentWorkflow,
					edges: currentWorkflow.edges.filter(e => e.id !== edgeToRemove!.id)
				};
				workflowVersion++;
				return true;
			} catch (e) {
				console.error('Failed to delete edge:', e);
				return false;
			}
		},

		// Update an edge's properties (for conditional edges)
		updateEdge(edgeId: string, edgeData: Partial<WorkflowEdge>): boolean {
			if (!currentWorkflow) {
				return false;
			}

			// Try to find by ID first
			let edgeIndex = currentWorkflow.edges.findIndex(e => e.id === edgeId);

			// If not found, try to extract source-target from SvelteFlow's ID format (xy-edge__source-target)
			if (edgeIndex === -1 && edgeId.startsWith('xy-edge__')) {
				const strippedId = edgeId.replace('xy-edge__', '');
				edgeIndex = currentWorkflow.edges.findIndex(e => e.id === strippedId);
			}

			// If still not found, try to find by source-target pattern
			if (edgeIndex === -1) {
				// Parse source-target from the ID (format: source-target or xy-edge__source-target)
				const idPart = edgeId.replace('xy-edge__', '');
				const lastDash = idPart.lastIndexOf('-');
				if (lastDash > 0) {
					const source = idPart.substring(0, lastDash);
					const target = idPart.substring(lastDash + 1);
					edgeIndex = currentWorkflow.edges.findIndex(e => e.source === source && e.target === target);
				}
			}

			if (edgeIndex === -1) {
				return false;
			}

			const updatedEdge = {
				...currentWorkflow.edges[edgeIndex],
				...edgeData
			};

			const newEdges = [...currentWorkflow.edges];
			newEdges[edgeIndex] = updatedEdge;

			currentWorkflow = {
				...currentWorkflow,
				edges: newEdges
			};

			return true;
		},

		// Update node position
		updateNodePosition(nodeId: string, position: { x: number; y: number }) {
			if (!currentWorkflow) return;

			const nodeIndex = currentWorkflow.nodes.findIndex(n => n.id === nodeId);
			if (nodeIndex === -1) return;

			currentWorkflow.nodes[nodeIndex] = {
				...currentWorkflow.nodes[nodeIndex],
				position
			};
			currentWorkflow = { ...currentWorkflow, nodes: [...currentWorkflow.nodes] };
		},

		// Apply auto-layout using d3-dag Sugiyama algorithm
		applyAutoLayout() {
			if (!currentWorkflow) return;

			// Dynamic import to avoid SSR issues
			import('$lib/utils/layoutUtils').then(({ autoLayout, layoutAllInnerGraphs }) => {
				// First, recursively layout all inner graphs to get proper sizes
				const nodesWithInnerLayouts = layoutAllInnerGraphs(currentWorkflow!.nodes);

				// Then apply the main layout with accurate subgraph sizes
				const result = autoLayout(nodesWithInnerLayouts, currentWorkflow!.edges);

				currentWorkflow = {
					...currentWorkflow!,
					nodes: result.nodes
				};
			}).catch(e => {
				console.error('Failed to apply auto-layout:', e);
			});
		},

		// Save workflow to backend
		async saveWorkflow(workflowData?: Partial<Workflow> & { savePath?: string; filename?: string }): Promise<boolean> {
			if (!currentWorkflow) return false;

			// Extract save location params
			const { savePath, filename, ...restData } = workflowData || {};
			const dataToSave = restData ? { ...currentWorkflow, ...restData } : currentWorkflow;

			try {
				const isNew = currentWorkflow.id.startsWith('new_');
				const method = isNew ? 'POST' : 'PUT';
				const url = isNew
					? `${API_BASE}/workflows`
					: `${API_BASE}/workflows/${currentWorkflow.id}`;

				// Include save path in request body
				const requestBody = {
					...dataToSave,
					...(savePath && { save_path: savePath }),
					...(filename && { filename: filename })
				};

				const response = await fetch(url, {
					method,
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(requestBody)
				});

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({ detail: response.statusText }));
					throw new Error(errorData.detail || 'Failed to save workflow');
				}

				const result = await response.json();

				// Update current workflow with new ID, name, and source_path from save response
				if (result.success && result.workflow_id) {
					currentWorkflow = {
						...currentWorkflow,
						...restData,  // Include updated name, description, etc.
						id: result.workflow_id,
						source_path: result.source_path
					};
				}

				// Refresh workflow list
				await this.loadWorkflows();

				return true;
			} catch (e) {
				console.error('saveWorkflow error:', e);
				error = e instanceof Error ? e.message : 'Unknown error';
				return false;
			}
		},

		// Group selected nodes into a subgraph
		groupNodesAsSubgraph(
			nodeIds: string[],
			subgraphName: string,
			subgraphDescription?: string
		): WorkflowNode | null {
			if (!currentWorkflow) return null;
			if (nodeIds.length < 2) return null;

			// Get the nodes to group
			const nodesToGroup = currentWorkflow.nodes.filter(n => nodeIds.includes(n.id));
			if (nodesToGroup.length !== nodeIds.length) return null;

			// Validate: cannot include START, END, data, or output nodes
			const invalidNodes = nodesToGroup.filter(n =>
				n.id === 'START' || n.id === 'END' ||
				n.node_type === 'data' || n.node_type === 'output'
			);
			if (invalidNodes.length > 0) return null;

			const nodeIdSet = new Set(nodeIds);

			// Classify edges
			const internalEdges = currentWorkflow.edges.filter(e =>
				nodeIdSet.has(e.source) && nodeIdSet.has(e.target)
			);
			const incomingEdges = currentWorkflow.edges.filter(e =>
				nodeIdSet.has(e.target) && !nodeIdSet.has(e.source)
			);
			const outgoingEdges = currentWorkflow.edges.filter(e =>
				nodeIdSet.has(e.source) && !nodeIdSet.has(e.target)
			);

			// Calculate bounding box center for subgraph position
			const minX = Math.min(...nodesToGroup.map(n => n.position.x));
			const maxX = Math.max(...nodesToGroup.map(n => n.position.x));
			const minY = Math.min(...nodesToGroup.map(n => n.position.y));
			const maxY = Math.max(...nodesToGroup.map(n => n.position.y));
			const centerPosition = {
				x: (minX + maxX) / 2,
				y: (minY + maxY) / 2
			};

			// Create temporary inner nodes with relative positions for layout
			const tempInnerNodes: WorkflowNode[] = nodesToGroup.map(n => ({
				...n,
				position: {
					x: n.position.x - minX + 20,  // 20px padding
					y: n.position.y - minY + 20
				}
			}));

			// Create inner edges (same as internal edges but with new IDs)
			const innerEdges: WorkflowEdge[] = internalEdges.map(e => ({
				...e,
				id: `inner_${e.id}`
			}));

			// Apply auto-layout to inner nodes for proper arrangement
			const { nodes: layoutedInnerNodes, width: innerWidth, height: innerHeight } = layoutInnerGraph(
				tempInnerNodes,
				innerEdges
			);

			// Calculate subgraph dimensions based on laid out inner content
			const subgraphWidth = innerWidth + 40; // 40px total padding
			const subgraphHeight = innerHeight + 100; // 60px header + 40px padding

			// Generate incremental subgraph ID
			const existingSubgraphIds = currentWorkflow.nodes
				.filter(n => n.id.startsWith('subgraph_'))
				.map(n => {
					const match = n.id.match(/^subgraph_(\d+)$/);
					return match ? parseInt(match[1], 10) : 0;
				});
			const nextSubgraphNum = existingSubgraphIds.length > 0 ? Math.max(...existingSubgraphIds) + 1 : 1;
			const subgraphId = `subgraph_${nextSubgraphNum}`;
			const subgraphNode: WorkflowNode = {
				id: subgraphId,
				node_type: 'subgraph',
				summary: subgraphName,
				description: subgraphDescription,
				position: centerPosition,
				size: {
					width: subgraphWidth,
					height: subgraphHeight
				},
				inner_graph: {
					name: subgraphName,
					nodes: layoutedInnerNodes,
					edges: innerEdges
				}
			};

			// Create new edges to replace external connections
			const newEdges: WorkflowEdge[] = [];

			// Rewire incoming edges: external → subgraph
			const processedIncoming = new Set<string>();
			for (const edge of incomingEdges) {
				if (!processedIncoming.has(edge.source)) {
					newEdges.push({
						id: `${edge.source}-${subgraphId}`,
						source: edge.source,
						target: subgraphId,
						is_conditional: edge.is_conditional,
						label: edge.label
					});
					processedIncoming.add(edge.source);
				}
			}

			// Rewire outgoing edges: subgraph → external
			const processedOutgoing = new Set<string>();
			for (const edge of outgoingEdges) {
				if (!processedOutgoing.has(edge.target)) {
					newEdges.push({
						id: `${subgraphId}-${edge.target}`,
						source: subgraphId,
						target: edge.target,
						is_conditional: edge.is_conditional,
						label: edge.label
					});
					processedOutgoing.add(edge.target);
				}
			}

			// Update the workflow
			// 1. Remove grouped nodes
			// 2. Add subgraph node
			// 3. Remove internal and external edges
			// 4. Add new edges
			const remainingNodes = currentWorkflow.nodes.filter(n => !nodeIdSet.has(n.id));
			const remainingEdges = currentWorkflow.edges.filter(e =>
				!nodeIdSet.has(e.source) && !nodeIdSet.has(e.target)
			);

			currentWorkflow = {
				...currentWorkflow,
				nodes: [...remainingNodes, subgraphNode],
				edges: [...remainingEdges, ...newEdges]
			};

			return subgraphNode;
		}
	};
}

// Execution Store
function createExecutionStore() {
	let currentExecution = $state<Execution | null>(null);
	let executionHistory = $state<Execution[]>([]);
	let isPolling = $state(false);
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let currentPollingId: string | null = null;
	let isPaused = $state(false);

	// Pagination state
	let totalExecutions = $state(0);
	let hasMoreExecutions = $state(false);
	let isLoadingMore = $state(false);
	const PAGE_SIZE = 50;

	// Adaptive polling intervals
	const POLL_INTERVAL_FAST = 1000;   // 1 second when running
	const POLL_INTERVAL_SLOW = 3000;   // 3 seconds when pending/starting
	let currentPollInterval = POLL_INTERVAL_SLOW;

	return {
		get currentExecution() { return currentExecution; },
		get executionHistory() { return executionHistory; },
		get isPolling() { return isPolling; },
		get isPaused() { return isPaused; },
		get totalExecutions() { return totalExecutions; },
		get hasMoreExecutions() { return hasMoreExecutions; },
		get isLoadingMore() { return isLoadingMore; },

		async startExecution(workflowId: string, options: ExecutionOptions) {
			try {
				// Map frontend option names to backend snake_case
				const requestBody = {
					input_data: options.inputData,
					start_index: options.startIndex,
					num_records: options.numRecords,
					batch_size: options.batchSize,
					checkpoint_interval: options.checkpointInterval,
					run_name: options.runName,
					output_with_ts: options.outputWithTs,
					output_dir: options.outputDir || null,
					debug: options.debug,
					resume: options.resume,
					quality: options.quality,
					disable_metadata: options.disableMetadata,
					run_args: options.runArgs
				};

				const response = await fetch(`${API_BASE}/workflows/${workflowId}/execute`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(requestBody)
				});

				if (!response.ok) {
					const error = await response.json();
					throw new Error(error.detail || 'Failed to start execution');
				}

				const result = await response.json();
				currentExecution = {
					id: result.execution_id,
					workflow_id: workflowId,
					workflow_name: '',
					status: 'pending',
					input_data: options.inputData,
					node_states: {},
					logs: []
				};

				this.startPolling(result.execution_id);
				return result.execution_id;
			} catch (e) {
				throw e;
			}
		},

		startPolling(executionId: string) {
			if (pollInterval) clearInterval(pollInterval);
			isPolling = true;
			isPaused = false;
			currentPollingId = executionId;
			currentPollInterval = POLL_INTERVAL_SLOW; // Start with slow polling

			const poll = async () => {
				// Skip polling if paused
				if (isPaused) return;

				try {
					const response = await fetch(`${API_BASE}/executions/${executionId}`);
					if (response.ok) {
						const prevStatus = currentExecution?.status;
						currentExecution = await response.json();

						// Adaptive polling: speed up when running, slow down when pending
						const newInterval = currentExecution?.status === 'running'
							? POLL_INTERVAL_FAST
							: POLL_INTERVAL_SLOW;

						// Restart polling if interval changed
						if (newInterval !== currentPollInterval) {
							currentPollInterval = newInterval;
							if (pollInterval) {
								clearInterval(pollInterval);
								pollInterval = setInterval(poll, currentPollInterval);
							}
						}

						// Stop polling if execution is done
						if (currentExecution?.status === 'completed' ||
						    currentExecution?.status === 'failed' ||
						    currentExecution?.status === 'cancelled') {
							this.stopPolling();
							// Reload full execution history from server to get complete metadata
							await this.loadExecutionHistory();
						}
					}
				} catch (e) {
					console.error('Polling error:', e);
				}
			};

			poll(); // Initial poll
			pollInterval = setInterval(poll, currentPollInterval);
		},

		stopPolling() {
			if (pollInterval) {
				clearInterval(pollInterval);
				pollInterval = null;
			}
			isPolling = false;
			isPaused = false;
			currentPollingId = null;
		},

		// Pause polling when tab is hidden
		pausePolling() {
			if (isPolling && !isPaused) {
				isPaused = true;
				if (pollInterval) {
					clearInterval(pollInterval);
					pollInterval = null;
				}
			}
		},

		// Resume polling when tab becomes visible
		resumePolling() {
			if (isPaused && currentPollingId) {
				isPaused = false;
				this.startPolling(currentPollingId);
			}
		},

		async cancelExecution() {
			if (!currentExecution) return;

			try {
				const response = await fetch(`${API_BASE}/executions/${currentExecution.id}/cancel`, {
					method: 'POST'
				});

				if (response.ok) {
					this.stopPolling();
					// Update current execution status
					currentExecution = { ...currentExecution, status: 'cancelled' };
					// Reload execution history
					await this.loadExecutionHistory();
				}
			} catch (e) {
				console.error('Cancel error:', e);
			}
		},

		clearExecution() {
			this.stopPolling();
			currentExecution = null;
		},

		async loadExecutionHistory(workflowId?: string, limit: number = PAGE_SIZE, forceRefresh: boolean = false) {
			try {
				// Optionally refresh the storage index first (detects files added/deleted externally)
				if (forceRefresh) {
					await fetch(`${API_BASE}/executions/storage/refresh`, { method: 'POST' });
				}

				const url = workflowId
					? `${API_BASE}/executions?workflow_id=${workflowId}&limit=${limit}`
					: `${API_BASE}/executions?limit=${limit}`;
				const response = await fetch(url);
				if (response.ok) {
					const data = await response.json();
					// Handle both new paginated response and legacy array response
					if (Array.isArray(data)) {
						// Legacy response format (backward compatibility)
						executionHistory = data;
						totalExecutions = data.length;
						hasMoreExecutions = false;
					} else {
						// New paginated response format
						executionHistory = data.executions || [];
						totalExecutions = data.total || 0;
						hasMoreExecutions = data.has_more || false;
					}
				}
			} catch (e) {
				console.error('Failed to load execution history:', e);
			}
		},

		async loadMoreExecutions(workflowId?: string) {
			if (!hasMoreExecutions || isLoadingMore) return;

			isLoadingMore = true;
			try {
				const offset = executionHistory.length;
				const params = new URLSearchParams({
					limit: String(PAGE_SIZE),
					offset: String(offset)
				});
				if (workflowId) {
					params.set('workflow_id', workflowId);
				}

				const url = `${API_BASE}/executions?${params.toString()}`;
				const response = await fetch(url);
				if (response.ok) {
					const data = await response.json();
					if (!Array.isArray(data)) {
						// Append new executions to existing list
						const newExecutions = data.executions || [];
						executionHistory = [...executionHistory, ...newExecutions];
						totalExecutions = data.total || executionHistory.length;
						hasMoreExecutions = data.has_more || false;
					}
				}
			} catch (e) {
				console.error('Failed to load more executions:', e);
			} finally {
				isLoadingMore = false;
			}
		},

		async getExecution(executionId: string): Promise<Execution | null> {
			try {
				const response = await fetch(`${API_BASE}/executions/${executionId}`);
				if (response.ok) {
					return await response.json();
				}
				return null;
			} catch (e) {
				console.error('Failed to get execution:', e);
				return null;
			}
		},

		resumeRunningExecution() {
			// Find any running or pending executions from history and resume polling
			const runningExecution = executionHistory.find(
				e => e.status === 'running' || e.status === 'pending'
			);

			if (runningExecution) {
				currentExecution = runningExecution;
				this.startPolling(runningExecution.id);
			}
		},

		setCurrentExecution(execution: Execution | null) {
			currentExecution = execution;
		},

		async removeFromHistory(executionId: string): Promise<boolean> {
			try {
				// Call API to delete from disk storage
				const response = await fetch(`${API_BASE}/executions/${executionId}`, {
					method: 'DELETE'
				});

				if (!response.ok) {
					console.error('Failed to delete execution from storage:', await response.text());
					return false;
				}

				// Update local state
				executionHistory = executionHistory.filter(e => e.id !== executionId);
				totalExecutions = Math.max(0, totalExecutions - 1);

				// If the current execution is being removed, clear it
				if (currentExecution?.id === executionId) {
					currentExecution = null;
				}

				return true;
			} catch (e) {
				console.error('Failed to delete execution:', e);
				return false;
			}
		},

		async removeMultipleFromHistory(executionIds: string[]): Promise<boolean> {
			if (executionIds.length === 0) return true;

			try {
				// Call API to delete multiple executions from disk storage
				const response = await fetch(`${API_BASE}/executions`, {
					method: 'DELETE',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(executionIds)
				});

				if (!response.ok) {
					console.error('Failed to delete executions from storage:', await response.text());
					return false;
				}

				const result = await response.json();

				// Update local state
				const idsSet = new Set(executionIds);
				executionHistory = executionHistory.filter(e => !idsSet.has(e.id));
				totalExecutions = Math.max(0, totalExecutions - result.deleted_count);

				// If the current execution is being removed, clear it
				if (currentExecution && idsSet.has(currentExecution.id)) {
					currentExecution = null;
				}

				return result.deleted_count === executionIds.length;
			} catch (e) {
				console.error('Failed to delete executions:', e);
				return false;
			}
		}
	};
}

// View type for main content area
export type ViewType = 'home' | 'workflow' | 'workflows' | 'runs' | 'builder' | 'library' | 'models';

// Node type definitions for the builder
export const NODE_TYPES = [
	// Core Flow
	{ type: 'start', label: 'Start', color: '#22c55e', description: 'Entry point of the workflow', category: 'flow' },
	{ type: 'end', label: 'End', color: '#ef4444', description: 'Exit point of the workflow', category: 'flow' },
	// AI Nodes (tools are configured on these nodes via the Tools tab)
	{ type: 'llm', label: 'LLM', color: '#8b5cf6', description: 'Language model with optional tools', category: 'ai' },
	{ type: 'agent', label: 'Agent', color: '#ec4899', description: 'ReAct agent with tool calling', category: 'ai' },
	// Data
	{ type: 'data', label: 'Data', color: '#0ea5e9', description: 'Data source & sink configuration', category: 'data' },
	{ type: 'output', label: 'Output', color: '#10b981', description: 'Output mapping & generator', category: 'data' },
	// Processing
	{ type: 'lambda', label: 'Lambda', color: '#f97316', description: 'Custom Python function', category: 'processing' },
	{ type: 'weighted_sampler', label: 'Sampler', color: '#a855f7', description: 'Random weighted sampler', category: 'processing' },
	{ type: 'subgraph', label: 'Subgraph', color: '#3b82f6', description: 'Nested workflow', category: 'processing' },
] as const;

// Node categories for palette grouping
export const NODE_CATEGORIES = [
	{ id: 'flow', label: 'Flow Control', description: 'Start and end points' },
	{ id: 'ai', label: 'AI Nodes', description: 'LLM and agents with tools' },
	{ id: 'data', label: 'Data', description: 'Input/output handling' },
	{ id: 'processing', label: 'Processing', description: 'Transform and compute' },
] as const;

export type NodeType = typeof NODE_TYPES[number]['type'];
export type NodeCategory = typeof NODE_CATEGORIES[number]['id'];

// UI Store
function createUIStore() {
	let sidebarCollapsed = $state(false);
	let selectedNodeId = $state<string | null>(null);
	let showExecutionPanel = $state(false);
	let showResultsModal = $state(false);
	let showRunModal = $state(false);
	let currentView = $state<ViewType>('home');
	let selectedRunId = $state<string | null>(null);

	// Navigation guard for builder unsaved changes
	let pendingNavigation = $state<ViewType | null>(null);
	let builderHasChanges = $state(false);

	return {
		get sidebarCollapsed() { return sidebarCollapsed; },
		get selectedNodeId() { return selectedNodeId; },
		get showExecutionPanel() { return showExecutionPanel; },
		get showResultsModal() { return showResultsModal; },
		get showRunModal() { return showRunModal; },
		get currentView() { return currentView; },
		get selectedRunId() { return selectedRunId; },
		get pendingNavigation() { return pendingNavigation; },
		get builderHasChanges() { return builderHasChanges; },

		toggleSidebar() { sidebarCollapsed = !sidebarCollapsed; },
		selectNode(id: string | null) { selectedNodeId = id; },
		toggleExecutionPanel() { showExecutionPanel = !showExecutionPanel; },
		openResultsModal() { showResultsModal = true; },
		closeResultsModal() { showResultsModal = false; },
		openRunModal() { showRunModal = true; },
		closeRunModal() { showRunModal = false; },

		// Set builder has changes flag (called by WorkflowBuilder)
		setBuilderHasChanges(hasChanges: boolean) {
			builderHasChanges = hasChanges;
		},

		// Request navigation - may be blocked if builder has unsaved changes
		requestNavigation(view: ViewType) {
			if (currentView === 'builder' && builderHasChanges) {
				// Block navigation, show confirmation modal
				pendingNavigation = view;
				return false;
			}
			// Proceed with navigation
			this.setView(view);
			return true;
		},

		// Clear pending navigation (user cancelled)
		clearPendingNavigation() {
			pendingNavigation = null;
		},

		// Confirm pending navigation (user saved or discarded)
		confirmPendingNavigation() {
			if (pendingNavigation) {
				const view = pendingNavigation;
				pendingNavigation = null;
				builderHasChanges = false;
				this.setView(view);
			}
		},

		setView(view: ViewType) {
			currentView = view;
			if (view === 'runs' || view === 'workflows') {
				selectedRunId = null;
			}
			// Clear builder changes flag when leaving builder
			if (view !== 'builder') {
				builderHasChanges = false;
			}
		},
		selectRun(id: string | null) {
			selectedRunId = id;
		},
		clearSelectedRun() {
			selectedRunId = null;
		}
	};
}

// Export singleton instances
export const workflowStore = createWorkflowStore();
export const executionStore = createExecutionStore();
export const uiStore = createUIStore();
