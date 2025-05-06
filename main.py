import re
from langdetect import detect
from unidecode import unidecode
import streamlit as st
import openai
import os
import fitz
import logging
import time
import json
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

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

# Inicializa o cliente OpenAI
openai.api_key = openai_key

# Configuração do modelo fine-tuned
FINE_TUNED_MODEL = "ft:gpt-3.5-turbo-0125:opuspac::8BxgTr4S"  # ID do modelo fine-tuned

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

# Função para carregar o arquivo JSONL do fine-tuning
def carregar_dados_fine_tuning():
    try:
        dados = []
        with open('fine_tuning.jsonl', 'r', encoding='utf-8') as file:
            for line in file:
                dados.append(json.loads(line))
        logging.info(f"Arquivo de fine-tuning carregado com {len(dados)} exemplos")
        return dados
    except Exception as e:
        logging.error(f"Erro ao carregar dados de fine-tuning: {e}")
        return []

# Processa a pergunta e a maneira como será a resposta do modelo
def retorna_resposta_modelo(mensagens, openai_key, modelo=None, temperatura=0, stream=True, max_tokens=900, usar_fine_tuned=True):
    openai.api_key = openai_key
    
    # Define o modelo a ser usado (fine-tuned ou padrão)
    if usar_fine_tuned and FINE_TUNED_MODEL:
        modelo_usado = FINE_TUNED_MODEL
    else:
        modelo_usado = modelo if modelo else 'gpt-4o-mini-2024-07-18'
    
    start_time = time.time()
    logging.info(f"Processando mensagem com modelo {modelo_usado} e {len(mensagens)} entradas")
    
    try:
        if stream:
            response_stream = openai.ChatCompletion.create(
                model=modelo_usado,
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
                model=modelo_usado,
                messages=mensagens,
                temperature=temperatura,
                max_tokens=max_tokens
            )
            return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Erro ao processar resposta do modelo: {e}")
        return f"Ocorreu um erro ao processar sua solicitação: {str(e)}"
    
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

# Função para realizar o upload do arquivo de fine-tuning para a OpenAI
def upload_file_for_fine_tuning():
    try:
        response = openai.File.create(
            file=open("fine_tuning.jsonl", "rb"),
            purpose="fine-tune"
        )
        file_id = response.id
        logging.info(f"Arquivo enviado com sucesso. ID: {file_id}")
        return file_id
    except Exception as e:
        logging.error(f"Erro ao enviar arquivo para fine-tuning: {e}")
        return None

# Função para criar um trabalho de fine-tuning
def create_fine_tuning_job(file_id, model="gpt-3.5-turbo-0125"):
    try:
        response = openai.FineTuningJob.create(
            training_file=file_id,
            model=model,
            suffix="opuspac"
        )
        job_id = response.id
        logging.info(f"Trabalho de fine-tuning criado. ID: {job_id}")
        return job_id
    except Exception as e:
        logging.error(f"Erro ao criar trabalho de fine-tuning: {e}")
        return None

# Função para verificar o status do trabalho de fine-tuning
def check_fine_tuning_status(job_id):
    try:
        response = openai.FineTuningJob.retrieve(job_id)
        status = response.status
        logging.info(f"Status do trabalho de fine-tuning: {status}")
        
        if status == "succeeded":
            fine_tuned_model = response.fine_tuned_model
            logging.info(f"Modelo fine-tuned criado: {fine_tuned_model}")
            return fine_tuned_model
        
        return None
    except Exception as e:
        logging.error(f"Erro ao verificar status do trabalho de fine-tuning: {e}")
        return None

# Responsavél por toda parte de comunicação/respostas ETC
def inicializacao():
    if not 'mensagens' in st.session_state:
        st.session_state['mensagens'] = []
    
    if not 'fine_tuned_model' in st.session_state:
        st.session_state['fine_tuned_model'] = FINE_TUNED_MODEL
        
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
    
    # Adicionar opção para usar o modelo fine-tuned
    usar_fine_tuned = st.sidebar.checkbox('Usar modelo fine-tuned', value=True)
    
    # Exibir informações sobre o modelo fine-tuned no sidebar
    if usar_fine_tuned:
        st.sidebar.info(f"Usando modelo fine-tuned: {st.session_state.get('fine_tuned_model', FINE_TUNED_MODEL)}")
    
    # Botão para iniciar o processo de fine-tuning (apenas para testes)
    if st.sidebar.button("Iniciar Novo Fine-Tuning"):
        with st.spinner("Iniciando processo de fine-tuning..."):
            file_id = upload_file_for_fine_tuning()
            if file_id:
                job_id = create_fine_tuning_job(file_id)
                if job_id:
                    st.sidebar.success(f"Fine-tuning iniciado. Job ID: {job_id}")
                    st.session_state['job_id'] = job_id
                else:
                    st.sidebar.error("Erro ao criar job de fine-tuning")
            else:
                st.sidebar.error("Erro ao enviar arquivo")
    
    # Botão para verificar status do fine-tuning (apenas para testes)
    if 'job_id' in st.session_state and st.sidebar.button("Verificar Status do Fine-Tuning"):
        with st.spinner("Verificando status..."):
            model_id = check_fine_tuning_status(st.session_state['job_id'])
            if model_id:
                st.sidebar.success(f"Fine-tuning concluído! Modelo: {model_id}")
                st.session_state['fine_tuned_model'] = model_id
            else:
                st.sidebar.info("Fine-tuning ainda em andamento...")
    
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
        
        resposta_completa = retorna_resposta_modelo(
            mensagens_para_modelo, 
            openai_key, 
            stream=True, 
            max_tokens=900,
            usar_fine_tuned=usar_fine_tuned
        )
        
        exibe_mensagem_assistente(resposta_completa)
        
        nova_mensagem = {'role': 'assistant', 'content': resposta_completa}
        mensagens.append(nova_mensagem)
        
        st.session_state['mensagens'] = mensagens

# Função para realizar o fine-tuning (pode ser chamada fora da interface)
def realizar_fine_tuning():
    file_id = upload_file_for_fine_tuning()
    if file_id:
        job_id = create_fine_tuning_job(file_id)
        if job_id:
            logging.info(f"Fine-tuning iniciado. Job ID: {job_id}")
            # Aguardar conclusão (em produção, isso deve ser assíncrono)
            import time
            model_id = None
            while not model_id:
                time.sleep(60)  # Verificar a cada minuto
                model_id = check_fine_tuning_status(job_id)
            logging.info(f"Fine-tuning concluído. Modelo: {model_id}")
            return model_id
    return None
        
# Roda efetivamente o modelo
def main():
    inicializacao()
    pagina_principal()

if __name__ == '__main__':
    main()
    
realizar_fine_tuning()