"""Gera planilha de exemplo com a estrutura real do Controle Geral_NR23."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.utils import (
    CONTROLE_GERAL_FILE,
    KNOWLEDGE_BASE_DIR,
    SHEET_CONTROLE_NOMINAL,
    SHEET_CRONOGRAMA,
    ensure_directories,
)

ensure_directories()

controle = pd.DataFrame(
    {
        "NOME COMPLETO": [f"Colaborador {i}" for i in range(1, 46)],
        "NR 23 CÓDIGO DA TURMA": [pd.NA] * 45,
        "LOCAL DO BRIGADISTA - PCI": (
            ["SALVADOR"] * 8
            + ["RECIFE"] * 7
            + ["NATAL"] * 6
            + ["FEIRA DE SANTANA"] * 5
            + ["CAMACARI"] * 4
            + ["OLINDA"] * 5
            + ["MOSSORO"] * 4
            + [pd.NA] * 6
        ),
        "SUAREA": [pd.NA] * 39 + ["CARUARU", "TERESINA", "TERESINA", "CARUARU", "TERESINA", "TERESINA"],
    }
)
controle.loc[0, "NR 23 CÓDIGO DA TURMA"] = "TURMA-HIST-001"

cronograma = pd.DataFrame(
    {
        "CÓDIGO DA TURMA": [
            "TURMA-HIST-001",
            "TURMA-HOJE-001",
            "TURMA-2026-001",
            "TURMA-2026-002",
            "TURMA-2026-003",
            "TURMA-2026-004",
            "TURMA-2026-005",
            "TURMA-2026-006",
        ],
        "TURMA /LOCALIDADE": [
            "SALVADOR",
            "SALVADOR",
            "SALVADOR",
            "RECIFE",
            "NATAL",
            "FEIRA DE SANTANA",
            "CAMACARI",
            "OLINDA",
        ],
        "DATA": [
            "10/05/2026",
            pd.Timestamp.today().strftime("%d/%m/%Y"),
            "20/07/2026",
            "25/07/2026",
            "01/08/2026",
            "15/08/2026",
            "20/08/2026",
            "05/09/2026",
        ],
        "STATUS DA TURMA": [
            "OK",
            "OK",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
            "AGENDADO",
        ],
    }
)

output_path = KNOWLEDGE_BASE_DIR / CONTROLE_GERAL_FILE
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    controle.to_excel(writer, sheet_name=SHEET_CONTROLE_NOMINAL, index=False)
    cronograma.to_excel(writer, sheet_name=SHEET_CRONOGRAMA, index=False)

print(f"Gerado: {output_path}")
print(f"  Aba: {SHEET_CONTROLE_NOMINAL} ({len(controle)} linhas)")
print(f"  Aba: {SHEET_CRONOGRAMA} ({len(cronograma)} linhas)")
