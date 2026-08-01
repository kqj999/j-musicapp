import test from 'node:test';
import assert from 'node:assert/strict';
import {
  normalizeUsername, generateSalt, hashPin, verifyPin,
  getUser, putUser, listUsernames, createUser, resolveAuth, setUserPin,
  getProfile, setApiKey
} from './auth.js';

// In-memory mock of Cloudflare KV, just enough surface for these tests.
function mockKV() {
  const store = new Map();
  return {
    async get(key) { return store.has(key) ? store.get(key) : null; },
    async put(key, value) { store.set(key, value); },
    async list({ prefix } = {}) {
      const keys = [...store.keys()].filter(k => !prefix || k.startsWith(prefix)).map(name => ({ name }));
      return { keys };
    },
    _store: store
  };
}

test('normalizeUsername lowercases and strips spaces', () => {
  assert.equal(normalizeUsername('  Jade Q  '), 'jadeq');
});

test('generateSalt produces unique 32-char hex strings', () => {
  const a = generateSalt(), b = generateSalt();
  assert.notEqual(a, b);
  assert.match(a, /^[0-9a-f]{32}$/);
});

test('hashPin is deterministic for same pin+salt, differs by salt or pin', async () => {
  const salt = generateSalt();
  const h1 = await hashPin('1234', salt);
  const h2 = await hashPin('1234', salt);
  const h3 = await hashPin('1234', generateSalt());
  const h4 = await hashPin('4321', salt);
  assert.equal(h1, h2);
  assert.notEqual(h1, h3);
  assert.notEqual(h1, h4);
});

test('verifyPin accepts correct pin, rejects wrong pin', async () => {
  const salt = generateSalt();
  const hash = await hashPin('9999', salt);
  assert.equal(await verifyPin('9999', salt, hash), true);
  assert.equal(await verifyPin('0000', salt, hash), false);
});

test('putUser/getUser round trip, normalizes username on both sides', async () => {
  const kv = mockKV();
  await putUser(kv, '  Jade  ', { name: 'Jade', tier: 'admin' });
  const user = await getUser(kv, 'jade');
  assert.equal(user.name, 'Jade');
  assert.equal(user.tier, 'admin');
});

test('getUser returns null for unknown user', async () => {
  const kv = mockKV();
  assert.equal(await getUser(kv, 'nobody'), null);
});

test('createUser rejects duplicate username', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await assert.rejects(
    createUser(kv, { username: 'sam', name: 'Sam Again', tempPin: '2222', tier: 'friend' }),
    /already exists/
  );
});

test('createUser sets pinIsTemp true and default record shape', async () => {
  const kv = mockKV();
  const record = await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  assert.equal(record.pinIsTemp, true);
  assert.equal(record.apiKey, null);
  assert.deepEqual(record.vibes, []);
  assert.deepEqual(record.badges, []);
});

test('listUsernames returns normalized usernames under the user: prefix', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'Sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await createUser(kv, { username: 'Jade', name: 'Jade', tempPin: '2222', tier: 'admin' });
  const names = await listUsernames(kv);
  assert.deepEqual(names.sort(), ['jade', 'sam']);
});

test('resolveAuth: guest and special_guest tiers via shared PINs, no name needed', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  assert.deepEqual(await resolveAuth(kv, env, { pin: 'g-pin' }), { level: 'guest' });
  assert.deepEqual(await resolveAuth(kv, env, { pin: 'v-pin' }), { level: 'special_guest' });
});

test('resolveAuth: no pin at all returns none', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  assert.deepEqual(await resolveAuth(kv, env, {}), { level: 'none' });
});

test('resolveAuth: named admin/friend login, correct pin', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const result = await resolveAuth(kv, env, { pin: '1111', name: 'Sam' });
  assert.equal(result.level, 'friend');
  assert.equal(result.username, 'sam');
  assert.equal(result.pinIsTemp, true);
});

test('resolveAuth: named login with wrong pin returns none (no leak of tier/user existence)', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  assert.deepEqual(await resolveAuth(kv, env, { pin: 'wrong', name: 'Sam' }), { level: 'none' });
});

test('resolveAuth: unknown username returns none', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  assert.deepEqual(await resolveAuth(kv, env, { pin: '1111', name: 'nobody' }), { level: 'none' });
});

test('resolveAuth: pinIsTemp false once real PIN has been set', async () => {
  const kv = mockKV();
  const env = { GUEST_PIN: 'g-pin', VIEW_PIN: 'v-pin' };
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await setUserPin(kv, { username: 'sam', currentPin: '1111', newPin: '4242' });
  const result = await resolveAuth(kv, env, { pin: '4242', name: 'sam' });
  assert.equal(result.pinIsTemp, false);
  // old temp pin no longer works
  assert.deepEqual(await resolveAuth(kv, env, { pin: '1111', name: 'sam' }), { level: 'none' });
});

test('setUserPin rejects wrong current pin and does not change stored hash', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await assert.rejects(
    setUserPin(kv, { username: 'sam', currentPin: 'wrong', newPin: '4242' }),
    /current PIN incorrect/
  );
  const user = await getUser(kv, 'sam');
  assert.equal(user.pinIsTemp, true);
  assert.equal(await verifyPin('1111', user.pinSalt, user.pinHash), true);
});

test('setUserPin throws for nonexistent user', async () => {
  const kv = mockKV();
  await assert.rejects(
    setUserPin(kv, { username: 'ghost', currentPin: '1111', newPin: '4242' }),
    /no such user/
  );
});

test('getProfile: returns safe summary, never the pin hash/salt or raw api key', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const profile = await getProfile(kv, 'sam');
  assert.equal(profile.name, 'Sam');
  assert.equal(profile.tier, 'friend');
  assert.equal(profile.hasApiKey, false);
  assert.deepEqual(profile.badges, []);
  assert.equal('pinHash' in profile, false);
  assert.equal('pinSalt' in profile, false);
  assert.equal('apiKey' in profile, false);
});

test('getProfile: returns null for unknown user', async () => {
  const kv = mockKV();
  assert.equal(await getProfile(kv, 'ghost'), null);
});

test('setApiKey: sets key with correct pin, getProfile reflects hasApiKey true but never exposes the raw key', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const result = await setApiKey(kv, { username: 'sam', pin: '1111', apiKey: 'sk-ant-test123' });
  assert.equal(result.hasApiKey, true);
  const profile = await getProfile(kv, 'sam');
  assert.equal(profile.hasApiKey, true);
  assert.equal('apiKey' in profile, false);
});

test('setApiKey: rejects wrong pin, does not set the key', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await assert.rejects(
    setApiKey(kv, { username: 'sam', pin: 'wrong', apiKey: 'sk-ant-test123' }),
    /PIN incorrect/
  );
  const profile = await getProfile(kv, 'sam');
  assert.equal(profile.hasApiKey, false);
});

test('setApiKey: passing null/empty clears an existing key', async () => {
  const kv = mockKV();
  await createUser(kv, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  await setApiKey(kv, { username: 'sam', pin: '1111', apiKey: 'sk-ant-test123' });
  const result = await setApiKey(kv, { username: 'sam', pin: '1111', apiKey: null });
  assert.equal(result.hasApiKey, false);
  const profile = await getProfile(kv, 'sam');
  assert.equal(profile.hasApiKey, false);
});

test('setApiKey: throws for nonexistent user', async () => {
  const kv = mockKV();
  await assert.rejects(
    setApiKey(kv, { username: 'ghost', pin: '1111', apiKey: 'sk-ant-test' }),
    /no such user/
  );
});
