import os
import uvicorn
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import traceback

app = FastAPI(title="GoGroup BI API - Cloud Version")

# Habilita CORS para permitir que o Dashboard (HTML) acesse os dados
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL da planilha publicada como CSV
SHEET_URL = "https://docs.google.com/spreadsheets/d/1yMaNNFgxFJPO7U4I9th92dhM3Z3K5qIDWeqlrfh8LAM/export?format=csv&gid=1851867780"

def clean_currency(val):
    """Converte valores monetários do padrão BR (R$ 1.000,00) para float."""
    if pd.isna(val) or val == "" or val == "-":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(s)
    except:
        return 0.0

@app.get("/api/dashboard")
async def get_data():
    try:
        # Lê os dados diretamente da URL pública do Google Sheets
        df = pd.read_csv(SHEET_URL)
        
        # Limpeza de nomes de colunas
        df.columns = [c.strip() for c in df.columns]
        
        # Processamento de colunas financeiras conhecidas
        finance_keywords = ['valor', 'condenação', 'acordo', 'garantia']
        for col in df.columns:
            if any(key in col.lower() for key in finance_keywords):
                df[col] = df[col].apply(clean_currency)
        
        # Garantir que anos sejam inteiros
        if 'Ano Distribuição' in df.columns:
            df['Ano Distribuição'] = pd.to_numeric(df['Ano Distribuição'], errors='coerce').fillna(0).astype(int)

        return {"processos": df.to_dict(orient="records")}
    except Exception as e:
        print("Erro ao processar planilha:")
        traceback.print_exc()
        return {"error": str(e), "processos": []}

@app.get("/")
def health():
    return {"status": "online", "source": "google_sheets_direct"}

if __name__ == "__main__":
    # O Render define a porta automaticamente através da variável de ambiente PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
