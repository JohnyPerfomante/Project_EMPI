export type Role = 'student' | 'teacher' | 'admin'
export type QuestionStatus = 'draft' | 'published' | 'archived'
export type VariationStatus = 'proposed' | 'approved' | 'rejected' | 'archived'
export type SubmissionStatus = 'queued' | 'processing' | 'analyzed' | 'failed'
export type Category = 'HIGH_MATCH' | 'NEEDS_REVIEW' | 'LOW_MATCH'
export type Decision = 'approved' | 'partial' | 'rejected'
export type Difficulty = 'easy' | 'medium' | 'hard'
export type Visibility = 'automatic' | 'reviewed' | 'hidden'

export interface RecordBase { id: number; created_at: string }
export interface Page<T> { items: T[]; total: number; offset: number; limit: number }
export interface User extends RecordBase {
  full_name: string
  email: string
  role: Role
  active: boolean
  demo: boolean
  last_login_at: string | null
}
export interface Specialty extends RecordBase { code: string; name: string }
export interface Subject extends RecordBase { name: string; specialty_id: number; description: string }
export interface Group extends RecordBase { name: string; specialty_id: number; academic_year: string }
export interface Course extends RecordBase {
  name: string
  subject_id: number
  subject_name: string
  specialty: string
  academic_year: string
  description: string
  active: boolean
  demo: boolean
  result_visibility: Visibility
  analysis_overrides: { high_threshold?: number; low_threshold?: number }
}
export interface Membership extends RecordBase {
  student_id: number; group_id: number; full_name: string; group_name: string; active: boolean
}
export interface TeacherAccess extends RecordBase { teacher_id: number; full_name: string; active: boolean }

export interface Concept { concept: string; synonyms: string[]; importance_weight: number; is_required: boolean }
export interface ConflictRule { phrase: string; kind: 'contradiction' | 'terminology'; message: string }
export interface ReferenceFields { text: string; concepts: Concept[]; conflict_rules: ConflictRule[] }
export interface Reference extends RecordBase, ReferenceFields { question_id: number; updated_at: string }
export interface Question extends RecordBase {
  text: string
  course_id: number
  course_name: string
  subject_name: string
  difficulty: Difficulty
  status: QuestionStatus
  author?: string
  reference_count?: number
  variation_count?: number
  demo: boolean
  max_answer_length: number
  updated_at: string
}
export interface Variation extends RecordBase {
  text: string
  reference_answer_id: number
  status: VariationStatus
  question_id: number
  question_text: string
  reference_text: string
  course_name: string
  author: string
  reviewer: string | null
  approved_at: string | null
  rejected_at: string | null
  archived_at: string | null
  demo: boolean
}
export interface Submission extends RecordBase {
  question_id: number; question_text: string; course_id: number; course_name: string
  student_name: string | null; group_name: string | null; answer_text: string
  status: SubmissionStatus; category: Category | null; decision: Decision | null
}
export interface StudentAnalysis { final_similarity: number; category: Category; explanation: string }
export interface Analysis extends RecordBase, StudentAnalysis {
  semantic_similarity: number; lexical_similarity: number; concept_coverage: number | null
  reference_answer_id: number; variation_id: number | null; warnings: { code: string; message: string; critical: boolean }[]
  matches: string[]; missing: string[]; processing_ms: number; model_name: string; model_version: string
  configuration_snapshot: Record<string, unknown>
  material_snapshot: { reference_text: string; variation_text: string | null; concepts: Concept[]; conflict_rules: ConflictRule[] }
}
export interface Review extends RecordBase {
  analysis_result_id: number; decision: Decision; comment: string; reviewer: string | null; variation_id: number | null
}
export interface Result {
  status: SubmissionStatus; visibility: Visibility | 'staff'; review_status: 'pending' | 'reviewed'
  analysis: Analysis | StudentAnalysis | null; review: Review | null
}
export interface Summary {
  counts: { courses: number; subjects: number; questions: number; submissions: number; pending_reviews: number;
    reviewed: number; proposed_variations: number }
  categories: { category: Category; count: number }[]
  activity: { date: string; count: number }[]
  courses: { course_id: number; name: string; submissions: number; reviewed: number }[]
  students: { student_id: number; name: string; submissions: number }[]
}
export interface Configuration {
  high_threshold: number; low_threshold: number; semantic_weight: number; lexical_weight: number
  concept_weight: number; min_answer_length: number; max_answer_length: number; detect_negation: boolean
  calibrated: boolean; model_name: string; model_revision: string; provider: string
}
export interface Audit extends RecordBase {
  user_id: number | null; action: string; entity_type: string; entity_id: number | null; details: Record<string, unknown>
}
