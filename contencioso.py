from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

app = FastAPI(title="API Contencioso GoGroup - Data Engine")

# Habilita a comunicação com o Frontend HTML
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Função inteligente para converter qualquer formato de dinheiro do Excel num número matemático puro """
    if pd.isna(valor):
        return 0.0
    # Se já for um número (inteiro ou decimal), mantém-no
    if isinstance(valor, (int, float)):
        return float(valor)
    
    # Se for texto (string), remove R$, espaços e trata a pontuação brasileira
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').strip()
        if v_str == '' or v_str == '-':
            return 0.0
        
        # Se tiver ponto e vírgula (ex: 1.500.000,00) -> Remove pontos e troca vírgula por ponto
        if '.' in v_str and ',' in v_str:
            v_str = v_str.replace('.', '').replace(',', '.')
        # Se tiver apenas vírgula (ex: 1500,00) -> Troca a vírgula por ponto
        elif ',' in v_str:
            v_str = v_str.replace(',', '.')
        
        try:
            return float(v_str)
        except ValueError:
            return 0.0
            
    return 0.0

def load_data():
    global df_global
    caminho_arquivo = r"H:\Meu Drive\Contencioso_Tributario\Contencioso_GoGroup.xlsx"
    
    try:
        # Lê o Excel e remove espaços vazios acidentais nos cabeçalhos
        df = pd.read_excel(caminho_arquivo)
        df.columns = df.columns.str.strip()
        
        # 1. TRATAMENTO FINANCEIRO INTELIGENTE
        # Identifica automaticamente qualquer coluna que remeta a valores
        cols_financeiras = [col for col in df.columns if 'valor' in col.lower() or 'garantia' in col.lower() or 'condenação' in col.lower()]
        
        for col in cols_financeiras:
            df[col] = df[col].apply(limpar_valor_monetario)
        
        # 2. TRATAMENTO DE DATAS E ANOS
        if "Data de Distribuição" in df.columns:
            df["Data de Distribuição"] = pd.to_datetime(df["Data de Distribuição"], errors='coerce').dt.strftime('%Y-%m-%d').fillna("")
            
        for col_ano in ["Ano Distribuição", "Anos Distribuição"]:
            if col_ano in df.columns:
                 df[col_ano] = pd.to_numeric(df[col_ano], errors='coerce').fillna(0).astype(int).astype(str)
                 df[col_ano] = df[col_ano].replace('0', '')

        # 3. GARANTIA DE TEXTO NAS CLASSIFICAÇÕES
        # Evita que campos vazios de texto originem erros de 'NaN' na filtragem do JavaScript
        cols_texto = ["Risk Assessment (probabilidade de PERDA)", "Status", "Matéria", "UF"]
        for col in cols_texto:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '')

        # 4. LIMPEZA EXTREMA GERAL
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna("")
        
        df_global = df
        print(f"✅ Servidor Pronto: {len(df_global)} processos carregados e tratados sem erros matemáticos.")
        
    except Exception as e:
        print(f"❌ Erro crítico ao ler o Excel: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/dashboard")
def get_all_data():
    # Envia os dados encapsulados para o Frontend processar
    registros = df_global.to_dict(orient="records")
    return {"processos": registros}
