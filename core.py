# core.py
import pandas as pd
from dataclasses import dataclass
from typing import Optional
import logging

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

    Retorna um DataFrame com:
    - produto, data, estoque_anterior, compras, vendas, estoque_atual
    - estoque_esperado, diferenca, tipo_discrepancia, sugestao
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

# Função auxiliar: dados de exemplo (para uso pela UI)
def get_example_data():
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
    return compras_ex, vendas_ex, estoque_ex

if __name__ == "__main__":
    # Exemplo de execução direta do módulo
    c, v, e = get_example_data()
    rpt = detect_discrepancies(c, v, e, tolerance=2)
    print(rpt)
