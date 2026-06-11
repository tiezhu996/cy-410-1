from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImportResult:
    inserted: int
    invalid_rows: list[dict[str, Any]]


@dataclass
class CleanReport:
    normalized: int
    duplicates_removed: int
    defaults_filled: int
    anomalies_marked: int


@dataclass
class StatsResult:
    headers: list[str]
    rows: list[tuple[Any, ...]]


@dataclass
class FieldDiagnostic:
    name: str
    display_name: str
    total: int
    missing_count: int
    missing_ratio: float
    duplicate_count: int
    duplicate_ratio: float
    anomaly_count: int
    anomaly_ratio: float
    sample_values: list[Any] = field(default_factory=list)
    note: str = ""

    @property
    def completeness_score(self) -> float:
        return (1.0 - self.missing_ratio) * 100

    @property
    def uniqueness_score(self) -> float:
        return (1.0 - self.duplicate_ratio) * 100

    @property
    def validity_score(self) -> float:
        return (1.0 - self.anomaly_ratio) * 100


@dataclass
class TableDiagnostic:
    name: str
    total_rows: int
    total_columns: int
    fields: list[FieldDiagnostic]
    duplicate_rows: int
    duplicate_rows_ratio: float
    overall_completeness: float
    overall_uniqueness: float
    overall_validity: float
    quality_score: float

    @property
    def grade(self) -> str:
        if self.quality_score >= 90:
            return "A (优秀)"
        elif self.quality_score >= 80:
            return "B (良好)"
        elif self.quality_score >= 70:
            return "C (一般)"
        elif self.quality_score >= 60:
            return "D (较差)"
        else:
            return "F (严重)"


@dataclass
class DatabaseDiagnostic:
    db_path: str
    total_tables: int
    total_records: int
    tables: list[TableDiagnostic]
    overall_quality_score: float
    generated_at: str
    issues_summary: dict[str, int] = field(default_factory=dict)
