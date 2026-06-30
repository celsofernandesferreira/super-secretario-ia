import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components

# Configuração da página
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# --- INJEÇÃO DE CSS (ALINHAMENTO DO MICROFONE) ---
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

# Configuração da API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets.")
    st.stop()

# --- FUNÇÕES DE CONTEXTO ---
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
            return resumo
        return "Tracking indisponível."
    except Exception as e:
        return f"Erro no tracking: {e}"

def ler_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "\n--- Nota: Sem documentos na pasta 'knowledge/'. ---"

# --- JOGO EMBUTIDO ---
def renderizar_jogo():
    html_jogo = """
    <div style="text-align:center; background-color:#111; padding:20px; border-radius:10px; margin-bottom: 20px;">
        <h3 style="color:#ffe135; font-family:sans-serif; margin-top:0;">🕹️ Modo Pausa: Mini-Game Retro 🕹️</h3>
        <canvas id="stage" width="400" height="350" style="border:2px solid #ffe135; background-color:#000;"></canvas>
        <script>
            var canvas = document.getElementById('stage');
            var ctx = canvas.getContext('2d');
            var tnt = 20, snake = [{x:160, y:160}], dx = tnt, dy = 0, apple = {x:80, y:80};
            function game() {
                var head = {x: snake[0].x + dx, y: snake[0].y + dy};
                if (head.x < 0 || head.x >= canvas.width || head.y < 0 || head.y >= canvas.height) resetGame();
                for (var i = 0; i < snake.length; i++) { if (snake[i].x === head.x && snake[i].y === head.y) resetGame(); }
                snake.unshift(head);
                if (head.x === apple.x && head.y === apple.y) {
                    apple.x = Math.floor(Math.random() * (canvas.width/tnt)) * tnt;
                    apple.y = Math.floor(Math.random() * (canvas.height/tnt)) * tnt;
                } else { snake.pop(); }
                ctx.fillStyle = '#000'; ctx.fillRect(0,0,canvas.width,canvas.height);
                ctx.fillStyle = '#ffe135'; ctx.fillRect(apple.x, apple.y, tnt-2, tnt-2);
                ctx.fillStyle = '#00ff00'; for(var i=0; i<snake.length; i++) ctx.fillRect(snake[i].x, snake[i].y, tnt-2, tnt-2);
            }
            function resetGame() { snake = [{x:160, y:160}]; dx = tnt; dy = 0; }
            document.addEventListener('keydown', function(e) {
                if(e.keyCode == 37 && dx == 0) { dx = -tnt; dy = 0; }
                if(e.keyCode == 38 && dy == 0) { dx = 0; dy = -tnt; }
                if(e.keyCode == 39 && dx == 0) { dx = tnt; dy = 0; }
                if(e.keyCode == 40 && dy == 0) { dx = 0; dy = tnt; }
            });
            setInterval(game, 100);
        </script>
    </div>
    """
    components.html(html_jogo, height=450)

# --- INICIALIZAÇÃO DE ESTADOS ---
if "messages" not in st.session_state:
    st.session_state.messages = [] # Armazena o histórico no formato Streamlit

if "jogo_ativo" not in st.session_state:
    st.session_state.jogo_ativo = False

# --- SIDEBAR DE ELITE ---
with st.sidebar:
    st.header("⚙️ Painel do Agente")
    if st.button("🗑️ Limpar Histórico / Reset Memória", use_container_width=True):
        st.session_state.messages = []
        st.session_state.jogo_ativo = False
        st.rerun()
    st.divider()
    st.subheader("🕹️ Entretenimento")
    texto_botao_jogo = "Fechar Jogo X" if st.session_state.jogo_ativo else "Abrir Mini-Game 👾"
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()

PROMPT_SISTEMA = """
Tu és o Assistente Executivo de Elite do Celso Ferreira. 
És um Agente focado em automação e suporte de infraestrutura.
Responde de forma concisa utilizando sempre o contexto fornecido da Knowledge Base e o histórico da conversa para manter a continuidade do diálogo.
"""

# --- INTERFACE PRINCIPAL ---
if st.session_state.jogo_ativo:
    renderizar_jogo()

# Mostrar mensagens anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CAPTURA DE ENTRADA ---
prompt_texto = st.chat_input("Como posso ajudar hoje?")
audio_file = st.audio_input("Falar")

prompt = None
if prompt_texto:
    prompt = prompt_texto
elif audio_file:
    prompt = "Ficheiro de áudio registado na interface."

# --- FLUXO DO AGENTE ---
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agente a processar contexto..."):
            try:
                # 1. Recuperação de Conhecimento (RAG)
                contexto = ler_knowledge_base()
                if any(word in prompt.lower() for word in ["autocarro", "horário", "tracking", "onde está"]):
                    contexto += "\n" + obter_dados_guimabus()
                
                # 2. Construção da memória histórica para a API do Gemini
                # Convertemos o histórico do Streamlit para o formato de conteúdos da API do Gemini
                historico_api = []
                for msg in st.session_state.messages[:-1]: # Tudo exceto a pergunta atual
                    role_api = "model" if msg["role"] == "assistant" else "user"
                    historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                # Adicionamos a pergunta atual enriquecida com os dados capturados
                prompt_enriquecido = f"{contexto}\n\n[Histórico de Contexto Aplicado]\nPergunta Atual: {prompt}"
                
                # Execução resiliente com Fallback de Modelos
                try:
                    model = genai.GenerativeModel("gemini-3.5-flash", system_instruction=PROMPT_SISTEMA)
                    # Iniciamos o chat diretamente com o histórico para simular memória contínua
                    chat = model.start_chat(history=historico_api)
                    response = chat.send_message(prompt_enriquecido)
                except Exception as e:
                    if "429" in str(e):
                        st.warning("⚠️ Cota atingida. A alternar para modelo secundário...")
                        model = genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=PROMPT_SISTEMA)
                        chat = model.start_chat(history=historico_api)
                        response = chat.send_message(prompt_enriquecido)
                    else:
                        raise e

                full_response = response.text
                st.markdown(full_response)
                
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Erro no pipeline do agente: {e}")
