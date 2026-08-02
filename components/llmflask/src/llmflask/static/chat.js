// SPDX-License-Identifier: MIT
// Copyright (c) 2024-2026 LLMFlask contributors
const {
    escapeHtml,
    renderMarkdown,
    sessionStorageKeyForUser,
    clampMenuPosition,
} = window.LLMFlaskHelpers;

const state = {
    currentSessionId: null,
    currentModel: '',
    isStreaming: false,
    abortController: null,
    currentUser: sessionStorage.getItem('llmflask_user') || 'default',
    sessions: [],
};

const messagesEl = document.getElementById('messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');
const sessionsList = document.getElementById('sessions-list');
const newChatBtn = document.getElementById('new-chat-btn');
const searchToggle = document.getElementById('search-toggle');
const toastEl = document.getElementById('toast');
const sidebarToggle = document.getElementById('sidebar-toggle');
const sidebarOverlay = document.getElementById('sidebar-overlay');
let userContextMenu = null;

function showError(msg) {
    toastEl.textContent = msg;
    toastEl.className = 'toast show';
    setTimeout(() => { toastEl.className = 'toast'; }, 4000);
}

function setSidebarOpen(open) {
    document.body.classList.toggle('sidebar-open', open);
    sidebarToggle.setAttribute('aria-expanded', String(open));
    sidebarOverlay.hidden = !open;
}

function closeSidebar() {
    setSidebarOpen(false);
}

function toggleSidebar() {
    setSidebarOpen(!document.body.classList.contains('sidebar-open'));
}

async function apiJson(url, options = {}, fallback = 'Anfrage fehlgeschlagen.') {
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        options.headers = {...(options.headers || {}), 'X-LLMFlask-Request': '1'};
    }
    const resp = await fetch(url, options);
    let data = null;
    try {
        data = await resp.json();
    } catch (e) {}
    if (!resp.ok) {
        throw new Error(data?.error || fallback);
    }
    return data;
}

function showModal({title, body, inputValue = '', danger = false, confirmText = 'OK'}) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-backdrop';
        const inputHtml = inputValue !== null
            ? `<input class="modal-input" type="text" value="${escapeHtml(inputValue)}">`
            : '';
        overlay.innerHTML = `
            <div class="modal">
                <h2>${escapeHtml(title)}</h2>
                <p>${escapeHtml(body)}</p>
                ${inputHtml}
                <div class="modal-actions">
                    <button type="button" class="modal-cancel">Abbrechen</button>
                    <button type="button" class="modal-confirm ${danger ? 'danger' : ''}">${escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;
        const close = value => {
            overlay.remove();
            resolve(value);
        };
        overlay.querySelector('.modal-cancel').addEventListener('click', () => close(null));
        overlay.querySelector('.modal-confirm').addEventListener('click', () => {
            const input = overlay.querySelector('.modal-input');
            close(input ? input.value.trim() : true);
        });
        overlay.addEventListener('click', e => {
            if (e.target === overlay) close(null);
        });
        overlay.addEventListener('keydown', e => {
            if (e.key === 'Escape') close(null);
            if (e.key === 'Enter') overlay.querySelector('.modal-confirm').click();
        });
        document.body.appendChild(overlay);
        const input = overlay.querySelector('.modal-input');
        if (input) {
            input.focus();
            input.select();
        } else {
            overlay.querySelector('.modal-confirm').focus();
        }
    });
}

function showEmptyState() {
    state.currentSessionId = null;
    sessionStorage.removeItem(sessionStorageKey());
    messagesEl.innerHTML = '<div class="loading">Noch kein Chat. Klicke auf + New Chat.</div>';
}

async function loadModels() {
    try {
        const models = await apiJson('/api/models', {}, 'Modelle konnten nicht geladen werden.');
        modelSelect.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.name;
            opt.textContent = m.label || m.name;
            modelSelect.appendChild(opt);
        });
        if (models.length && !state.currentModel) {
            state.currentModel = models[0].name;
            modelSelect.value = state.currentModel;
        }
    } catch (e) {
        showError('Ollama nicht erreichbar — Modelle konnten nicht geladen werden.');
    }
}

function getUserParam() {
    return '?user=' + encodeURIComponent(state.currentUser);
}

function sessionStorageKey() {
    return sessionStorageKeyForUser(state.currentUser);
}

async function createUser(name) {
    const data = await apiJson('/api/users', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name}),
    }, 'Benutzername ist ungueltig.');
    return data.name;
}

function hideUserContextMenu() {
    if (userContextMenu) {
        userContextMenu.hidden = true;
    }
}

function getUserContextMenu() {
    if (userContextMenu) {
        return userContextMenu;
    }
    userContextMenu = document.createElement('div');
    userContextMenu.className = 'user-context-menu';
    userContextMenu.hidden = true;
    userContextMenu.innerHTML = `
        <button type="button" data-action="rename">Umbenennen</button>
        <button type="button" data-action="delete">Löschen</button>
    `;
    userContextMenu.addEventListener('click', async (e) => {
        e.stopPropagation();
        const action = e.target.dataset.action;
        const name = userContextMenu.dataset.user;
        hideUserContextMenu();
        if (!action || !name) return;
        if (action === 'rename') {
            await renameUser(name);
        }
        if (action === 'delete') {
            await deleteUser(name);
        }
    });
    document.body.appendChild(userContextMenu);
    return userContextMenu;
}

function showUserContextMenu(e, name) {
    e.preventDefault();
    e.stopPropagation();
    const menu = getUserContextMenu();
    menu.dataset.user = name;
    const isDefault = name === 'default';
    menu.querySelector('[data-action="rename"]').disabled = isDefault;
    menu.querySelector('[data-action="delete"]').disabled = isDefault;
    menu.hidden = false;
    const rect = menu.getBoundingClientRect();
    const position = clampMenuPosition(e.clientX, e.clientY, rect.width, rect.height, window.innerWidth, window.innerHeight);
    menu.style.left = `${position.left}px`;
    menu.style.top = `${position.top}px`;
}

async function renameUser(oldName) {
    if (oldName === 'default') {
        showError('default kann nicht umbenannt werden.');
        return;
    }
    const newName = await showModal({
        title: 'Benutzer umbenennen',
        body: `Neuer Name für "${oldName}"`,
        inputValue: oldName,
        confirmText: 'Umbenennen',
    });
    if (newName === null) return;
    const trimmed = newName.trim();
    if (!trimmed || trimmed === oldName) return;

    try {
        const data = await apiJson(`/api/users/${encodeURIComponent(oldName)}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: trimmed}),
        }, 'Umbenennen fehlgeschlagen.');
        if (state.currentUser === oldName) {
            const oldSessionId = sessionStorage.getItem(sessionStorageKey());
            state.currentUser = data.name;
            document.getElementById('user-btn').textContent = state.currentUser;
            sessionStorage.setItem('llmflask_user', state.currentUser);
            if (oldSessionId) {
                sessionStorage.setItem(sessionStorageKey(), oldSessionId);
            }
        }
        await loadUsers();
        if (state.currentUser === data.name) {
            await loadSessions();
        }
    } catch (e) {
        showError(e.message || 'Umbenennen fehlgeschlagen.');
    }
}

async function deleteUser(name) {
    if (name === 'default') {
        showError('default kann nicht gelöscht werden.');
        return;
    }
    try {
        const users = await apiJson('/api/users', {}, 'Benutzer konnten nicht geladen werden.');
        const user = users.find(u => u.name === name);
        const chats = user ? user.chats : 0;
        const confirmed = await showModal({
            title: 'Benutzer löschen',
            body: `Benutzer "${name}" und ${chats} Chat(s) endgültig löschen?`,
            inputValue: null,
            danger: true,
            confirmText: 'Löschen',
        });
        if (!confirmed) return;
        await apiJson(`/api/users/${encodeURIComponent(name)}`, {method: 'DELETE'}, 'Benutzer konnte nicht gelöscht werden.');
        if (state.currentUser === name) {
            sessionStorage.removeItem(sessionStorageKey());
            await selectUser('default');
        } else {
            await loadUsers();
        }
    } catch (e) {
        showError(e.message || 'Benutzer konnte nicht gelöscht werden.');
    }
}

async function loadUsers() {
    try {
        const users = await apiJson('/api/users', {}, 'Benutzer konnten nicht geladen werden.');
        const menu = document.getElementById('user-menu');
        menu.innerHTML = '';
        users.forEach(u => {
            const div = document.createElement('div');
            div.className = 'user-item';
            div.dataset.user = u.name;
            div.innerHTML = `<span>${escapeHtml(u.name)} (${u.chats} Chats)</span><button type="button" class="user-action-btn" title="Aktionen">⋮</button>`;
            div.addEventListener('contextmenu', (e) => showUserContextMenu(e, u.name));
            div.querySelector('.user-action-btn').addEventListener('click', e => showUserContextMenu(e, u.name));
            menu.appendChild(div);
        });
        const divider = document.createElement('div');
        divider.className = 'user-divider';
        menu.appendChild(divider);
        const newBtn = document.createElement('div');
        newBtn.className = 'user-item user-new';
        newBtn.id = 'user-new-btn';
        newBtn.textContent = '+ Neuer Benutzer';
        menu.appendChild(newBtn);
    } catch (e) {}
}

async function selectUser(name) {
    if (state._selecting) return;
    state._selecting = true;
    try {
        state.currentUser = await createUser(name);
        document.getElementById('user-btn').textContent = state.currentUser;
        sessionStorage.setItem('llmflask_user', state.currentUser);
        document.getElementById('user-menu').hidden = true;
        state.currentSessionId = null;
        messagesEl.innerHTML = '';
        await loadUsers();
        const sessions = await loadSessions();
        if (sessions.length) {
            await switchSession(sessions[0].id);
        } else {
            showEmptyState();
        }
        state._selecting = false;
    } catch (e) {
        showError(e.message || 'Benutzer konnte nicht gewechselt werden.');
        state._selecting = false;
    }
}

document.getElementById('user-btn').addEventListener('click', (e) => {
    e.stopPropagation();
    loadUsers();
    document.getElementById('user-menu').hidden = !document.getElementById('user-menu').hidden;
});

document.getElementById('user-menu').addEventListener('click', (e) => {
    e.stopPropagation();
    const item = e.target.closest('.user-item');
    if (!item) return;
    if (item.id === 'user-new-btn') {
        const input = document.createElement('input');
        input.className = 'user-new-input';
        input.placeholder = 'Name...';
        input.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter') {
                ev.stopPropagation();
                const name = input.value.trim();
                if (name) { selectUser(name); return; }
                document.getElementById('user-menu').hidden = true;
            }
            if (ev.key === 'Escape') {
                document.getElementById('user-menu').hidden = true;
            }
            ev.stopPropagation();
        });
        input.addEventListener('blur', () => {
            document.getElementById('user-menu').hidden = true;
        });
        item.replaceWith(input);
        input.focus();
    } else if (item.dataset.user) {
        selectUser(item.dataset.user);
    }
});

document.addEventListener('click', (e) => {
    hideUserContextMenu();
    if (!document.getElementById('user-dropdown').contains(e.target)) {
        document.getElementById('user-menu').hidden = true;
    }
});

async function loadSessions() {
    try {
        const sessions = await apiJson('/api/sessions' + getUserParam(), {}, 'Sessions konnten nicht geladen werden.');
        state.sessions = sessions;
        sessionsList.innerHTML = '';
        sessions.forEach(s => {
            const div = document.createElement('div');
            div.className = 'session-item' + (s.id === state.currentSessionId ? ' active' : '');
            div.innerHTML = `<span class="session-title" data-sid="${s.id}">${escapeHtml(s.title)}</span>
                <button class="delete-btn" data-sid="${s.id}">&times;</button>`;
            const span = div.querySelector('.session-title');
            span.addEventListener('click', async () => {
                if (await switchSession(s.id)) {
                    closeSidebar();
                }
            });
            span.addEventListener('dblclick', () => startRename(s.id, span));
            div.querySelector('.delete-btn').addEventListener('click', (e) => {
                e.stopPropagation();
                confirmDelete(s.id);
            });
            sessionsList.appendChild(div);
        });
        return sessions;
    } catch (e) {
        showError('Sessions konnten nicht geladen werden.');
        return [];
    }
}

function startRename(sid, span) {
    const oldTitle = span.textContent;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = oldTitle;
    input.className = 'rename-input';
    span.replaceWith(input);
    input.focus();
    input.select();

    let finished = false;
    const finish = async () => {
        if (finished) return;
        finished = true;
        const newTitle = input.value.trim() || oldTitle;
        const restored = document.createElement('span');
        restored.className = 'session-title';
        restored.textContent = newTitle;
        restored.setAttribute('data-sid', sid);
        restored.addEventListener('click', () => switchSession(sid));
        restored.addEventListener('dblclick', () => startRename(sid, restored));
        input.replaceWith(restored);
        try {
            await apiJson(`/api/sessions/${sid}${getUserParam()}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title: newTitle}),
            }, 'Umbenennen fehlgeschlagen.');
        } catch (e) {
            showError('Umbenennen fehlgeschlagen.');
        }
    };

    input.addEventListener('blur', finish);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') finish();
        if (e.key === 'Escape') {
            input.value = oldTitle;
            finish();
        }
    });
}

async function confirmDelete(sid) {
    const session = state.sessions.find(s => s.id === sid);
    const confirmed = await showModal({
        title: 'Chat löschen',
        body: `Chat "${session?.title || 'Chat'}" endgültig löschen?`,
        inputValue: null,
        danger: true,
        confirmText: 'Löschen',
    });
    if (!confirmed) return;
    await deleteSession(sid);
}

async function newSession() {
    try {
        const data = await apiJson('/api/sessions' + getUserParam(), {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({model: state.currentModel}),
        }, 'Neuer Chat konnte nicht erstellt werden.');
        state.currentSessionId = data.id;
        sessionStorage.setItem(sessionStorageKey(), data.id);
        messagesEl.innerHTML = '<div class="loading">Start chatting...</div>';
        await loadSessions();
        closeSidebar();
    } catch (e) {
        showError('Neuer Chat konnte nicht erstellt werden.');
    }
}

async function deleteSession(sid) {
    try {
        await apiJson(`/api/sessions/${sid}${getUserParam()}`, {method: 'DELETE'}, 'Löschen fehlgeschlagen.');
    } catch (e) {
        showError('Löschen fehlgeschlagen.');
        return false;
    }
    if (state.currentSessionId === sid) {
        state.currentSessionId = null;
        sessionStorage.removeItem(sessionStorageKey());
    }
    const sessions = await loadSessions();
    if (state.currentSessionId === null) {
        if (sessions.length) {
            await switchSession(sessions[0].id);
        } else {
            showEmptyState();
        }
    }
    return true;
}

async function switchSession(sid) {
    state.currentSessionId = sid;
    sessionStorage.setItem(sessionStorageKey(), sid);
    const session = state.sessions.find(s => s.id === sid);
    if (session?.model && Array.from(modelSelect.options).some(opt => opt.value === session.model)) {
        state.currentModel = session.model;
        modelSelect.value = session.model;
    }
    try {
        const msgs = await apiJson(`/api/chat/${sid}/messages${getUserParam()}`, {}, 'Chat-Verlauf konnte nicht geladen werden.');
        renderMessages(msgs);
    } catch (e) {
        state.currentSessionId = null;
        sessionStorage.removeItem(sessionStorageKey());
        showError('Chat-Verlauf konnte nicht geladen werden.');
        await loadSessions();
        showEmptyState();
        return false;
    }
    await loadSessions();
    return true;
}

function renderMessages(msgs) {
    messagesEl.innerHTML = '';
    msgs.forEach(m => addMessageToDOM(m.role, m.content));
    scrollToBottom();
}

function addMessageToDOM(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    if (role === 'assistant') {
        div.innerHTML = renderMarkdown(content);
    } else {
        div.textContent = content;
    }
    messagesEl.appendChild(div);
}

function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

messagesEl.addEventListener('scroll', () => {
    const dist = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight;
    document.getElementById('scroll-btn').style.display = dist > 150 ? 'flex' : 'none';
});

async function sendMessage() {
    const text = userInput.value.trim();
    if (state.isStreaming) {
        state.abortController?.abort();
        return;
    }
    if (!text) return;
    if (!state.currentSessionId) {
        showError('Bitte zuerst einen Chat anlegen.');
        return;
    }

    const sessionId = state.currentSessionId;
    const model = state.currentModel;
    userInput.value = '';
    state.isStreaming = true;
    state.abortController = new AbortController();
    sendBtn.disabled = false;
    sendBtn.textContent = 'Stop';

    addMessageToDOM('user', text);
    scrollToBottom();

    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'message assistant typing-indicator';
    messagesEl.appendChild(assistantDiv);
    scrollToBottom();

    let fullText = '';
    try {
        const resp = await fetch('/api/chat' + getUserParam(), {
            method: 'POST',
            signal: state.abortController.signal,
            headers: {
                'Content-Type': 'application/json',
                'X-LLMFlask-Request': '1',
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: text,
                model,
                search: searchToggle.checked,
            }),
        });
        if (!resp.ok) {
            throw new Error(`Server-Fehler (${resp.status})`);
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            buf += decoder.decode(value, {stream: true});
            const lines = buf.split('\n');
            buf = lines.pop() || '';
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    if (data.error) {
                        throw new Error(data.error);
                    }
                    if (data.done) {
                        assistantDiv.classList.remove('typing-indicator');
                        assistantDiv.innerHTML = renderMarkdown(fullText);
                        state.isStreaming = false;
                        state.abortController = null;
                        sendBtn.disabled = false;
                        sendBtn.textContent = 'Send';
                        await loadSessions();
                        scrollToBottom();
                        return;
                    }
                    fullText += data.token;
                    assistantDiv.textContent = fullText;
                    assistantDiv.classList.remove('typing-indicator');
                    scrollToBottom();
                }
            }
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            assistantDiv.remove();
            showError('Streaming abgebrochen.');
        } else {
            assistantDiv.textContent = 'Fehler: ' + e.message;
            showError(e.message);
        }
    }
    state.isStreaming = false;
    state.abortController = null;
    sendBtn.disabled = false;
    sendBtn.textContent = 'Send';
    assistantDiv.classList.remove('typing-indicator');
}

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', newSession);
sidebarToggle.addEventListener('click', toggleSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeSidebar();
    }
});
modelSelect.addEventListener('change', () => {
    state.currentModel = modelSelect.value;
});

loadModels();
loadUsers();

document.getElementById('user-btn').textContent = state.currentUser;

async function initializeCurrentUser() {
    try {
        state.currentUser = await createUser(state.currentUser);
    } catch (e) {
        state.currentUser = await createUser('default');
        sessionStorage.setItem('llmflask_user', state.currentUser);
        document.getElementById('user-btn').textContent = state.currentUser;
    }
    const savedSession = sessionStorage.getItem(sessionStorageKey());
    if (savedSession && await switchSession(parseInt(savedSession))) {
        return;
    }
    const sessions = await loadSessions();
    if (sessions.length) {
        await switchSession(sessions[0].id);
    } else {
        showEmptyState();
    }
}

initializeCurrentUser().catch(e => showError(e.message || 'Initialisierung fehlgeschlagen.'));

async function exportChat(fmt) {
    if (!state.currentSessionId) return;
    const url = `/api/chat/${state.currentSessionId}/export?fmt=${fmt}&user=${encodeURIComponent(state.currentUser)}`;
    window.open(url, '_blank');
}

document.getElementById('export-md').addEventListener('click', () => exportChat('md'));
document.getElementById('export-pdf').addEventListener('click', () => exportChat('pdf'));
document.getElementById('export-ipynb').addEventListener('click', () => exportChat('ipynb'));
