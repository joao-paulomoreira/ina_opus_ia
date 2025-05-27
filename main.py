import re
from langdetect import detect
from unidecode import unidecode
import streamlit as st
import openai
import os
import fitz
import logging
import time
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

st.markdown("""
            <style>
                .st-emotion-cache-6shykm{
                    padding: 1rem 1rem 5.5rem;
                }
            </style>
            """, unsafe_allow_html=True)

# Configuração de logs simples
def setup_logging():
    # Criar diretório de logs se não existir
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/app.log", encoding='utf-8'),
            logging.StreamHandler()
        ],
        force=True  # Força reconfiguração se já existe
    )
    return logging.getLogger('OpuspacApp')

# Configurar logger
logger = setup_logging()
logger.info("Aplicação iniciada")

# Carregar chave da API
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
    logger.info("API key carregada do Streamlit secrets")
except:
    try:
        load_dotenv()
        openai_key = os.getenv("OPENAI_API_KEY")
        logger.info("API key carregada do .env")
    except Exception as e:
        logger.error(f"Erro ao carregar API key: {e}")
        openai_key = None

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
    if not openai_key:
        logger.error("API key não encontrada")
        return "Erro: API key não configurada"
        
    openai.api_key = openai_key
    
    start_time = time.time()
    logger.info(f"Processando com modelo {modelo} - {len(mensagens)} mensagens")
    
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
            try:
                with open("processing_rate.txt", "a", encoding='utf-8') as txt_file:
                    txt_file.write(f'Resposta processada em {elapsed_time:.2f} segundos\n')
            except Exception as e:
                logger.warning(f"Erro ao escrever processing_rate.txt: {e}")
                
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
        elapsed_time = time.time() - start_time
        logger.error(f"Erro na API após {elapsed_time:.2f}s: {e}")
        return f"Erro ao processar: {str(e)}"
    
# Carrega pastas com PDFs
def carregar_pdfs(pasta):
    textos = {}
    try:
        if not os.path.exists(pasta):
            logger.warning(f"Pasta '{pasta}' não encontrada")
            return textos
    
        arquivos_pdf = [f for f in os.listdir(pasta) if f.endswith('.pdf')]
        logger.info(f"Encontrados {len(arquivos_pdf)} arquivos PDF na pasta '{pasta}'")
        
        for arquivo in arquivos_pdf:
            try:
                caminho = os.path.join(pasta, arquivo)
                logger.info(f'Carregando PDF: {arquivo}')
                documento = fitz.open(caminho)
                texto = ""
                for pagina in documento:
                    texto += pagina.get_text()
                textos[arquivo] = texto
                logger.info(f'PDF {arquivo} carregado - {len(texto)} caracteres, {documento.page_count} páginas')
                documento.close()
            except Exception as e:
                logger.error(f'Erro ao carregar {arquivo}: {e}')
                
    except Exception as e:
        logger.error(f'Erro geral ao carregar PDFs: {e}')
    
    logger.info(f"Carregamento concluído - {len(textos)} PDFs processados")
    return textos

# Busca respostas nos PDFs
def buscar_resposta(textos, pergunta):
    if not textos:
        logger.info("Nenhum PDF disponível para busca")
        return ["Nenhum documento PDF disponível para consulta."]
        
    logger.info(f"Buscando: '{pergunta[:50]}...' em {len(textos)} documentos")
    
    respostas_encontradas = []
    for arquivo, texto in textos.items():
        if pergunta.lower() in texto.lower():
            respostas_encontradas.append(f"Resposta encontrada no arquivo {arquivo}: {texto[:100]}...")
            logger.info(f"Resposta encontrada em {arquivo}")
    
    if not respostas_encontradas:
        logger.info("Nenhuma resposta encontrada nos PDFs")
        return ["Nenhuma resposta encontrada."]
    
    logger.info(f"{len(respostas_encontradas)} respostas encontradas")
    return respostas_encontradas

# Responsável por toda parte de comunicação/respostas
def inicializacao():
    if 'mensagens' not in st.session_state:
        st.session_state['mensagens'] = []
        logger.info("Estado da sessão inicializado")
        
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
    
    # Carregar PDFs uma vez por sessão
    if 'textos_pdf' not in st.session_state:
        st.session_state['textos_pdf'] = carregar_pdfs('documents')
    textos_pdf = st.session_state['textos_pdf']
    
    st.header('Assistente Comercial', divider=True)
    
    if len(mensagens) == 0:
        mensagem_inicial = {'role': 'assistant', 'content': 'Me faça perguntas relacionadas às máquinas.'}
        mensagens.append(mensagem_inicial)
        logger.info("Mensagem inicial adicionada")
        
    for mensagem in mensagens:
        if mensagem['role'] == 'assistant':
            exibe_mensagem_assistente(mensagem['content'])
        else:
            exibe_mensagem_usuario(mensagem['content'])
            
    prompt = st.chat_input('Faça uma pergunta...')
    
    if prompt:
        start_time = time.time()
        logger.info(f"Nova pergunta: '{prompt[:50]}...'")
        
        try:
            idioma = detect(prompt)
            logger.info(f"Idioma detectado: {idioma}")
        except Exception as e:
            idioma = 'desconhecido'
            logger.warning(f"Erro na detecção de idioma: {e}")
        
        nova_mensagem = {'role': 'user', 'content': prompt}
        exibe_mensagem_usuario(nova_mensagem['content'])
        mensagens.append(nova_mensagem)
        
        try:
            # Buscar em PDFs
            respostas = buscar_resposta(textos_pdf, prompt)
            
            # Preparar mensagens para o modelo
            mensagens_para_modelo = mensagens.copy()
            instrucoes_sistema = carregar_instrucoes_sistema()
            mensagens_para_modelo.append({'role': 'system', 'content': instrucoes_sistema})
            
            # Obter resposta
            resposta_completa = retorna_resposta_modelo(mensagens_para_modelo, openai_key, stream=True, max_tokens=900)
            
            # Exibir resposta
            exibe_mensagem_assistente(resposta_completa)
            
            # Adicionar ao histórico
            nova_resposta = {'role': 'assistant', 'content': resposta_completa}
            mensagens.append(nova_resposta)
            
            interaction_time = time.time() - start_time
            logger.info(f"Interação concluída em {interaction_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Erro na interação: {e}")
            erro_msg = f"Erro ao processar sua pergunta: {str(e)}"
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
        logger.error(f"Erro crítico na aplicação: {e}")
        st.error(f"Erro na aplicação: {str(e)}")
    finally:
        logger.info("=== FIM DA SESSÃO ===")

if __name__ == '__main__':
    main()