<script lang="ts">
	import { Play, Pause, Volume2, VolumeX, Download } from 'lucide-svelte';

	interface Props {
		src: string;
		title?: string;
		compact?: boolean;
		showDownload?: boolean;
	}

	let { src, title = 'Audio', compact = false, showDownload = true }: Props = $props();

	// Audio element reference
	let audioElement: HTMLAudioElement | null = $state(null);

	// Player state
	let isPlaying = $state(false);
	let isMuted = $state(false);
	let currentTime = $state(0);
	let duration = $state(0);
	let volume = $state(0.8);
	let isLoading = $state(true);
	let error = $state<string | null>(null);

	// Format time as mm:ss
	function formatTime(seconds: number): string {
		if (!isFinite(seconds) || isNaN(seconds)) return '0:00';
		const mins = Math.floor(seconds / 60);
		const secs = Math.floor(seconds % 60);
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// Toggle play/pause
	function togglePlay() {
		if (!audioElement) return;
		if (isPlaying) {
			audioElement.pause();
		} else {
			audioElement.play().catch(e => {
				console.error('Audio play failed:', e);
				error = 'Failed to play audio';
			});
		}
	}

	// Toggle mute
	function toggleMute() {
		if (!audioElement) return;
		isMuted = !isMuted;
		audioElement.muted = isMuted;
	}

	// Handle seek
	function handleSeek(e: Event) {
		if (!audioElement) return;
		const target = e.target as HTMLInputElement;
		const time = parseFloat(target.value);
		audioElement.currentTime = time;
		currentTime = time;
	}

	// Handle volume change
	function handleVolumeChange(e: Event) {
		if (!audioElement) return;
		const target = e.target as HTMLInputElement;
		volume = parseFloat(target.value);
		audioElement.volume = volume;
		if (volume > 0 && isMuted) {
			isMuted = false;
			audioElement.muted = false;
		}
	}

	// Download audio
	function downloadAudio() {
		const link = document.createElement('a');
		link.href = src;
		link.download = title || 'audio';
		link.click();
	}

	// Audio event handlers
	function onLoadedMetadata() {
		if (audioElement) {
			duration = audioElement.duration;
			isLoading = false;
		}
	}

	function onTimeUpdate() {
		if (audioElement) {
			currentTime = audioElement.currentTime;
		}
	}

	function onPlay() {
		isPlaying = true;
	}

	function onPause() {
		isPlaying = false;
	}

	function onEnded() {
		isPlaying = false;
		if (audioElement) {
			audioElement.currentTime = 0;
			currentTime = 0;
		}
	}

	function onError() {
		isLoading = false;
		error = 'Failed to load audio';
	}

	function onCanPlay() {
		isLoading = false;
		error = null;
	}

	// Progress percentage for styling
	let progressPercent = $derived(duration > 0 ? (currentTime / duration) * 100 : 0);
</script>

<!-- Hidden audio element -->
<audio
	bind:this={audioElement}
	{src}
	preload="metadata"
	onloadedmetadata={onLoadedMetadata}
	ontimeupdate={onTimeUpdate}
	onplay={onPlay}
	onpause={onPause}
	onended={onEnded}
	onerror={onError}
	oncanplay={onCanPlay}
/>

{#if error}
	<!-- Error state -->
	<div class="flex items-center gap-2 px-3 py-2 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
		<span class="text-red-600 dark:text-red-400 text-xs">{error}</span>
	</div>
{:else if compact}
	<!-- Compact player for table cells -->
	<div class="flex items-center gap-2 min-w-[180px] max-w-[280px]">
		<!-- Play/Pause button -->
		<button
			onclick={togglePlay}
			disabled={isLoading}
			class="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full transition-colors
				{isPlaying
					? 'bg-[#7661FF] hover:bg-[#5a4acc] text-white'
					: 'bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300'}
				disabled:opacity-50 disabled:cursor-not-allowed"
			title={isPlaying ? 'Pause' : 'Play'}
		>
			{#if isLoading}
				<div class="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
			{:else if isPlaying}
				<Pause size={14} />
			{:else}
				<Play size={14} class="ml-0.5" />
			{/if}
		</button>

		<!-- Progress bar -->
		<div class="flex-1 flex items-center gap-2">
			<span class="text-[10px] text-gray-500 dark:text-gray-400 tabular-nums w-8 text-right">
				{formatTime(currentTime)}
			</span>
			<div class="flex-1 relative h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
				<div
					class="absolute left-0 top-0 h-full bg-[#7661FF] rounded-full transition-all duration-100"
					style="width: {progressPercent}%"
				></div>
				<input
					type="range"
					min="0"
					max={duration || 100}
					step="0.1"
					value={currentTime}
					oninput={handleSeek}
					class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
				/>
			</div>
			<span class="text-[10px] text-gray-500 dark:text-gray-400 tabular-nums w-8">
				{formatTime(duration)}
			</span>
		</div>

		<!-- Volume toggle (compact) -->
		<button
			onclick={toggleMute}
			class="flex-shrink-0 p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
			title={isMuted ? 'Unmute' : 'Mute'}
		>
			{#if isMuted || volume === 0}
				<VolumeX size={14} />
			{:else}
				<Volume2 size={14} />
			{/if}
		</button>
	</div>
{:else}
	<!-- Full player -->
	<div class="flex flex-col gap-2 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 min-w-[280px] max-w-[400px]">
		<!-- Title and controls row -->
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				<!-- Play/Pause button -->
				<button
					onclick={togglePlay}
					disabled={isLoading}
					class="w-9 h-9 flex items-center justify-center rounded-full transition-colors
						{isPlaying
							? 'bg-[#7661FF] hover:bg-[#5a4acc] text-white'
							: 'bg-white dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 border border-gray-300 dark:border-gray-600'}
						disabled:opacity-50 disabled:cursor-not-allowed"
					title={isPlaying ? 'Pause' : 'Play'}
				>
					{#if isLoading}
						<div class="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
					{:else if isPlaying}
						<Pause size={16} />
					{:else}
						<Play size={16} class="ml-0.5" />
					{/if}
				</button>

				<!-- Title -->
				{#if title}
					<span class="text-sm font-medium text-gray-700 dark:text-gray-300 truncate max-w-[150px]" {title}>
						{title}
					</span>
				{/if}
			</div>

			<!-- Right side controls -->
			<div class="flex items-center gap-1">
				{#if showDownload}
					<button
						onclick={downloadAudio}
						class="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
						title="Download audio"
					>
						<Download size={14} />
					</button>
				{/if}
			</div>
		</div>

		<!-- Progress bar row -->
		<div class="flex items-center gap-2">
			<span class="text-xs text-gray-500 dark:text-gray-400 tabular-nums w-10 text-right">
				{formatTime(currentTime)}
			</span>
			<div class="flex-1 relative h-2 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden group">
				<div
					class="absolute left-0 top-0 h-full bg-[#7661FF] rounded-full transition-all duration-100"
					style="width: {progressPercent}%"
				></div>
				<input
					type="range"
					min="0"
					max={duration || 100}
					step="0.1"
					value={currentTime}
					oninput={handleSeek}
					class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
				/>
			</div>
			<span class="text-xs text-gray-500 dark:text-gray-400 tabular-nums w-10">
				{formatTime(duration)}
			</span>
		</div>

		<!-- Volume row -->
		<div class="flex items-center gap-2">
			<button
				onclick={toggleMute}
				class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
				title={isMuted ? 'Unmute' : 'Mute'}
			>
				{#if isMuted || volume === 0}
					<VolumeX size={14} />
				{:else}
					<Volume2 size={14} />
				{/if}
			</button>
			<div class="flex-1 relative h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden max-w-[100px]">
				<div
					class="absolute left-0 top-0 h-full bg-gray-400 dark:bg-gray-500 rounded-full"
					style="width: {volume * 100}%"
				></div>
				<input
					type="range"
					min="0"
					max="1"
					step="0.05"
					value={volume}
					oninput={handleVolumeChange}
					class="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
				/>
			</div>
		</div>
	</div>
{/if}
