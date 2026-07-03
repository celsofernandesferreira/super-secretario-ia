import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components
import logging
import sqlite3
import json
from datetime import datetime

# 1. CONFIGURAÇÃO DE LOGS (Auditoria Técnica)
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. CONFIGURAÇÃO DA BASE DE DADOS
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS high_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            nome TEXT,
            pontor INTEGER
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

def obter_top_10():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome, pontor FROM high_scores ORDER BY pontor DESC, id ASC LIMIT 10")
        resultados = cursor.fetchall()
        conn.close()
        return resultados
    except Exception as e:
        logging.error(f"Erro ao ler High Scores: {e}")
        return []

def guardar_score_bd(nome, pontor):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "INSERT INTO high_scores (timestamp, nome, pontor) VALUES (?, ?, ?)",
            (timestamp, nome, pontor)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao gravar High Score: {e}")

inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# Processamento imediato do score vindo do URL (Query Params)
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_gravado = query_params["save_nome"].upper()
    pontos_gravados = int(query_params["save_pontos"])
    
    # Grava na BD
    guardar_score_bd(nome_gravado, pontos_gravados)
    st.toast(f"💾 Recorde de {nome_gravado} ({pontos_gravados} pas.) guardado com sucesso!")
    
    # Limpa os parâmetros do URL para evitar loops de gravação ao fazer refresh
    st.query_params.clear()
    st.rerun()

# 4. Injeção de CSS Avançado
st.markdown("""
    <style>
        .stChatInputContainer {
            position: relative;
        }
        .stChatInputContainer textarea {
            padding-left: 55px !important;
        }
        div[data-testid="stAudioInput"] {
            position: absolute;
            left: 12px;
            bottom: 8px;
            z-index: 9999;
            width: 38px !important;
            height: 38px !important;
            background: transparent !important;
        }
        div[data-testid="stAudioInput"] > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
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
    st.stop()

# --- FUNÇÕES DE CONTEXTO / FERRAMENTAS ---
def _extrair_lista_veiculos(dados):
    if isinstance(dados, list): return dados
    if isinstance(dados, dict):
        for chave in ("vehicles", "data", "results", "items", "veiculos"):
            valor = dados.get(chave)
            if isinstance(valor, list): return valor
        for valor in dados.values():
            if isinstance(valor, list): return valor
    return []

def _primeiro_valor(dicionario, chaves, default=None):
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default

@st.cache_data(ttl=60)
def obter_dados_guimabus(route_id: str = None):
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = "https://gmr.elevensystems.pt/api/locations"
    params = {"passengerInfo": "true"}
    if route_id: params["routeId"] = route_id

    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()
        dados = response.json()
        veiculos = _extrair_lista_veiculos(dados)
        if not veiculos:
            linha_txt = f" da linha {route_id}" if route_id else ""
            return f"Não há autocarros{linha_txt} em circulação neste momento."

        total_atraso = 0
        count_com_atraso = 0
        resumo = "Dados de frota em tempo real (Guimabus):\n"
        for bus in veiculos:
            id_bus = _primeiro_valor(bus, ["id", "vehicleId", "vehicle_id", "code"], "N/A")
            linha = _primeiro_valor(bus, ["line", "lineName", "route", "routeShortName", "routeId"], None)
            status = _primeiro_valor(bus, ["busStatus", "status", "state"], "N/A")
            atraso = _primeiro_valor(bus, ["delay", "delayMinutes", "delay_min"], None)

            linha_txt = f" (Linha {linha})" if linha else ""
            atraso_txt = f"{atraso}min" if atraso is not None else "desconhecido"
            resumo += f"- Autocarro {id_bus}{linha_txt}: Status {status} (Atraso: {atraso_txt})\n"

            if isinstance(atraso, (int, float)):
                total_atraso += atraso
                count_com_atraso += 1

        if count_com_atraso > 0:
            media = total_atraso / count_com_atraso
            resumo += f"\n--- Estatística: Atraso médio da frota: {media:.1f} minutos. ---"
        return resumo
    except Exception as e:
        return f"Erro na ligação ao tracking: {e}"

@st.cache_data(ttl=30)
def obter_horarios_paragem(stop_id: str):
    if not stop_id: return "É necessário indicar o ID da paragem."
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = f"https://gmr.elevensystems.pt/api/stops/{stop_id}/routes"
    params = {"shape": "true", "passengerInfo": "true"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()
        dados = response.json()
        rotas = _extrair_lista_veiculos(dados)
        if not rotas: return f"Não há informação de carreiras para a paragem {stop_id} neste momento."

        resumo = f"Horários/previsões para a paragem {stop_id}:\n"
        for rota in rotas:
            linha = _primeiro_valor(rota, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
            destino = _primeiro_valor(rota, ["destination", "headsign", "direction"], None)
            eta = _primeiro_valor(rota, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
            destino_txt = f" → {destino}" if destino else ""
            eta_txt = f"{eta} min" if eta is not None else "sem previsão"
            resumo += f"- Linha {linha}{destino_txt}: {eta_txt}\n"
        return resumo
    except Exception as e:
        return f"Erro na ligação: {e}"

def len_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

# --- INTERFACE: MINI-GAME (COM PONTE DE COMUNICAÇÃO VIA URL CORRIGIDA) ---
def renderizar_jogo():
    top_scores = obter_top_10()
    json_scores = json.dumps(top_scores)

    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:15px; border-radius:10px; font-family:sans-serif;">
        <h3 style="color:#2ecc71; margin-top:0; margin-bottom:10px;">🚌 Guimabus Arcade: Cabine de Condução 🚌</h3>
        
        <canvas id="stage" width="650" height="360" style="border:2px solid #2ecc71; background-color:#000; display:block; margin:0 auto; touch-action:none;"></canvas>
        
        <div style="margin-top: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 6px 15px; background:#2ecc71; color:white; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">Play ▶</button>
            <input type="text" id="nomeInput" placeholder="Teu Nome aqui" maxlength="10" style="display:none; padding: 5px; border-radius:4px; border:1px solid #2ecc71; background:#222; color:white; width:120px; margin-left:10px; vertical-align:middle; text-transform:uppercase;">
            <button id="btnGravar" onclick="gravarRecorde()" style="display:none; padding: 6px 15px; background:#f1c40f; color:black; border:none; border-radius:5px; font-weight:bold; cursor:pointer; margin-left:5px; vertical-align:middle;">Gravar 💾</button>
        </div>
        
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var btnAction = document.getElementById('btnAction');
            var nomeInput = document.getElementById('nomeInput');
            var btnGravar = document.getElementById('btnGravar');
            
            var tnt = 20;
            var gameWidth = 400;
            var cols = gameWidth / tnt, rows = canvas.height / tnt;
            var snake, dx, dy, apple, score, velocidadeMs;
            var proximaDirecao = null;
            var gameInterval = null;
            var gameStarted = false;
            var gameOver = false;
            
            var leaderboard = JSON.parse('JSON_SCORES_PLACEHOLDER');

            function novaMaca() {
                var pos;
                do {
                    pos = {
                        x: Math.floor(Math.random() * cols) * tnt,
                        y: Math.floor(Math.random() * rows) * tnt
                    };
                } while (snake.some(function(s) { return s.x === pos.x && s.y === pos.y; }));
                return pos;
            }

            function estadoInicial() {
                snake = [{x:160, y:160}, {x:140, y:160}, {x:120, y:160}];
                dx = tnt; dy = 0;
                proximaDirecao = null;
                score = 0;
                velocidadeMs = 180;
                apple = novaMaca();
                gameOver = false;
                nomeInput.style.display = 'none';
                btnGravar.style.display = 'none';
            }
            estadoInicial();
            
            function drawScene() {
                ctx.fillStyle = '#222222'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
                ctx.lineWidth = 1;
                for(var i=tnt; i<canvas.height; i+=tnt) {
                    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(gameWidth, i); ctx.stroke();
                }

                ctx.fillStyle = '#2ecc71'; ctx.fillRect(gameWidth, 0, 3, canvas.height);

                // Passageiro
                ctx.fillStyle = '#3498db'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-4)/2, 0, 2 * Math.PI); ctx.fill();
                ctx.fillStyle = '#ffffff'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-12)/2, 0, 2 * Math.PI); ctx.fill();
                
                // Autocarro
                for(var i=0; i<snake.length; i++) {
                    if (i === 0) {
                        ctx.fillStyle = '#27ae60'; ctx.fillRect(snake[i].x, snake[i].y, tnt-1, tnt-1);
                        ctx.fillStyle = '#f1c40f';
                        if (dx > 0) { ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + tnt - 6, 3, 3); }
                        else if (dx < 0) { ctx.fillRect(snake[i].x + 1, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + 1, snake[i].y + tnt - 6, 3, 3); }
                        else if (dy < 0) { ctx.fillRect(snake[i].x + 2, snake[i].y + 1, 3, 3); ctx.fillRect(snake[i].x + tnt - 6, snake[i].y + 1, 3, 3); }
                        else if (dy > 0) { ctx.fillRect(snake[i].x + 2, snake[i].y + tnt - 4, 3, 3); ctx.fillRect(snake[i].x + tnt - 6, snake[i].y + tnt - 4, 3, 3); }
                    } else {
                        ctx.fillStyle = '#2ecc71'; ctx.fillRect(snake[i].x + 1, snake[i].y + 1, tnt-3, tnt-3);
                        ctx.fillStyle = '#2c3e50'; ctx.fillRect(snake[i].x + 4, snake[i].y + 4, tnt-9, tnt-9);
                    }
                }
                
                if(snake.length > 1) {
                    var textPos = snake[1];
                    ctx.fillStyle = '#ffffff'; ctx.font = 'bold 8px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('GMR', textPos.x + tnt/2, textPos.y + tnt/2 + 3);
                }

                ctx.fillStyle = '#ffffff'; ctx.font = 'bold 14px sans-serif'; ctx.textAlign = 'start';
                ctx.fillText('Passageiros: ' + (score / 10), 15, 25);

                // Desenhar Leaderboard Lateral
                ctx.fillStyle = '#151515'; ctx.fillRect(gameWidth + 3, 0, canvas.width - gameWidth - 3, canvas.height);
                ctx.fillStyle = '#2ecc71'; ctx.font = 'bold 14px sans-serif';
                ctx.fillText('🏆 TOP 10 MOTORISTAS', gameWidth + 15, 30);
                
                ctx.font = '12px sans-serif';
                for(var k=0; k<10; k++) {
                    var yPos = 65 + (k * 26);
                    ctx.fillStyle = (k === 0) ? '#f1c40f' : ((k===1) ? '#bdc3c7' : ((k===2) ? '#e67e22' : '#ffffff'));
                    
                    var medalha = (k===0)?"1º ":((k===1)?"2º ":((k===2)?"3º ":(k+1)+"º "));
                    if (leaderboard[k]) {
                        var item = leaderboard[k];
                        ctx.fillText(medalha + item[0], gameWidth + 15, yPos);
                        ctx.textAlign = 'end';
                        ctx.fillText(item[1] + ' pas.', canvas.width - 15, yPos);
                        ctx.textAlign = 'start';
                    } else {
                        ctx.fillStyle = '#444';
                        ctx.fillText(medalha + '------', gameWidth + 15, yPos);
                    }
                }
                
                if (gameOver) {
                    ctx.fillStyle = 'rgba(0, 0, 0, 0.85)'; ctx.fillRect(0, 0, gameWidth, canvas.height);
                    ctx.fillStyle = '#e74c3c'; ctx.font = 'bold 22px sans-serif'; ctx.textAlign = 'center';
                    ctx.fillText('FIM DA LINHA', gameWidth/2, canvas.height/2 - 20);
                    ctx.fillStyle = '#ffffff'; ctx.font = '14px sans-serif';
                    ctx.fillText('Transportaste ' + (score / 10) + ' passageiros!', gameWidth/2, canvas.height/2 + 5);
                    ctx.font = '11px sans-serif'; ctx.fillStyle = '#f1c40f';
                    ctx.fillText('Digita o teu nome no painel abaixo.', gameWidth/2, canvas.height/2 + 30);
                    ctx.textAlign = 'start';
                }
            }
            
            function game() {
                if (gameOver) return;
                if (proximaDirecao) {
                    if (proximaDirecao.dx !== -dx || proximaDirecao.dy !== -dy) {
                        dx = proximaDirecao.dx; dy = proximaDirecao.dy;
                    }
                    proximaDirecao = null;
                }
                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                if (head.x < 0) head.x = gameWidth - tnt;
                else if (head.x >= gameWidth) head.x = 0;
                if (head.y < 0) head.y = canvas.height - tnt;
                else if (head.y >= canvas.height) head.y = 0;

                var vaiComer = (head.x === apple.x && head.y === apple.y);
                var corpoParaVerificar = vaiComer ? snake : snake.slice(0, snake.length - 1);
                for (var i = 0; i < corpoParaVerificar.length; i++) { 
                    if (corpoParaVerificar[i].x === head.x && corpoParaVerificar[i].y === head.y) {
                        triggerGameOver(); return;
                    } 
                }
                snake.unshift(head);
                if (vaiComer) {
                    score += 10;
                    if (score % 50 === 0 && velocidadeMs > 80) {
                        velocidadeMs -= 10;
                        clearInterval(gameInterval); gameInterval = setInterval(game, velocidadeMs);
                    }
                    apple = novaMaca();
                } else { snake.pop(); }
                drawScene();
            }
            
            function toggleGame() {
                if (gameOver) { resetGame(); return; }
                if (!gameStarted) {
                    gameStarted = true; btnAction.innerText = "Pause ⏸";
                    gameInterval = setInterval(game, velocidadeMs);
                } else {
                    gameStarted = false; btnAction.innerText = "Play ▶"; clearInterval(gameInterval);
                }
            }
            function triggerGameOver() {
                gameOver = true; gameStarted = false; clearInterval(gameInterval);
                btnAction.innerText = "Reset 🔄";
                if((score/10) > 0) {
                    nomeInput.style.display = 'inline-block';
                    btnGravar.style.display = 'inline-block';
                    nomeInput.focus();
                }
                drawScene();
            }
            function resetGame() { 
                estadoInicial(); gameOver = false; gameStarted = true;
                btnAction.innerText = "Pause ⏸"; gameInterval = setInterval(game, velocidadeMs);
                drawScene();
            }
            
            // CORREÇÃO AQUI: Forçar a janela principal (parent) a atualizar os Query Params
            function gravarRecorde() {
                var nome = nomeInput.value.trim().toUpperCase();
                if(!nome) { alert('Por favor introduz o teu nome!'); return; }
                
                btnGravar.disabled = true;
                btnGravar.innerText = "A gravar...";
                
                // Envia os dados atualizando o URL da aplicação Streamlit pai
                var pontos Finais = (score / 10);
                window.parent.location.search = "?save_nome=" + encodeURIComponent(nome) + "&save_pontos=" + pontosFinais;
            }
            
            function mudarDirecao(dir) {
                if (!gameStarted || gameOver) return;
                if(dir === 'esquerda' && dx === 0) proximaDirecao = {dx:-tnt, dy:0};
                if(dir === 'cima' && dy === 0) proximaDirecao = {dx:0, dy:-tnt};
                if(dir === 'direita' && dx === 0) proximaDirecao = {dx:tnt, dy:0};
                if(dir === 'baixo' && dy === 0) proximaDirecao = {dx:0, dy:tnt};
            }
            document.addEventListener('keydown', function(e) {
                var mapa = {37:'esquerda', 38:'cima', 39:'direita', 40:'baixo'};
                if (mapa[e.keyCode]) { e.preventDefault(); mudarDirecao(mapa[e.keyCode]); }
            });
            drawScene();
        </script>
    </div>
    """.replace("JSON_SCORES_PLACEHOLDER", json_scores)
    return components.html(html_jogo, height=520)

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

# --- SIDEBAR DE ELITE ---
with st.sidebar:
    st.header("⚙️ Painel do Agente")
    if st.button("🗑️ Limpar O Meu Histórico", use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": MENSAGEM_INICIAL}]
        st.session_state.jogo_ativo = False
        st.rerun()
    st.divider()
    
    st.subheader("🕹️ Entretenimento")
    texto_botao_jogo = "Fechar Jogo X" if st.session_state.jogo_ativo else "Abrir Mini-Game 👾"
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()
    
    st.sidebar.subheader("👨‍💻 Desenvolvedor")
    st.sidebar.info("""**Celso Ferreira**
*À procura de emprego na área de IT / Informática.*
📞 Contacto: **917 486 683**""")
    st.sidebar.divider()
    
    st.write("Estado: **Online**")
    st.write("Modelo Nativo: `Gemini-3.5-Flash`")
    st.sidebar.divider()
    
    # ÁREA DE ADMINISTRADOR
    if "admin_autenticado" not in st.session_state:
        st.session_state.admin_autenticado = False

    if not st.session_state.admin_autenticado:
        with st.sidebar.expander("Entrar como administrador"):
            password_input = st.text_input("Password de administrador", type="password", key="admin_pwd")
            if st.button("Entrar", key="admin_login_btn"):
                if password_input and password_input == st.secrets.get("ADMIN_PASSWORD", None):
                    st.session_state.admin_autenticado = True
                    logging.info("Login de administrador bem-sucedido.")
                    st.rerun()
                else:
                    st.sidebar.error("Password incorreta.")
                    logging.warning("Tentativa de login de administrador falhada.")
    else:
        st.sidebar.success("Sessão de administrador activa.")
        if st.sidebar.button("Sair da área de administrador", key="admin_logout_btn"):
            st.session_state.admin_autenticado = False
            st.rerun()

        st.sidebar.subheader("📊 Telemetria e BD")
        if os.path.exists("agente_memoria.db"):
            with open("agente_memoria.db", "rb") as f:
                st.sidebar.download_button("📥 Exportar DB SQLite (.db)", f, "agente_memoria.db", "application/octet-stream", use_container_width=True)

        with st.sidebar.expander("👁️ Ver Logs do Sistema"):
            if os.path.exists("auditoria_agente.log"):
                with open("auditoria_agente.log", "r", encoding="utf-8") as f:
                    linhas_log = f.readlines()[-10:]
                    for linha in linhas_log: st.caption(linha.strip())

        with st.sidebar.expander("🗄️ Histórico Permanente Global (BD)"):
            if os.path.exists("agente_memoria.db"):
                conn = sqlite3.connect("agente_memoria.db")
                cursor = conn.cursor()
                cursor.execute("SELECT timestamp, session_id, role, content FROM historico_global ORDER BY id DESC LIMIT 30")
                linhas_bd = cursor.fetchall()
                conn.close()
                for r in reversed(linhas_bd):
                    hora_min = r[0].split(" ")[1] if " " in r[0] else r[0]
                    sessao = r[1]
                    if r[2] == "user":
                        st.markdown(f"**🟢 [{hora_min}] Visitante ({sessao}):** {r[3]}")
                    else:
                        st.markdown(f"**🤖 [{hora_min}] Agente ({sessao}):** {r[3]}")
                    st.divider()

# --- ÁREA DO JOGO PRINCIPAL ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

# Mostrar histórico visual no chat
for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA MULTIMODAL ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar")

prompt = None
tipo_input = "Texto"

if "ultimo_audio_processado_id" not in st.session_state:
    st.session_state.ultimo_audio_processado_id = None

if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    audio_id_atual = audio_file.file_id if hasattr(audio_file, "file_id") else audio_file.name

    if audio_id_atual != st.session_state.ultimo_audio_processado_id:
        st.session_state.ultimo_audio_processado_id = audio_id_atual
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

# --- FLUXO PRINCIPAL DO AGENTE ---
if prompt:
    logging.info(f"Input processado [{tipo_input}]: {prompt}")
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner("Agente a processar contexto e ferramentas..."):
            try:
                contexto_base = len_knowledge_base()
                
                PROMPT_EXECUTIVO = """Tu és o Assistente Executivo de Elite do Celso Ferreira.
                És um Agente focado em automação, suporte e infraestrutura IT.
                Responde de forma concisa em Português de Portugal utilizando sempre a Knowledge Base e ferramentas.

                Tens duas ferramentas relacionadas com a Guimabus, para perguntas diferentes:
                - obter_dados_guimabus: estado em tempo real da frota (posições/atrasos dos autocarros já em circulação). Aceita opcionalmente um "route_id" para filtrar por linha.
                - obter_horarios_paragem: previsão de tempos de espera/carreiras para uma paragem específica (precisa do ID numérico da paragem)."""
                
                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time."""
                
                PROMPT_HELPDESK_TUTOR = """Tu és um Tutor Técnico de Helpdesk e Suporte de IT.
                Independentemente do problema de suporte indicado pelo utilizador, deves começar a tua resposta OBRIGATORIAMENTE com: 
                'O Celso faria desta maneira para resolver este problema de IT:'"""

                prompt_normalizado = prompt.lower()
                gatilhos_helpdesk = ["problema", "helpdesk", "ticket", "avaria", "erro", "servidor", "computador", "rede", "suporte", "falha"]
                
                if "entrevista" in prompt_normalizado or "interview" in prompt_normalizado:
                    prompt_sistema_ativo = PROMPT_RECRUITER
                elif any(word in prompt_normalizado for word in gatilhos_helpdesk):
                    prompt_sistema_ativo = PROMPT_HELPDESK_TUTOR
                else:
                    prompt_sistema_ativo = PROMPT_EXECUTIVO

                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] != MENSAGEM_INICIAL:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                prompt_enriquecido = f"{contexto_base}\n\nUser Prompt: {prompt}"
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem]
                
                TIMEOUT_SEGUNDOS = 25
                candidatos_modelo = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

                response = None
                for nome_modelo in candidatos_modelo:
                    try:
                        model = genai.GenerativeModel(
                            model_name=nome_modelo,
                            system_instruction=prompt_sistema_ativo,
                            tools=ferramentas_agente
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(prompt_enriquecido, request_options={"timeout": TIMEOUT_SEGUNDOS})
                        break
                    except Exception as e:
                        logging.warning(f"Modelo '{nome_modelo}' falhou. A tentar o próximo.")
                        continue

                if response is None:
                    st.error("🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento.")
                    st.stop()

                full_response = response.text
                st.markdown(full_response)
                
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
