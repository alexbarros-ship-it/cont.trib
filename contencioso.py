import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build
import traceback

app = FastAPI(title="GoGroup - API Contencioso Final")

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
        
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            print(f"❌ Erro: {SERVICE_ACCOUNT_FILE} não existe.")
            return

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # 1. Mapear as abas reais da planilha
        sheet_metadata = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_titles = [s['properties']['title'] for s in sheets]
        
        # 2. Tentar encontrar a aba específica, senão pega a primeira aba disponível
        target_sheet = 'Planilha Completa - Grupo'
        if target_sheet not in sheet_titles:
            print(f"⚠️ Aba '{target_sheet}' não encontrada. Abas detectadas: {sheet_titles}")
            target_sheet = sheet_titles[0]
            print(f"➡️ Redirecionando para a aba: '{target_sheet}'")
        
        # 3. Baixar os dados
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=target_sheet).execute()
        values = result.get('values', [])
        
        if not values:
            print(f"⚠️ A aba '{target_sheet}' está completamente vazia.")
            df_global = pd.DataFrame()
            return

        # 4. Localizar inteligentemente o cabeçalho (ignora títulos soltos ou logos na linha 1)
        header_idx = 0
        for i, row in enumerate(values):
            # Procura a primeira linha que tenha pelo menos 4 colunas preenchidas
            filled_cells = len([c for c in row if str(c).strip()])
            if filled_cells >= 4:
                header_idx = i
                break
                
        print(f"📌 Cabeçalho detectado na linha {header_idx + 1} do Excel.")
        
        raw_headers = values[header_idx]
        # Garante nomes únicos para evitar falhas de duplicidade no Pandas
        headers = [str(h).strip() if h else f"Coluna_Sem_Nome_{i}" for i, h in enumerate(raw_headers)]
        
        data = values[header_idx + 1:]
        
        if not data:
            print("⚠️ Não existem dados abaixo do cabeçalho.")
            df_global = pd.DataFrame()
            return

        # 5. Criar a Tabela e Limpar "Fantasmas"
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        df = pd.DataFrame(data_padded, columns=headers)
        
        # Deleta linhas inteiramente vazias (frequente no Excel/Sheets)
        df = df.replace('', np.nan).dropna(how='all').fillna('')
        
        if df.empty:
            print("⚠️ A tabela ficou vazia após remover linhas em branco.")
            df_global = pd.DataFrame()
            return
        
        # 6. Processamento de dados financeiros
        for col in df.columns:
            col_lower = str(col).lower()
            if any(k in col_lower for k in ['valor', 'causa', 'atualizado', 'garantia', 'condenação', 'acordo']):
                df[col] = df[col].apply(limpar_valor_monetario)
        
        df = df.replace([np.inf, -np.inf], np.nan).fillna("")
        df_global = df
        print(f"✅ Sucesso Absoluto: {len(df_global)} processos estruturados e carregados!")
        
    except Exception as e:
        print(f"❌ Erro fatal no Python:")
        traceback.print_exc()

@app.on_event("startup")
def startup_event():
    load_data()

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
