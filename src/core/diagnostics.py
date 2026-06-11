from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.fields import REQUIRED_FIELDS, STANDARD_FIELDS
from src.models.schemas import (
    DatabaseDiagnostic,
    FieldDiagnostic,
    TableDiagnostic,
)
from src.store.repository import HeritageRepository
from src.utils.constants import FIELD_DISPLAY_NAMES


class DataDiagnostic:
    SYSTEM_TABLE_PREFIXES = ("sqlite_", "sys_", "pg_", "_test_")

    def __init__(self) -> None:
        self.field_notes = {
            "project_name": "非遗项目正式名称，应为唯一标识",
            "project_code": "项目编码，主键字段，应唯一且非空",
            "category": "项目类别，应在标准分类列表中",
            "batch": "申报批次，应为1-10之间的整数",
            "region_province": "省级行政区，必填字段",
            "region_city": "市级行政区",
            "region_district": "县级行政区",
            "protection_unit": "保护单位名称",
            "inheritor_name": "代表性传承人姓名",
            "inheritor_age": "传承人年龄，应在0-120之间",
            "inheritor_gender": "传承人性别，应为'男'或'女'",
            "endangerment": "濒危程度，应为'濒危'/'一般'/'良好'",
            "description": "项目详细描述",
            "declare_year": "申报年份，应在合理范围内",
        }

    def _is_system_table(self, name: str) -> bool:
        return any(name.startswith(prefix) for prefix in self.SYSTEM_TABLE_PREFIXES)

    def scan_database(self, db_path: str) -> DatabaseDiagnostic:
        repo = HeritageRepository(db_path)
        tables = repo.list_tables()
        tables = [t for t in tables if not self._is_system_table(t)]
        table_diagnostics: list[TableDiagnostic] = []
        total_records = 0

        for table in tables:
            table_diag = self._diagnose_table(repo, table)
            table_diagnostics.append(table_diag)
            total_records += table_diag.total_rows

        overall_score = (
            sum(t.quality_score * t.total_rows for t in table_diagnostics) / total_records
            if total_records > 0
            else 0.0
        )

        issues_summary = self._summarize_issues(table_diagnostics)

        return DatabaseDiagnostic(
            db_path=db_path,
            total_tables=len(tables),
            total_records=total_records,
            tables=table_diagnostics,
            overall_quality_score=round(overall_score, 2),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            issues_summary=issues_summary,
        )

    def _diagnose_table(self, repo: HeritageRepository, table: str) -> TableDiagnostic:
        total_rows = repo.count_total(table)
        columns = repo.get_table_columns(table)
        field_diagnostics: list[FieldDiagnostic] = []

        for column_name, _ in columns:
            if column_name in ("id", "created_at", "updated_at", "is_anomaly"):
                continue
            field_diag = self._diagnose_field(repo, table, column_name, total_rows)
            field_diagnostics.append(field_diag)

        duplicate_rows = repo.count_duplicate_rows(table)
        duplicate_rows_ratio = duplicate_rows / total_rows if total_rows > 0 else 0.0

        if field_diagnostics:
            overall_completeness = sum(f.completeness_score for f in field_diagnostics) / len(
                field_diagnostics
            )
            overall_uniqueness = sum(f.uniqueness_score for f in field_diagnostics) / len(
                field_diagnostics
            )
            overall_validity = sum(f.validity_score for f in field_diagnostics) / len(
                field_diagnostics
            )
        else:
            overall_completeness = overall_uniqueness = overall_validity = 0.0

        quality_score = (
            overall_completeness * 0.4 + overall_uniqueness * 0.3 + overall_validity * 0.3
        )

        return TableDiagnostic(
            name=table,
            total_rows=total_rows,
            total_columns=len(columns),
            fields=field_diagnostics,
            duplicate_rows=duplicate_rows,
            duplicate_rows_ratio=round(duplicate_rows_ratio, 4),
            overall_completeness=round(overall_completeness, 2),
            overall_uniqueness=round(overall_uniqueness, 2),
            overall_validity=round(overall_validity, 2),
            quality_score=round(quality_score, 2),
        )

    def _diagnose_field(
        self, repo: HeritageRepository, table: str, field: str, total_rows: int
    ) -> FieldDiagnostic:
        display_name = FIELD_DISPLAY_NAMES.get(field, field)

        missing_count = repo.count_nulls(field, table)
        missing_ratio = missing_count / total_rows if total_rows > 0 else 0.0

        duplicate_count = repo.count_duplicates(field, table)
        duplicate_ratio = duplicate_count / total_rows if total_rows > 0 else 0.0

        anomaly_count = repo.count_field_anomalies(field, table)
        anomaly_ratio = anomaly_count / total_rows if total_rows > 0 else 0.0

        sample_values = repo.get_sample_values(field, limit=5, table=table)

        note = self.field_notes.get(field, "")
        if field in REQUIRED_FIELDS:
            note = "【必填】" + note
        if field in STANDARD_FIELDS:
            note = "【标准字段】" + note

        return FieldDiagnostic(
            name=field,
            display_name=display_name,
            total=total_rows,
            missing_count=missing_count,
            missing_ratio=round(missing_ratio, 4),
            duplicate_count=duplicate_count,
            duplicate_ratio=round(duplicate_ratio, 4),
            anomaly_count=anomaly_count,
            anomaly_ratio=round(anomaly_ratio, 4),
            sample_values=sample_values,
            note=note,
        )

    def _summarize_issues(self, tables: list[TableDiagnostic]) -> dict[str, int]:
        summary = {
            "high_missing_fields": 0,
            "high_duplicate_fields": 0,
            "high_anomaly_fields": 0,
            "total_duplicate_rows": 0,
            "required_fields_missing": 0,
        }

        for table in tables:
            summary["total_duplicate_rows"] += table.duplicate_rows
            for field in table.fields:
                if field.missing_ratio > 0.2:
                    summary["high_missing_fields"] += 1
                if field.duplicate_ratio > 0.5:
                    summary["high_duplicate_fields"] += 1
                if field.anomaly_ratio > 0.1:
                    summary["high_anomaly_fields"] += 1
                if field.name in REQUIRED_FIELDS and field.missing_count > 0:
                    summary["required_fields_missing"] += 1

        return summary

    def export_html(self, diagnostic: DatabaseDiagnostic, output_path: str) -> None:
        template_dir = Path(__file__).resolve().parents[1] / "templates"
        env = Environment(loader=FileSystemLoader(template_dir))
        env.filters["multiply"] = lambda value, factor: value * factor
        env.filters["pct"] = self._format_pct
        template = env.get_template("diagnostics.html.j2")
        html = template.render(
            diagnostic=diagnostic,
            pct=self._format_pct,
            bar_color=self._get_bar_color,
        )
        Path(output_path).write_text(html, encoding="utf-8")

    def print_summary(self, diagnostic: DatabaseDiagnostic) -> None:
        print("\n" + "=" * 60)
        print("  数据质量诊断报告")
        print("=" * 60)
        print(f"数据库: {diagnostic.db_path}")
        print(f"生成时间: {diagnostic.generated_at}")
        print(f"总记录数: {diagnostic.total_records}")
        print(f"综合质量评分: {diagnostic.overall_quality_score:.2f}/100")
        print("-" * 60)

        for table in diagnostic.tables:
            print(f"\n【表: {table.name}】")
            print(f"  记录数: {table.total_rows} | 字段数: {table.total_columns}")
            print(f"  完整性: {table.overall_completeness:.2f}% | "
                  f"唯一性: {table.overall_uniqueness:.2f}% | "
                  f"有效性: {table.overall_validity:.2f}%")
            print(f"  质量等级: {table.grade} | 评分: {table.quality_score:.2f}/100")
            if table.duplicate_rows > 0:
                print(f"  ⚠️  重复记录数: {table.duplicate_rows} "
                      f"({table.duplicate_rows_ratio*100:.2f}%)")

            print(f"\n  字段诊断 (前5个问题最多的字段):")
            sorted_fields = sorted(
                table.fields,
                key=lambda f: f.missing_ratio + f.duplicate_ratio + f.anomaly_ratio,
                reverse=True,
            )[:5]

            for field in sorted_fields:
                issues = []
                if field.missing_ratio > 0:
                    issues.append(f"缺失 {field.missing_ratio*100:.1f}%")
                if field.duplicate_ratio > 0:
                    issues.append(f"重复 {field.duplicate_ratio*100:.1f}%")
                if field.anomaly_ratio > 0:
                    issues.append(f"异常 {field.anomaly_ratio*100:.1f}%")
                issue_str = ", ".join(issues) if issues else "✓ 正常"
                print(f"    {field.display_name} ({field.name}): {issue_str}")

        print("\n" + "-" * 60)
        print("问题汇总:")
        for key, value in diagnostic.issues_summary.items():
            if value > 0:
                label = {
                    "high_missing_fields": "  - 高缺失字段 (>20%)",
                    "high_duplicate_fields": "  - 高重复字段 (>50%)",
                    "high_anomaly_fields": "  - 高异常字段 (>10%)",
                    "total_duplicate_rows": "  - 重复记录总数",
                    "required_fields_missing": "  - 必填字段缺失",
                }.get(key, f"  - {key}")
                print(f"{label}: {value}")
        print("=" * 60 + "\n")

    @staticmethod
    def _format_pct(value: float) -> str:
        return f"{value * 100:.2f}%"

    @staticmethod
    def _get_bar_color(ratio: float) -> str:
        pct = ratio * 100
        if pct < 5:
            return "#10b981"
        elif pct < 15:
            return "#f59e0b"
        else:
            return "#ef4444"
