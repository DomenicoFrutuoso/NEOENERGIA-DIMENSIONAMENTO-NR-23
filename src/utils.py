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

# Aba Cronograma de Turmas (nomes canônicos após normalização)
COL_CODIGO_TURMA = "CÓDIGO DA TURMA"
COL_TURMA_LOCALIDADE = "TURMA /LOCALIDADE"
COL_STATUS_TURMA = "STATUS DA TURMA"
COL_DATA_TURMA = "DATA"
COL_ACAO_RECOMENDADA = "AÇÃO RECOMENDADA"
COL_VINCULOS = "VÍNCULOS REAIS"
COL_MOTIVO_PENDENCIA = "MOTIVO PENDÊNCIA"
COL_LOCALIDADE_USADA = "LOCALIDADE USADA"

# Aliases reais da planilha Controle Geral_NR23
CRONOGRAMA_CODIGO_ALIASES = ("CÓDIGO DA TURMA", "NR")
CRONOGRAMA_DATA_ALIASES = ("DATA INÍCIO", "DATA INICIO", "DATA")
CRONOGRAMA_LOCALIDADE_ALIASES = ("TURMA /LOCALIDADE", "TURMA/LOCALIDADE")
CRONOGRAMA_STATUS_ALIASES = ("STATUS DA TURMA",)

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


def strip_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Remove espaços extras dos cabeçalhos e descarta colunas sem nome."""
    frame = df.copy()
    new_cols: list[str] = []
    for i, col in enumerate(frame.columns):
        name = str(col).strip() if pd.notna(col) else ""
        if not name or name.lower().startswith("unnamed"):
            name = f"_DROP_{i}"
        new_cols.append(name)
    frame.columns = new_cols
    drop_cols = [c for c in frame.columns if c.startswith("_DROP_")]
    return frame.drop(columns=drop_cols, errors="ignore")


def resolve_column(df: pd.DataFrame, candidates: tuple[str, ...], *, context: str) -> str:
    """Localiza coluna por nome exato ou normalizado (sem acentos/caixa)."""
    exact = {str(col).strip(): col for col in df.columns}
    for candidate in candidates:
        if candidate in exact:
            return candidate
    normalized = {sanitize_string(col): str(col).strip() for col in df.columns}
    for candidate in candidates:
        key = sanitize_string(candidate)
        if key in normalized:
            return normalized[key]
    disponiveis = ", ".join(str(c) for c in df.columns)
    raise ValueError(
        f"Coluna obrigatória ausente em {context}. "
        f"Esperada uma de: {', '.join(candidates)}. "
        f"Colunas encontradas: {disponiveis}"
    )


def normalize_cronograma(df: pd.DataFrame) -> pd.DataFrame:
    """Mapeia colunas reais do cronograma para os nomes canônicos do engine."""
    frame = strip_column_names(df)
    rename_map = {
        resolve_column(frame, CRONOGRAMA_CODIGO_ALIASES, context="Cronograma de Turmas"): COL_CODIGO_TURMA,
        resolve_column(frame, CRONOGRAMA_LOCALIDADE_ALIASES, context="Cronograma de Turmas"): COL_TURMA_LOCALIDADE,
        resolve_column(frame, CRONOGRAMA_STATUS_ALIASES, context="Cronograma de Turmas"): COL_STATUS_TURMA,
    }
    try:
        data_col = resolve_column(frame, CRONOGRAMA_DATA_ALIASES, context="Cronograma de Turmas")
        rename_map[data_col] = COL_DATA_TURMA
    except ValueError:
        pass
    return frame.rename(columns=rename_map)


def normalize_controle_nominal(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza cabeçalhos da aba de colaboradores."""
    frame = strip_column_names(df)
    resolve_column(frame, (COL_NOME_COMPLETO,), context="NR23 Controle Nominal")
    if sanitize_string(COL_CODIGO_TURMA_NOMINAL) not in {sanitize_string(c) for c in frame.columns}:
        raise ValueError(
            f"Coluna obrigatória ausente em NR23 Controle Nominal: {COL_CODIGO_TURMA_NOMINAL}"
        )
    # Renomeia para o nome canônico se vier com variação de espaço/acento
    for col in frame.columns:
        if sanitize_string(col) == sanitize_string(COL_CODIGO_TURMA_NOMINAL) and col != COL_CODIGO_TURMA_NOMINAL:
            frame = frame.rename(columns={col: COL_CODIGO_TURMA_NOMINAL})
    return frame


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

    controle = normalize_controle_nominal(pd.read_excel(workbook, sheet_name=SHEET_CONTROLE_NOMINAL))
    cronograma = normalize_cronograma(pd.read_excel(workbook, sheet_name=SHEET_CRONOGRAMA))
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
