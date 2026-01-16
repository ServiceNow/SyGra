import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			'/api': {
				target: 'http://localhost:8000',
				changeOrigin: true
			},
			'/ws': {
				target: 'ws://localhost:8000',
				ws: true,
				changeOrigin: true
			}
		}
	},
	optimizeDeps: {
		include: ['monaco-editor']
	},
	build: {
		rollupOptions: {
			output: {
				manualChunks(id) {
					// Split heavy vendor libraries into separate chunks
					if (id.includes('chart.js')) {
						return 'vendor-chartjs';
					}
					if (id.includes('@xyflow/svelte') || id.includes('@xyflow/system')) {
						return 'vendor-xyflow';
					}
					if (id.includes('d3-dag') || id.includes('d3-array') || id.includes('d3-shape')) {
						return 'vendor-d3';
					}
				}
			}
		}
	}
});
