import os
import uvicorn
import pandas as pd
import numpy as np
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import traceback

app = FastAPI(title="GoGroup - BI API Public Link")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Link da planilha exportada como CSV (Baseado no seu ID e GID)
SHEET_ID = "1yMaNNFgxFJPO7U4I9th92dhM3Z3K5qIDWeqlrfh8LAM"
GID = "1851867780"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    if pd.isna(valor) or valor == '' or valor == '-':
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        # Remove R$, espaços e converte padrão BR para US
        v_str = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
        try:
            return float(v_str)
        except:
            return 0.0
    return 0.0

def load_data():
    global df_global
    try:
        print(f"🔍 Conectando à planilha pública: {SHEET_ID}...")
        # Lendo o CSV diretamente da URL do Google
        df = pd.read_csv(CSV_URL)
        
        # Limpar nomes das colunas (remover espaços invisíveis)
        df.columns = df.columns.str.strip()
        
        # Converter colunas financeiras
        cols_financeiras = [
            'Valor da causa', 'Valor Atualizado', 'Valor em Garantia', 
            'Valor de Condenação ou Acordo (casos encerrados)'
        ]
        for col in cols_financeiras:
            if col in df.columns:
                df[col] = df[col].apply(limpar_valor_monetario)
        
        # Garantir que o Ano é numérico ou string limpa
        if 'Ano Distribuição' in df.columns:
            df['Ano Distribuição'] = pd.to_numeric(df['Ano Distribuição'], errors='coerce').fillna(0).astype(int)

        df_global = df
        print(f"✅ Sucesso: {len(df_global)} processos carregados via link público!")

    except Exception as e:
        print("❌ Erro ao ler link público:")
        traceback.print_exc()

@app.on_event("startup")
async def startup_event():
    load_data()

@app.get("/")
def health():
    return {"status": "active", "rows": len(df_global), "source": "public_web_link"}

@app.get("/api/dashboard")
def get_data():
    if df_global.empty:
        load_data()
    return {"processos": df_global.to_dict(orient="records")}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=b"", media_type="image/x-icon")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
