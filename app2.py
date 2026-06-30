import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components
import logging
import sqlite3
from datetime import datetime

# 1. CONFIGURAÇÃO DE LOGS (Auditoria Técnica)
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. CONFIGURAÇÃO DA BASE DE DADOS (SQLite Persistente)
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

# Inicializa o armazenamento no arranque
inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# Identificador único de sessão
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# 4. Injeção de CSS Customizado (Ajuste preciso do microfone à direita)
st.markdown("""
    <style>
        .stChatInputContainer {
            position: relative;
            padding-right: 60px !important;
        }
        div[data-testid="stAudioInput"] {
            position: absolute;
            right: 15px;
            bottom: 4px;
            z-index: 999;
            width: auto !important;
        }
        div[data-testid="stAudioInput"] label {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

# 5. Inicialização da API do Gemini
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets do Streamlit.")
    logging.error("Falha ao inicializar a aplicação: Chave API ausente nos Secrets.")
    st.stop()

# --- FUNÇÕES DE CONTEXTO / FERRAMENTAS (TOOLS) ---
@st.cache_data(ttl=60)
def obter_dados_guimabus():
    """Consulta a API de tracking em tempo real da Guimabus e devolve o estado atual dos autocarros e atrasos médios."""
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

def ler_knowledge_base():
    """Recupera dados dinâmicos de todos os ficheiros Markdown guardados na pasta knowledge/."""
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

# --- INTERFACE: MINI-GAME RETRO UPGRADED (CONTROLOS + SCOREBOARD) ---
def renderizar_jogo():
    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:20px; border-radius:10px; margin-bottom: 20px;">
        <h3 style="color:#ffe135; font-family:sans-serif; margin-top:0; margin-bottom:10px;">🕹️ Modo Pausa: Snake Arcade Retro 🕹️</h3>
        <canvas id="stage" width="400" height="350" style="border:2px solid #ffe135; background-color:#000; display:block; margin:0 auto;"></canvas>
        
        <div style="margin-top: 15px; display: inline-block;">
            <button onclick="mudarDirecao('cima')" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▲</button><br>
            <button onclick="mudarDirecao('esquerda')" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">◀</button>
            <button onclick="mudarDirecao('baixo')" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▼</button>
            <button onclick="mudarDirecao('direita')" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▶</button>
        </div>
        <p style="color:#aaa; font-family:sans-serif; font-size:12px; margin-top:10px;">Usa as setas do teclado ou os botões do ecrã para controlar a cobra.</p>
        
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var tnt = 20, snake = [{x:160, y:160}], dx = tnt, dy = 0, apple = {x:80, y:80}, score = 0;
            
            function game() {
                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                if (head.x < 0 || head.x >= canvas.width || head.y < 0 || head.y >= canvas.height) resetGame();
                for (var i = 0; i < snake.length; i++) { if (snake[i].x === head.x && snake[i].y === head.y) resetGame(); }
                
                snake.unshift(head);
                if (head.x === apple.x && head.y === apple.y) {
                    score += 10;
                    apple.x = Math.floor(Math.random() * (canvas.width/tnt)) * tnt;
                    apple.y = Math.floor(Math.random() * (canvas.height/tnt)) * tnt;
                } else { snake.pop(); }
                
                // Desenhar Fundo
                ctx.fillStyle = '#000'; ctx.fillRect(0,0,canvas.width,canvas.height);
                
                // Desenhar Maçã
                ctx.fillStyle = '#ff4444'; ctx.fillRect(apple.x, apple.y, tnt-2, tnt-2);
                
                // Desenhar Cobra
                ctx.fillStyle = '#00ff00'; 
                for(var i=0; i<snake.length; i++) ctx.fillRect(snake[i].x, snake[i].y, tnt-2, tnt-2);
                
                // Desenhar Scoreboard Nativo no Canvas
                ctx.fillStyle = '#ffffff'; ctx.font = '16px sans-serif';
                ctx.fillText('Score: ' + score, 15, 25);
            }
            
            function resetGame() { snake = [{x:160, y:160}]; dx = tnt; dy = 0; score = 0; }
            
            function mudarDirecao(dir) {
                if(dir === 'esquerda' && dx == 0) { dx = -tnt; dy = 0; }
                if(dir === 'cima' && dy == 0) { dx = 0; dy = -tnt; }
                if(dir === 'direita' && dx == 0) { dx = tnt; dy = 0; }
                if(dir === 'baixo' && dy == 0) { dx = 0; dy = tnt; }
            }
            
            document.addEventListener('keydown', function(e) {
                if(e.keyCode == 37) mudarDirecao('esquerda');
                if(e.keyCode == 38) mudarDirecao('cima');
                if(e.keyCode == 39) mudarDirecao('direita');
                if(e.keyCode == 40) mudarDirecao('baixo');
            });
            setInterval(game, 120);
        </script>
    </div>
    """
    components.html(html_jogo, height=540)

# --- INICIALIZAÇÃO DE ESTADOS ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    logging.info(f"Nova sessão de utilizador iniciada. ID Temporário: {st.session_state.session_id}")

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# --- SIDEBAR DE ELITE (GERENCIAMENTO DO AGENTE) ---
with st.sidebar:
    st.header("⚙️ Painel do Agente")
    if st.button("🗑️ Limpar O Meu Histórico", use_container_width=True):
        st.session_state.messages = []
        st.session_state.jogo_ativo = False
        logging.info(f"Histórico da sessão {st.session_state.session_id} limpo pelo utilizador.")
        st.rerun()
    st.divider()
    
    st.subheader("🕹️ Entretenimento")
    texto_botao_jogo = "Fechar Jogo X" if st.session_state.jogo_ativo else "Abrir Mini-Game 👾"
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()
    
    st.write("Estado: **Online**")
    st.write("Modelo Nativo: `Gemini-3.5-Flash`")
    st.divider()
    
    # VISUALIZADOR DE LOGS E DE HISTÓRICO GLOBAL FORMATADO
    st.subheader("📊 Telemetria e BD")
    with st.expander("👁️ Ver Logs do Sistema"):
        if os.path.exists("auditoria_agente.log"):
            with open("auditoria_agente.log", "r", encoding="utf-8") as f:
                linhas_log = f.readlines()[-10:]
                for linha in linhas_log: st.caption(linha.strip())
                
    with st.expander("🗄️ Histórico Permanente Global (BD)"):
        if os.path.exists("agente_memoria.db"):
            conn = sqlite3.connect("agente_memoria.db")
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, role, content FROM historico_global ORDER BY id DESC LIMIT 15")
            linhas_bd = cursor.fetchall()
            conn.close()
            
            for r in reversed(linhas_bd):
                # Extrai apenas a hora do timestamp para simplificar
                hora_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                if r[1] == "user":
                    st.markdown(f"**🟢 [{hora_min}] Tu:** {r[2]}")
                else:
                    st.markdown(f"**🤖 [{hora_min}] Agente:** {r[2]}")
                st.divider()

# --- PARAMETRIZAÇÃO DO AGENTE ---
PROMPT_SISTEMA = """
Tu és o Assistente Executivo de Elite do Celso Ferreira.
És um Agente inteligente focado em automação, suporte e infraestrutura IT.
Tens acesso direto a ferramentas em tempo real (Tools) e à Knowledge Base estática.
Responde sempre de forma executiva, breve e certeira, consultando os ficheiros e mantendo o contexto histórico da conversa.
"""

# --- RENDERIZAÇÃO DA INTERFACE ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA MULTIMODAL ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar")

prompt = None
tipo_input = "Texto"
if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    prompt = "Ficheiro de áudio registado na interface."
    tipo_input = "Áudio"

# --- FLUXO PRINCIPAL DO AGENTE ---
if prompt:
    logging.info(f"Input processado [{tipo_input}]: {prompt}")
    
    # Grava na Base de Dados local a pergunta do utilizador antes do envio para a API
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agente a processar contexto e ferramentas..."):
            try:
                contexto_base = ler_knowledge_base()
                
                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    role_api = "model" if msg["role"] == "assistant" else "user"
                    historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                prompt_enriquecido = f"{contexto_base}\n\nPergunta Atual do Utilizador: {prompt}"
                ferramentas_agente = [obter_dados_guimabus]
                
                try:
                    model = genai.GenerativeModel(
                        model_name="gemini-3.5-flash",
                        system_instruction=PROMPT_SISTEMA,
                        tools=ferramentas_agente
                    )
                    chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                    response = chat.send_message(prompt_enriquecido)
                except Exception as e:
                    if "429" in str(e):
                        logging.warning("Cota 429 atingida no modelo principal. Fallback ativo.")
                        st.warning("⚠️ Limite atingido. A alternar para modelo secundário...")
                        model = genai.GenerativeModel(
                            model_name="gemini-2.0-flash-lite",
                            system_instruction=PROMPT_SISTEMA,
                            tools=ferramentas_agente
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(prompt_enriquecido)
                    else:
                        raise e

                full_response = response.text
                st.markdown(full_response)
                
                logging.info(f"Resposta gerada com sucesso ({len(full_response)} caracteres).")
                
                # Grava na Base de Dados a resposta oficial do modelo vinculada a esta sessão
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
                logging.error(f"Falha crítica no pipeline do agente: {e}")
