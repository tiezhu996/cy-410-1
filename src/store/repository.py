from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from src.models.fields import STANDARD_FIELDS
from src.store.database import connect, init_db


class HeritageRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        init_db(db_path)

    def insert_frame(self, frame: pd.DataFrame, incremental: bool = True) -> int:
        if frame.empty:
            return 0
        columns = STANDARD_FIELDS
        placeholders = ", ".join(["?"] * len(columns))
        conflict = "OR IGNORE" if incremental else "OR REPLACE"
        sql = f"INSERT {conflict} INTO items ({', '.join(columns)}) VALUES ({placeholders})"
        rows = [tuple(None if pd.isna(row[col]) else row[col] for col in columns) for _, row in frame.iterrows()]
        with connect(self.db_path) as conn:
            before = conn.total_changes
            conn.executemany(sql, rows)
            return conn.total_changes - before

    def fetch(self, where: list[str] | None = None, order_by: str | None = None, limit: int | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM items"
        params: list[Any] = []
        if where:
            clauses = []
            for expression in where:
                if ">=" in expression:
                    field, value = expression.split(">=", 1)
                    clauses.append(f"{field.strip()} >= ?")
                    params.append(value.strip())
                elif "=" in expression:
                    field, value = expression.split("=", 1)
                    clauses.append(f"{field.strip()} = ?")
                    params.append(value.strip())
                else:
                    raise ValueError(f"不支持的查询条件: {expression}")
            sql += " WHERE " + " AND ".join(clauses)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with connect(self.db_path) as conn:
            return conn.execute(sql, params).fetchall()

    def count_by(self, field: str) -> list[tuple[Any, int]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(f"SELECT {field}, COUNT(*) AS total FROM items GROUP BY {field} ORDER BY total DESC").fetchall()
            return [(row[0], row[1]) for row in rows]

    def cross_count(self, left: str, right: str) -> list[tuple[Any, Any, int]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT {left}, {right}, COUNT(*) AS total FROM items GROUP BY {left}, {right} ORDER BY total DESC"
            ).fetchall()
            return [(row[0], row[1], row[2]) for row in rows]

    def update_cleaned(self, rows: list[dict[str, Any]]) -> None:
        with connect(self.db_path) as conn:
            for row in rows:
                columns = [key for key in row.keys() if key != "id"]
                assignments = ", ".join(f"{column}=?" for column in columns)
                values = [row[column] for column in columns]
                values.append(row["id"])
                conn.execute(f"UPDATE items SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE id=?", values)

    def delete_ids(self, ids: list[int]) -> int:
        if not ids:
            return 0
        with connect(self.db_path) as conn:
            before = conn.total_changes
            conn.executemany("DELETE FROM items WHERE id=?", [(item_id,) for item_id in ids])
            return conn.total_changes - before

    def execute_sql(self, sql: str) -> list[sqlite3.Row]:
        with connect(self.db_path) as conn:
            cursor = conn.execute(sql)
            return cursor.fetchall() if cursor.description else []

    def count_total(self, table: str = "items") -> int:
        with connect(self.db_path) as conn:
            result = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return result[0] if result else 0

    def count_nulls(self, field: str, table: str = "items") -> int:
        with connect(self.db_path) as conn:
            result = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL OR {field} = ''"
            ).fetchone()
            return result[0] if result else 0

    def count_duplicates(self, field: str, table: str = "items") -> int:
        with connect(self.db_path) as conn:
            result = conn.execute(
                f"SELECT SUM(cnt) FROM (SELECT COUNT(*) AS cnt FROM {table} WHERE {field} IS NOT NULL GROUP BY {field} HAVING COUNT(*) > 1)"
            ).fetchone()
            return result[0] if result and result[0] else 0

    def count_anomalies(self, table: str = "items") -> int:
        with connect(self.db_path) as conn:
            result = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE is_anomaly = 1").fetchone()
            return result[0] if result else 0

    def count_field_anomalies(self, field: str, table: str = "items") -> int:
        from src.models.fields import INTEGER_FIELDS

        if field in INTEGER_FIELDS:
            with connect(self.db_path) as conn:
                if field == "inheritor_age":
                    result = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND ({field} < 0 OR {field} > 120)"
                    ).fetchone()
                elif field == "declare_year":
                    result = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND ({field} < 1900 OR {field} > 2100)"
                    ).fetchone()
                elif field == "batch":
                    result = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND ({field} < 1 OR {field} > 10)"
                    ).fetchone()
                else:
                    result = conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND {field} < 0"
                    ).fetchone()
                return result[0] if result else 0
        elif field == "endangerment":
            from src.utils.constants import ENDANGERMENT_LEVELS

            placeholders = ", ".join(["?"] * len(ENDANGERMENT_LEVELS))
            with connect(self.db_path) as conn:
                result = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND {field} NOT IN ({placeholders})",
                    ENDANGERMENT_LEVELS,
                ).fetchone()
                return result[0] if result else 0
        elif field == "inheritor_gender":
            with connect(self.db_path) as conn:
                result = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {field} IS NOT NULL AND {field} NOT IN ('男', '女')"
                ).fetchone()
                return result[0] if result else 0
        return 0

    def get_sample_values(self, field: str, limit: int = 5, table: str = "items") -> list[Any]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT DISTINCT {field} FROM {table} WHERE {field} IS NOT NULL LIMIT ?",
                (limit,),
            ).fetchall()
            return [row[0] for row in rows]

    SYSTEM_TABLE_PREFIXES = ("sqlite_", "sys_", "pg_", "_test_")

    def list_tables(self, include_system: bool = False) -> list[str]:
        with connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            tables = [row[0] for row in rows]
            if not include_system:
                tables = [
                    name for name in tables
                    if not any(name.startswith(prefix) for prefix in self.SYSTEM_TABLE_PREFIXES)
                ]
            return tables

    def get_table_columns(self, table: str) -> list[tuple[str, str]]:
        with connect(self.db_path) as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            return [(row["name"], row["type"]) for row in rows]

    def count_duplicate_rows(self, table: str = "items") -> int:
        with connect(self.db_path) as conn:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "project_code" in columns:
                result = conn.execute(
                    f"SELECT COUNT(*) - COUNT(DISTINCT project_code) FROM {table} WHERE project_code IS NOT NULL"
                ).fetchone()
                return result[0] if result else 0
            return 0
