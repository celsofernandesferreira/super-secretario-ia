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

# Inicializa a BD no arranque
inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# Identificador único de sessão
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# 4. Injeção de CSS Avançado (Microfone embutido DIRETAMENTE na barra de escrita)
st.markdown("""
    <style>
        /* Dá um espaçamento à esquerda no input de texto para o texto não sobrepor o microfone */
        .stChatInputContainer textarea {
            padding-left: 55px !important;
        }
        
        /* Força a barra de escrita a ser o container de posicionamento principal */
        .stChatInputContainer {
            position: relative;
        }
        
        /* Posiciona e integra o microfone de forma invisível no canto esquerdo da barra */
        div[data-testid="stAudioInput"] {
            position: absolute;
            left: 10px;
            bottom: 6px;
            z-index: 9999;
            width: 40px !important;
            background: transparent !important;
        }
        
        /* Remove o fundo, bordas e textos nativos do componente grande do Streamlit */
        div[data-testid="stAudioInput"] > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
        }
        
        div[data-testid="stAudioInput"] label {
            display: none !important;
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

# --- INTERFACE: MINI-GAME RETRO UPGRADED ---
def renderizar_jogo():
    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:20px; border-radius:10px; margin-bottom: 20px;">
        <h3 style="color:#ffe135; font-family:sans-serif; margin-top:0; margin-bottom:10px;">🕹️ Modo Pausa: Snake Arcade Retro 🕹️</h3>
        
        <div style="margin-bottom: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 8px 20px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; font-size:14px; cursor:pointer;">Play ▶</button>
        </div>

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
            var btnAction = document.getElementById('btnAction');
            
            var tnt = 20, snake = [{x:160, y:160}], dx = tnt, dy = 0, apple = {x:80, y:80}, score = 0;
            var gameInterval = null;
            var gameStarted = false;
            var gameOver = false;
            
            function drawScene() {
                ctx.fillStyle = '#1a1a1a'; ctx.fillRect(0,0,canvas.width,canvas.height);
                ctx.fillStyle = '#ff6666'; ctx.fillRect(apple.x, apple.y, tnt-2, tnt-2);
                ctx.fillStyle = '#33ff33'; 
                for(var i=0; i<snake.length; i++) ctx.fillRect(snake[i].x, snake[i].y, tnt-2, tnt-2);
                ctx.fillStyle = '#ffffff'; ctx.font = '16px sans-serif';
                ctx.fillText('Score: ' + score, 15, 25);
                
                if (gameOver) {
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)'; ctx.fillRect(0, 0, canvas.width, canvas.height);
                    ctx.fillStyle = '#ff4444'; ctx.font = '24px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('GAME OVER', canvas.width/2, canvas.height/2);
                    ctx.textAlign = 'start';
                }
            }
            
            function game() {
                if (gameOver) return;
                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                
                if (head.x < 0) head.x = canvas.width - tnt;
                else if (head.x >= canvas.width) head.x = 0;
                
                if (head.y < 0) head.y = canvas.height - tnt;
                else if (head.y >= canvas.height) head.y = 0;
                
                for (var i = 0; i < snake.length; i++) { 
                    if (snake[i].x === head.x && snake[i].y === head.y) {
                        triggerGameOver();
                        return;
                    } 
                }
                
                snake.unshift(head);
                if (head.x === apple.x && head.y === apple.y) {
                    score += 10;
                    apple.x = Math.floor(Math.random() * (canvas.width/tnt)) * tnt;
                    apple.y = Math.floor(Math.random() * (canvas.height/tnt)) * tnt;
                } else { snake.pop(); }
                
                drawScene();
            }
            
            function toggleGame() {
                if (gameOver) { resetGame(); return; }
                if (!gameStarted) {
                    gameStarted = true;
                    btnAction.innerText = "Pause ⏸";
                    gameInterval = setInterval(game, 180);
                } else {
                    gameStarted = false;
                    btnAction.innerText = "Play ▶";
                    clearInterval(gameInterval);
                }
            }
            
            function triggerGameOver() {
                gameOver = true; gameStarted = false;
                clearInterval(gameInterval);
                btnAction.innerText = "Reset 🔄";
                drawScene();
            }
            
            function resetGame() { 
                snake = [{x:160, y:160}]; dx = tnt; dy = 0; score = 0; 
                gameOver = false; gameStarted = true;
                btnAction.innerText = "Pause ⏸";
                gameInterval = setInterval(game, 180);
                drawScene();
            }
            
            function mudarDirecao(dir) {
                if (!gameStarted || gameOver) return;
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
            drawScene();
        </script>
    </div>
    """
    components.html(html_jogo, height=600)

# --- MENSAGEM INICIAL AUTOMÁTICA ---
MENSAGEM_INICIAL = """Olá, Celso! Sou o teu **Agente de Produtividade de Elite**. 

Estou pronto para te apoiar em três frentes:
1. **Modo Executivo:** Monitorização da frota Guimabus e consulta à Knowledge Base.
2. **Modo Tech Recruiter:** Diz-me *'Quero treinar para uma entrevista'* para simularmos testes técnicos em inglês.
3. **Modo Helpdesk Técnico:** Envia-me um problema de IT ou avaria e eu mostro-te como o Celso resolveria a situação.

Como posso ajudar hoje?"""

# --- INICIALIZAÇÃO DE ESTADOS ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
    logging.info(f"Nova sessão de utilizador iniciada. ID Temporário: {st.session_state.session_id}")

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# --- SIDEBAR DE ELITE (GERENCIAMENTO DO AGENTE) ---
with st.sidebar:
    st.header("⚙️ Painel do Agente")
    if st.button("🗑️ Limpar O Meu Histórico", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
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
    
    # SECÇÃO: CONTACTO DIRETO E RECRUTAMENTO
    st.subheader("👨‍💻 Desenvolvedor")
    st.info("""**Celso Ferreira**
*À procura de emprego na área de IT / Informática.*
📞 Contacto: **917 486 683**""")
    st.divider()
    
    st.write("Estado: **Online**")
    st.write("Modelo Nativo: `Gemini-3.5-Flash`")
    st.divider()
    
    # VISUALIZADOR DE DADOS E EXPORTAÇÃO
    st.subheader("📊 Telemetria e BD")
    if os.path.exists("agente_memoria.db"):
        with open("agente_memoria.db", "rb") as f:
            st.download_button("📥 Exportar DB SQLite (.db)", f, "agente_memoria.db", "application/octet-stream", use_container_width=True)

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
                hora_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                if r[1] == "user":
                    st.markdown(f"**🟢 [{hora_min}] Tu:** {r[2]}")
                else:
                    st.markdown(f"**🤖 [{hora_min}] Agente:** {r[2]}")
                st.divider()

# --- ÁREA DO CHAT PRINCIPAL ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

# Mostrar histórico visual no chat com Avatares Estilizados
for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA MULTIMODAL ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar")

prompt = None
tipo_input = "Texto"

if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    tipo_input = "Áudio"
    with st.spinner("A processar e a transcrever o teu áudio..."):
        try:
            audio_data = audio_file.read()
            model_transcrever = genai.GenerativeModel("gemini-3.5-flash")
            audio_part = {"mime_type": "audio/wav", "data": audio_data}
            
            response_transcricao = model_transcrever.generate_content([
                "Transcreve estritamente o áudio fornecido para texto, mantendo a pontuação correta e no idioma original. Não adiciones comentários extras.",
                audio_part
            ])
            prompt = response_transcricao.text.strip()
            logging.info(f"Transcrição de voz concluída com sucesso: '{prompt}'")
        except Exception as e:
            st.error(f"Erro ao processar o ficheiro de voz: {e}")
            logging.error(f"Falha na transcrição de áudio: {e}")

# --- FLUXO PRINCIPAL DO AGENTE DE ROTEAMENTO (ROUTER DE PERSONAS) ---
if prompt:
    logging.info(f"Input processado [{tipo_input}]: {prompt}")
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner("Agente a processar contexto e ferramentas..."):
            try:
                contexto_base = ler_knowledge_base()
                
                # DEFINIÇÃO DOS PROMPTS DE SISTEMA (MÚLTIPLAS PERSONAS)
                PROMPT_EXECUTIVO = """Tu és o Assistente Executivo de Elite do Celso Ferreira.
                És um Agente focado em automação, suporte e infraestrutura IT.
                Responde de forma concisa em Português de Portugal utilizando sempre a Knowledge Base e ferramentas."""
                
                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                PROMPT_HELPDESK_TUTOR = """Tu és um Tutor Técnico Técnico de Helpdesk e Suporte de IT.
                O teu objetivo é atuar como uma fonte interminável de resolução de problemas de IT.
                Independentemente do problema de suporte indicado pelo utilizador (Active Directory, Redes, Sistemas, Avarias), deves começar a tua resposta OBRIGATORIAMENTE com a seguinte frase padrão: 
                'O Celso faria desta maneira para resolver este problema de IT:'
                Depois, detalha passos de troubleshooting técnicos, comandos em PowerShell ou Linux, e boas práticas aplicadas com precisão."""

                # LÓGICA DO ROUTER EM TEMPO DE EXECUÇÃO
                prompt_normalizado = prompt.lower()
                gatilhos_helpdesk = ["problema", "helpdesk", "ticket", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha"]
                
                if "entrevista" in prompt_normalizado or "interview" in prompt_normalizado:
                    prompt_sistema_ativo = PROMPT_RECRUITER
                    logging.info("Router selecionou a Persona: IT Technical Recruiter (EN)")
                elif any(word in prompt_normalizado for word in gatilhos_helpdesk):
                    prompt_sistema_ativo = PROMPT_HELPDESK_TUTOR
                    logging.info("Router selecionou a Persona: Tutor de Helpdesk / Modo Celso (PT)")
                else:
                    prompt_sistema_ativo = PROMPT_EXECUTIVO
                    logging.info("Router selecionou a Persona: Assistente Executivo (PT)")

                # Estruturar histórico limpo para o payload da API
                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] != MENSAGEM_INICIAL:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                prompt_enriquecido = f"{contexto_base}\n\nUser Prompt: {prompt}"
                ferramentas_agente = [obter_dados_guimabus]
                
                # Execução Resiliente com Fallback
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
                        st.warning("⚠️ Limite atingido. A alternar para modelo secundário...")
                        model = genai.GenerativeModel(
                            model_name="gemini-2.0-flash-lite",
                            system_instruction=prompt_sistema_ativo,
                            tools=ferramentas_agente
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(prompt_enriquecido)
                    else:
                        raise e

                full_response = response.text
                st.markdown(full_response)
                
                logging.info(f"Resposta gerada com sucesso ({len(full_response)} caracteres).")
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
                logging.error(f"Falha crítica no pipeline do agente: {e}")
