// SPDX-License-Identifier: MIT
// Copyright (c) 2024-2026 LLMFlask contributors
const test = require('node:test');
const assert = require('node:assert/strict');

const {
    escapeHtml,
    renderInlineMarkdown,
    renderMarkdown,
    sessionStorageKeyForUser,
    clampMenuPosition,
} = require('../../components/llmflask/src/llmflask/static/chat_helpers.js');

test('escapeHtml escapes unsafe markup', () => {
    assert.equal(
        escapeHtml('<script>alert("x")</script>&'),
        '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;',
    );
});

test('renderInlineMarkdown renders code bold and safe links', () => {
    const html = renderInlineMarkdown('Use `code`, **bold**, and [site](https://example.test).');

    assert.match(html, /<code>code<\/code>/);
    assert.match(html, /<strong>bold<\/strong>/);
    assert.match(html, /<a href="https:\/\/example\.test" target="_blank" rel="noopener noreferrer">site<\/a>/);
});

test('renderMarkdown renders blocks and escapes html', () => {
    const html = renderMarkdown([
        '# Title',
        '',
        '- one',
        '- <two>',
        '> quote',
        '```',
        '<unsafe>',
        '```',
    ].join('\n'));

    assert.match(html, /<h2>Title<\/h2>/);
    assert.match(html, /<ul><li>one<\/li><li>&lt;two&gt;<\/li><\/ul>/);
    assert.match(html, /<blockquote>quote<\/blockquote>/);
    assert.match(html, /<pre><code>&lt;unsafe&gt;<\/code><\/pre>/);
});

test('sessionStorageKeyForUser scopes keys by user', () => {
    assert.equal(sessionStorageKeyForUser('alice'), 'llmflask_session:alice');
    assert.equal(sessionStorageKeyForUser('bob'), 'llmflask_session:bob');
});

test('clampMenuPosition keeps menu inside viewport', () => {
    assert.deepEqual(
        clampMenuPosition(900, 700, 200, 100, 1000, 720),
        {left: 792, top: 612},
    );
    assert.deepEqual(
        clampMenuPosition(-20, -10, 200, 100, 1000, 720),
        {left: 8, top: 8},
    );
});
