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

st.set_page_config(
    page_title="Assistente Comercial",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items=None
)

# CSS super agressivo para remover todos os elementos indesejados
st.markdown("""
    <style>
    /* Remoção completa do footer */
    footer {display: none !important;}
    footer::after {display: none !important;}
    
    /* Remover absolutamente qualquer botão de perfil */
    .viewerBadge, .stDeployButton, div[data-testid="stToolbar"], div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"], .stTooltipIcon, img[alt="Streamlit logo"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        width: 0 !important;
        height: 0 !important;
        position: absolute !important;
        top: -9999px !important;
        left: -9999px !important;
        z-index: -9999 !important;
        pointer-events: none !important;
    }
    
    /* Remover todo e qualquer link para streamlit.io */
    a[href*="streamlit.io"], a[href*="streamlit.app"], div:has(> a[href*="streamlit.io"]),
    div:has(> a[href*="streamlit.app"]), span:has(> a[href*="streamlit"]), p:has(> a[href*="streamlit"]) {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Remover todos os elementos fixos no canto inferior direito */
    div[style*="position: fixed"][style*="bottom"], div[style*="position: absolute"][style*="bottom"],
    div[style*="position: fixed"][style*="right"], div[style*="position: absolute"][style*="right"],
    div:has(> a[href*="github"]), a[href*="github"], a[target="_blank"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* Cobrir o canto inferior direito com um bloco da mesma cor */
    body::after {
        content: '';
        position: fixed;
        bottom: 0;
        right: 0;
        width: 150px;
        height: 70px;
        background-color: #0e1117; /* cor de fundo igual à do Streamlit dark mode */
        z-index: 9999 !important;
    }
    
    /* Cobrir a barra superior direita com um bloco da mesma cor */
    body::before {
        content: '';
        position: fixed;
        top: 0;
        right: 0;
        width: 200px;
        height: 50px;
        background-color: #0e1117; /* cor de fundo igual à do Streamlit dark mode */
        z-index: 9999 !important;
    }
    
    /* Remover todos os scripts externos */
    script[src*="streamlit"], link[href*="streamlit"] {
        display: none !important;
    }
    
    /* Esconde todos os elementos que contenham 'streamlit' em qualquer atributo */
    [class*="streamlit"], [id*="streamlit"], [data-*="streamlit"], 
    [aria-*="streamlit"], [name*="streamlit"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# JavaScript ultra agressivo para remover elementos
st.markdown("""
    <script>
        // Função para remover TODOS os elementos indesejados
        function nukeUnwantedElements() {
            // Arrays de termos a procurar
            const terms = ['streamlit', 'github', 'profile', 'avatar', 'footer', 'badge', 'hosted'];
            
            // Remover links
            document.querySelectorAll('a').forEach(el => {
                if (el.href && terms.some(term => el.href.toLowerCase().includes(term))) {
                    if (el.parentNode) {
                        el.parentNode.removeChild(el);
                    }
                }
            });
            
            // Remover imagens
            document.querySelectorAll('img').forEach(el => {
                if (el.parentNode && (
                    el.alt && terms.some(term => el.alt.toLowerCase().includes(term)) ||
                    el.src && terms.some(term => el.src.toLowerCase().includes(term))
                )) {
                    el.parentNode.removeChild(el);
                }
            });
            
            // Remover botões
            document.querySelectorAll('button').forEach(el => {
                if (el.parentNode && (
                    el.textContent && terms.some(term => el.textContent.toLowerCase().includes(term)) ||
                    el.className && terms.some(term => el.className.toLowerCase().includes(term))
                )) {
                    el.parentNode.removeChild(el);
                }
            });
            
            // Remover elementos fixos no canto inferior
            document.querySelectorAll('div').forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.position === 'fixed' || style.position === 'absolute') {
                    if ((style.bottom === '0px' || parseInt(style.bottom) < 100) && 
                        (style.right === '0px' || parseInt(style.right) < 100)) {
                        if (el.parentNode) {
                            el.parentNode.removeChild(el);
                        }
                    }
                }
            });
            
            // Remover footer especificamente
            document.querySelectorAll('footer').forEach(el => {
                if (el.parentNode) {
                    el.parentNode.removeChild(el);
                }
            });
        }
        
        // Executar imediatamente, após carregamento e em intervalos
        nukeUnwantedElements();
        window.addEventListener('load', nukeUnwantedElements);
        
        // Executar a cada segundo por 10 segundos para garantir
        for (let i = 1; i <= 10; i++) {
            setTimeout(nukeUnwantedElements, i * 1000);
        }
    </script>
    """, unsafe_allow_html=True)

# Injetar uma técnica extrema: iframe sobreposto para esconder os elementos
st.markdown("""
    <div style="position: fixed; bottom: 0; right: 0; z-index: 9999; width: 200px; height: 80px; overflow: hidden;">
        <iframe src="about:blank" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; background-color: #0e1117;"></iframe>
    </div>
    
    <div style="position: fixed; top: 0; right: 0; z-index: 9999; width: 250px; height: 60px; overflow: hidden;">
        <iframe src="about:blank" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; background-color: #0e1117;"></iframe>
    </div>
    """, unsafe_allow_html=True)

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

# Processa a pergunta do e a maneira como será a resposta do modelo
def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-4o-mini-2024-07-18', temperatura=0, stream=True, max_tokens=900):
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
# OBS Optei por não seguir com arquivos PDFs, por isso não tem nenhum, um treinamento em txt é mais efetivo. Talvez sejam adicionados PDFs no futuro, mas no momento é apenas o treinamento em txt
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
