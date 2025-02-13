import re
from langdetect import detect
from unidecode import unidecode
import pickle
import streamlit as st
import openai
import os
import fitz
import logging
import time
import openai
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

PASTA_MENSAGEM = Path(__file__).parent / 'mensagens'
PASTA_MENSAGEM.mkdir(exist_ok=True)
CACHE_DESCONVERTE = {}

load_dotenv()
openai_key = st.secrets["OPENAI_API_KEY"]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_log.log"),
        logging.StreamHandler()
    ]
)

def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-4o-mini-2024-07-18', temperatura=0, stream=True, max_tokens=900):
    openai.api_key = openai_key
    
    start_time = time.time()
    logging.info(f"Processando mensagens com {len(mensagens)} entradas")
    
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


def converte_nome_mensagem(nome_mensagem):
    nome_arquivo = unidecode(nome_mensagem) 
    nome_arquivo = re.sub('\W+', '', nome_arquivo).lower()
    return nome_arquivo

def desconverte_nome_mensagem(nome_arquivo):
    if not nome_arquivo in CACHE_DESCONVERTE:
        nome_mensagem = ler_mensagem_por_nome_arquivo(nome_arquivo, key='nome_mensagem')
        CACHE_DESCONVERTE[nome_arquivo] = nome_mensagem
    return CACHE_DESCONVERTE[nome_arquivo]

def retorna_nome_da_mensagem(mensagens):
    nome_mensagem = ''
    for mensagem in mensagens:
        if mensagem['role'] == 'user':
            nome_mensagem = mensagem['content'][:30]
            break
    return nome_mensagem

##def salvar_mensagens(mensagens):
  ##  if len(mensagens) == 0:
    ##    return False
  ##  nome_mensagem = retorna_nome_da_mensagem(mensagens)
  ##  nome_arquivo = converte_nome_mensagem(nome_mensagem)
  ##  arquivo_salvar = {'nome_mensagem': nome_mensagem, 'nome_arquivo': nome_arquivo, 'mensagem': mensagens}
  ##  with open(PASTA_MENSAGEM / nome_arquivo, 'wb') as f:
  ##      pickle.dump(arquivo_salvar, f)

def ler_mensagem_por_nome_arquivo(nome_arquivo, key='mensagens'):
    with open(PASTA_MENSAGEM / nome_arquivo, 'rb') as f:
        mensagens = pickle.load(f)
    return mensagens[key]

def ler_mensagens(mensagens, key='mensagem'):
    if len(mensagens) == 0:
        return []
    nome_mensagem = retorna_nome_da_mensagem(mensagens)
    nome_arquivo = converte_nome_mensagem(nome_mensagem)
    
    arquivo_path = PASTA_MENSAGEM / nome_arquivo
    if not arquivo_path.is_file():
        return []
    
    try:
        with open(arquivo_path, 'rb') as f:
            mensagens = pickle.load(f)
        return mensagens[key]
    except EOFError:
        return []
    except Exception as e:
        st.error(f"Erro ao ler mensagens: {str(e)}")
        return []
        
def listar_conversas():
    conversas = list(PASTA_MENSAGEM.glob('*'))
    conversas = sorted(conversas, key=lambda item: item.stat().st_mtime_ns, reverse=True)
    return [c.stem for c in conversas]

def carregar_pdfs(pasta):
    textos = {}
    try:
        if not os.path.exists(pasta):
            print(f"A pasta '{pasta}' não foi encontrada.")
            return textos

        for arquivo in os.listdir(pasta):
            if arquivo.endswith('.pdf'):
                caminho = os.path.join(pasta, arquivo)
                print(f"Lendo o arquivo: {caminho}")
                documento = fitz.open(caminho)
                texto = ""
                for pagina in documento:
                    texto += pagina.get_text()
                textos[arquivo] = texto
            else:
                print(f"Ignorando o arquivo não-PDF: {arquivo}")
    except Exception as e:
        print(f"Ocorreu um erro ao carregar os PDFs: {e}")
    return textos

def buscar_resposta(textos, pergunta):
    respostas_encontradas = []
    for arquivo, texto in textos.items():
        if pergunta.lower() in texto.lower():
            respostas_encontradas.append(f"Resposta encontrada no arquivo {arquivo}: {texto[:100]}...")
    return respostas_encontradas if respostas_encontradas else ["Nenhuma resposta encontrada."]

def inicializacao():
    if not 'mensagens' in st.session_state:
        st.session_state['mensagens'] = []
    if not 'conversa_atual' in st.session_state:
        st.session_state['conversa_atual'] = ''
        
def exibe_mensagem_assistente(conteudo):
    col1, col2 = st.columns([1, 9])
    with col1:
        st.image("ina.png", width=40)
    with col2:
        st.markdown(conteudo)

def exibe_mensagem_usuario(conteudo):
    col1, col2 = st.columns([1, 9])
    with col1:
        st.image('icon_person_no_bg.png', width=40)
    with col2:
        st.markdown(f"**Você:** {conteudo}")

def pagina_principal():
    if 'mensagens' not in st.session_state:
        st.session_state['mensagens'] = []

    mensagens = st.session_state['mensagens']
    textos_pdf = carregar_pdfs('documents')

    st.header(' Ina', divider=True)

    if len(mensagens) == 0:
        mensagem_inicial = {'role': 'assistant', 'content': 'Olá, meu nome é Ina, eu sou a inteligência Artificial da Opuspac University, como eu posso te ajudar hoje?'}
        mensagens.append(mensagem_inicial)

    for mensagem in mensagens:
        if mensagem['role'] == 'assistant':
            exibe_mensagem_assistente(mensagem['content'])
        else:
            exibe_mensagem_usuario(mensagem['content'])

    prompt = st.chat_input('Escreva uma mensagem...')
    if prompt:
        idioma = detect(prompt)
        nova_mensagem = {'role': 'user', 'content': prompt}
        exibe_mensagem_usuario(nova_mensagem['content'])
        mensagens.append(nova_mensagem)

        respostas = buscar_resposta(textos_pdf, prompt)

        mensagens_para_modelo = mensagens.copy()
        mensagens_para_modelo.append({'role': 'system', 'content': f'''
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

Conteudos_proibidos:
    Tópicos:
        - Você não pode comentar de outros assuntos, só pode comentar e conversar sobre o que já foi passado.
        - Não de receitas de nenhum tipo de alimento.
        - Não fale de conteúdos que não sejam aquelas voltado para as áreas de Farmácia, Enfermagem, Medicina e Logística hospitalar
diretrizes_respostas:
  referencias:
    - "Mencione autores apenas se relevante, sem repetição excessiva."
    - "Exemplo: 'Como abordado por Victor Basso sobre segurança do paciente…'."
  foco:
    - "Priorize informações essenciais, sem detalhes desnecessários."
    - "Mantenha respostas resumidas e objetivas."
autores_e_obras:
  autores:
    - "Victor Basso"
    - "Marcelo A. Murad"
    - "Fernando Capabianco"
    - "Claudia Caduro"
    - "Carlos Vageler"
  obras:
    - "Administração de Medicamentos para a Segurança do Paciente - Victor Basso"
    - "Cultura Lean Healthcare - Victor Basso"
    - "Gestão Hospitalar em Tempos de Crise - Victor Basso"
    - "O Dilema do Gestor - Victor Basso"
    - "O Sistema Opuspac - Victor Basso"
    - "Segurança do Paciente - Victor Basso"
    - "A Farmácia Lean - Marcelo A. Murad"
    - "Logística Hospitalar - Fernando Capabianco"
    - "Gestão de Estoque e Acuracidade em Farmácia Hospitalar - Claudia Caduro"
    - "Aplicação dos Princípios ESG em Farmácias Hospitalares - Carlos Vageler"
objetivos_opuspac_university:
  - "Qualificar profissionais para habilidades específicas em logística hospitalar."
  - "Disseminar as melhores práticas na área da saúde."
  - "Reduzir desperdícios e otimizar custos nas instituições de saúde."
  - "Melhorar a qualidade do atendimento, com foco na segurança do paciente."
publico_alvo:
  - "Farmacêuticos"
  - "Enfermeiros"
  - "Técnicos em farmácia"
  - "Gestores hospitalares"
  - "Alunos da área da saúde"


        '''})

        resposta_completa = retorna_resposta_modelo(mensagens_para_modelo, openai_key, stream=True, max_tokens=300)

        # Se o stream for utilizado, a resposta já é concatenada corretamente em resposta_completa
        exibe_mensagem_assistente(resposta_completa)

        nova_mensagem = {'role': 'assistant', 'content': resposta_completa}
        mensagens.append(nova_mensagem)

        st.session_state['mensagens'] = mensagens
        ##salvar_mensagens(mensagens)


# A parte das abas foi removida
# def tab_conversas(tab):
#     tab.button('Nova conversa', on_click=seleciona_conversa, args=('', ), use_container_width=True)
#     tab.markdown('')
#     conversas = listar_conversas()
#     for nome_arquivo in conversas:
#         nome_mensagem = desconverte_nome_mensagem(nome_arquivo).capitalize()
#         if len(nome_mensagem) == 30:
#             nome_mensagem += '...'
#         tab.button(desconverte_nome_mensagem(nome_arquivo).capitalize(), on_click=seleciona_conversa, args=(nome_arquivo, ), disabled=nome_arquivo==st.session_state['conversa_atual'], use_container_width=True)

# def seleciona_conversa(nome_arquivo):
#     if nome_arquivo == '':
#         st.session_state.mensagens = []
#     else:
#         mensagem = ler_mensagem_por_nome_arquivo(nome_arquivo, key='mensagem')
#         st.session_state.mensagens = mensagem
#     st.session_state['conversa_atual'] = nome_arquivo

def main():
    inicializacao()
    pagina_principal()
    # Removido a parte das abas
    # tab1, tab2 = st.sidebar.tabs(['Conversas', 'Configurações'])
    # tab_conversas(tab1)

if __name__ == '__main__':
    main()
