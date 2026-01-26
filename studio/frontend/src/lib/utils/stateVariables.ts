/**
 * State Variables Utility
 *
 * Collects and manages state variables from the workflow graph.
 * Variables come from multiple sources:
 * - Data source columns (from data_config)
 * - Node output_keys (from upstream nodes)
 * - Weighted sampler attributes
 * - Framework-provided variables (messages, id, etc.)
 */

import type { Workflow, WorkflowNode, WorkflowEdge, DataSourceConfig } from '$lib/stores/workflow.svelte';

export interface StateVariable {
	name: string;
	source: 'data' | 'output' | 'sampler' | 'framework' | 'prompt';
	sourceNode?: string;  // Node ID that produces this variable
	description?: string;
}

export interface StateVariablesResult {
	variables: StateVariable[];
	bySource: {
		data: StateVariable[];
		output: StateVariable[];
		sampler: StateVariable[];
		framework: StateVariable[];
	};
}

/**
 * Framework-provided state variables that are always available
 */
const FRAMEWORK_VARIABLES: StateVariable[] = [
	{ name: 'messages', source: 'framework', description: 'Message history for the conversation' },
	{ name: 'id', source: 'framework', description: 'Record ID from data source' },
];

/**
 * Extract fields added by transformations (e.g., AddNewFieldTransform, RenameColumnsTransform)
 */
function extractTransformationFields(transformations?: any[]): string[] {
	if (!transformations || !Array.isArray(transformations)) return [];
	
	const fields: string[] = [];
	
	for (const transform of transformations) {
		const params = transform.params || {};
		
		// AddNewFieldTransform adds new columns from mapping keys
		// RenameColumnsTransform renames columns - mapping values are new names
		if (params.mapping && typeof params.mapping === 'object') {
			const transformName = transform.transform || '';
			
			if (transformName.includes('AddNewField') || transformName.includes('AddColumn')) {
				// For AddNewFieldTransform, mapping keys are the new column names
				fields.push(...Object.keys(params.mapping));
			} else if (transformName.includes('Rename')) {
				// For RenameColumnsTransform, mapping values are the new column names
				fields.push(...Object.values(params.mapping).filter((v): v is string => typeof v === 'string'));
			} else {
				// Generic case - assume mapping keys are new fields
				fields.push(...Object.keys(params.mapping));
			}
		}
		
		// Some transforms use 'columns' or 'new_columns' param
		if (params.new_columns && Array.isArray(params.new_columns)) {
			fields.push(...params.new_columns);
		}
		if (params.column && typeof params.column === 'string') {
			fields.push(params.column);
		}
	}
	
	return fields;
}

/**
 * Extract column names from data source configuration.
 * Uses fetchedColumns if available (from API), otherwise falls back to inline data.
 * 
 * When aliases are defined in multiple data sources, columns are transformed to
 * {alias}->{column} format to match the actual variable names used in prompts.
 * 
 * Also extracts fields added by transformations (e.g., AddNewFieldTransform).
 *
 * @param dataConfig The data source configuration
 * @param fetchedColumns Optional pre-fetched columns from the API (with transformations applied)
 */
function extractDataColumns(dataConfig?: DataSourceConfig, fetchedColumns?: string[]): StateVariable[] {
	const variables: StateVariable[] = [];

	// Check if we have multiple sources with aliases - in that case, we need special handling
	const sources = dataConfig?.source 
		? (Array.isArray(dataConfig.source) ? dataConfig.source : [dataConfig.source])
		: [];
	const hasMultipleSources = sources.length > 1;

	// If we have fetched columns (from API) and it's a simple single source scenario, use them directly
	if (fetchedColumns && fetchedColumns.length > 0 && !hasMultipleSources) {
		for (const colName of fetchedColumns) {
			if (!variables.some(v => v.name === colName)) {
				variables.push({
					name: colName,
					source: 'data',
					sourceNode: 'DATA',
					description: 'Column from data source'
				});
			}
		}
		
		// Also add transformation-added fields for single source
		if (sources.length > 0 && sources[0].transformations) {
			const transformFields = extractTransformationFields(sources[0].transformations);
			for (const fieldName of transformFields) {
				if (!variables.some(v => v.name === fieldName)) {
					variables.push({
						name: fieldName,
						source: 'data',
						sourceNode: 'DATA',
						description: 'Field added by transformation'
					});
				}
			}
		}
		
		return variables;
	}

	// For multiple sources with aliases, we need to handle each source separately
	// The API only returns columns for source_index=0 by default, so we use fetchedColumns
	// for the first source (with its alias) and extract from dataConfig for others.
	if (!dataConfig?.source) return [];

	// When there are multiple sources with aliases, extract columns from each source
	// and apply the alias->{column} notation

	for (let sourceIndex = 0; sourceIndex < sources.length; sourceIndex++) {
		const source = sources[sourceIndex];
		const alias = source.alias;
		let columnsForSource: string[] = [];
		
		// For the first source (index 0), use fetchedColumns if available
		// since the API returns columns for source_index=0 by default
		if (sourceIndex === 0 && fetchedColumns && fetchedColumns.length > 0) {
			columnsForSource = fetchedColumns;
		}
		// Extract from inline data (memory type)
		else if (source.data && Array.isArray(source.data) && source.data.length > 0) {
			const firstRecord = source.data[0];
			if (typeof firstRecord === 'object' && firstRecord !== null) {
				columnsForSource = Object.keys(firstRecord);
			}
		}
		// Extract from ServiceNow or other sources with explicit fields
		else if (source.fields && Array.isArray(source.fields)) {
			columnsForSource = source.fields;
		}
		
		// Add columns with proper alias notation
		for (const colName of columnsForSource) {
			// Use arrow notation for multiple sources with aliases
			const varName = (hasMultipleSources && alias) ? `${alias}->${colName}` : colName;
			if (!variables.some(v => v.name === varName)) {
				variables.push({
					name: varName,
					source: 'data',
					sourceNode: 'DATA',
					description: `Column from data source${alias ? ` (${alias})` : ''}`
				});
			}
		}
		
		// Add transformation-added fields for this source
		if (source.transformations) {
			const transformFields = extractTransformationFields(source.transformations);
			for (const fieldName of transformFields) {
				const varName = (hasMultipleSources && alias) ? `${alias}->${fieldName}` : fieldName;
				if (!variables.some(v => v.name === varName)) {
					variables.push({
						name: varName,
						source: 'data',
						sourceNode: 'DATA',
						description: `Field added by transformation${alias ? ` (${alias})` : ''}`
					});
				}
			}
		}
	}

	return variables;
}

/**
 * Extract output_keys from a node
 */
function extractOutputKeys(node: WorkflowNode): StateVariable[] {
	if (!node.output_keys) return [];

	const keys = Array.isArray(node.output_keys) ? node.output_keys : [node.output_keys];

	return keys.map(key => ({
		name: key,
		source: 'output' as const,
		sourceNode: node.id,
		description: `Output from ${node.summary || node.id}`
	}));
}

/**
 * Extract attributes from weighted sampler nodes
 */
function extractSamplerAttributes(node: WorkflowNode): StateVariable[] {
	if (node.node_type !== 'weighted_sampler' || !node.sampler_config?.attributes) {
		return [];
	}

	return Object.keys(node.sampler_config.attributes).map(attr => ({
		name: attr,
		source: 'sampler' as const,
		sourceNode: node.id,
		description: `Sampled attribute from ${node.summary || node.id}`
	}));
}

/**
 * Get upstream nodes for a given node (nodes that execute before it)
 * Uses topological ordering based on edges
 */
function getUpstreamNodes(nodeId: string, nodes: WorkflowNode[], edges: WorkflowEdge[]): Set<string> {
	const upstream = new Set<string>();
	const visited = new Set<string>();

	function traverse(currentId: string) {
		if (visited.has(currentId)) return;
		visited.add(currentId);

		// Find all edges that target this node
		const incomingEdges = edges.filter(e => e.target === currentId);

		for (const edge of incomingEdges) {
			if (edge.source !== 'START') {
				upstream.add(edge.source);
				traverse(edge.source);
			}
		}
	}

	traverse(nodeId);
	return upstream;
}

/**
 * Collect all state variables available for a specific node
 * Only includes variables from upstream nodes (that execute before this node)
 *
 * @param workflow The workflow containing nodes and edges
 * @param nodeId The ID of the node to collect variables for
 * @param fetchedColumns Optional pre-fetched columns from the API (with transformations applied)
 */
export function collectStateVariablesForNode(
	workflow: Workflow | null,
	nodeId: string,
	fetchedColumns?: string[]
): StateVariablesResult {
	const result: StateVariablesResult = {
		variables: [],
		bySource: {
			data: [],
			output: [],
			sampler: [],
			framework: []
		}
	};

	if (!workflow) return result;

	// Get upstream nodes
	const upstreamNodeIds = getUpstreamNodes(nodeId, workflow.nodes, workflow.edges);

	// Always include DATA node's variables if it exists
	const dataNode = workflow.nodes.find(n => n.node_type === 'data');
	if (dataNode) {
		const dataVars = extractDataColumns(dataNode.data_config, fetchedColumns);
		result.bySource.data.push(...dataVars);
		result.variables.push(...dataVars);
	}

	// Also check workflow-level data_config if no DATA node exists
	// We pass fetchedColumns here too so alias notation can be applied correctly
	if (workflow.data_config && !dataNode) {
		const workflowDataVars = extractDataColumns(workflow.data_config, fetchedColumns);
		for (const v of workflowDataVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.data.push(v);
				result.variables.push(v);
			}
		}
	}

	// Collect from upstream nodes
	for (const node of workflow.nodes) {
		if (!upstreamNodeIds.has(node.id) && node.id !== 'DATA') continue;

		// Output keys
		const outputVars = extractOutputKeys(node);
		for (const v of outputVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.output.push(v);
				result.variables.push(v);
			}
		}

		// Sampler attributes
		const samplerVars = extractSamplerAttributes(node);
		for (const v of samplerVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.sampler.push(v);
				result.variables.push(v);
			}
		}
	}

	// Add framework variables
	for (const v of FRAMEWORK_VARIABLES) {
		if (!result.variables.some(existing => existing.name === v.name)) {
			result.bySource.framework.push(v);
			result.variables.push(v);
		}
	}

	return result;
}

/**
 * Collect ALL state variables in the workflow (for overview purposes)
 */
export function collectAllStateVariables(workflow: Workflow | null): StateVariablesResult {
	const result: StateVariablesResult = {
		variables: [],
		bySource: {
			data: [],
			output: [],
			sampler: [],
			framework: []
		}
	};

	if (!workflow) return result;

	// Data node variables
	const dataNode = workflow.nodes.find(n => n.node_type === 'data');
	if (dataNode) {
		const dataVars = extractDataColumns(dataNode.data_config);
		result.bySource.data.push(...dataVars);
		result.variables.push(...dataVars);
	}

	// Workflow-level data_config
	if (workflow.data_config) {
		const workflowDataVars = extractDataColumns(workflow.data_config);
		for (const v of workflowDataVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.data.push(v);
				result.variables.push(v);
			}
		}
	}

	// All nodes
	for (const node of workflow.nodes) {
		// Output keys
		const outputVars = extractOutputKeys(node);
		for (const v of outputVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.output.push(v);
				result.variables.push(v);
			}
		}

		// Sampler attributes
		const samplerVars = extractSamplerAttributes(node);
		for (const v of samplerVars) {
			if (!result.variables.some(existing => existing.name === v.name)) {
				result.bySource.sampler.push(v);
				result.variables.push(v);
			}
		}
	}

	// Framework variables
	for (const v of FRAMEWORK_VARIABLES) {
		if (!result.variables.some(existing => existing.name === v.name)) {
			result.bySource.framework.push(v);
			result.variables.push(v);
		}
	}

	return result;
}

/**
 * Filter variables by search query
 */
export function filterVariables(variables: StateVariable[], query: string): StateVariable[] {
	if (!query) return variables;
	const lowerQuery = query.toLowerCase();
	return variables.filter(v =>
		v.name.toLowerCase().includes(lowerQuery) ||
		v.description?.toLowerCase().includes(lowerQuery)
	);
}

/**
 * Represents a variable reference found in a prompt
 */
export interface VariableReference {
	name: string;
	startIndex: number;
	endIndex: number;
	isValid: boolean;
	isEscaped: boolean;  // True if {{ or }}
}

/**
 * Validation result for a prompt
 */
export interface PromptValidationResult {
	isValid: boolean;
	references: VariableReference[];
	invalidReferences: VariableReference[];
	errors: PromptValidationError[];
}

export interface PromptValidationError {
	type: 'undefined_variable' | 'syntax_error';
	message: string;
	variableName?: string;
	position: { start: number; end: number };
}

/**
 * Parse a prompt string to extract all variable references.
 * Handles escaped braces ({{ and }}) correctly.
 *
 * Valid patterns:
 * - {variable_name} - variable reference
 * - {{literal}} - escaped, not a variable (renders as {literal})
 *
 * @param prompt The prompt string to parse
 * @returns Array of variable references found
 */
export function parseVariableReferences(prompt: string): VariableReference[] {
	const references: VariableReference[] = [];

	if (!prompt) return references;

	// Regex to match {word} but not {{word}} or {word}}
	// We need to be careful about escaped braces
	let i = 0;
	while (i < prompt.length) {
		// Check for escaped opening brace {{
		if (prompt[i] === '{' && prompt[i + 1] === '{') {
			// Find the closing }}
			let j = i + 2;
			let depth = 1;
			while (j < prompt.length && depth > 0) {
				if (prompt[j] === '{' && prompt[j + 1] === '{') {
					depth++;
					j++;
				} else if (prompt[j] === '}' && prompt[j + 1] === '}') {
					depth--;
					if (depth === 0) {
						// This is an escaped/literal brace, skip it
						references.push({
							name: prompt.substring(i + 2, j),
							startIndex: i,
							endIndex: j + 2,
							isValid: true,  // Escaped braces are always valid
							isEscaped: true
						});
						i = j + 2;
						break;
					}
					j++;
				}
				j++;
			}
			if (depth > 0) {
				// Unclosed escaped brace, move past the {{
				i += 2;
			}
			continue;
		}

		// Check for single opening brace {
		if (prompt[i] === '{') {
			const startIndex = i;
			i++;

			// Read the variable name (alphanumeric, underscore, dot allowed)
			let varName = '';
			while (i < prompt.length && prompt[i] !== '}' && prompt[i] !== '{' && prompt[i] !== '\n') {
				varName += prompt[i];
				i++;
			}

			// Check if properly closed with single }
			if (i < prompt.length && prompt[i] === '}') {
				// Make sure it's not }} (which would be an error in this context)
				const isDoubleClose = prompt[i + 1] === '}';

				if (!isDoubleClose && varName.trim()) {
					references.push({
						name: varName.trim(),
						startIndex,
						endIndex: i + 1,
						isValid: false,  // Will be validated later
						isEscaped: false
					});
				}
				i++;
			}
			// If not closed properly, just continue
			continue;
		}

		i++;
	}

	return references;
}

/**
 * Validate variable references in a prompt against available variables
 *
 * @param prompt The prompt string to validate
 * @param availableVariables List of valid variable names
 * @returns Validation result with errors
 */
export function validatePromptVariables(
	prompt: string,
	availableVariables: StateVariable[]
): PromptValidationResult {
	const references = parseVariableReferences(prompt);
	const availableNames = new Set(availableVariables.map(v => v.name));

	const errors: PromptValidationError[] = [];
	const invalidReferences: VariableReference[] = [];

	for (const ref of references) {
		// Skip escaped references (they're literal text)
		if (ref.isEscaped) {
			ref.isValid = true;
			continue;
		}

		// Check if variable exists
		if (availableNames.has(ref.name)) {
			ref.isValid = true;
		} else {
			ref.isValid = false;
			invalidReferences.push(ref);
			errors.push({
				type: 'undefined_variable',
				message: `Variable "{${ref.name}}" is not defined. Check if the upstream node has this output_key or if it's a valid data column.`,
				variableName: ref.name,
				position: { start: ref.startIndex, end: ref.endIndex }
			});
		}
	}

	return {
		isValid: errors.length === 0,
		references,
		invalidReferences,
		errors
	};
}

/**
 * Validate all prompts in a node
 * Handles both simple string content and multi-modal content (array of parts)
 */
export function validateNodePrompts(
	prompts: Array<{ role: string; content: string | Array<{ type: string; text?: string; audio_url?: string; image_url?: string; video_url?: string }> }> | undefined,
	availableVariables: StateVariable[]
): PromptValidationResult {
	if (!prompts || prompts.length === 0) {
		return { isValid: true, references: [], invalidReferences: [], errors: [] };
	}

	const allReferences: VariableReference[] = [];
	const allInvalidReferences: VariableReference[] = [];
	const allErrors: PromptValidationError[] = [];

	for (const prompt of prompts) {
		if (typeof prompt.content === 'string') {
			// Simple string content
			const result = validatePromptVariables(prompt.content, availableVariables);
			allReferences.push(...result.references);
			allInvalidReferences.push(...result.invalidReferences);
			allErrors.push(...result.errors);
		} else if (Array.isArray(prompt.content)) {
			// Multi-modal content - validate each part
			for (const part of prompt.content) {
				// Extract the text value from the part based on type
				let textValue: string | undefined;
				if (part.type === 'text') textValue = part.text;
				else if (part.type === 'audio_url') textValue = part.audio_url;
				else if (part.type === 'image_url') textValue = part.image_url;
				else if (part.type === 'video_url') textValue = part.video_url;
				
				if (textValue) {
					const result = validatePromptVariables(textValue, availableVariables);
					allReferences.push(...result.references);
					allInvalidReferences.push(...result.invalidReferences);
					allErrors.push(...result.errors);
				}
			}
		}
	}

	return {
		isValid: allErrors.length === 0,
		references: allReferences,
		invalidReferences: allInvalidReferences,
		errors: allErrors
	};
}
