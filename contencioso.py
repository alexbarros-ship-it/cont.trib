import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

# Importações do Google
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="API Contencioso GoGroup - Google Sheets")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Converte dinheiro da planilha num número puro """
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
        print("Iniciando conexão segura com o Google Sheets API...")
        
        # 1. Configurações de Autenticação
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        SERVICE_ACCOUNT_FILE = 'credenciais.json' # Lembre-se de renomear o seu arquivo JSON para este nome
        
        # 2. SUAS INFORMAÇÕES EXATAS
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H' # Apenas o ID limpo
        RANGE_NAME = 'Planilha Completa - Grupo' 
        
        # Conecta na API do Google
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        
        # 3. Faz o download instantâneo dos valores
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get('values', [])
        
        if not values:
            raise ValueError("A planilha retornou vazia. Verifique se o nome da aba está correto e se há dados nela.")
            
        # 4. Transforma a resposta do Google em uma tabela Pandas
        headers = values[0]
        data = values[1:]
        
        # Proteção anti-quebra: Preenche células vazias no final das linhas para igualar ao cabeçalho
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        
        df = pd.DataFrame(data_padded, columns=headers)
        df.columns = df.columns.str.strip()
        
        # --- TRATAMENTO DE DADOS ---
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
        print(f"✅ Sucesso Absoluto: {len(df_global)} processos lidos via Google Sheets API!")
        
    except Exception as e:
        print(f"❌ Erro crítico ao ler o Google Sheets: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/dashboard")
def get_all_data():
    registros = df_global.to_dict(orient="records")
    return {"processos": registros}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
