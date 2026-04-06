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

app = FastAPI(title="GoGroup - BI API Final")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    if pd.isna(valor) or valor == '' or valor == '-':
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
        if v_str == '' or v_str == '-': return 0.0
        try: return float(v_str)
        except ValueError: return 0.0
    return 0.0

def load_data():
    global df_global
    try:
        print("🔍 A iniciar busca de dados no Google Sheets...")
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H'
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"❌ Erro: O ficheiro {SERVICE_ACCOUNT_FILE} não existe.")
            return

        # =========================================================
        # FIX: CORREÇÃO AUTOMÁTICA DA ASSINATURA JWT (PRIVATE KEY)
        # =========================================================
        with open(SERVICE_ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            creds_info = json.load(f)
            
        if "\\n" in creds_info.get('private_key', ''):
            creds_info['private_key'] = creds_info['private_key'].replace("\\n", "\n")
            print("💡 Chave JWT higienizada: Quebras de linha (\\n) foram corrigidas automaticamente.")

        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
        # =========================================================

        service = build('sheets', 'v4', credentials=creds)
        
        # LER APENAS A ABA EXATA
        target_sheet = 'Planilha Completa - Grupo'
        print(f"➡️ A ler estritamente a aba: '{target_sheet}'")
        
        target_range = f"'{target_sheet}'!A1:ZZ10000"
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=target_range).execute()
        values = result.get('values', [])
        
        print(f"📊 Total de linhas brutas extraídas: {len(values)}")
        
        if not values:
            print(f"⚠️ A aba '{target_sheet}' está completamente vazia.")
            df_global = pd.DataFrame()
            return

        # Localizar o cabeçalho (linha com pelo menos 2 colunas preenchidas)
        header_idx = 0
        for i, row in enumerate(values):
            if len([c for c in row if str(c).strip()]) >= 2:
                header_idx = i
                break
                
        print(f"📌 Cabeçalho detetado na linha {header_idx + 1} do Excel.")
        
        raw_headers = values[header_idx]
        headers = [str(h).strip() if h else f"Coluna_Sem_Nome_{i}" for i, h in enumerate(raw_headers)]
        
        data = values[header_idx + 1:]
        
        # Limpar linhas vazias
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        df = pd.DataFrame(data_padded, columns=headers)
        df = df.replace('', np.nan).dropna(how='all').fillna('')
        
        if df.empty:
            print("⚠️ A tabela ficou vazia após remover linhas em branco.")
            df_global = pd.DataFrame()
            return
        
        # Processamento financeiro
        for col in df.columns:
            if any(k in str(col).lower() for k in ['valor', 'causa', 'atualizado', 'garantia', 'condenação', 'acordo']):
                df[col] = df[col].apply(limpar_valor_monetario)
        
        df_global = df
        print(f"✅ Sucesso: {len(df_global)} processos carregados!")
        
    except Exception as e:
        print(f"❌ Erro fatal no Python:")
        traceback.print_exc()

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(content=b"", media_type="image/x-icon")

@app.get("/")
def health():
    return {"status": "active", "processes_in_memory": len(df_global)}

@app.get("/api/dashboard")
def get_all_data():
    if df_global.empty:
        load_data()
    if df_global.empty:
        return {"processos": [], "status": "empty_sheet"}
    return {"processos": df_global.to_dict(orient="records")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
