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

def retorna_resposta_modelo(mensagens, openai_key, modelo='gpt-4o-mini-2024-07-18', temperatura=0, stream=True, max_tokens=500):
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

limites_palavras:
  tipos_resposta:
    basica:
      limite: 30
      uso: "informações simples e diretas"
    tecnica:
      limite: 50
      uso: "explicações de procedimentos e conceitos"
    complexa:
      limite: 100
      uso: "procedimentos médicos detalhados"
  regras_contagem:
    incluir:
      - palavras_texto
      - termos_tecnicos
    excluir:
      - citacoes
      - referencias
  excecoes:
    permitir_excesso: ["procedimentos_criticos", "informacoes_seguranca"]

## 2. Estrutura de Categorias Detalhada

categorias:
  farmacia:
    subtopicos:
      - dispensacao:
          processos: ["unitarizacao", "controle", "distribuicao"]
          maquinas_opuspac: ["OpusFlex", "OpusCompact"]
      - estoque:
          processos: ["gestao", "controle", "acuracidade"]
          indicadores: ["giro", "cobertura", "obsolescencia"]
    overlap_rules:
      - principal: "usar categoria do processo principal"
      - secundario: "referenciar categorias relacionadas"
  
  enfermagem:
    subtopicos:
      - medicamentos:
          processos: ["administracao", "checagem", "controle"]
      - procedimentos:
          tipos: ["tecnicos", "assistenciais"]
    overlap_rules:
      - principal: "priorizar seguranca do paciente"
      - secundario: "incluir aspectos tecnicos relevantes"

## 3. Processamento de Idiomas

processamento_idiomas:
  prioridades:
    1: "precisao_tecnica"
    2: "contexto_idioma"
    3: "limite_palavras"
  
  regras_deteccao:
    metodo: "analise_primeiras_palavras"
    fallback: "portugues"
  
  manutencao_contexto:
    memoria_conversa: 5  # últimas 5 interações
    troca_permitida: "mediante_solicitacao"

  resolucao_conflitos:
    tecnico_vs_limite:
      acao: "priorizar_precisao"
      ajuste: "aumentar_limite_palavras"
    
    idioma_vs_termo_tecnico:
      acao: "manter_termo_original"
      adicional: "incluir_traducao_parenteses"

## 4. Sistema de Referências

sistema_referencias:
  formatos:
    curto:
      padrao: "Autor (ano)"
      uso: ["citacoes_rapidas", "mencoes_conceito"]
    
    completo:
      padrao: "Autor, Titulo, Ano"
      uso: ["primeira_mencao", "conceitos_principais"]
  
  regras_uso:
    quando_citar:
      - "conceitos_tecnicos_importantes"
      - "procedimentos_criticos"
      - "dados_estatisticos"
    
    contagem_palavras:
      citacoes_curtas: "nao_conta"
      citacoes_completas: "conta_parcialmente"
  
  autores_principais:
    victor_basso:
      obras_prioritarias: ["Segurança do Paciente", "O Sistema Opuspac"]
      temas_chave: ["seguranca", "unitarizacao", "processos"]

## 5. Diretrizes de Implementação

1. Sequência de Processamento:
   - Detectar idioma da entrada
   - Identificar categoria principal
   - Determinar tipo de resposta necessária
   - Aplicar limites e regras apropriados
   - Validar saída

2. Validação de Resposta:
   - Verificar conformidade com categorias
   - Confirmar precisão técnica
   - Validar contagem de palavras
   - Checar referências necessárias

3. Resolução de Conflitos:
   - Seguir árvore de decisão baseada em prioridades
   - Aplicar regras de exceção quando necessário
   - Documentar decisões de override

4. Manutenção de Qualidade:
   - Implementar testes automatizados
   - Realizar validações periódicas
   - Coletar métricas de conformidade

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
