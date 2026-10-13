import { beforeAll, describe, it, expect, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { useNotifications } from '../src/features/plans/notifications/useNotifications'
import { NotificationError } from '../src/features/plans/notifications/client'
import type { NotificationApi } from '../src/features/plans/notifications/client'
import { actor, otherActor, version, preference, notification, page, notificationApi, deferred, id, context } from './notificationsFixtures'
beforeAll(() => Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true }))
async function ready(api = notificationApi(), profile: ReturnType<typeof version> | null = version()) {
  const invalidated = vi.fn(), expired = vi.fn(), w = useNotifications({ api }, invalidated, expired)
  w.setAccess(actor, true, 1); await w.setProfile(profile); await w.refreshContext()
  return { w, api, invalidated, expired }
}
describe('T36 independent notification state', () => {
  it('starts empty without requests and reads without a selected profile', async () => {
    const api = notificationApi(), w = useNotifications({ api })
    expect(api.context).not.toHaveBeenCalled(); expect(w.state.enabled).toBe(false)
    w.setAccess(actor, true, 1); await w.refreshContext(); await w.readPreferences(); await w.readNotifications()
    expect(w.state.profile).toBeNull(); expect(w.state.preferences?.version).toBe(0); expect(w.state.page?.items).toHaveLength(1)
  })
  it('requires explicit current profile and independent confirmation to enable, then binds exact proof', async () => {
    const { w, api } = await ready(notificationApi(), null)
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); await w.savePreferences()
    expect(api.savePreferences).not.toHaveBeenCalled()
    await w.setProfile(version()); await w.refreshContext(); await w.readPreferences(); w.setEnabled(true)
    await w.savePreferences(); expect(api.savePreferences).not.toHaveBeenCalled()
    w.setConfirmed(true); await w.savePreferences()
    expect(w.state.preferences).toEqual(preference(true)); expect(w.state.confirmed).toBe(false)
    expect(api.savePreferences).toHaveBeenCalledWith({ expected_version: 0, enabled: true, profile_id: version().profile_id, student_confirmed: true }, expect.any(AbortSignal))
  })
  it('permits explicit disabling without selected profile and does not guess new opt-in authorization', async () => {
    const api = notificationApi({ preferences: async () => preference(true) }), { w } = await ready(api, null)
    await w.readPreferences(); expect(w.state.enabled).toBe(true); w.setEnabled(false); expect(w.state.confirmed).toBe(false)
    w.setConfirmed(true); await w.savePreferences()
    expect(api.savePreferences).toHaveBeenCalledWith({ expected_version: 1, enabled: false, profile_id: null, student_confirmed: true }, expect.any(AbortSignal))
    expect(w.state.preferences).toEqual(preference(false, 2))
  })
  it('reads effective-off with retained server CAS and requires new explicit selection/confirmation', async () => {
    const { w, api } = await ready(notificationApi({ preferences: async () => preference(false, 3) }))
    await w.readPreferences(); expect(w.state.enabled).toBe(false); expect(w.state.preferences?.version).toBe(3)
    w.setEnabled(true); await w.savePreferences(); expect(api.savePreferences).not.toHaveBeenCalled()
    w.setConfirmed(true); await w.savePreferences(); expect(w.state.preferences?.version).toBe(4)
  })
  it('does not optimistically save a preference or mark a message read', async () => {
    const saving = deferred<ReturnType<typeof preference>>(), reading = deferred<ReturnType<typeof notification>>()
    const { w } = await ready(notificationApi({ savePreferences: () => saving.promise, markRead: () => reading.promise }))
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); const save = w.savePreferences()
    expect(w.state.preferences?.enabled).toBe(false); saving.resolve(preference(true)); await save
    await w.readNotifications(); const marked = w.markRead(notification().id)
    expect(w.state.page?.items[0]?.read_at).toBeNull(); reading.resolve(notification(true)); await marked
    expect(w.state.page?.items[0]?.read_at).toBe(notification(true).read_at)
  })
  it('locks a stale preference CAS without automatically repeating and unlocks only through an explicit read', async () => {
    const api = notificationApi({ savePreferences: vi.fn(async () => { throw new NotificationError(409) }) }), { w } = await ready(api)
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); await w.savePreferences()
    expect(w.state.conflict).toBe(true); expect(w.state.preferences).toBeNull(); expect(w.state.confirmed).toBe(false)
    await w.savePreferences(); expect(api.savePreferences).toHaveBeenCalledOnce()
    await w.readPreferences(); expect(w.state.conflict).toBe(false); expect(w.state.confirmed).toBe(false)
  })
  it('a mark-read conflict remains unread until explicit current server state is read', async () => {
    const api = notificationApi({ markRead: vi.fn(async () => { throw new NotificationError(409) }) }), { w } = await ready(api)
    await w.readNotifications(); await w.markRead(notification().id)
    expect(w.state.page).toBeNull(); expect(w.state.conflict).toBe(true)
    await w.markRead(notification().id); expect(api.markRead).toHaveBeenCalledOnce()
    await w.readNotifications(); expect(w.state.page?.items[0]?.version).toBe(1); expect(w.state.conflict).toBe(false)
  })
  it('rejects a valid-looking enable response bound to a different current profile version', async () => {
    const { w, invalidated } = await ready(notificationApi({ savePreferences: async () => ({ ...preference(true), profile_version_id: id(1199) }) }))
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); await w.savePreferences()
    expect(w.state.error).toBe(200); expect(w.state.preferences).toBeNull(); expect(w.state.profile).toBeNull(); expect(invalidated).toHaveBeenCalledOnce()
  })
  it('rejects immutable notification content changes even when the read CAS and shape are valid', async () => {
    const { w } = await ready(notificationApi({ markRead: async () => notification(true, { offering_version: 2 }) }))
    await w.readNotifications(); await w.markRead(notification().id)
    expect(w.state.error).toBe(200); expect(w.state.page).toBeNull()
  })
  it.each([401, 403, 404, 503, 200])('clears every private field for status %s and emits invalidation', async status => {
    const api = notificationApi({ list: async () => { throw new NotificationError(status) } }), { w, invalidated, expired } = await ready(api)
    await w.readPreferences(); w.setConfirmed(true); await w.readNotifications()
    expect(w.state.context).toBeNull(); expect(w.state.preferences).toBeNull(); expect(w.state.profile).toBeNull(); expect(w.state.confirmed).toBe(false)
    expect(invalidated).toHaveBeenCalledOnce(); expect(expired).toHaveBeenCalledTimes(status === 401 ? 1 : 0)
  })
  it('keeps configured capabilities closed without fabricated success and rejects actor-mode pollution', async () => {
    const { w, api } = await ready(notificationApi({ context: async () => context({ can_read: false, can_manage_preferences: false, can_mark_read: false }) }))
    await w.readPreferences(); await w.readNotifications(); expect(api.list).not.toHaveBeenCalled(); expect(w.state.message).toContain('尚未开放')
    const polluted = await ready(notificationApi({ context: async () => context({ is_synthetic: false }) }))
    expect(polluted.w.state.error).toBe(200); expect(polluted.w.state.context).toBeNull()
  })
  it('clears loaded preferences, reminders and confirmation when a fresh context removes read capability', async () => {
    const api = notificationApi(), { w } = await ready(api)
    await w.readPreferences(); await w.readNotifications(); w.setConfirmed(true)
    api.context = async () => context({ can_read: false, can_manage_preferences: false, can_mark_read: false })
    await w.refreshContext()
    expect(w.state.page).toBeNull(); expect(w.state.preferences).toBeNull(); expect(w.state.confirmed).toBe(false)
    expect(w.canRead()).toBe(false); expect(w.canSave()).toBe(false)
  })
  it('does not automatically repeat an uncertain preference write and clears prior inbox after a successful change', async () => {
    const api = notificationApi({ savePreferences: vi.fn(async () => { throw new NotificationError(0) }) }), { w } = await ready(api)
    await w.readPreferences(); await w.readNotifications(); w.setEnabled(true); w.setConfirmed(true); await w.savePreferences()
    expect(w.state.page).toBeNull(); expect(w.state.conflict).toBe(true); await w.savePreferences(); expect(api.savePreferences).toHaveBeenCalledOnce()
  })
  it('follows only the returned opaque cursor and rejects a self-loop', async () => {
    const api = notificationApi({ list: vi.fn(async after => page([notification()], after ?? 'NEXT')) }), { w } = await ready(api)
    await w.readNotifications(); await w.nextPage(); expect(api.list).toHaveBeenLastCalledWith('NEXT', expect.any(AbortSignal))
    expect(w.state.error).toBe(200); expect(w.state.page).toBeNull()
  })
  it.each(['actor', 'core', 'epoch', 'profile', 'dispose'])('ignores successful late reads after %s invalidation despite an API ignoring abort', async boundary => {
    const pending = deferred<ReturnType<typeof page>>(), { w } = await ready(notificationApi({ list: () => pending.promise }))
    const request = w.readNotifications()
    if (boundary === 'actor') w.setAccess(otherActor, true, 1)
    if (boundary === 'core') w.setAccess(actor, false, 1)
    if (boundary === 'epoch') w.setAccess(actor, true, 2)
    if (boundary === 'profile') await w.setProfile(null)
    if (boundary === 'dispose') w.dispose()
    pending.resolve(page()); await request
    expect(w.state.page).toBeNull(); expect(w.state.context).toBeNull(); expect(w.state.error).toBeNull(); expect(w.state.busy).toBe(false)
  })
  it.each(['actor', 'core', 'epoch'])('ignores successful late preference writes after %s invalidation', async boundary => {
    const pending = deferred<ReturnType<typeof preference>>(), { w } = await ready(notificationApi({ savePreferences: () => pending.promise }))
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); const request = w.savePreferences()
    w.setAccess(boundary === 'actor' ? otherActor : actor, boundary !== 'core', boundary === 'epoch' ? 2 : 1)
    pending.resolve(preference(true)); await request
    expect(w.state.preferences).toBeNull(); expect(w.state.confirmed).toBe(false); expect(w.state.profile).toBeNull()
  })
  it('invalidates a pending preference when its local choice is changed instead of restoring old enablement', async () => {
    const pending = deferred<ReturnType<typeof preference>>(), { w } = await ready(notificationApi({ savePreferences: () => pending.promise }))
    await w.readPreferences(); w.setEnabled(true); w.setConfirmed(true); const request = w.savePreferences()
    w.setEnabled(false); pending.resolve(preference(true)); await request
    expect(w.state.preferences?.enabled).toBe(false); expect(w.state.enabled).toBe(false); expect(w.state.confirmed).toBe(false)
  })
})
