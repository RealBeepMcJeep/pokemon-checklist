import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const rules = JSON.parse(readFileSync(new URL('../../firebase/database.rules.json', import.meta.url), 'utf8'));
const expression = rules.rules.users.$uid.state.records.$key['.validate'];
const evaluate = new Function('$key', 'newData', `return (${expression});`);
const accepts = (key, value) => evaluate(
  { matches: pattern => pattern.test(key) },
  { child: field => { assert.equal(field, 's'); return { val: () => value }; } },
);

test('favorite rules reject the published v4 unknown-family none clears', () => {
  for (const key of ['starform:52:kanto', 'starlegacy:52']) {
    assert.equal(accepts(key, 'none'), false, `${key} must reject the v4 clear`);
  }
});

test('favorite rules only admit exact supported regional keys', () => {
  for (const key of ['starform:25:kanto', 'starform:52:alola', 'starform:052:kanto', 'starform:52:kanto:extra', 'starform:', 'starlegacy:25', 'starlegacy:052', 'starlegacy:52:extra', 'starlegacy:']) {
    for (const value of ['on', 'off']) assert.equal(accepts(key, value), false, key);
  }
});

test('favorite key admission agrees with the full regional catalogue', () => {
  const catalogue = JSON.parse(readFileSync(new URL('../../data/regional-forms.json', import.meta.url), 'utf8'));
  const forms = new Set(Object.keys(catalogue.forms));
  const ids = new Set(Object.values(catalogue.forms).map(row => row.id));
  assert.equal(forms.size, 36);
  for (let id = 1; id <= 808; id++) {
    for (const value of ['on', 'off']) {
      for (const region of ['alolan', 'kanto']) {
        const key = `${id}:${region}`;
        assert.equal(accepts(`starform:${key}`, value), forms.has(key), key);
      }
      assert.equal(accepts(`starlegacy:${id}`, value), ids.has(id), String(id));
    }
  }
});

test('favorite flags reject malformed values without changing other record families', () => {
  for (const key of ['starform:52:kanto', 'starlegacy:52']) {
    for (const value of ['none', 'caught', '', 'ON', true, false, null, 1, {}]) {
      assert.equal(accepts(key, value), false, `${key} ${JSON.stringify(value)}`);
    }
  }
  for (const [key, value] of [['species:52', 'caught'], ['form:52:kanto', 'seen'], ['star:52', 'off'], ['setting:mode', 'moon'], ['setting:forms', 'on']]) {
    assert.equal(accepts(key, value), true, key);
  }
  for (const unlock of ['tauros', 'surfing', 'fishing', 'sos', 'weather-sos']) {
    for (const value of ['on', 'off']) assert.equal(accepts(`setting:unlock:${unlock}`, value), true);
    assert.equal(accepts(`setting:unlock:${unlock}`, 'none'), false);
  }
  assert.equal(accepts('setting:unlock:unknown', 'on'), false);
});
