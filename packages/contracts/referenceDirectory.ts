// Independent reference identity protocol; existing generated contracts stay frozen.
export interface DirectoryIdentityProof {
  release_id: string
  offering_id: string
  offering_version: number
  identity_evidence_entry_year: number
  requirements_version: string
}
export interface DirectoryInstitution {
  id: string
  name: string
  country: string
  is_synthetic: false
  outcome_subject_ref: string
  proof: DirectoryIdentityProof
}
export interface DirectoryProgram extends DirectoryInstitution {
  institution_id: string
}
export interface DirectoryFilters {
  q: string
  country: string | null
  institution_id: string | null
}
interface DirectoryPageBase {
  schema_version: 'reference.directory.1'
  filters: DirectoryFilters
  page: { limit: number; next_cursor: string | null; has_more: boolean }
  directory_available: boolean
  missing_reason: 'directory_not_enabled' | 'no_published_matches' | null
  catalog_watermark: number | null
  expected_total: null
}
export interface InstitutionsDirectoryData extends DirectoryPageBase {
  resource: 'institutions'
  items: readonly DirectoryInstitution[]
}
export interface ProgramsDirectoryData extends DirectoryPageBase {
  resource: 'programs'
  items: readonly DirectoryProgram[]
}
export type ReferenceDirectoryData = InstitutionsDirectoryData | ProgramsDirectoryData
export interface DirectorySelection {
  institution: DirectoryInstitution | null
  program: DirectoryProgram | null
}
// Local component-event pin only; these fields are never sent to directory HTTP.
export interface DirectorySelectionEvent extends DirectorySelection {
  purpose: 'curricula' | 'outcomes'
  context_key: string
}
