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
import json

# Configuração de logs no arquivo app_log e no terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_log.log"),
        logging.StreamHandler()
    ]
)

# Carregar chave da API
try:
    openai_key = st.secrets["OPENAI_API_KEY"]
except:
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")

# Carrega todo o treinamento no modelo
def carregar_instrucoes_sistema():
    """Carrega todo o treinamento do modelo a partir de um arquivo externo"""
    try:
        caminho = os.path.join(os.path.dirname(__file__), 'system_instructions.txt')
        with open(caminho, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logging.error(f"Erro ao carregar instruções do sistema: {e}")
        return "Você é uma assistente da equipe comercial da Opuspac. Responda de maneira breve e resumida."

# Função para iniciar o fine-tuning do modelo
def iniciar_fine_tuning():
    try:
        # Verifica se o arquivo existe
        jsonl_file = "fine_tuning.jsonl"
        if not os.path.exists(jsonl_file):
            logging.error(f"Arquivo JSONL não encontrado: {jsonl_file}")
            return "Erro: Arquivo fine_tuning.jsonl não encontrado."
        
        # Faz o upload do arquivo para a API
        logging.info(f"Iniciando upload do arquivo {jsonl_file}")
        file_response = openai.File.create(
            file=open(jsonl_file, "rb"),
            purpose="fine-tune"
        )
        file_id = file_response.id
        
        # Inicia o fine-tuning usando o arquivo enviado
        logging.info(f"Iniciando processo de fine-tuning com o arquivo {file_id}")
        fine_tune_response = openai.FineTuningJob.create(
            training_file=file_id,
            model="gpt-4o-mini-2024-07-18"
        )
        
        fine_tune_id = fine_tune_response.id
        logging.info(f"Fine-tuning iniciado com sucesso. ID: {fine_tune_id}")
        
        # Salva o ID para consultas posteriores
        with open("fine_tune_id.txt", "w") as f:
            f.write(fine_tune_id)
            
        return f"Fine-tuning iniciado com sucesso! ID: {fine_tune_id}"
    
    except Exception as e:
        logging.error(f"Erro ao iniciar fine-tuning: {e}")
        return f"Erro ao iniciar fine-tuning: {str(e)}"

# Função para verificar o status do fine-tuning
def verificar_status_fine_tuning():
    try:
        # Tenta ler o ID do arquivo
        if os.path.exists("fine_tune_id.txt"):
            with open("fine_tune_id.txt", "r") as f:
                fine_tune_id = f.read().strip()
        else:
            return "Nenhum fine-tuning encontrado. Inicie um fine-tuning primeiro."
        
        # Consulta o status na API
        logging.info(f"Verificando status do fine-tuning: {fine_tune_id}")
        response = openai.FineTuningJob.retrieve(fine_tune_id)
        
        # Formata a resposta para exibição
        status = response.status
        model = response.fine_tuned_model if response.fine_tuned_model else "Ainda não disponível"
        
        # Se o fine-tuning foi concluído, salva o modelo para uso
        if status == "succeeded" and response.fine_tuned_model:
            with open("fine_tuned_model.txt", "w") as f:
                f.write(response.fine_tuned_model)
        
        return f"Status: {status}\nModelo Fine-tuned: {model}"
    
    except Exception as e:
        logging.error(f"Erro ao verificar status: {e}")
        return f"Erro ao verificar status: {str(e)}"

# Processa a pergunta do e a maneira como será a resposta do modelo
def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-4o-mini-2024-07-18', temperatura=0, stream=True, max_tokens=900):
    # Verifica se existe um modelo fine-tuned para usar
    if os.path.exists("fine_tuned_model.txt"):
        with open("fine_tuned_model.txt", "r") as f:
            fine_tuned_model = f.read().strip()
            if fine_tuned_model:
                modelo = fine_tuned_model
                logging.info(f"Usando modelo fine-tuned: {modelo}")
    
    openai.api_key = openai_key
    
    start_time = time.time()
    logging.info(f"Processando mensagem com {len(mensagens)} entradas")
    
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
        processing_rate = f'Resposta processada com sucesso em {elapsed_time:.2f} segundos'
        
        with open("processing_rate.txt", "a") as txt_file:
            txt_file.write(processing_rate + "\n")
            
        logging.info(processing_rate)
        
        return resposta_completa
    else:
        response = openai.ChatCompletion.create(
            model=modelo,
            messages=mensagens,
            temperature=temperatura,
            max_tokens=max_tokens
        )
        return response['choices'][0]['message']['content']
    
# Carrega pastas com PDFs
def carregar_pdfs(pasta):
    textos = {}
    try:
        if not os.path.exists(pasta):
            print(f"A pasta '{pasta}' não foi encontrada")
            return textos
    
        for arquivo in os.listdir(pasta):
            if arquivo.endswith('.pdf'):
                caminho = os.path.join(pasta, arquivo)
                print(f'Lendo o arquivo: {caminho}')
                documento = fitz.open(caminho)
                texto = ""
                for pagina in documento:
                    texto += pagina.get_text()
                textos[arquivo] = texto
            else:
                print(f'Ignorando o arquivo não-PDF: {arquivo}')
    except Exception as e:
        print(f'Ocorreu um erro ao carregar os PDFs: {e}')
    return textos

# Busca respostas nos PDFs
def buscar_resposta(textos, pergunta):
    respostas_encontradas = []
    for arquivo, texto in textos.items():
        if pergunta.lower() in texto.lower():
            respostas_encontradas.append(f"Resposta encontrada no arquivo {arquivo}: {texto[:100]}...")
    return respostas_encontradas if respostas_encontradas else ["Nenhuma resposta encontrada."]

# Responsavél por toda parte de comunicação/respostas ETC
def inicializacao():
    if not 'mensagens' in st.session_state:
        st.session_state['mensagens'] = []
        
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
    
    # Adiciona botões de fine-tuning na sidebar
    with st.sidebar:
        st.header("Fine-Tuning")
        if st.button("Iniciar Fine-Tuning"):
            resultado = iniciar_fine_tuning()
            st.info(resultado)
            
        if st.button("Verificar Status"):
            status = verificar_status_fine_tuning()
            st.info(status)
    
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
        idioma = detect(prompt)
        nova_mensagem = {'role': 'user', 'content': prompt}
        exibe_mensagem_usuario(nova_mensagem['content'])
        mensagens.append(nova_mensagem)
        
        respostas = buscar_resposta(textos_pdf, prompt)
        
        mensagens_para_modelo = mensagens.copy()
        
        instrucoes_sistema = carregar_instrucoes_sistema()
        
        mensagens_para_modelo.append({'role': 'system', 'content': instrucoes_sistema})
        
        resposta_completa = retorna_resposta_modelo(mensagens_para_modelo, openai_key, stream=True, max_tokens=900)
        
        exibe_mensagem_assistente(resposta_completa)
        
        nova_mensagem = {'role': 'assistant', 'content': resposta_completa}
        mensagens.append(nova_mensagem)
        
        st.session_state['mensagens'] = mensagens
        
# Roda efetivamente o modelo
def main():
    inicializacao()
    pagina_principal()

if __name__ == '__main__':
    main()