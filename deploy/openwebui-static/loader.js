(function () {
	'use strict';

	const ACTION_ID = 'stage2_media_transcription_action';
	const ACTION_URL = `/api/chat/actions/${ACTION_ID}`;
	const FILE_UPLOAD_PATH = '/api/v1/files/';
	const TRANSCRIBE_LABEL = 'Транскрибировать';
	const RUNNING_LABEL = 'Транскрибирование...';
	const DONE_LABEL = 'Готово';
	const SUPPORTED_MIME = 'audio/mpeg';
	const state = {
		filesById: new Map(),
		filesByName: new Map(),
		modelId: null,
		scanQueued: false
	};

	function isMp3File(file) {
		if (!file) {
			return false;
		}
		const type = String(file.type || '').toLowerCase();
		const name = String(file.name || '').toLowerCase();
		return type === SUPPORTED_MIME || name.endsWith('.mp3');
	}

	function uploadFormData(body) {
		if (!(body instanceof FormData)) {
			return null;
		}
		for (const value of body.values()) {
			if (value instanceof File && isMp3File(value)) {
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

	function normalizeUploadedFile(uploaded, fallbackFile) {
		if (!uploaded || !uploaded.id) {
			return null;
		}
		const meta = uploaded.meta || {};
		const filename = uploaded.filename || uploaded.name || (fallbackFile && fallbackFile.name);
		const mimeType = meta.content_type || uploaded.content_type || uploaded.type || (fallbackFile && fallbackFile.type);
		if (!filename || !isSupportedMedia(filename, mimeType)) {
			return null;
		}
		return {
			id: String(uploaded.id),
			filename: String(filename),
			name: String(filename),
			mime_type: String(mimeType || SUPPORTED_MIME),
			content_type: String(mimeType || SUPPORTED_MIME),
			size: meta.size || uploaded.size || (fallbackFile && fallbackFile.size) || null
		};
	}

	function isSupportedMedia(filename, mimeType) {
		return String(mimeType || '').toLowerCase() === SUPPORTED_MIME || String(filename || '').toLowerCase().endsWith('.mp3');
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
		const originalFetch = window.fetch.bind(window);
		window.fetch = async function patchedFetch(input, init) {
			let fallbackFile = null;
			let nextInput = input;
			if (isFileUpload(input, init)) {
				fallbackFile = uploadFormData(requestBody(input, init));
				if (fallbackFile) {
					nextInput = withProcessFalse(input);
				}
			}

			const response = await originalFetch(nextInput, init);
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

		const status = document.createElement('div');
		status.dataset.stage2SttStatus = '1';
		status.textContent = '';
		status.style.minHeight = '1rem';
		status.style.fontSize = '0.7rem';
		status.style.lineHeight = '1rem';
		status.style.color = 'rgb(107, 114, 128)';

		button.addEventListener('click', (event) => {
			event.preventDefault();
			event.stopPropagation();
			runTranscription(file, button, status);
		});

		panel.append(button, status);
		const contentColumn = card.querySelector('.flex.flex-col.w-full') || card;
		contentColumn.appendChild(panel);
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
		button.textContent = RUNNING_LABEL;
		status.textContent = 'Отправка подготовленного MP3...';
		try {
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
				throw new Error(result.detail || 'Transcription action failed.');
			}
			const content = String(result.content || '').trim();
			if (!content) {
				throw new Error('Transcription action returned an empty result.');
			}
			if (!appendToComposer(content)) {
				throw new Error('Composer is unavailable for transcript insertion.');
			}
			button.textContent = DONE_LABEL;
			status.textContent = 'Текст добавлен в сообщение.';
		} catch (error) {
			button.disabled = false;
			button.textContent = TRANSCRIBE_LABEL;
			status.textContent = error && error.message ? error.message : 'Ошибка транскрибирования.';
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
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', observeUi, { once: true });
	} else {
		observeUi();
	}
})();
