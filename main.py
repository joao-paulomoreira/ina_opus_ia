import re
from langdetect import detect
from unidecode import unidecode
import streamlit as st
import openai
import os
import fitz
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Importar logger simples
from simple_logger import get_logger

# Configurar logger
logger = get_logger()

st.markdown("""
            <style>
                .st-emotion-cache-6shykm{
                    padding: 1rem 1rem 5.5rem;
                }
            </style>
            """, unsafe_allow_html=True)

logger.info("Aplicação iniciada")

# Carregar chave da API
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
    logger.info("API key carregada do Streamlit secrets")
except:
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    logger.info("API key carregada do .env")

# Carrega todo o treinamento no modelo
def carregar_instrucoes_sistema():
    """Carrega todo o treinamento do modelo a partir de um arquivo externo"""
    try:
        caminho = os.path.join(os.path.dirname(__file__), 'system_instructions.txt')
        with open(caminho, 'r', encoding='utf-8') as file:
            instrucoes = file.read()
            logger.info(f"Instruções carregadas - {len(instrucoes)} caracteres")
            return instrucoes
    except Exception as e:
        logger.error(f"Erro ao carregar instruções: {e}")
        return "Você é uma assistente da equipe comercial da Opuspac. Responda de maneira breve e resumida."

# Processa a pergunta do e a maneira como será a resposta do modelo
def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-4o-mini-2024-07-18', temperatura=0.2, stream=True, max_tokens=900):
    openai.api_key = openai_key
    
    start_time = time.time()
    logger.info(f"Processando com modelo {modelo}")
    
    try:
        if stream:
            response_stream = openai.ChatCompletion.create(
                model=modelo,
                messages=mensagens,
                temperature=temperatura,
                max_tokens=max_tokens,
                stream=True
            )
            
            resposta_completa = ''
            for chunk in response_stream:
                if isinstance(chunk, dict) and 'choices' in chunk and len(chunk['choices']) > 0:
                    delta = chunk['choices'][0].get('delta', {})
                    resposta_completa += delta.get('content', '')
                    
            elapsed_time = time.time() - start_time
            logger.info(f"Resposta processada em {elapsed_time:.2f}s")
            
            # Manter arquivo de performance existente
            with open("processing_rate.txt", "a") as txt_file:
                txt_file.write(f'Resposta processada em {elapsed_time:.2f} segundos\n')
                
            return resposta_completa
        else:
            response = openai.ChatCompletion.create(
                model=modelo,
                messages=mensagens,
                temperature=temperatura,
                max_tokens=max_tokens
            )
            elapsed_time = time.time() - start_time
            logger.info(f"Resposta processada em {elapsed_time:.2f}s (não-stream)")
            return response['choices'][0]['message']['content']
            
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        return f"Erro ao processar: {str(e)}"
    
# Carrega pastas com PDFs
def carregar_pdfs(pasta):
    textos = {}
    try:
        if not os.path.exists(pasta):
            logger.warning(f"Pasta '{pasta}' não encontrada")
            return textos
    
        arquivos_pdf = [f for f in os.listdir(pasta) if f.endswith('.pdf')]
        logger.info(f"Encontrados {len(arquivos_pdf)} PDFs")
        
        for arquivo in arquivos_pdf:
            try:
                caminho = os.path.join(pasta, arquivo)
                logger.info(f'Carregando PDF: {arquivo}')
                documento = fitz.open(caminho)
                texto = ""
                for pagina in documento:
                    texto += pagina.get_text()
                textos[arquivo] = texto
                logger.info(f'PDF {arquivo} carregado - {len(texto)} caracteres')
            except Exception as e:
                logger.error(f'Erro ao carregar {arquivo}: {e}')
                
    except Exception as e:
        logger.error(f'Erro ao carregar PDFs: {e}')
    
    return textos

# Busca respostas nos PDFs
def buscar_resposta(textos, pergunta):
    logger.info(f"Buscando: '{pergunta[:50]}...'")
    respostas_encontradas = []
    for arquivo, texto in textos.items():
        if pergunta.lower() in texto.lower():
            respostas_encontradas.append(f"Resposta encontrada no arquivo {arquivo}: {texto[:100]}...")
            logger.info(f"Resposta encontrada em {arquivo}")
    
    if not respostas_encontradas:
        logger.info("Nenhuma resposta encontrada nos PDFs")
        return ["Nenhuma resposta encontrada."]
    
    return respostas_encontradas

# Responsavél por toda parte de comunicação/respostas ETC
def inicializacao():
    if not 'mensagens' in st.session_state:
        st.session_state['mensagens'] = []
        logger.info("Sessão inicializada")
        
def exibe_mensagem_assistente(conteudo):
    col1, col2 = st.columns([1, 9])
    with col1:
        if os.path.exists("ina.png"):
            st.image("ina.png", width=40)
    with col2:
        st.markdown(f"**IA:** {conteudo}")

def exibe_mensagem_usuario(conteudo):
    col1, col2 = st.columns([1, 9])
    with col1:
        if os.path.exists("icon_person_no_bg.png"):
            st.image('icon_person_no_bg.png', width=40)
    with col2:
        st.markdown(f"**Você:** {conteudo}")

# Layout principal do modelo
def pagina_principal():
    if 'mensagens' not in st.session_state:
        st.session_state['mensagens'] = []
        
    mensagens = st.session_state['mensagens']
    textos_pdf = carregar_pdfs('documents')
    
    st.header('Assistente Comercial', divider=True)
    
    if len(mensagens) == 0:
        mensagem_inicial = {'role': 'assistant', 'content': 'Me faça perguntas relacionadas as máquinas.'}
        mensagens.append(mensagem_inicial)
        
    for mensagem in mensagens:
        if mensagem['role'] == 'assistant':
            exibe_mensagem_assistente(mensagem['content'])
        else:
            exibe_mensagem_usuario(mensagem['content'])
            
    prompt = st.chat_input('Faça uma pergunta...')
    
    if prompt:
        logger.info(f"Nova pergunta: '{prompt[:50]}...'")
        
        try:
            idioma = detect(prompt)
            logger.info(f"Idioma detectado: {idioma}")
        except:
            idioma = 'desconhecido'
            logger.warning("Erro na detecção de idioma")
        
        nova_mensagem = {'role': 'user', 'content': prompt}
        exibe_mensagem_usuario(nova_mensagem['content'])
        mensagens.append(nova_mensagem)
        
        try:
            respostas = buscar_resposta(textos_pdf, prompt)
            
            mensagens_para_modelo = mensagens.copy()
            instrucoes_sistema = carregar_instrucoes_sistema()
            mensagens_para_modelo.append({'role': 'system', 'content': instrucoes_sistema})
            
            resposta_completa = retorna_resposta_modelo(mensagens_para_modelo, openai_key, stream=True, max_tokens=900)
            
            exibe_mensagem_assistente(resposta_completa)
            
            nova_mensagem = {'role': 'assistant', 'content': resposta_completa}
            mensagens.append(nova_mensagem)
            
            logger.info("Interação concluída com sucesso")
            
        except Exception as e:
            logger.error(f"Erro na interação: {e}")
            erro_msg = f"Erro: {str(e)}"
            exibe_mensagem_assistente(erro_msg)
            mensagens.append({'role': 'assistant', 'content': erro_msg})
        
        st.session_state['mensagens'] = mensagens
        
# Roda efetivamente o modelo
def main():
    try:
        logger.info("=== INÍCIO DA SESSÃO ===")
        inicializacao()
        pagina_principal()
    except Exception as e:
        logger.error(f"Erro crítico: {e}")
        st.error(f"Erro na aplicação: {str(e)}")

if __name__ == '__main__':
    main()