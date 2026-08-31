export type Workspace = {
  id: string;
  name: string;
  role: string;
};

export type Brand = {
  id: string;
  name: string;
};

export type Recommendation = {
  id: string;
  version: number;
  status: "candidate" | "approved" | "rejected" | "rolled_back";
  minimum_quality_score: number;
  minimum_cohort_size: number;
  confidence_score: number;
  recommendation_reason: string;
  requires_human_approval: boolean;
  activation_performed: boolean;
  created_at: string;
};

export type Activation = {
  id: string;
  recommendation_id: string;
  version: number;
  policy_version: number;
  mode: "shadow" | "enforced";
  status: string;
  minimum_quality_score: number;
  effective_at: string;
  expires_at: string | null;
};

export type Effect = {
  id: string;
  activation_id: string;
  observation_count: number;
  baseline_quality_score: string;
  observed_quality_score: string;
  quality_delta: string;
  confidence_score: number;
  state: "stable" | "watch" | "degraded";
  window_started_at: string;
  window_ended_at: string;
};

export type Degradation = {
  id: string;
  observation_id: string;
  activation_id: string;
  action: "no_change" | "investigate" | "rollback";
  status: "pending_review" | "accepted" | "dismissed";
  confidence_score: number;
  reason: string;
  requires_human_review: boolean;
  automatic_action_performed: boolean;
};

export type Remediation = {
  id: string;
  degradation_recommendation_id: string;
  source_activation_id: string;
  target_activation_id: string;
  expected_policy_version: number;
  status: string;
  observation_window_count: number;
  recovery_threshold: number;
  created_at: string;
};

export type GovernanceCase = {
  id: string;
  remediation_id: string;
  activation_id: string;
  policy_version: number;
  remediation_status_snapshot: string;
  status: string;
  evidence_manifest_sha256: string;
  evidence_item_count: number;
  governance_summary: Record<string, unknown>;
  closure_reason: string | null;
  closed_at: string | null;
  created_at: string;
};

export type GovernanceSnapshot = {
  recommendation: Recommendation[];
  active: Activation | null;
  effects: Effect[];
  degradations: Degradation[];
  remediations: Remediation[];
  cases: GovernanceCase[];
};

export type ActionKind =
  | "recommendation-decision"
  | "activation"
  | "activation-rollback"
  | "degradation-review"
  | "remediation-proposal"
  | "remediation-decision"
  | "remediation-execution"
  | "remediation-closure"
  | "case-open"
  | "case-closure";

export type PendingAction = {
  kind: ActionKind;
  title: string;
  subjectId: string;
  subjectLabel: string;
  defaults?: Record<string, string | number | boolean | null>;
};
