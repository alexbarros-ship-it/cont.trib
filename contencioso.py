import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="GoGroup - API Contencioso (Google Sheets)")

# Configuração de CORS para permitir que o Dashboard (HTML) aceda aos dados
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variável global para armazenar os processos em memória
df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Converte strings de moeda (ex: R$ 1.250,00) em floats (1250.0) """
    if pd.isna(valor) or valor == '' or valor == '-':
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').strip()
        if v_str == '' or v_str == '-':
            return 0.0
        # Trata o formato brasileiro (ponto para milhar, vírgula para decimal)
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
    """ Carrega os dados diretamente da API do Google Sheets """
    global df_global
    try:
        print("A tentar ligar à Google Sheets API...")
        
        # Definição do escopo e ficheiro de credenciais
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        
        # Parâmetros da sua planilha (ID e Aba)
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H'
        RANGE_NAME = 'Planilha Completa - Grupo' 
        
        # Autenticação
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # Chamada à API para obter os valores
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range=RANGE_NAME
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            print("Aviso: A planilha está vazia ou a aba não foi encontrada.")
            return

        # Transformação em DataFrame
        headers = values[0] # Primeira linha como cabeçalho
        data = values[1:]   # Resto como dados
        
        # Normalização do tamanho das linhas (evita erros se houver células vazias no fim)
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        
        df = pd.DataFrame(data_padded, columns=headers)
        df.columns = df.columns.str.strip()
        
        # --- Limpeza de Dados ---
        
        # 1. Colunas Financeiras
        cols_financeiras = [
            col for col in df.columns 
            if 'valor' in col.lower() or 'garantia' in col.lower() or 'condenação' in col.lower()
        ]
        for col in cols_financeiras:
            df[col] = df[col].apply(limpar_valor_monetario)
        
        # 2. Formatação de Datas (ISO para o JS entender)
        if "Data de Distribuição" in df.columns:
            df["Data de Distribuição"] = pd.to_datetime(
                df["Data de Distribuição"], errors='coerce'
            ).dt.strftime('%Y-%m-%d').fillna("")
            
        # 3. Formatação de Anos
        for col_ano in ["Ano Distribuição", "Anos Distribuição"]:
            if col_ano in df.columns:
                 df[col_ano] = pd.to_numeric(df[col_ano], errors='coerce').fillna(0).astype(int).astype(str)
                 df[col_ano] = df[col_ano].replace('0', '')

        # 4. Strings Limpas
        df = df.replace([np.inf, -np.inf], np.nan).fillna("")
        
        df_global = df
        print(f"✅ Sucesso: {len(df_global)} processos carregados da Nuvem!")
        
    except Exception as e:
        print(f"❌ Erro na carga de dados: {e}")

@app.on_event("startup")
def startup_event():
    """ Executado quando o servidor inicia """
    load_data()

@app.get("/")
def health_check():
    """ Rota simples para verificar se o servidor está online """
    return {"status": "online", "processos_carregados": len(df_global)}

@app.get("/api/dashboard")
def get_all_data():
    """ Endpoint que o index.html consome """
    if df_global.empty:
        # Se os dados falharem, tenta recarregar antes de responder
        load_data()
    
    registros = df_global.to_dict(orient="records")
    return {"processos": registros}

if __name__ == "__main__":
    # Porta configurada para o Render ou porta 8000 local
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
