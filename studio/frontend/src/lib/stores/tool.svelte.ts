/**
 * Tool Store - Manages reusable tools for LLM/Agent nodes
 *
 * Allows users to create, manage, and reuse tools across workflows.
 * Tools are Python functions decorated with @tool from langchain.
 */

const STORAGE_KEY = 'sygra_tools';

export type ToolCategory = 'search' | 'data' | 'api' | 'utility' | 'custom';

export interface Tool {
	id: string;
	name: string;
	description: string;
	category: ToolCategory;
	code: string;
	import_path: string;
	parameters?: ToolParameter[];
	createdAt: string;
	updatedAt: string;
	author?: string;
}

export interface ToolParameter {
	name: string;
	type: string;
	description: string;
	required: boolean;
	default?: string;
}

export interface ToolInput {
	name: string;
	description: string;
	category: ToolCategory;
	code: string;
	import_path: string;
	parameters?: ToolParameter[];
	author?: string;
}

// Generate unique ID
function generateId(): string {
	return `tool_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Tool Store using Svelte 5 Runes
function createToolStore() {
	let tools = $state<Tool[]>([]);
	let isLoading = $state(false);
	let searchQuery = $state('');
	let selectedCategory = $state<ToolCategory | 'all'>('all');

	// Check if we're in browser environment
	const isBrowser = typeof window !== 'undefined';

	// Load tools from localStorage
	function loadTools() {
		if (!isBrowser) return;
		try {
			const stored = localStorage.getItem(STORAGE_KEY);
			if (stored) {
				tools = JSON.parse(stored);
			}
		} catch (e) {
			console.error('Failed to load tools:', e);
			tools = [];
		}
	}

	// Save tools to localStorage
	function saveTools() {
		if (!isBrowser) return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(tools));
		} catch (e) {
			console.error('Failed to save tools:', e);
		}
	}

	// Initialize on first access
	loadTools();

	return {
		get tools() { return tools; },
		get isLoading() { return isLoading; },
		get searchQuery() { return searchQuery; },
		set searchQuery(value: string) { searchQuery = value; },
		get selectedCategory() { return selectedCategory; },
		set selectedCategory(value: ToolCategory | 'all') { selectedCategory = value; },

		// Filtered tools based on search and category
		get filteredTools() {
			let filtered = tools;

			// Filter by category
			if (selectedCategory !== 'all') {
				filtered = filtered.filter(t => t.category === selectedCategory);
			}

			// Filter by search query
			if (searchQuery.trim()) {
				const query = searchQuery.toLowerCase();
				filtered = filtered.filter(t =>
					t.name.toLowerCase().includes(query) ||
					t.description.toLowerCase().includes(query) ||
					t.import_path.toLowerCase().includes(query)
				);
			}

			return filtered;
		},

		// Add a new tool
		addTool(input: ToolInput): Tool {
			const tool: Tool = {
				id: generateId(),
				name: input.name,
				description: input.description,
				category: input.category,
				code: input.code,
				import_path: input.import_path,
				parameters: input.parameters,
				createdAt: new Date().toISOString(),
				updatedAt: new Date().toISOString(),
				author: input.author
			};

			tools = [tool, ...tools];
			saveTools();
			return tool;
		},

		// Update an existing tool
		updateTool(id: string, updates: Partial<ToolInput>): Tool | null {
			const index = tools.findIndex(t => t.id === id);
			if (index === -1) return null;

			const existing = tools[index];
			const updated: Tool = {
				...existing,
				...updates,
				updatedAt: new Date().toISOString()
			};

			tools = [...tools.slice(0, index), updated, ...tools.slice(index + 1)];
			saveTools();
			return updated;
		},

		// Delete a tool
		deleteTool(id: string): boolean {
			const index = tools.findIndex(t => t.id === id);
			if (index === -1) return false;

			tools = [...tools.slice(0, index), ...tools.slice(index + 1)];
			saveTools();
			return true;
		},

		// Get a tool by ID
		getTool(id: string): Tool | undefined {
			return tools.find(t => t.id === id);
		},

		// Get tool by import path
		getToolByPath(path: string): Tool | undefined {
			return tools.find(t => t.import_path === path);
		},

		// Duplicate a tool
		duplicateTool(id: string): Tool | null {
			const original = tools.find(t => t.id === id);
			if (!original) return null;

			return this.addTool({
				name: `${original.name} (Copy)`,
				description: original.description,
				category: original.category,
				code: original.code,
				import_path: `${original.import_path}_copy`,
				parameters: original.parameters ? [...original.parameters] : undefined,
				author: original.author
			});
		},

		// Export tool as JSON
		exportTool(id: string): string | null {
			const tool = tools.find(t => t.id === id);
			if (!tool) return null;
			return JSON.stringify(tool, null, 2);
		},

		// Import tool from JSON
		importTool(json: string): Tool | null {
			try {
				const data = JSON.parse(json);
				if (!data.name || !data.code || !data.import_path) {
					throw new Error('Invalid tool format');
				}

				return this.addTool({
					name: data.name,
					description: data.description || '',
					category: data.category || 'custom',
					code: data.code,
					import_path: data.import_path,
					parameters: data.parameters,
					author: data.author
				});
			} catch (e) {
				console.error('Failed to import tool:', e);
				return null;
			}
		},

		// Clear all tools
		clearAll() {
			tools = [];
			saveTools();
		},

		// Reload from storage
		reload() {
			loadTools();
		}
	};
}

// Export singleton store instance
export const toolStore = createToolStore();

// Category metadata for UI
export const TOOL_CATEGORIES: { value: ToolCategory; label: string; icon: string; color: string }[] = [
	{ value: 'search', label: 'Search', icon: 'search', color: '#52B8FF' },
	{ value: 'data', label: 'Data', icon: 'database', color: '#7661FF' },
	{ value: 'api', label: 'API', icon: 'globe', color: '#BF71F2' },
	{ value: 'utility', label: 'Utility', icon: 'wrench', color: '#0A4D6E' },
	{ value: 'custom', label: 'Custom', icon: 'puzzle', color: '#63DF4E' }
];

// Default tool template
export const DEFAULT_TOOL_CODE = `from langchain_core.tools import tool

@tool
def my_tool(query: str) -> str:
    """Description of what this tool does.

    Args:
        query: The input query to process.

    Returns:
        The result of processing the query.
    """
    # Implement your tool logic here
    return f"Processed: {query}"
`;
