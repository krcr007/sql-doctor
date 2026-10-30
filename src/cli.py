import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from src.analyzer import Analyzer

console = Console()

def run_check(sql: str):
    """Run static AST analysis and print a rich report."""
    # 1. Print syntax-highlighted SQL
    syntax = Syntax(sql.strip(), "sql", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title="[bold cyan]Target Query[/bold cyan]", expand=False))

    # 2. Run analysis
    analyzer = Analyzer(sql)
    issues = analyzer.analyze()

    # 3. Clean query case
    if not issues:
        console.print("\n[bold green]No obvious static anti-patterns detected![/bold green]\n")
        return

    # 4. Findings table
    table = Table(title=f"\n[bold red]Static Analysis Findings ({len(issues)} issues)[/bold red]")
    table.add_column("Severity", justify="center")
    table.add_column("Rule", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Recommendation", style="green")

    for issue in issues:
        severity_badge = (
            "[bold red]CRITICAL[/bold red]"
            if issue.severity.upper() == "CRITICAL"
            else "[bold yellow]WARNING[/bold yellow]"
        )
        table.add_row(severity_badge, issue.rule, issue.message, issue.suggestion)

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        prog="sql-doctor",
        description="sql-doctor: Offline SQL Static Analyzer & Query Doctor"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    check_parser = subparsers.add_parser("check", help="Run static AST analysis on a SQL query")
    check_parser.add_argument("sql", help="The raw SQL query string to inspect")

    args = parser.parse_args()

    if args.command == "check":
        run_check(args.sql)


if __name__ == "__main__":
    main()