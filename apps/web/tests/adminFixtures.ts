import { createHash } from 'node:crypto'
import { vi } from 'vitest'
import type { AdminApi, AdminContextData, AdminSourceData, FileData, ImportResult, SourceDefinition } from '../src/features/admin/client'
export { actor, otherActor, deferred } from './privacyFixtures'
export const datasetId = '588e905d-8a66-41eb-8b6e-985d297252d1'
export const sourceId = '7665e851-b1e2-4c19-a4dd-e647b93146a7'
export const fileId = 'ba0cddcc-2ad5-4e38-8d80-1e401716db28'
export const importId = 'ed0c1a6e-3e12-4c10-bcc2-c3ec6859d322'
export const content = '[{"DEMO_value":"600.00"}]\r\n'
export const sha256 = (value: string) => createHash('sha256').update(value, 'utf8').digest('hex')
export function context(overrides: Partial<AdminContextData> = {}): AdminContextData {
  return { schema_version: 'v2.t21', can_manage_sources: true, can_import: true, is_synthetic: true, ...overrides }
}
export function definition(overrides: Partial<SourceDefinition> = {}): SourceDefinition {
  return { publisher: 'DEMO_合成发布者', entry_url: 'https://source-sentinel.invalid/reference', purpose: 'admissions_reference',
    data_type: 'entry_requirements', scope_note: 'DEMO 本科要求', authority_claim: 'unclassified',
    manual_import_permission: 'granted', publication_permission: 'pending', automated_fetch_permission: 'pending',
    license_basis: 'DEMO_仅合成测试授权', permission_record_reference: 'DEMO_permission', recheck_days: 30, manual_import_enabled: true, ...overrides }
}
export function source(overrides: Partial<AdminSourceData> = {}): AdminSourceData {
  return { ...definition(), id: '4b3bac4c-9b59-43f7-abcd-56bc4e7f70c6', dataset_id: datasetId, source_id: sourceId, version: 1,
    dataset_revision: 2, is_synthetic: true, created_at: '2026-10-03T00:00:00Z', permission_reviewed_at: '2026-10-03T00:00:00Z',
    recheck_due_at: '2026-11-02T00:00:00Z', auto_fetch_enabled: false, ...overrides }
}
export function file(overrides: Partial<FileData> = {}): FileData {
  return { id: fileId, namespace: 'source_quarantine', is_synthetic: true, status: 'quarantined', media_type: 'application/json',
    size_bytes: Buffer.byteLength(content), sha256: sha256(content), created_at: '2026-10-03T00:00:00Z', expires_at: '2026-10-04T00:00:00Z', ...overrides }
}
export function result(overrides: Partial<ImportResult> = {}): ImportResult {
  return { id: importId, status: 'staged', total_rows: 3, staged_rows: 3, error_count: 0, errors: [], replayed: false, ...overrides }
}
export function rejected(): ImportResult {
  return result({ status: 'rejected', total_rows: null, staged_rows: 0, error_count: 1, errors: [{ row_number: 0, field: 'document', code: 'INVALID_STRUCTURE' }] })
}
export function adminApi(overrides: Partial<AdminApi> = {}) {
  return { context: vi.fn(async () => context()), register: vi.fn(async input => source({ ...input.source.definition, source_id: input.source.id,
    dataset_id: input.source.dataset_id, dataset_revision: input.expected_dataset_revision + 1 })), source: vi.fn(async () => source()),
    revise: vi.fn(async (_id, input) => source({ ...input.definition, version: input.expected_source_version + 1, dataset_revision: input.expected_dataset_revision + 1 })),
    upload: vi.fn(async input => file({ sha256: sha256(input.content_utf8), size_bytes: Buffer.byteLength(input.content_utf8), media_type: input.content_type })),
    import: vi.fn(async () => result()), result: vi.fn(async () => result()), ...overrides } satisfies AdminApi
}
