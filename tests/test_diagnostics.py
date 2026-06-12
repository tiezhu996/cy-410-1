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


def test_repository_list_tables_excludes_only_sqlite_tables(tmp_path: Path) -> None:
    from src.store.database import connect, init_db
    from src.store.repository import HeritageRepository

    db = tmp_path / "heritage.db"
    init_db(str(db))
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))

    with connect(str(db)) as conn:
        conn.execute("ANALYZE")
        conn.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT, value TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS pg_catalog (data TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS _test_internal (data TEXT)")
        all_tables_before = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        has_sqlite = any(t.startswith("sqlite_") for t in all_tables_before)
        if not has_sqlite:
            conn.execute("CREATE TABLE IF NOT EXISTS sqlite_stat1 (tbl, idx, stat)")
        conn.commit()

    repo = HeritageRepository(str(db))
    tables = repo.list_tables()

    assert "items" in tables
    assert "sys_config" in tables, "sys_ 前缀的业务表不应被误伤"
    assert "pg_catalog" in tables, "pg_ 前缀的业务表不应被误伤"
    assert "_test_internal" in tables, "_test_ 前缀的业务表不应被误伤"
    for t in tables:
        assert not t.startswith("sqlite_"), f"SQLite 内部表 {t} 应被过滤"

    all_tables = repo.list_tables(include_system=True)
    has_sqlite_all = any(t.startswith("sqlite_") for t in all_tables)
    assert has_sqlite_all, "include_system=True 应返回包含 sqlite_ 表的完整列表"


def test_diagnostics_excludes_only_sqlite_internal_tables(tmp_path: Path) -> None:
    from src.store.database import connect, init_db

    db = tmp_path / "heritage.db"
    init_db(str(db))
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))

    with connect(str(db)) as conn:
        conn.execute("ANALYZE")
        conn.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT, value TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS pg_settings (name TEXT, value TEXT)")
        conn.commit()

    with connect(str(db)) as conn:
        all_tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        has_sqlite = any(t.startswith("sqlite_") for t in all_tables)
        if not has_sqlite:
            conn.execute("CREATE TABLE IF NOT EXISTS sqlite_stat1 (tbl, idx, stat)")
            conn.execute("INSERT INTO sqlite_stat1 VALUES ('items', 'idx', '100')")
            conn.commit()

    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))

    table_names = [t.name for t in report.tables]
    assert "items" in table_names, "业务表 items 应该在报告中"
    assert "sys_config" in table_names, "sys_ 前缀的真实业务表不应被误伤"
    assert "pg_settings" in table_names, "pg_ 前缀的真实业务表不应被误伤"
    for t in table_names:
        assert not t.startswith("sqlite_"), f"SQLite 内部表 {t} 不应出现在诊断报告中"

    assert report.total_tables == len(table_names)
    assert report.total_records == sum(t.total_rows for t in report.tables)


def test_diagnostics_sqlite_sequence_not_in_report_but_sys_preserved(tmp_path: Path) -> None:
    from src.store.database import connect, init_db

    db = tmp_path / "heritage.db"
    output = tmp_path / "diagnostics.html"
    init_db(str(db))
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))

    with connect(str(db)) as conn:
        conn.execute("ANALYZE")
        conn.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT, value TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS _test_users (id INTEGER, name TEXT)")
        conn.commit()

    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))
    diagnostic.export_html(report, str(output))

    content = output.read_text(encoding="utf-8")
    assert "sqlite_sequence" not in content, "HTML 中不应出现 sqlite_sequence"
    assert "sqlite_stat" not in content, "HTML 中不应出现 sqlite_stat 系列表"
    assert "sys_config" in content, "HTML 中应正常出现 sys_config 业务表"
    assert "_test_users" in content, "HTML 中应正常出现 _test_users 业务表"
    assert "items" in content, "HTML 中应包含业务表 items"
    assert str(report.total_tables) in content


def test_diagnostics_is_system_table_helper_narrow() -> None:
    diagnostic = DataDiagnostic()
    assert diagnostic._is_system_table("sqlite_sequence")
    assert diagnostic._is_system_table("sqlite_stat1")
    assert diagnostic._is_system_table("sqlite_stat4")
    assert not diagnostic._is_system_table("sys_config"), "sys_ 不应被判定为系统表"
    assert not diagnostic._is_system_table("pg_catalog"), "pg_ 不应被判定为系统表"
    assert not diagnostic._is_system_table("_test_internal"), "_test_ 不应被判定为系统表"
    assert not diagnostic._is_system_table("items")
    assert not diagnostic._is_system_table("users")
    assert not diagnostic._is_system_table("my_sqlite_data"), "含 sqlite_ 子串但非前缀不应被过滤"
