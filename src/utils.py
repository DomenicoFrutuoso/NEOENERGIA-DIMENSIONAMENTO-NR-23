"""Helpers de I/O, sanitização de strings e caminhos do projeto."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "knowledge-base"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

CONTROLE_GERAL_FILE = "Controle Geral_NR23.xlsx"
OUTPUT_FILE = "NR23_SANEADO_2026.xlsx"

SHEET_CONTROLE_NOMINAL = "NR23 Controle Nominal"
SHEET_CRONOGRAMA = "Cronograma de Turmas"

# Aba NR23 Controle Nominal
COL_NOME_COMPLETO = "NOME COMPLETO"
COL_CODIGO_TURMA_NOMINAL = "NR 23 CÓDIGO DA TURMA"
COL_LOCAL_PCI = "LOCAL DO BRIGADISTA - PCI"
COL_SUAREA = "SUAREA"

# Aba Cronograma de Turmas
COL_CODIGO_TURMA = "CÓDIGO DA TURMA"
COL_TURMA_LOCALIDADE = "TURMA /LOCALIDADE"
COL_STATUS_TURMA = "STATUS DA TURMA"
COL_DATA_TURMA = "DATA"
COL_ACAO_RECOMENDADA = "AÇÃO RECOMENDADA"
COL_VINCULOS = "VÍNCULOS REAIS"
COL_MOTIVO_PENDENCIA = "MOTIVO PENDÊNCIA"
COL_LOCALIDADE_USADA = "LOCALIDADE USADA"

HISTORICAL_CUTOFF = pd.Timestamp("2026-06-12")
MIN_VINCULOS = 10
MAX_VINCULOS = 20
STATUS_AGENDADO = "AGENDADO"


def sanitize_string(value: object) -> str:
    """Normaliza strings para comparação (trim, upper, sem acentos)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def has_text(value: object) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return bool(str(value).strip())


def has_vinculo(value: object) -> bool:
    return has_text(value)


def resolve_localidade_colaborador(row: pd.Series) -> object:
    """Prioriza LOCAL DO BRIGADISTA - PCI; fallback para SUAREA."""
    if has_text(row.get(COL_LOCAL_PCI)):
        return row[COL_LOCAL_PCI]
    if has_text(row.get(COL_SUAREA)):
        return row[COL_SUAREA]
    return pd.NA


def ensure_directories() -> None:
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def resolve_input(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    return KNOWLEDGE_BASE_DIR / CONTROLE_GERAL_FILE


def resolve_output(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    return OUTPUTS_DIR / OUTPUT_FILE


def load_excel(path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    return pd.read_excel(path, sheet_name=sheet_name, engine="openpyxl")


def load_controle_geral(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega as abas de colaboradores e cronograma do arquivo único."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    workbook = pd.ExcelFile(path, engine="openpyxl")
    missing = [s for s in (SHEET_CONTROLE_NOMINAL, SHEET_CRONOGRAMA) if s not in workbook.sheet_names]
    if missing:
        abas = ", ".join(workbook.sheet_names)
        raise ValueError(
            f"Abas ausentes em '{path.name}': {', '.join(missing)}. "
            f"Abas encontradas: {abas}"
        )

    controle = pd.read_excel(workbook, sheet_name=SHEET_CONTROLE_NOMINAL)
    cronograma = pd.read_excel(workbook, sheet_name=SHEET_CRONOGRAMA)
    return controle, cronograma


def save_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name, index=False)


def parse_date(value: object) -> pd.Timestamp | pd.NaT:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return pd.NaT
    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    return parsed


def reference_tomorrow(data_referencia: pd.Timestamp | None = None) -> pd.Timestamp:
    """Retorna a data de amanhã (início do dia) em relação à data de referência."""
    base = data_referencia if data_referencia is not None else pd.Timestamp.today()
    return base.normalize() + pd.Timedelta(days=1)
