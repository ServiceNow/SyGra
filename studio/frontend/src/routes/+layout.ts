// This file configures the static adapter behavior for SvelteKit
// The app is a SPA (Single Page Application) that makes API calls

// Disable server-side rendering - this is a client-only SPA
export const ssr = false;

// Enable prerendering for the fallback page
export const prerender = true;
