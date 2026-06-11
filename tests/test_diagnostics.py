from pathlib import Path

from src.core.diagnostics import DataDiagnostic
from src.core.importer import DataImporter
from src.models.schemas import DatabaseDiagnostic, TableDiagnostic


def test_diagnostics_scans_database(tmp_path: Path) -> None:
    db = tmp_path / "heritage.db"
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))

    assert isinstance(report, DatabaseDiagnostic)
    assert report.total_tables >= 1
    assert report.total_records > 0
    assert 0 <= report.overall_quality_score <= 100


def test_diagnostics_returns_table_details(tmp_path: Path) -> None:
    db = tmp_path / "heritage.db"
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))

    items_table = next(t for t in report.tables if t.name == "items")
    assert isinstance(items_table, TableDiagnostic)
    assert items_table.total_rows > 0
    assert items_table.total_columns > 0
    assert len(items_table.fields) > 0
    assert 0 <= items_table.overall_completeness <= 100
    assert 0 <= items_table.overall_uniqueness <= 100
    assert 0 <= items_table.overall_validity <= 100
    assert 0 <= items_table.quality_score <= 100


def test_diagnostics_field_level_analysis(tmp_path: Path) -> None:
    db = tmp_path / "heritage.db"
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))

    items_table = next(t for t in report.tables if t.name == "items")
    project_code_field = next(f for f in items_table.fields if f.name == "project_code")

    assert project_code_field.total == items_table.total_rows
    assert project_code_field.missing_count >= 0
    assert 0 <= project_code_field.missing_ratio <= 1
    assert project_code_field.duplicate_count >= 0
    assert 0 <= project_code_field.duplicate_ratio <= 1
    assert project_code_field.anomaly_count >= 0
    assert 0 <= project_code_field.anomaly_ratio <= 1
    assert project_code_field.completeness_score == (1 - project_code_field.missing_ratio) * 100


def test_diagnostics_grade_calculation() -> None:
    from src.models.schemas import TableDiagnostic

    report_a = TableDiagnostic(
        name="test", total_rows=0, total_columns=0, fields=[],
        duplicate_rows=0, duplicate_rows_ratio=0.0,
        overall_completeness=0, overall_uniqueness=0, overall_validity=0,
        quality_score=95,
    )
    assert report_a.grade == "A (优秀)"

    report_b = TableDiagnostic(
        name="test", total_rows=0, total_columns=0, fields=[],
        duplicate_rows=0, duplicate_rows_ratio=0.0,
        overall_completeness=0, overall_uniqueness=0, overall_validity=0,
        quality_score=85,
    )
    assert report_b.grade == "B (良好)"

    report_c = TableDiagnostic(
        name="test", total_rows=0, total_columns=0, fields=[],
        duplicate_rows=0, duplicate_rows_ratio=0.0,
        overall_completeness=0, overall_uniqueness=0, overall_validity=0,
        quality_score=75,
    )
    assert report_c.grade == "C (一般)"

    report_d = TableDiagnostic(
        name="test", total_rows=0, total_columns=0, fields=[],
        duplicate_rows=0, duplicate_rows_ratio=0.0,
        overall_completeness=0, overall_uniqueness=0, overall_validity=0,
        quality_score=65,
    )
    assert report_d.grade == "D (较差)"

    report_f = TableDiagnostic(
        name="test", total_rows=0, total_columns=0, fields=[],
        duplicate_rows=0, duplicate_rows_ratio=0.0,
        overall_completeness=0, overall_uniqueness=0, overall_validity=0,
        quality_score=50,
    )
    assert report_f.grade == "F (严重)"


def test_diagnostics_export_html(tmp_path: Path) -> None:
    db = tmp_path / "heritage.db"
    output = tmp_path / "diagnostics.html"
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))
    diagnostic.export_html(report, str(output))

    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "数据质量诊断报告" in content
    assert "综合质量评分" in content
    assert str(report.overall_quality_score) in content
