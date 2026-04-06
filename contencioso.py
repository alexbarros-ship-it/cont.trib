import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

app = FastAPI(title="API Contencioso GoGroup - Cloud Engine")

# Libera o acesso para que o seu HTML no GitHub consiga puxar os dados da API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Converte dinheiro do Excel num número puro """
    if pd.isna(valor):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').strip()
        if v_str in ('', '-'):
            return 0.0
        if '.' in v_str and ',' in v_str:
            v_str = v_str.replace('.', '').replace(',', '.')
        elif ',' in v_str:
            v_str = v_str.replace(',', '.')
        try:
            return float(v_str)
        except ValueError:
            return 0.0
    return 0.0

def load_data():
    global df_global
    
    # ⚠️ MUDANÇA CRUCIAL PARA A NUVEM:
    # Como a nuvem não tem o disco "H:\", o arquivo Excel DEVE ser subido 
    # para o seu repositório no GitHub na mesma pasta deste arquivo .py
    caminho_arquivo = "Contencioso_GoGroup.xlsx"
    
    try:
        df = pd.read_excel(caminho_arquivo)
        df.columns = df.columns.str.strip()
        
        cols_financeiras = [col for col in df.columns if 'valor' in col.lower() or 'garantia' in col.lower() or 'condenação' in col.lower()]
        for col in cols_financeiras:
            df[col] = df[col].apply(limpar_valor_monetario)
        
        if "Data de Distribuição" in df.columns:
            df["Data de Distribuição"] = pd.to_datetime(df["Data de Distribuição"], errors='coerce').dt.strftime('%Y-%m-%d').fillna("")
            
        for col_ano in ["Ano Distribuição", "Anos Distribuição"]:
            if col_ano in df.columns:
                 df[col_ano] = pd.to_numeric(df[col_ano], errors='coerce').fillna(0).astype(int).astype(str)
                 df[col_ano] = df[col_ano].replace('0', '')

        cols_texto = ["Risk Assessment (probabilidade de PERDA)", "Status", "Matéria", "UF"]
        for col in cols_texto:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '')

        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna("")
        
        df_global = df
        print(f"✅ Servidor Cloud Pronto: {len(df_global)} processos carregados.")
        
    except Exception as e:
        print(f"❌ Erro crítico ao ler o Excel na Nuvem: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/dashboard")
def get_all_data():
    registros = df_global.to_dict(orient="records")
    return {"processos": registros}

if __name__ == "__main__":
    # Servidores em nuvem exigem que a porta seja definida dinamicamente pelo ambiente
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
