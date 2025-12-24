import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	compilerOptions: {
		// Suppress specific warnings that are false positives for common patterns
		warningFilter: (warning) => {
			// Suppress a11y warnings for modals and interactive patterns
			if (warning.code.startsWith('a11y_')) return false;
			// Suppress svelte:component deprecation (still works, will migrate later)
			if (warning.code === 'svelte_component_deprecated') return false;
			// Suppress non-reactive update for canvas/DOM refs (intentional)
			if (warning.code === 'non_reactive_update') return false;
			// Suppress state_referenced_locally for props (intentional pattern)
			if (warning.code === 'state_referenced_locally') return false;
			return true;
		}
	},
	kit: {
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html',
			precompress: false,
			strict: true
		}),
		paths: {
			base: ''
		}
	}
};

export default config;
