import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="GoGroup - API Contencioso v3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Converte formatos de moeda para float """
    if pd.isna(valor) or valor == '' or valor == '-':
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
        if v_str == '' or v_str == '-':
            return 0.0
        try:
            return float(v_str)
        except ValueError:
            return 0.0
    return 0.0

def load_data():
    global df_global
    try:
        print("🔍 Iniciando busca de dados no Google Sheets...")
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H'
        # Mudando para capturar explicitamente a aba inteira
        RANGE_NAME = "'Planilha Completa - Grupo'!A1:ZZ10000" 
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"❌ Erro: {SERVICE_ACCOUNT_FILE} não existe.")
            return

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get('values', [])
        
        if not values or len(values) < 2:
            print("⚠️ Aviso: API retornou lista vazia ou sem dados além do cabeçalho.")
            df_global = pd.DataFrame()
            return

        headers = values[0]
        data = values[1:]
        
        # Filtra linhas completamente vazias (que vêm como listas vazias da API)
        data = [r for r in data if any(r)]
        
        if not data:
            print("⚠️ Todas as linhas além do cabeçalho estão vazias.")
            df_global = pd.DataFrame()
            return

        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        
        df = pd.DataFrame(data_padded, columns=headers)
        df.columns = df.columns.str.strip()
        
        # Processamento financeiro
        for col in df.columns:
            if any(k in col.lower() for k in ['valor', 'causa', 'atualizado', 'garantia']):
                df[col] = df[col].apply(limpar_valor_monetario)
        
        df = df.replace([np.inf, -np.inf], np.nan).fillna("")
        df_global = df
        print(f"✅ Sucesso: {len(df_global)} processos reais carregados!")
        
    except Exception as e:
        print(f"❌ Erro fatal: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/")
def health():
    return {"status": "active", "processes": len(df_global)}

@app.get("/api/dashboard")
def get_all_data():
    # Retorna sempre os dados atuais ou tenta recarregar se estiver vazio
    if df_global.empty:
        load_data()
    return {"processos": df_global.to_dict(orient="records")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
