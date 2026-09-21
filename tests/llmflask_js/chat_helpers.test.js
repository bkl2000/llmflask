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
    renderModelOptions,
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

test('model selector renders Local, Free, and API groups without a fake option', () => {
    const document = {createElement: tag => ({tag, children: [], appendChild(child) { this.children.push(child); }})};
    const select = {
        children: [],
        set innerHTML(value) { this.children = []; },
        appendChild(child) { this.children.push(child); },
    };
    renderModelOptions(select, {
        groups: [{id: 'local', label: 'Local'}, {id: 'free', label: 'Free'}, {id: 'api', label: 'API'}],
        free_hint: 'Configure Zen',
        default_model: 'ollama/qwen3:14b',
        models: [
            {name: 'ollama/qwen3:14b', label: 'Ollama: qwen3:14b', group: 'local'},
            {name: 'zen/example-free', label: 'OpenCode Zen: example-free', group: 'free'},
            {name: 'deepseek/deepseek-chat', label: 'DeepSeek: deepseek-chat', group: 'api'},
        ],
    }, document);
    assert.deepEqual(select.children.map(group => group.label), ['Local', 'Free', 'API']);
    assert.deepEqual(select.children.map(group => group.children[0].value), [
        'ollama/qwen3:14b', 'zen/example-free', 'deepseek/deepseek-chat',
    ]);

    renderModelOptions(select, {
        groups: [{id: 'local', label: 'Local'}, {id: 'free', label: 'Free'}, {id: 'api', label: 'API'}],
        free_hint: 'Configure Zen',
        default_model: 'ollama/qwen3:14b',
        models: [{name: 'ollama/qwen3:14b', group: 'local'}],
    }, document);
    assert.deepEqual(select.children.map(group => group.label), ['Local']);
    assert.deepEqual(select.children[0].children.map(option => option.value), ['ollama/qwen3:14b']);

    renderModelOptions(select, {
        groups: [{id: 'local', label: 'Local'}, {id: 'free', label: 'Free'}, {id: 'api', label: 'API'}],
        default_model: '',
        models: [{name: 'deepseek/deepseek-chat', group: 'api'}],
    }, document);
    assert.equal(select.children[0].value, '');
    assert.equal(select.children[0].disabled, true);
    assert.equal(select.children[1].label, 'API');
});
