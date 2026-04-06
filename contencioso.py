import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

# Importações exclusivas da Google Sheets API
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = FastAPI(title="API Contencioso GoGroup - Google Sheets Engine")

# Permite que o seu HTML comunique com esta API sem bloqueios
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def limpar_valor_monetario(valor):
    """ Converte qualquer formato de dinheiro da planilha num número matemático puro """
    if pd.isna(valor) or valor == '': 
        return 0.0
    if isinstance(valor, (int, float)): 
        return float(valor)
    if isinstance(valor, str):
        v_str = valor.replace('R$', '').replace(' ', '').strip()
        if v_str in ('', '-'): 
            return 0.0
        # Trata o formato brasileiro/europeu (ex: 1.500,00 -> 1500.00)
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
    
    try:
        print("A iniciar ligação segura à Google Sheets API...")
        
        # 1. Configurações de Autenticação (Acesso estrito de leitura ao Sheets)
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        # O ficheiro JSON que descarregou deve ser renomeado para 'credenciais.json'
        SERVICE_ACCOUNT_FILE = 'credenciais.json' 
        
        # 2. INFORMAÇÕES EXATAS DA SUA PLANILHA
        SPREADSHEET_ID = '1ekyHYNG_tRp8Ar6iZjtqjM3RgX4jAc2H' 
        RANGE_NAME = 'Planilha Completa - Grupo' 
        
        # Autentica e constrói o serviço do Google
        creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)
        
        # 3. Faz a extração nativa dos dados
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get('values', [])
        
        if not values:
            raise ValueError("A API não encontrou dados. Verifique se a aba tem informação.")
            
        # 4. Estruturação dos dados para o Pandas
        headers = values[0]
        data = values[1:]
        
        # Proteção: Preenche células vazias no final das linhas para que a tabela não fique desalinhada
        data_padded = [row + [''] * (len(headers) - len(row)) for row in data]
        
        df = pd.DataFrame(data_padded, columns=headers)
        df.columns = df.columns.str.strip()
        
        # --- LIMPEZA E TRATAMENTO DE DADOS ---
        # A) Tratamento de Colunas Financeiras
        cols_financeiras = [col for col in df.columns if 'valor' in col.lower() or 'garantia' in col.lower() or 'condenação' in col.lower()]
        for col in cols_financeiras:
            df[col] = df[col].apply(limpar_valor_monetario)
        
        # B) Tratamento de Datas
        if "Data de Distribuição" in df.columns:
            df["Data de Distribuição"] = pd.to_datetime(df["Data de Distribuição"], errors='coerce').dt.strftime('%Y-%m-%d').fillna("")
            
        # C) Tratamento de Anos
        for col_ano in ["Ano Distribuição", "Anos Distribuição"]:
            if col_ano in df.columns:
                 df[col_ano] = pd.to_numeric(df[col_ano], errors='coerce').fillna(0).astype(int).astype(str)
                 df[col_ano] = df[col_ano].replace('0', '')

        # D) Garantia de Texto em Classificações para evitar erros no HTML
        cols_texto = ["Risk Assessment (probabilidade de PERDA)", "Status", "Matéria", "UF"]
        for col in cols_texto:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', '')

        # Remoção de infinitos e nulos restantes
        df = df.replace([np.inf, -np.inf], np.nan)
        df = df.fillna("")
        
        df_global = df
        print(f"✅ Sucesso Absoluto: {len(df_global)} processos carregados através da Google Sheets API!")
        
    except Exception as e:
        print(f"❌ Erro crítico ao ler os dados da Google Sheets: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/dashboard")
def get_all_data():
    # Converte o DataFrame para um formato que o JavaScript do painel consiga ler
    registros = df_global.to_dict(orient="records")
    return {"processos": registros}

if __name__ == "__main__":
    # Permite execução local ou na nuvem (o Render injeta a porta automaticamente)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
