import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    if pd.isna(valor) or valor == '': return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').strip()
        if v_str in ('', '-'): return 0.0
        if '.' in v_str and ',' in v_str: v_str = v_str.replace('.', '').replace(',', '.')
        elif ',' in v_str: v_str = v_str.replace(',', '.')
        try: return float(v_str)
        except ValueError: return 0.0
    return 0.0

def load_data():
    global df_global
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        # ⚠️ Certifique-se que o nome no GitHub seja exatamente credenciais.json
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H'
        RANGE_NAME = 'Planilha Completa - Grupo' 
        
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get('values', [])
        
        if not values:
            return

        headers = values[0]
        data = values[1:]
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        
        df = pd.DataFrame(data_padded, columns=headers)
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

        df = df.replace([np.inf, -np.inf], np.nan).fillna("")
        df_global = df
        print("✅ Dados carregados com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/dashboard")
def get_all_data():
    return {"processos": df_global.to_dict(orient="records")}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
