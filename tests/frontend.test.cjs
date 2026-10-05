// Node 内置测试：用小型 DOM 替身验证事件流程；不代替真实浏览器视觉验收。
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../app/static/app.js'), 'utf8');
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
function element() {
  return {
    value: '', disabled: false, hidden: false, dataset: {}, listeners: {},
    classList: { add() {}, remove() {} }, focus() {},
    addEventListener(name, handler) { this.listeners[name] = handler; },
    set textContent(value) { this.text = String(value); this.html = escape(value); },
    get textContent() { return this.text || ''; },
    set innerHTML(value) { this.html = value; },
    get innerHTML() { return this.html || ''; },
  };
}
const reply = (body, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => body });
const entry = { id: 'test-id', mood: '疲惫', emoji: '🌧️', intensity: 3,
  response: '休息一下', action: '喝杯水', original_text: '<img src=x onerror=alert(1)>',
  created_at: '2026-10-05T01:00:00Z' };

async function setup(handler, initialEntries = [], confirm = () => true) {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  vm.runInNewContext(source, {
    document: { querySelector: get, createElement: element },
    fetch: async (url, options) => {
      if (url === '/api/status') return reply({ ai_configured: true });
      if (url === '/api/entries' && !options) return reply(initialEntries);
      return handler(url, options);
    },
    window: { setTimeout, clearTimeout, confirm },
    AbortController, console, TypeError,
  });
  await new Promise(setImmediate);
  return { get, click: () => get('#analyze-button').listeners.click() };
}

test('successful response renders server entry, escapes text, and resets controls', async () => {
  const ui = await setup(async (url, options) => {
    assert.equal(url, '/api/analyze');
    assert.deepEqual(JSON.parse(options.body), { text: '今天很累' });
    return reply(entry);
  });
  ui.get('#mood-input').value = '  今天很累  ';
  await ui.click();
  assert.equal(ui.get('#mood-input').value, '');
  assert.equal(ui.get('#analyze-button').disabled, false);
  assert.equal(ui.get('#result-empty').hidden, true);
  assert.match(ui.get('#history-list').innerHTML, /&lt;img/);
  assert.doesNotMatch(ui.get('#history-list').innerHTML, /<img/);
});

test('failed API leaves text available for retry and creates no visible entry', async () => {
  const ui = await setup(async () => reply({ detail: { message: 'AI 响应超时，本次未保存。' } }, false));
  ui.get('#mood-input').value = '今天很累';
  await ui.click();
  assert.equal(ui.get('#mood-input').value, '今天很累');
  assert.match(ui.get('#input-message').textContent, /本次未保存/);
  assert.equal(ui.get('#analyze-button').disabled, false);
  assert.match(ui.get('#history-list').innerHTML, /还没有记录/);
});

test('duplicate clicks while awaiting AI send only one request', async () => {
  let resolve, calls = 0;
  const ui = await setup(() => { calls++; return new Promise(done => { resolve = done; }); });
  ui.get('#mood-input').value = '今天很累';
  const first = ui.click();
  await ui.click();
  assert.equal(calls, 1);
  assert.equal(ui.get('#mood-input').disabled, true);
  resolve(reply(entry));
  await first;
  assert.equal(ui.get('#mood-input').disabled, false);
});

test('support response is displayed without adding a history entry', async () => {
  const ui = await setup(async () => reply({ status: 'support_needed', message: '请联系可信任的人。', saved: false }));
  ui.get('#mood-input').value = '安全分支演示';
  await ui.click();
  assert.equal(ui.get('#mood-card').textContent, '请联系可信任的人。');
  assert.match(ui.get('#history-list').innerHTML, /还没有记录/);
  assert.equal(ui.get('#analyze-button').disabled, false);
});

test('empty input is stopped before network call', async () => {
  let calls = 0;
  const ui = await setup(async () => { calls++; return reply(entry); });
  ui.get('#mood-input').value = '  ';
  await ui.click();
  assert.equal(calls, 0);
  assert.match(ui.get('#input-message').textContent, /请先写下/);
});

test('length uses Unicode code points and blocks over 500', async () => {
  let calls = 0;
  const ui = await setup(async () => { calls++; return reply(entry); });
  ui.get('#mood-input').value = '😀'.repeat(501);
  ui.get('#mood-input').listeners.input();
  assert.match(ui.get('#input-message').innerHTML, />501</);
  await ui.click();
  assert.equal(calls, 0);
  assert.match(ui.get('#input-message').textContent, /最多输入 500/);
  ui.get('#mood-input').value = '😀'.repeat(500);
  await ui.click();
  assert.equal(calls, 1);
});

const eventFor = (selector, id) => ({ target: { closest: value =>
  value === selector ? { dataset: { id }, disabled: false } : null } });

test('saved history can reopen its complete analysis', async () => {
  const ui = await setup(async () => { throw Error('unexpected call'); }, [entry]);
  await ui.get('#history-list').listeners.click(eventFor('.view-button', entry.id));
  assert.match(ui.get('#mood-card').innerHTML, /休息一下/);
  assert.match(ui.get('#mood-card').innerHTML, /喝杯水/);
  assert.equal(ui.get('#mood-card').hidden, false);
});

test('deleting the selected entry clears its result card', async () => {
  const entries = [entry];
  const ui = await setup(async (url, options) => {
    assert.equal(options.method, 'DELETE');
    assert.equal(url, '/api/entries/test-id');
    entries.length = 0;
    return reply(null);
  }, entries);
  await ui.get('#history-list').listeners.click(eventFor('.view-button', entry.id));
  await ui.get('#history-list').listeners.click(eventFor('.delete-button', entry.id));
  assert.equal(ui.get('#mood-card').hidden, true);
  assert.equal(ui.get('#mood-card').innerHTML, '');
  assert.match(ui.get('#history-list').innerHTML, /还没有记录/);
});

test('cancelled clear preserves records without network mutation', async () => {
  const ui = await setup(async () => { throw Error('unexpected call'); }, [entry], () => false);
  await ui.get('#clear-history').listeners.click();
  assert.match(ui.get('#history-list').innerHTML, /疲惫/);
});

test('failed deletion preserves the record and shows a retry message', async () => {
  const ui = await setup(async () => reply({}, false), [entry]);
  await ui.get('#history-list').listeners.click(eventFor('.delete-button', entry.id));
  assert.match(ui.get('#history-list').innerHTML, /疲惫/);
  assert.match(ui.get('#history-message').textContent, /删除未确认/);
});
