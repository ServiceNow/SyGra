/**
 * DAG Layout Utilities using d3-dag
 *
 * Provides automatic layout algorithms for workflow graph visualization.
 * Uses the Sugiyama algorithm for layered DAG layout.
 */

import * as d3dag from 'd3-dag';
import type { WorkflowNode, WorkflowEdge } from '$lib/stores/workflow.svelte';

// Layout configuration
export interface LayoutConfig {
	nodeWidth: number;
	nodeHeight: number;
	horizontalGap: number;
	verticalGap: number;
	direction: 'LR' | 'TB'; // Left-to-Right or Top-to-Bottom
}

const DEFAULT_CONFIG: LayoutConfig = {
	nodeWidth: 200,
	nodeHeight: 100,
	horizontalGap: 120,  // Better horizontal spacing
	verticalGap: 80,     // Better vertical spacing
	direction: 'LR'
};

// Subgraph nodes are larger
const SUBGRAPH_CONFIG = {
	nodeWidth: 350,
	nodeHeight: 250
};

/**
 * Get the dimensions for a node based on its type
 */
function getNodeDimensions(node: WorkflowNode, cfg: LayoutConfig): { width: number; height: number } {
	if (node.node_type === 'subgraph') {
		return { width: SUBGRAPH_CONFIG.nodeWidth, height: SUBGRAPH_CONFIG.nodeHeight };
	}
	return { width: cfg.nodeWidth, height: cfg.nodeHeight };
}

export interface LayoutResult {
	nodes: WorkflowNode[];
	width: number;
	height: number;
}

/**
 * Apply Sugiyama (layered) layout to workflow nodes using d3-dag.
 * This creates a clean, hierarchical visualization of the DAG.
 */
export function applyDagLayout(
	nodes: WorkflowNode[],
	edges: WorkflowEdge[],
	config: Partial<LayoutConfig> = {}
): LayoutResult {
	const cfg = { ...DEFAULT_CONFIG, ...config };

	if (nodes.length === 0) {
		return { nodes: [], width: 0, height: 0 };
	}

	// Build adjacency structure for d3-dag
	const nodeIds = new Set(nodes.map(n => n.id));
	const parentMap = new Map<string, string[]>();

	// Initialize all nodes with empty parent lists
	nodes.forEach(n => parentMap.set(n.id, []));

	// Build parent relationships from edges
	edges.forEach(edge => {
		if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
			const parents = parentMap.get(edge.target) || [];
			if (!parents.includes(edge.source)) {
				parents.push(edge.source);
			}
			parentMap.set(edge.target, parents);
		}
	});

	try {
		// Check for cycles first - d3-dag requires a true DAG
		if (hasCycles(nodes, edges)) {
			console.warn('Graph has cycles, using simple layout');
			return applySimpleLayout(nodes, edges, cfg);
		}

		// Create DAG using d3-dag's stratify
		const dagData = nodes.map(n => ({
			id: n.id,
			parentIds: parentMap.get(n.id) || []
		}));

		console.log('DAG data for d3-dag:', dagData);

		const dag = d3dag.graphStratify()(dagData);

		// Configure Sugiyama layout
		const nodeSize: [number, number] = cfg.direction === 'LR'
			? [cfg.nodeHeight + cfg.verticalGap, cfg.nodeWidth + cfg.horizontalGap]
			: [cfg.nodeWidth + cfg.horizontalGap, cfg.nodeHeight + cfg.verticalGap];

		const layout = d3dag.sugiyama()
			.nodeSize(nodeSize)
			.layering(d3dag.layeringSimplex())
			.decross(d3dag.decrossOpt())
			.coord(d3dag.coordQuad());

		// Apply layout
		layout(dag);

		console.log('d3-dag layout completed');

		// First pass: check if all nodes have valid coordinates
		// Note: d3-dag throws an error when accessing .x/.y if layout failed
		let hasValidCoords = true;
		for (const node of nodes) {
			const dagNode = dag.node(node.id);
			if (dagNode) {
				try {
					// After layout, x and y should be defined
					// d3-dag throws if ux/uy are undefined
					const x = dagNode.x;
					const y = dagNode.y;
					if (x === undefined || y === undefined || isNaN(x) || isNaN(y)) {
						hasValidCoords = false;
						break;
					}
				} catch {
					// d3-dag throws when coordinates aren't computed
					hasValidCoords = false;
					break;
				}
			} else {
				// Node not found in DAG
				hasValidCoords = false;
				break;
			}
		}

		// If any node has invalid coordinates, fall back to simple layout
		if (!hasValidCoords) {
			console.warn('d3-dag produced invalid coordinates, falling back to simple layout');
			return applySimpleLayout(nodes, edges, cfg);
		}

		// Extract positions and update nodes
		const layoutedNodes = nodes.map(node => {
			const dagNode = dag.node(node.id);
			if (dagNode) {
				// d3-dag uses (x, y) where x is layer position and y is within-layer position
				// For LR direction: x becomes horizontal, y becomes vertical
				const position = cfg.direction === 'LR'
					? { x: dagNode.x, y: dagNode.y }
					: { x: dagNode.y, y: dagNode.x };

				return {
					...node,
					position: {
						x: position.x + 50, // Add padding
						y: position.y + 50
					}
				};
			}
			return node;
		});

		// Calculate bounds
		let maxX = 0, maxY = 0;
		layoutedNodes.forEach(n => {
			maxX = Math.max(maxX, n.position.x + cfg.nodeWidth);
			maxY = Math.max(maxY, n.position.y + cfg.nodeHeight);
		});

		return {
			nodes: layoutedNodes,
			width: maxX + 100,
			height: maxY + 100
		};
	} catch (e) {
		console.warn('d3-dag layout failed, falling back to simple layout:', e);
		return applySimpleLayout(nodes, edges, cfg);
	}
}

/**
 * Simple fallback layout using topological sorting.
 * Used when d3-dag fails (e.g., for cyclic graphs).
 * Handles cycles by detecting strongly connected components.
 */
export function applySimpleLayout(
	nodes: WorkflowNode[],
	edges: WorkflowEdge[],
	config: Partial<LayoutConfig> = {}
): LayoutResult {
	const cfg = { ...DEFAULT_CONFIG, ...config };

	if (nodes.length === 0) {
		return { nodes: [], width: 0, height: 0 };
	}

	// Build adjacency and in-degree maps (ignoring back-edges for layering)
	const nodeIds = new Set(nodes.map(n => n.id));
	const adjacency = new Map<string, string[]>();
	const reverseAdjacency = new Map<string, string[]>();
	const inDegree = new Map<string, number>();

	nodes.forEach(n => {
		adjacency.set(n.id, []);
		reverseAdjacency.set(n.id, []);
		inDegree.set(n.id, 0);
	});

	// Track bidirectional edges (cycles between two nodes)
	const bidirectionalPairs = new Set<string>();
	edges.forEach(edge => {
		if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
			// Check if reverse edge exists
			const reverseKey = `${edge.target}->${edge.source}`;
			const forwardKey = `${edge.source}->${edge.target}`;
			if (edges.some(e => e.source === edge.target && e.target === edge.source)) {
				bidirectionalPairs.add([edge.source, edge.target].sort().join('<->'));
			}
			adjacency.get(edge.source)?.push(edge.target);
			reverseAdjacency.get(edge.target)?.push(edge.source);
		}
	});

	// For layering, ignore back-edges (edges that go from higher to lower nodes)
	// Use a modified Kahn's algorithm that breaks cycles
	const processedEdges = new Set<string>();
	edges.forEach(edge => {
		if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
			const pairKey = [edge.source, edge.target].sort().join('<->');
			// For bidirectional edges, only count one direction for in-degree
			if (bidirectionalPairs.has(pairKey)) {
				const edgeKey = `${edge.source}->${edge.target}`;
				if (!processedEdges.has(pairKey)) {
					// First edge of the pair - count it
					inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
					processedEdges.add(pairKey);
				}
				// Second edge (reverse) - don't count for in-degree
			} else {
				inDegree.set(edge.target, (inDegree.get(edge.target) || 0) + 1);
			}
		}
	});

	// Topological sort to determine layers
	const layers: string[][] = [];
	const nodeLayer = new Map<string, number>();
	const queue: string[] = [];
	const visited = new Set<string>();

	// Start with nodes that have no incoming edges
	nodes.forEach(n => {
		if ((inDegree.get(n.id) || 0) === 0) {
			queue.push(n.id);
		}
	});

	while (queue.length > 0) {
		const current = queue.shift()!;
		if (visited.has(current)) continue;
		visited.add(current);

		// Calculate layer based on predecessors
		let maxPredLayer = -1;
		reverseAdjacency.get(current)?.forEach(pred => {
			if (nodeLayer.has(pred)) {
				maxPredLayer = Math.max(maxPredLayer, nodeLayer.get(pred)!);
			}
		});

		const layer = maxPredLayer + 1;
		nodeLayer.set(current, layer);

		if (!layers[layer]) {
			layers[layer] = [];
		}
		layers[layer].push(current);

		// Process successors
		adjacency.get(current)?.forEach(successor => {
			if (!visited.has(successor)) {
				const newDegree = (inDegree.get(successor) || 0) - 1;
				inDegree.set(successor, Math.max(0, newDegree));
				if (newDegree <= 0) {
					queue.push(successor);
				}
			}
		});
	}

	// Handle remaining nodes (part of cycles or disconnected)
	nodes.forEach(n => {
		if (!nodeLayer.has(n.id)) {
			// Find the best layer based on neighbors
			let bestLayer = layers.length;
			const neighbors = [...(adjacency.get(n.id) || []), ...(reverseAdjacency.get(n.id) || [])];
			neighbors.forEach(neighbor => {
				if (nodeLayer.has(neighbor)) {
					bestLayer = Math.min(bestLayer, nodeLayer.get(neighbor)!);
				}
			});

			nodeLayer.set(n.id, bestLayer);
			if (!layers[bestLayer]) {
				layers[bestLayer] = [];
			}
			layers[bestLayer].push(n.id);
		}
	});

	// Group nodes in bidirectional relationships to same layer for better visualization
	bidirectionalPairs.forEach(pair => {
		const [node1, node2] = pair.split('<->');
		const layer1 = nodeLayer.get(node1);
		const layer2 = nodeLayer.get(node2);
		if (layer1 !== undefined && layer2 !== undefined && layer1 !== layer2) {
			// Move the later node to the same layer as earlier, but offset vertically
			const targetLayer = Math.min(layer1, layer2);
			const nodeToMove = layer1 > layer2 ? node1 : node2;
			const sourceLayer = Math.max(layer1, layer2);

			// Remove from old layer
			const oldLayerIdx = layers.findIndex(l => l.includes(nodeToMove));
			if (oldLayerIdx >= 0) {
				layers[oldLayerIdx] = layers[oldLayerIdx].filter(id => id !== nodeToMove);
			}

			// Add to new layer
			nodeLayer.set(nodeToMove, targetLayer);
			if (!layers[targetLayer].includes(nodeToMove)) {
				layers[targetLayer].push(nodeToMove);
			}
		}
	});

	// Clean up empty layers
	const cleanLayers = layers.filter(l => l && l.length > 0);

	// Create a node lookup map
	const nodeMap = new Map(nodes.map(n => [n.id, n]));

	// Calculate the max width for each layer (considering subgraph nodes)
	const layerWidths = cleanLayers.map(layerNodeIds => {
		let maxWidth = 0;
		layerNodeIds.forEach(nodeId => {
			const node = nodeMap.get(nodeId);
			if (node) {
				const dims = getNodeDimensions(node, cfg);
				maxWidth = Math.max(maxWidth, dims.width);
			}
		});
		return maxWidth;
	});

	// Calculate positions with better vertical distribution
	const nodePositions = new Map<string, { x: number; y: number }>();

	// Calculate max height needed for any layer
	let maxLayerHeight = 0;
	cleanLayers.forEach(layerNodeIds => {
		let layerHeight = 0;
		layerNodeIds.forEach(nodeId => {
			const node = nodeMap.get(nodeId);
			if (node) {
				const dims = getNodeDimensions(node, cfg);
				layerHeight += dims.height + cfg.verticalGap;
			}
		});
		maxLayerHeight = Math.max(maxLayerHeight, layerHeight);
	});

	const centerY = 100 + maxLayerHeight / 2;

	// Calculate cumulative x position for each layer
	let currentX = 100;
	cleanLayers.forEach((layerNodeIds, layerIdx) => {
		// Calculate total height of this layer
		let layerHeight = 0;
		layerNodeIds.forEach(nodeId => {
			const node = nodeMap.get(nodeId);
			if (node) {
				const dims = getNodeDimensions(node, cfg);
				layerHeight += dims.height + cfg.verticalGap;
			}
		});

		const startY = centerY - layerHeight / 2;
		let currentY = startY;

		layerNodeIds.forEach(nodeId => {
			const node = nodeMap.get(nodeId);
			if (node) {
				const dims = getNodeDimensions(node, cfg);
				nodePositions.set(nodeId, { x: currentX, y: currentY });
				currentY += dims.height + cfg.verticalGap;
			}
		});

		// Move x to next layer based on this layer's max width
		currentX += layerWidths[layerIdx] + cfg.horizontalGap;
	});

	// Update nodes with positions
	const layoutedNodes = nodes.map(node => ({
		...node,
		position: nodePositions.get(node.id) || node.position
	}));

	// Calculate bounds
	let maxX = 0, maxY = 0;
	layoutedNodes.forEach(n => {
		const dims = getNodeDimensions(n, cfg);
		maxX = Math.max(maxX, n.position.x + dims.width);
		maxY = Math.max(maxY, n.position.y + dims.height);
	});

	return {
		nodes: layoutedNodes,
		width: maxX + 100,
		height: maxY + 100
	};
}

/**
 * Check if the graph has cycles (for determining which layout to use)
 */
export function hasCycles(nodes: WorkflowNode[], edges: WorkflowEdge[]): boolean {
	const nodeIds = new Set(nodes.map(n => n.id));
	const adjacency = new Map<string, string[]>();
	const visited = new Set<string>();
	const recursionStack = new Set<string>();

	nodes.forEach(n => adjacency.set(n.id, []));
	edges.forEach(edge => {
		if (nodeIds.has(edge.source) && nodeIds.has(edge.target)) {
			adjacency.get(edge.source)?.push(edge.target);
		}
	});

	console.log('Checking for cycles. Edges:', edges.map(e => `${e.source} -> ${e.target}`));

	function dfs(nodeId: string): boolean {
		visited.add(nodeId);
		recursionStack.add(nodeId);

		for (const neighbor of adjacency.get(nodeId) || []) {
			if (!visited.has(neighbor)) {
				if (dfs(neighbor)) return true;
			} else if (recursionStack.has(neighbor)) {
				console.log(`Cycle detected: ${nodeId} -> ${neighbor} (${neighbor} is in recursion stack)`);
				return true;
			}
		}

		recursionStack.delete(nodeId);
		return false;
	}

	for (const node of nodes) {
		if (!visited.has(node.id)) {
			if (dfs(node.id)) return true;
		}
	}

	return false;
}

/**
 * Auto-layout the graph using the best available algorithm.
 */
export function autoLayout(
	nodes: WorkflowNode[],
	edges: WorkflowEdge[],
	config: Partial<LayoutConfig> = {}
): LayoutResult {
	// Try d3-dag first, fall back to simple layout
	return applyDagLayout(nodes, edges, config);
}
