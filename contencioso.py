from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np

app = FastAPI(title="API Contencioso GoGroup - Data Engine Server")

# Permite que o HTML local converse com o servidor Python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

df_global = pd.DataFrame()

def load_data():
    global df_global
    caminho_arquivo = r"H:\Meu Drive\Contencioso_Tributario\Contencioso_GoGroup.xlsx"
    
    try:
        # 1. Lê o Excel
        df = pd.read_excel(caminho_arquivo)
        df.columns = df.columns.str.strip()
        
        # 2. Tratamento Financeiro (limpa R$, pontos e converte para número puro)
        cols_fin = ["Valor da causa", "Valor Atualizado", "Valor em Garantia", "Valor de Condenação ou Acordo (casos encerrados)"]
        for col in cols_fin:
            if col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace('R$', '', regex=False).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 3. Tratamento de Datas (O Javascript faz o .split('-') para pegar o ano e mês)
        # Convertendo para o formato ISO AAAA-MM-DD
        if "Data de Distribuição" in df.columns:
            df["Data de Distribuição"] = pd.to_datetime(df["Data de Distribuição"], errors='coerce').dt.strftime('%Y-%m-%d')
            
        # 4. Tratamento do "Ano Distribuição" para evitar casas decimais como "2024.0"
        if "Ano Distribuição" in df.columns:
             df["Ano Distribuição"] = pd.to_numeric(df["Ano Distribuição"], errors='coerce').fillna(0).astype(int).astype(str)
             df["Ano Distribuição"] = df["Ano Distribuição"].replace('0', '')
             
        if "Anos Distribuição" in df.columns:
             df["Anos Distribuição"] = pd.to_numeric(df["Anos Distribuição"], errors='coerce').fillna(0).astype(int).astype(str)
             df["Anos Distribuição"] = df["Anos Distribuição"].replace('0', '')

        # 5. Preenche vazios para não quebrar o JSON
        df_global = df.fillna("")
        print(f"✅ Servidor Pronto: {len(df_global)} processos carregados e limpos para o BI.")
        
    except Exception as e:
        print(f"❌ Erro crítico ao ler o Excel: {e}")

@app.on_event("startup")
def startup_event():
    load_data()

# O seu HTML atual faz uma requisição GET simples e espera a chave "processos"
@app.get("/api/dashboard")
def get_all_data():
    # Converte a tabela inteira para um formato que o Javascript entende
    registros = df_global.to_dict(orient="records")
    
    # Envia encapsulado na chave 'processos', exatamente como o seu JS pede: data.processos
    return {"processos": registros}
