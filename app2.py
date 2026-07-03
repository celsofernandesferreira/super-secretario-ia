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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            nome TEXT,
            pontuacao INTEGER
        )
    """)
    conn.commit()
    conn.close()

def guardar_pontuacao_leaderboard(nome: str, pontuacao: int):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO leaderboard (timestamp, nome, pontuacao) VALUES (?, ?, ?)",
            (timestamp, nome.strip()[:30], pontuacao)
        )
        conn.commit()
        conn.close()
        logging.info(f"Pontuação gravada no leaderboard: {nome} - {pontuacao} pontos.")
        return True
    except Exception as e:
        logging.error(f"Erro ao gravar pontuação no leaderboard: {e}")
        return False

def obter_top_leaderboard(limite: int = 10):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT nome, pontuacao, timestamp FROM leaderboard ORDER BY pontuacao DESC LIMIT ?", (limite,))
        resultado = cursor.fetchall()
        conn.close()
        return resultado
    except Exception as e:
        logging.error(f"Erro ao ler leaderboard: {e}")
        return []

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

# 4. Injeção de CSS Avançado (Microfone embutido de forma nativa DENTRO da barra de escrita)
st.markdown("""
    <style>
        /* Cria um ponto de referência relativo na barra de chat */
        .stChatInputContainer {
            position: relative;
        }
        
        /* Empurra o texto digitado para a direita para dar espaço ao microfone no canto esquerdo */
        .stChatInputContainer textarea {
            padding-left: 55px !important;
        }
        
        /* Ajusta o componente de áudio e posiciona-o exatamente DENTRO da barra no canto esquerdo */
        div[data-testid="stAudioInput"] {
            position: absolute;
            left: 12px;
            bottom: 8px;
            z-index: 9999;
            width: 38px !important;
            height: 38px !important;
            background: transparent !important;
        }
        
        /* Limpa o design bruto e retira as caixas cinzentas grandes do Streamlit */
        div[data-testid="stAudioInput"] > div {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            box-shadow: none !important;
        }
        
        /* Esconde textos informativos desnecessários do componente */
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
def _extrair_lista_veiculos(dados):
    """A API não é documentada publicamente e diferentes deployments do Eleven Systems
    devolvem formatos ligeiramente diferentes (lista direta, ou objeto com a lista
    dentro de uma chave como 'vehicles'/'data'/'results'/'items'). Esta função tenta
    encontrar a lista de veículos seja qual for o "invólucro" usado."""
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("vehicles", "data", "results", "items", "veiculos"):
            valor = dados.get(chave)
            if isinstance(valor, list):
                return valor
        # fallback: primeiro valor do dicionário que seja uma lista
        for valor in dados.values():
            if isinstance(valor, list):
                return valor
    return []


def _primeiro_valor(dicionario, chaves, default=None):
    """Tenta várias variantes possíveis do nome de um campo (a API não documenta o schema)."""
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default


@st.cache_data(ttl=60)
def obter_dados_guimabus(route_id: str = None):
    """Consulta a API de tracking em tempo real da Guimabus (posições/atrasos dos autocarros
    em circulação neste momento). Endpoint confirmado via inspeção do tráfego de rede do site
    oficial: https://gmr.elevensystems.pt/api/locations

    NOTA: esta API devolve o estado ao vivo da frota, não o horário/planeamento das carreiras —
    para horários previstos por paragem seria necessário outro endpoint (ver comentário no
    fim do ficheiro).

    Args:
        route_id: opcional. ID de uma linha específica (ex: "53") para filtrar os resultados
                  a essa carreira. Sem este argumento, tenta obter todos os veículos.
    """
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = "https://gmr.elevensystems.pt/api/locations"
    params = {"passengerInfo": "true"}
    if route_id:
        params["routeId"] = route_id

    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()

        try:
            dados = response.json()
        except ValueError:
            logging.error("API Guimabus devolveu conteúdo que não é JSON válido.")
            return "Não foi possível ler os dados da Guimabus (resposta em formato inesperado)."

        veiculos = _extrair_lista_veiculos(dados)
        if not veiculos:
            linha_txt = f" da linha {route_id}" if route_id else ""
            logging.info(f"API Guimabus respondeu sem veículos{linha_txt} (provavelmente fora de serviço agora).")
            return f"Não há autocarros{linha_txt} em circulação neste momento (fora de horário de serviço ou sem veículos ativos)."

        # Regista o primeiro registo em bruto no log, para conseguirmos afinar os nomes
        # de campo com um exemplo real assim que a frota estiver ativa.
        logging.info(f"Exemplo de registo Guimabus (para afinação futura): {str(veiculos[0])[:500]}")

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
            resumo += f"\n--- Estatística: Atraso médio da frota: {media:.1f} minutos (com base em {count_com_atraso} veículo(s) com esse dado). ---"
        else:
            resumo += "\n--- Não foi possível calcular o atraso médio: a API não devolveu esse campo para nenhum veículo. ---"

        return resumo

    except requests.exceptions.Timeout:
        logging.error("Timeout ao chamar a API Guimabus.")
        return "Tracking da Guimabus demorou demasiado tempo a responder. Tenta novamente dentro de momentos."
    except requests.exceptions.HTTPError as e:
        logging.warning(f"API Guimabus devolveu erro HTTP: {e}")
        return "Tracking da Guimabus temporariamente indisponível (erro do servidor)."
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de ligação à API Guimabus: {e}")
        return f"Erro na ligação ao tracking: {e}"


@st.cache_data(ttl=30)
def obter_horarios_paragem(stop_id: str):
    """Consulta as carreiras e horários/tempos de espera previstos (passenger info) para uma
    paragem específica da Guimabus, através do ID da paragem. Endpoint confirmado via
    inspeção do tráfego de rede do site oficial: https://gmr.elevensystems.pt/api/stops/{id}/routes

    Args:
        stop_id: o ID numérico da paragem (ex: "1108"). Este ID pode ser obtido no site
                 https://tracking.elevensystems.pt/gmr ao selecionar a paragem pretendida no mapa.
    """
    if not stop_id:
        return "É necessário indicar o ID da paragem para consultar os horários."

    headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
    url = f"https://gmr.elevensystems.pt/api/stops/{stop_id}/routes"
    params = {"shape": "true", "passengerInfo": "true"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        response.raise_for_status()

        try:
            dados = response.json()
        except ValueError:
            logging.error("API de paragens da Guimabus devolveu conteúdo que não é JSON válido.")
            return "Não foi possível ler os horários desta paragem (resposta em formato inesperado)."

        rotas = _extrair_lista_veiculos(dados)  # a mesma lógica de "desembrulhar" listas serve aqui
        if not rotas:
            logging.info(f"API de paragens Guimabus respondeu sem carreiras para a paragem {stop_id} (fora de serviço agora, ou ID inválido).")
            return f"Não há informação de carreiras/horários para a paragem {stop_id} neste momento (pode estar fora de horário de serviço, ou o ID da paragem pode estar incorreto)."

        logging.info(f"Exemplo de registo de paragem (para afinação futura): {str(rotas[0])[:500]}")

        resumo = f"Horários/previsões para a paragem {stop_id}:\n"
        for rota in rotas:
            linha = _primeiro_valor(rota, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
            destino = _primeiro_valor(rota, ["destination", "headsign", "direction"], None)
            eta = _primeiro_valor(rota, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)

            destino_txt = f" → {destino}" if destino else ""
            eta_txt = f"{eta} min" if eta is not None else "sem previsão disponível"
            resumo += f"- Linha {linha}{destino_txt}: {eta_txt}\n"

        return resumo

    except requests.exceptions.Timeout:
        logging.error("Timeout ao chamar a API de paragens da Guimabus.")
        return "A consulta de horários demorou demasiado tempo a responder. Tenta novamente dentro de momentos."
    except requests.exceptions.HTTPError as e:
        logging.warning(f"API de paragens da Guimabus devolveu erro HTTP: {e}")
        return "Consulta de horários por paragem temporariamente indisponível (erro do servidor)."
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro de ligação à API de paragens da Guimabus: {e}")
        return f"Erro na ligação à consulta de horários: {e}"

# Nota: /api/locations dá o estado em tempo real da frota (posições/atrasos dos autocarros
# já em circulação); /api/stops/{id}/routes dá as previsões/horários de uma paragem específica.
# São dados complementares — o agente escolhe qual ferramenta usar consoante a pergunta.

def ler_knowledge_base():
    """Recupera dados dinâmicos de todos os ficheiros Markdown guardados na pasta knowledge/."""
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

# --- INTERFACE: MINI-GAME RETRO UPGRADED (PAREDES INFINITAS + BOTÃO START/RESET + VELOCIDADE 180MS) ---
def renderizar_jogo():
    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:20px; border-radius:10px; margin-bottom: 20px;">
        <h3 style="color:#ffe135; font-family:sans-serif; margin-top:0; margin-bottom:10px;">🕹️ Modo Pausa: Snake Arcade Retro 🕹️</h3>
        
        <div style="margin-bottom: 10px;">
            <button id="btnAction" onclick="toggleGame()" style="padding: 8px 20px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; font-size:14px; cursor:pointer;">Play ▶</button>
        </div>

        <canvas id="stage" width="400" height="360" style="border:2px solid #ffe135; background-color:#000; display:block; margin:0 auto; touch-action:none;"></canvas>
        
        <div style="margin-top: 15px; display: inline-block;">
            <button data-dir="cima" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▲</button><br>
            <button data-dir="esquerda" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">◀</button>
            <button data-dir="baixo" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▼</button>
            <button data-dir="direita" style="width:50px; height:40px; margin:2px; background:#ffe135; border:none; border-radius:5px; font-weight:bold; cursor:pointer;">▶</button>
        </div>
        <p style="color:#aaa; font-family:sans-serif; font-size:12px; margin-top:10px;">Usa as setas do teclado ou os botões do ecrã para controlar a cobra.</p>
        
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var btnAction = document.getElementById('btnAction');
            
            var tnt = 20;
            var cols = canvas.width / tnt, rows = canvas.height / tnt;
            var snake, dx, dy, apple, score, velocidadeMs;
            var proximaDirecao = null; // só uma mudança de direção é aplicada por "tick", evita a reversão instantânea
            var gameInterval = null;
            var gameStarted = false;
            var gameOver = false;

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
            }
            estadoInicial();
            
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

                // aplica no máximo uma mudança de direção por tick, e nunca inversão a 180º
                if (proximaDirecao) {
                    if (proximaDirecao.dx !== -dx || proximaDirecao.dy !== -dy) {
                        dx = proximaDirecao.dx; dy = proximaDirecao.dy;
                    }
                    proximaDirecao = null;
                }

                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                
                if (head.x < 0) head.x = canvas.width - tnt;
                else if (head.x >= canvas.width) head.x = 0;
                
                if (head.y < 0) head.y = canvas.height - tnt;
                else if (head.y >= canvas.height) head.y = 0;

                var vaiComer = (head.x === apple.x && head.y === apple.y);
                // se não comer, a cauda vai sair nesta jogada — não conta como colisão entrar nessa célula
                var corpoParaVerificar = vaiComer ? snake : snake.slice(0, snake.length - 1);

                for (var i = 0; i < corpoParaVerificar.length; i++) { 
                    if (corpoParaVerificar[i].x === head.x && corpoParaVerificar[i].y === head.y) {
                        triggerGameOver();
                        return;
                    } 
                }
                
                snake.unshift(head);
                if (vaiComer) {
                    score += 10;
                    if (score % 50 === 0 && velocidadeMs > 80) {
                        velocidadeMs -= 10; // fica ligeiramente mais rápido a cada 5 maçãs
                        clearInterval(gameInterval);
                        gameInterval = setInterval(game, velocidadeMs);
                    }
                    apple = novaMaca();
                } else {
                    snake.pop();
                }
                
                drawScene();
            }
            
            function toggleGame() {
                if (gameOver) { resetGame(); return; }
                if (!gameStarted) {
                    gameStarted = true;
                    btnAction.innerText = "Pause ⏸";
                    gameInterval = setInterval(game, velocidadeMs);
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
                estadoInicial();
                gameOver = false; gameStarted = true;
                btnAction.innerText = "Pause ⏸";
                gameInterval = setInterval(game, velocidadeMs);
                drawScene();
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
                if (mapa[e.keyCode]) {
                    e.preventDefault(); // impede o scroll da página com as setas
                    mudarDirecao(mapa[e.keyCode]);
                }
            });

            // botões: touchstart (resposta imediata em mobile) + click (compatibilidade com rato)
            document.querySelectorAll('button[data-dir]').forEach(function(btn) {
                btn.addEventListener('touchstart', function(e) {
                    e.preventDefault();
                    mudarDirecao(btn.getAttribute('data-dir'));
                }, {passive: false});
                btn.addEventListener('click', function() {
                    mudarDirecao(btn.getAttribute('data-dir'));
                });
            });

            btnAction.addEventListener('touchstart', function(e) { e.preventDefault(); toggleGame(); }, {passive: false});

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
    
    # VISUALIZADOR DE DADOS E EXPORTAÇÃO — SÓ VISÍVEL PARA O ADMINISTRADOR
    st.subheader("🔒 Área de Administrador")

    if "admin_autenticado" not in st.session_state:
        st.session_state.admin_autenticado = False

    if not st.session_state.admin_autenticado:
        with st.expander("Entrar como administrador"):
            password_input = st.text_input("Password de administrador", type="password", key="admin_pwd")
            if st.button("Entrar", key="admin_login_btn"):
                # A password fica nos Secrets do Streamlit (nunca no código):
                # ADMIN_PASSWORD = "a-tua-password" em .streamlit/secrets.toml
                if password_input and password_input == st.secrets.get("ADMIN_PASSWORD", None):
                    st.session_state.admin_autenticado = True
                    logging.info("Login de administrador bem-sucedido.")
                    st.rerun()
                else:
                    st.error("Password incorreta.")
                    logging.warning("Tentativa de login de administrador falhada.")
    else:
        st.success("Sessão de administrador ativa.")
        if st.button("Sair da área de administrador", key="admin_logout_btn"):
            st.session_state.admin_autenticado = False
            st.rerun()

        st.subheader("📊 Telemetria e BD")
        if os.path.exists("agente_memoria.db"):
            with open("agente_memoria.db", "rb") as f:
                st.download_button("📥 Exportar DB SQLite (.db)", f, "agente_memoria.db", "application/octet-stream", use_container_width=True)

        with st.expander("👁️ Ver Logs do Sistema"):
            if os.path.exists("auditoria_agente.log"):
                with open("auditoria_agente.log", "r", encoding="utf-8") as f:
                    linhas_log = f.readlines()[-10:]
                    for linha in linhas_log: st.caption(linha.strip())

        with st.expander("🗄️ Histórico Permanente Global (BD) — todas as sessões"):
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

# --- ÁREA DO CHAT PRINCIPAL ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

    with st.expander("🏆 Leaderboard — guardar a minha pontuação", expanded=False):
        st.caption("O jogo corre isolado num iframe e não consegue enviar a pontuação automaticamente — introduz o valor que vês no ecrã do jogo.")
        col_nome, col_score = st.columns([2, 1])
        nome_jogador = col_nome.text_input("O teu nome", key="leaderboard_nome", max_chars=30)
        pontuacao_jogador = col_score.number_input("Pontuação", key="leaderboard_score", min_value=0, step=10)

        if st.button("💾 Guardar no Leaderboard", key="leaderboard_guardar"):
            if not nome_jogador.strip():
                st.warning("Introduz um nome antes de guardar.")
            else:
                if guardar_pontuacao_leaderboard(nome_jogador, int(pontuacao_jogador)):
                    st.success(f"Pontuação de {pontuacao_jogador} guardada para {nome_jogador}! 🎉")
                else:
                    st.error("Não foi possível gravar a pontuação. Tenta novamente.")

        st.markdown("**Top 10:**")
        top_scores = obter_top_leaderboard(10)
        if top_scores:
            for i, (nome, pontos, ts) in enumerate(top_scores, start=1):
                medalha = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
                st.markdown(f"{medalha} **{nome}** — {pontos} pontos")
        else:
            st.caption("Ainda ninguém guardou pontuação. Sê o primeiro!")

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

if "ultimo_audio_processado_id" not in st.session_state:
    st.session_state.ultimo_audio_processado_id = None

if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    # st.audio_input NÃO se limpa sozinho como o chat_input — fica retido na sessão.
    # Sem esta verificação, qualquer rerun não relacionado (abrir o jogo, entrar como
    # admin, um refresh que reconecta a sessão) reprocessava e reenviava o MESMO áudio
    # à API repetidamente, consumindo quota sem o utilizador saber.
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
                Responde de forma concisa em Português de Portugal utilizando sempre a Knowledge Base e ferramentas.

                Tens duas ferramentas relacionadas com a Guimabus, para perguntas diferentes:
                - obter_dados_guimabus: estado em tempo real da frota (posições/atrasos dos autocarros já em circulação). Aceita opcionalmente um "route_id" para filtrar por linha.
                - obter_horarios_paragem: previsão de tempos de espera/carreiras para uma paragem específica (precisa do ID numérico da paragem).

                REGRAS IMPORTANTES para usar estas ferramentas (para poupar chamadas à API, que têm limite):
                1. Chama NO MÁXIMO uma ferramenta por pergunta. Nunca tentes as duas seguidas "para ver qual dá melhor resultado".
                2. Se a pergunta do utilizador for vaga (ex: "que horários há agora?", sem indicar linha ou paragem), NÃO chames nenhuma ferramenta — pergunta primeiro ao utilizador se quer saber da frota em geral (e nesse caso podes indicar um route_id se ele mencionar uma linha) ou de uma paragem específica (nesse caso precisas do ID da paragem).
                3. Se uma ferramenta já respondeu (mesmo que a resposta seja "sem dados disponíveis"), não voltes a chamá-la nem chames a outra à procura de mais informação — reporta o resultado obtido ao utilizador tal como está.

                REGRA ANTI-ALUCINAÇÃO — A MAIS IMPORTANTE DE TODAS:
                NUNCA inventes, estimes ou "preenchas" dados que as ferramentas ou a Knowledge Base não te deram. Isto inclui: números de autocarro, atrasos, percursos, horários, ou nomes/números de linhas. NUNCA digas que "consultaste" uma ferramenta, cache ou base de dados que não chamaste de facto. Se as ferramentas devolverem uma lista vazia ou sem essa informação, e a Knowledge Base também não a tiver, diz clara e honestamente ao utilizador que não tens essa informação disponível neste momento — nunca substituas por uma resposta que pareça plausível mas seja inventada. É preferível admitir "não sei" do que dar uma resposta errada com aparência de certeza."""
                
                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                PROMPT_HELPDESK_TUTOR = """Tu és um Tutor Técnico de Helpdesk e Suporte de IT.
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
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem]
                
                # Execução Resiliente com Fallback e timeout explícito (evita pedidos "pendurados")
                TIMEOUT_SEGUNDOS = 25
                # Cadeia de candidatos com os modelos atuais e suportados (verificado em julho 2026):
                # gemini-3.5-flash é o modelo Flash mais recente e capaz (GA desde maio 2026).
                # Os antigos "gemini-2.0-flash" / "gemini-2.0-flash-lite" foram desativados
                # pela Google a 1 de junho de 2026 e já não podem ser usados.
                candidatos_modelo = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

                response = None
                ultimo_erro_modelo = None
                for nome_modelo in candidatos_modelo:
                    try:
                        model = genai.GenerativeModel(
                            model_name=nome_modelo,
                            system_instruction=prompt_sistema_ativo,
                            tools=ferramentas_agente
                        )
                        chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                        response = chat.send_message(
                            prompt_enriquecido,
                            request_options={"timeout": TIMEOUT_SEGUNDOS}
                        )
                        if nome_modelo != candidatos_modelo[0]:
                            logging.warning(f"Modelo principal falhou; resposta obtida com fallback '{nome_modelo}'.")
                            st.info(f"ℹ️ Modelo principal indisponível — resposta gerada com '{nome_modelo}'.")
                        break  # sucesso, não tenta os restantes
                    except Exception as e:
                        ultimo_erro_modelo = e
                        motivo = "limite de quota (429)" if "429" in str(e) else ("timeout" if "timeout" in str(e).lower() or "deadline" in str(e).lower() else str(e))
                        logging.warning(f"Modelo '{nome_modelo}' falhou ({motivo}). A tentar o próximo candidato, se existir.")
                        continue

                if response is None:
                    logging.error(f"Todos os modelos candidatos falharam. Último erro: {ultimo_erro_modelo}")
                    if ultimo_erro_modelo is not None and "429" in str(ultimo_erro_modelo):
                        st.error("🚫 Limite diário gratuito da API do Gemini esgotado. Tenta novamente mais tarde (a quota costuma renovar-se ao fim de 24h), ou ativa faturação na Google AI Studio para aumentar o limite.")
                    else:
                        st.error("🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento. Tenta novamente dentro de instantes.")
                    st.stop()

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
