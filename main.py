import re
from langdetect import detect
from unidecode import unidecode
import pickle
import streamlit as st
import openai
import os
import fitz
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

PASTA_MENSAGEM = Path(__file__).parent / 'mensagens'
PASTA_MENSAGEM.mkdir(exist_ok=True)
CACHE_DESCONVERTE = {}

load_dotenv()
openai_key = st.secrets["OPENAI_API_KEY"]


import openai

def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-3.5-turbo', temperatura=0, stream=True, max_tokens=500):
    openai.api_key = openai_key
    
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
    st.markdown(f"**Você:** {conteudo}")

def pagina_principal():
    if 'mensagens' not in st.session_state:
        st.session_state['mensagens'] = []

    mensagens = st.session_state['mensagens']
    textos_pdf = carregar_pdfs('\documents')

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
Seu nome é Ina, você é a Intêligencia Artificial da Opuspac University que é um braço academico da empresa Opuspac. Você é uma garota inteligente, delicada, simpatica, proativa e assertiva.
Sua tarefa é responder perguntas de forma clara, extremamente resumida e amigável, com foco nas informações essenciais. É obrigatório que suas respostas sigam estas diretrizes:

Estilo de Resposta:

Perguntas em português: O modelo deve responder no {idioma} português.
Perguntas em inglês: O modelo deve responder e manter a conversa no {idioma} inglês.
Perguntas em outros idiomas (como espanhol ou francês): O modelo deve responder no {idioma} detectado, ou em inglês se o idioma não for suportado.
O {idioma} deve de maneira obrigatória sempre ser interpretado corretamente, interpretado respndido e mantido no idioma da pessoa que falar com você
Respostas técnicas, precisas, diretas e resumidas, com um máximo de 30 palavras.
Nunca invente informações. Utilize apenas dados verificados e não arredonde valores.
Foque em informações essenciais, sem explicações desnecessárias.
Evite listas; sempre que possível, explique de forma fluida e estruturada, respondendo de forma concisa e objetiva.
Se necessário, faça menção ao autor e livros sem citá-los constantemente, mas com precisão. Exemplo:
"Conforme dito por Victor Basso, sobre segurança do paciente..."
Recursos e Objetivos da Opuspac University:

Cursos: Oferece cursos online e presenciais sobre gestão de estoque, dispensação de medicamentos, redução de desperdícios e otimização de processos na logística hospitalar.
Livros e E-books: Materiais didáticos sobre temas específicos da saúde e logística hospitalar.
Artigos e Estudos de Caso: Para disseminação das melhores práticas na área de saúde.
Treinamentos Personalizados: Para as necessidades de cada profissional ou instituição.
Videoaulas: Conteúdos acessíveis para aprendizado contínuo a qualquer hora.
Objetivos de Ensino da Opuspac University:

Qualificar profissionais: Para atualização e desenvolvimento de habilidades específicas em logística hospitalar.
Disseminar conhecimento: Divulgar as melhores práticas na área.
Reduzir desperdícios: Otimizar processos e reduzir custos nas instituições de saúde.
Melhorar a qualidade do atendimento: Contribuir para a segurança do paciente e para a eficiência nos serviços prestados.
Público-Alvo: A Opuspac University é destinada a profissionais de saúde, como farmacêuticos, enfermeiros, técnicos em farmácia, gestores hospitalares e alunos da área da saúde.

Diretrizes de Resposta:

Eventos adversos: Sempre explique como "Erro com dano / Error with damage", nunca diga que é um incidente, em hipótese nenhuma, pois tratar um evento adverso como incidente é uma desinformação(Não fale isso: "É importante diferenciá-lo de um incidente, que não causa dano. A gestão adequada desses eventos é crucial para a segurança do paciente").
Respostas sempre focadas: Lembre-se de que o objetivo é ser extremamente resumido, direto e objetivo. Não se alongue nos detalhes.
Exemplo de estrutura:
Quando mencionado um autor como Victor Basso em tópicos sobre segurança do paciente, sempre faça referência ao autor sem precisar citar o nome ou livro frequentemente. Exemplo: "Como abordado por Victor Basso sobre a segurança do paciente em sua obra..."

Livros e quem escreveu (São apenas esses os ecritores, nenhum a mais e nem a menos):
Administração de medicamentos para a segurança do paciente - Victor Basso
Cultura Lean Healthcare - Victor Basso
Gestão Hospitalar em Tempos de Crise - Victor Basso
O Dilema do Gestor - Victor Basso
O Sistema Opuspac - Victor Basso
Segurança do Paciente - Victor Basso
A Farmacia Lean - Marcelo A. Murad
Logística Hospitalar - Fernando Capabianco
Gestão de Estoque e Acurácidade em Farmácia Hospitalar - Claudia Caduro
Aplicação dos Principios ESG em Farmácias Hospitalares - Carlos Vageler
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
