# 🧮 Detecção de Discrepâncias de Estoque

Este projeto tem como objetivo **detectar discrepâncias de estoque** com base em dados de **compras, vendas e inventário físico**.  
A aplicação conta com uma **interface gráfica intuitiva (Tkinter)** que permite ao usuário importar planilhas, executar as análises e visualizar os resultados de forma clara e acessível.

---

## 🚀 Funcionalidades

- **Importação de dados** de compras, vendas e estoque (CSV ou Excel).
- **Detecção automática de discrepâncias**, com base nas movimentações e histórico de estoque.
- **Relatórios detalhados** com:
  - Estoque anterior e atual  
  - Quantidades compradas e vendidas  
  - Diferença e tipo de discrepância  
  - Sugestões automáticas de correção
- **Interface gráfica moderna** com suporte a:
  - Tema claro/escuro  
  - Tabelas roláveis e ajustáveis  
  - Validação de entradas  
  - Mensagens de erro e sucesso  
  - Atalhos de teclado  
  - Layout responsivo básico

---

## 🧩 Estrutura do Projeto

```
📦 projeto_discrepancias
 ┣ 📂 data
 ┃ ┗ 📄 dados_teste.xlsx          # Planilha exemplo com três abas (compras, vendas, estoque)
 ┣ 📂 modules
 ┃ ┣ 📄 logic.py                  # Contém a lógica principal (detect_discrepancies e helpers)
 ┃ ┣ 📄 ui_main.py                # Interface Tkinter principal
 ┃ ┗ 📄 utils.py                  # Funções auxiliares (ex: carregar arquivos, mensagens)
 ┣ 📄 main.py                     # Ponto de entrada da aplicação
 ┣ 📄 README.md                   # Este arquivo
 ┗ 📄 requirements.txt            # Dependências do projeto
```

---

## ⚙️ Requisitos

- Python 3.9+
- Dependências (instale via pip):

```bash
pip install pandas numpy openpyxl
```

> O Tkinter já vem incluído na maioria das instalações do Python.

---

## ▶️ Execução

1. **Clone o repositório** ou copie os arquivos do projeto.
2. Certifique-se de ter os arquivos de dados (`dados_teste.xlsx` ou CSVs equivalentes).
3. Execute o programa principal:

```bash
python main.py
```

A interface gráfica será aberta, permitindo carregar os arquivos e executar a análise.

---

## 🧠 Como Usar

1. **Selecione os arquivos** de compras, vendas e estoque.  
   - Suporte a `.csv` e `.xlsx` (planilhas com abas nomeadas `compras`, `vendas`, `estoque`).
2. **Defina a tolerância** (diferença aceitável entre o estoque esperado e o informado).
3. **Clique em "Detectar Discrepâncias"**.
4. Visualize os resultados diretamente na tabela da interface.
5. Opcionalmente, **exporte o relatório** para CSV/Excel.

---

## 🧾 Testes Manuais (Simples)

1. **Carregar dados de exemplo** (`dados_teste.xlsx`).  
2. **Executar a detecção** com tolerância = 2.  
3. **Verificar saída esperada**: discrepâncias listadas com colunas  
   `produto`, `data`, `diferenca`, `tipo_discrepancia`, `sugestao`.

### ✅ Critérios de Aceitação
- A interface deve permitir carregar os três arquivos sem erro.  
- Ao clicar em "Detectar Discrepâncias", deve exibir uma tabela com os resultados.  
- Mensagens de erro devem ser exibidas para arquivos ausentes ou formato incorreto.

---

## 🧑‍💻 Autor

**Filipe Fonseca**  
Analista de Sistemas Computacionais  
Especialista em Python, Interface Design e Automação de Processos.

---

## 📄 Licença

Este projeto é de uso livre para fins educacionais e profissionais, mediante citação do autor.

---
