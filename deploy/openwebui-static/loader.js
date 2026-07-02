(function () {
	'use strict';

	const ACTION_ID = 'stage2_media_transcription_action';
	const ACTION_URL = `/api/chat/actions/${ACTION_ID}`;
	const FILE_UPLOAD_PATH = '/api/v1/files/';
	const CONFIG_URL = '/static/stage2-stt-normalization.json';
	const TRANSCRIBE_LABEL = '\u0422\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u0431\u0438\u0440\u043e\u0432\u0430\u0442\u044c';
	const RUNNING_LABEL = '\u0422\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u0431\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u0435...';
	const DONE_LABEL = '\u0413\u043e\u0442\u043e\u0432\u043e';
	const MP3_MIME = 'audio/mpeg';
	const DEFAULT_CONFIG = Object.freeze({
		input_accept_mode: 'broad_ffmpeg_probe',
		declared_input_mime_prefixes: ['audio/', 'video/'],
		declared_input_extensions: ['mp3', 'wav', 'm4a', 'webm', 'ogg', 'mp4', 'mov', 'mkv', 'avi', 'flac', 'aac'],
		ffmpeg_probe_required: true,
		require_audio_stream: true,
		selected_output_profile: 'mp3_high_compat',
		fallback_output_profile: 'mp3_high_compat',
		available_output_profiles: ['opus_webm_compact', 'opus_ogg_compact', 'mp3_high_compat', 'wav_pcm_safe'],
		max_browser_input_mb: 1024,
		max_browser_duration_minutes: null,
		max_prepared_audio_mb: 100,
		ffmpeg_asset_mode: 'self_hosted',
		ffmpeg_package_version: '0.12.6',
		ffmpeg_core_version: '0.12.6',
		ffmpeg_core_base_url: '/static/stage2-assets/ffmpeg/0.12.6',
		ffmpeg_script_url: '/static/stage2-assets/ffmpeg/0.12.6/ffmpeg.js',
		ffmpeg_util_script_url: '/static/stage2-assets/ffmpeg/0.12.6/ffmpeg-util.js'
	});
	const PROFILE_DEFINITIONS = Object.freeze({
		opus_webm_compact: {
			mime_type: 'audio/webm;codecs=opus',
			extension: 'webm',
			args(input, output) {
				return ['-hide_banner', '-nostdin', '-y', '-i', input, '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-c:a', 'libopus', '-b:a', '24k', '-f', 'webm', output];
			}
		},
		opus_ogg_compact: {
			mime_type: 'audio/ogg;codecs=opus',
			extension: 'ogg',
			args(input, output) {
				return ['-hide_banner', '-nostdin', '-y', '-i', input, '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-c:a', 'libopus', '-b:a', '24k', '-f', 'ogg', output];
			}
		},
		mp3_high_compat: {
			mime_type: MP3_MIME,
			extension: 'mp3',
			args(input, output) {
				return ['-hide_banner', '-nostdin', '-y', '-i', input, '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-c:a', 'libmp3lame', '-b:a', '64k', '-f', 'mp3', output];
			}
		},
		wav_pcm_safe: {
			mime_type: 'audio/wav',
			extension: 'wav',
			args(input, output) {
				return ['-hide_banner', '-nostdin', '-y', '-i', input, '-vn', '-map', '0:a:0', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', '-f', 'wav', output];
			}
		}
	});
	const ERROR_MESSAGES = Object.freeze({
		ffmpeg_probe_failed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u043c\u0435\u0434\u0438\u0430\u0444\u0430\u0439\u043b.',
		ffmpeg_decode_unsupported: '\u0424\u043e\u0440\u043c\u0430\u0442 \u043d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u0442\u044c \u0432 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435.',
		ffmpeg_no_audio_stream: '\u0412 \u0444\u0430\u0439\u043b\u0435 \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d \u0430\u0443\u0434\u0438\u043e\u043f\u043e\u0442\u043e\u043a.',
		ffmpeg_browser_memory_limit: '\u0411\u0440\u0430\u0443\u0437\u0435\u0440\u0443 \u043d\u0435 \u0445\u0432\u0430\u0442\u0438\u043b\u043e \u043f\u0430\u043c\u044f\u0442\u0438 \u0434\u043b\u044f \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438.',
		ffmpeg_input_too_large: '\u0424\u0430\u0439\u043b \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u043d\u043e\u0439 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438.',
		ffmpeg_duration_limit_exceeded: '\u0414\u043b\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0444\u0430\u0439\u043b\u0430 \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442.',
		ffmpeg_normalization_failed: '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u0438\u0442\u044c \u0430\u0443\u0434\u0438\u043e \u0432 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u0435.',
		prepared_audio_too_large: '\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u043d\u043e\u0435 \u0430\u0443\u0434\u0438\u043e \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438.',
		provider_direct_upload_limit_exceeded: '\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u043d\u043e\u0435 \u0430\u0443\u0434\u0438\u043e \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442 \u043f\u0440\u044f\u043c\u043e\u0439 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438.',
		unsupported_input_format: '\u0424\u043e\u0440\u043c\u0430\u0442 \u043d\u0435 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u0430\u043d \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u043d\u043e\u0439 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u043e\u0439.',
		ffmpeg_assets_unavailable: 'FFmpeg assets are not available',
		source_file_unavailable: '\u0418\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0444\u0430\u0439\u043b \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d \u0432 \u044d\u0442\u043e\u0439 \u0441\u0435\u0441\u0441\u0438\u0438. \u041f\u0440\u0438\u043a\u0440\u0435\u043f\u0438\u0442\u0435 \u0444\u0430\u0439\u043b \u0437\u0430\u043d\u043e\u0432\u043e.',
		stt_action_failed: '\u0417\u0430\u043f\u0440\u043e\u0441 \u043a STT \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d.'
	});
	const STATUS_TEXT = Object.freeze({
		ready: '\u0413\u043e\u0442\u043e\u0432\u043e \u043a \u0442\u0440\u0430\u043d\u0441\u043a\u0440\u0438\u0431\u0430\u0446\u0438\u0438.',
		loading_ffmpeg: '\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 FFmpeg...',
		probing: '\u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u043c\u0435\u0434\u0438\u0430...',
		normalizing: '\u041d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f \u0430\u0443\u0434\u0438\u043e...',
		uploading: '\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u043d\u043e\u0433\u043e \u0430\u0443\u0434\u0438\u043e...',
		transcribing: '\u041e\u0442\u043f\u0440\u0430\u0432\u043a\u0430 \u0432 STT...',
		completed: '\u0422\u0435\u043a\u0441\u0442 \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d \u0432 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435.'
	});
	const state = {
		filesById: new Map(),
		filesByName: new Map(),
		modelId: null,
		scanQueued: false,
		config: null,
		configPromise: null,
		ffmpeg: null,
		ffmpegLoadPromise: null,
		ffmpegLogBuffer: [],
		progressStatus: null,
		originalFetch: null,
		scriptPromises: new Map()
	};

	function extensionOf(filename) {
		const text = String(filename || '').toLowerCase();
		const index = text.lastIndexOf('.');
		return index >= 0 ? text.slice(index + 1) : '';
	}

	function baseMime(mimeType) {
		return String(mimeType || '').toLowerCase().split(';')[0].trim();
	}

	function baseName(filename) {
		const text = String(filename || 'media').replace(/[\\/]/g, '_');
		const index = text.lastIndexOf('.');
		return (index > 0 ? text.slice(0, index) : text).slice(0, 80) || 'media';
	}

	function byteLimit(mb) {
		const number = Number(mb);
		return Number.isFinite(number) && number > 0 ? number * 1024 * 1024 : null;
	}

	function formatLimitMb(mb) {
		const number = Number(mb);
		if (!Number.isFinite(number) || number <= 0) {
			return '\u043d\u0435 \u0437\u0430\u0434\u0430\u043d';
		}
		if (number >= 1024 && number % 1024 === 0) {
			return `${number / 1024} GB`;
		}
		return `${number} MB`;
	}

	function limitSummary(config) {
		return `\u041b\u0438\u043c\u0438\u0442\u044b: \u0438\u0441\u0445\u043e\u0434\u043d\u044b\u0439 \u0444\u0430\u0439\u043b \u0434\u043e ${formatLimitMb(config.max_browser_input_mb)}; \u0430\u0443\u0434\u0438\u043e \u043f\u043e\u0441\u043b\u0435 \u043f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0438 \u0434\u043e ${formatLimitMb(config.max_prepared_audio_mb)}.`;
	}

	function stageError(code, fallbackMessage) {
		const error = new Error(fallbackMessage || ERROR_MESSAGES[code] || ERROR_MESSAGES.unsupported_input_format);
		error.code = code;
		return error;
	}

	function safeArray(value, fallback) {
		if (!Array.isArray(value)) {
			return fallback.slice();
		}
		return value.map((item) => String(item || '').trim()).filter(Boolean);
	}

	function safeProfile(value, fallback) {
		const profile = String(value || '').trim();
		return PROFILE_DEFINITIONS[profile] ? profile : fallback;
	}

	function normalizeConfig(raw) {
		const config = raw && typeof raw === 'object' ? raw : {};
		const merged = {
			...DEFAULT_CONFIG,
			...config,
			declared_input_mime_prefixes: safeArray(config.declared_input_mime_prefixes, DEFAULT_CONFIG.declared_input_mime_prefixes),
			declared_input_extensions: safeArray(config.declared_input_extensions, DEFAULT_CONFIG.declared_input_extensions).map((item) => item.replace(/^\./, '').toLowerCase()),
			available_output_profiles: safeArray(config.available_output_profiles, DEFAULT_CONFIG.available_output_profiles).filter((profile) => PROFILE_DEFINITIONS[profile])
		};
		merged.selected_output_profile = safeProfile(merged.selected_output_profile, DEFAULT_CONFIG.selected_output_profile);
		merged.fallback_output_profile = safeProfile(merged.fallback_output_profile, DEFAULT_CONFIG.fallback_output_profile);
		if (!merged.available_output_profiles.length) {
			merged.available_output_profiles = DEFAULT_CONFIG.available_output_profiles.slice();
		}
		merged.ffmpeg_core_base_url = String(merged.ffmpeg_core_base_url || DEFAULT_CONFIG.ffmpeg_core_base_url).replace(/\/+$/, '');
		merged.ffmpeg_script_url = String(merged.ffmpeg_script_url || `${merged.ffmpeg_core_base_url}/ffmpeg.js`);
		merged.ffmpeg_util_script_url = String(merged.ffmpeg_util_script_url || `${merged.ffmpeg_core_base_url}/ffmpeg-util.js`);
		return merged;
	}

	async function loadConfig() {
		if (state.config) {
			return state.config;
		}
		if (state.configPromise) {
			return state.configPromise;
		}
		const fetcher = state.originalFetch || window.fetch.bind(window);
		state.configPromise = fetcher(CONFIG_URL, { cache: 'no-store' })
			.then((response) => (response.ok ? response.json() : null))
			.then((payload) => {
				state.config = normalizeConfig(payload);
				return state.config;
			})
			.catch(() => {
				state.config = normalizeConfig(null);
				return state.config;
			});
		return state.configPromise;
	}

	function isCandidateMedia(filename, mimeType, config) {
		const activeConfig = config || state.config || DEFAULT_CONFIG;
		const mime = baseMime(mimeType);
		const extension = extensionOf(filename);
		const prefixMatch = activeConfig.declared_input_mime_prefixes.some((prefix) => mime.startsWith(String(prefix).toLowerCase()));
		return prefixMatch || activeConfig.declared_input_extensions.includes(extension);
	}

	function isPreparedStage2Audio(file) {
		if (!file || file.prepared !== true) {
			return false;
		}
		const profile = String(file.output_profile || '');
		const definition = PROFILE_DEFINITIONS[profile];
		if (!definition) {
			return false;
		}
		return baseMime(file.mime_type) === baseMime(definition.mime_type);
	}

	function uploadFormDataCandidate(body) {
		if (!(body instanceof FormData)) {
			return null;
		}
		for (const value of body.values()) {
			if (value instanceof File && isCandidateMedia(value.name, value.type)) {
				return value;
			}
		}
		return null;
	}

	function requestUrl(input) {
		if (typeof input === 'string') {
			return input;
		}
		if (input instanceof URL) {
			return input.toString();
		}
		if (input instanceof Request) {
			return input.url;
		}
		return '';
	}

	function requestMethod(input, init) {
		return String((init && init.method) || (input instanceof Request && input.method) || 'GET').toUpperCase();
	}

	function requestBody(input, init) {
		return (init && init.body) || (input instanceof Request && input.body) || null;
	}

	function isFileUpload(input, init) {
		const url = requestUrl(input);
		return requestMethod(input, init) === 'POST' && url.includes(FILE_UPLOAD_PATH);
	}

	function withProcessFalse(input) {
		const rawUrl = requestUrl(input);
		if (!rawUrl) {
			return input;
		}
		const url = new URL(rawUrl, window.location.origin);
		url.searchParams.set('process', 'false');
		const nextUrl = url.pathname + url.search + url.hash;
		if (input instanceof Request) {
			return new Request(nextUrl, input);
		}
		if (input instanceof URL) {
			return new URL(nextUrl, window.location.origin);
		}
		return nextUrl;
	}

	function normalizeUploadedFile(uploaded, fallbackFile, options) {
		if (!uploaded || !uploaded.id) {
			return null;
		}
		const meta = uploaded.meta || {};
		const filename = uploaded.filename || uploaded.name || (fallbackFile && fallbackFile.name);
		const mimeType = (options && options.forceMimeType) || meta.content_type || uploaded.content_type || uploaded.type || (fallbackFile && fallbackFile.type);
		if (!filename || !isCandidateMedia(filename, mimeType)) {
			return null;
		}
		return {
			id: String(uploaded.id),
			filename: String(filename),
			name: String(filename),
			mime_type: String(mimeType || 'application/octet-stream'),
			content_type: String(mimeType || 'application/octet-stream'),
			size: meta.size || uploaded.size || (fallbackFile && fallbackFile.size) || null,
			sourceFile: (options && options.sourceFile) || fallbackFile || null,
			output_profile: options && options.outputProfile ? options.outputProfile : null,
			prepared: Boolean(options && options.prepared)
		};
	}

	function rememberFile(file) {
		if (!file || !file.id) {
			return;
		}
		state.filesById.set(file.id, file);
		state.filesByName.set(file.filename, file);
		queueScan();
	}

	function patchFetch() {
		if (window.__stage2SttFetchPatched) {
			return;
		}
		window.__stage2SttFetchPatched = true;
		state.originalFetch = window.fetch.bind(window);
		window.fetch = async function patchedFetch(input, init) {
			let fallbackFile = null;
			let nextInput = input;
			if (isFileUpload(input, init)) {
				fallbackFile = uploadFormDataCandidate(requestBody(input, init));
				if (fallbackFile) {
					nextInput = withProcessFalse(input);
				}
			}

			const response = await state.originalFetch(nextInput, init);
			if (fallbackFile && response.ok) {
				response
					.clone()
					.json()
					.then((uploaded) => rememberFile(normalizeUploadedFile(uploaded, fallbackFile)))
					.catch(() => {});
			}
			return response;
		};
	}

	function queueScan() {
		if (state.scanQueued) {
			return;
		}
		state.scanQueued = true;
		window.requestAnimationFrame(() => {
			state.scanQueued = false;
			scanAttachmentCards();
		});
	}

	function findCardFile(card) {
		const text = (card.innerText || '').trim();
		for (const file of state.filesByName.values()) {
			if (text.includes(file.filename)) {
				return file;
			}
		}
		return null;
	}

	function scanAttachmentCards() {
		const root = document.querySelector('#message-input-container');
		if (!root) {
			return;
		}
		const cards = root.querySelectorAll('button');
		for (const card of cards) {
			if (card.dataset.stage2SttCard === '1' || card.dataset.stage2SttAction === '1') {
				continue;
			}
			const file = findCardFile(card);
			if (!file) {
				continue;
			}
			installCardAction(card, file);
		}
	}

	function installCardAction(card, file) {
		card.dataset.stage2SttCard = '1';
		card.style.minHeight = '4.5rem';
		card.style.alignItems = 'stretch';

		const panel = document.createElement('div');
		panel.dataset.stage2SttPanel = '1';
		panel.style.display = 'flex';
		panel.style.flexDirection = 'column';
		panel.style.gap = '0.25rem';
		panel.style.marginTop = '0.35rem';
		panel.style.width = '100%';

		const button = document.createElement('button');
		button.type = 'button';
		button.dataset.stage2SttAction = '1';
		button.title = TRANSCRIBE_LABEL;
		button.textContent = TRANSCRIBE_LABEL;
		button.style.alignSelf = 'flex-start';
		button.style.border = '1px solid rgba(14, 165, 233, 0.35)';
		button.style.borderRadius = '0.5rem';
		button.style.padding = '0.2rem 0.45rem';
		button.style.fontSize = '0.75rem';
		button.style.lineHeight = '1rem';
		button.style.background = 'rgba(14, 165, 233, 0.10)';
		button.style.color = 'inherit';
		button.style.cursor = 'pointer';
		button.addEventListener('focus', () => {
			button.style.outline = '2px solid rgba(14, 165, 233, 0.75)';
			button.style.outlineOffset = '2px';
		});
		button.addEventListener('blur', () => {
			button.style.outline = 'none';
			button.style.outlineOffset = '0';
		});

		const status = document.createElement('div');
		status.dataset.stage2SttStatus = 'ready';
		status.textContent = STATUS_TEXT.ready;
		status.style.minHeight = '1rem';
		status.style.fontSize = '0.7rem';
		status.style.lineHeight = '1rem';
		status.style.color = 'rgb(107, 114, 128)';
		status.style.whiteSpace = 'normal';

		loadConfig()
			.then((config) => {
				if (status.dataset.stage2SttStatus === 'ready') {
					setStatus(status, 'ready', `${STATUS_TEXT.ready} ${limitSummary(config)}`);
				}
			})
			.catch(() => {});

		button.addEventListener('click', (event) => {
			event.preventDefault();
			event.stopPropagation();
			runTranscription(file, button, status);
		});

		panel.append(button, status);
		const contentColumn = card.querySelector('.flex.flex-col.w-full') || card;
		contentColumn.appendChild(panel);
	}

	function setStatus(status, key, text) {
		if (!status) {
			return;
		}
		status.dataset.stage2SttStatus = key;
		status.textContent = text || STATUS_TEXT[key] || '';
	}

	function setErrorStatus(status, error) {
		const code = (error && error.code) || 'stt_action_failed';
		const message = (error && error.message) || ERROR_MESSAGES[code] || ERROR_MESSAGES.stt_action_failed;
		if (status) {
			status.dataset.stage2SttStatus = 'failed';
			status.dataset.stage2SttReason = code;
			status.textContent = `${message} [${code}]`;
		}
	}

	function loadScript(url) {
		if (state.scriptPromises.has(url)) {
			return state.scriptPromises.get(url);
		}
		const promise = new Promise((resolve, reject) => {
			const existing = Array.from(document.scripts).find((script) => script.dataset.stage2SttSrc === url);
			if (existing) {
				resolve();
				return;
			}
			const script = document.createElement('script');
			script.src = url;
			script.async = true;
			script.dataset.stage2SttSrc = url;
			script.onload = () => resolve();
			script.onerror = () => reject(stageError('ffmpeg_assets_unavailable'));
			document.head.appendChild(script);
		});
		state.scriptPromises.set(url, promise);
		return promise;
	}

	function captureLog(message) {
		state.ffmpegLogBuffer.push(String(message || ''));
		if (state.ffmpegLogBuffer.length > 250) {
			state.ffmpegLogBuffer.shift();
		}
	}

	function resetLogs() {
		state.ffmpegLogBuffer = [];
	}

	function logsText() {
		return state.ffmpegLogBuffer.join('\n');
	}

	async function loadFfmpeg(config, status) {
		if (state.ffmpeg && state.ffmpeg.loaded) {
			return state.ffmpeg;
		}
		if (state.ffmpegLoadPromise) {
			return state.ffmpegLoadPromise;
		}
		state.ffmpegLoadPromise = (async () => {
			setStatus(status, 'loading_ffmpeg');
			await loadScript(config.ffmpeg_util_script_url);
			await loadScript(config.ffmpeg_script_url);
			if (!window.FFmpegWASM || !window.FFmpegWASM.FFmpeg) {
				throw stageError('ffmpeg_assets_unavailable');
			}
			const ffmpeg = new window.FFmpegWASM.FFmpeg();
			ffmpeg.on('log', ({ message }) => captureLog(message));
			ffmpeg.on('progress', ({ progress }) => {
				if (!state.progressStatus || !Number.isFinite(progress)) {
					return;
				}
				const percent = Math.max(0, Math.min(100, Math.round(progress * 100)));
				setStatus(state.progressStatus, 'normalizing', `${STATUS_TEXT.normalizing} ${percent}%`);
			});
			let coreURL = `${config.ffmpeg_core_base_url}/ffmpeg-core.js`;
			let wasmURL = `${config.ffmpeg_core_base_url}/ffmpeg-core.wasm`;
			if (window.FFmpegUtil && typeof window.FFmpegUtil.toBlobURL === 'function') {
				coreURL = await window.FFmpegUtil.toBlobURL(coreURL, 'text/javascript');
				wasmURL = await window.FFmpegUtil.toBlobURL(wasmURL, 'application/wasm');
			}
			await ffmpeg.load({ coreURL, wasmURL });
			state.ffmpeg = ffmpeg;
			return ffmpeg;
		})().catch((error) => {
			state.ffmpegLoadPromise = null;
			if (error && error.code) {
				throw error;
			}
			throw stageError('ffmpeg_assets_unavailable');
		});
		return state.ffmpegLoadPromise;
	}

	function parseDurationSeconds(text) {
		const match = String(text || '').match(/Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)/i);
		if (!match) {
			return null;
		}
		return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
	}

	function classifyFfmpegFailure(fallbackCode) {
		const text = logsText();
		if (/matches no streams|stream map.*0:a:0|does not contain any stream/i.test(text)) {
			return stageError('ffmpeg_no_audio_stream');
		}
		if (/invalid data|could not find codec|unknown decoder|decoder .* not found|moov atom not found|error opening input|failed to read/i.test(text)) {
			return stageError('ffmpeg_decode_unsupported');
		}
		if (/out of memory|memory/i.test(text)) {
			return stageError('ffmpeg_browser_memory_limit');
		}
		return stageError(fallbackCode || 'ffmpeg_probe_failed');
	}

	async function execFfmpeg(ffmpeg, args, fallbackCode) {
		try {
			const result = await ffmpeg.exec(args);
			if (typeof result === 'number' && result !== 0) {
				throw classifyFfmpegFailure(fallbackCode);
			}
		} catch (error) {
			if (error && error.code) {
				throw error;
			}
			if (error instanceof RangeError || /memory/i.test(String(error && error.message))) {
				throw stageError('ffmpeg_browser_memory_limit');
			}
			throw classifyFfmpegFailure(fallbackCode);
		}
	}

	async function probeAudio(ffmpeg, inputName, config, status) {
		setStatus(status, 'probing');
		resetLogs();
		await execFfmpeg(ffmpeg, ['-hide_banner', '-nostdin', '-i', inputName, '-map', '0:a:0', '-t', '0.1', '-f', 'null', '-'], 'ffmpeg_probe_failed');
		const durationSeconds = parseDurationSeconds(logsText());
		const durationLimitMinutes = Number(config.max_browser_duration_minutes);
		if (durationSeconds !== null && Number.isFinite(durationLimitMinutes) && durationLimitMinutes > 0 && durationSeconds > durationLimitMinutes * 60) {
			throw stageError('ffmpeg_duration_limit_exceeded', `\u0414\u043b\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0441\u0442\u044c \u0444\u0430\u0439\u043b\u0430 \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442: \u0434\u043e ${durationLimitMinutes} \u043c\u0438\u043d.`);
		}
		return { durationSeconds };
	}

	function profileOrder(config) {
		const candidates = [
			config.selected_output_profile,
			config.fallback_output_profile,
			'mp3_high_compat',
			'wav_pcm_safe'
		];
		return candidates.filter((profile, index) => PROFILE_DEFINITIONS[profile] && candidates.indexOf(profile) === index);
	}

	async function deleteFfmpegFile(ffmpeg, filename) {
		try {
			await ffmpeg.deleteFile(filename);
		} catch (_) {}
	}

	async function prepareMediaFile(file, status) {
		const config = await loadConfig();
		const sourceFile = file.sourceFile;
		if (!(sourceFile instanceof File)) {
			throw stageError('source_file_unavailable');
		}
		const inputLimit = byteLimit(config.max_browser_input_mb);
		if (inputLimit !== null && sourceFile.size > inputLimit) {
			throw stageError('ffmpeg_input_too_large', `\u0424\u0430\u0439\u043b \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442 \u0431\u0440\u0430\u0443\u0437\u0435\u0440\u043d\u043e\u0439 \u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0438: \u0434\u043e ${formatLimitMb(config.max_browser_input_mb)}.`);
		}

		const ffmpeg = await loadFfmpeg(config, status);
		const extension = extensionOf(sourceFile.name) || 'bin';
		const inputName = `input-${Date.now()}.${extension}`;
		const preparedLimit = byteLimit(config.max_prepared_audio_mb);

		try {
			resetLogs();
			const bytes = window.FFmpegUtil && typeof window.FFmpegUtil.fetchFile === 'function'
				? await window.FFmpegUtil.fetchFile(sourceFile)
				: new Uint8Array(await sourceFile.arrayBuffer());
			await ffmpeg.writeFile(inputName, bytes);
			await probeAudio(ffmpeg, inputName, config, status);

			let lastError = null;
			for (const profile of profileOrder(config)) {
				const definition = PROFILE_DEFINITIONS[profile];
				const outputName = `output-${Date.now()}-${profile}.${definition.extension}`;
				resetLogs();
				state.progressStatus = status;
				setStatus(status, 'normalizing', `${STATUS_TEXT.normalizing} ${profile}`);
				try {
					await execFfmpeg(ffmpeg, definition.args(inputName, outputName), 'ffmpeg_normalization_failed');
					const data = await ffmpeg.readFile(outputName);
					const outputBytes = data instanceof Uint8Array ? data : new Uint8Array(data);
					if (preparedLimit !== null && outputBytes.byteLength > preparedLimit) {
						throw stageError('prepared_audio_too_large', `\u041f\u043e\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u043d\u043e\u0435 \u0430\u0443\u0434\u0438\u043e \u043f\u0440\u0435\u0432\u044b\u0448\u0430\u0435\u0442 \u043b\u0438\u043c\u0438\u0442 \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0438: \u0434\u043e ${formatLimitMb(config.max_prepared_audio_mb)}.`);
					}
					const preparedFile = new File(
						[outputBytes],
						`${baseName(sourceFile.name)}.stage2-stt.${definition.extension}`,
						{ type: definition.mime_type }
					);
					await deleteFfmpegFile(ffmpeg, outputName);
					return uploadPreparedFile(preparedFile, profile, definition, status);
				} catch (error) {
					lastError = error && error.code ? error : classifyFfmpegFailure('ffmpeg_normalization_failed');
					await deleteFfmpegFile(ffmpeg, outputName);
					if (lastError.code === 'prepared_audio_too_large') {
						throw lastError;
					}
				} finally {
					state.progressStatus = null;
				}
			}
			throw lastError || stageError('ffmpeg_normalization_failed');
		} finally {
			await deleteFfmpegFile(ffmpeg, inputName);
		}
	}

	async function uploadPreparedFile(preparedFile, profile, definition, status) {
		setStatus(status, 'uploading');
		const form = new FormData();
		form.append('file', preparedFile, preparedFile.name);
		const response = await state.originalFetch('/api/v1/files/?process=false', {
			method: 'POST',
			body: form
		});
		const uploaded = await response.json().catch(() => null);
		if (!response.ok || !uploaded) {
			throw stageError('ffmpeg_normalization_failed', 'Prepared audio upload failed.');
		}
		const normalized = normalizeUploadedFile(uploaded, preparedFile, {
			forceMimeType: definition.mime_type,
			sourceFile: preparedFile,
			outputProfile: profile,
			prepared: true
		});
		if (!normalized) {
			throw stageError('ffmpeg_normalization_failed', 'Prepared audio upload response is invalid.');
		}
		rememberFile(normalized);
		return normalized;
	}

	async function selectedModelId() {
		if (state.modelId) {
			return state.modelId;
		}
		const response = await fetch('/api/models');
		if (!response.ok) {
			throw new Error('OpenWebUI models endpoint is unavailable.');
		}
		const payload = await response.json();
		const model = payload && Array.isArray(payload.data) && payload.data[0];
		if (!model || !model.id) {
			throw new Error('OpenWebUI model is not selected.');
		}
		state.modelId = model.id;
		return state.modelId;
	}

	function currentChatId() {
		const match = window.location.pathname.match(/\/c\/([^/?#]+)/);
		return match ? match[1] : `local:stage2-stt-${Date.now()}`;
	}

	function currentSessionId() {
		try {
			for (const storage of [window.sessionStorage, window.localStorage]) {
				for (let i = 0; i < storage.length; i += 1) {
					const key = storage.key(i);
					if (key && /session/i.test(key)) {
						const value = storage.getItem(key);
						if (value && value.length < 128) {
							return value;
						}
					}
				}
			}
		} catch (_) {}
		return `stage2-stt-${Date.now()}`;
	}

	async function runTranscription(file, button, status) {
		if (button.disabled) {
			return;
		}
		button.disabled = true;
		button.style.opacity = '0.65';
		button.style.cursor = 'wait';
		button.textContent = RUNNING_LABEL;
		delete status.dataset.stage2SttReason;
		try {
			const preparedFile = isPreparedStage2Audio(file) ? file : await prepareMediaFile(file, status);
			await callTranscriptionAction(preparedFile, status);
			button.textContent = DONE_LABEL;
			button.style.cursor = 'default';
			setStatus(status, 'completed');
		} catch (error) {
			button.disabled = false;
			button.style.opacity = '1';
			button.style.cursor = 'pointer';
			button.textContent = TRANSCRIBE_LABEL;
			setErrorStatus(status, error);
		}
	}

	async function callTranscriptionAction(file, status) {
		setStatus(status, 'transcribing');
		const model = await selectedModelId();
		const payload = {
			id: `stage2-stt-${Date.now()}`,
			chat_id: currentChatId(),
			session_id: currentSessionId(),
			model,
			messages: [],
			files: [
				{
					type: 'file',
					file: {
						id: file.id,
						filename: file.filename,
						name: file.filename,
						mime_type: file.mime_type,
						content_type: file.content_type,
						size: file.size
					}
				}
			]
		};
		const response = await fetch(ACTION_URL, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(payload)
		});
		const result = await response.json().catch(() => ({}));
		if (!response.ok) {
			throw stageError('stt_action_failed', result.detail || 'Transcription action failed.');
		}
		const content = String(result.content || '').trim();
		if (!content) {
			throw stageError('stt_action_failed', 'Transcription action returned an empty result.');
		}
		if (/^(STT sidecar request failed|STT transcription is not configured|Unable to access|No supported prepared audio)/i.test(content)) {
			throw stageError('stt_action_failed', content);
		}
		if (!appendToComposer(content)) {
			throw stageError('stt_action_failed', 'Composer is unavailable for transcript insertion.');
		}
	}

	function appendToComposer(text) {
		const composer = document.querySelector('#message-input-container [contenteditable="true"], [contenteditable="true"]');
		if (!composer) {
			return false;
		}
		const currentText = (composer.innerText || '').trim();
		const insertion = `${currentText ? '\n\n' : ''}${text}`;
		composer.focus();
		const selection = window.getSelection();
		if (selection) {
			const range = document.createRange();
			range.selectNodeContents(composer);
			range.collapse(false);
			selection.removeAllRanges();
			selection.addRange(range);
		}
		let inserted = false;
		try {
			inserted = document.execCommand('insertText', false, insertion);
		} catch (_) {
			inserted = false;
		}
		if (!inserted) {
			composer.textContent = `${composer.textContent || ''}${insertion}`;
		}
		composer.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: insertion }));
		return true;
	}

	function observeUi() {
		const observer = new MutationObserver(queueScan);
		observer.observe(document.documentElement, { childList: true, subtree: true });
		queueScan();
	}

	patchFetch();
	loadConfig().then(queueScan).catch(() => queueScan());
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', observeUi, { once: true });
	} else {
		observeUi();
	}
})();
