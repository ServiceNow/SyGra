<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import {
		X, CheckCircle2, XCircle, Clock, Loader2, FileJson, FileText,
		Calendar, Timer, Hash, Database, ChevronDown, Copy, Check,
		Activity, Layers, ArrowRight, DollarSign, Zap, Cpu, GitBranch,
		BarChart3, Coins, Server, Box, TrendingUp, AlertTriangle
	} from 'lucide-svelte';
	import type { Execution, ExecutionMetadata } from '$lib/stores/workflow.svelte';

	interface Props {
		execution: Execution;
	}

	let { execution }: Props = $props();

	const dispatch = createEventDispatcher<{ close: void }>();

	// Tab state
	type TabId = 'overview' | 'output' | 'logs' | 'metadata';
	let activeTab = $state<TabId>('overview');

	// Copy state
	let copiedField = $state<string | null>(null);

	// Status styling
	const statusConfig = {
		pending: { color: 'text-gray-500', bg: 'bg-gray-100 dark:bg-gray-800', icon: Clock },
		running: { color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-900/30', icon: Loader2 },
		completed: { color: 'text-green-500', bg: 'bg-green-100 dark:bg-green-900/30', icon: CheckCircle2 },
		failed: { color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-900/30', icon: XCircle },
		cancelled: { color: 'text-yellow-500', bg: 'bg-yellow-100 dark:bg-yellow-900/30', icon: XCircle }
	};

	let statusInfo = $derived(statusConfig[execution.status] || statusConfig.pending);
	let StatusIcon = $derived(statusInfo.icon);

	// Format duration
	function formatDuration(ms?: number): string {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
		const mins = Math.floor(ms / 60000);
		const secs = ((ms % 60000) / 1000).toFixed(1);
		return `${mins}m ${secs}s`;
	}

	// Format date
	function formatDate(date?: string): string {
		if (!date) return '-';
		return new Date(date).toLocaleString();
	}

	// Copy to clipboard
	async function copyToClipboard(text: string, field: string) {
		await navigator.clipboard.writeText(text);
		copiedField = field;
		setTimeout(() => copiedField = null, 2000);
	}

	// Handle escape key
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			dispatch('close');
		}
	}

	// Get sample output data (first few records)
	let sampleOutput = $derived(() => {
		if (!execution.output_data) return null;
		if (Array.isArray(execution.output_data)) {
			return execution.output_data.slice(0, 5);
		}
		return execution.output_data;
	});

	// Count output records
	let outputCount = $derived(() => {
		if (!execution.output_data) return 0;
		if (Array.isArray(execution.output_data)) {
			return execution.output_data.length;
		}
		return 1;
	});

	// Get metadata
	let metadata = $derived(execution.metadata);

	// Format helpers for metadata
	function formatCost(usd: number): string {
		if (usd < 0.01) return `$${(usd * 100).toFixed(3)}¢`;
		return `$${usd.toFixed(4)}`;
	}

	function formatNumber(n: number): string {
		if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
		if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
		return n.toLocaleString();
	}

	function formatPercent(rate: number): string {
		return `${(rate * 100).toFixed(1)}%`;
	}

	function formatLatency(seconds: number): string {
		if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`;
		return `${seconds.toFixed(2)}s`;
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onclick={() => dispatch('close')}>
	<div
		class="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] flex flex-col"
		onclick={(e) => e.stopPropagation()}
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-800">
			<div class="flex items-center gap-4">
				<div class="p-2 rounded-lg {statusInfo.bg}">
					<StatusIcon size={20} class={statusInfo.color} />
				</div>
				<div>
					<h3 class="text-lg font-semibold text-gray-800 dark:text-gray-200">
						Run Details
					</h3>
					<p class="text-sm text-gray-500 flex items-center gap-2">
						<span class="font-mono">{execution.id.slice(0, 8)}</span>
						<span>·</span>
						<span class="capitalize {statusInfo.color}">{execution.status}</span>
					</p>
				</div>
			</div>
			<button
				onclick={() => dispatch('close')}
				class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
			>
				<X size={20} />
			</button>
		</div>

		<!-- Tabs -->
		<div class="flex border-b border-gray-200 dark:border-gray-800 px-6">
			{#each [
				{ id: 'overview', label: 'Overview', icon: Activity },
				{ id: 'output', label: 'Output Data', icon: Database },
				{ id: 'logs', label: 'Logs', icon: FileText },
				{ id: 'metadata', label: 'Metadata', icon: Layers }
			] as tab}
				<button
					onclick={() => activeTab = tab.id as TabId}
					class="flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors"
					class:border-[#7661FF]={activeTab === tab.id}
					class:text-[#7661FF]={activeTab === tab.id}
					class:dark:text-[#52B8FF]={activeTab === tab.id}
					class:border-transparent={activeTab !== tab.id}
					class:text-gray-500={activeTab !== tab.id}
					class:hover:text-gray-700={activeTab !== tab.id}
					class:dark:hover:text-gray-300={activeTab !== tab.id}
				>
					<tab.icon size={16} />
					{tab.label}
				</button>
			{/each}
		</div>

		<!-- Body -->
		<div class="flex-1 overflow-y-auto p-6">
			{#if activeTab === 'overview'}
				<!-- Overview Tab -->
				<div class="grid grid-cols-2 gap-6">
					<!-- Left column: Run info -->
					<div class="space-y-4">
						<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
							Run Information
						</h4>

						<div class="space-y-3">
							<div class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<Hash size={16} class="text-gray-400 mt-0.5" />
								<div class="flex-1 min-w-0">
									<div class="text-xs text-gray-500 uppercase">Execution ID</div>
									<div class="text-sm font-mono text-gray-800 dark:text-gray-200 flex items-center gap-2">
										<span class="truncate">{execution.id}</span>
										<button
											onclick={() => copyToClipboard(execution.id, 'id')}
											class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
										>
											{#if copiedField === 'id'}
												<Check size={12} class="text-green-500" />
											{:else}
												<Copy size={12} class="text-gray-400" />
											{/if}
										</button>
									</div>
								</div>
							</div>

							<div class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<Layers size={16} class="text-gray-400 mt-0.5" />
								<div>
									<div class="text-xs text-gray-500 uppercase">Workflow</div>
									<div class="text-sm text-gray-800 dark:text-gray-200">
										{execution.workflow_name || execution.workflow_id}
									</div>
								</div>
							</div>

							<div class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<Calendar size={16} class="text-gray-400 mt-0.5" />
								<div>
									<div class="text-xs text-gray-500 uppercase">Started</div>
									<div class="text-sm text-gray-800 dark:text-gray-200">
										{formatDate(execution.started_at)}
									</div>
								</div>
							</div>

							<div class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<Timer size={16} class="text-gray-400 mt-0.5" />
								<div>
									<div class="text-xs text-gray-500 uppercase">Duration</div>
									<div class="text-sm text-gray-800 dark:text-gray-200">
										{formatDuration(execution.duration_ms)}
									</div>
								</div>
							</div>

							{#if execution.output_file}
								<div class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
									<FileJson size={16} class="text-gray-400 mt-0.5" />
									<div class="flex-1 min-w-0">
										<div class="text-xs text-gray-500 uppercase">Output File</div>
										<div class="text-sm font-mono text-gray-800 dark:text-gray-200 truncate">
											{execution.output_file}
										</div>
									</div>
								</div>
							{/if}
						</div>
					</div>

					<!-- Right column: Node states & stats -->
					<div class="space-y-4">
						<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
							Node Execution
						</h4>

						<div class="space-y-2">
							{#each Object.entries(execution.node_states) as [nodeId, state]}
								{@const nodeStatus = statusConfig[state.status] || statusConfig.pending}
								{@const NodeIcon = nodeStatus.icon}
								<div class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
									<NodeIcon size={16} class={nodeStatus.color} />
									<div class="flex-1 min-w-0">
										<div class="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">
											{nodeId}
										</div>
										{#if state.duration_ms}
											<div class="text-xs text-gray-500">
												{formatDuration(state.duration_ms)}
											</div>
										{/if}
									</div>
									<span class="text-xs capitalize px-2 py-0.5 rounded-full {nodeStatus.bg} {nodeStatus.color}">
										{state.status}
									</span>
								</div>
							{/each}
						</div>

						{#if execution.error}
							<div class="mt-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
								<div class="text-sm font-medium text-red-700 dark:text-red-400 mb-1">Error</div>
								<div class="text-sm text-red-600 dark:text-red-300 font-mono">
									{execution.error}
								</div>
							</div>
						{/if}
					</div>
				</div>

			{:else if activeTab === 'output'}
				<!-- Output Data Tab -->
				<div class="space-y-4">
					{#if execution.output_data}
						<div class="flex items-center justify-between mb-4">
							<div class="text-sm text-gray-500">
								Showing {Math.min(5, outputCount())} of {outputCount()} records
							</div>
							<button
								onclick={() => copyToClipboard(JSON.stringify(execution.output_data, null, 2), 'output')}
								class="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 rounded-lg transition-colors"
							>
								{#if copiedField === 'output'}
									<Check size={14} class="text-green-500" />
									Copied!
								{:else}
									<Copy size={14} />
									Copy All
								{/if}
							</button>
						</div>

						<!-- Sample records display -->
						<div class="space-y-4">
							{#each (Array.isArray(sampleOutput()) ? sampleOutput() : [sampleOutput()]) as record, i}
								<div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg overflow-hidden">
									<div class="px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
										<span class="text-sm font-medium text-gray-600 dark:text-gray-400">
											Record {i + 1}
										</span>
									</div>
									<div class="p-4">
										{#if typeof record === 'object' && record !== null}
											<div class="space-y-2">
												{#each Object.entries(record) as [key, value]}
													<div class="grid grid-cols-3 gap-2 text-sm">
														<div class="font-medium text-gray-600 dark:text-gray-400 truncate" title={key}>
															{key}
														</div>
														<div class="col-span-2 text-gray-800 dark:text-gray-200 break-words">
															{#if typeof value === 'object'}
																<details class="cursor-pointer">
																	<summary class="text-[#032D42] dark:text-[#52B8FF] hover:underline">
																		{Array.isArray(value) ? `[${value.length} items]` : '{object}'}
																	</summary>
																	<pre class="mt-2 p-2 bg-gray-900 text-gray-100 rounded text-xs overflow-x-auto max-h-40">{JSON.stringify(value, null, 2)}</pre>
																</details>
															{:else if typeof value === 'string' && value.length > 200}
																<details class="cursor-pointer">
																	<summary class="text-[#032D42] dark:text-[#52B8FF] hover:underline">
																		{value.slice(0, 100)}...
																	</summary>
																	<div class="mt-2 p-2 bg-gray-100 dark:bg-gray-900 rounded text-xs whitespace-pre-wrap">
																		{value}
																	</div>
																</details>
															{:else}
																{String(value)}
															{/if}
														</div>
													</div>
												{/each}
											</div>
										{:else}
											<pre class="text-sm text-gray-800 dark:text-gray-200">{JSON.stringify(record, null, 2)}</pre>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					{:else}
						<div class="text-center py-12 text-gray-500">
							<Database size={48} class="mx-auto mb-4 opacity-50" />
							<p>No output data available</p>
						</div>
					{/if}
				</div>

			{:else if activeTab === 'logs'}
				<!-- Logs Tab -->
				<div class="bg-gray-900 rounded-lg p-4 max-h-96 overflow-auto">
					{#if execution.logs.length > 0}
						{#each execution.logs as log}
							<div class="text-xs text-gray-300 font-mono leading-relaxed">{log}</div>
						{/each}
					{:else}
						<div class="text-center py-8 text-gray-500">
							<FileText size={32} class="mx-auto mb-2 opacity-50" />
							<p class="text-sm">No logs captured</p>
						</div>
					{/if}
				</div>

			{:else if activeTab === 'metadata'}
				<!-- Metadata Tab - Rich visualization -->
				{#if metadata}
					<div class="space-y-6">
						<!-- Key Metrics Cards -->
						<div class="grid grid-cols-4 gap-4">
							<!-- Cost Card -->
							<div class="bg-gradient-to-br from-emerald-50 to-emerald-100 dark:from-emerald-900/20 dark:to-emerald-800/20 rounded-xl p-4 border border-emerald-200 dark:border-emerald-800">
								<div class="flex items-center gap-2 mb-2">
									<DollarSign size={16} class="text-emerald-600 dark:text-emerald-400" />
									<span class="text-xs font-medium text-emerald-600 dark:text-emerald-400 uppercase">Total Cost</span>
								</div>
								<div class="text-2xl font-bold text-emerald-700 dark:text-emerald-300">
									{formatCost(metadata.aggregate_statistics.cost.total_cost_usd)}
								</div>
								<div class="text-xs text-emerald-600/70 dark:text-emerald-400/70 mt-1">
									{formatCost(metadata.aggregate_statistics.cost.average_cost_per_record)}/record
								</div>
							</div>

							<!-- Tokens Card -->
							<div class="bg-gradient-to-br from-[#7661FF]/10 to-[#7661FF]/20 dark:from-[#7661FF]/15 dark:to-[#7661FF]/25 rounded-xl p-4 border border-[#7661FF]/30 dark:border-[#7661FF]/40">
								<div class="flex items-center gap-2 mb-2">
									<Zap size={16} class="text-[#7661FF] dark:text-[#BF71F2]" />
									<span class="text-xs font-medium text-[#7661FF] dark:text-[#BF71F2] uppercase">Total Tokens</span>
								</div>
								<div class="text-2xl font-bold text-[#7661FF] dark:text-[#52B8FF]">
									{formatNumber(metadata.aggregate_statistics.tokens.total_tokens)}
								</div>
								<div class="text-xs text-[#7661FF]/70 dark:text-[#52B8FF]/70 mt-1">
									{formatNumber(metadata.aggregate_statistics.tokens.total_prompt_tokens)} prompt · {formatNumber(metadata.aggregate_statistics.tokens.total_completion_tokens)} completion
								</div>
							</div>

							<!-- Success Rate Card -->
							<div class="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-4 border border-blue-200 dark:border-blue-800">
								<div class="flex items-center gap-2 mb-2">
									<TrendingUp size={16} class="text-blue-600 dark:text-blue-400" />
									<span class="text-xs font-medium text-blue-600 dark:text-blue-400 uppercase">Success Rate</span>
								</div>
								<div class="text-2xl font-bold text-blue-700 dark:text-blue-300">
									{formatPercent(metadata.aggregate_statistics.records.success_rate)}
								</div>
								<div class="text-xs text-blue-600/70 dark:text-blue-400/70 mt-1">
									{metadata.aggregate_statistics.records.total_processed} processed · {metadata.aggregate_statistics.records.total_failed} failed
								</div>
							</div>

							<!-- Requests Card -->
							<div class="bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/20 dark:to-amber-800/20 rounded-xl p-4 border border-amber-200 dark:border-amber-800">
								<div class="flex items-center gap-2 mb-2">
									<Server size={16} class="text-amber-600 dark:text-amber-400" />
									<span class="text-xs font-medium text-amber-600 dark:text-amber-400 uppercase">API Requests</span>
								</div>
								<div class="text-2xl font-bold text-amber-700 dark:text-amber-300">
									{metadata.aggregate_statistics.requests.total_requests}
								</div>
								<div class="text-xs text-amber-600/70 dark:text-amber-400/70 mt-1">
									{metadata.aggregate_statistics.requests.total_retries} retries · {metadata.aggregate_statistics.requests.total_failures} failures
								</div>
							</div>
						</div>

						<!-- Execution & Dataset Info -->
						<div class="grid grid-cols-2 gap-4">
							<!-- Execution Info -->
							<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
									<Activity size={16} />
									Execution Details
								</h4>
								<div class="space-y-2 text-sm">
									<div class="flex justify-between">
										<span class="text-gray-500">Task:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.execution.task_name}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Run Name:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.execution.run_name}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Duration:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.execution.timing.duration_seconds.toFixed(2)}s</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Batch Size:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.execution.batch_size}</span>
									</div>
									{#if metadata.execution.git}
										<div class="flex justify-between items-center">
											<span class="text-gray-500 flex items-center gap-1"><GitBranch size={12} /> Git:</span>
											<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">
												{metadata.execution.git.branch} @ {metadata.execution.git.commit_hash.slice(0, 7)}
												{#if metadata.execution.git.is_dirty}
													<span class="text-amber-500 ml-1">*</span>
												{/if}
											</span>
										</div>
									{/if}
								</div>
							</div>

							<!-- Dataset Info -->
							<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
									<Database size={16} />
									Dataset
								</h4>
								<div class="space-y-2 text-sm">
									<div class="flex justify-between">
										<span class="text-gray-500">Source:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs truncate max-w-48" title={metadata.dataset.source_path}>
											{metadata.dataset.source_path}
										</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Type:</span>
										<span class="text-gray-800 dark:text-gray-200 uppercase text-xs px-2 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">
											{metadata.dataset.source_type}
										</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Records:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.dataset.num_records_processed}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Start Index:</span>
										<span class="text-gray-800 dark:text-gray-200">{metadata.dataset.start_index}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Hash:</span>
										<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.dataset.dataset_hash}</span>
									</div>
								</div>
							</div>
						</div>

						<!-- Models Section -->
						{#if Object.keys(metadata.models).length > 0}
							<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
									<Cpu size={16} />
									Model Performance
								</h4>
								<div class="space-y-3">
									{#each Object.entries(metadata.models) as [modelName, model]}
										{@const latencyRange = model.performance.latency_statistics.max - model.performance.latency_statistics.min}
										{@const p50Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p50 - model.performance.latency_statistics.min) / latencyRange) * 100 : 50}
										{@const p95Pct = latencyRange > 0 ? ((model.performance.latency_statistics.p95 - model.performance.latency_statistics.min) / latencyRange) * 100 : 95}
										<div class="bg-white dark:bg-gray-900 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
											<div class="flex items-center justify-between mb-3">
												<div>
													<span class="font-medium text-gray-800 dark:text-gray-200">{modelName}</span>
													<span class="text-xs text-gray-500 ml-2">{model.model_type}</span>
												</div>
												<div class="flex items-center gap-4 text-sm">
													<span class="text-emerald-600 dark:text-emerald-400 font-medium">{formatCost(model.cost.total_cost_usd)}</span>
													<span class="text-[#7661FF] dark:text-[#52B8FF]">{formatNumber(model.token_statistics.total_tokens)} tokens</span>
												</div>
											</div>
											<div class="grid grid-cols-4 gap-4 text-xs">
												<div>
													<div class="text-gray-500 mb-1">Requests</div>
													<div class="font-medium text-gray-800 dark:text-gray-200">{model.performance.total_requests}</div>
												</div>
												<div>
													<div class="text-gray-500 mb-1">Avg Latency</div>
													<div class="font-medium text-gray-800 dark:text-gray-200">{formatLatency(model.performance.average_latency_seconds)}</div>
												</div>
												<div>
													<div class="text-gray-500 mb-1">Throughput</div>
													<div class="font-medium text-gray-800 dark:text-gray-200">{model.performance.tokens_per_second.toFixed(1)} tok/s</div>
												</div>
												<div>
													<div class="text-gray-500 mb-1">P95 Latency</div>
													<div class="font-medium text-gray-800 dark:text-gray-200">{formatLatency(model.performance.latency_statistics.p95)}</div>
												</div>
											</div>
											<!-- Latency distribution bar -->
											<div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
												<div class="flex items-center gap-2 text-xs text-gray-500 mb-2">
													<span>Latency Distribution:</span>
													<span>min {formatLatency(model.performance.latency_statistics.min)}</span>
													<span>→</span>
													<span>p50 {formatLatency(model.performance.latency_statistics.p50)}</span>
													<span>→</span>
													<span>max {formatLatency(model.performance.latency_statistics.max)}</span>
												</div>
												<div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
													<div class="h-full flex">
														<div class="bg-emerald-400" style="width: {p50Pct}%"></div>
														<div class="bg-amber-400" style="width: {p95Pct - p50Pct}%"></div>
														<div class="bg-red-400" style="width: {100 - p95Pct}%"></div>
													</div>
												</div>
												<div class="flex justify-between text-xs text-gray-500 mt-1">
													<span class="flex items-center gap-1"><span class="w-2 h-2 bg-emerald-400 rounded"></span> ≤p50</span>
													<span class="flex items-center gap-1"><span class="w-2 h-2 bg-amber-400 rounded"></span> p50-p95</span>
													<span class="flex items-center gap-1"><span class="w-2 h-2 bg-red-400 rounded"></span> >p95</span>
												</div>
											</div>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						<!-- Nodes Section -->
						{#if Object.keys(metadata.nodes).length > 0}
							<div class="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-4">
								<h4 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
									<Box size={16} />
									Node Execution Stats
								</h4>
								<div class="overflow-x-auto">
									<table class="w-full text-sm">
										<thead>
											<tr class="text-left text-xs text-gray-500 uppercase border-b border-gray-200 dark:border-gray-700">
												<th class="pb-2 font-medium">Node</th>
												<th class="pb-2 font-medium">Type</th>
												<th class="pb-2 font-medium text-right">Executions</th>
												<th class="pb-2 font-medium text-right">Avg Latency</th>
												<th class="pb-2 font-medium text-right">P95</th>
												<th class="pb-2 font-medium text-right">Tokens</th>
											</tr>
										</thead>
										<tbody>
											{#each Object.entries(metadata.nodes) as [nodeName, node]}
												<tr class="border-b border-gray-100 dark:border-gray-800">
													<td class="py-2 font-medium text-gray-800 dark:text-gray-200">{nodeName}</td>
													<td class="py-2">
														<span class="text-xs px-2 py-0.5 rounded bg-[#7661FF]/15 dark:bg-[#7661FF]/20 text-[#7661FF] dark:text-[#52B8FF]">
															{node.node_type}
														</span>
													</td>
													<td class="py-2 text-right text-gray-600 dark:text-gray-400">{node.total_executions}</td>
													<td class="py-2 text-right text-gray-600 dark:text-gray-400">{formatLatency(node.average_latency_seconds)}</td>
													<td class="py-2 text-right text-gray-600 dark:text-gray-400">{formatLatency(node.latency_statistics.p95)}</td>
													<td class="py-2 text-right text-gray-600 dark:text-gray-400">
														{#if node.token_statistics}
															{formatNumber(node.token_statistics.total_tokens)}
														{:else}
															-
														{/if}
													</td>
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							</div>
						{/if}

						<!-- Environment Info -->
						<details class="group">
							<summary class="cursor-pointer text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 flex items-center gap-2">
								<ChevronDown size={16} class="transition-transform group-open:rotate-180" />
								Environment & Raw Data
							</summary>
							<div class="mt-3 space-y-3">
								<div class="grid grid-cols-2 gap-4">
									<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
										<div class="text-xs text-gray-500 uppercase mb-2">Environment</div>
										<div class="text-sm space-y-1">
											<div class="flex justify-between">
												<span class="text-gray-500">Python:</span>
												<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.execution.environment.python_version.split(' ')[0]}</span>
											</div>
											<div class="flex justify-between">
												<span class="text-gray-500">SyGra:</span>
												<span class="text-gray-800 dark:text-gray-200 font-mono text-xs">{metadata.execution.environment.sygra_version}</span>
											</div>
										</div>
									</div>
									<div class="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
										<div class="text-xs text-gray-500 uppercase mb-2">Metadata File</div>
										<div class="text-xs font-mono text-gray-600 dark:text-gray-400 break-all">
											{execution.metadata_file || 'N/A'}
										</div>
									</div>
								</div>
								<pre class="p-4 bg-gray-900 text-gray-100 rounded-lg text-xs overflow-auto max-h-64">{JSON.stringify(metadata, null, 2)}</pre>
							</div>
						</details>
					</div>
				{:else}
					<!-- Fallback when no metadata -->
					<div class="space-y-4">
						<div class="text-center py-8 text-gray-500">
							<BarChart3 size={48} class="mx-auto mb-4 opacity-50" />
							<p class="text-sm font-medium">No metadata available</p>
							<p class="text-xs mt-1">Metadata is collected when runs complete with metadata enabled</p>
						</div>

						<div class="grid grid-cols-2 gap-4">
							<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<div class="text-xs text-gray-500 uppercase mb-1">Input Data</div>
								<pre class="text-sm text-gray-800 dark:text-gray-200 overflow-auto max-h-40">{JSON.stringify(execution.input_data, null, 2)}</pre>
							</div>
							<div class="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
								<div class="text-xs text-gray-500 uppercase mb-1">Execution Timeline</div>
								<div class="space-y-2 text-sm">
									<div class="flex justify-between">
										<span class="text-gray-500">Started:</span>
										<span class="text-gray-800 dark:text-gray-200">{formatDate(execution.started_at)}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Completed:</span>
										<span class="text-gray-800 dark:text-gray-200">{formatDate(execution.completed_at)}</span>
									</div>
									<div class="flex justify-between">
										<span class="text-gray-500">Duration:</span>
										<span class="text-gray-800 dark:text-gray-200">{formatDuration(execution.duration_ms)}</span>
									</div>
								</div>
							</div>
						</div>
					</div>
				{/if}
			{/if}
		</div>

		<!-- Footer -->
		<div class="flex items-center justify-end px-6 py-4 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-200 dark:border-gray-700 rounded-b-xl">
			<button
				onclick={() => dispatch('close')}
				class="px-4 py-2 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 transition-colors"
			>
				Close
			</button>
		</div>
	</div>
</div>
