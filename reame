Como sou um modelo de inteligência artificial, não consigo forçar o download direto de um arquivo para a sua máquina. No entanto, gerei o conteúdo completo e formatado abaixo.

Você só precisa criar um arquivo chamado `DEVELOPMENT.md` (ou `README.md`) na raiz do seu projeto e colar o bloco de texto a seguir. Este documento foi escrito com foco estrito em **engenharia e desenvolvimento**, servindo como um guia definitivo para qualquer desenvolvedor que vá assumir, manter ou escalar o código.

---

```markdown
# 🛠️ NR23 CLI Engine — Guia de Desenvolvimento

Este documento é destinado a engenheiros de software, cientistas de dados e desenvolvedores que atuarão na manutenção, extensão ou refatoração do **NR23 CLI Engine**. 

O sistema é um utilitário de interface de linha de comando (CLI) em Python focado em engenharia de dados. Ele executa o saneamento de dados de RH, processamento geoespacial em memória e aplicação de algoritmos de roteirização e regras rígidas de capacidade (min/max) para enturmação em treinamentos normativos.

---

## 🏗️ Arquitetura do Sistema

O projeto adota uma arquitetura de scripts modulares (ETL/CLI), separando a camada de apresentação no terminal da lógica de negócios e dos cálculos matemáticos/geográficos. 

O banco de dados é substituído por manipulação direta de arquivos no File System local (`knowledge-base/` para _Input_ e `outputs/` para _Output_), utilizando o motor vetorial do Pandas para garantir alta performance no processamento em memória.

### 🗂️ Árvore de Diretórios

```text
nr23-cli-engine/
│
├── knowledge-base/             # (Input) Planilhas originais em formato .xlsx
│   ├── nr23_controle_nominal.xlsx
│   └── cronograma_turmas.xlsx
│
├── outputs/                    # (Output) Artefatos processados pelo engine
│   └── NR23_SANEADO_2026.xlsx
│
├── src/                        # Código-fonte principal
│   ├── __init__.py
│   ├── main.py                 # Camada de Apresentação CLI (Rotas do Typer)
│   ├── engine.py               # Core Domain (Regras de negócio e Pandas ETL)
│   ├── geo.py                  # Cálculos de Haversine e Dicionários de Coordenadas
│   └── utils.py                # Helpers (I/O de arquivos, sanitização de strings)
│
├── .gitignore                  # Ignorar outputs/, knowledge-base/ (se sensível) e venv
├── requirements.txt            # Dependências fixadas do projeto
└── DEVELOPMENT.md              # Este documento

```

---

## 💻 Setup do Ambiente de Desenvolvimento

Para garantir a paridade de ambiente, utilize o Python 3.11 ou superior e isole as dependências em um ambiente virtual.

**1. Clonar e preparar o ambiente virtual:**

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/MacOS
source venv/bin/activate

```

**2. Instalar dependências:**

```bash
pip install -r requirements.txt

```

> **Nota sobre Dependências Principais:**
> * `pandas` & `openpyxl`: Motor principal de ETL.
> * `geopy`: Responsável pela métrica de distância `geodesic` (Haversine).
> * `typer` & `rich`: Frameworks de CLI. O Typer lida com o parse de argumentos e o Rich provê a interface visual (cores, tabelas, progress bars).
> 
> 

---

## 🧠 Core Domain: Regras de Negócio Estritas

Ao alterar o arquivo `src/engine.py`, você deve respeitar o seguinte pipeline de estado da máquina:

### 1. Limites de Capacidade (Hard Limits)

Nenhuma turma pode ser salva com o estado `OK` ou `PLANEJAR DATA` se não respeitar a restrição matemática:

* **Min:** 10 colaboradores vinculados.
* **Max:** 20 colaboradores vinculados.

### 2. Mutação de Status de Ocupação

O algoritmo deve atualizar as turmas *in-place* na memória baseando-se na contagem exata (Count) de vínculos associados ao `CÓDIGO DA TURMA`.

| Vínculos Reais | Status da Turma | Ação Recomendada |
| --- | --- | --- |
| **0** | `SEM PARTICIPANTES` | Cancelar Turma ou Remanejar Demanda |
| **1 a 9** | `ABAIXO DO MÍNIMO` | Consolidar ou Convidar Colaboradores |
| **10 a 20** | `OK` (se houver data) ou `PLANEJAR DATA` | Manter Cronograma ou Definir Data |
| **> 20** | `ACIMA DO LIMITE` | Dividir Excedente |

### 3. Mecanismo de Fallback Geográfico (`src/geo.py`)

A vinculação tenta primeiramente um *match exato* na localidade. Se falhar, calcula a distância em linha reta (Haversine) baseada em latitude/longitude.

* **Parâmetro dinâmico:** O `--raio-max` é injetado via CLI (padrão 50km).
* **Atenção:** Se adicionar novas localidades à base de dados da empresa, é estritamente necessário atualizar o dicionário de coordenadas no módulo `geo.py`.

---

## 🚀 Padrões de Extensão e Contribuição

### Adicionando Novos Comandos na CLI

A CLI é gerenciada pelo Typer em `src/main.py`. Para registrar uma nova rotina (ex: gerar um relatório analítico separado), adicione o decorator `@app.command()`:

```python
@app.command()
def gerar_relatorio_cidades():
    """Gera um heatmap de colaboradores por cidade."""
    console.print("[cyan]Processando relatório espacial...[/cyan]")
    # Inserir lógica de integração com o engine.py

```

### Lidando com DataFrames do Pandas

* **Não itere linhas a menos que seja estritamente necessário:** O loop `.iterrows()` é custoso. Onde for possível, prefira filtros vetoriais do Pandas. No entanto, para o cálculo de capacidade que diminui em tempo real (estado compartilhado iterativo), o loop atual em `engine.py` é a solução de engenharia aceitável, dado que a volumetria de planilhas locais costuma ser menor que o limite de gargalo da CPU.
* **Manejo de NaNs:** Atenção redobrada ao comparar localidades (strings) que podem vir como `NaN` do Excel. Utilize `pd.notna()` antes de injetar nas funções de sanitização.

### Manutenção da Auditoria

Toda alteração que envolver exclusão ou mudança massiva de dados deve gerar registros nas abas analíticas geradas no output final (`SANEAMENTO_TURMAS_NR23` e `PENDENTES_DIMENSIONAMENTO_NR23`). Estas abas são a principal forma de depuração (debug visual) da liderança de RH.

---

## 🧪 Validações de Fluxo (Sanity Checks)

Antes de fazer o push de uma alteração significativa, rode o script localmente num dataset de testes garantindo que:

1. Nenhum código de turma existente anterior a `12/06/2026` foi sobrescrito (preservação histórica).
2. O total de colaboradores no `.xlsx` de entrada é exatamente igual à soma de: `(colaboradores vinculados)` + `(colaboradores pendentes)` no arquivo gerado no output. Não pode haver sumiço de IDs.

```

```
