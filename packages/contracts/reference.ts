// Separate hand-maintained minimal contract; existing generated profiles stay frozen.
export interface EmptyReferenceData {
  schema_version: 'reference.minimal.1'
  resource: string
  filters: Record<string, string | number | null>
  items: readonly []
  page: { limit: number; next_cursor: null; has_more: false }
  release_id: null
  expected_total: null
  coverage_ratio: null
  missing_reason: 'source_not_enabled' | 'not_applicable' | 'scope_incomplete'
  business_available: false
}

// Explicit local-only reference protocol; not a T19 public release contract.
export type LocalCutoffLineKind = 'segment_first' | 'segment_second' | 'special_category'
export type LocalCutoffMissingReason = 'not_collected' | 'not_applicable' | 'scope_not_supported' | 'withdrawn' | 'review_pending'
export interface LocalCutoffSource {
  publisher: '浙江省教育考试院'
  url: 'https://www.zjzs.net/art/2026/6/25/art_155_12467.html'
  title: '2026年浙江省普通高校招生各类别分数线'
  published_label: string
  published_timezone: null
  retrieved_at: string
  original_sha256: string
  body_bytes: number
  authority_status: 'official_site_checked'
  public_reuse_permission: 'unknown'
}
export interface LocalCutoffBatch {
  batch_id: string
  manifest_sha256: string
  state: 'approved_local'
  review_ref: string
  approved_at: string
}
export interface LocalCutoffRecord {
  record_key: string
  exam_year: 2026
  region_key: 'cn_region_11'
  subject_category: '普通类'
  line_kind: LocalCutoffLineKind
  original_label: string
  value: number
  unit: 'points'
  is_synthetic: false
  max_score: null
  bonus_definition: null
  max_score_missing_reason: 'not_stated_in_source'
  bonus_missing_reason: 'not_stated_in_source'
  excerpt: string
  locator: string
}
export interface LocalCutoffData {
  schema_version: 'reference.cutoffs.local.1'
  resource: 'province_cutoffs'
  filters: Record<string, string | number | null>
  items: readonly LocalCutoffRecord[]
  page: { limit: number; next_cursor: null; has_more: false }
  release_id: null
  expected_total: null
  coverage_ratio: null
  business_available: false
  local_reference_only: true
  reference_available: boolean
  missing_reason: LocalCutoffMissingReason | null
  source: LocalCutoffSource | null
  batch: LocalCutoffBatch | null
}
export type ReferenceData = EmptyReferenceData | LocalCutoffData
