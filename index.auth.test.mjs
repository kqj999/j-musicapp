import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveRequestAuth, handleSetPin, handleBootstrapAdmin, handleAuthCheck, handleProfileGet, handleProfileApiKey } from './index.js';
import { createUser, getUser, setApiKey } from './auth.js';

function mockKV() {
  const store = new Map();
  return {
    async get(key) { return store.has(key) ? store.get(key) : null; },
    async put(key, value) { store.set(key, value); },
    async list({ prefix } = {}) {
      const keys = [...store.keys()].filter(k => !prefix || k.startsWith(prefix)).map(name => ({ name }));
      return { keys };
    },
  };
}

function mockRequest({ pin, name, body } = {}) {
  const headers = new Map();
  if (pin !== undefined) headers.set('X-Pin', pin);
  if (name !== undefined) headers.set('X-Name', name);
  return {
    headers: { get: (k) => (headers.has(k) ? headers.get(k) : null) },
    json: async () => body ?? {},
  };
}

function mockEnv(overrides = {}) {
  return { APP_PIN: 'admin-secret', VIEW_PIN: 'v-pin', GUEST_PIN: 'g-pin', JADE_KV: mockKV(), ...overrides };
}

async function bodyOf(response) {
  return JSON.parse(await response.text());
}

test('resolveRequestAuth: shared PINs still work exactly as before, no name needed', async () => {
  const env = mockEnv();
  assert.deepEqual(await resolveRequestAuth(mockRequest({ pin: 'v-pin' }), env), { level: 'view' });
  assert.deepEqual(await resolveRequestAuth(mockRequest({ pin: 'g-pin' }), env), { level: 'guest' });
});

test('resolveRequestAuth: flat APP_PIN still grants admin (transitional fallback, no name)', async () => {
  const env = mockEnv();
  assert.deepEqual(await resolveRequestAuth(mockRequest({ pin: 'admin-secret' }), env), { level: 'admin' });
});

test('resolveRequestAuth: named Friend login via KV overrides nothing else and works', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const result = await resolveRequestAuth(mockRequest({ pin: '1111', name: 'Sam' }), env);
  assert.equal(result.level, 'friend');
  assert.equal(result.pinIsTemp, true);
});

test('resolveRequestAuth: wrong pin for a real username returns none, does not fall through to APP_PIN', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const result = await resolveRequestAuth(mockRequest({ pin: 'wrong', name: 'Sam' }), env);
  assert.equal(result.level, 'none');
});

test('resolveRequestAuth: no pin, no name -> none', async () => {
  const env = mockEnv();
  assert.deepEqual(await resolveRequestAuth(mockRequest({}), env), { level: 'none' });
});

test('handleAuthCheck: returns full resolveRequestAuth shape as JSON', async () => {
  const env = mockEnv();
  const res = await handleAuthCheck(mockRequest({ pin: 'g-pin' }), env);
  assert.deepEqual(await bodyOf(res), { level: 'guest' });
});

test('handleBootstrapAdmin: creates the initial admin record when appPin matches', async () => {
  const env = mockEnv();
  const res = await handleBootstrapAdmin(
    mockRequest({ body: { username: 'jade', name: 'Jade', tempPin: '9999', appPin: 'admin-secret' } }),
    env
  );
  const data = await bodyOf(res);
  assert.equal(data.ok, true);
  assert.equal(data.username, 'jade');
  const user = await getUser(env.JADE_KV, 'jade');
  assert.equal(user.tier, 'admin');
  assert.equal(user.pinIsTemp, true);
});

test('handleBootstrapAdmin: rejects wrong appPin', async () => {
  const env = mockEnv();
  const res = await handleBootstrapAdmin(
    mockRequest({ body: { username: 'jade', name: 'Jade', tempPin: '9999', appPin: 'not-the-real-one' } }),
    env
  );
  assert.equal(res.status, 403);
});

test('handleBootstrapAdmin: refuses to run twice for the same username', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'jade', name: 'Jade', tempPin: '9999', tier: 'admin' });
  const res = await handleBootstrapAdmin(
    mockRequest({ body: { username: 'jade', name: 'Jade', tempPin: '0000', appPin: 'admin-secret' } }),
    env
  );
  assert.equal(res.status, 400);
});

test('handleSetPin: forced reset succeeds with correct temp pin, then old pin stops working', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });

  const res = await handleSetPin(
    mockRequest({ body: { name: 'sam', currentPin: '1111', newPin: '4242' } }),
    env
  );
  assert.deepEqual(await bodyOf(res), { ok: true });

  const afterOldPin = await resolveRequestAuth(mockRequest({ pin: '1111', name: 'sam' }), env);
  assert.equal(afterOldPin.level, 'none');

  const afterNewPin = await resolveRequestAuth(mockRequest({ pin: '4242', name: 'sam' }), env);
  assert.equal(afterNewPin.level, 'friend');
  assert.equal(afterNewPin.pinIsTemp, false);
});

test('handleSetPin: rejects wrong currentPin without changing anything', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const res = await handleSetPin(
    mockRequest({ body: { name: 'sam', currentPin: 'wrong', newPin: '4242' } }),
    env
  );
  const data = await bodyOf(res);
  assert.equal(data.ok, false);
  const stillWorks = await resolveRequestAuth(mockRequest({ pin: '1111', name: 'sam' }), env);
  assert.equal(stillWorks.level, 'friend');
});

test('handleSetPin: rejects a newPin shorter than 4 digits', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const res = await handleSetPin(
    mockRequest({ body: { name: 'sam', currentPin: '1111', newPin: '12' } }),
    env
  );
  assert.equal(res.status, 400);
});

test('handleProfileGet: rejects when not logged in as admin/friend', async () => {
  const env = mockEnv();
  const res = await handleProfileGet(mockRequest({ pin: 'g-pin' }), env);
  assert.equal(res.status, 401);
});

test('handleProfileGet: rejects the flat APP_PIN fallback (no username to look up)', async () => {
  const env = mockEnv();
  const res = await handleProfileGet(mockRequest({ pin: 'admin-secret' }), env);
  assert.equal(res.status, 401);
});

test('handleProfileGet: returns profile summary for a named Friend login', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const res = await handleProfileGet(mockRequest({ pin: '1111', name: 'sam' }), env);
  const data = await bodyOf(res);
  assert.equal(data.name, 'Sam');
  assert.equal(data.tier, 'friend');
  assert.equal(data.hasApiKey, false);
});

test('handleProfileApiKey: sets the key with correct pin, never echoes it back', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const res = await handleProfileApiKey(
    mockRequest({ body: { name: 'sam', pin: '1111', apiKey: 'sk-ant-real-key' } }),
    env
  );
  const data = await bodyOf(res);
  assert.equal(data.ok, true);
  assert.equal(data.hasApiKey, true);
  assert.equal('apiKey' in data, false);

  const user = await getUser(env.JADE_KV, 'sam');
  assert.equal(user.apiKey, 'sk-ant-real-key');
});

test('handleProfileApiKey: rejects wrong pin', async () => {
  const env = mockEnv();
  await createUser(env.JADE_KV, { username: 'sam', name: 'Sam', tempPin: '1111', tier: 'friend' });
  const res = await handleProfileApiKey(
    mockRequest({ body: { name: 'sam', pin: 'wrong', apiKey: 'sk-ant-real-key' } }),
    env
  );
  const data = await bodyOf(res);
  assert.equal(data.ok, false);
});
