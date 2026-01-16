/**
 * Media detection and formatting utilities for audio, image, and video content.
 */

// Supported audio MIME types and extensions
export const AUDIO_MIME_TYPES = [
	'audio/mpeg',
	'audio/mp3',
	'audio/wav',
	'audio/wave',
	'audio/x-wav',
	'audio/ogg',
	'audio/opus',
	'audio/aac',
	'audio/flac',
	'audio/x-flac',
	'audio/m4a',
	'audio/x-m4a',
	'audio/mp4',
	'audio/aiff',
	'audio/x-aiff',
	'audio/webm'
] as const;

export const AUDIO_EXTENSIONS = [
	'.mp3',
	'.wav',
	'.ogg',
	'.opus',
	'.aac',
	'.flac',
	'.m4a',
	'.aiff',
	'.webm'
] as const;

// Supported image MIME types and extensions
export const IMAGE_MIME_TYPES = [
	'image/jpeg',
	'image/jpg',
	'image/png',
	'image/gif',
	'image/webp',
	'image/svg+xml',
	'image/bmp',
	'image/tiff'
] as const;

export const IMAGE_EXTENSIONS = [
	'.jpg',
	'.jpeg',
	'.png',
	'.gif',
	'.webp',
	'.svg',
	'.bmp',
	'.tiff'
] as const;

export type MediaType = 'audio' | 'image' | 'video' | 'unknown';

/**
 * Check if a string is a data URL (base64 encoded)
 */
export function isDataUrl(value: string): boolean {
	return typeof value === 'string' && value.startsWith('data:');
}

/**
 * Check if a string is a base64 audio data URL
 */
export function isAudioDataUrl(value: string): boolean {
	if (!isDataUrl(value)) return false;
	const mimeMatch = value.match(/^data:(audio\/[^;,]+)/i);
	if (!mimeMatch) return false;
	const mime = mimeMatch[1].toLowerCase();
	return AUDIO_MIME_TYPES.some(m => mime.includes(m.split('/')[1]));
}

/**
 * Check if a string is a base64 image data URL
 */
export function isImageDataUrl(value: string): boolean {
	if (!isDataUrl(value)) return false;
	const mimeMatch = value.match(/^data:(image\/[^;,]+)/i);
	return !!mimeMatch;
}

/**
 * Check if a string is an audio file path or URL
 */
export function isAudioFilePath(value: string): boolean {
	if (typeof value !== 'string') return false;
	const lower = value.toLowerCase();
	return AUDIO_EXTENSIONS.some(ext => lower.endsWith(ext));
}

/**
 * Check if a string is an image file path or URL
 */
export function isImageFilePath(value: string): boolean {
	if (typeof value !== 'string') return false;
	const lower = value.toLowerCase();
	return IMAGE_EXTENSIONS.some(ext => lower.endsWith(ext));
}

/**
 * Check if an object is a HuggingFace/media audio object with src and type
 * Format: { src: "url", type: "audio/wav" } or { src: "url", type: "audio/..." }
 */
export function isAudioObject(value: unknown): boolean {
	if (typeof value !== 'object' || value === null) return false;
	const obj = value as Record<string, unknown>;

	// Check for { src: string, type: "audio/..." } format
	if (typeof obj.src === 'string' && typeof obj.type === 'string') {
		if (obj.type.startsWith('audio/')) return true;
	}

	// Check for { src: string } where src is an audio URL
	if (typeof obj.src === 'string') {
		if (isAudioFilePath(obj.src) || isAudioDataUrl(obj.src)) return true;
	}

	// Check for { url: string, type: "audio/..." } format (alternative)
	if (typeof obj.url === 'string' && typeof obj.type === 'string') {
		if (obj.type.startsWith('audio/')) return true;
	}

	return false;
}

/**
 * Check if a value represents audio data (data URL, file path, audio object, or array of audio)
 */
export function isAudio(value: unknown): boolean {
	// Check string formats
	if (typeof value === 'string') {
		return isAudioDataUrl(value) || isAudioFilePath(value);
	}
	// Check array containing audio object (common HuggingFace format: [{src, type}])
	if (Array.isArray(value) && value.length > 0) {
		return isAudioObject(value[0]);
	}
	// Check object formats (HuggingFace, etc.)
	return isAudioObject(value);
}

/**
 * Check if an object is an image object with src property
 * Format: { src: "url", height?: number, width?: number } or { src: "url", type: "image/..." }
 */
export function isImageObject(value: unknown): boolean {
	if (typeof value !== 'object' || value === null) return false;
	const obj = value as Record<string, unknown>;

	// Check for { src: string, type: "image/..." } format
	if (typeof obj.src === 'string' && typeof obj.type === 'string') {
		if (obj.type.startsWith('image/')) return true;
	}

	// Check for { src: string } where src is an image URL (common HuggingFace format)
	if (typeof obj.src === 'string') {
		// Check if URL ends with image extension or contains image indicators
		if (isImageFilePath(obj.src)) return true;
		// Check for HuggingFace image URLs that may not have extension in path
		if (obj.src.includes('/images/') || obj.src.includes('image-')) return true;
		// Check if object has height/width properties (indicates image)
		if (typeof obj.height === 'number' || typeof obj.width === 'number') return true;
	}

	// Check for { url: string, type: "image/..." } format (alternative)
	if (typeof obj.url === 'string' && typeof obj.type === 'string') {
		if (obj.type.startsWith('image/')) return true;
	}

	return false;
}

/**
 * Check if a value represents image data (data URL, file path, image object, or array)
 */
export function isImage(value: unknown): boolean {
	// Check string formats
	if (typeof value === 'string') {
		return isImageDataUrl(value) || isImageFilePath(value);
	}
	// Check array containing image object (common HuggingFace format: [{src, height, width}])
	if (Array.isArray(value) && value.length > 0) {
		return isImageObject(value[0]);
	}
	// Check object formats
	return isImageObject(value);
}

/**
 * Detect the media type of a value (string, media object, array, etc.)
 */
export function detectMediaType(value: unknown): MediaType {
	// Check audio first (handles strings, objects, and arrays)
	if (isAudio(value)) return 'audio';
	// Check image (handles strings, objects, and arrays)
	if (isImage(value)) return 'image';
	return 'unknown';
}

/**
 * Extract MIME type from a data URL
 */
export function getMimeFromDataUrl(dataUrl: string): string | null {
	if (!isDataUrl(dataUrl)) return null;
	const match = dataUrl.match(/^data:([^;,]+)/);
	return match ? match[1] : null;
}

/**
 * Get file extension from MIME type
 */
export function getExtensionFromMime(mime: string): string {
	const mimeToExt: Record<string, string> = {
		'audio/mpeg': '.mp3',
		'audio/mp3': '.mp3',
		'audio/wav': '.wav',
		'audio/wave': '.wav',
		'audio/x-wav': '.wav',
		'audio/ogg': '.ogg',
		'audio/opus': '.opus',
		'audio/aac': '.aac',
		'audio/flac': '.flac',
		'audio/x-flac': '.flac',
		'audio/m4a': '.m4a',
		'audio/x-m4a': '.m4a',
		'audio/mp4': '.m4a',
		'audio/aiff': '.aiff',
		'audio/x-aiff': '.aiff',
		'audio/webm': '.webm',
		'image/jpeg': '.jpg',
		'image/jpg': '.jpg',
		'image/png': '.png',
		'image/gif': '.gif',
		'image/webp': '.webp',
		'image/svg+xml': '.svg',
		'image/bmp': '.bmp'
	};
	return mimeToExt[mime.toLowerCase()] || '';
}

/**
 * Get a display-friendly name from a file path, URL, media object, or array
 */
export function getMediaDisplayName(value: unknown): string {
	// Handle array format: [{src, type}] or [{src, height, width}] - extract from first element
	if (Array.isArray(value) && value.length > 0) {
		return getMediaDisplayName(value[0]);
	}
	// Handle media objects (audio or image)
	if (typeof value === 'object' && value !== null) {
		const obj = value as Record<string, unknown>;
		// If it has a type field, use that (audio/wav, image/jpeg, etc.)
		if (typeof obj.type === 'string') {
			const parts = obj.type.split('/');
			return `${parts[0]} (${parts[1] || 'unknown'})`;
		}
		// For image objects with height/width, indicate it's an image
		if (typeof obj.height === 'number' && typeof obj.width === 'number') {
			return `image (${obj.width}x${obj.height})`;
		}
		// Try to extract URL and get name from it
		const url = extractMediaUrl(value);
		if (url) {
			return getMediaDisplayName(url);
		}
		return 'media';
	}

	if (typeof value !== 'string') return 'media';

	if (isDataUrl(value)) {
		const mime = getMimeFromDataUrl(value);
		if (mime) {
			const type = mime.split('/')[0];
			const subtype = mime.split('/')[1];
			return `${type} (${subtype})`;
		}
		return 'media';
	}
	// Extract filename from path
	const parts = value.split('/');
	const filename = parts[parts.length - 1];
	// Remove query params if any
	return filename.split('?')[0] || 'media';
}

/**
 * Extract media URL from various formats (string, media object, array, etc.)
 * Works for both audio and image objects with src/url properties
 */
export function extractMediaUrl(value: unknown): string | null {
	if (typeof value === 'string') {
		return value;
	}
	// Handle array format: [{src, type}] or [{src, height, width}] - extract from first element
	if (Array.isArray(value) && value.length > 0) {
		return extractMediaUrl(value[0]);
	}
	if (typeof value === 'object' && value !== null) {
		const obj = value as Record<string, unknown>;
		// Check for src property first (HuggingFace format)
		if (typeof obj.src === 'string') {
			return obj.src;
		}
		// Check for url property
		if (typeof obj.url === 'string') {
			return obj.url;
		}
	}
	return null;
}

// Aliases for backwards compatibility and clarity
export const extractAudioUrl = extractMediaUrl;
export const extractImageUrl = extractMediaUrl;

/**
 * Convert a file path or media object to an API URL for serving
 * This assumes the backend has an endpoint to serve files
 */
export function filePathToApiUrl(value: unknown, workflowId?: string): string {
	// Extract URL from media objects if needed
	const filePath = extractMediaUrl(value);
	if (!filePath) return '';

	// If already a data URL or http URL, return as-is
	if (isDataUrl(filePath) || filePath.startsWith('http://') || filePath.startsWith('https://')) {
		return filePath;
	}
	// If it's an absolute path, convert to API URL
	if (filePath.startsWith('/')) {
		const encodedPath = encodeURIComponent(filePath);
		return `/api/media/file?path=${encodedPath}${workflowId ? `&workflow_id=${workflowId}` : ''}`;
	}
	return filePath;
}

/**
 * Check if a record/object contains any audio fields
 */
export function hasAudioFields(record: Record<string, unknown>): boolean {
	for (const value of Object.values(record)) {
		if (isAudio(value)) return true;
		if (Array.isArray(value) && value.some(v => isAudio(v))) return true;
	}
	return false;
}

/**
 * Get all audio field names from a record
 */
export function getAudioFieldNames(record: Record<string, unknown>): string[] {
	const audioFields: string[] = [];
	for (const [key, value] of Object.entries(record)) {
		if (isAudio(value)) {
			audioFields.push(key);
		} else if (Array.isArray(value) && value.some(v => isAudio(v))) {
			audioFields.push(key);
		}
	}
	return audioFields;
}

/**
 * Check if a string looks like a HuggingFace audio dict (serialized)
 * These have format: {"array": [...], "sampling_rate": 16000} or {"bytes": "...", "path": "..."}
 */
export function isHuggingFaceAudioDict(value: unknown): boolean {
	if (typeof value !== 'object' || value === null) return false;
	const obj = value as Record<string, unknown>;
	// Check for array + sampling_rate format
	if ('array' in obj && 'sampling_rate' in obj) return true;
	// Check for bytes + path format
	if ('bytes' in obj && 'path' in obj) return true;
	return false;
}

/**
 * Truncate a data URL for display purposes
 */
export function truncateDataUrl(dataUrl: string, maxLength: number = 50): string {
	if (!isDataUrl(dataUrl)) return dataUrl;
	if (dataUrl.length <= maxLength) return dataUrl;
	const mime = getMimeFromDataUrl(dataUrl);
	return `data:${mime};base64,...(${Math.round(dataUrl.length / 1024)}KB)`;
}
