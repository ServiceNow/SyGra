/**
 * Recipe Store - Manages reusable workflow templates (recipes)
 *
 * Allows users to save subgraphs as recipes and reuse them in other workflows.
 * Persists to localStorage for now, can be extended to API backend later.
 */

import type { WorkflowNode, WorkflowEdge } from './workflow.svelte';

const STORAGE_KEY = 'sygra_recipes';

// Recipe categories for organization
export type RecipeCategory = 'llm' | 'data' | 'transform' | 'agent' | 'utility' | 'custom';

export interface Recipe {
	id: string;
	name: string;
	description: string;
	category: RecipeCategory;
	tags: string[];
	nodes: WorkflowNode[];
	edges: WorkflowEdge[];
	createdAt: string;
	updatedAt: string;
	author?: string;
	version: string;
	// Preview metadata
	nodeCount: number;
	edgeCount: number;
	nodeTypes: string[];
}

export interface RecipeInput {
	name: string;
	description: string;
	category: RecipeCategory;
	tags: string[];
	nodes: WorkflowNode[];
	edges: WorkflowEdge[];
	author?: string;
}

// Generate unique ID
function generateId(): string {
	return `recipe_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Normalize node positions to start from (0, 0)
function normalizePositions(nodes: WorkflowNode[]): WorkflowNode[] {
	if (nodes.length === 0) return nodes;

	const minX = Math.min(...nodes.map(n => n.position.x));
	const minY = Math.min(...nodes.map(n => n.position.y));

	return nodes.map(node => ({
		...node,
		position: {
			x: node.position.x - minX,
			y: node.position.y - minY
		}
	}));
}

// Recipe Store using Svelte 5 Runes
function createRecipeStore() {
	let recipes = $state<Recipe[]>([]);
	let isLoading = $state(false);
	let searchQuery = $state('');
	let selectedCategory = $state<RecipeCategory | 'all'>('all');

	// Check if we're in browser environment
	const isBrowser = typeof window !== 'undefined';

	// Load recipes from localStorage
	function loadRecipes() {
		if (!isBrowser) return;
		try {
			const stored = localStorage.getItem(STORAGE_KEY);
			if (stored) {
				recipes = JSON.parse(stored);
			}
		} catch (e) {
			console.error('Failed to load recipes:', e);
			recipes = [];
		}
	}

	// Save recipes to localStorage
	function saveRecipes() {
		if (!isBrowser) return;
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(recipes));
		} catch (e) {
			console.error('Failed to save recipes:', e);
		}
	}

	// Initialize on first access
	loadRecipes();

	return {
		get recipes() { return recipes; },
		get isLoading() { return isLoading; },
		get searchQuery() { return searchQuery; },
		set searchQuery(value: string) { searchQuery = value; },
		get selectedCategory() { return selectedCategory; },
		set selectedCategory(value: RecipeCategory | 'all') { selectedCategory = value; },

		// Filtered recipes based on search and category
		get filteredRecipes() {
			let filtered = recipes;

			// Filter by category
			if (selectedCategory !== 'all') {
				filtered = filtered.filter(r => r.category === selectedCategory);
			}

			// Filter by search query
			if (searchQuery.trim()) {
				const query = searchQuery.toLowerCase();
				filtered = filtered.filter(r =>
					r.name.toLowerCase().includes(query) ||
					r.description.toLowerCase().includes(query) ||
					r.tags.some(t => t.toLowerCase().includes(query))
				);
			}

			return filtered;
		},

		// Add a new recipe
		addRecipe(input: RecipeInput): Recipe {
			const normalizedNodes = normalizePositions(input.nodes);
			const nodeTypes = [...new Set(normalizedNodes.map(n => n.node_type))];

			const recipe: Recipe = {
				id: generateId(),
				name: input.name,
				description: input.description,
				category: input.category,
				tags: input.tags,
				nodes: normalizedNodes,
				edges: input.edges,
				createdAt: new Date().toISOString(),
				updatedAt: new Date().toISOString(),
				author: input.author,
				version: '1.0.0',
				nodeCount: normalizedNodes.length,
				edgeCount: input.edges.length,
				nodeTypes
			};

			recipes = [recipe, ...recipes];
			saveRecipes();
			return recipe;
		},

		// Update an existing recipe
		updateRecipe(id: string, updates: Partial<RecipeInput>): Recipe | null {
			const index = recipes.findIndex(r => r.id === id);
			if (index === -1) return null;

			const existing = recipes[index];
			const normalizedNodes = updates.nodes
				? normalizePositions(updates.nodes)
				: existing.nodes;
			const nodeTypes = [...new Set(normalizedNodes.map(n => n.node_type))];

			const updated: Recipe = {
				...existing,
				...updates,
				nodes: normalizedNodes,
				edges: updates.edges ?? existing.edges,
				updatedAt: new Date().toISOString(),
				nodeCount: normalizedNodes.length,
				edgeCount: (updates.edges ?? existing.edges).length,
				nodeTypes
			};

			recipes = [...recipes.slice(0, index), updated, ...recipes.slice(index + 1)];
			saveRecipes();
			return updated;
		},

		// Delete a recipe
		deleteRecipe(id: string): boolean {
			const index = recipes.findIndex(r => r.id === id);
			if (index === -1) return false;

			recipes = [...recipes.slice(0, index), ...recipes.slice(index + 1)];
			saveRecipes();
			return true;
		},

		// Get a recipe by ID
		getRecipe(id: string): Recipe | undefined {
			return recipes.find(r => r.id === id);
		},

		// Duplicate a recipe
		duplicateRecipe(id: string): Recipe | null {
			const original = recipes.find(r => r.id === id);
			if (!original) return null;

			return this.addRecipe({
				name: `${original.name} (Copy)`,
				description: original.description,
				category: original.category,
				tags: [...original.tags],
				nodes: JSON.parse(JSON.stringify(original.nodes)),
				edges: JSON.parse(JSON.stringify(original.edges)),
				author: original.author
			});
		},

		// Export recipe as JSON
		exportRecipe(id: string): string | null {
			const recipe = recipes.find(r => r.id === id);
			if (!recipe) return null;
			return JSON.stringify(recipe, null, 2);
		},

		// Import recipe from JSON
		importRecipe(json: string): Recipe | null {
			try {
				const data = JSON.parse(json);
				if (!data.name || !data.nodes || !data.edges) {
					throw new Error('Invalid recipe format');
				}

				return this.addRecipe({
					name: data.name,
					description: data.description || '',
					category: data.category || 'custom',
					tags: data.tags || [],
					nodes: data.nodes,
					edges: data.edges,
					author: data.author
				});
			} catch (e) {
				console.error('Failed to import recipe:', e);
				return null;
			}
		},

		// Clear all recipes
		clearAll() {
			recipes = [];
			saveRecipes();
		},

		// Reload from storage
		reload() {
			loadRecipes();
		}
	};
}

// Export singleton store instance
export const recipeStore = createRecipeStore();

// Category metadata for UI
export const RECIPE_CATEGORIES: { value: RecipeCategory; label: string; icon: string; color: string }[] = [
	{ value: 'llm', label: 'LLM Patterns', icon: 'brain', color: '#8b5cf6' },
	{ value: 'data', label: 'Data Processing', icon: 'database', color: '#3b82f6' },
	{ value: 'transform', label: 'Transformations', icon: 'shuffle', color: '#f59e0b' },
	{ value: 'agent', label: 'Agents', icon: 'bot', color: '#ec4899' },
	{ value: 'utility', label: 'Utilities', icon: 'wrench', color: '#6b7280' },
	{ value: 'custom', label: 'Custom', icon: 'puzzle', color: '#10b981' }
];
