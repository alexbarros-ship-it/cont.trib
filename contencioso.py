import os
import uvicorn
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import traceback

app = FastAPI(title="GoGroup BI API - Ligação Direta")

# Configuração de CORS para permitir que o Dashboard (HTML) aceda aos dados
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL da folha de cálculo publicada como CSV (Exportação Direta)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1yMaNNFgxFJPO7U4I9th92dhM3Z3K5qIDWeqlrfh8LAM/export?format=csv&gid=1851867780"

def limpar_moeda(valor):
    """Converte valores monetários do padrão brasileiro/português para float."""
    if pd.isna(valor) or valor == "" or valor == "-":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    # Remove símbolos de moeda, espaços e ajusta os separadores numéricos
    s = str(valor).replace('R$', '').replace('€', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(s)
    except:
        return 0.0

@app.get("/api/dashboard")
async def obter_dados():
    try:
        # Lê os dados em tempo real diretamente da URL pública do Google Sheets
        df = pd.read_csv(SHEET_URL)
        
        # Limpeza de nomes das colunas (remove espaços em branco invisíveis)
        df.columns = [c.strip() for c in df.columns]
        
        # Processamento automático de colunas financeiras detetadas por palavras-chave
        palavras_chave_fin = ['valor', 'condenação', 'acordo', 'garantia']
        for col in df.columns:
            if any(key in col.lower() for key in palavras_chave_fin):
                df[col] = df[col].apply(limpar_moeda)
        
        # Garante que a coluna de Ano é tratada como numérica
        if 'Ano Distribuição' in df.columns:
            df['Ano Distribuição'] = pd.to_numeric(df['Ano Distribuição'], errors='coerce').fillna(0).astype(int)

        # Retorna os processos no formato JSON esperado pelo Dashboard
        return {"processos": df.to_dict(orient="records")}
    except Exception as e:
        print("Erro ao processar a folha de cálculo:")
        traceback.print_exc()
        return {"error": str(e), "processos": []}

@app.get("/")
def estado_servidor():
    """Endpoint de verificação de saúde da API."""
    return {"status": "online", "fonte": "google_sheets_direto"}

if __name__ == "__main__":
    # O Render ou outros serviços de nuvem definem a porta via variável de ambiente PORT
    porta = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=porta)
