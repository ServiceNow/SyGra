<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		Search, Plus, RefreshCw, Server, Check, X, AlertTriangle,
		Clock, Zap, Settings, Trash2, Edit3, ChevronDown, ChevronRight,
		Activity, Cloud, Cpu, Brain, MoreVertical, ExternalLink,
		LayoutList, LayoutGrid, CheckCircle2, XCircle, HelpCircle, AlertOctagon,
		Shield, Lock, ArrowUpDown, Info, Copy, Loader2, Eye
	} from 'lucide-svelte';
	import ConfirmationModal from '$lib/components/common/ConfirmationModal.svelte';
	import CustomSelect from '$lib/components/common/CustomSelect.svelte';
	import { modelsStore } from '$lib/stores/models.svelte';

	// Types
	interface ModelType {
		label: string;
		description: string;
		env_vars: string[];
	}

	interface ModelCredentials {
		[key: string]: string | boolean;
	}

	interface Model {
		name: string;
		model_type: string;
		model_type_label: string;
		model: string;
		description: string;
		parameters: Record<string, any>;
		api_version?: string;
		credentials: ModelCredentials;
		credentials_configured: boolean;
		status: 'online' | 'offline' | 'error' | 'unknown' | 'unconfigured' | 'timeout';
		status_code?: number;
		latency_ms?: number;
		last_checked?: string;
		error?: string;
		is_builtin?: boolean; // SyGra core models (read-only)
	}

	// State
	let models = $state<Model[]>([]);
	let modelTypes = $state<Record<string, ModelType>>({});
	let loading = $state(true);
	let pingingAll = $state(false);
	let searchQuery = $state('');
	let statusFilter = $state<string>('all');
	let typeFilter = $state<string>('all');
	let showEditor = $state(false);
	let editingModel = $state<Model | null>(null);
	let showDeleteConfirm = $state(false);
	let modelToDelete = $state<string | null>(null);

	// Context menu state
	let openMenuId = $state<string | null>(null);

	// Details modal state
	let showDetails = $state(false);
	let detailsModel = $state<Model | null>(null);

	// Recently checked models (for visual feedback)
	let recentlyChecked = $state<Map<string, 'success' | 'error'>>(new Map());

	// View mode (persisted)
	let viewMode = $state<'card' | 'list'>('card');

	// Sorting state
	let sortField = $state<'name' | 'model_type' | 'status' | 'latency'>('name');
	let sortDirection = $state<'asc' | 'desc'>('asc');

	// Form state
	let formName = $state('');
	let formModelType = $state('azure_openai');
	let formModel = $state('');
	let formApiVersion = $state('');
	let formCredentials = $state<Record<string, string>>({});
	let formParameters = $state<Array<{ key: string; value: string }>>([
		{ key: 'max_tokens', value: '1000' },
		{ key: 'temperature', value: '0.7' }
	]);
	let formError = $state('');

	// Additional model properties
	let formHfChatTemplateModelId = $state('');
	let formModelServingName = $state('');
	let formPostProcess = $state('');
	let formInputType = $state('');
	let formOutputType = $state('');

	// Custom properties (for arbitrary key-value pairs like image_capabilities)
	let formCustomProperties = $state<Array<{ key: string; value: string }>>([]);

	// Show advanced options
	let showAdvancedOptions = $state(false);

	// Stats
	let onlineCount = $derived(models.filter(m => m.status === 'online').length);
	let configuredCount = $derived(models.filter(m => m.credentials_configured).length);
	let needsConfigCount = $derived(models.filter(m => !m.credentials_configured).length);

	// Filtered models
	let filteredModels = $derived.by(() => {
		let result = [...models];

		// Status filter
		if (statusFilter === 'online') {
			result = result.filter(m => m.status === 'online');
		} else if (statusFilter === 'configured') {
			result = result.filter(m => m.credentials_configured && m.status !== 'online');
		} else if (statusFilter === 'needs_config') {
			result = result.filter(m => !m.credentials_configured);
		}

		// Type filter
		if (typeFilter !== 'all') {
			result = result.filter(m => m.model_type === typeFilter);
		}

		// Search
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(m =>
				m.name.toLowerCase().includes(q) ||
				m.model.toLowerCase().includes(q) ||
				m.model_type_label.toLowerCase().includes(q)
			);
		}

		// Sort
		result.sort((a, b) => {
			let comparison = 0;
			switch (sortField) {
				case 'name':
					comparison = a.name.localeCompare(b.name);
					break;
				case 'model_type':
					comparison = a.model_type_label.localeCompare(b.model_type_label);
					break;
				case 'status':
					// Order: online > configured > needs_config > error
					const statusOrder = (m: Model) => {
						if (m.status === 'online') return 0;
						if (m.credentials_configured && m.status !== 'error') return 1;
						if (!m.credentials_configured) return 2;
						return 3;
					};
					comparison = statusOrder(a) - statusOrder(b);
					break;
				case 'latency':
					comparison = (a.latency_ms || 9999999) - (b.latency_ms || 9999999);
					break;
			}
			return sortDirection === 'asc' ? comparison : -comparison;
		});

		return result;
	});

	// Grouped models for card view
	let onlineModels = $derived(filteredModels.filter(m => m.status === 'online'));
	let configuredModels = $derived(filteredModels.filter(m => m.credentials_configured && m.status !== 'online'));
	let needsConfigModels = $derived(filteredModels.filter(m => !m.credentials_configured));

	// Check if any filter is active
	let hasActiveFilters = $derived(searchQuery !== '' || statusFilter !== 'all' || typeFilter !== 'all');

	// Status filter options
	const statusOptions = [
		{ value: 'all', label: 'All Status' },
		{ value: 'online', label: '✓ Online' },
		{ value: 'configured', label: '● Configured' },
		{ value: 'needs_config', label: '○ Needs Config' }
	];

	// Type filter options (derived from loaded model types)
	let typeOptions = $derived.by(() => {
		const options = [{ value: 'all', label: 'All Types' }];
		for (const [type, info] of Object.entries(modelTypes)) {
			options.push({ value: type, label: info.label });
		}
		return options;
	});

	// Model type options for the form (no "All Types" option)
	let modelTypeFormOptions = $derived.by(() => {
		const options: { value: string; label: string }[] = [];
		for (const [type, info] of Object.entries(modelTypes)) {
			options.push({ value: type, label: info.label });
		}
		return options.length > 0 ? options : [{ value: 'azure_openai', label: 'Azure OpenAI' }];
	});

	// Track which models are being pinged individually
	let pingingModels = $state<Set<string>>(new Set());

	// AbortController for cancellable requests
	let abortController: AbortController | null = null;

	// Format last refresh time for display
	function formatLastRefresh(date: Date, _tick: number): string {
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffSec = Math.floor(diffMs / 1000);
		const diffMin = Math.floor(diffSec / 60);

		if (diffSec < 10) return 'just now';
		if (diffSec < 60) return `${diffSec}s ago`;
		if (diffMin < 60) return `${diffMin}m ago`;
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	// Tick counter to force refresh time updates (updates every 10 seconds)
	let timeTick = $state(0);
	let tickInterval: ReturnType<typeof setInterval> | null = null;

	// Load data on mount - fast, non-blocking
	onMount(() => {
		// Load view mode from localStorage
		const savedViewMode = localStorage.getItem('models-view-mode');
		if (savedViewMode === 'list' || savedViewMode === 'card') {
			viewMode = savedViewMode;
		}

		// Load data
		loadModelTypes();
		loadModels();

		// Start tick interval for updating "refreshed X ago" display
		tickInterval = setInterval(() => {
			timeTick++;
		}, 10000); // Update every 10 seconds
	});

	onDestroy(() => {
		if (abortController) abortController.abort();
		if (tickInterval) clearInterval(tickInterval);
	});

	function setViewMode(mode: 'card' | 'list') {
		viewMode = mode;
		localStorage.setItem('models-view-mode', mode);
	}

	function clearFilters() {
		searchQuery = '';
		statusFilter = 'all';
		typeFilter = 'all';
	}

	function toggleSort(field: typeof sortField) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	async function loadModels() {
		loading = true;
		try {
			const res = await fetch('/api/models');
			if (!res.ok) throw new Error('Failed to load models');
			const data = await res.json();
			models = data.models || [];

			// Update shared store with counts
			const onlineCount = models.filter(m => m.status === 'online').length;
			modelsStore.updateCounts(onlineCount, models.length);
		} catch (e) {
			console.error('Failed to load models:', e);
			models = [];
		} finally {
			loading = false;
		}
	}

	async function loadModelTypes() {
		try {
			const res = await fetch('/api/models/types');
			if (!res.ok) throw new Error('Failed to load model types');
			const data = await res.json();
			modelTypes = data.types || {};
		} catch (e) {
			console.error('Failed to load model types:', e);
		}
	}

	async function pingModel(modelName: string) {
		// Track this specific model as pinging
		pingingModels = new Set([...pingingModels, modelName]);

		// Clear any previous "recently checked" state
		const newRecentMap = new Map(recentlyChecked);
		newRecentMap.delete(modelName);
		recentlyChecked = newRecentMap;

		let checkResult: 'success' | 'error' = 'success';

		try {
			const controller = new AbortController();
			const timeoutId = setTimeout(() => controller.abort(), 20000); // 20s timeout

			const res = await fetch(`/api/models/${modelName}/ping`, {
				method: 'POST',
				signal: controller.signal
			});

			clearTimeout(timeoutId);

			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();

			// Update model in list (non-blocking update)
			models = models.map(m =>
				m.name === modelName
					? { ...m, status: data.status, status_code: data.status_code, latency_ms: data.latency_ms, last_checked: data.last_checked, error: data.error }
					: m
			);

			checkResult = data.status === 'online' ? 'success' : 'error';
		} catch (e: any) {
			checkResult = 'error';
			if (e.name === 'AbortError') {
				// Update with timeout error
				models = models.map(m =>
					m.name === modelName
						? { ...m, status: 'error', error: 'Request timeout', last_checked: new Date().toISOString() }
						: m
				);
			} else {
				console.error('Failed to ping model:', e);
				models = models.map(m =>
					m.name === modelName
						? { ...m, status: 'error', error: e.message || 'Ping failed', last_checked: new Date().toISOString() }
						: m
				);
			}
		} finally {
			// Remove from pinging set
			const newSet = new Set(pingingModels);
			newSet.delete(modelName);
			pingingModels = newSet;

			// Mark as recently checked for visual feedback
			const updatedRecentMap = new Map(recentlyChecked);
			updatedRecentMap.set(modelName, checkResult);
			recentlyChecked = updatedRecentMap;

			// Clear the "recently checked" state after 3 seconds
			setTimeout(() => {
				const clearMap = new Map(recentlyChecked);
				clearMap.delete(modelName);
				recentlyChecked = clearMap;
			}, 3000);
		}
	}

	function openDetails(model: Model) {
		detailsModel = model;
		showDetails = true;
	}

	function closeDetails() {
		showDetails = false;
		detailsModel = null;
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}

	async function pingAllModels() {
		if (pingingAll) return; // Prevent double-click

		pingingAll = true;
		modelsStore.setRefreshing(true);
		abortController = new AbortController();

		try {
			const timeoutId = setTimeout(() => abortController?.abort(), 30000); // 30s overall timeout

			const res = await fetch('/api/models/ping-all', {
				method: 'POST',
				signal: abortController.signal
			});

			clearTimeout(timeoutId);

			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();

			// Update all models with results
			models = models.map(m => {
				const result = data.results[m.name];
				return result ? { ...m, ...result } : m;
			});

			// Update shared store with new counts
			const onlineCount = models.filter(m => m.status === 'online').length;
			modelsStore.updateCounts(onlineCount, models.length);
		} catch (e: any) {
			if (e.name === 'AbortError') {
				console.log('Ping all cancelled');
			} else {
				console.error('Failed to ping all models:', e);
			}
		} finally {
			pingingAll = false;
			modelsStore.setRefreshing(false);
			abortController = null;
		}
	}

	function cancelPingAll() {
		if (abortController) {
			abortController.abort();
		}
	}

	function openEditor(model?: Model) {
		if (model) {
			editingModel = model;
			formName = model.name;
			formModelType = model.model_type;
			formModel = model.model;
			formApiVersion = model.api_version || '';

			// Convert parameters object to array format
			formParameters = Object.entries(model.parameters || {}).map(([key, value]) => ({
				key,
				value: typeof value === 'object' ? JSON.stringify(value) : String(value)
			}));
			if (formParameters.length === 0) {
				formParameters = [{ key: 'max_tokens', value: '1000' }, { key: 'temperature', value: '0.7' }];
			}

			// Initialize credentials from env keys
			formCredentials = {};
			const typeInfo = modelTypes[model.model_type];
			if (typeInfo) {
				for (const envVar of typeInfo.env_vars) {
					formCredentials[envVar] = '';
				}
			}

			// Load additional properties (these would need to come from the API)
			formHfChatTemplateModelId = (model as any).hf_chat_template_model_id || '';
			formModelServingName = (model as any).model_serving_name || '';
			formPostProcess = (model as any).post_process || '';
			formInputType = (model as any).input_type || '';
			formOutputType = (model as any).output_type || '';

			// Load custom properties (anything not in standard fields)
			const standardKeys = ['name', 'model_type', 'model', 'api_version', 'parameters', 'credentials',
				'hf_chat_template_model_id', 'model_serving_name', 'post_process', 'input_type', 'output_type',
				'model_type_label', 'description', 'credentials_configured', 'status', 'status_code', 'latency_ms', 'last_checked', 'error'];
			formCustomProperties = Object.entries(model)
				.filter(([key]) => !standardKeys.includes(key))
				.map(([key, value]) => ({
					key,
					value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
				}));

			showAdvancedOptions = !!(formHfChatTemplateModelId || formModelServingName || formPostProcess ||
				formInputType || formOutputType || formCustomProperties.length > 0);
		} else {
			editingModel = null;
			formName = '';
			formModelType = 'azure_openai';
			formModel = '';
			formApiVersion = '2024-08-01-preview';
			formParameters = [{ key: 'max_tokens', value: '1000' }, { key: 'temperature', value: '0.7' }];
			formCredentials = { URL: '', TOKEN: '' };
			formHfChatTemplateModelId = '';
			formModelServingName = '';
			formPostProcess = '';
			formInputType = '';
			formOutputType = '';
			formCustomProperties = [];
			showAdvancedOptions = false;
		}
		formError = '';
		showEditor = true;
	}

	function closeEditor() {
		showEditor = false;
		editingModel = null;
		formError = '';
	}

	// Helper to parse parameter value
	function parseParamValue(value: string): any {
		const trimmed = value.trim();
		// Try to parse as JSON first (for arrays, objects)
		try {
			return JSON.parse(trimmed);
		} catch {
			// Try as number
			const num = Number(trimmed);
			if (!isNaN(num) && trimmed !== '') return num;
			// Return as string
			return trimmed;
		}
	}

	// Add parameter
	function addParameter() {
		formParameters = [...formParameters, { key: '', value: '' }];
	}

	// Remove parameter
	function removeParameter(index: number) {
		formParameters = formParameters.filter((_, i) => i !== index);
	}

	// Add custom property
	function addCustomProperty() {
		formCustomProperties = [...formCustomProperties, { key: '', value: '' }];
	}

	// Remove custom property
	function removeCustomProperty(index: number) {
		formCustomProperties = formCustomProperties.filter((_, i) => i !== index);
	}

	async function saveModel() {
		formError = '';

		if (!formName.trim()) {
			formError = 'Model name is required';
			return;
		}

		if (!formModelType) {
			formError = 'Model type is required';
			return;
		}

		// Convert parameters array to object
		const parametersObj: Record<string, any> = {};
		for (const param of formParameters) {
			if (param.key.trim()) {
				parametersObj[param.key.trim()] = parseParamValue(param.value);
			}
		}

		// Build the model payload
		const payload: Record<string, any> = {
			name: formName.trim(),
			model_type: formModelType,
			model: formModel.trim() || formName.trim(),
			parameters: parametersObj,
			credentials: formCredentials
		};

		// Add optional standard fields
		if (formApiVersion.trim()) payload.api_version = formApiVersion.trim();
		if (formHfChatTemplateModelId.trim()) payload.hf_chat_template_model_id = formHfChatTemplateModelId.trim();
		if (formModelServingName.trim()) payload.model_serving_name = formModelServingName.trim();
		if (formPostProcess.trim()) payload.post_process = formPostProcess.trim();
		if (formInputType.trim()) payload.input_type = formInputType.trim();
		if (formOutputType.trim()) payload.output_type = formOutputType.trim();

		// Add custom properties
		for (const prop of formCustomProperties) {
			if (prop.key.trim()) {
				payload[prop.key.trim()] = parseParamValue(prop.value);
			}
		}

		try {
			const res = await fetch('/api/models', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				const data = await res.json();
				throw new Error(data.detail || 'Failed to save model');
			}

			await loadModels();
			closeEditor();
		} catch (e: any) {
			formError = e.message || 'Failed to save model';
		}
	}

	function requestDelete(modelName: string) {
		modelToDelete = modelName;
		showDeleteConfirm = true;
	}

	async function confirmDelete() {
		if (!modelToDelete) return;

		try {
			const res = await fetch(`/api/models/${modelToDelete}`, { method: 'DELETE' });
			if (res.ok) {
				models = models.filter(m => m.name !== modelToDelete);
			}
		} catch (e) {
			console.error('Failed to delete model:', e);
		} finally {
			showDeleteConfirm = false;
			modelToDelete = null;
		}
	}

	// Context menu functions
	let menuPosition = $state<{ x: number; top?: number; bottom?: number } | null>(null);

	function toggleMenu(e: MouseEvent, modelName: string) {
		e.stopPropagation();

		if (openMenuId === modelName) {
			openMenuId = null;
			menuPosition = null;
			return;
		}

		// Calculate position with viewport boundary detection
		const menuWidth = 208; // w-52 = 13rem = 208px
		const menuHeight = 280; // Approximate menu height
		const padding = 8;

		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		let x = rect.right;

		// Adjust if menu would go off right edge
		if (x + menuWidth + padding > window.innerWidth) {
			x = rect.left - menuWidth;
		}
		// Ensure x is not negative
		if (x < padding) {
			x = padding;
		}

		// Check if menu would go off bottom edge
		const spaceBelow = window.innerHeight - rect.bottom;
		const openUpward = spaceBelow < menuHeight + padding;

		openMenuId = modelName;

		if (openUpward) {
			// Use bottom positioning - menu's bottom aligns near button's top
			menuPosition = { x, bottom: window.innerHeight - rect.top + 4 };
		} else {
			// Use top positioning - menu's top aligns with button's bottom
			menuPosition = { x, top: rect.bottom + 4 };
		}
	}

	function closeMenu() {
		openMenuId = null;
		menuPosition = null;
	}

	function handleWindowClick() {
		if (openMenuId) {
			closeMenu();
		}
	}

	function toggleExpand(modelName: string) {
		const newSet = new Set(expandedModels);
		if (newSet.has(modelName)) {
			newSet.delete(modelName);
		} else {
			newSet.add(modelName);
		}
		expandedModels = newSet;
	}

	function getStatusColor(status: string): string {
		switch (status) {
			case 'online': return 'text-green-500';
			case 'error': return 'text-red-500';
			default: return 'text-gray-400';
		}
	}

	function getStatusBg(status: string): string {
		switch (status) {
			case 'online': return 'bg-green-100 dark:bg-green-900/30';
			case 'error': return 'bg-red-100 dark:bg-red-900/30';
			default: return 'bg-gray-100 dark:bg-gray-800';
		}
	}

	function getModelIcon(modelType: string) {
		switch (modelType) {
			case 'azure_openai':
			case 'openai':
				return Cloud;
			case 'ollama':
				return Cpu;
			case 'vllm':
			case 'tgi':
				return Server;
			case 'vertex_ai':
			case 'bedrock':
				return Cloud;
			default:
				return Brain;
		}
	}

	function formatLatency(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${Math.round(ms)}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	function formatTime(isoString?: string): string {
		if (!isoString) return 'Never';
		const date = new Date(isoString);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMins = Math.floor(diffMs / 60000);

		if (diffMins < 1) return 'Just now';
		if (diffMins < 60) return `${diffMins}m ago`;
		if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
		return date.toLocaleDateString();
	}

	// Update form credentials when model type changes - track previous type to avoid loops
	let prevFormModelType = $state('');

	$effect(() => {
		// Only update when model type actually changes (avoid infinite loop)
		if (formModelType && formModelType !== prevFormModelType && modelTypes[formModelType]) {
			prevFormModelType = formModelType;
			const typeInfo = modelTypes[formModelType];
			const newCreds: Record<string, string> = {};
			for (const envVar of typeInfo.env_vars) {
				newCreds[envVar] = '';  // Don't read from formCredentials to avoid loop
			}
			formCredentials = newCreds;
		}
	});
</script>

<svelte:window onclick={handleWindowClick} />

<div class="h-full w-full flex flex-col bg-white dark:bg-gray-900">
	<!-- Header -->
	<div class="flex-shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
		<div class="flex items-center justify-between mb-4">
			<div>
				<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Models</h1>
				<p class="text-sm text-gray-500 dark:text-gray-400">
					{filteredModels.length} of {models.length} models
					{#if onlineCount > 0}
						<span class="ml-2 text-green-600 dark:text-green-400">• {onlineCount} online</span>
					{/if}
					{#if needsConfigCount > 0}
						<span class="ml-2 text-amber-600 dark:text-amber-400">• {needsConfigCount} need config</span>
					{/if}
					{#if modelsStore.lastRefresh}
						<span class="ml-2 text-gray-400">|</span>
						<span class="ml-2 text-gray-400">refreshed {formatLastRefresh(modelsStore.lastRefresh, timeTick)}</span>
					{/if}
				</p>
			</div>
			<div class="flex items-center gap-2">
				<!-- View Mode Toggle -->
				<div class="flex items-center bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
					<button
						onclick={() => setViewMode('card')}
						class="p-2 rounded-md transition-colors {viewMode === 'card' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
						title="Card view"
					>
						<LayoutGrid size={18} />
					</button>
					<button
						onclick={() => setViewMode('list')}
						class="p-2 rounded-md transition-colors {viewMode === 'list' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'}"
						title="List view"
					>
						<LayoutList size={18} />
					</button>
				</div>

				<div class="w-px h-6 bg-gray-200 dark:bg-gray-700"></div>

				{#if pingingAll}
					<button
						onclick={cancelPingAll}
						class="flex items-center gap-2 px-3 py-2 border border-red-300 dark:border-red-600 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 rounded-lg transition-colors text-sm"
					>
						<X size={16} />
						Cancel
					</button>
				{/if}
				<button
					onclick={() => pingAllModels()}
					disabled={pingingAll}
					class="flex items-center gap-2 px-3 py-2 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg transition-colors text-sm disabled:opacity-50"
				>
					<RefreshCw size={16} class={pingingAll ? 'animate-spin' : ''} />
					{pingingAll ? 'Refreshing...' : 'Refresh'}
				</button>
				<button
					onclick={() => openEditor()}
					class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors text-sm"
				>
					<Plus size={16} />
					Add Model
				</button>
			</div>
		</div>

		<!-- Filters -->
		<div class="flex flex-wrap items-center gap-3">
			<!-- Search -->
			<div class="relative flex-1 min-w-64 max-w-md">
				<Search size={16} class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
				<input
					type="text"
					placeholder="Search models..."
					bind:value={searchQuery}
					class="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
				/>
			</div>

			<!-- Status Filter -->
			<CustomSelect
				options={statusOptions}
				bind:value={statusFilter}
				placeholder="All Status"
				searchable={false}
				class="w-40"
			/>

			<!-- Type Filter -->
			<CustomSelect
				options={typeOptions}
				bind:value={typeFilter}
				placeholder="All Types"
				searchable={typeOptions.length > 5}
				searchPlaceholder="Search types..."
				class="w-44"
			/>

			{#if hasActiveFilters}
				<button
					onclick={clearFilters}
					class="flex items-center gap-1.5 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
				>
					<X size={14} />
					Clear filters
				</button>
			{/if}
		</div>
	</div>

	<!-- Models List -->
	<div class="flex-1 overflow-auto">
		{#if loading}
			<div class="flex items-center justify-center h-full p-6">
				<RefreshCw size={24} class="animate-spin text-violet-500" />
			</div>
		{:else if filteredModels.length === 0}
			<div class="flex flex-col items-center justify-center h-full text-center p-6">
				<Brain size={48} class="text-gray-300 dark:text-gray-600 mb-4" />
				{#if models.length === 0}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No models configured</h3>
					<p class="text-sm text-gray-500 mb-4 max-w-md">
						Add LLM models to use in your workflows. Configure API endpoints, credentials, and parameters.
					</p>
					<button
						onclick={() => openEditor()}
						class="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm"
					>
						<Plus size={16} />
						Add Your First Model
					</button>
				{:else}
					<h3 class="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">No matching models</h3>
					<p class="text-sm text-gray-500">Try adjusting your search or filters</p>
				{/if}
			</div>
		{:else if viewMode === 'list'}
			<!-- List View -->
			<table class="w-full">
				<thead class="sticky top-0 bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
					<tr>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('name')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Model
								<ArrowUpDown size={14} class={sortField === 'name' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('model_type')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Type
								<ArrowUpDown size={14} class={sortField === 'model_type' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('status')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Status
								<ArrowUpDown size={14} class={sortField === 'status' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-left px-6 py-3">
							<button
								onclick={() => toggleSort('latency')}
								class="flex items-center gap-1 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider hover:text-gray-700 dark:hover:text-gray-200"
							>
								Latency
								<ArrowUpDown size={14} class={sortField === 'latency' ? 'text-violet-500' : ''} />
							</button>
						</th>
						<th class="text-right px-6 py-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-200 dark:divide-gray-800">
					{#each filteredModels as model (model.name)}
						{@const Icon = getModelIcon(model.model_type)}
						<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
							<td class="px-6 py-4">
								<div class="flex items-center gap-3">
									<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
										<Icon size={20} class="text-violet-600 dark:text-violet-400" />
									</div>
									<div>
										<div class="flex items-center gap-2">
											<span class="font-medium text-gray-900 dark:text-gray-100">{model.name}</span>
											{#if model.is_builtin}
												<span class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-medium" title="SyGra builtin model (read-only)">
													<Shield size={10} />
													SyGra
												</span>
											{/if}
										</div>
										<div class="text-xs text-gray-500 font-mono">{model.model}</div>
									</div>
								</div>
							</td>
							<td class="px-6 py-4">
								<span class="text-sm text-gray-600 dark:text-gray-400">{model.model_type_label}</span>
							</td>
							<td class="px-6 py-4">
								{#if pingingModels.has(model.name)}
									<!-- Checking status -->
									<span class="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 animate-pulse">
										<Loader2 size={12} class="animate-spin" />
										Checking...
									</span>
								{:else if recentlyChecked.has(model.name)}
									<!-- Just checked - show result briefly -->
									{@const result = recentlyChecked.get(model.name)}
									{#if result === 'success'}
										<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 ring-2 ring-green-300 dark:ring-green-600 ring-opacity-50">
											<CheckCircle2 size={12} />
											Online
										</span>
									{:else}
										<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 ring-2 ring-red-300 dark:ring-red-600 ring-opacity-50">
											<XCircle size={12} />
											{model.status}
										</span>
									{/if}
								{:else if !model.credentials_configured}
									<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
										<AlertTriangle size={12} />
										Needs Config
									</span>
								{:else if model.status === 'online'}
									<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
										<CheckCircle2 size={12} />
										Online
									</span>
								{:else if model.status === 'offline' || model.status === 'error'}
									<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
										<XCircle size={12} />
										{model.status}
									</span>
								{:else}
									<span class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
										<HelpCircle size={12} />
										Unknown
									</span>
								{/if}
							</td>
							<td class="px-6 py-4 text-sm text-gray-500">
								{#if pingingModels.has(model.name)}
									<span class="text-violet-500 animate-pulse">...</span>
								{:else}
									{model.latency_ms ? formatLatency(model.latency_ms) : '-'}
								{/if}
							</td>
							<td class="px-6 py-4">
								<div class="flex items-center justify-end gap-2">
									<!-- Three-dot menu -->
									<button
										onclick={(e) => toggleMenu(e, model.name)}
										class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400 transition-colors"
										title="More options"
									>
										<MoreVertical size={16} />
									</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{:else}
			<!-- Card View with Groups -->
			<div class="space-y-8 p-6">
				<!-- Online Models -->
				{#if onlineModels.length > 0}
					<div>
						<div class="flex items-center gap-2 mb-3">
							<CheckCircle2 size={18} class="text-green-500" />
							<h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">Online ({onlineModels.length})</h2>
						</div>
						<div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
							{#each onlineModels as model (model.name)}
								{@const Icon = getModelIcon(model.model_type)}
								{@const isChecking = pingingModels.has(model.name)}
								{@const wasJustChecked = recentlyChecked.has(model.name)}
								<div
									class="bg-white dark:bg-gray-800 rounded-xl border p-4 hover:shadow-md transition-all relative {isChecking ? 'border-violet-300 dark:border-violet-700' : wasJustChecked ? 'border-green-400 dark:border-green-600 ring-2 ring-green-200 dark:ring-green-800' : 'border-green-200 dark:border-green-900/50'}"
									ondblclick={() => openDetails(model)}
								>
									{#if isChecking}
										<div class="absolute top-2 right-2">
											<Loader2 size={14} class="animate-spin text-violet-500" />
										</div>
									{/if}
									<div class="flex items-start gap-3">
										<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-emerald-600/20 flex items-center justify-center flex-shrink-0">
											<Icon size={20} class="text-green-600 dark:text-green-400" />
										</div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center gap-2">
												<h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate">{model.name}</h3>
												{#if model.is_builtin}
													<span class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-medium flex-shrink-0" title="SyGra builtin model">
														<Shield size={9} />
														SyGra
													</span>
												{/if}
											</div>
											<p class="text-xs text-gray-500 font-mono truncate">{model.model}</p>
											<div class="flex items-center gap-3 mt-2 text-xs text-gray-500">
												<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{model.model_type_label}</span>
												{#if isChecking}
													<span class="flex items-center gap-1 text-violet-500 animate-pulse">checking...</span>
												{:else if model.latency_ms}
													<span class="flex items-center gap-1"><Zap size={10} />{formatLatency(model.latency_ms)}</span>
												{/if}
											</div>
										</div>
										<!-- Three-dot menu -->
										<button
											onclick={(e) => toggleMenu(e, model.name)}
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors {isChecking ? 'opacity-0' : ''}"
											title="More options"
										>
											<MoreVertical size={16} />
										</button>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Configured Models (not online) -->
				{#if configuredModels.length > 0}
					<div>
						<div class="flex items-center gap-2 mb-3">
							<Server size={18} class="text-blue-500" />
							<h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">Configured ({configuredModels.length})</h2>
						</div>
						<div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
							{#each configuredModels as model (model.name)}
								{@const Icon = getModelIcon(model.model_type)}
								{@const isChecking = pingingModels.has(model.name)}
								{@const wasJustChecked = recentlyChecked.has(model.name)}
								{@const checkResult = recentlyChecked.get(model.name)}
								<div
									class="bg-white dark:bg-gray-800 rounded-xl border p-4 hover:shadow-md transition-all relative {isChecking ? 'border-violet-300 dark:border-violet-700' : wasJustChecked ? (checkResult === 'success' ? 'border-green-400 dark:border-green-600 ring-2 ring-green-200 dark:ring-green-800' : 'border-red-400 dark:border-red-600 ring-2 ring-red-200 dark:ring-red-800') : 'border-gray-200 dark:border-gray-700'}"
									ondblclick={() => openDetails(model)}
								>
									{#if isChecking}
										<div class="absolute top-2 right-2">
											<Loader2 size={14} class="animate-spin text-violet-500" />
										</div>
									{/if}
									<div class="flex items-start gap-3">
										<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-indigo-600/20 flex items-center justify-center flex-shrink-0">
											<Icon size={20} class="text-blue-600 dark:text-blue-400" />
										</div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center gap-2">
												<h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate">{model.name}</h3>
												{#if model.is_builtin}
													<span class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-medium flex-shrink-0" title="SyGra builtin model">
														<Shield size={9} />
														SyGra
													</span>
												{/if}
												{#if isChecking}
													<span class="flex-shrink-0 w-2 h-2 rounded-full bg-violet-500 animate-pulse"></span>
												{:else if model.status === 'offline' || model.status === 'error'}
													<span class="flex-shrink-0 w-2 h-2 rounded-full bg-red-500"></span>
												{:else}
													<span class="flex-shrink-0 w-2 h-2 rounded-full bg-gray-400"></span>
												{/if}
											</div>
											<p class="text-xs text-gray-500 font-mono truncate">{model.model}</p>
											<div class="flex items-center gap-3 mt-2 text-xs text-gray-500">
												<span class="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700">{model.model_type_label}</span>
												{#if isChecking}
													<span class="flex items-center gap-1 text-violet-500 animate-pulse">checking...</span>
												{:else if model.error}
													<span class="text-red-500 truncate" title={model.error}>{model.error}</span>
												{/if}
											</div>
										</div>
										<!-- Three-dot menu -->
										<button
											onclick={(e) => toggleMenu(e, model.name)}
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors {isChecking ? 'opacity-0' : ''}"
											title="More options"
										>
											<MoreVertical size={16} />
										</button>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Needs Config Models -->
				{#if needsConfigModels.length > 0}
					<div>
						<div class="flex items-center gap-2 mb-3">
							<AlertTriangle size={18} class="text-amber-500" />
							<h2 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wider">Needs Configuration ({needsConfigModels.length})</h2>
						</div>
						<div class="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
							{#each needsConfigModels as model (model.name)}
								{@const Icon = getModelIcon(model.model_type)}
								{@const isChecking = pingingModels.has(model.name)}
								<div
									class="bg-white dark:bg-gray-800 rounded-xl border border-dashed p-4 hover:shadow-md transition-all relative {isChecking ? 'border-violet-300 dark:border-violet-700' : 'border-amber-200 dark:border-amber-900/50'}"
									ondblclick={() => openDetails(model)}
								>
									{#if isChecking}
										<div class="absolute top-2 right-2">
											<Loader2 size={14} class="animate-spin text-violet-500" />
										</div>
									{/if}
									<div class="flex items-start gap-3">
										<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500/20 to-orange-600/20 flex items-center justify-center flex-shrink-0">
											<Icon size={20} class="text-amber-600 dark:text-amber-400" />
										</div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center gap-2">
												<h3 class="font-semibold text-gray-900 dark:text-gray-100 truncate">{model.name}</h3>
												{#if model.is_builtin}
													<span class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-medium flex-shrink-0" title="SyGra builtin model">
														<Shield size={9} />
														SyGra
													</span>
												{/if}
											</div>
											<p class="text-xs text-gray-500 font-mono truncate">{model.model}</p>
											<div class="flex items-center gap-2 mt-2">
												<span class="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">{model.model_type_label}</span>
												{#if isChecking}
													<span class="flex items-center gap-1 text-xs text-violet-500 animate-pulse">checking...</span>
												{/if}
											</div>
										</div>
										<!-- Three-dot menu -->
										<button
											onclick={(e) => toggleMenu(e, model.name)}
											class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors {isChecking ? 'opacity-0' : ''}"
											title="More options"
										>
											<MoreVertical size={16} />
										</button>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

<!-- Floating Context Menu -->
{#if openMenuId && menuPosition}
	{@const model = models.find(m => m.name === openMenuId)}
	{#if model}
		{@const modelName = model.name}
		{@const modelId = model.model}
		{@const isBuiltin = model.is_builtin}
		{@const modelRef = model}
		<div
			class="fixed w-52 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 py-1 z-[100] max-h-[calc(100vh-16px)] overflow-y-auto"
			style="left: {menuPosition.x}px; {menuPosition.top !== undefined ? `top: ${menuPosition.top}px` : `bottom: ${menuPosition.bottom}px`}"
			onclick={(e) => e.stopPropagation()}
		>
			<!-- View Details -->
			<button
				onclick={(e) => { e.stopPropagation(); const m = modelRef; closeMenu(); openDetails(m); }}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
			>
				<Eye size={14} />
				View Details
			</button>

			<!-- Check Status -->
			<button
				onclick={(e) => { e.stopPropagation(); const name = modelName; closeMenu(); pingModel(name); }}
				disabled={pingingModels.has(modelName) || pingingAll}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-50"
			>
				{#if pingingModels.has(modelName)}
					<Loader2 size={14} class="animate-spin" />
					Checking...
				{:else}
					<Activity size={14} />
					Check Status
				{/if}
			</button>

			<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>

			<!-- Copy Model Name -->
			<button
				onclick={(e) => { e.stopPropagation(); const name = modelName; closeMenu(); copyToClipboard(name); }}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
			>
				<Copy size={14} />
				Copy Name
			</button>

			<!-- Copy Model ID -->
			<button
				onclick={(e) => { e.stopPropagation(); const id = modelId; closeMenu(); copyToClipboard(id); }}
				class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
			>
				<Copy size={14} />
				Copy Model ID
			</button>

			<div class="h-px bg-gray-200 dark:bg-gray-700 my-1"></div>

			<!-- Edit -->
			{#if !isBuiltin}
				<button
					onclick={(e) => { e.stopPropagation(); const m = modelRef; closeMenu(); openEditor(m); }}
					class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
				>
					<Edit3 size={14} />
					Edit Configuration
				</button>
			{:else}
				<div class="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 dark:text-gray-500 cursor-not-allowed">
					<Lock size={14} />
					Edit (Read-only)
				</div>
			{/if}

			<!-- Delete -->
			{#if !isBuiltin}
				<button
					onclick={(e) => { e.stopPropagation(); const name = modelName; closeMenu(); requestDelete(name); }}
					class="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
				>
					<Trash2 size={14} />
					Delete Model
				</button>
			{/if}
		</div>
	{/if}
{/if}

<!-- Model Editor Modal -->
{#if showEditor}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
		<div class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
				<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
					{editingModel ? 'Edit Model' : 'Add New Model'}
				</h3>
				<button onclick={closeEditor} class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
					<X size={18} />
				</button>
			</div>

			<div class="flex-1 overflow-y-auto p-6">
				{#if formError}
					<div class="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
						{formError}
					</div>
				{/if}

				<div class="space-y-4">
					<!-- Name & Type -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Model Name *</label>
							<input
								type="text"
								bind:value={formName}
								placeholder="my-gpt4o"
								disabled={!!editingModel}
								class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 disabled:opacity-50"
							/>
						</div>
						<div>
							<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Type *</label>
							<CustomSelect
								options={modelTypeFormOptions}
								bind:value={formModelType}
								placeholder="Select type..."
								searchable={modelTypeFormOptions.length > 5}
								searchPlaceholder="Search types..."
								class="w-full"
							/>
						</div>
					</div>

					<!-- Model & API Version -->
					<div class="grid grid-cols-2 gap-4">
						<div>
							<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Model ID</label>
							<input
								type="text"
								bind:value={formModel}
								placeholder="gpt-4o"
								class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
							/>
						</div>
						<div>
							<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">API Version</label>
							<input
								type="text"
								bind:value={formApiVersion}
								placeholder="2024-08-01-preview"
								class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
							/>
						</div>
					</div>

					<!-- Credentials Section -->
					{#if Object.keys(formCredentials).length > 0}
						<div>
							<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">Credentials</label>
							<p class="text-xs text-gray-400 mb-3">Leave empty to keep existing values. Values are stored in environment variables.</p>
							<div class="grid grid-cols-2 gap-3">
								{#each Object.keys(formCredentials) as envVar}
									<div>
										<label class="block text-xs text-gray-500 mb-1">{envVar}</label>
										<input
											type={envVar.toLowerCase().includes('token') || envVar.toLowerCase().includes('secret') || envVar.toLowerCase().includes('key') ? 'password' : 'text'}
											bind:value={formCredentials[envVar]}
											placeholder={`SYGRA_${formName.toUpperCase().replace(/[-.]/g, '_')}_${envVar}`}
											class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
										/>
									</div>
								{/each}
							</div>
						</div>
					{/if}

					<!-- Parameters Section -->
					<div>
						<div class="flex items-center justify-between mb-2">
							<label class="text-xs font-medium text-gray-500 uppercase tracking-wider">Parameters</label>
							<button
								type="button"
								onclick={addParameter}
								class="text-xs text-violet-600 hover:text-violet-700 dark:text-violet-400 flex items-center gap-1"
							>
								<Plus size={12} />
								Add Parameter
							</button>
						</div>
						<div class="space-y-2">
							{#each formParameters as param, index}
								<div class="flex items-center gap-2">
									<input
										type="text"
										bind:value={param.key}
										placeholder="key (e.g., max_tokens)"
										class="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
									/>
									<input
										type="text"
										bind:value={param.value}
										placeholder="value (e.g., 1000)"
										class="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
									/>
									<button
										type="button"
										onclick={() => removeParameter(index)}
										class="p-2 text-gray-400 hover:text-red-500 transition-colors"
										title="Remove parameter"
									>
										<X size={16} />
									</button>
								</div>
							{/each}
						</div>
						<p class="text-xs text-gray-400 mt-2">For arrays use JSON: ["value1", "value2"]. For nested objects use JSON syntax.</p>
					</div>

					<!-- Advanced Options Toggle -->
					<button
						type="button"
						onclick={() => showAdvancedOptions = !showAdvancedOptions}
						class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400"
					>
						{#if showAdvancedOptions}
							<ChevronDown size={16} />
						{:else}
							<ChevronRight size={16} />
						{/if}
						Advanced Options
					</button>

					{#if showAdvancedOptions}
						<!-- Additional Properties -->
						<div class="space-y-4 pl-4 border-l-2 border-gray-200 dark:border-gray-700">
							<!-- HF Chat Template & Model Serving Name -->
							<div class="grid grid-cols-2 gap-4">
								<div>
									<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">HF Chat Template Model ID</label>
									<input
										type="text"
										bind:value={formHfChatTemplateModelId}
										placeholder="Qwen/Qwen3-32B"
										class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
									/>
								</div>
								<div>
									<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Model Serving Name</label>
									<input
										type="text"
										bind:value={formModelServingName}
										placeholder="my_model_server"
										class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
									/>
								</div>
							</div>

							<!-- Input/Output Types -->
							<div class="grid grid-cols-2 gap-4">
								<div>
									<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Input Type</label>
									<input
										type="text"
										bind:value={formInputType}
										placeholder="audio, image, etc."
										class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
									/>
								</div>
								<div>
									<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Output Type</label>
									<input
										type="text"
										bind:value={formOutputType}
										placeholder="audio, image, etc."
										class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500"
									/>
								</div>
							</div>

							<!-- Post Process -->
							<div>
								<label class="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-1.5">Post Process Function</label>
								<input
									type="text"
									bind:value={formPostProcess}
									placeholder="sygra.core.models.model_postprocessor.RemoveThinkData"
									class="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
								/>
							</div>

							<!-- Custom Properties -->
							<div>
								<div class="flex items-center justify-between mb-2">
									<label class="text-xs font-medium text-gray-500 uppercase tracking-wider">Custom Properties</label>
									<button
										type="button"
										onclick={addCustomProperty}
										class="text-xs text-violet-600 hover:text-violet-700 dark:text-violet-400 flex items-center gap-1"
									>
										<Plus size={12} />
										Add Property
									</button>
								</div>
								<p class="text-xs text-gray-400 mb-2">Add any additional properties (e.g., image_capabilities). Use JSON for nested objects.</p>
								<div class="space-y-2">
									{#each formCustomProperties as prop, index}
										<div class="flex items-start gap-2">
											<input
												type="text"
												bind:value={prop.key}
												placeholder="property_name"
												class="w-1/3 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono"
											/>
											<textarea
												bind:value={prop.value}
												placeholder="JSON object or simple value"
												rows="2"
												class="flex-1 px-3 py-2 text-sm rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 focus:ring-2 focus:ring-violet-500 font-mono resize-y"
											></textarea>
											<button
												type="button"
												onclick={() => removeCustomProperty(index)}
												class="p-2 text-gray-400 hover:text-red-500 transition-colors"
												title="Remove property"
											>
												<X size={16} />
											</button>
										</div>
									{/each}
								</div>
							</div>
						</div>
					{/if}
				</div>
			</div>

			<div class="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-800">
				<button onclick={closeEditor} class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
					Cancel
				</button>
				<button
					onclick={saveModel}
					class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg"
				>
					{editingModel ? 'Save Changes' : 'Add Model'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Delete Confirmation Modal -->
{#if showDeleteConfirm}
	<ConfirmationModal
		title="Delete Model"
		message={`Are you sure you want to delete "${modelToDelete}"? This will remove the model from your configuration.`}
		confirmText="Delete"
		variant="danger"
		on:confirm={confirmDelete}
		on:cancel={() => { showDeleteConfirm = false; modelToDelete = null; }}
	/>
{/if}

<!-- Model Details Modal -->
{#if showDetails && detailsModel}
	{@const Icon = getModelIcon(detailsModel.model_type)}
	<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={closeDetails}>
		<div
			class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col"
			onclick={(e) => e.stopPropagation()}
		>
			<!-- Header -->
			<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
				<div class="flex items-center gap-3">
					<div class="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500/20 to-purple-600/20 flex items-center justify-center">
						<Icon size={20} class="text-violet-600 dark:text-violet-400" />
					</div>
					<div>
						<div class="flex items-center gap-2">
							<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">{detailsModel.name}</h3>
							{#if detailsModel.is_builtin}
								<span class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400 font-medium">
									<Shield size={10} />
									SyGra
								</span>
							{/if}
						</div>
						<p class="text-xs text-gray-500 font-mono">{detailsModel.model}</p>
					</div>
				</div>
				<button onclick={closeDetails} class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500">
					<X size={18} />
				</button>
			</div>

			<!-- Content -->
			<div class="flex-1 overflow-y-auto p-6 space-y-6">
				<!-- Status Section -->
				<div class="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
					<div class="flex items-center gap-4">
						<!-- Status Badge -->
						{#if pingingModels.has(detailsModel.name)}
							<span class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-400">
								<Loader2 size={14} class="animate-spin" />
								Checking...
							</span>
						{:else if !detailsModel.credentials_configured}
							<span class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400">
								<AlertTriangle size={14} />
								Needs Configuration
							</span>
						{:else if detailsModel.status === 'online'}
							<span class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
								<CheckCircle2 size={14} />
								Online
							</span>
						{:else if detailsModel.status === 'offline' || detailsModel.status === 'error'}
							<span class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
								<XCircle size={14} />
								{detailsModel.status.charAt(0).toUpperCase() + detailsModel.status.slice(1)}
							</span>
						{:else}
							<span class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
								<HelpCircle size={14} />
								Unknown
							</span>
						{/if}

						<!-- Latency -->
						{#if detailsModel.latency_ms}
							<span class="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
								<Zap size={14} class="text-amber-500" />
								{formatLatency(detailsModel.latency_ms)}
							</span>
						{/if}

						<!-- Last Checked -->
						{#if detailsModel.last_checked}
							<span class="flex items-center gap-1.5 text-sm text-gray-500">
								<Clock size={14} />
								{formatTime(detailsModel.last_checked)}
							</span>
						{/if}
					</div>

					<button
						onclick={() => pingModel(detailsModel.name)}
						disabled={pingingModels.has(detailsModel.name) || pingingAll}
						class="flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors"
					>
						{#if pingingModels.has(detailsModel.name)}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<RefreshCw size={14} />
						{/if}
						Check Now
					</button>
				</div>

				<!-- Error Message -->
				{#if detailsModel.error}
					<div class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
						<div class="flex items-start gap-2">
							<AlertTriangle size={16} class="text-red-500 flex-shrink-0 mt-0.5" />
							<div>
								<p class="text-sm font-medium text-red-800 dark:text-red-300">Error Details</p>
								<p class="text-sm text-red-600 dark:text-red-400 mt-1">{detailsModel.error}</p>
							</div>
						</div>
					</div>
				{/if}

				<!-- Model Information -->
				<div>
					<h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Model Information</h4>
					<div class="grid grid-cols-2 gap-4">
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
							<p class="text-xs text-gray-500 mb-1">Type</p>
							<p class="text-sm font-medium text-gray-900 dark:text-gray-100">{detailsModel.model_type_label}</p>
						</div>
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
							<p class="text-xs text-gray-500 mb-1">Model ID</p>
							<div class="flex items-center gap-2">
								<p class="text-sm font-mono text-gray-900 dark:text-gray-100 truncate">{detailsModel.model}</p>
								<button
									onclick={() => copyToClipboard(detailsModel.model)}
									class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
									title="Copy model ID"
								>
									<Copy size={12} class="text-gray-400" />
								</button>
							</div>
						</div>
						{#if detailsModel.api_version}
							<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
								<p class="text-xs text-gray-500 mb-1">API Version</p>
								<p class="text-sm font-mono text-gray-900 dark:text-gray-100">{detailsModel.api_version}</p>
							</div>
						{/if}
						<div class="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
							<p class="text-xs text-gray-500 mb-1">Credentials</p>
							<p class="text-sm font-medium {detailsModel.credentials_configured ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}">
								{detailsModel.credentials_configured ? 'Configured' : 'Not Configured'}
							</p>
						</div>
					</div>
				</div>

				<!-- Parameters -->
				{#if Object.keys(detailsModel.parameters || {}).length > 0}
					<div>
						<h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Parameters</h4>
						<div class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
							<table class="w-full text-sm">
								<tbody class="divide-y divide-gray-200 dark:divide-gray-700">
									{#each Object.entries(detailsModel.parameters) as [key, value]}
										<tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
											<td class="px-4 py-2.5 font-mono text-gray-600 dark:text-gray-400 w-1/3">{key}</td>
											<td class="px-4 py-2.5 font-mono text-gray-900 dark:text-gray-100">
												{typeof value === 'object' ? JSON.stringify(value) : String(value)}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
						</div>
					</div>
				{/if}

				<!-- Status Code -->
				{#if detailsModel.status_code}
					<div class="flex items-center gap-2 text-sm text-gray-500">
						<Info size={14} />
						<span>HTTP Status Code: <span class="font-mono">{detailsModel.status_code}</span></span>
					</div>
				{/if}
			</div>

			<!-- Footer -->
			<div class="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-800">
				<div class="flex items-center gap-2">
					{#if !detailsModel.is_builtin}
						<button
							onclick={() => { closeDetails(); openEditor(detailsModel); }}
							class="flex items-center gap-2 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
						>
							<Edit3 size={14} />
							Edit
						</button>
						<button
							onclick={() => { closeDetails(); requestDelete(detailsModel.name); }}
							class="flex items-center gap-2 px-3 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
						>
							<Trash2 size={14} />
							Delete
						</button>
					{/if}
				</div>
				<button
					onclick={closeDetails}
					class="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}
