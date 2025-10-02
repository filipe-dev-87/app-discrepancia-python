# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import pandas as pd
import logging
from dataclasses import dataclass
from typing import Optional
import sys
import csv
import io

# --- Mantive a lógica original exatamente como fornecida ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("consistencia")

@dataclass
class Discrepancy:
    produto: str
    data: pd.Timestamp
    estoque_anterior: Optional[int]
    compras: int
    vendas: int
    estoque_atual: Optional[int]
    estoque_esperado: Optional[int]
    diferenca: Optional[int]
    tipo: str
    sugestao: str

def _ensure_df(df, cols, date_col='data'):
    """Valida/normaliza DataFrame: garante colunas e tipos."""
    if df is None:
        return pd.DataFrame(columns=cols)
    df = df.copy()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        raise ValueError(f"Coluna de data '{date_col}' não encontrada no DataFrame")
    for c in cols:
        if c not in df.columns:
            df[c] = 0 if c != date_col else pd.NaT
    return df[cols]

def detect_discrepancies(compras_df, vendas_df, estoque_df, tolerance=0):
    """
    Detecta discrepâncias entre Compras, Vendas e Estoque.
    Retorna DataFrame com colunas de relatório.
    """
    # Normalizar
    compras = _ensure_df(compras_df, ['data','produto','quantidade_comprada'])
    vendas = _ensure_df(vendas_df, ['data','produto','quantidade_vendida'])
    estoque = _ensure_df(estoque_df, ['data','produto','quantidade_em_estoque'])

    # Somar movimentos por dia/produto
    compras_agg = compras.groupby(['produto','data'], as_index=False).quantidade_comprada.sum()
    vendas_agg = vendas.groupby(['produto','data'], as_index=False).quantidade_vendida.sum()
    estoque_agg = estoque.groupby(['produto','data'], as_index=False).quantidade_em_estoque.sum()

    produtos = sorted(set(compras_agg['produto']).union(vendas_agg['produto']).union(estoque_agg['produto']))
    logger.info(f"Produtos encontrados: {produtos}")

    discrepancias = []

    for prod in produtos:
        dates = sorted(set(
            compras_agg.loc[compras_agg['produto']==prod,'data'].tolist() +
            vendas_agg.loc[vendas_agg['produto']==prod,'data'].tolist() +
            estoque_agg.loc[estoque_agg['produto']==prod,'data'].tolist()
        ))
        prev_stock = None

        for d in dates:
            c = int(compras_agg.loc[(compras_agg['produto']==prod) & (compras_agg['data']==d),'quantidade_comprada'].sum()) if not compras_agg.empty else 0
            v = int(vendas_agg.loc[(vendas_agg['produto']==prod) & (vendas_agg['data']==d),'quantidade_vendida'].sum()) if not vendas_agg.empty else 0
            estoque_rows = estoque_agg.loc[(estoque_agg['produto']==prod) & (estoque_agg['data']==d),'quantidade_em_estoque']
            atual = int(estoque_rows.iloc[0]) if not estoque_rows.empty else None

            if prev_stock is None:
                if atual is not None:
                    prev_stock = atual
                    expected = prev_stock + c - v
                    diff = None
                    tipo = 'baseline'
                    sugestao = 'Registrar histórico anterior de estoque para validação.'
                    if c!=0 or v!=0 and abs(atual - expected) > tolerance:
                        if atual - expected > 0 and c==0:
                            tipo = 'falta_registro_compra'
                            sugestao = f'Sugerir adicionar compra de {atual - expected} unidades.'
                        elif atual - expected < 0 and v==0:
                            tipo = 'falta_registro_venda'
                            sugestao = f'Sugerir adicionar venda de {- (atual - expected)} unidades.'
                        else:
                            tipo = 'erro_lancamento_estoque'
                            sugestao = 'Revisar lançamento de estoque ou registros do dia.'
                        discrepancias.append(Discrepancy(prod, d, prev_stock, c, v, atual, expected, atual - expected, tipo, sugestao))
                    continue
                else:
                    tipo = 'sem_baseline'
                    sugestao = 'Não há registro de estoque inicial para validar.'
                    discrepancias.append(Discrepancy(prod, d, None, c, v, None, None, None, tipo, sugestao))
                    continue

            expected = prev_stock + c - v
            diff = None if atual is None else (atual - expected)

            if atual is None:
                tipo = 'estoque_nao_informado'
                sugestao = 'Registro de estoque ausente.'
                discrepancias.append(Discrepancy(prod, d, prev_stock, c, v, None, expected, None, tipo, sugestao))
                continue

            if abs(diff) <= tolerance:
                prev_stock = atual
                continue

            if diff > 0:
                if c == 0:
                    tipo = 'falta_registro_compra'
                    sugestao = f'Adicionar compra de {diff} unidades ou ajustar estoque para {expected}.'
                else:
                    tipo = 'erro_lancamento_estoque'
                    sugestao = f'Revisar lançamento de estoque (diferenca +{diff}) e validar compras.'
            else:
                if v == 0:
                    tipo = 'falta_registro_venda'
                    sugestao = f'Adicionar venda de {-diff} unidades ou ajustar estoque para {expected}.'
                else:
                    tipo = 'erro_lancamento_estoque'
                    sugestao = f'Revisar lançamento de estoque (diferenca {diff}) e validar vendas.'
            discrepancias.append(Discrepancy(prod, d, prev_stock, c, v, atual, expected, diff, tipo, sugestao))
            prev_stock = atual

    report = pd.DataFrame([{
        'produto': x.produto,
        'data': x.data,
        'estoque_anterior': x.estoque_anterior,
        'compras': x.compras,
        'vendas': x.vendas,
        'estoque_atual': x.estoque_atual,
        'estoque_esperado': x.estoque_esperado,
        'diferenca': x.diferenca,
        'tipo_discrepancia': x.tipo,
        'sugestao': x.sugestao
    } for x in discrepancias])

    if not report.empty:
        report = report.sort_values(['produto','data']).reset_index(drop=True)
    return report

# ----------------- Fim da lógica original -----------------


# --- UI aprimorada para visualização elegante ---
class StockValidatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Validador de Estoque — Visualização Aprimorada")
        self.geometry("1200x700")
        self.minsize(1000, 600)

        # Tema
        self.themes = {
            "light": {
                "bg": "#f5f7fb",
                "frame": "#ffffff",
                "accent": "#2b7a78",
                "text": "#111111",
                "muted": "#666666",
                "zebra1": "#ffffff",
                "zebra2": "#f2f4f7",
            },
            "dark": {
                "bg": "#181a1b",
                "frame": "#242627",
                "accent": "#7aa2f7",
                "text": "#e8eefc",
                "muted": "#bfc6d6",
                "zebra1": "#232526",
                "zebra2": "#1e1f20",
            },
        }
        self.current_theme = "light"
        self.style = ttk.Style(self)
        self.configure(bg=self.themes[self.current_theme]["bg"])

        # Dados
        self.compras_df = None
        self.vendas_df = None
        self.estoque_df = None
        self.report_df = pd.DataFrame()

        self._build_ui()
        self._bind_shortcuts()
        self.apply_theme()  # aplica cores iniciais

    def _build_ui(self):
        # Top frame for controls
        top = tk.Frame(self, bg=self.themes[self.current_theme]["bg"])
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10,5))

        # Left controls (file selectors and tolerance)
        left_ctrl = tk.Frame(top, bg=self.themes[self.current_theme]["bg"])
        left_ctrl.pack(side=tk.LEFT, anchor='n')

        # File selectors
        def make_file_row(parent, label_text, setter):
            row = tk.Frame(parent, bg=self.themes[self.current_theme]["bg"])
            row.pack(fill=tk.X, pady=2)
            lbl = tk.Label(row, text=label_text, bg=self.themes[self.current_theme]["bg"])
            lbl.pack(side=tk.LEFT, padx=(0,6))
            entry = tk.Entry(row, width=40)
            entry.pack(side=tk.LEFT, padx=(0,6))
            btn = tk.Button(row, text="Selecionar", command=lambda e=entry, s=setter: s(e))
            btn.pack(side=tk.LEFT)
            return entry

        self.entry_compras = make_file_row(left_ctrl, "Compras (CSV):", self._load_compras_from_entry)
        self.entry_vendas  = make_file_row(left_ctrl, "Vendas (CSV):", self._load_vendas_from_entry)
        self.entry_estoque = make_file_row(left_ctrl, "Estoque (CSV):", self._load_estoque_from_entry)

        # tolerance and buttons
        row_tol = tk.Frame(left_ctrl, bg=self.themes[self.current_theme]["bg"])
        row_tol.pack(fill=tk.X, pady=(6,2))
        tk.Label(row_tol, text="Tolerância:", bg=self.themes[self.current_theme]["bg"]).pack(side=tk.LEFT)
        self.entry_tolerance = tk.Entry(row_tol, width=8)
        self.entry_tolerance.insert(0, "0")
        self.entry_tolerance.pack(side=tk.LEFT, padx=(6,10))

        btn_generate = tk.Button(row_tol, text="Gerar Relatório (Ctrl+G)", command=self.generate_report, bg="#2b7a78", fg="white")
        btn_generate.pack(side=tk.LEFT, padx=5)
        btn_export = tk.Button(row_tol, text="Exportar CSV (Ctrl+E)", command=self.export_report)
        btn_export.pack(side=tk.LEFT, padx=5)
        btn_theme = tk.Button(row_tol, text="Alternar Tema (Ctrl+T)", command=self.toggle_theme)
        btn_theme.pack(side=tk.LEFT, padx=5)

        # Center area: filters + summary
        center_ctrl = tk.Frame(top, bg=self.themes[self.current_theme]["bg"])
        center_ctrl.pack(side=tk.LEFT, padx=20, anchor='n')

        # Search
        search_row = tk.Frame(center_ctrl, bg=self.themes[self.current_theme]["bg"])
        search_row.pack(fill=tk.X)
        tk.Label(search_row, text="Busca rápida:", bg=self.themes[self.current_theme]["bg"]).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.entry_search = tk.Entry(search_row, textvariable=self.search_var, width=30)
        self.entry_search.pack(side=tk.LEFT, padx=(6,6))
        self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters())
        tk.Label(search_row, text=" (produto / sugestão / tipo)", bg=self.themes[self.current_theme]["bg"], fg=self.themes[self.current_theme]["muted"]).pack(side=tk.LEFT)

        # Filters
        filter_row = tk.Frame(center_ctrl, bg=self.themes[self.current_theme]["bg"])
        filter_row.pack(fill=tk.X, pady=(6,0))
        tk.Label(filter_row, text="Produto:", bg=self.themes[self.current_theme]["bg"]).pack(side=tk.LEFT)
        self.produto_filter = ttk.Combobox(filter_row, values=[], state="readonly", width=20)
        self.produto_filter.pack(side=tk.LEFT, padx=6)
        self.produto_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        tk.Label(filter_row, text="Tipo:", bg=self.themes[self.current_theme]["bg"]).pack(side=tk.LEFT)
        self.tipo_filter = ttk.Combobox(filter_row, values=[], state="readonly", width=25)
        self.tipo_filter.pack(side=tk.LEFT, padx=6)
        self.tipo_filter.bind("<<ComboboxSelected>>", lambda e: self.apply_filters())

        # Summary
        self.summary_lbl = tk.Label(center_ctrl, text="Resumo: —", bg=self.themes[self.current_theme]["bg"])
        self.summary_lbl.pack(anchor='w', pady=(6,0))

        # Right: treeview + detail panel (split)
        right_frame = tk.Frame(self, bg=self.themes[self.current_theme]["bg"])
        right_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(4,10))

        # Treeview frame
        tree_frame = tk.Frame(right_frame, bg=self.themes[self.current_theme]["bg"])
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        cols = ("produto","data","estoque_anterior","compras","vendas","estoque_atual","estoque_esperado","diferenca","tipo_discrepancia","sugestao")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode='browse')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, anchor="center")
        # scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Bind selection
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_full_suggestion())

        # Detail / suggestion panel
        detail_frame = tk.Frame(right_frame, height=180, bg=self.themes[self.current_theme]["frame"])
        detail_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(8,0))
        detail_frame.pack_propagate(False)

        # Detail labels
        self.detail_text = tk.Text(detail_frame, height=6, wrap='word', state='disabled')
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0), pady=6)
        # Scrolled suggestion (read-only)
        self.sugg_box = ScrolledText(detail_frame, width=50, height=6, wrap='word', state='disabled')
        self.sugg_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6,6), pady=6)

        # Footer status
        self.status = tk.Label(self, text="Pronto", anchor='w', bg=self.themes[self.current_theme]["bg"])
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # --- Loaders (com diálogo de arquivo) ---
    def _load_compras_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path)
                self.compras_df = df
                self.status['text'] = f"Compras carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Compras: {e}")

    def _load_vendas_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path)
                self.vendas_df = df
                self.status['text'] = f"Vendas carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Vendas: {e}")

    def _load_estoque_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path)
                self.estoque_df = df
                self.status['text'] = f"Estoque carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Estoque: {e}")

    # --- Geração de relatório e preenchimento da tabela ---
    def generate_report(self, event=None):
        # valida tolerância
        try:
            tolerance = int(self.entry_tolerance.get())
        except Exception:
            messagebox.showerror("Erro", "Tolerância inválida. Insira um número inteiro.")
            return

        # se faltar arquivo, oferecer dados de exemplo
        if self.compras_df is None or self.vendas_df is None or self.estoque_df is None:
            r = messagebox.askyesno("Dados ausentes", "Alguns arquivos não foram informados. Usar dados de exemplo?")
            if r:
                compras_ex = pd.DataFrame([
                    {'data':'2025-09-01','produto':'Parafuso','quantidade_comprada':100},
                    {'data':'2025-09-03','produto':'Parafuso','quantidade_comprada':20},
                    {'data':'2025-09-02','produto':'Porca','quantidade_comprada':50},
                ])
                vendas_ex = pd.DataFrame([
                    {'data':'2025-09-02','produto':'Parafuso','quantidade_vendida':10},
                    {'data':'2025-09-03','produto':'Parafuso','quantidade_vendida':5},
                    {'data':'2025-09-04','produto':'Parafuso','quantidade_vendida':30},
                    {'data':'2025-09-03','produto':'Porca','quantidade_vendida':5},
                ])
                estoque_ex = pd.DataFrame([
                    {'data':'2025-09-01','produto':'Parafuso','quantidade_em_estoque':100},
                    {'data':'2025-09-03','produto':'Parafuso','quantidade_em_estoque':105},
                    {'data':'2025-09-04','produto':'Parafuso','quantidade_em_estoque':70},
                    {'data':'2025-09-02','produto':'Porca','quantidade_em_estoque':50},
                    {'data':'2025-09-03','produto':'Porca','quantidade_em_estoque':45},
                ])
                self.compras_df, self.vendas_df, self.estoque_df = compras_ex, vendas_ex, estoque_ex
            else:
                messagebox.showerror("Erro", "Forneça os 3 arquivos CSV ou aceite usar os dados de exemplo.")
                return

        # rodar a função fornecida (sem alteração de lógica)
        try:
            df = detect_discrepancies(self.compras_df, self.vendas_df, self.estoque_df, tolerance)
        except Exception as e:
            messagebox.showerror("Erro ao gerar relatório", str(e))
            return

        self.report_df = df.copy()
        self._refresh_filters()
        self._populate_tree(self.report_df)
        self.status['text'] = f"Relatório gerado: {len(self.report_df)} discrepâncias encontradas."

    def _refresh_filters(self):
        # atualiza listas de produtos e tipos
        prods = sorted(self.report_df['produto'].dropna().unique().tolist()) if not self.report_df.empty else []
        tipos = sorted(self.report_df['tipo_discrepancia'].dropna().unique().tolist()) if not self.report_df.empty else []
        self.produto_filter['values'] = ["(todos)"] + prods
        self.tipo_filter['values'] = ["(todos)"] + tipos
        self.produto_filter.set("(todos)")
        self.tipo_filter.set("(todos)")
        self._update_summary()

    def _update_summary(self):
        if self.report_df.empty:
            self.summary_lbl['text'] = "Resumo: nenhum registro."
            return
        counts = self.report_df['tipo_discrepancia'].value_counts().to_dict()
        parts = [f"{k}: {v}" for k, v in counts.items()]
        self.summary_lbl['text'] = "Resumo: " + " | ".join(parts)

    def _populate_tree(self, df):
        # limpar
        for r in self.tree.get_children():
            self.tree.delete(r)

        if df.empty:
            return

        # adicionar tags e cores baseadas em tipo
        # tags: falta_registro_compra (verde), falta_registro_venda (vermelho), erro_lancamento_estoque (amarelo), baseline/sem_baseline/estoque_nao_informado (cinza)
        for idx, row in df.iterrows():
            sug_preview = (row.sugestao[:80] + '...') if row.sugestao and len(row.sugestao) > 80 else (row.sugestao or '')
            vals = (row.produto, row.data.strftime('%Y-%m-%d'), row.estoque_anterior, row.compras, row.vendas, row.estoque_atual, row.estoque_esperado, row.diferenca, row.tipo_discrepancia, sug_preview)
            tag = self._tag_for_tipo(str(row.tipo_discrepancia))
            self.tree.insert("", "end", iid=str(idx), values=vals, tags=(tag,))

        # configurar estilo das tags (zebra + destaque)
        self._style_tree_tags()
        self._autosize_columns()

    def _tag_for_tipo(self, tipo):
        if tipo == 'falta_registro_compra':
            return 'tag_compra'
        if tipo == 'falta_registro_venda':
            return 'tag_venda'
        if tipo == 'erro_lancamento_estoque':
            return 'tag_erro'
        if tipo in ('baseline','sem_baseline','estoque_nao_informado'):
            return 'tag_info'
        return 'tag_default'

    def _style_tree_tags(self):
        # apply zebra background and tag colors
        theme = self.themes[self.current_theme]
        # zebra rows
        children = self.tree.get_children()
        for i, cid in enumerate(children):
            bg = theme['zebra1'] if i % 2 == 0 else theme['zebra2']
            self.tree.item(cid, tags=self.tree.item(cid, 'tags'))  # keep tags
            # unfortunately Treeview doesn't allow per-row background color through tags reliably cross-platform,
            # so we set tag configure centrally:
        # configure tag styles (ttk styling for Treeview doesn't directly style rows' bg in a simple cross-platform way,
        # but we can configure tag foreground)
        self.tree.tag_configure('tag_compra', foreground='#1b5e20')  # verde escuro
        self.tree.tag_configure('tag_venda', foreground='#b71c1c')   # vermelho
        self.tree.tag_configure('tag_erro', foreground='#e65100')    # laranja
        self.tree.tag_configure('tag_info', foreground='#37474f')    # cinza
        self.tree.tag_configure('tag_default', foreground=theme['muted'])

    def _autosize_columns(self):
        # ajusta largura das colunas baseado no conteúdo (estimativa)
        for col in self.tree['columns']:
            max_len = len(col)
            for iid in self.tree.get_children():
                val = str(self.tree.set(iid, col))
                if len(val) > max_len:
                    max_len = len(val)
            # heurística: ~8 pixels por caractere + padding
            width = min(max(80, max_len * 8 + 20), 500)
            self.tree.column(col, width=width)

    # --- seleção e detalhe ---
    def on_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            row = self.report_df.iloc[int(iid)]
        except Exception:
            # fallback se indices mudaram, procurar por valores
            vals = self.tree.item(iid, 'values')
            if not vals:
                return
            produto, data = vals[0], vals[1]
            mask = (self.report_df['produto'] == produto) & (self.report_df['data'].dt.strftime('%Y-%m-%d') == data)
            if not mask.any():
                return
            row = self.report_df.loc[mask].iloc[0]

        # atualizar painel de detalhes
        details = (
            f"Produto: {row.produto}\n"
            f"Data: {row.data.strftime('%Y-%m-%d')}\n"
            f"Estoque anterior: {row.estoque_anterior}\n"
            f"Compras: {row.compras}\n"
            f"Vendas: {row.vendas}\n"
            f"Estoque atual: {row.estoque_atual}\n"
            f"Estoque esperado: {row.estoque_esperado}\n"
            f"Diferença: {row.diferenca}\n"
            f"Tipo: {row.tipo_discrepancia}\n"
        )
        self.detail_text.config(state='normal')
        self.detail_text.delete('1.0', tk.END)
        self.detail_text.insert(tk.END, details)
        self.detail_text.config(state='disabled')

        self.sugg_box.config(state='normal')
        self.sugg_box.delete('1.0', tk.END)
        self.sugg_box.insert(tk.END, row.sugestao or "")
        self.sugg_box.config(state='disabled')

    def open_full_suggestion(self):
        # abre janela modal com texto completo da sugestão
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        try:
            row = self.report_df.iloc[int(iid)]
        except Exception:
            vals = self.tree.item(iid, 'values')
            produto, data = vals[0], vals[1]
            mask = (self.report_df['produto'] == produto) & (self.report_df['data'].dt.strftime('%Y-%m-%d') == data)
            row = self.report_df.loc[mask].iloc[0]

        top = tk.Toplevel(self)
        top.title("Sugestão completa")
        top.geometry("600x300")
        txt = ScrolledText(top, wrap='word')
        txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, row.sugestao or "")
        txt.config(state='disabled')

    # --- filtros e busca ---
    def apply_filters(self):
        if self.report_df.empty:
            return
        df = self.report_df.copy()
        q = self.search_var.get().strip().lower()
        prod = self.produto_filter.get()
        tipo = self.tipo_filter.get()
        if prod and prod != "(todos)":
            df = df[df['produto'] == prod]
        if tipo and tipo != "(todos)":
            df = df[df['tipo_discrepancia'] == tipo]
        if q:
            mask = df.apply(lambda r: q in str(r['produto']).lower() or q in str(r['sugestao']).lower() or q in str(r['tipo_discrepancia']).lower(), axis=1)
            df = df[mask]
        self._populate_tree(df)

    # --- exportar ---
    def export_report(self, event=None):
        if self.report_df.empty:
            messagebox.showinfo("Exportar", "Relatório vazio — nada a exportar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path:
            return
        # pegar dados atualmente exibidos na tree (para exportar filtro atual)
        rows = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, 'values')
            # map para cabeçalho
            rows.append({
                'produto': vals[0],
                'data': vals[1],
                'estoque_anterior': vals[2],
                'compras': vals[3],
                'vendas': vals[4],
                'estoque_atual': vals[5],
                'estoque_esperado': vals[6],
                'diferenca': vals[7],
                'tipo_discrepancia': vals[8],
                'sugestao_preview': vals[9],
            })
        try:
            pd.DataFrame(rows).to_csv(path, index=False)
            self.status['text'] = f"Exportado: {path.split('/')[-1]}"
            messagebox.showinfo("Exportado", f"Arquivo salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro exportar", str(e))

    # --- tema e estilos ---
    def toggle_theme(self, event=None):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def apply_theme(self):
        th = self.themes[self.current_theme]
        self.configure(bg=th["bg"])
        # atualizar widgets que definimos explicitamente
        for w in self.winfo_children():
            try:
                w.configure(bg=th["bg"])
            except Exception:
                pass
        # status and summary
        self.status.configure(bg=th["bg"], fg=th["text"])
        self.summary_lbl.configure(bg=th["bg"], fg=th["text"])
        # Treeview style tweaks
        self.style.theme_use('clam')
        # headings
        self.style.configure("Treeview.Heading", background=th["frame"], foreground=th["text"], font=('Helvetica', 10, 'bold'))
        self.style.configure("Treeview", background=th["zebra1"], foreground=th["text"], fieldbackground=th["zebra1"])
        # text boxes
        self.detail_text.configure(bg=th["frame"], fg=th["text"])
        self.sugg_box.configure(bg=th["frame"], fg=th["text"])

        # recolor tags after applying theme
        self._style_tree_tags()

    # --- atalhos ---
    def _bind_shortcuts(self):
        self.bind_all("<Control-g>", self.generate_report)
        self.bind_all("<Control-G>", self.generate_report)
        self.bind_all("<Control-e>", self.export_report)
        self.bind_all("<Control-E>", self.export_report)
        self.bind_all("<Control-f>", lambda e: self.entry_search.focus_set())
        self.bind_all("<Control-F>", lambda e: self.entry_search.focus_set())
        self.bind_all("<Control-t>", lambda e: self.toggle_theme())
        self.bind_all("<Control-T>", lambda e: self.toggle_theme())

def main():
    app = StockValidatorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
