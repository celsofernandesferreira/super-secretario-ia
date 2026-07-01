📦 1. Importação de Bibliotecas (Linhas 1 a 9)
Python
import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components
import logging
import sqlite3
from datetime import datetime
import streamlit as st: Ativa a framework web que constrói a interface gráfica (caixas de chat, botões, barras laterais) usando apenas Python, sem necessidade de HTML/CSS manual complexo.

import google.generativeai as genai: É o SDK oficial da Google para interagir com os modelos LLM do Gemini (enviar prompts, receber respostas, passar ferramentas).

import requests: Permite à aplicação efetuar pedidos HTTP REST (como o método GET) para consumir dados de APIs externas (neste caso, o sistema de tracking da Guimabus).

import os e import glob: O os gere interações com o sistema operativo (verificar se ficheiros existem) e o glob serve para pesquisar caminhos de ficheiros usando padrões (como procurar por todos os .md dentro de uma pasta).

import streamlit.components.v1 as components: Uma extensão do Streamlit que permite injetar código HTML5/JavaScript cru dentro de uma sandbox isolada (Iframe). Usado aqui para renderizar o jogo.

import logging: Módulo nativo para gerar telemetria e auditoria (escrever ficheiros de texto .log que registam eventos do sistema).

import sqlite3: Motor de base de dados relacional leve que armazena os dados localmente num ficheiro sem necessidade de configurar um servidor dedicado (como MySQL ou PostgreSQL).

from datetime import datetime: Fornece funções para capturar a data e hora exatas do sistema operativo, usadas nos carimbos de data (timestamps) da base de dados e logs.

🪵 2. Configuração de Logs e Telemetria (Linhas 11 a 18)
Python
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)
logging.basicConfig(...): Inicializa o motor de logs.

filename="auditoria_agente.log": Define que todos os registos técnicos vão ser gravados de forma persistente neste ficheiro de texto na raiz do projeto.

level=logging.INFO: Configura o nível de severidade. Grava mensagens informativas (INFO), avisos (WARNING) e falhas (ERROR).

format="..." e datefmt="...": Define a estrutura cronológica de cada linha do log: Ano-Mês-Dia Hora:Minuto:Segundo [NÍVEL_DO_LOG] Mensagem.

encoding="utf-8": Garante o suporte correto a caracteres especiais e acentuações da língua portuguesa.

🗄️ 3. Camada de Persistência em Base de Dados (Linhas 20 a 50)
Python
def inicializar_bd():
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_global (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            session_id TEXT,
            role TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()
sqlite3.connect("agente_memoria.db"): Abre uma ligação ao ficheiro da base de dados relacional. Se o ficheiro não existir, o SQLite cria-o automaticamente no momento.

conn.cursor(): Cria um objeto cursor, que funciona como o intermediário para executar queries SQL diretamente na base de dados.

cursor.execute("CREATE TABLE IF NOT EXISTS..."): Executa um comando DDL SQL para criar a tabela historico_global. Define colunas para indexação automática (id), tempo (timestamp), rastreio do utilizador (session_id), papel na conversa (role: se é utilizador ou assistente) e o texto em si (content).

conn.commit(): Grava as alterações na arquitetura do ficheiro física de forma permanente (transação segura).

conn.close(): Fecha a ligação para libertar memória RAM e prevenir ficheiros corrompidos ou bloqueados em disco.

Python
def guardar_mensagem_bd(session_id, role, content):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO historico_global (timestamp, session_id, role, content) VALUES (?, ?, ?, ?)",
            (timestamp, session_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao gravar na Base de Dados: {e}")
guardar_mensagem_bd(...): Função parametrizada que aceita os dados de uma mensagem e executa um comando DML INSERT INTO para persistir o fluxo de diálogo.

try/except: Camada de resiliência. Se a escrita na base de dados falhar (por exemplo, por falta de permissões no disco), a aplicação não vai abaixo (crash); em vez disso, apanha a exceção e regista o erro no ficheiro de logs através de logging.error.

🎨 4. Configurações de UI e Injeção de Código CSS (Linhas 52 a 81)
Python
inicializar_bd()

st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")
st.set_page_config(layout="wide"): Altera a disposição do ecrã do Streamlit. Passa do modo centrado padrão para o modo largo (wide), distribuindo o espaço horizontal para que o jogo e o chat fiquem bem enquadrados.

st.session_state: É um dicionário em memória que o Streamlit mantém ativo enquanto o utilizador interage com a página (mesmo quando a página faz re-scripts).

st.session_state.session_id = ...: Atribui um identificador único baseado na hora, minuto, segundo e microssegundo atuais ao navegador. Serve para diferenciar os dados de utilizadores diferentes na tabela do SQLite.

Python
st.markdown("""
    <style>
        .stChatInputContainer {
            position: relative;
            margin-top: 50px !important;
        }
        div[data-testid="stAudioInput"] {
            position: absolute;
            left: 0px;
            bottom: 54px;
            z-index: 999;
            width: auto !important;
        }
        div[data-testid="stAudioInput"] label {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)
st.markdown(..., unsafe_allow_html=True): Permite contornar as restrições de estilo do Streamlit, injetando uma tag de estilos CSS diretamente no cabeçalho do browser.

.stChatInputContainer { position: relative; ... }: Torna a barra de chat o ponto de ancoragem relativo para elementos filhos.

div[data-testid="stAudioInput"] { position: absolute; bottom: 54px; ... }: Seleciona o componente nativo de gravação de voz através do ID de testes do Streamlit e força-o a flutuar exatamente acima da caixa de input de texto, criando um design integrado.

🔑 5. Autenticação e Gestão de Chaves de API (Linhas 83 a 91)
Python
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets do Streamlit.")
    logging.error("Falha ao inicializar a aplicação: Chave API ausente nos Secrets.")
    st.stop()
st.secrets["GOOGLE_API_KEY"]: Acede de forma segura às variáveis de ambiente configuradas no ficheiro oculto local .streamlit/secrets.toml ou no painel da Cloud. Evita expor chaves privadas de forma explícita no código público do GitHub.

st.stop(): Um comando de interrupção imediata. Bloqueia a execução do resto do script caso a chave da Google esteja em falta, prevenindo erros em cascata no código inferior.

🛠️ 6. Core de Funções RAG e Integração de Ferramentas (Linhas 93 a 129)
Python
@st.cache_data(ttl=60)
def obter_dados_guimabus():
    url = "https://tracking.elevensystems.pt/api/gmr/vehicles"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            if not dados: return "Nenhum autocarro detetado no momento."
            
            total_atraso = 0
            count = 0
            resumo = "Dados de frota em tempo real:\n"
            for bus in dados:
                atraso = bus.get('delay', 0)
                resumo += f"- Autocarro {bus.get('id', 'N/A')}: Status {bus.get('busStatus', 'N/A')} (Atraso: {atraso}min)\n"
                total_atraso += atraso
                count += 1
            
            media = total_atraso / count if count > 0 else 0
            resumo += f"\n--- Estatística: Atraso médio da frota: {media:.1f} minutos. ---"
            logging.info("Ferramenta Guimabus executada com sucesso pelo modelo.")
            return resumo
        logging.warning(f"API Guimabus devolveu status code HTTP {response.status_code}")
        return "Tracking da Guimabus temporariamente indisponível."
    except Exception as e:
        logging.error(f"Erro ao chamar API Guimabus: {e}")
        return f"Erro na ligação ao tracking: {e}"
@st.cache_data(ttl=60): Mecanismo de otimização de infraestrutura (Caching). Guarda em memória RAM o resultado do pedido HTTP durante 60 segundos (Time-To-Live). Se o utilizador ou a IA chamarem esta função várias vezes num espaço de um minuto, o código não sobrecarrega a API externa com pedidos repetidos.

requests.get(url, timeout=5): Faz a chamada REST para o servidor remoto. O timeout=5 dita que se o servidor de tracking não responder em 5 segundos, a ligação cai, prevenindo que a aplicação fique eternamente congelada à espera da resposta.

response.json(): Descodifica o corpo da resposta HTTP (que chega como texto bruto estruturado) num dicionário/lista nativa de Python para poder ser facilmente iterado através de ciclos for.

Python
def ler_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."
glob.glob("knowledge/*.md"): Pesquisa recursivamente e devolve uma lista com os caminhos de todos os ficheiros Markdown dentro do diretório /knowledge.

f.read(): Efetua a leitura do conteúdo do ficheiro de texto e junta-o (concatenar) na variável contexto. É este bloco de texto que vai alimentar o motor de contexto contextual (RAG) da IA.

🕹️ 7. Motor Gráfico e de Estados do Mini-Game Retro (Linhas 131 a 221)
Python
def renderizar_jogo():
    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:20px; ...">
        ...
        <canvas id="stage" width="400" height="350" ...></canvas>
        ...
        <script>
            ...
            function game() { ... }
            ...
            setInterval(game, 180);
        </script>
    </div>
    """
    components.html(html_jogo, height=600)
components.html(html_jogo, height=600): Injeta uma árvore DOM isolada de HTML5. Todo o código lá dentro corre do lado do cliente (no browser do utilizador), poupando por completo a quota e processamento do servidor Python do Streamlit.

<canvas>: Elemento HTML5 usado para desenhar gráficos bidimensionais via programação JavaScript pixel por pixel (fundo, maçã e corpo da cobra).

setInterval(game, 180): O temporizador do motor de jogo. Executa a função lógica game() a cada 180 microssegundos, definindo a taxa de atualização (Frame Rate) e velocidade da cobra.

Lógica de Paredes Infinitas (head.x < 0, etc.): Verifica se as coordenadas da cabeça ultrapassaram os limites do canvas. Se sim, inverte a posição para o extremo oposto (ex: se x for menor que 0, passa a ser a largura total do ecrã menos o tamanho do bloco), impedindo colisões fatais com as margens.

📋 8. Estado da Conversa e Painel de Monitorização Lateral (Linhas 223 a 306)
Python
MENSAGEM_INICIAL = "..."

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
Mensagem Inicial Automatizada: Configura o estado da conversa com uma mensagem predefinida do assistente caso a sessão acabe de nascer. Garante que a interface nunca abre vazia e orienta o utilizador logo no primeiro segundo.

Python
with st.sidebar:
    ...
    if st.button("🗑️ Limpar O Meu Histórico", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
        st.session_state.jogo_ativo = False
        st.rerun()
st.sidebar: Move todos os componentes declarados dentro deste bloco indentado para a barra lateral esquerda.

st.rerun(): Interrompe o fluxo atual de leitura de código do Streamlit e força o interpretador a ler o ficheiro desde a linha 1. Útil aqui para atualizar instantaneamente as alterações visuais de limpeza do ecrã.

Python
    with st.expander("🗄️ Histórico Permanente Global (BD)"):
        if os.path.exists("agente_memoria.db"):
            conn = sqlite3.connect("agente_memoria.db")
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, role, content FROM historico_global ORDER BY id DESC LIMIT 15")
            linhas_bd = cursor.fetchall()
            conn.close()
            
            for r in reversed(linhas_bd):
                ...
                if r[1] == "user": st.markdown(f"**🟢 ... Tu:** {r[2]}")
                else: st.markdown(f"**🤖 ... Agente:** {r[2]}")
st.expander(...): Menu expansível colapsável que otimiza o espaço da barra lateral.

SELECT ... ORDER BY id DESC LIMIT 15: Query SQL que extrai os últimos 15 registos globais contidos no SQLite. O loop for r in reversed(...) inverte o resultado para desenhar a cronologia da conversa na ordem correta (as mais antigas em cima, as novas em baixo).

🤖 9. O Roteador de Contexto Multi-Persona (Linhas 308 a 415)
Python
if prompt:
    logging.info(f"Input processado [{tipo_input}]: {prompt}")
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
if prompt:: Bloco condicional principal. Tudo o que está aqui dentro só corre se o utilizador submeter um texto ou um ficheiro de áudio válido. Guarda de imediato a interação na auditoria (logging) e na base de dados (guardar_mensagem_bd).

Python
    # CONFIGURAÇÃO DE PERSONAS DINÂMICAS (ROUTER DE PERSONAS)
    PROMPT_EXECUTIVO = "..."
    PROMPT_RECRUITER = "..."
    PROMPT_HELPDESK_TUTOR = "..."

    prompt_normalizado = prompt.lower()
    gatilhos_helpdesk = ["problema", "helpdesk", "ticket", ...]
    
    if "entrevista" in prompt_normalizado or "interview" in prompt_normalizado:
        prompt_sistema_ativo = PROMPT_RECRUITER
    elif any(word in prompt_normalizado for word in gatilhos_helpdesk):
        prompt_sistema_ativo = PROMPT_HELPDESK_TUTOR
    else:
        prompt_sistema_ativo = PROMPT_EXECUTIVO
O Roteador Semântico (Router): Camada de inteligência artificial algorítmica. Analisa o texto normalizado (tudo em minúsculas) em busca de termos específicos ou gatilhos. Conforme a regra de correspondência válida, seleciona e ativa a persona correta (prompt_sistema_ativo), alterando radicalmente o comportamento de raciocínio da IA no passo seguinte.

Python
    historico_api = []
    for msg in st.session_state.messages[:-1]:
        if msg["content"] != MENSAGEM_INICIAL:
            role_api = "model" if msg["role"] == "assistant" else "user"
            historico_api.append({"role": role_api, "parts": [msg["content"]]})
Preparação de Memória (Stateful Chat): Formata a lista cronológica acumulada no Streamlit para a estrutura exata exigida pelo SDK da Google ({"role": ..., "parts": [...]}). Ignora a mensagem estática de boas-vindas para evitar poluir o histórico com instruções repetidas desnecessárias.

Python
    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction=prompt_sistema_ativo,
            tools=ferramentas_agente
        )
        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
        response = chat.send_message(prompt_enriquecido)
    except Exception as e:
        if "429" in str(e):
            logging.warning("Cota 429 atingida. Ativando fallback económico.")
            model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite", ...)
            ...
tools=ferramentas_agente: Passa a assinatura da função Python obter_dados_guimabus para o Gemini.

enable_automatic_function_calling=True: Ativa a autonomia do agente. Se o utilizador perguntar algo que exija os autocarros, o Gemini deteta que a ferramenta resolve a questão, suspende temporariamente a resposta, chama a função Python local, recolhe os dados e formula a resposta final consolidada sem intervenção humana manual.

Estratégia de Fallback (Contingência): Se a API da Google devolver um erro de quota excedida (Código HTTP 429), o bloco except interceta o erro, regista o aviso no log e instancia automaticamente o modelo secundário económico gemini-2.0-flash-lite, mantendo o serviço operacional.

Python
    full_response = response.text
    st.markdown(full_response)
    
    guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.refresh_data()
Fecho de Ciclo: Captura a resposta final em formato texto (response.text), renderiza-a no ecrã com suporte a Markdown, persiste os dados como "assistant" no SQLite e atualiza o estado em memória para manter o chat fluido e contínuo.
