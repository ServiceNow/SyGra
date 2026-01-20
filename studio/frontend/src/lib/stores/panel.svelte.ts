/**
 * Panel Store - Manages panel preferences and state persistence
 *
 * Persists:
 * - Panel widths (node and edge panels)
 * - Collapsed sections per node type
 * - Last active tab per node type
 */

const STORAGE_KEY = 'sygra_panel_preferences';

interface PanelPreferences {
	nodeWidth: number;
	edgeWidth: number;
	collapsedSections: Record<string, string[]>; // nodeType -> sectionIds
	lastTabByNodeType: Record<string, string>; // nodeType -> tabId
}

const DEFAULT_PREFERENCES: PanelPreferences = {
	nodeWidth: 640,
	edgeWidth: 640,
	collapsedSections: {},
	lastTabByNodeType: {}
};

function loadPreferences(): PanelPreferences {
	if (typeof window === 'undefined') return DEFAULT_PREFERENCES;

	try {
		const stored = localStorage.getItem(STORAGE_KEY);
		if (stored) {
			const parsed = JSON.parse(stored);
			return { ...DEFAULT_PREFERENCES, ...parsed };
		}
	} catch (e) {
		console.error('Failed to load panel preferences:', e);
	}
	return DEFAULT_PREFERENCES;
}

function savePreferences(prefs: PanelPreferences) {
	if (typeof window === 'undefined') return;

	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
	} catch (e) {
		console.error('Failed to save panel preferences:', e);
	}
}

function createPanelStore() {
	let preferences = $state<PanelPreferences>(DEFAULT_PREFERENCES);
	let initialized = $state(false);

	// Initialize from localStorage on mount
	function initialize() {
		if (initialized) return;
		preferences = loadPreferences();
		initialized = true;
	}

	return {
		// Getters
		get nodeWidth() {
			initialize();
			return preferences.nodeWidth;
		},
		get edgeWidth() {
			initialize();
			return preferences.edgeWidth;
		},

		// Width setters
		setNodeWidth(width: number) {
			initialize();
			const clampedWidth = Math.max(480, Math.min(1000, width));
			preferences = { ...preferences, nodeWidth: clampedWidth };
			savePreferences(preferences);
		},

		setEdgeWidth(width: number) {
			initialize();
			const clampedWidth = Math.max(480, Math.min(1000, width));
			preferences = { ...preferences, edgeWidth: clampedWidth };
			savePreferences(preferences);
		},

		// Collapsed sections
		isSectionCollapsed(nodeType: string, sectionId: string): boolean {
			initialize();
			return preferences.collapsedSections[nodeType]?.includes(sectionId) ?? false;
		},

		toggleSection(nodeType: string, sectionId: string) {
			initialize();
			const current = preferences.collapsedSections[nodeType] ?? [];
			const isCollapsed = current.includes(sectionId);

			const updated = isCollapsed
				? current.filter(id => id !== sectionId)
				: [...current, sectionId];

			preferences = {
				...preferences,
				collapsedSections: {
					...preferences.collapsedSections,
					[nodeType]: updated
				}
			};
			savePreferences(preferences);
		},

		setSectionCollapsed(nodeType: string, sectionId: string, collapsed: boolean) {
			initialize();
			const current = preferences.collapsedSections[nodeType] ?? [];
			const isCurrentlyCollapsed = current.includes(sectionId);

			if (collapsed === isCurrentlyCollapsed) return;

			const updated = collapsed
				? [...current, sectionId]
				: current.filter(id => id !== sectionId);

			preferences = {
				...preferences,
				collapsedSections: {
					...preferences.collapsedSections,
					[nodeType]: updated
				}
			};
			savePreferences(preferences);
		},

		// Last active tab
		getLastTab(nodeType: string): string | null {
			initialize();
			return preferences.lastTabByNodeType[nodeType] ?? null;
		},

		setLastTab(nodeType: string, tabId: string) {
			initialize();
			preferences = {
				...preferences,
				lastTabByNodeType: {
					...preferences.lastTabByNodeType,
					[nodeType]: tabId
				}
			};
			savePreferences(preferences);
		},

		// Reset
		resetPreferences() {
			preferences = { ...DEFAULT_PREFERENCES };
			savePreferences(preferences);
		}
	};
}

export const panelStore = createPanelStore();
