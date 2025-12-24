<script lang="ts">
	import { onDestroy, createEventDispatcher, tick } from 'svelte';
	import {
		Terminal, X, Trash2, Square, Download,
		CheckCircle2, XCircle, Loader2, Circle,
		Play, SkipForward, ArrowDownToLine, ArrowUpFromLine, Pause,
		ChevronRight, ChevronDown, Bug
	} from 'lucide-svelte';

	interface OutputLine {
		type: 'stdout' | 'stderr' | 'status' | 'debug' | 'heartbeat' | 'error' |
			  'debug_stopped' | 'debug_location' | 'debug_variables' | 'debug_continued' | 'debug_terminated';
		content?: string;
		timestamp?: string;
		status?: string;
		debug_port?: number;
		line?: number;
		file?: string;
		frame_id?: number;
		frames?: any[];
		variables?: DebugVariable[];
		reason?: string;
		thread_id?: number;
	}

	interface DebugVariable {
		scope: string;
		name: string;
		value: string;
		type?: string;
		variablesReference: number;
	}

	interface Props {
		executionId: string | null;
		isRunning?: boolean;
		height?: string;
	}

	let {
		executionId,
		isRunning = $bindable(false),
		height = '200px'
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		stop: void;
		clear: void;
		debugLocation: { line: number; file: string };
		debugVariables: { variables: DebugVariable[] };
		debugPaused: { reason: string };
		debugContinued: void;
	}>();

	// Debug state
	let debugVariables = $state<DebugVariable[]>([]);
	let isPaused = $state(false);
	let currentDebugLine = $state<number | null>(null);
	let showVariables = $state(true);

	let output = $state<OutputLine[]>([]);
	let status = $state<'idle' | 'running' | 'completed' | 'failed' | 'cancelled'>('idle');
	let error = $state<string | null>(null);
	let outputContainer: HTMLDivElement;
	let autoScroll = $state(true);

	// Track connection state separately (not reactive)
	let wsConnection: WebSocket | null = null;
	let currentExecId: string | null = null;
	let pollingInterval: ReturnType<typeof setInterval> | null = null;

	// Watch for executionId changes with proper cleanup
	$effect(() => {
		const execId = executionId;

		// Only act if executionId actually changed
		if (execId !== currentExecId) {
			currentExecId = execId;

			if (execId) {
				// Use setTimeout to break out of the reactive context
				setTimeout(() => startExecution(execId), 0);
			} else {
				cleanup();
				status = 'idle';
			}
		}
	});

	async function startExecution(execId: string) {
		cleanup();
		output = [];
		error = null;
		status = 'running';

		// Try WebSocket first, fall back to polling
		const wsConnected = await tryWebSocket(execId);

		if (!wsConnected) {
			console.log('WebSocket failed, using polling fallback');
			startPolling(execId);
		}
	}

	function tryWebSocket(execId: string): Promise<boolean> {
		return new Promise((resolve) => {
			try {
				const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
				const wsUrl = `${wsProtocol}//${window.location.host}/ws/code/${execId}`;

				const ws = new WebSocket(wsUrl);
				let resolved = false;

				// Timeout for connection
				const timeout = setTimeout(() => {
					if (!resolved) {
						resolved = true;
						ws.close();
						resolve(false);
					}
				}, 3000);

				ws.onopen = () => {
					if (!resolved) {
						resolved = true;
						clearTimeout(timeout);
						wsConnection = ws;
						console.log('WebSocket connected for execution:', execId);
						resolve(true);
					}
				};

				ws.onmessage = (event) => {
					handleMessage(event.data);
				};

				ws.onclose = () => {
					wsConnection = null;
					if (status === 'running') {
						// Connection closed unexpectedly, switch to polling
						startPolling(execId);
					}
				};

				ws.onerror = () => {
					if (!resolved) {
						resolved = true;
						clearTimeout(timeout);
						ws.close();
						resolve(false);
					}
				};

			} catch (e) {
				console.error('WebSocket creation failed:', e);
				resolve(false);
			}
		});
	}

	function startPolling(execId: string) {
		if (pollingInterval) return;

		let lastOutputLength = 0;

		pollingInterval = setInterval(async () => {
			try {
				const response = await fetch(`/api/code/executions/${execId}`);
				if (!response.ok) {
					stopPolling();
					status = 'failed';
					error = 'Failed to fetch execution status';
					return;
				}

				const data = await response.json();

				// Add new output lines
				if (data.output && data.output.length > lastOutputLength) {
					const newLines = data.output.slice(lastOutputLength);
					for (const line of newLines) {
						if (line.type !== 'heartbeat') {
							output = [...output, line];
						}
					}
					lastOutputLength = data.output.length;
					scrollToBottom();
				}

				// Update status
				if (data.status && data.status !== 'running' && data.status !== 'pending') {
					status = data.status;
					if (data.error) error = data.error;
					stopPolling();
				}

			} catch (e) {
				console.error('Polling error:', e);
			}
		}, 500);
	}

	function stopPolling() {
		if (pollingInterval) {
			clearInterval(pollingInterval);
			pollingInterval = null;
		}
	}

	function handleMessage(data: string) {
		try {
			const parsed: OutputLine = JSON.parse(data);

			if (parsed.type === 'heartbeat') {
				return;
			}

			// Log all debug-related messages to trace what's being received
			if (parsed.type && (parsed.type.startsWith('debug') || parsed.type === 'debug')) {
				console.log('[WS] Debug message:', parsed.type, parsed);
			}

			if (parsed.type === 'status') {
				status = parsed.status as typeof status;
				if (parsed.error) {
					error = parsed.error;
				}
			} else if (parsed.type === 'debug_stopped') {
				// Execution paused at breakpoint
				console.log('[ExecutionOutputPanel] Received debug_stopped:', parsed);
				isPaused = true;
				if (parsed.content) {
					output = [...output, { type: 'debug', content: parsed.content }];
				}
				console.log('[ExecutionOutputPanel] DISPATCHING debugPaused event');
				dispatch('debugPaused', { reason: parsed.reason || 'breakpoint' });
				scrollToBottom();
			} else if (parsed.type === 'debug_location') {
				// Update current execution line
				console.log('[ExecutionOutputPanel] Received debug_location:', parsed);
				currentDebugLine = parsed.line || null;
				if (parsed.line && parsed.file) {
					console.log('[ExecutionOutputPanel] DISPATCHING debugLocation event');
					dispatch('debugLocation', { line: parsed.line, file: parsed.file });
				}
			} else if (parsed.type === 'debug_variables') {
				// Update variables
				console.log('[ExecutionOutputPanel] Received debug_variables:', parsed.variables?.length, 'vars');
				debugVariables = parsed.variables || [];
				console.log('[ExecutionOutputPanel] DISPATCHING debugVariables event');
				dispatch('debugVariables', { variables: debugVariables });
			} else if (parsed.type === 'debug_continued') {
				// Execution resumed
				isPaused = false;
				currentDebugLine = null;
				debugVariables = [];
				dispatch('debugContinued');
				if (parsed.content) {
					output = [...output, { type: 'debug', content: parsed.content }];
					scrollToBottom();
				}
			} else if (parsed.type === 'debug_terminated') {
				// Debug session ended
				isPaused = false;
				currentDebugLine = null;
				if (parsed.content) {
					output = [...output, { type: 'debug', content: parsed.content }];
					scrollToBottom();
				}
			} else {
				output = [...output, parsed];
				scrollToBottom();
			}
		} catch (e) {
			console.error('Failed to parse message:', e);
		}
	}

	function scrollToBottom() {
		if (autoScroll && outputContainer) {
			tick().then(() => {
				outputContainer.scrollTop = outputContainer.scrollHeight;
			});
		}
	}

	function cleanup() {
		if (wsConnection) {
			wsConnection.close();
			wsConnection = null;
		}
		stopPolling();
	}

	function handleStop() {
		dispatch('stop');
	}

	function handleClear() {
		output = [];
		error = null;
		debugVariables = [];
		isPaused = false;
		currentDebugLine = null;
		dispatch('clear');
	}

	async function sendDebugAction(action: string) {
		if (!executionId) return;

		try {
			const response = await fetch('/api/debug/action', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					session_id: executionId,
					action: action
				})
			});

			if (!response.ok) {
				console.error('Debug action failed:', await response.text());
			}
		} catch (e) {
			console.error('Debug action error:', e);
		}
	}

	function handleContinue() {
		sendDebugAction('continue');
	}

	function handleStepOver() {
		sendDebugAction('step_over');
	}

	function handleStepInto() {
		sendDebugAction('step_into');
	}

	function handleStepOut() {
		sendDebugAction('step_out');
	}

	function downloadOutput() {
		const text = output
			.filter(l => l.type !== 'heartbeat')
			.map(l => `[${l.type}] ${l.content}`)
			.join('\n');

		const blob = new Blob([text], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `execution-${executionId || 'output'}.log`;
		a.click();
		URL.revokeObjectURL(url);
	}

	onDestroy(() => {
		cleanup();
	});

	// Update isRunning based on status
	$effect(() => {
		isRunning = status === 'running';
	});

	// Group variables by scope for display
	let groupedVariables = $derived.by(() => {
		return debugVariables.reduce((acc, v) => {
			if (!acc[v.scope]) acc[v.scope] = [];
			acc[v.scope].push(v);
			return acc;
		}, {} as Record<string, typeof debugVariables>);
	});
</script>

<div class="flex flex-col bg-gray-900 rounded-lg border border-gray-700 overflow-hidden" style="height: {height}">
	<!-- Header -->
	<div class="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
		<div class="flex items-center gap-2">
			<Terminal size={16} class="text-green-400" />
			<span class="text-sm font-medium text-gray-300">Output</span>
			{#if executionId}
				<span class="text-xs text-gray-500 font-mono">({executionId})</span>
			{/if}
		</div>

		<div class="flex items-center gap-2">
			<!-- Debug controls (when paused) -->
			{#if isPaused}
				<div class="flex items-center gap-1 border-r border-gray-600 pr-2 mr-1">
					<span class="text-xs text-yellow-400 font-medium flex items-center gap-1">
						<Pause size={12} />
						Paused
					</span>
					<button
						onclick={handleContinue}
						class="p-1 hover:bg-green-900/50 rounded text-green-400 hover:text-green-300 transition-colors"
						title="Continue (F5)"
					>
						<Play size={14} />
					</button>
					<button
						onclick={handleStepOver}
						class="p-1 hover:bg-blue-900/50 rounded text-blue-400 hover:text-blue-300 transition-colors"
						title="Step Over (F10)"
					>
						<SkipForward size={14} />
					</button>
					<button
						onclick={handleStepInto}
						class="p-1 hover:bg-blue-900/50 rounded text-blue-400 hover:text-blue-300 transition-colors"
						title="Step Into (F11)"
					>
						<ArrowDownToLine size={14} />
					</button>
					<button
						onclick={handleStepOut}
						class="p-1 hover:bg-blue-900/50 rounded text-blue-400 hover:text-blue-300 transition-colors"
						title="Step Out (Shift+F11)"
					>
						<ArrowUpFromLine size={14} />
					</button>
				</div>
			{/if}

			<!-- Status indicator -->
			<div class="flex items-center gap-1.5">
				{#if status === 'running'}
					<Loader2 size={14} class="text-blue-500 animate-spin" />
				{:else if status === 'completed'}
					<CheckCircle2 size={14} class="text-green-500" />
				{:else if status === 'failed'}
					<XCircle size={14} class="text-red-500" />
				{:else if status === 'cancelled'}
					<Square size={14} class="text-yellow-500" />
				{:else}
					<Circle size={14} class="text-gray-400" />
				{/if}
				<span class="text-xs text-gray-400 capitalize">{status}</span>
			</div>

			{#if isRunning}
				<button
					onclick={handleStop}
					class="p-1 hover:bg-red-900/50 rounded text-red-400 hover:text-red-300 transition-colors"
					title="Stop execution"
				>
					<Square size={14} />
				</button>
			{/if}

			<button
				onclick={downloadOutput}
				class="p-1 hover:bg-gray-700 rounded text-gray-400 hover:text-gray-300 transition-colors"
				title="Download output"
				disabled={output.length === 0}
			>
				<Download size={14} />
			</button>

			<button
				onclick={handleClear}
				class="p-1 hover:bg-gray-700 rounded text-gray-400 hover:text-gray-300 transition-colors"
				title="Clear output"
			>
				<Trash2 size={14} />
			</button>
		</div>
	</div>

	<!-- Main content area -->
	<div class="flex-1 flex overflow-hidden">
		<!-- Output content -->
		<div
			bind:this={outputContainer}
			class="flex-1 overflow-auto font-mono text-sm p-3 space-y-0.5"
		>
			{#if output.length === 0}
				<div class="text-gray-500 text-center py-8">
					{#if status === 'idle'}
						Click "Run" to execute the code
					{:else if status === 'running'}
						Waiting for output...
					{:else}
						No output
					{/if}
				</div>
			{:else}
				{#each output as line}
					{#if line.type === 'stdout'}
						<div class="text-gray-100 whitespace-pre-wrap break-all">{line.content}</div>
					{:else if line.type === 'stderr'}
						<div class="text-red-400 whitespace-pre-wrap break-all">{line.content}</div>
					{:else if line.type === 'debug'}
						<div class="text-blue-400 whitespace-pre-wrap break-all">{line.content}</div>
					{:else if line.type === 'error'}
						<div class="text-red-500 whitespace-pre-wrap break-all">
							<span class="font-bold">[ERROR]</span> {line.content}
						</div>
					{:else if line.type === 'status'}
						<div class="text-yellow-400 whitespace-pre-wrap">
							<span class="text-yellow-500">[STATUS]</span> {line.status}
							{#if line.error}
								- {line.error}
							{/if}
						</div>
					{/if}
				{/each}
			{/if}

			{#if error && status !== 'running'}
				<div class="mt-2 p-2 bg-red-900/30 border border-red-800 rounded text-red-400 text-xs">
					{error}
				</div>
			{/if}

			{#if isPaused && debugVariables.length > 0}
				<div class="mt-4 p-3 bg-yellow-900/20 border border-yellow-700/50 rounded-lg text-yellow-300 text-sm flex items-center gap-2">
					<Bug size={16} class="text-yellow-400" />
					<span><strong>{debugVariables.length} variables</strong> available. Switch to <strong>Code</strong> tab to view variables and highlighted line.</span>
				</div>
			{/if}
		</div>

		<!-- Variables panel removed - now shown in Code tab only -->
	</div>
</div>
