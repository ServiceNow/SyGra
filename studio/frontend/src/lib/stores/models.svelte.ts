/**
 * Models Store - Tracks model status and provides shared state between Sidebar and ModelsView
 */

const API_BASE = '/api';

// Refresh interval in milliseconds (2 minutes)
const REFRESH_INTERVAL = 120000;

function createModelsStore() {
	let onlineCount = $state(0);
	let totalCount = $state(0);
	let lastRefresh = $state<Date | null>(null);
	let isRefreshing = $state(false);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	async function refreshCounts() {
		try {
			const res = await fetch(`${API_BASE}/models`);
			if (res.ok) {
				const data = await res.json();
				const models = data.models || [];
				totalCount = models.length;
				onlineCount = models.filter((m: any) => m.status === 'online').length;
				lastRefresh = new Date();
			}
		} catch (e) {
			console.error('Failed to refresh model counts:', e);
		}
	}

	function startAutoRefresh() {
		// Initial load
		refreshCounts();

		// Set up periodic refresh
		if (!refreshInterval) {
			refreshInterval = setInterval(refreshCounts, REFRESH_INTERVAL);
		}
	}

	function stopAutoRefresh() {
		if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	// Update counts directly (called by ModelsView after ping)
	function updateCounts(online: number, total: number) {
		onlineCount = online;
		totalCount = total;
		lastRefresh = new Date();
	}

	function setRefreshing(value: boolean) {
		isRefreshing = value;
	}

	return {
		get onlineCount() { return onlineCount; },
		get totalCount() { return totalCount; },
		get lastRefresh() { return lastRefresh; },
		get isRefreshing() { return isRefreshing; },

		refreshCounts,
		startAutoRefresh,
		stopAutoRefresh,
		updateCounts,
		setRefreshing
	};
}

export const modelsStore = createModelsStore();
