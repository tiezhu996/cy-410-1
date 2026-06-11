import click

from src.core.diagnostics import DataDiagnostic


@click.command(help="全库数据质量诊断，生成评分报告")
@click.option("--db", default="heritage.db", show_default=True, help="数据库路径")
@click.option("--output", default="diagnostics.html", show_default=True, help="HTML 报告输出路径")
@click.option("--format", "output_format", type=click.Choice(["html", "both"]), default="html", show_default=True, help="输出格式")
@click.option("--no-print", is_flag=True, help="不在控制台打印摘要")
def diagnose(db: str, output: str, output_format: str, no_print: bool) -> None:
    click.echo(f"🔍 正在扫描数据库: {db} ...")
    diagnostic = DataDiagnostic()
    report = diagnostic.scan_database(db)

    if not no_print:
        diagnostic.print_summary(report)

    if output_format in ("html", "both"):
        diagnostic.export_html(report, output)
        click.echo(f"✅ HTML 诊断报告已生成: {output}")

    if report.overall_quality_score < 70:
        click.echo("⚠️  数据质量低于 70 分，建议优先清洗数据后再进行分析。")
    elif report.overall_quality_score < 80:
        click.echo("💡 数据质量一般，部分字段需要关注和优化。")
    else:
        click.echo("✅ 数据质量良好，可以放心使用！")
