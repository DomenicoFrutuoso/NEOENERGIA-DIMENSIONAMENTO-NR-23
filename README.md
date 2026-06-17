# NR23 CLI Engine

Utilitário de linha de comando (CLI) em Python para saneamento de dados de RH, processamento geoespacial em memória e dimensionamento de turmas de treinamento normativo (NR-23).

O sistema lê planilhas Excel da pasta `knowledge-base/`, aplica regras de capacidade e vinculação geográfica, e gera um arquivo consolidado em `outputs/`.

---

## Requisitos

- Python 3.11 ou superior
- Dependências listadas em `requirements.txt`

---

## Instalação

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### Dependências principais

| Pacote | Função |
| --- | --- |
| `pandas` + `openpyxl` | ETL e leitura/escrita de planilhas |
| `geopy` | Distância geodésica (Haversine) entre localidades |
| `typer` + `rich` | Interface CLI com tabelas e formatação |

---

## Uso rápido

### 1. Preparar o arquivo de entrada

Coloque o arquivo em `knowledge-base/`:

- **`Controle Geral_NR23.xlsx`** — arquivo único com duas abas:
  - `NR23 Controle Nominal` — colaboradores
  - `Cronograma de Turmas` — turmas

Para gerar dados de exemplo para testes locais:

```bash
python scripts/generate_sample_data.py
```

### 2. Executar o saneamento

```bash
python -m src.main saneamento
```

### 3. Opções disponíveis

```bash
# Alterar raio máximo de vinculação geográfica (padrão: 50 km)
python -m src.main saneamento --raio-max 80

# Caminho alternativo do arquivo de entrada
python -m src.main saneamento --arquivo "caminho\Controle Geral_NR23.xlsx" --output "caminho\saida.xlsx"

# Ver informações do engine
python -m src.main info
```

### 4. Saída gerada

O arquivo `outputs/NR23_SANEADO_2026.xlsx` contém as abas:

| Aba | Conteúdo |
| --- | --- |
| `NR23 Controle Nominal` | Colaboradores com `NR 23 CÓDIGO DA TURMA` preenchido |
| `Cronograma de Turmas` | Turmas com status e contagem de vínculos |
| `SANEAMENTO_TURMAS_NR23` | Auditoria de turmas (debug para RH) |
| `VINCULACOES_REALIZADAS` | Log de cada vinculação (método e distância) |
| `PENDENTES_DIMENSIONAMENTO_NR23` | Colaboradores sem turma atribuída |

---

## Formato do arquivo de entrada

### `Controle Geral_NR23.xlsx`

#### Aba `NR23 Controle Nominal`

| Coluna | Obrigatória | Descrição |
| --- | --- | --- |
| `NOME COMPLETO` | Sim | Nome do colaborador |
| `NR 23 CÓDIGO DA TURMA` | Sim | Vazio = será dimensionado pelo engine |
| `LOCAL DO BRIGADISTA - PCI` | Não* | Localidade principal para vinculação |
| `SUAREA` | Não* | Usada quando PCI estiver vazio |

\* Pelo menos uma das colunas de localidade deve estar preenchida.

#### Aba `Cronograma de Turmas`

| Coluna | Obrigatória | Descrição |
| --- | --- | --- |
| `NR` | Sim | Código da turma (equivalente a CÓDIGO DA TURMA) |
| `TURMA /LOCALIDADE` | Sim | Localidade da turma (match geográfico) |
| `DATA INÍCIO` | Não | Data de início do treinamento |
| `STATUS DA TURMA` | Sim | Apenas `AGENDADO` recebe novos vínculos |

---

## Regras de negócio

### Limites de capacidade

Nenhuma turma recebe status `OK` ou `PLANEJAR DATA` fora da faixa permitida:

- **Mínimo:** 10 colaboradores vinculados
- **Máximo:** 20 colaboradores vinculados

### Status das turmas

O status é calculado com base na contagem exata de vínculos por `CÓDIGO DA TURMA`:

| Vínculos | Status | Ação recomendada |
| --- | --- | --- |
| 0 | `SEM PARTICIPANTES` | Cancelar turma ou remanejar demanda |
| 1 a 9 | `ABAIXO DO MÍNIMO` | Consolidar ou convidar colaboradores |
| 10 a 20 | `OK` (com data) ou `PLANEJAR DATA` (sem data) | Manter cronograma ou definir data |
| > 20 | `ACIMA DO LIMITE` | Dividir excedente |

### Localidade do colaborador

1. Usa `LOCAL DO BRIGADISTA - PCI` quando preenchido
2. Se PCI estiver vazio, usa `SUAREA`
3. Correlaciona com `TURMA /LOCALIDADE` do cronograma (match exato ou proximidade geográfica)

### Vinculação geográfica

O algoritmo avalia **todas as turmas elegíveis** e seleciona aquela cuja localidade está **geograficamente mais próxima** do colaborador:

1. Calcula a distância geodésica (Haversine) entre a localidade do colaborador e a de cada turma candidata
2. Filtra turmas dentro do raio máximo (`--raio-max`, padrão 50 km)
3. Escolhe a turma com **menor distância**; em empate, prioriza a de menor ocupação atual
4. Match na mesma cidade resulta em distância 0 km (`MATCH EXATO`); demais casos são `PROXIMIDADE`

### Filtro de data das turmas

Colaboradores só são vinculados a turmas **futuras**:

- **Elegíveis:** data >= amanhã (em relação à data de execução) ou sem data definida (em planejamento)
- **Excluídas:** turmas com data de hoje, ontem ou qualquer data passada

### Filtro de status das turmas

Colaboradores só são vinculados a turmas cujo `STATUS DA TURMA` na planilha de entrada é **`AGENDADO`**.

Turmas com qualquer outro status (ex.: `OK`, `PLANEJAR DATA`, `CANCELADO`) são ignoradas no dimensionamento.

Turmas com data anterior a **12/06/2026** também são preservadas historicamente e não recebem novos vínculos.

### Conservação de dados

O total de colaboradores na entrada deve ser igual a:

```
vinculados + pendentes = total de entrada
```

Nenhum ID pode desaparecer no processamento.

---

## Arquitetura

```text
NEOENERGIA-DIMENSIONAMENTO-NR-23/
│
├── knowledge-base/             # Entrada
│   └── Controle Geral_NR23.xlsx  # Abas: NR23 Controle Nominal + Cronograma de Turmas
│
├── outputs/                    # Saída — artefatos processados
│   └── NR23_SANEADO_2026.xlsx
│
├── scripts/
│   └── generate_sample_data.py # Gera planilhas de exemplo
│
├── src/
│   ├── main.py                 # CLI (Typer)
│   ├── engine.py               # Regras de negócio e ETL
│   ├── geo.py                  # Coordenadas e distância geodésica
│   └── utils.py                # I/O, sanitização e constantes
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

O processamento é feito inteiramente em memória com Pandas — não há banco de dados. A camada CLI (`main.py`) é separada da lógica de domínio (`engine.py`) e dos cálculos geográficos (`geo.py`).

---

## Desenvolvimento

### Adicionar novos comandos CLI

Registre novos comandos em `src/main.py` com o decorator `@app.command()`:

```python
@app.command()
def gerar_relatorio_cidades():
    """Gera um heatmap de colaboradores por cidade."""
    console.print("[cyan]Processando relatório espacial...[/cyan]")
    # Integrar com engine.py
```

### Adicionar localidades

Ao incluir novas cidades na base da empresa, atualize o dicionário `COORDENADAS` em `src/geo.py`:

```python
COORDENADAS = {
    "NOVA CIDADE": (-12.0000, -38.0000),
    # ...
}
```

### Boas práticas com Pandas

- Prefira operações vetoriais a `.iterrows()` sempre que possível
- O loop iterativo em `engine.py` é intencional: a capacidade das turmas muda a cada vinculação
- Use `pd.notna()` antes de comparar localidades que podem vir como `NaN` do Excel

### Validações antes de commit

Execute localmente com um dataset de testes e verifique:

1. Turmas anteriores a `12/06/2026` não tiveram vínculos alterados
2. A conservação de colaboradores está correta (entrada = vinculados + pendentes)
3. Nenhuma turma com status `OK` ou `PLANEJAR DATA` está fora da faixa 10–20 vínculos

```bash
python scripts/generate_sample_data.py
python -m src.main saneamento
```
