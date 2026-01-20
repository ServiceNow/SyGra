<script lang="ts">
	import { useSvelteFlow } from '@xyflow/svelte';
	import { Download, Image, FileImage, FileCode, FileText, ChevronDown } from 'lucide-svelte';
	import html2canvas from 'html2canvas';
	import { jsPDF } from 'jspdf';

	interface Props {
		workflowName?: string;
	}

	let { workflowName = 'workflow' }: Props = $props();

	const { fitView } = useSvelteFlow();

	let showDropdown = $state(false);
	let isExporting = $state(false);

	// Get device pixel ratio (2 for Retina displays)
	function getPixelRatio(): number {
		return window.devicePixelRatio || 1;
	}

	// Get the SvelteFlow container element
	function getFlowContainer(): HTMLElement | null {
		return document.querySelector('.svelte-flow');
	}

	// CSS class name for hiding elements during export
	const EXPORT_HIDE_CLASS = 'export-hidden';

	// Elements to hide during export (UI overlays)
	const ELEMENTS_TO_HIDE = [
		'.svelte-flow__panel',        // All panels (export button, minimap container)
		'.svelte-flow__controls',     // Zoom controls
		'.svelte-flow__minimap',      // Minimap (if rendered separately)
		'.svelte-flow__background',   // Background pattern
		'.svelte-flow__attribution',  // Attribution link
	];

	// Add global style for hiding elements during export
	function ensureExportStyles() {
		if (!document.getElementById('export-hide-styles')) {
			const style = document.createElement('style');
			style.id = 'export-hide-styles';
			style.textContent = `.${EXPORT_HIDE_CLASS} { display: none !important; visibility: hidden !important; }`;
			document.head.appendChild(style);
		}
	}

	// Hide UI elements during export using class
	function hideUIElements(): Element[] {
		ensureExportStyles();
		const hiddenElements: Element[] = [];

		ELEMENTS_TO_HIDE.forEach(selector => {
			document.querySelectorAll(selector).forEach(el => {
				el.classList.add(EXPORT_HIDE_CLASS);
				hiddenElements.push(el);
			});
		});

		return hiddenElements;
	}

	// Restore UI elements after export by removing class
	function restoreUIElements(elements: Element[]) {
		elements.forEach(el => {
			el.classList.remove(EXPORT_HIDE_CLASS);
		});
	}

	// Prepare for export: fit view and wait for render
	async function prepareForExport(): Promise<void> {
		// Fit view to show all nodes with generous padding
		await fitView({ padding: 0.2, duration: 0 });
		// Wait for rendering to complete
		await new Promise(resolve => setTimeout(resolve, 300));
	}

	// Generate filename with timestamp
	function getFilename(extension: string): string {
		const sanitizedName = workflowName.replace(/[^a-z0-9]/gi, '_').toLowerCase();
		const timestamp = new Date().toISOString().slice(0, 10);
		return `${sanitizedName}_${timestamp}.${extension}`;
	}

	// Capture the full container with proper Retina support
	// Key insight: Clone element to position (0,0) to avoid html2canvas positioning issues
	async function captureCanvas(container: HTMLElement): Promise<HTMLCanvasElement> {
		const pixelRatio = getPixelRatio();

		// Create an offscreen wrapper at origin to isolate from page layout
		const wrapper = document.createElement('div');
		wrapper.style.cssText = `
			position: fixed;
			left: 0;
			top: 0;
			width: ${container.offsetWidth}px;
			height: ${container.offsetHeight}px;
			overflow: hidden;
			z-index: -9999;
			pointer-events: none;
		`;

		// Clone the container into the wrapper at origin
		const clone = container.cloneNode(true) as HTMLElement;
		clone.style.cssText = `
			position: absolute;
			left: 0;
			top: 0;
			width: ${container.offsetWidth}px;
			height: ${container.offsetHeight}px;
		`;
		wrapper.appendChild(clone);
		document.body.appendChild(wrapper);

		try {
			// Capture the isolated clone - no positioning issues since it's at (0,0)
			const canvas = await html2canvas(clone, {
				backgroundColor: '#ffffff',
				scale: pixelRatio,
				logging: false,
				useCORS: true,
				allowTaint: true,
				foreignObjectRendering: true,
			});

			return canvas;
		} finally {
			// Clean up the temporary wrapper
			document.body.removeChild(wrapper);
		}
	}

	// Export as PNG
	async function exportPNG() {
		isExporting = true;
		showDropdown = false;

		const hiddenElements = hideUIElements();

		try {
			await prepareForExport();
			const container = getFlowContainer();
			if (!container) throw new Error('Flow container not found');

			const canvas = await captureCanvas(container);

			const link = document.createElement('a');
			link.download = getFilename('png');
			link.href = canvas.toDataURL('image/png');
			link.click();
		} catch (e) {
			console.error('Failed to export PNG:', e);
		} finally {
			restoreUIElements(hiddenElements);
			isExporting = false;
		}
	}

	// Export as JPG
	async function exportJPG() {
		isExporting = true;
		showDropdown = false;

		const hiddenElements = hideUIElements();

		try {
			await prepareForExport();
			const container = getFlowContainer();
			if (!container) throw new Error('Flow container not found');

			const canvas = await captureCanvas(container);

			const link = document.createElement('a');
			link.download = getFilename('jpg');
			link.href = canvas.toDataURL('image/jpeg', 0.95);
			link.click();
		} catch (e) {
			console.error('Failed to export JPG:', e);
		} finally {
			restoreUIElements(hiddenElements);
			isExporting = false;
		}
	}

	// Export as SVG (embedded PNG for compatibility)
	async function exportSVG() {
		isExporting = true;
		showDropdown = false;

		const hiddenElements = hideUIElements();

		try {
			await prepareForExport();
			const container = getFlowContainer();
			if (!container) throw new Error('Flow container not found');

			const canvas = await captureCanvas(container);

			// Create SVG with embedded image
			const svgContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}">
  <image href="${canvas.toDataURL('image/png')}" width="${canvas.width}" height="${canvas.height}"/>
</svg>`;

			const blob = new Blob([svgContent], { type: 'image/svg+xml' });
			const url = URL.createObjectURL(blob);
			const link = document.createElement('a');
			link.download = getFilename('svg');
			link.href = url;
			link.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			console.error('Failed to export SVG:', e);
		} finally {
			restoreUIElements(hiddenElements);
			isExporting = false;
		}
	}

	// Export as PDF
	async function exportPDF() {
		isExporting = true;
		showDropdown = false;

		const hiddenElements = hideUIElements();

		try {
			await prepareForExport();
			const container = getFlowContainer();
			if (!container) throw new Error('Flow container not found');

			const canvas = await captureCanvas(container);

			const imgData = canvas.toDataURL('image/png');
			const imgWidth = canvas.width;
			const imgHeight = canvas.height;

			// Determine orientation
			const isLandscape = imgWidth > imgHeight;

			// Scale down for PDF to get reasonable dimensions
			const pdfScale = 2; // Divide by 2 for reasonable PDF size
			const pdfWidth = imgWidth / pdfScale;
			const pdfHeight = imgHeight / pdfScale;

			const pdf = new jsPDF({
				orientation: isLandscape ? 'landscape' : 'portrait',
				unit: 'px',
				format: [pdfWidth, pdfHeight]
			});

			pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
			pdf.save(getFilename('pdf'));
		} catch (e) {
			console.error('Failed to export PDF:', e);
		} finally {
			restoreUIElements(hiddenElements);
			isExporting = false;
		}
	}

	// Close dropdown when clicking outside
	function handleClickOutside(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.export-dropdown')) {
			showDropdown = false;
		}
	}
</script>

<svelte:window onclick={handleClickOutside} />

<div class="export-dropdown relative">
	<button
		onclick={() => showDropdown = !showDropdown}
		disabled={isExporting}
		class="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors text-sm font-medium text-gray-700 dark:text-gray-300 disabled:opacity-50"
		title="Export graph"
	>
		{#if isExporting}
			<div class="w-4 h-4 border-2 border-gray-400 border-t-transparent rounded-full animate-spin"></div>
		{:else}
			<Download size={16} />
		{/if}
		<span class="hidden sm:inline">Export</span>
		<ChevronDown size={14} class="transition-transform {showDropdown ? 'rotate-180' : ''}" />
	</button>

	{#if showDropdown}
		<div class="absolute top-full right-0 mt-1 w-40 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg overflow-hidden z-50">
			<button
				onclick={exportPNG}
				class="w-full px-3 py-2 flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
			>
				<Image size={16} class="text-blue-500" />
				PNG
			</button>
			<button
				onclick={exportJPG}
				class="w-full px-3 py-2 flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
			>
				<FileImage size={16} class="text-green-500" />
				JPG
			</button>
			<button
				onclick={exportSVG}
				class="w-full px-3 py-2 flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
			>
				<FileCode size={16} class="text-orange-500" />
				SVG
			</button>
			<button
				onclick={exportPDF}
				class="w-full px-3 py-2 flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
			>
				<FileText size={16} class="text-red-500" />
				PDF
			</button>
		</div>
	{/if}
</div>
