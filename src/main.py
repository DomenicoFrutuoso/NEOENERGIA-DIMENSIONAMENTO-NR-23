"""Camada de apresentação CLI — rotas Typer do NR23 CLI Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.engine import run_engine, validate_conservation
from src.utils import (
    CONTROLE_NOMINAL_FILE,
    CRONOGRAMA_TURMAS_FILE,
    ensure_directories,
    has_vinculo,
    load_excel,
    resolve_input,
    resolve_output,
    save_excel,
)

app = typer.Typer(
    name="nr23",
    help="NR23 CLI Engine — saneamento de RH e dimensionamento de turmas normativas.",
    add_completion=False,
)
console = Console()


@app.command("saneamento")
def saneamento(
    raio_max: float = typer.Option(
        50.0,
        "--raio-max",
        help="Raio máximo (km) para vinculação geográfica por proximidade.",
    ),
    controle: Optional[Path] = typer.Option(
        None,
        "--controle",
        help="Caminho alternativo para nr23_controle_nominal.xlsx.",
    ),
    cronograma: Optional[Path] = typer.Option(
        None,
        "--cronograma",
        help="Caminho alternativo para cronograma_turmas.xlsx.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Caminho do arquivo Excel de saída.",
    ),
) -> None:
    """Executa o pipeline completo de saneamento e dimensionamento NR-23."""
    ensure_directories()

    controle_path = resolve_input(controle, CONTROLE_NOMINAL_FILE)
    cronograma_path = resolve_input(cronograma, CRONOGRAMA_TURMAS_FILE)
    output_path = resolve_output(output)

    console.print(Panel.fit("[bold cyan]NR23 CLI Engine[/bold cyan]\nSaneamento em execução..."))

    try:
        df_controle = load_excel(controle_path)
        df_cronograma = load_excel(cronograma_path)
    except FileNotFoundError as exc:
        console.print(f"[bold red]Erro:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"  Controle nominal: [green]{controle_path.name}[/green] ({len(df_controle)} linhas)")
    console.print(f"  Cronograma turmas: [green]{cronograma_path.name}[/green] ({len(df_cronograma)} linhas)")
    console.print(f"  Raio máximo: [yellow]{raio_max:.0f} km[/yellow]")

    result = run_engine(df_controle, df_cronograma, raio_max_km=raio_max)

    ok, msg = validate_conservation(df_controle, result)
    status_color = "green" if ok else "red"
    console.print(f"  Validação: [{status_color}]{msg}[/{status_color}]")

    vinculacoes = int(result.colaboradores["CÓDIGO DA TURMA"].apply(has_vinculo).sum())
    sheets = {
        "COLABORADORES_SANEADOS": result.colaboradores,
        "CRONOGRAMA_ATUALIZADO": result.turmas,
        "SANEAMENTO_TURMAS_NR23": result.saneamento_turmas,
        "VINCULACOES_REALIZADAS": result.vinculacoes,
        "PENDENTES_DIMENSIONAMENTO_NR23": result.pendentes,
    }
    save_excel(output_path, sheets)

    table = Table(title="Resumo do Processamento")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", justify="right", style="bold")
    table.add_row("Colaboradores processados", str(len(df_controle)))
    table.add_row("Vinculados", str(int(vinculacoes)))
    table.add_row("Pendentes", str(len(result.pendentes)))
    table.add_row("Turmas no cronograma", str(len(result.turmas)))
    table.add_row("Arquivo gerado", str(output_path))
    console.print(table)

    if result.audit_log:
        console.print("\n[dim]Últimos eventos de auditoria:[/dim]")
        for line in result.audit_log[-5:]:
            console.print(f"  [dim]• {line}[/dim]")

    if not ok:
        raise typer.Exit(code=1)

    console.print(f"\n[bold green]Saneamento concluido:[/bold green] {output_path}")


@app.command("info")
def info() -> None:
    """Exibe informações sobre o engine e estrutura esperada dos arquivos."""
    console.print(
        Panel(
            "[bold]NR23 CLI Engine[/bold]\n\n"
            "Entrada (knowledge-base/):\n"
            "  • nr23_controle_nominal.xlsx — colaboradores e localidades\n"
            "  • cronograma_turmas.xlsx — turmas, datas e status\n\n"
            "Saída (outputs/):\n"
            "  • NR23_SANEADO_2026.xlsx — abas de saneamento e auditoria\n\n"
            "Regras de capacidade: mín. 10 / máx. 20 colaboradores por turma.\n"
            "Vinculação: match exato de localidade → fallback Haversine (--raio-max).",
            title="Informações",
            border_style="blue",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
