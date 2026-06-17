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
    COL_CODIGO_TURMA_NOMINAL,
    CONTROLE_GERAL_FILE,
    ensure_directories,
    has_vinculo,
    load_controle_geral,
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
    arquivo: Optional[Path] = typer.Option(
        None,
        "--arquivo",
        help=f"Caminho alternativo para {CONTROLE_GERAL_FILE}.",
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

    arquivo_path = resolve_input(arquivo)
    output_path = resolve_output(output)

    console.print(Panel.fit("[bold cyan]NR23 CLI Engine[/bold cyan]\nSaneamento em execução..."))

    try:
        df_controle, df_cronograma = load_controle_geral(arquivo_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Erro:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(f"  Arquivo: [green]{arquivo_path.name}[/green]")
    console.print(f"    Aba colaboradores: {len(df_controle)} linhas")
    console.print(f"    Aba cronograma: {len(df_cronograma)} linhas")
    console.print(f"  Raio máximo: [yellow]{raio_max:.0f} km[/yellow]")

    result = run_engine(df_controle, df_cronograma, raio_max_km=raio_max)

    ok, msg = validate_conservation(df_controle, result)
    status_color = "green" if ok else "red"
    console.print(f"  Validação: [{status_color}]{msg}[/{status_color}]")

    vinculacoes = int(result.colaboradores[COL_CODIGO_TURMA_NOMINAL].apply(has_vinculo).sum())
    sem_turma_antes = int((~df_controle[COL_CODIGO_TURMA_NOMINAL].apply(has_vinculo)).sum())
    novas = len(result.vinculacoes)

    sheets = {
        "NR23 Controle Nominal": result.colaboradores,
        "Cronograma de Turmas": result.turmas,
        "SANEAMENTO_TURMAS_NR23": result.saneamento_turmas,
        "VINCULACOES_REALIZADAS": result.vinculacoes,
        "PENDENTES_DIMENSIONAMENTO_NR23": result.pendentes,
    }
    save_excel(output_path, sheets)

    table = Table(title="Resumo do Processamento")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", justify="right", style="bold")
    table.add_row("Colaboradores no controle", str(len(df_controle)))
    table.add_row("Sem turma (entrada)", str(sem_turma_antes))
    table.add_row("Novas vinculações", str(novas))
    table.add_row("Com turma (saída)", str(vinculacoes))
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
            f"Entrada (knowledge-base/{CONTROLE_GERAL_FILE}):\n"
            "  • Aba [cyan]NR23 Controle Nominal[/cyan] — colaboradores\n"
            "    - NOME COMPLETO\n"
            "    - NR 23 CÓDIGO DA TURMA (vazio = a dimensionar)\n"
            "    - LOCAL DO BRIGADISTA - PCI (localidade principal)\n"
            "    - SUAREA (fallback de localidade)\n"
            "  • Aba [cyan]Cronograma de Turmas[/cyan] — turmas\n"
            "    - CÓDIGO DA TURMA\n"
            "    - TURMA /LOCALIDADE\n"
            "    - STATUS DA TURMA (apenas AGENDADO recebe vínculos)\n\n"
            "Saída (outputs/):\n"
            "  • NR23_SANEADO_2026.xlsx\n\n"
            "Regras: mín. 10 / máx. 20 por turma; proximidade geográfica; "
            "turmas futuras (>= amanhã).",
            title="Informações",
            border_style="blue",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
