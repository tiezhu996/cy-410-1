import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.diagnostics import DataDiagnostic
from src.core.importer import DataImporter
from src.store.database import connect, init_db
from src.store.repository import HeritageRepository

tmp_dir = Path("_test_tmp")
tmp_dir.mkdir(exist_ok=True)
db = tmp_dir / "heritage.db"
output = tmp_dir / "diagnostics.html"

try:
    print("=" * 60)
    print("1. 初始化数据库并导入数据")
    init_db(str(db))
    DataImporter().import_file("tests/fixtures/sample.csv", str(db))

    print("\n2. 生成 SQLite 系统表（通过 ANALYZE 触发，模拟真实场景）")
    with connect(str(db)) as conn:
        conn.execute("ANALYZE")
        user_tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        system_tables = [t for t in user_tables if t.startswith("sqlite_")]
        conn.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT, value TEXT)")
        conn.commit()
    print(f"   系统表: {system_tables} (ANALYZE 自动生成)")
    print(f"   额外添加 sys_config 测试表")

    print("\n3. 验证 repository.list_tables() 过滤功能")
    repo = HeritageRepository(str(db))
    tables_default = repo.list_tables()
    tables_all = repo.list_tables(include_system=True)

    print(f"   默认返回表: {tables_default}")
    print(f"   全部表(含系统): {tables_all}")

    has_system_default = any(t.startswith("sqlite_") for t in tables_default)
    has_system_all = any(t.startswith("sqlite_") for t in tables_all)
    print(f"   默认含系统表: {has_system_default}")
    print(f"   全部含系统表: {has_system_all}")
    assert not has_system_default, "默认模式不应包含系统表!"
    assert has_system_all, "全部模式应包含系统表!"
    print("   ✅ repository.list_tables() 过滤正确")

    print("\n4. 验证 DataDiagnostic.scan_database() 过滤功能")
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(str(db))

    table_names = [t.name for t in report.tables]
    print(f"   诊断报告中的表: {table_names}")
    print(f"   total_tables: {report.total_tables}")
    print(f"   total_records: {report.total_records}")

    has_system_in_report = any(t.startswith("sqlite_") for t in table_names)
    assert not has_system_in_report, "诊断报告不应包含 SQLite 系统表!"
    assert "items" in table_names, "诊断报告应包含业务表 items!"
    print("   ✅ DataDiagnostic 过滤正确")

    print("\n5. 验证 _is_system_table() 辅助方法")
    tests = [
        ("sqlite_sequence", True),
        ("sqlite_stat1", True),
        ("sys_config", True),
        ("pg_catalog", True),
        ("_test_internal", True),
        ("items", False),
        ("users", False),
        ("my_sqlite_data", False),
    ]
    all_pass = True
    for name, expected in tests:
        result = diagnostic._is_system_table(name)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_pass = False
        print(f"   {status} _is_system_table('{name}') = {result} (期望 {expected})")
    assert all_pass, "_is_system_table 测试失败!"
    print("   ✅ 全部通过")

    print("\n6. 验证 HTML 报告不包含系统表")
    diagnostic.export_html(report, str(output))
    content = output.read_text(encoding="utf-8")
    # 检查不应包含任何 sqlite_ 或 sys_ 开头的表名
    assert "sqlite_stat" not in content, "HTML 不应含 sqlite_stat 系统表!"
    assert "sys_config" not in content, "HTML 不应含 sys_config 系统表!"
    assert "items" in content, "HTML 应含业务表 items!"
    print("   ✅ HTML 报告过滤正确")

    print("\n7. 验证报告记录数未被污染")
    items_table = next(t for t in report.tables if t.name == "items")
    assert report.total_records == items_table.total_rows, (
        f"记录数被污染! total={report.total_records}, items={items_table.total_rows}"
    )
    assert report.total_tables == len(report.tables), (
        f"表数不一致! total_tables={report.total_tables}, actual={len(report.tables)}"
    )
    print(f"   total_records={report.total_records} == items_table.total_rows={items_table.total_rows}")
    print("   ✅ 统计数据未被系统表污染")

    print("\n" + "=" * 60)
    print("🎉 所有验证全部通过! 系统表已成功过滤!")
    print("=" * 60)

finally:
    import shutil
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if Path("_run_tests.py").exists():
        os.remove("_run_tests.py")
    if Path("_verify_fix.py").exists():
        pass
