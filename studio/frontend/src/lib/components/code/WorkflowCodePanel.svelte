<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import {
		ChevronDown, ChevronUp, FileCode2, FileText,
		Maximize2, Minimize2, RefreshCw, Copy, Check,
		GripHorizontal, X, Play, Bug, Square, Terminal,
		Settings, ChevronRight, Save, AlertCircle,
		FolderTree, ChevronLeft, File, FolderOpen, ExternalLink,
		SkipForward, ArrowDownToLine, ArrowUpFromLine, Pause, Loader2,
		Code2
	} from 'lucide-svelte';
	import MonacoEditor from '$lib/components/editor/MonacoEditor.svelte';
	import ExecutionOutputPanel from './ExecutionOutputPanel.svelte';

	interface Props {
		workflowId: string;
		isCollapsed?: boolean;
		defaultHeight?: number;
	}

	let {
		workflowId,
		isCollapsed = $bindable(false),
		defaultHeight = 400
	}: Props = $props();

	const dispatch = createEventDispatcher<{
		collapse: boolean;
		resize: number;
		close: void;
	}>();

	// Panel state
	let panelHeight = $state(defaultHeight);
	let isMaximized = $state(false);
	let previousHeight = $state(defaultHeight);

	// Tab state - now includes 'output'
	let activeTab = $state<'yaml' | 'code' | 'output'>('code');
	let selectedCodeFile = $state<string>('task_executor.py');

	// Content state
	let yamlContent = $state<string>('');
	let yamlOriginal = $state<string>('');  // Original content for dirty checking
	let yamlPath = $state<string>('');
	let yamlLoading = $state(false);
	let yamlError = $state<string | null>(null);
	let yamlSaving = $state(false);

	let codeFiles = $state<Record<string, { content: string; path: string; filename: string; original: string }>>({});
	let codeFileList = $state<string[]>([]);
	let codeLoading = $state(false);
	let codeError = $state<string | null>(null);
	let codeSaving = $state(false);

	// Dirty state (unsaved changes)
	let yamlDirty = $derived(yamlContent !== yamlOriginal);
	let codeDirty = $derived.by(() => {
		const file = codeFiles[selectedCodeFile];
		return file ? file.content !== file.original : false;
	});
	let hasUnsavedChanges = $derived(yamlDirty || codeDirty);

	// Execution state
	let executionId = $state<string | null>(null);
	let isRunning = $state(false);
	let showArgsInput = $state(false);
	let runArgs = $state<string>('');
	let breakpoints = $state<number[]>([]);

	// Debug state
	let currentDebugLine = $state<number | null>(null);
	let isDebugPaused = $state(false);
	let debugVariables = $state<Array<{scope: string; name: string; value: string; type?: string; variablesReference?: number}>>([]);
	let showDebugPanel = $state(true);

	// Expanded variables tracking (key = "scope:name" or "parentRef:name")
	let expandedVars = $state<Set<string>>(new Set());
	let childVariables = $state<Record<number, Array<{name: string; value: string; type?: string; variablesReference?: number}>>>({});
	let loadingVars = $state<Set<number>>(new Set());

	// Debug state monitoring - only log significant changes
	$effect(() => {
		if (isDebugPaused || debugVariables.length > 0) {
			console.log('[DEBUG STATE]', { activeTab, isDebugPaused, line: currentDebugLine, vars: debugVariables.length });
		}
	});

	// Group variables by scope
	let groupedVariables = $derived.by(() => {
		const groups: Record<string, typeof debugVariables> = {};
		for (const v of debugVariables) {
			const scope = v.scope || 'Local';
			if (!groups[scope]) groups[scope] = [];
			groups[scope].push(v);
		}
		return groups;
	});

	// Copy state
	let copied = $state(false);

	// Resize state
	let isResizing = $state(false);
	let startY = $state(0);
	let startHeight = $state(0);

	// File sidebar state
	let showFileSidebar = $state(true);
	let sidebarWidth = $state(220);

	// Referenced files (extracted from YAML and code)
	interface ReferencedFile {
		name: string;
		path: string;
		type: 'subgraph' | 'module' | 'file';
		exists?: boolean;
	}
	let referencedFiles = $state<ReferencedFile[]>([]);

	const API_BASE = '/api';

	// Load YAML content
	async function loadYaml() {
		if (!workflowId || workflowId.startsWith('new_')) {
			yamlContent = '# New workflow - save to generate YAML';
			yamlOriginal = yamlContent;
			return;
		}

		yamlLoading = true;
		yamlError = null;

		try {
			const response = await fetch(`${API_BASE}/workflows/${workflowId}/yaml`);
			const data = await response.json();

			if (data.error) {
				yamlError = data.error;
				yamlContent = '';
				yamlOriginal = '';
			} else {
				yamlContent = data.content || '';
				yamlOriginal = yamlContent;  // Store original for dirty checking
				yamlPath = data.path || '';
			}
		} catch (e) {
			yamlError = e instanceof Error ? e.message : 'Failed to load YAML';
			yamlContent = '';
			yamlOriginal = '';
		} finally {
			yamlLoading = false;
		}
	}

	// Load code files
	async function loadCode() {
		if (!workflowId || workflowId.startsWith('new_')) {
			codeFiles = {};
			codeFileList = [];
			return;
		}

		codeLoading = true;
		codeError = null;

		try {
			const response = await fetch(`${API_BASE}/workflows/${workflowId}/code`);
			const data = await response.json();

			// Store files with original content for dirty checking
			const filesWithOriginal: Record<string, { content: string; path: string; filename: string; original: string }> = {};
			for (const [name, file] of Object.entries(data.files || {})) {
				const f = file as { content: string; path: string; filename: string };
				filesWithOriginal[name] = { ...f, original: f.content };
			}

			codeFiles = filesWithOriginal;
			codeFileList = data.file_list || [];

			// Select first available file if current selection doesn't exist
			if (codeFileList.length > 0 && !codeFiles[selectedCodeFile]) {
				selectedCodeFile = codeFileList[0];
			}
		} catch (e) {
			codeError = e instanceof Error ? e.message : 'Failed to load code';
			codeFiles = {};
			codeFileList = [];
		} finally {
			codeLoading = false;
		}
	}

	// Save YAML content
	async function saveYaml(): Promise<boolean> {
		if (!yamlDirty || !workflowId || workflowId.startsWith('new_')) return true;

		yamlSaving = true;
		try {
			const response = await fetch(`${API_BASE}/workflows/${workflowId}/yaml`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: yamlContent })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to save');
			}

			yamlOriginal = yamlContent;  // Update original after save
			return true;
		} catch (e) {
			yamlError = e instanceof Error ? e.message : 'Failed to save YAML';
			return false;
		} finally {
			yamlSaving = false;
		}
	}

	// Save code file
	async function saveCode(): Promise<boolean> {
		if (!codeDirty || !workflowId || workflowId.startsWith('new_')) return true;

		const file = codeFiles[selectedCodeFile];
		if (!file) return true;

		codeSaving = true;
		try {
			const response = await fetch(`${API_BASE}/workflows/${workflowId}/code/${selectedCodeFile}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: file.content })
			});

			if (!response.ok) {
				const data = await response.json();
				throw new Error(data.detail || 'Failed to save');
			}

			// Update original after save
			codeFiles[selectedCodeFile] = { ...file, original: file.content };
			return true;
		} catch (e) {
			codeError = e instanceof Error ? e.message : 'Failed to save code';
			return false;
		} finally {
			codeSaving = false;
		}
	}

	// Save all unsaved changes
	async function saveAll(): Promise<boolean> {
		const results = await Promise.all([saveYaml(), saveCode()]);
		return results.every(r => r);
	}

	// Force save all files regardless of dirty state (for run/debug)
	async function saveAllForced(): Promise<boolean> {
		if (!workflowId || workflowId.startsWith('new_')) return true;

		const results: boolean[] = [];

		// Save YAML if we have content
		if (yamlContent) {
			yamlSaving = true;
			try {
				const response = await fetch(`${API_BASE}/workflows/${workflowId}/yaml`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ content: yamlContent })
				});
				if (response.ok) {
					yamlOriginal = yamlContent;
					results.push(true);
					console.log('YAML saved successfully');
				} else {
					results.push(false);
					console.error('YAML save failed:', await response.text());
				}
			} catch (e) {
				results.push(false);
				console.error('YAML save error:', e);
			} finally {
				yamlSaving = false;
			}
		}

		// Save all code files
		for (const [filename, file] of Object.entries(codeFiles)) {
			if (!file || !file.content) continue;

			codeSaving = true;
			try {
				const response = await fetch(`${API_BASE}/workflows/${workflowId}/code/${filename}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ content: file.content })
				});
				if (response.ok) {
					codeFiles[filename] = { ...file, original: file.content };
					results.push(true);
					console.log(`Code file ${filename} saved successfully`);
				} else {
					results.push(false);
					console.error(`Code file ${filename} save failed:`, await response.text());
				}
			} catch (e) {
				results.push(false);
				console.error(`Code file ${filename} save error:`, e);
			} finally {
				codeSaving = false;
			}
		}

		return results.length === 0 || results.every(r => r);
	}

	// Python stdlib modules to exclude from references
	const PYTHON_STDLIB = new Set([
		// Built-in modules
		'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio', 'asyncore',
		'atexit', 'audioop', 'base64', 'bdb', 'binascii', 'binhex', 'bisect',
		'builtins', 'bz2', 'calendar', 'cgi', 'cgitb', 'chunk', 'cmath', 'cmd',
		'code', 'codecs', 'codeop', 'collections', 'colorsys', 'compileall',
		'concurrent', 'configparser', 'contextlib', 'contextvars', 'copy', 'copyreg',
		'cProfile', 'crypt', 'csv', 'ctypes', 'curses', 'dataclasses', 'datetime',
		'dbm', 'decimal', 'difflib', 'dis', 'distutils', 'doctest', 'email',
		'encodings', 'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
		'fnmatch', 'fractions', 'ftplib', 'functools', 'gc', 'getopt', 'getpass',
		'gettext', 'glob', 'graphlib', 'grp', 'gzip', 'hashlib', 'heapq', 'hmac',
		'html', 'http', 'idlelib', 'imaplib', 'imghdr', 'imp', 'importlib', 'inspect',
		'io', 'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
		'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal', 'math',
		'mimetypes', 'mmap', 'modulefinder', 'multiprocessing', 'netrc', 'nis',
		'nntplib', 'numbers', 'operator', 'optparse', 'os', 'ossaudiodev', 'pathlib',
		'pdb', 'pickle', 'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
		'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats', 'pty', 'pwd',
		'py_compile', 'pyclbr', 'pydoc', 'queue', 'quopri', 'random', 'readline',
		're', 'reprlib', 'resource', 'rlcompleter', 'runpy', 'sched', 'secrets',
		'select', 'selectors', 'shelve', 'shlex', 'shutil', 'signal', 'site',
		'smtpd', 'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3',
		'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct', 'subprocess',
		'sunau', 'symtable', 'sys', 'sysconfig', 'syslog', 'tabnanny', 'tarfile',
		'telnetlib', 'tempfile', 'termios', 'test', 'textwrap', 'threading', 'time',
		'timeit', 'tkinter', 'token', 'tokenize', 'trace', 'traceback', 'tracemalloc',
		'tty', 'turtle', 'turtledemo', 'types', 'typing', 'unicodedata', 'unittest',
		'urllib', 'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref', 'webbrowser',
		'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml', 'xmlrpc', 'zipapp',
		'zipfile', 'zipimport', 'zlib',
		// Common third-party that aren't local modules
		'numpy', 'pandas', 'scipy', 'matplotlib', 'sklearn', 'torch', 'tensorflow',
		'requests', 'flask', 'django', 'fastapi', 'pydantic', 'sqlalchemy',
		'pytest', 'setuptools', 'pip', 'wheel', 'tqdm', 'PIL', 'cv2', 'openai',
		'langchain', 'transformers', 'datasets', 'huggingface_hub'
	]);

	// Extract referenced files from YAML and code
	function extractReferencedFiles() {
		const refs: ReferencedFile[] = [];

		// Parse YAML for subgraph references
		if (yamlContent) {
			// Match subgraph patterns like: subgraph: path/to/graph_config.yaml or graph_config: path
			const subgraphMatches = yamlContent.matchAll(/(?:subgraph|graph_config)\s*:\s*["']?([^\s"'\n]+)["']?/g);
			for (const match of subgraphMatches) {
				const path = match[1];
				if (path && !path.startsWith('#') && path.includes('/')) {
					refs.push({
						name: path.split('/').pop() || path,
						path: path,
						type: 'subgraph'
					});
				}
			}

			// Match module references like: lambda: module.function or post_process: module.Class
			const moduleMatches = yamlContent.matchAll(/(?:lambda|pre_process|post_process|function)\s*:\s*["']?([a-zA-Z_][a-zA-Z0-9_.]+)["']?/g);
			for (const match of moduleMatches) {
				const modulePath = match[1];
				if (modulePath && modulePath.includes('.')) {
					const parts = modulePath.split('.');
					const moduleName = parts.slice(0, -1).join('.');
					const rootModule = moduleName.split('.')[0];
					// Only include if it's a local/tasks module, not stdlib or sygra
					if (moduleName &&
						!PYTHON_STDLIB.has(rootModule) &&
						!moduleName.startsWith('sygra') &&
						(moduleName.startsWith('tasks') || moduleName.includes('.'))) {
						if (!refs.some(r => r.name === moduleName)) {
							refs.push({
								name: moduleName,
								path: moduleName.replace(/\./g, '/') + '.py',
								type: 'module'
							});
						}
					}
				}
			}
		}

		referencedFiles = refs;
	}

	// Load content when workflowId changes
	$effect(() => {
		if (workflowId) {
			loadYaml();
			loadCode();
		}
	});

	// Extract referenced files when content changes
	$effect(() => {
		// Reference yamlContent and codeFiles to track changes
		const _y = yamlContent;
		const _c = codeFiles;
		extractReferencedFiles();
	});

	// Open a referenced file (navigate to subgraph or load module)
	async function openReferencedFile(ref: ReferencedFile) {
		if (ref.type === 'subgraph') {
			// Navigate to the subgraph workflow
			// Extract workflow name from path
			const pathParts = ref.path.split('/');
			const workflowName = pathParts[pathParts.length - 2] || pathParts[pathParts.length - 1].replace('.yaml', '');
			window.open(`/?workflow=${workflowName}`, '_blank');
		} else if (ref.type === 'module') {
			// Try to load the module file
			try {
				const response = await fetch(`${API_BASE}/file-content?file_path=${encodeURIComponent(ref.path)}&workflow_id=${workflowId}`);
				if (response.ok) {
					const data = await response.json();
					if (data.content) {
						// Add to code files if not already there
						if (!codeFiles[ref.name + '.py']) {
							codeFiles[ref.name + '.py'] = {
								content: data.content,
								original: data.content,
								path: data.file_path || ref.path,
								filename: ref.name + '.py'
							};
							codeFileList = [...codeFileList, ref.name + '.py'];
						}
						selectedCodeFile = ref.name + '.py';
						activeTab = 'code';
					}
				}
			} catch (e) {
				console.error('Failed to load module:', e);
			}
		}
	}

	// Get current code content
	let currentCodeContent = $derived(
		codeFiles[selectedCodeFile]?.content || '# No code file found'
	);

	// Calculate editor height (panel height - header height ~48px)
	let editorHeight = $derived(`${Math.max(100, panelHeight - 48)}px`);

	// Toggle collapse
	function toggleCollapse() {
		isCollapsed = !isCollapsed;
		dispatch('collapse', isCollapsed);
	}

	// Toggle maximize
	function toggleMaximize() {
		if (isMaximized) {
			panelHeight = previousHeight;
			isMaximized = false;
		} else {
			previousHeight = panelHeight;
			panelHeight = window.innerHeight - 150; // Leave space for header
			isMaximized = true;
		}
		dispatch('resize', panelHeight);
	}

	// Copy content to clipboard
	async function copyContent() {
		const content = activeTab === 'yaml' ? yamlContent : currentCodeContent;
		await navigator.clipboard.writeText(content);
		copied = true;
		setTimeout(() => copied = false, 2000);
	}

	// Refresh content
	function refresh() {
		if (activeTab === 'yaml') {
			loadYaml();
		} else {
			loadCode();
		}
	}

	// Resize handlers
	function startResize(e: MouseEvent) {
		isResizing = true;
		startY = e.clientY;
		startHeight = panelHeight;

		window.addEventListener('mousemove', handleResize);
		window.addEventListener('mouseup', stopResize);
	}

	function handleResize(e: MouseEvent) {
		if (!isResizing) return;

		const delta = startY - e.clientY;
		const newHeight = Math.max(150, Math.min(window.innerHeight - 200, startHeight + delta));
		panelHeight = newHeight;
	}

	function stopResize() {
		isResizing = false;
		window.removeEventListener('mousemove', handleResize);
		window.removeEventListener('mouseup', stopResize);
		dispatch('resize', panelHeight);
	}

	// Run code execution
	async function runCode(debug: boolean = false) {
		if (!selectedCodeFile || !codeFiles[selectedCodeFile]) {
			console.error('No file selected to run');
			return;
		}

		// ALWAYS save before running to ensure disk files are up-to-date
		// This is especially important for debug mode which reads files from disk
		console.log('Saving files before execution...', { yamlDirty, codeDirty, hasUnsavedChanges });
		const saved = await saveAllForced();
		if (!saved) {
			console.error('Failed to save changes before running');
			// Continue anyway - files might already be saved
		}

		const filePath = codeFiles[selectedCodeFile].path;
		const args = runArgs.trim() ? runArgs.trim().split(/\s+/) : [];

		try {
			const response = await fetch(`${API_BASE}/code/execute`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					file_path: filePath,
					args,
					workflow_id: workflowId,
					debug,
					breakpoints: debug ? breakpoints : []
				})
			});

			if (!response.ok) {
				throw new Error('Failed to start execution');
			}

			const data = await response.json();
			executionId = data.execution_id;
			isRunning = true;
			// For debugging, stay on code tab to see breakpoints and variables
			// For regular run, switch to output tab
			if (!debug) {
				activeTab = 'output';
			}
			console.log('[runCode] Started execution, debug=', debug, 'activeTab=', activeTab);

		} catch (e) {
			console.error('Run failed:', e);
		}
	}

	// Stop code execution
	async function stopExecution() {
		if (!executionId) return;

		try {
			await fetch(`${API_BASE}/code/executions/${executionId}/stop`, {
				method: 'POST'
			});
			isRunning = false;
		} catch (e) {
			console.error('Stop failed:', e);
		}
	}

	// Handle output panel events
	function handleOutputStop() {
		stopExecution();
	}

	function handleOutputClear() {
		executionId = null;
		currentDebugLine = null;
		isDebugPaused = false;
	}

	function handleDebugLocation(event: CustomEvent<{ line: number; file: string }>) {
		console.log('[EVENT] debugLocation:', event.detail.line);
		currentDebugLine = event.detail.line;
		// Only switch to code tab once on first location update
		if (!isDebugPaused) {
			activeTab = 'code';
		}
	}

	function handleDebugPaused(event: CustomEvent<{ reason: string }>) {
		console.log('[EVENT] debugPaused:', event.detail.reason);
		// Only switch tab if not already paused (first time pausing)
		if (!isDebugPaused) {
			activeTab = 'code';
		}
		isDebugPaused = true;
	}

	function handleDebugContinued() {
		console.log('[EVENT] debugContinued');
		isDebugPaused = false;
		currentDebugLine = null;
		debugVariables = [];
	}

	function handleDebugVariables(event: CustomEvent<{ variables: typeof debugVariables }>) {
		console.log('[EVENT] debugVariables:', event.detail.variables?.length);
		debugVariables = event.detail.variables || [];
	}

	// Toggle variable expansion and fetch children if needed
	async function toggleVarExpand(varKey: string, variablesReference: number) {
		console.log('[EXPAND] Toggle', varKey, 'ref=', variablesReference, 'expanded=', expandedVars.has(varKey));
		if (expandedVars.has(varKey)) {
			// Collapse
			expandedVars = new Set([...expandedVars].filter(k => k !== varKey));
		} else {
			// Expand
			expandedVars = new Set([...expandedVars, varKey]);

			// Fetch children if not already loaded and has reference
			if (variablesReference > 0 && !childVariables[variablesReference]) {
				console.log('[EXPAND] Fetching children for ref=', variablesReference);
				loadingVars = new Set([...loadingVars, variablesReference]);
				try {
					const response = await fetch(`${API_BASE}/debug/variables`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							session_id: executionId,
							variables_reference: variablesReference
						})
					});
					console.log('[EXPAND] Response status:', response.status);
					if (response.ok) {
						const data = await response.json();
						console.log('[EXPAND] Got', data.variables?.length, 'children');
						childVariables = { ...childVariables, [variablesReference]: data.variables || [] };
					} else {
						const errText = await response.text();
						console.error('[EXPAND] Error:', errText);
					}
				} catch (e) {
					console.error('[EXPAND] Failed to fetch variables:', e);
				} finally {
					loadingVars = new Set([...loadingVars].filter(v => v !== variablesReference));
				}
			} else {
				console.log('[EXPAND] Already have children:', childVariables[variablesReference]?.length);
			}
		}
	}

	// Debug action functions
	async function sendDebugAction(action: string) {
		if (!executionId) return;
		try {
			await fetch(`${API_BASE}/debug/action`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ session_id: executionId, action })
			});
		} catch (e) {
			console.error('Debug action failed:', e);
		}
	}
</script>

<div
	class="flex flex-col border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 transition-all duration-200"
	style={isCollapsed ? 'height: 40px;' : `height: ${panelHeight}px;`}
>
	<!-- Resize Handle -->
	{#if !isCollapsed}
		<div
			class="h-1 bg-gray-100 dark:bg-gray-800 hover:bg-violet-200 dark:hover:bg-violet-800 cursor-ns-resize flex items-center justify-center group transition-colors"
			onmousedown={startResize}
			role="separator"
			aria-orientation="horizontal"
		>
			<GripHorizontal size={14} class="text-gray-400 group-hover:text-violet-500 transition-colors" />
		</div>
	{/if}

	<!-- Header -->
	<div class="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
		<div class="flex items-center gap-4">
			<!-- Code Panel Title -->
			<div class="flex items-center gap-2">
				<div class="flex items-center gap-2 text-violet-600 dark:text-violet-400">
					<Code2 size={16} />
					<span class="text-sm font-medium">Code Panel</span>
				</div>
				<button
					onclick={toggleCollapse}
					class="p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded transition-colors"
					title={isCollapsed ? 'Expand panel' : 'Collapse panel'}
				>
					{#if isCollapsed}
						<ChevronUp size={18} class="text-gray-500" />
					{:else}
						<ChevronDown size={18} class="text-gray-500" />
					{/if}
				</button>
			</div>

			<!-- Tabs -->
			{#if !isCollapsed}
				<div class="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
					<button
						onclick={() => activeTab = 'yaml'}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'yaml' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'}"
					>
						<FileText size={14} />
						YAML
						{#if yamlDirty}
							<span class="w-2 h-2 bg-orange-500 rounded-full" title="Unsaved changes"></span>
						{/if}
					</button>
					<button
						onclick={() => activeTab = 'code'}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'code' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'}"
					>
						<FileCode2 size={14} />
						Code
						{#if codeDirty}
							<span class="w-2 h-2 bg-orange-500 rounded-full" title="Unsaved changes"></span>
						{/if}
					</button>
					<button
						onclick={() => activeTab = 'output'}
						class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors {activeTab === 'output' ? 'bg-white dark:bg-gray-700 text-violet-600 dark:text-violet-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'}"
					>
						<Terminal size={14} />
						Output
						{#if isRunning}
							<span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
						{/if}
					</button>
				</div>

				<!-- Code file selector -->
				{#if activeTab === 'code' && codeFileList.length > 1}
					<select
						bind:value={selectedCodeFile}
						class="text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1 text-gray-700 dark:text-gray-300 focus:outline-none focus:ring-2 focus:ring-violet-500"
					>
						{#each codeFileList as file}
							<option value={file}>{file}</option>
						{/each}
					</select>
				{/if}

				<!-- Save button (shown when there are unsaved changes) -->
				{#if (activeTab === 'yaml' && yamlDirty) || (activeTab === 'code' && codeDirty)}
					<button
						onclick={() => activeTab === 'yaml' ? saveYaml() : saveCode()}
						disabled={yamlSaving || codeSaving}
						class="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium transition-colors"
						title="Save changes (Ctrl+S)"
					>
						{#if yamlSaving || codeSaving}
							<RefreshCw size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						Save
					</button>
				{/if}

				<!-- Run/Debug buttons for code tab -->
				{#if activeTab === 'code' && codeFileList.length > 0}
					<div class="flex items-center gap-1 ml-2">
						{#if isDebugPaused}
							<!-- VS Code-style debug toolbar -->
							<div class="flex items-center gap-0.5 px-2 py-1 bg-[#3c3c3c] rounded-md shadow-lg border border-[#555]">
								<button
									onclick={() => sendDebugAction('continue')}
									class="p-1.5 hover:bg-[#505050] rounded transition-colors text-[#75beff]"
									title="Continue (F5)"
								>
									<Play size={16} fill="currentColor" />
								</button>
								<button
									onclick={() => sendDebugAction('step_over')}
									class="p-1.5 hover:bg-[#505050] rounded transition-colors text-[#75beff]"
									title="Step Over (F10)"
								>
									<SkipForward size={16} />
								</button>
								<button
									onclick={() => sendDebugAction('step_into')}
									class="p-1.5 hover:bg-[#505050] rounded transition-colors text-[#75beff]"
									title="Step Into (F11)"
								>
									<ArrowDownToLine size={16} />
								</button>
								<button
									onclick={() => sendDebugAction('step_out')}
									class="p-1.5 hover:bg-[#505050] rounded transition-colors text-[#75beff]"
									title="Step Out (Shift+F11)"
								>
									<ArrowUpFromLine size={16} />
								</button>
								<div class="w-px h-4 bg-[#555] mx-1"></div>
								<button
									onclick={stopExecution}
									class="p-1.5 hover:bg-[#505050] rounded transition-colors text-[#f14c4c]"
									title="Stop (Shift+F5)"
								>
									<Square size={16} fill="currentColor" />
								</button>
							</div>
						{:else if isRunning}
							<button
								onclick={stopExecution}
								class="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium transition-colors"
								title="Stop execution"
							>
								<Square size={14} />
								Stop
							</button>
						{:else}
							<button
								onclick={() => runCode(false)}
								class="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium transition-colors"
								title="Run code"
							>
								<Play size={14} />
								Run
							</button>
							<button
								onclick={() => runCode(true)}
								class="flex items-center gap-1.5 px-3 py-1.5 bg-orange-600 hover:bg-orange-700 text-white rounded-lg text-sm font-medium transition-colors relative"
								title={breakpoints.length > 0 ? `Debug with ${breakpoints.length} breakpoint(s)` : 'Debug code (click line numbers to set breakpoints)'}
							>
								<Bug size={14} />
								Debug
								{#if breakpoints.length > 0}
									<span class="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
										{breakpoints.length}
									</span>
								{/if}
							</button>
						{/if}
						<button
							onclick={() => showArgsInput = !showArgsInput}
							class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors {showArgsInput ? 'bg-gray-200 dark:bg-gray-700' : ''}"
							title="Configure arguments"
						>
							<Settings size={16} class="text-gray-500" />
						</button>
					</div>
				{/if}
			{/if}
		</div>

		<!-- Actions (only when expanded) -->
		{#if !isCollapsed}
			<div class="flex items-center gap-2">
				<!-- File path indicator -->
				{#if activeTab === 'yaml' && yamlPath}
					<span class="text-xs text-gray-500 dark:text-gray-500 font-mono truncate max-w-64" title={yamlPath}>
						{yamlPath.split('/').slice(-2).join('/')}
					</span>
				{:else if activeTab === 'code' && codeFiles[selectedCodeFile]?.path}
					<span class="text-xs text-gray-500 dark:text-gray-500 font-mono truncate max-w-64" title={codeFiles[selectedCodeFile]?.path}>
						{codeFiles[selectedCodeFile]?.path.split('/').slice(-2).join('/')}
					</span>
				{/if}

				<button
					onclick={refresh}
					class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					title="Refresh"
					disabled={yamlLoading || codeLoading}
				>
					<RefreshCw size={16} class="text-gray-500 {yamlLoading || codeLoading ? 'animate-spin' : ''}" />
				</button>

				<button
					onclick={copyContent}
					class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					title="Copy to clipboard"
				>
					{#if copied}
						<Check size={16} class="text-green-500" />
					{:else}
						<Copy size={16} class="text-gray-500" />
					{/if}
				</button>

				<button
					onclick={toggleMaximize}
					class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					title={isMaximized ? 'Restore' : 'Maximize'}
				>
					{#if isMaximized}
						<Minimize2 size={16} class="text-gray-500" />
					{:else}
						<Maximize2 size={16} class="text-gray-500" />
					{/if}
				</button>

				<!-- Separator -->
				<div class="w-px h-5 bg-gray-300 dark:bg-gray-600"></div>

				<!-- Collapse Button (closes/collapses the panel) -->
				<button
					onclick={() => dispatch('close')}
					class="p-1.5 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg transition-colors"
					title="Collapse panel"
				>
					<ChevronDown size={16} class="text-gray-500" />
				</button>
			</div>
		{/if}
	</div>

	<!-- Arguments input (shown when settings clicked) -->
	{#if !isCollapsed && showArgsInput && activeTab === 'code'}
		<div class="px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center gap-3">
			<label class="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">Arguments:</label>
			<input
				type="text"
				bind:value={runArgs}
				placeholder="e.g., --input data.json --verbose"
				class="flex-1 px-3 py-1.5 text-sm bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
			/>
			<button
				onclick={() => showArgsInput = false}
				class="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
				title="Close"
			>
				<X size={16} class="text-gray-500" />
			</button>
		</div>
	{/if}

	<!-- Content -->
	{#if !isCollapsed}
		<div class="flex-1 flex overflow-hidden">
			<!-- References Sidebar (only show when there are references) -->
			{#if showFileSidebar && referencedFiles.length > 0 && (activeTab === 'yaml' || activeTab === 'code')}
				<div class="bg-gray-900 border-r border-gray-700 flex flex-col" style="width: {sidebarWidth}px; min-width: {sidebarWidth}px">
					<!-- Sidebar Header -->
					<div class="flex items-center justify-between px-3 py-2 border-b border-gray-700">
						<span class="text-xs font-semibold text-gray-400 uppercase tracking-wide">References</span>
						<button
							onclick={() => showFileSidebar = false}
							class="p-0.5 hover:bg-gray-700 rounded"
							title="Hide sidebar"
						>
							<ChevronLeft size={14} class="text-gray-500" />
						</button>
					</div>

					<!-- Referenced Files -->
					<div class="flex-1 overflow-y-auto px-2 py-2">
						{#each referencedFiles as ref}
							<button
								onclick={() => openReferencedFile(ref)}
								class="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-300 transition-colors group"
								title={ref.path}
							>
								{#if ref.type === 'subgraph'}
									<FolderOpen size={14} class="text-blue-400" />
									<span class="truncate flex-1">{ref.name}</span>
									<span class="text-xs text-gray-600">subgraph</span>
								{:else}
									<File size={14} class="text-green-400" />
									<span class="truncate flex-1">{ref.name}</span>
									<span class="text-xs text-gray-600">module</span>
								{/if}
								<ExternalLink size={12} class="text-gray-600 group-hover:text-gray-400" />
							</button>
						{/each}
					</div>
				</div>
			{:else if !showFileSidebar && referencedFiles.length > 0 && (activeTab === 'yaml' || activeTab === 'code')}
				<!-- Collapsed sidebar toggle (only show if there are references) -->
				<button
					onclick={() => showFileSidebar = true}
					class="bg-gray-900 border-r border-gray-700 px-1 hover:bg-gray-800 transition-colors flex items-center"
					title="Show references ({referencedFiles.length})"
				>
					<ChevronRight size={14} class="text-gray-500" />
					<span class="text-xs text-gray-500 writing-mode-vertical">{referencedFiles.length}</span>
				</button>
			{/if}

			<!-- Editor Area -->
			<div class="flex-1 overflow-hidden">
				{#if activeTab === 'yaml'}
					{#if yamlLoading}
						<div class="flex items-center justify-center h-full">
							<div class="flex items-center gap-2 text-gray-500">
								<RefreshCw size={20} class="animate-spin" />
								<span>Loading YAML...</span>
							</div>
						</div>
					{:else if yamlError}
						<div class="flex items-center justify-center h-full">
							<div class="text-center text-red-500">
								<p class="font-medium">Error loading YAML</p>
								<p class="text-sm mt-1">{yamlError}</p>
							</div>
						</div>
					{:else}
						<MonacoEditor
							bind:value={yamlContent}
							language="yaml"
							readonly={false}
							theme="vs-dark"
							height={editorHeight}
							minimap={false}
							lineNumbers={true}
							on:save={() => saveYaml()}
						/>
					{/if}
				{:else if activeTab === 'code'}
					{#if codeLoading}
						<div class="flex items-center justify-center h-full">
							<div class="flex items-center gap-2 text-gray-500">
								<RefreshCw size={20} class="animate-spin" />
								<span>Loading code...</span>
							</div>
						</div>
					{:else if codeError}
						<div class="flex items-center justify-center h-full">
							<div class="text-center text-red-500">
								<p class="font-medium">Error loading code</p>
								<p class="text-sm mt-1">{codeError}</p>
							</div>
						</div>
					{:else if codeFileList.length === 0}
						<div class="flex items-center justify-center h-full">
							<div class="text-center text-gray-500">
								<FileCode2 size={32} class="mx-auto mb-2 opacity-50" />
								<p class="font-medium">No Python files found</p>
								<p class="text-sm mt-1">This workflow has no task_executor.py or other Python files</p>
							</div>
						</div>
					{:else}
						<!-- Code tab: Variables panel on LEFT, Monaco on RIGHT -->
						<div class="flex flex-1 overflow-hidden">
							<!-- Variables Panel - LEFT side when debugging -->
							{#if isDebugPaused}
								<div class="w-[320px] min-w-[280px] border-r border-[#3c3c3c] bg-[#252526] flex flex-col overflow-hidden">
									<!-- VS Code style header -->
									<div class="px-3 py-1.5 bg-[#3c3c3c] border-b border-[#252526] flex items-center justify-between">
										<span class="text-[11px] font-semibold text-[#cccccc] uppercase tracking-wide">Variables</span>
										{#if currentDebugLine}
											<span class="text-[10px] text-[#cccccc]/70">
												Line {currentDebugLine}
											</span>
										{/if}
									</div>
									<div class="flex-1 overflow-auto text-[12px]">
										{#if debugVariables.length === 0}
											<div class="flex flex-col items-center justify-center py-8 text-[#808080]">
												<Loader2 size={18} class="animate-spin mb-2" />
												<span class="text-[11px]">Loading variables...</span>
											</div>
										{:else}
											{#each Object.entries(groupedVariables) as [scope, vars]}
												<div class="border-b border-[#3c3c3c]">
													<!-- Scope header (collapsible) -->
													<div class="flex items-center gap-1 px-2 py-1 bg-[#2d2d2d] text-[11px] font-semibold text-[#cccccc]">
														<ChevronDown size={12} class="text-[#808080]" />
														<span>{scope}</span>
													</div>
													<!-- Variables in scope -->
													{#each vars as variable}
														{@const varKey = `${scope}:${variable.name}`}
														{@const hasChildren = (variable.variablesReference ?? 0) > 0}
														{@const isExpanded = expandedVars.has(varKey)}
														{@const isLoading = loadingVars.has(variable.variablesReference ?? 0)}
														<div class="select-text">
															<!-- Variable row -->
															<div
																class="flex items-center gap-1 px-2 py-0.5 hover:bg-[#2a2d2e] cursor-pointer"
																onclick={() => hasChildren && toggleVarExpand(varKey, variable.variablesReference ?? 0)}
															>
																<!-- Expand/collapse icon -->
																<span class="w-3 flex-shrink-0">
																	{#if hasChildren}
																		{#if isLoading}
																			<Loader2 size={10} class="animate-spin text-[#808080]" />
																		{:else if isExpanded}
																			<ChevronDown size={10} class="text-[#808080]" />
																		{:else}
																			<ChevronRight size={10} class="text-[#808080]" />
																		{/if}
																	{/if}
																</span>
																<!-- Variable name -->
																<span class="text-[#9cdcfe]">{variable.name}</span>
																<span class="text-[#808080] mx-1">=</span>
																<!-- Variable value (truncated) -->
																<span class="text-[#ce9178] truncate flex-1" title={variable.value}>
																	{variable.value.length > 50 ? variable.value.slice(0, 50) + '...' : variable.value}
																</span>
																{#if variable.type}
																	<span class="text-[#4ec9b0] text-[10px] ml-1 flex-shrink-0">{variable.type}</span>
																{/if}
															</div>
															<!-- Child variables (if expanded) -->
															{#if isExpanded && hasChildren && childVariables[variable.variablesReference ?? 0]}
																{#each childVariables[variable.variablesReference ?? 0] as child}
																	{@const childKey = `${variable.variablesReference}:${child.name}`}
																	{@const childHasChildren = (child.variablesReference ?? 0) > 0}
																	{@const childIsExpanded = expandedVars.has(childKey)}
																	{@const childIsLoading = loadingVars.has(child.variablesReference ?? 0)}
																	<div
																		class="flex items-center gap-1 px-2 py-0.5 pl-6 hover:bg-[#2a2d2e] cursor-pointer"
																		onclick={() => childHasChildren && toggleVarExpand(childKey, child.variablesReference ?? 0)}
																	>
																		<span class="w-3 flex-shrink-0">
																			{#if childHasChildren}
																				{#if childIsLoading}
																					<Loader2 size={10} class="animate-spin text-[#808080]" />
																				{:else if childIsExpanded}
																					<ChevronDown size={10} class="text-[#808080]" />
																				{:else}
																					<ChevronRight size={10} class="text-[#808080]" />
																				{/if}
																			{/if}
																		</span>
																		<span class="text-[#9cdcfe]">{child.name}</span>
																		<span class="text-[#808080] mx-1">=</span>
																		<span class="text-[#ce9178] truncate flex-1" title={child.value}>
																			{child.value.length > 40 ? child.value.slice(0, 40) + '...' : child.value}
																		</span>
																		{#if child.type}
																			<span class="text-[#4ec9b0] text-[10px] ml-1 flex-shrink-0">{child.type}</span>
																		{/if}
																	</div>
																	<!-- Level 2 children -->
																	{#if childIsExpanded && childHasChildren && childVariables[child.variablesReference ?? 0]}
																		{#each childVariables[child.variablesReference ?? 0] as grandchild}
																			<div class="flex items-center gap-1 px-2 py-0.5 pl-10 hover:bg-[#2a2d2e]">
																				<span class="w-3"></span>
																				<span class="text-[#9cdcfe]">{grandchild.name}</span>
																				<span class="text-[#808080] mx-1">=</span>
																				<span class="text-[#ce9178] truncate flex-1" title={grandchild.value}>
																					{grandchild.value.length > 30 ? grandchild.value.slice(0, 30) + '...' : grandchild.value}
																				</span>
																			</div>
																		{/each}
																	{/if}
																{/each}
															{/if}
														</div>
													{/each}
												</div>
											{/each}
										{/if}
									</div>
								</div>
							{/if}

							<!-- Monaco Editor -->
							<div class="flex-1 overflow-hidden">
								<MonacoEditor
									value={codeFiles[selectedCodeFile]?.content || ''}
									language="python"
									readonly={false}
									theme="vs-dark"
									height={editorHeight}
									minimap={false}
									lineNumbers={true}
									breakpointsEnabled={true}
									bind:breakpoints
									currentLine={currentDebugLine}
									on:breakpointsChange={(e) => { breakpoints = e.detail; }}
									on:change={(e) => {
										if (codeFiles[selectedCodeFile]) {
											codeFiles[selectedCodeFile].content = e.detail;
										}
									}}
									on:save={() => saveCode()}
								/>
							</div>
						</div>
					{/if}
				{/if}

				<!-- ExecutionOutputPanel - ALWAYS rendered but visibility controlled -->
				<div style={activeTab === 'output' ? '' : 'position: absolute; left: -9999px; visibility: hidden;'}>
					<ExecutionOutputPanel
						{executionId}
						bind:isRunning
						height={editorHeight}
						on:stop={handleOutputStop}
						on:clear={handleOutputClear}
						on:debugLocation={handleDebugLocation}
						on:debugPaused={handleDebugPaused}
						on:debugContinued={handleDebugContinued}
						on:debugVariables={handleDebugVariables}
					/>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	/* Prevent text selection during resize */
	:global(body.resizing) {
		user-select: none;
		cursor: ns-resize;
	}
</style>
