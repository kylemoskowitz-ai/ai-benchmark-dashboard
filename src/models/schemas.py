"""Pydantic schemas for benchmark data with full provenance tracking."""

from datetime import date, datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib
import json


class TrustTier(str, Enum):
    """Trust tier for data provenance.

    A = Official/Primary (benchmark authors, official leaderboards)
    B = Semi-Official (model provider results, Epoch AI)
    C = Third-Party (community runs, blog posts)
    """

    A = "A"
    B = "B"
    C = "C"


class SourceType(str, Enum):
    """Type of data source."""

    OFFICIAL_PAPER = "official_paper"
    OFFICIAL_LEADERBOARD = "official_leaderboard"
    OFFICIAL_BLOG = "official_blog"
    THIRD_PARTY_EVAL = "third_party_eval"
    THIRD_PARTY_LEADERBOARD = "third_party_leaderboard"
    MANUAL_ENTRY = "manual_entry"


class ParseMethod(str, Enum):
    """Method used to parse/extract data."""

    API = "api"
    CSV_DOWNLOAD = "csv_download"
    HTML_SCRAPE = "html_scrape"
    PDF_EXTRACT = "pdf_extract"
    MANUAL = "manual"


class ModelStatus(str, Enum):
    """Verification status of a model."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class Source(BaseModel):
    """Provenance record for data sources.

    Every Result must link to a Source to ensure full traceability.
    """

    source_id: str = Field(..., description="Unique source identifier (UUID or hash)")
    source_type: SourceType = Field(..., description="Type of data source")
    source_title: str = Field(..., description="Human-readable source title")
    source_url: str = Field(..., description="Full URL to source")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    parse_method: ParseMethod = Field(..., description="Method used to extract data")
    raw_snapshot_path: str | None = Field(
        default=None, description="Path to raw data snapshot file"
    )
    notes: str | None = Field(default=None, description="Additional notes about the source")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def generate_id(cls, url: str, retrieved_at: datetime) -> str:
        """Generate deterministic source ID from URL and timestamp."""
        content = f"{url}:{retrieved_at.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class Benchmark(BaseModel):
    """Benchmark definition with metadata."""

    benchmark_id: str = Field(..., description="Canonical benchmark ID (e.g., 'swe_bench_verified')")
    name: str = Field(..., description="Display name (e.g., 'SWE-Bench Verified')")
    category: str = Field(..., description="Category: coding, reasoning, agentic, math, etc.")
    description: str = Field(default="", description="Description of what the benchmark measures")
    unit: str = Field(default="percent", description="Unit of measurement: percent, score, etc.")
    scale_min: float = Field(default=0.0, description="Minimum possible score")
    scale_max: float = Field(default=100.0, description="Maximum possible score")
    higher_is_better: bool = Field(default=True, description="Whether higher scores are better")
    official_url: str | None = Field(default=None, description="Official benchmark URL")
    paper_url: str | None = Field(default=None, description="Associated paper URL")
    notes: str | None = Field(default=None, description="Notes about harness versions, known issues")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Model(BaseModel):
    """AI model with metadata."""

    model_id: str = Field(
        ..., description="Canonical ID: '{provider}:{name}:{version}' or simplified form"
    )
    name: str = Field(..., description="Display name (e.g., 'GPT-4o')")
    provider: str = Field(..., description="Organization (e.g., 'OpenAI', 'Anthropic')")
    family: str | None = Field(default=None, description="Model family (e.g., 'GPT-4', 'Claude-3')")
    release_date: date | None = Field(default=None, description="Official release date")
    release_date_source: str | None = Field(
        default=None, description="Source URL for release date"
    )
    status: ModelStatus = Field(default=ModelStatus.VERIFIED, description="Verification status")
    parameter_count: float | None = Field(default=None, description="Parameter count in billions")
    training_compute_flop: float | None = Field(default=None, description="Training compute in FLOP")
    training_compute_notes: str | None = Field(default=None, description="Notes about compute estimate")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def generate_id(cls, provider: str, name: str, version: str = "") -> str:
        """Generate canonical model ID."""
        parts = [provider.lower().replace(" ", "_"), name.lower().replace(" ", "_")]
        if version:
            parts.append(version)
        return ":".join(parts)


class Result(BaseModel):
    """Benchmark result with full provenance.

    This is the core data point. Every plotted value comes from a Result.
    """

    result_id: str = Field(..., description="Unique result identifier")
    model_id: str = Field(..., description="FK to Model")
    benchmark_id: str = Field(..., description="FK to Benchmark")

    # Score data (nullable for missing/unverified)
    score: float | None = Field(default=None, description="Benchmark score (NULL if unverified)")
    score_stderr: float | None = Field(default=None, description="Standard error of score")
    score_ci_low: float | None = Field(default=None, description="Lower confidence interval")
    score_ci_high: float | None = Field(default=None, description="Upper confidence interval")

    # Evaluation metadata
    evaluation_date: date | None = Field(default=None, description="When evaluation was run")
    harness_version: str | None = Field(default=None, description="Benchmark harness version")
    subset: str | None = Field(default=None, description="Subset used (e.g., 'verified', 'full')")

    # PROVENANCE (Required for all results)
    source_id: str = Field(..., description="FK to Source - REQUIRED")
    trust_tier: TrustTier = Field(..., description="Data quality tier (A/B/C)")
    evaluation_notes: str | None = Field(default=None, description="Additional eval notes")

    # Audit fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_override: bool = Field(default=False, description="True if from overrides.yml")

    @classmethod
    def generate_id(cls, model_id: str, benchmark_id: str, evaluation_date: date | None = None) -> str:
        """Generate deterministic result ID."""
        date_str = evaluation_date.isoformat() if evaluation_date else "unknown"
        content = f"{model_id}:{benchmark_id}:{date_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: float | None) -> float | None:
        """Basic score validation (benchmark-specific validation in ingestors)."""
        if v is not None and (v < -1000 or v > 1000):
            raise ValueError(f"Score {v} is outside reasonable range [-1000, 1000]")
        return v

    @model_validator(mode="after")
    def validate_provenance(self) -> "Result":
        """Ensure provenance fields are present."""
        if not self.source_id:
            raise ValueError("source_id is required for all results")
        if not self.trust_tier:
            raise ValueError("trust_tier is required for all results")
        return self


class ChangelogEntry(BaseModel):
    """Entry in the append-only changelog."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    action: str = Field(..., description="insert, update, delete, override")
    table: str = Field(..., description="Table affected: results, models, benchmarks, sources")
    record_id: str = Field(..., description="ID of affected record")
    old_value: dict[str, Any] | None = Field(default=None, description="Previous value (for updates)")
    new_value: dict[str, Any] | None = Field(default=None, description="New value")
    reason: str | None = Field(default=None, description="Reason for change")
    source: str = Field(default="ingestor", description="What triggered the change")

    def to_jsonl(self) -> str:
        """Convert to JSON Lines format."""
        return json.dumps(self.model_dump(mode="json"), default=str)


class Override(BaseModel):
    """Manual override specification from overrides.yml."""

    result_id: str | None = Field(default=None, description="Specific result to override")
    model_id: str | None = Field(default=None, description="Model to override (all results)")
    benchmark_id: str | None = Field(default=None, description="Benchmark to override")
    field_name: str = Field(..., description="Field to override (e.g., 'score', 'trust_tier')")
    old_value: Any | None = Field(default=None, description="Expected old value (for validation)")
    new_value: Any = Field(..., description="New value to set")
    reason: str = Field(..., description="Reason for override")
    override_date: date = Field(..., description="Date override was added")

    @model_validator(mode="after")
    def validate_target(self) -> "Override":
        """Ensure at least one target is specified."""
        if not any([self.result_id, self.model_id, self.benchmark_id]):
            raise ValueError("At least one of result_id, model_id, or benchmark_id is required")
        return self


class ProjectionResult(BaseModel):
    """Result of a projection/forecast."""

    benchmark_id: str
    method: str = Field(..., description="linear, saturation, etc.")
    forecast_dates: list[date]
    forecast_values: list[float]
    ci_80_low: list[float]
    ci_80_high: list[float]
    ci_95_low: list[float]
    ci_95_high: list[float]
    fit_window_start: date
    fit_window_end: date
    r_squared: float | None = None
    notes: str | None = None
