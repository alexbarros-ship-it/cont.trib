import os
import uvicorn
import json
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
import traceback

app = FastAPI(title="GoGroup - Diagnóstico de Conexão")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def load_data():
    global df_global
    try:
        print("--- INICIANDO DIAGNÓSTICO DE CONEXÃO ---")
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        # No Render, o ficheiro secreto fica na raiz ou caminho definido
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H'
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"❌ ERRO: O ficheiro {SERVICE_ACCOUNT_FILE} não foi encontrado no servidor Render.")
            return

        with open(SERVICE_ACCOUNT_FILE, 'r') as f:
            creds_info = json.load(f)
        
        # Correção de quebras de linha na chave privada
        if "\\n" in creds_info.get('private_key', ''):
            creds_info['private_key'] = creds_info['private_key'].replace("\\n", "\n")

        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        
        # TESTE 1: Tentar ler metadados da planilha (Verifica se o e-mail tem acesso)
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        titles = [s['properties']['title'] for s in sheets]
        print(f"✅ CONEXÃO ESTABELECIDA! Abas encontradas: {titles}")
        
        target_sheet = 'Planilha Completa - Grupo'
        
        if target_sheet not in titles:
            print(f"❌ ERRO: A aba '{target_sheet}' não foi listada pelo Google. Verifique o nome exato.")
            return

        # TESTE 2: Tentar ler os valores
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range=f"'{target_sheet}'!A1:ZZ10000"
        ).execute()
        
        values = result.get('values', [])
        print(f"📊 Linhas brutas encontradas: {len(values)}")

        if not values:
            df_global = pd.DataFrame()
            return

        # Processamento simplificado para garantir carga
        header = values[0]
        data = values[1:]
        df = pd.DataFrame(data, columns=header[:len(data[0])]) if data else pd.DataFrame()
        
        # Limpeza básica de colunas financeiras (exemplo)
        for col in df.columns:
            if 'Valor' in col:
                df[col] = df[col].apply(lambda x: str(x).replace('R$', '').replace('.', '').replace(',', '.').strip())
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        df_global = df
        print(f"✅ DADOS CARREGADOS: {len(df_global)} processos na memória.")

    except Exception as e:
        print("❌ FALHA NO DIAGNÓSTICO:")
        traceback.print_exc()

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/")
def health():
    return {"status": "online", "rows": len(df_global), "sheet_id": "1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H"}

@app.get("/api/dashboard")
def get_data():
    return {"processos": df_global.to_dict(orient="records")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
