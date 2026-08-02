// SPDX-License-Identifier: MIT
// Copyright (c) 2024-2026 LLMFlask contributors
(function (root) {
    function escapeHtml(text) {
        return String(text).replace(/[&<>"']/g, ch => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
        })[ch]);
    }

    function renderInlineMarkdown(text) {
        let escaped = escapeHtml(text);
        escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
        escaped = escaped.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
        return escaped;
    }

    function renderMarkdown(text) {
        const lines = String(text).split('\n');
        const html = [];
        let inCode = false;
        let codeLines = [];
        let inList = false;

        const closeList = () => {
            if (inList) {
                html.push('</ul>');
                inList = false;
            }
        };
        const closeCode = () => {
            if (inCode) {
                html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
                codeLines = [];
                inCode = false;
            }
        };

        for (const line of lines) {
            if (line.trim().startsWith('```')) {
                if (inCode) {
                    closeCode();
                } else {
                    closeList();
                    inCode = true;
                    codeLines = [];
                }
                continue;
            }
            if (inCode) {
                codeLines.push(line);
                continue;
            }
            const trimmed = line.trim();
            if (!trimmed) {
                closeList();
                html.push('<br>');
            } else if (trimmed.startsWith('### ')) {
                closeList();
                html.push(`<h3>${renderInlineMarkdown(trimmed.slice(4))}</h3>`);
            } else if (trimmed.startsWith('## ')) {
                closeList();
                html.push(`<h2>${renderInlineMarkdown(trimmed.slice(3))}</h2>`);
            } else if (trimmed.startsWith('# ')) {
                closeList();
                html.push(`<h2>${renderInlineMarkdown(trimmed.slice(2))}</h2>`);
            } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                if (!inList) {
                    html.push('<ul>');
                    inList = true;
                }
                html.push(`<li>${renderInlineMarkdown(trimmed.slice(2))}</li>`);
            } else if (trimmed.startsWith('> ')) {
                closeList();
                html.push(`<blockquote>${renderInlineMarkdown(trimmed.slice(2))}</blockquote>`);
            } else {
                closeList();
                html.push(`<p>${renderInlineMarkdown(line)}</p>`);
            }
        }
        closeCode();
        closeList();
        return html.join('');
    }

    function sessionStorageKeyForUser(user) {
        return `llmflask_session:${user}`;
    }

    function clampMenuPosition(clientX, clientY, menuWidth, menuHeight, viewportWidth, viewportHeight, margin = 8) {
        const left = Math.min(clientX, viewportWidth - menuWidth - margin);
        const top = Math.min(clientY, viewportHeight - menuHeight - margin);
        return {
            left: Math.max(margin, left),
            top: Math.max(margin, top),
        };
    }

    const helpers = {
        escapeHtml,
        renderInlineMarkdown,
        renderMarkdown,
        sessionStorageKeyForUser,
        clampMenuPosition,
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = helpers;
    }
    root.LLMFlaskHelpers = helpers;
})(typeof window !== 'undefined' ? window : globalThis);
