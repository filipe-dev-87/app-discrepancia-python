# ui.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import pandas as pd
from core import detect_discrepancies, get_example_data
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("ui")

class StockValidatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Validador de Estoque — Visualização Aprimorada")
        self.geometry("1200x700")
        self.minsize(1000, 600)

        # Temas simples
        self.themes = {
            "light": {"bg":"#f5f7fb","frame":"#ffffff","accent":"#2b7a78","text":"#111111","muted":"#666666","zebra1":"#ffffff","zebra2":"#f2f4f7"},
            "dark":  {"bg":"#181a1b","frame":"#242627","accent":"#7aa2f7","text":"#e8eefc","muted":"#bfc6d6","zebra1":"#232526","zebra2":"#1e1f20"}
        }
        self.current_theme = "light"
        self.style = ttk.Style(self)
        self.configure(bg=self.themes[self.current_theme]["bg"])

        # Data containers
        self.compras_df = None
        self.vendas_df = None
        self.estoque_df = None
        self.report_df = pd.DataFrame()

        self._build_ui()
        self._bind_shortcuts()
        self.apply_theme()

    def _build_ui(self):
        top = tk.Frame(self, bg=self.themes[self.current_theme]["bg"])
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10,5))

        # Left controls
        left_ctrl = tk.Frame(top, bg=self.themes[self.current_theme]["bg"])
        left_ctrl.pack(side=tk.LEFT, anchor='n')

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

        # Center area: search + filters + resumo
        center_ctrl = tk.Frame(top, bg=self.themes[self.current_theme]["bg"])
        center_ctrl.pack(side=tk.LEFT, padx=20, anchor='n')

        search_row = tk.Frame(center_ctrl, bg=self.themes[self.current_theme]["bg"])
        search_row.pack(fill=tk.X)
        tk.Label(search_row, text="Busca rápida:", bg=self.themes[self.current_theme]["bg"]).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.entry_search = tk.Entry(search_row, textvariable=self.search_var, width=30)
        self.entry_search.pack(side=tk.LEFT, padx=(6,6))
        self.entry_search.bind("<KeyRelease>", lambda e: self.apply_filters())
        tk.Label(search_row, text=" (produto / sugestão / tipo)", bg=self.themes[self.current_theme]["bg"], fg=self.themes[self.current_theme]["muted"]).pack(side=tk.LEFT)

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

        self.summary_lbl = tk.Label(center_ctrl, text="Resumo: —", bg=self.themes[self.current_theme]["bg"])
        self.summary_lbl.pack(anchor='w', pady=(6,0))

        # Right: Tree + detail
        right_frame = tk.Frame(self, bg=self.themes[self.current_theme]["bg"])
        right_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(4,10))

        tree_frame = tk.Frame(right_frame, bg=self.themes[self.current_theme]["bg"])
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        cols = ("produto","data","estoque_anterior","compras","vendas","estoque_atual","estoque_esperado","diferenca","tipo_discrepancia","sugestao")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode='browse')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=110, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.open_full_suggestion())

        detail_frame = tk.Frame(right_frame, height=180, bg=self.themes[self.current_theme]["frame"])
        detail_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=(8,0))
        detail_frame.pack_propagate(False)

        self.detail_text = tk.Text(detail_frame, height=6, wrap='word', state='disabled')
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6,0), pady=6)
        self.sugg_box = ScrolledText(detail_frame, width=50, height=6, wrap='word', state='disabled')
        self.sugg_box.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6,6), pady=6)

        self.status = tk.Label(self, text="Pronto", anchor='w', bg=self.themes[self.current_theme]["bg"])
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # Loaders (abre CSV e atualiza DataFrame)
    def _load_compras_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END); entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path); self.compras_df = df
                self.status['text'] = f"Compras carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Compras: {e}")

    def _load_vendas_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END); entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path); self.vendas_df = df
                self.status['text'] = f"Vendas carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Vendas: {e}")

    def _load_estoque_from_entry(self, entry_widget):
        path = filedialog.askopenfilename(filetypes=[("CSV files","*.csv")])
        if path:
            entry_widget.delete(0, tk.END); entry_widget.insert(0, path)
            try:
                df = pd.read_csv(path); self.estoque_df = df
                self.status['text'] = f"Estoque carregado: {path.split('/')[-1]}"
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível ler Estoque: {e}")

    # Geração do relatório (usa detect_discrepancies do módulo core)
    def generate_report(self, event=None):
        try:
            tolerance = int(self.entry_tolerance.get())
        except Exception:
            messagebox.showerror("Erro", "Tolerância inválida. Insira um número inteiro.")
            return

        if self.compras_df is None or self.vendas_df is None or self.estoque_df is None:
            r = messagebox.askyesno("Dados ausentes", "Alguns arquivos não foram informados. Usar dados de exemplo?")
            if r:
                self.compras_df, self.vendas_df, self.estoque_df = get_example_data()
            else:
                messagebox.showerror("Erro", "Forneça os 3 arquivos CSV ou aceite usar os dados de exemplo.")
                return

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
        prods = sorted(self.report_df['produto'].dropna().unique().tolist()) if not self.report_df.empty else []
        tipos = sorted(self.report_df['tipo_discrepancia'].dropna().unique().tolist()) if not self.report_df.empty else []
        self.produto_filter['values'] = ["(todos)"] + prods
        self.tipo_filter['values'] = ["(todos)"] + tipos
        self.produto_filter.set("(todos)"); self.tipo_filter.set("(todos)")
        self._update_summary()

    def _update_summary(self):
        if self.report_df.empty:
            self.summary_lbl['text'] = "Resumo: nenhum registro."; return
        counts = self.report_df['tipo_discrepancia'].value_counts().to_dict()
        parts = [f"{k}: {v}" for k, v in counts.items()]
        self.summary_lbl['text'] = "Resumo: " + " | ".join(parts)

    def _populate_tree(self, df):
        for r in self.tree.get_children(): self.tree.delete(r)
        if df.empty: return
        for idx, row in df.iterrows():
            sug_preview = (row.sugestao[:80] + '...') if row.sugestao and len(row.sugestao) > 80 else (row.sugestao or '')
            vals = (row.produto, row.data.strftime('%Y-%m-%d'), row.estoque_anterior, row.compras, row.vendas, row.estoque_atual, row.estoque_esperado, row.diferenca, row.tipo_discrepancia, sug_preview)
            tag = self._tag_for_tipo(str(row.tipo_discrepancia))
            self.tree.insert("", "end", iid=str(idx), values=vals, tags=(tag,))
        self._style_tree_tags(); self._autosize_columns()

    def _tag_for_tipo(self, tipo):
        if tipo == 'falta_registro_compra': return 'tag_compra'
        if tipo == 'falta_registro_venda': return 'tag_venda'
        if tipo == 'erro_lancamento_estoque': return 'tag_erro'
        if tipo in ('baseline','sem_baseline','estoque_nao_informado'): return 'tag_info'
        return 'tag_default'

    def _style_tree_tags(self):
        theme = self.themes[self.current_theme]
        self.tree.tag_configure('tag_compra', foreground='#1b5e20')
        self.tree.tag_configure('tag_venda', foreground='#b71c1c')
        self.tree.tag_configure('tag_erro', foreground='#e65100')
        self.tree.tag_configure('tag_info', foreground='#37474f')
        self.tree.tag_configure('tag_default', foreground=theme['muted'])

    def _autosize_columns(self):
        for col in self.tree['columns']:
            max_len = len(col)
            for iid in self.tree.get_children():
                val = str(self.tree.set(iid, col))
                if len(val) > max_len: max_len = len(val)
            width = min(max(80, max_len * 8 + 20), 500)
            self.tree.column(col, width=width)

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]
        try:
            row = self.report_df.iloc[int(iid)]
        except Exception:
            vals = self.tree.item(iid, 'values')
            produto, data = vals[0], vals[1]
            mask = (self.report_df['produto'] == produto) & (self.report_df['data'].dt.strftime('%Y-%m-%d') == data)
            if not mask.any(): return
            row = self.report_df.loc[mask].iloc[0]

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
        self.detail_text.config(state='normal'); self.detail_text.delete('1.0', tk.END); self.detail_text.insert(tk.END, details); self.detail_text.config(state='disabled')
        self.sugg_box.config(state='normal'); self.sugg_box.delete('1.0', tk.END); self.sugg_box.insert(tk.END, row.sugestao or ""); self.sugg_box.config(state='disabled')

    def open_full_suggestion(self):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]
        try:
            row = self.report_df.iloc[int(iid)]
        except Exception:
            vals = self.tree.item(iid, 'values'); produto, data = vals[0], vals[1]
            mask = (self.report_df['produto'] == produto) & (self.report_df['data'].dt.strftime('%Y-%m-%d') == data)
            row = self.report_df.loc[mask].iloc[0]
        top = tk.Toplevel(self); top.title("Sugestão completa"); top.geometry("600x300")
        txt = ScrolledText(top, wrap='word'); txt.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        txt.insert(tk.END, row.sugestao or ""); txt.config(state='disabled')

    def apply_filters(self):
        if self.report_df.empty: return
        df = self.report_df.copy()
        q = self.search_var.get().strip().lower()
        prod = self.produto_filter.get(); tipo = self.tipo_filter.get()
        if prod and prod != "(todos)": df = df[df['produto'] == prod]
        if tipo and tipo != "(todos)": df = df[df['tipo_discrepancia'] == tipo]
        if q:
            mask = df.apply(lambda r: q in str(r['produto']).lower() or q in str(r['sugestao']).lower() or q in str(r['tipo_discrepancia']).lower(), axis=1)
            df = df[mask]
        self._populate_tree(df)

    def export_report(self, event=None):
        if self.report_df.empty:
            messagebox.showinfo("Exportar", "Relatório vazio — nada a exportar."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path: return
        rows = []
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, 'values')
            rows.append({'produto': vals[0],'data': vals[1],'estoque_anterior': vals[2],'compras': vals[3],'vendas': vals[4],'estoque_atual': vals[5],'estoque_esperado': vals[6],'diferenca': vals[7],'tipo_discrepancia': vals[8],'sugestao_preview': vals[9]})
        try:
            pd.DataFrame(rows).to_csv(path, index=False)
            self.status['text'] = f"Exportado: {path.split('/')[-1]}"
            messagebox.showinfo("Exportado", f"Arquivo salvo em:\n{path}")
        except Exception as e:
            messagebox.showerror("Erro exportar", str(e))

    def toggle_theme(self, event=None):
        self.current_theme = "dark" if self.current_theme == "light" else "light"; self.apply_theme()

    def apply_theme(self):
        th = self.themes[self.current_theme]
        self.configure(bg=th["bg"])
        for w in self.winfo_children():
            try: w.configure(bg=th["bg"])
            except Exception: pass
        self.status.configure(bg=th["bg"], fg=th["text"]); self.summary_lbl.configure(bg=th["bg"], fg=th["text"])
        self.style.theme_use('clam')
        self.style.configure("Treeview.Heading", background=th["frame"], foreground=th["text"], font=('Helvetica', 10, 'bold'))
        self.style.configure("Treeview", background=th["zebra1"], foreground=th["text"], fieldbackground=th["zebra1"])
        self.detail_text.configure(bg=th["frame"], fg=th["text"]); self.sugg_box.configure(bg=th["frame"], fg=th["text"])
        self._style_tree_tags()

    def _bind_shortcuts(self):
        self.bind_all("<Control-g>", self.generate_report); self.bind_all("<Control-G>", self.generate_report)
        self.bind_all("<Control-e>", self.export_report); self.bind_all("<Control-E>", self.export_report)
        self.bind_all("<Control-f>", lambda e: self.entry_search.focus_set()); self.bind_all("<Control-F>", lambda e: self.entry_search.focus_set())
        self.bind_all("<Control-t>", lambda e: self.toggle_theme()); self.bind_all("<Control-T>", lambda e: self.toggle_theme())
