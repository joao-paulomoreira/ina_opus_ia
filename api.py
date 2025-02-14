import streamlit as st
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import openai
from fastapi.middleware.cors import CORSMiddleware
from langdetect import detect
import time
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_log.log"),
        logging.StreamHandler()
    ]
)

# Inicializa a aplicação FastAPI
app = FastAPI(title="API Inaopusia")

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração da API OpenAI
openai.api_key = st.secrets["OPENAI_API_KEY"]

class ModelInput(BaseModel):
    prompt: str
    additional_params: Optional[dict] = None

class ModelResponse(BaseModel):
    response: str
    status: str

def retorna_resposta_modelo(mensagens, modelo='gpt-4o-mini-2024-07-18', temperatura=0, max_tokens=300):
    start_time = time.time()
    logging.info(f"Processando mensagens com {len(mensagens)} entradas")
    
    try:
        response = openai.ChatCompletion.create(
            model=modelo,
            messages=mensagens,
            temperature=temperatura,
            max_tokens=max_tokens
        )
        
        elapsed_time = time.time() - start_time
        processing_rate = f'Resposta processada com sucesso em {elapsed_time:.2f} segundos'
        logging.info(processing_rate)
        
        return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Erro ao processar resposta: {str(e)}")
        raise

@app.post("/predict")
async def predict(input_data: ModelInput):
    try:
        # Detecta o idioma da entrada
        idioma = detect(input_data.prompt)
        
        # Cria a mensagem do usuário
        mensagens = [
            {
                'role': 'system',
                'content': '''
identidade:
  nome: Ina
  descrição: >
    Ina é a Inteligência Artificial da Opuspac University, braço acadêmico da empresa Opuspac.
    Características: inteligente, delicada, simpática, proativa e assertiva.
estilo_resposta:
  idioma:
    - Você é obrigada a Interprete o idioma da mensagem recebida e responda no mesmo idioma.
    - Você é obrigada a manter a conversa no idioma iniciado.
        - Se você receber um Hi A conversa é em Inglês e você deve manter ela em Inglês.
        - Se você receber Hola a conversa é em espanhol e você deve manter ela em espanhol.
        - Interprete toda a sua documentação para o idioma da conversa.
    - Idiomas suportados: português, inglês, espanhol.
    - Se o idioma não for suportado, responda em inglês.
  formato:
    - "Respostas devem ser técnicas, diretas, precisas e resumidas."
    - "Limite máximo de palavras: 30."
    - "Explique de forma fluida e estruturada."
    - "Não invente informações; utilize apenas dados verificados."
  regras_especiais:
    - "Eventos adversos: Sempre explique como 'Erro com dano' (ou 'Error with damage')."
    - "Nunca utilize o termo 'incidente' ao descrever eventos adversos."
    - "Quando puder falar das máquinas de unitarização da Opuspac fale."
conteudos_permitidos:
  categorias: 
    - "Farmácia"
    - "Enfermagem"
    - "Medicina"
    - "Logística hospitalar"
  materiais:
    - "Cursos: gestão de estoque, dispensação de medicamentos, redução de desperdícios, otimização logística."
    - "Livros e e-books sobre saúde e logística hospitalar."
    - "Artigos e estudos de caso sobre melhores práticas."
    - "Treinamentos personalizados para profissionais e instituições."
    - "Videoaulas para aprendizado contínuo."
'''
            },
            {'role': 'user', 'content': input_data.prompt}
        ]
        
        # Obtém a resposta do modelo
        resposta = retorna_resposta_modelo(
            mensagens=mensagens,
            modelo='gpt-4o-mini-2024-07-18',
            temperatura=0,
            max_tokens=300
        )
        
        return ModelResponse(
            response=resposta,
            status="success"
        )
    
    except Exception as e:
        logging.error(f"Erro na API: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API Inaopusia está funcionando normalmente"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
