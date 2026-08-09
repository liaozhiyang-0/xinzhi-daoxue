from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalysisDesign = Literal[
    "experimental_comparison",
    "multigroup_comparison",
    "repeated_measures",
    "observational_regression",
    "time_series",
    "small_sample",
    "prediction",
    "unknown",
]
AnalysisStatus = Literal[
    "planning",
    "quality_blocked",
    "ready_for_execution",
    "executed",
    "needs_review",
    "insufficient_data",
    "failed",
]
DataQualityStatus = Literal[
    "not_checked",
    "passed",
    "needs_review",
    "blocked",
]
VariableRole = Literal[
    "outcome",
    "exposure",
    "treatment",
    "control",
    "time",
    "identifier",
    "group",
    "feature",
    "weight",
    "unknown",
]
EvidenceRole = Literal[
    "user_dataset",
    "data_dictionary",
    "experiment_protocol",
    "method_reference",
    "software_environment",
]
ResamplingMethod = Literal["none", "bootstrap"]
MultipleComparisonMethod = Literal["none", "holm"]


class ResearchVariable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=120)
    role: VariableRole = "unknown"
    dtype: str = Field(default="unknown", max_length=40)
    unit: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=500)
    allowed_values: list[str] = Field(default_factory=list, max_length=30)


class ResearchDataManifest(BaseModel):
    """Metadata for an authorized dataset; raw data is handled separately."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1, max_length=120)
    version: str = Field(default="", max_length=64)
    format: Literal["csv", "tsv", "json", "parquet", "xlsx", "unknown"] = "unknown"
    checksum_sha256: str = Field(default="", max_length=128)
    row_count: int | None = Field(default=None, ge=0)
    column_count: int | None = Field(default=None, ge=0)
    authorized: bool = False
    contains_sensitive_data: bool = False
    source_ref: str = Field(default="", max_length=512)


class ResearchDatasetProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(min_length=1, max_length=120)
    version: str = Field(default="", max_length=64)
    format: Literal["csv", "tsv", "json", "parquet", "xlsx", "unknown"] = "unknown"
    checksum_sha256: str = Field(default="", max_length=128)
    row_count: int | None = Field(default=None, ge=0)
    column_count: int | None = Field(default=None, ge=0)
    authorized: bool = False
    contains_sensitive_data: bool = False
    source_ref_included: Literal[False] = False


class ResearchAnalysisProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provenance_schema_version: str = Field(default="1.0", max_length=32)
    research_question: str = Field(min_length=1, max_length=2000)
    analysis_goal: Literal[
        "describe", "compare", "estimate_effect", "explain", "predict", "explore"
    ]
    design: AnalysisDesign
    estimand: str = Field(default="", max_length=500)
    unit_of_analysis: str = Field(default="", max_length=200)
    dataset: ResearchDatasetProvenance | None = None
    variables: list[ResearchVariable] = Field(default_factory=list, max_length=100)
    software_environment: str = Field(default="", max_length=1000)
    reproducibility_notes: list[str] = Field(default_factory=list, max_length=10)


class ResearchEvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1, max_length=120)
    role: EvidenceRole
    title: str = Field(default="", max_length=300)
    source_ref: str = Field(default="", max_length=512)
    cited: bool = False

    @model_validator(mode="after")
    def validate_method_reference(self) -> ResearchEvidenceReference:
        source = self.source_ref.strip()
        if self.role != "method_reference":
            return self
        if self.cited and not source:
            raise ValueError("cited method reference requires source_ref")
        if not source:
            return self
        if source.startswith(("doi:", "arxiv:", "kb:")):
            return self
        parsed = urlsplit(source)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                "method reference source_ref must be a verifiable reference"
            )
        if parsed.username or parsed.password:
            raise ValueError("method reference source_ref must not contain credentials")
        return self


class ResearchAnalysisRequest(BaseModel):
    """V2 input contract before any analysis execution is allowed."""

    model_config = ConfigDict(extra="forbid")

    research_question: str = Field(min_length=1, max_length=2000)
    hypothesis: str = Field(default="", max_length=2000)
    analysis_goal: Literal[
        "describe", "compare", "estimate_effect", "explain", "predict", "explore"
    ] = "describe"
    design: AnalysisDesign = "unknown"
    estimand: str = Field(default="", max_length=500)
    unit_of_analysis: str = Field(default="", max_length=200)
    variables: list[ResearchVariable] = Field(default_factory=list, max_length=100)
    data_manifest: ResearchDataManifest | None = None
    data_dictionary: str = Field(default="", max_length=12000)
    study_design: str = Field(default="", max_length=6000)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    software_environment: str = Field(default="", max_length=1000)
    resampling_method: ResamplingMethod = "none"
    bootstrap_replicates: int = Field(default=0, ge=0, le=10000)
    random_seed: int = Field(default=0, ge=0, le=4_294_967_295)
    multiple_comparison_method: MultipleComparisonMethod = "none"
    evidence: list[ResearchEvidenceReference] = Field(
        default_factory=list, max_length=30
    )
    exploratory: bool = True

    @model_validator(mode="after")
    def validate_data_authority(self) -> ResearchAnalysisRequest:
        if self.data_manifest is not None and not self.data_manifest.authorized:
            raise ValueError("数据集必须明确标记为 authorized 才能进入执行阶段")
        if self.analysis_goal == "estimate_effect" and not self.estimand.strip():
            raise ValueError("estimate_effect 必须明确 estimand")
        if not self.exploratory and not self.hypothesis.strip():
            raise ValueError("验证性分析必须提供 hypothesis")
        if self.resampling_method == "bootstrap" and self.bootstrap_replicates <= 0:
            raise ValueError("bootstrap 必须提供正数 bootstrap_replicates")
        if self.resampling_method == "none" and self.bootstrap_replicates:
            raise ValueError("未启用 bootstrap 时 bootstrap_replicates 必须为 0")
        return self


class ResearchDataQualityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1, max_length=80)
    status: Literal["passed", "warning", "failed", "not_run"]
    summary: str = Field(min_length=1, max_length=500)
    affected_columns: list[str] = Field(default_factory=list, max_length=30)
    blocking: bool = False


class ResearchDataQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: DataQualityStatus = "not_checked"
    checks: list[ResearchDataQualityCheck] = Field(default_factory=list, max_length=50)
    missingness_summary: str = Field(default="", max_length=2000)
    leakage_findings: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    @property
    def has_blocking_issue(self) -> bool:
        return self.status == "blocked" or any(
            check.blocking or check.status == "failed" for check in self.checks
        )


class ResearchQualityGateDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_status: Literal[
        "planning", "quality_blocked", "ready_for_execution", "insufficient_data"
    ]
    report: ResearchDataQualityReport
    reasons: list[str] = Field(default_factory=list, max_length=20)


class ResearchAnalysisPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1, max_length=120)
    version: str = Field(default="2.0.0", max_length=32)
    research_question: str = Field(min_length=1, max_length=2000)
    hypothesis: str = Field(default="", max_length=2000)
    design: AnalysisDesign
    estimand: str = Field(default="", max_length=500)
    primary_method: str = Field(min_length=1, max_length=300)
    secondary_methods: list[str] = Field(default_factory=list, max_length=10)
    exclusion_rules: list[str] = Field(default_factory=list, max_length=20)
    missing_data_strategy: str = Field(min_length=1, max_length=500)
    diagnostic_checks: list[str] = Field(min_length=1, max_length=30)
    robustness_checks: list[str] = Field(default_factory=list, max_length=20)
    resampling_method: ResamplingMethod = "none"
    bootstrap_replicates: int = Field(default=0, ge=0, le=10000)
    random_seed: int = Field(default=0, ge=0, le=4_294_967_295)
    multiple_comparison_method: MultipleComparisonMethod = "none"
    conclusion_boundaries: list[str] = Field(min_length=1, max_length=20)
    exploratory: bool = True
    frozen_at: datetime | None = None
    plan_hash: str = Field(default="", max_length=128)

    @model_validator(mode="after")
    def validate_plan(self) -> ResearchAnalysisPlan:
        if self.design == "unknown":
            raise ValueError("分析计划必须先确定研究设计")
        if self.exploratory is False and not self.hypothesis.strip():
            raise ValueError("验证性分析计划必须包含假设")
        if not self.conclusion_boundaries:
            raise ValueError("分析计划必须声明结论边界")
        return self


class ResearchAnalysisPlanningDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_status: Literal[
        "planning", "quality_blocked", "ready_for_execution", "insufficient_data"
    ]
    quality_gate: ResearchQualityGateDecision
    plan: ResearchAnalysisPlan | None = None
    method_evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    warnings: list[str] = Field(default_factory=list, max_length=20)


class ResearchExecutionArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=1, max_length=120)
    artifact_type: Literal["script", "table", "figure", "diagnostic", "report"]
    label: str = Field(min_length=1, max_length=200)
    content_ref: str = Field(default="", max_length=512)
    checksum_sha256: str = Field(default="", max_length=128)
    reproducible: bool = False


class ResearchReviewItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str = Field(min_length=1, max_length=120)
    category: Literal["data", "design", "method", "interpretation", "artifact"]
    question: str = Field(min_length=1, max_length=500)
    status: Literal["pending", "accepted", "needs_change", "not_applicable"] = (
        "pending"
    )
    note: str = Field(default="", max_length=1000)


class ResearchReviewChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ResearchReviewItem] = Field(default_factory=list, max_length=30)
    reviewer_id: str = Field(default="", max_length=120)
    signed_off: bool = False

    @property
    def ready_for_signoff(self) -> bool:
        return bool(self.items) and all(
            item.status in {"accepted", "not_applicable"} for item in self.items
        )


class ResearchReviewSubmission(BaseModel):
    """Request body for the dedicated reviewer operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str = Field(min_length=1, max_length=120)
    reviewer_role: Literal["researcher", "statistician", "pi", "admin"]
    items: list[ResearchReviewItem] = Field(min_length=1, max_length=30)
    signed_off: bool = False


class ResearchReviewDecision(BaseModel):
    """A durable, auditable reviewer decision for one analysis task."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str = Field(min_length=1, max_length=120)
    reviewer_role: Literal["researcher", "statistician", "pi", "admin"]
    checklist: ResearchReviewChecklist
    signed_at: datetime
    decision_hash: str = Field(min_length=64, max_length=128)

    @model_validator(mode="after")
    def validate_signoff(self) -> ResearchReviewDecision:
        if not self.checklist.ready_for_signoff or not self.checklist.signed_off:
            raise ValueError("签字前必须完成全部人工复核项")
        if self.checklist.reviewer_id != self.reviewer_id:
            raise ValueError("reviewer_id 与 checklist.reviewer_id 不一致")
        return self


class ResearchAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: AnalysisStatus
    design_assessment: str = Field(default="", max_length=3000)
    data_quality: ResearchDataQualityReport
    plan: ResearchAnalysisPlan | None = None
    provenance: ResearchAnalysisProvenance | None = None
    artifacts: list[ResearchExecutionArtifact] = Field(
        default_factory=list, max_length=50
    )
    explanation_source: Literal[
        "local_deterministic", "model_assisted", "model_direct"
    ] = "local_deterministic"
    model_interpretation: str = Field(default="", max_length=3000)
    plain_language_summary: str = Field(default="", max_length=6000)
    primary_result: str = Field(default="", max_length=5000)
    effect_estimates: list[str] = Field(default_factory=list, max_length=20)
    uncertainty_summary: list[str] = Field(default_factory=list, max_length=20)
    diagnostics: list[str] = Field(default_factory=list, max_length=30)
    robustness_findings: list[str] = Field(default_factory=list, max_length=30)
    interpretation: str = Field(default="", max_length=5000)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    evidence_references: list[ResearchEvidenceReference] = Field(
        default_factory=list, max_length=30
    )
    human_review_required: bool = True
    review_checklist: ResearchReviewChecklist | None = None
