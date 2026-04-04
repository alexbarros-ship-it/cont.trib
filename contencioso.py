import pandas as pd
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configuração de CORS para permitir que o HTML comunique com a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Caminho absoluto para o seu Google Drive
FILE_PATH = r"H:\Meu Drive\Contencioso_Tributario\Contencioso_GoGroup.xlsx"

def load_data():
    """Lê a planilha Excel do diretório H:"""
    if not os.path.exists(FILE_PATH):
        return pd.DataFrame()
    
    try:
        # Lê a planilha. Se houver uma aba específica, adicione: sheet_name='NomeDaAba'
        df = pd.read_excel(FILE_PATH, engine='openpyxl')
        
        # Tratamento de Nulos para evitar erros no JSON
        df = df.fillna("")
        
        # Conversão de colunas numéricas (garantindo que o Python entenda os valores)
        df['Valor da causa'] = pd.to_numeric(df['Valor da causa'], errors='coerce').fillna(0)
        df['Valor Atualizado'] = pd.to_numeric(df['Valor Atualizado'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        print(f"Erro ao ler Excel: {e}")
        return pd.DataFrame()

@app.get("/api/dashboard")
async def get_dashboard():
    df = load_data()
    if df.empty:
        return {"error": "Planilha não encontrada ou vazia no caminho H:"}

    # Cálculos para os KPIs do Dashboard
    exposicao_total = float(df['Valor da causa'].sum())
    
    # Soma específica do cenário Provável (Case Insensitive)
    provavel_df = df[df['Risk Assessment (probabilidade de PERDA)'].astype(str).str.contains('Provável', case=False)]
    soma_provavel = float(provavel_df['Valor da causa'].sum())

    # Agrupamento para o gráfico de Rosca (BI)
    grafico_risco = df.groupby('Risk Assessment (probabilidade de PERDA)')['Valor da causa'].sum().to_dict()

    # Retorna os dados formatados
    return {
        "exposicao_total": exposicao_total,
        "provavel_soma": soma_provavel,
        "quantidade_processos": len(df),
        "grafico_risco": grafico_risco,
        "processos": df.to_dict(orient="records")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)