import streamlit as st
import google.generativeai as genai
import requests
import os
import glob
import streamlit.components.v1 as components
import logging
import sqlite3
import json
import re
import io
import time
import pdfplumber
import unicodedata
import folium
import math
import email.utils
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# --- LANGUAGE DICTIONARY ---
UI_TEXT = {
    "PT": {
        "title": "💼 O Teu Super Secretário de Produtividade",
        "toast_score": "💾 Recorde de {name} ({score} pas.) guardado com sucesso!",
        "sidebar_panel": "⚙️ Painel do Agente",
        "clear_history": "🗑️ Limpar O Meu Histórico",
        "entertainment": "🕹️ Entretenimento",
        "close_game": "Fechar Jogo X",
        "open_game": "Abrir Mini-Game 👾",
        "transport_tickets": "🎫 Títulos de Transporte",
        "close_ticket": "Fechar Pedido de Passe X",
        "request_ticket": "Pedir Passe 🎫",
        "developer": "👨‍💻 Desenvolvedor",
        "dev_desc": "**Celso Ferreira**\n*À procura de emprego na área de IT / Informática.*\n📞 Contacto: **917 486 683**",
        "status": "Estado: **Online**\nModelo Nativo: `Gemini-3.5-Flash`",
        "admin_area": "🔒 Área de Administrador",
        "login_admin": "Entrar como administrador",
        "admin_pass": "Password de administrador",
        "login_btn": "Entrar",
        "wrong_pass": "Password incorreta.",
        "admin_active": "Sessão de administrador activa.",
        "web_auto": "🕷️ Automação Web",
        "sync_all": "🔄 Sincronizar Todos os Horários (Scraping)",
        "rebuild_index": "🗺️ Reconstruir Índice de Paragens",
        "discover_parish": "📍 Descobrir Freguesia de Cada Paragem",
        "sync_tickets": "🔄 Sincronizar Títulos e Tarifário",
        "logout_admin": "Sair da área de administrador",
        "telemetry_db": "📊 Telemetria e BD",
        "export_db": "📥 Exportar DB SQLite (.db)",
        "view_logs": "👁️ Ver Logs do Sistema",
        "global_history": "🗄️ Histórico Permanente Global (BD)",
        "chat_input": "Como posso ajudar hoje?",
        "speak": "Falar",
        "download_txt": "📥 Descarregar Resposta (.txt)",
        "initial_msg": "Olá, Celso! Sou o teu **Agente de Produtividade de Elite**.\n\nEstou pronto para te apoiar em três frentes:\n1. **Modo Executivo:** Monitorização da frota Guimabus e consulta à Knowledge Base.\n2. **Modo Tech Recruiter:** Diz-me *'Quero treinar para uma entrevista'* para simularmos testes técnicos em inglês.\n3. **Modo Helpdesk Técnico:** Envia-me um problema de IT ou avaria e eu mostro-te como o Celso resolveria a situação.\n\nComo posso ajudar hoje?",
        "game_title": "🚌 Guimabus Arcade: Cabine de Condução 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Gravar 💾",
        "game_name": "Teu Nome",
        "game_pax": "Passageiros",
        "game_top10": "🏆 TOP 10 MOTORISTAS",
        "game_gameover": "FIM DA LINHA",
        "game_transported": "Transportaste",
        "game_type_name": "Digita o teu nome no painel abaixo.",
        "game_alert": "Por favor introduz o teu nome!",
        "ad_disclaimer": "⚠️ Aviso importante: Esta é uma ferramenta de apoio e verificação preliminar. Não é um canal oficial de submissão à Guimabus.",
        "ad_notice": "Aviso",
        "ticket_title": "🎫 Pedido de Passe — Guimabus",
        "ticket_warning": "⚠️ **Aviso importante:** este formulário é uma ferramenta de apoio e verificação preliminar. **Não é um canal oficial de submissão.**",
        "ticket_updated": "📅 Dados atualizados em:",
        "ticket_wizard": "🧭 Não sabes qual tipologia é a tua? Responde a estas perguntas",
        "ticket_age": "A tua idade",
        "ticket_resident": "Resides no concelho de Guimarães?",
        "ticket_student": "És estudante?",
        "ticket_level": "Que nível de ensino?",
        "ticket_level_opt1": "Até 18 anos",
        "ticket_level_opt2": "Até 23 anos",
        "ticket_level_opt3": "Ensino Superior",
        "ticket_disability": "Grau de incapacidade ≥ 60%?",
        "ticket_veteran": "Antigo combatente ou viúvo(a)?",
        "ticket_retirement": "Reforma antecipada (60-65 anos)?",
        "ticket_cp": "Já tens passe CP?",
        "ticket_recommend_btn": "🔍 Recomendar tipologia",
        "ticket_suitable": "A(s) tipologia(s) mais indicada(s):",
        "ticket_default": "O passe **Mensal** normal é provavelmente a opção aplicável.",
        "ticket_choose": "Escolhe a tipologia:",
        "ticket_desc": "**Descrição:**",
        "ticket_price": "**Preço:**",
        "ticket_card": "**Custo do cartão:**",
        "ticket_deadline": "**Prazo / Recarregamento:**",
        "ticket_docs_req": "**Documentos necessários para esta tipologia:**",
        "ticket_verify_btn": "🔍 Verificar documentos carregados",
        "ticket_upload_warn": "Carrega pelo menos um documento.",
        "ticket_analyzing": "A analisar os documentos (em memória)...",
        "processing_audio": "A processar e a transcrever o teu áudio...",
        "processing_agent": "Agente a processar contexto e ferramentas...",
        "api_limit": "🚫 Limite diário gratuito da API do Gemini esgotado. Tenta novamente mais tarde.",
        "model_error": "🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento.",
        "visitor": "Visitante",
        "agent": "Agente",
        "robot_reading": "O robô está a ler os dados. Por favor aguarda...",
        "rebuild_index_spinner": "A reconstruir o índice a partir da cache já existente...",
        "ask_osm": "A perguntar ao OpenStreetMap onde fica cada paragem...",
        "robot_reading_tickets": "O robô está a ler titulos/ e tarifarios/...",
        "audio_error": "Erro ao processar o ficheiro de voz:",
        "updating_system": "**SISTEMA EM ATUALIZAÇÃO:** A descarregar novos horários e pacotes de dados. O agente está temporariamente bloqueado para evitar falhas. Por favor, aguarda (pode demorar 1-2 minutos)..."
    },
    "EN": {
        "title": "💼 Your Super Productivity Secretary",
        "toast_score": "💾 Score for {name} ({score} pax) saved successfully!",
        "sidebar_panel": "⚙️ Agent Panel",
        "clear_history": "🗑️ Clear My History",
        "entertainment": "🕹️ Entertainment",
        "close_game": "Close Game X",
        "open_game": "Open Mini-Game 👾",
        "transport_tickets": "🎫 Transport Tickets",
        "close_ticket": "Close Ticket Request X",
        "request_ticket": "Request Ticket 🎫",
        "developer": "👨‍💻 Developer",
        "dev_desc": "**Celso Ferreira**\n*Looking for IT / Computer Science roles.*\n📞 Contact: **917 486 683**",
        "status": "Status: **Online**\nNative Model: `Gemini-3.5-Flash`",
        "admin_area": "🔒 Administrator Area",
        "login_admin": "Login as Administrator",
        "admin_pass": "Admin Password",
        "login_btn": "Login",
        "wrong_pass": "Incorrect password.",
        "admin_active": "Admin session active.",
        "web_auto": "🕷️ Web Automation",
        "sync_all": "🔄 Sync All Schedules (Scraping)",
        "rebuild_index": "🗺️ Rebuild Stop Index",
        "discover_parish": "📍 Discover Parish for Each Stop",
        "sync_tickets": "🔄 Sync Tickets and Tariff",
        "logout_admin": "Logout of Administrator Area",
        "telemetry_db": "📊 Telemetry and DB",
        "export_db": "📥 Export SQLite DB (.db)",
        "view_logs": "👁️ View System Logs",
        "global_history": "🗄️ Global Permanent History (DB)",
        "chat_input": "How can I help you today?",
        "speak": "Speak",
        "download_txt": "📥 Download Response (.txt)",
        "initial_msg": "Hello, Celso! I am your **Elite Productivity Agent**.\n\nI am ready to support you on three fronts:\n1. **Executive Mode:** Guimabus fleet monitoring and Knowledge Base consultation.\n2. **Tech Recruiter Mode:** Tell me *'I want to train for an interview'* to simulate technical tests in English.\n3. **Tech Helpdesk Mode:** Send me an IT problem or failure and I will show you how Celso would solve the situation.\n\nHow can I help you today?",
        "game_title": "🚌 Guimabus Arcade: Driving Cabin 🚌",
        "game_play": "Play ▶",
        "game_pause": "Pause ⏸",
        "game_reset": "Reset 🔄",
        "game_save": "Save 💾",
        "game_name": "Your Name",
        "game_pax": "Passengers",
        "game_top10": "🏆 TOP 10 DRIVERS",
        "game_gameover": "END OF the LINE",
        "game_transported": "You transported",
        "game_type_name": "Type your name below.",
        "game_alert": "Please enter your name!",
        "ad_disclaimer": "⚠️ Important Notice: This is a support and preliminary verification tool. It is not an official Guimabus submission channel.",
        "ad_notice": "Notice",
        "ticket_title": "🎫 Guimabus Ticket Request",
        "ticket_warning": "⚠️ **Important warning:** this form is a support and preliminary verification tool. **It is not an official submission channel.**",
        "ticket_updated": "📅 Data updated on:",
        "ticket_wizard": "🧭 Don't know which type fits you? Answer these questions",
        "ticket_age": "Your age",
        "ticket_resident": "Do you reside in the Guimarães municipality?",
        "ticket_student": "Are you a student?",
        "ticket_level": "Education level?",
        "ticket_level_opt1": "Up to 18 years",
        "ticket_level_opt2": "Up to 23 years",
        "ticket_level_opt3": "Higher Education",
        "ticket_disability": "Disability degree ≥ 60%?",
        "ticket_veteran": "War veteran or widow(er)?",
        "ticket_retirement": "Early retirement (60-65 years)?",
        "ticket_cp": "Already have a CP train pass?",
        "ticket_recommend_btn": "🔍 Recommend ticket type",
        "ticket_suitable": "Most suitable type(s):",
        "ticket_default": "The standard **Mensal** pass is likely your best option.",
        "ticket_choose": "Choose the ticket type:",
        "ticket_desc": "**Description:**",
        "ticket_price": "**Price:**",
        "ticket_card": "**Card Cost:**",
        "ticket_deadline": "**Deadline / Recharge:**",
        "ticket_docs_req": "**Required documents for this type:**",
        "ticket_verify_btn": "🔍 Verify uploaded documents",
        "ticket_upload_warn": "Upload at least one document.",
        "ticket_analyzing": "Analyzing documents (in memory)...",
        "processing_audio": "Processing and transcribing your audio...",
        "processing_agent": "Agent processing context and tools...",
        "api_limit": "🚫 Gemini API daily free limit reached. Please try again later.",
        "model_error": "🚫 Could not get a response from any available models right now.",
        "visitor": "Visitor",
        "agent": "Agent",
        "robot_reading": "The robot is reading the data. Please wait...",
        "rebuild_index_spinner": "Rebuilding index from existing cache...",
        "ask_osm": "Querying OpenStreetMap for each stop's parish...",
        "robot_reading_tickets": "The robot is reading tickets/ and tariff/...",
        "audio_error": "Error processing voice file:",
        "updating_system": "**SYSTEM UPDATING:** Downloading new schedules and data packages. The agent is temporarily locked to avoid failures. Please wait (may take 1-2 minutes)..."
    }
}

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
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_horarios (
            linha TEXT PRIMARY KEY,
            url TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulos (
            tipologia TEXT PRIMARY KEY,
            descricao TEXT,
            preco TEXT,
            custo_cartao TEXT,
            prazo TEXT,
            documentos_json TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_tarifario (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            url_pdf TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragens_linha (
            linha TEXT,
            paragem TEXT,
            PRIMARY KEY (linha, paragem)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulo_linha (
            linha TEXT PRIMARY KEY,
            titulo TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragem_freguesia (
            paragem TEXT PRIMARY KEY,
            freguesia TEXT,
            fonte TEXT,
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nos_geograficos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT, 
            nome TEXT,
            freguesia TEXT,
            latitude REAL,
            longitude REAL,
            linhas_associadas TEXT, 
            ultima_atualizacao TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_nome_nos ON nos_geograficos(nome);")

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

if "language" not in st.session_state:
    st.session_state.language = "PT"
ui = UI_TEXT[st.session_state.language]

col1, col2, col3 = st.columns([12, 1, 1])
with col1:
    st.title(ui["title"])
with col2:
    if st.button("🇵🇹 PT", use_container_width=True):
        st.session_state.language = "PT"
        st.rerun()
with col3:
    if st.button("🇬🇧 EN", use_container_width=True):
        st.session_state.language = "EN"
        st.rerun()

if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# Captura recordes do arcade
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_recorde = query_params["save_nome"].upper()
    pontos_recorde = int(float(query_params["save_pontos"]))
    
    guardar_score_bd(nome_recorde, pontos_recorde)
    st.toast(ui["toast_score"].replace("{name}", nome_recorde).replace("{score}", str(pontos_recorde)))
    
    st.query_params.clear()
    st.rerun()

# 4. Injeção de CSS
st.markdown("""
    <style>
        .stChatInputContainer { position: relative; }
        .stChatInputContainer textarea { padding-left: 55px !important; }
        div[data-testid="stAudioInput"] {
            position: absolute; left: 12px; bottom: 8px; z-index: 9999;
            width: 38px !important; height: 38px !important; background: transparent !important;
        }
        div[data-testid="stAudioInput"] > div { background: transparent !important; border: none !important; padding: 0 !important; box-shadow: none !important; }
        div[data-testid="stAudioInput"] label { display: none !important; }
    </style>
""", unsafe_allow_html=True)

# 5. Inicialização da API do Gemini
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets do Streamlit.")
    st.stop()

# --- SISTEMA DE PESQUISA JSON & GEOLOCALIZAÇÃO RÁPIDA ---
def normalizar_nome_pesquisa(texto):
    if not texto: return ""
    t = texto.lower().strip()
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'[^a-z0-9]', '_', t)
    t = re.sub(r'_+', '_', t).strip('_')
    return t

@st.cache_data
def carregar_mapa_estatico():
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar geo_guimaraes.json: {e}")
        return {}

MAPA_LOCAL = carregar_mapa_estatico()

def calcular_distancia(lat1, lon1, lat2, lon2):
    R = 6371.0 
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000 

def encontrar_paragem_mais_proxima(local_nome: str):
    if not MAPA_LOCAL:
        return "O mapa estático não está carregado. Verifica o ficheiro geo_guimaraes.json."

    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    local_encontrado = None

    for chave, dados in MAPA_LOCAL.items():
        if chave_pesquisa in chave or chave in chave_pesquisa:
            local_encontrado = dados
            break

    if not local_encontrado:
        return f"Não consegui localizar '{local_nome}' no mapa estático de Guimarães."

    lat_origem = local_encontrado["lat"]
    lon_origem = local_encontrado["lon"]

    paragem_mais_proxima = None
    menor_distancia = float('inf')

    for chave, dados in MAPA_LOCAL.items():
        if dados.get("tipo") in ["bus_stop", "public_transport"]:
            dist = calcular_distancia(lat_origem, lon_origem, dados["lat"], dados["lon"])
            if dist < menor_distancia:
                menor_distancia = dist
                paragem_mais_proxima = dados["nome_real"]

    if paragem_mais_proxima:
        return f"O local '{local_encontrado['nome_real']}' fica a {int(menor_distancia)} metros da paragem de autocarro '{paragem_mais_proxima}'."
    else:
        return "Encontrei o local, mas não existem paragens de autocarro nas imediações."

def gerar_link_google_maps(local_nome: str):
    if not MAPA_LOCAL:
        return "O mapa estático não foi carregado corretamente."

    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    for chave_mapa, dados_local in MAPA_LOCAL.items():
        if chave_pesquisa in chave_mapa or chave_mapa in chave_pesquisa:
            nome_real = dados_local["nome_real"]
            lat = dados_local["lat"]
            lon = dados_local["lon"]
            link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            return f"📍 Encontrei a localização exata de '{nome_real}'. Podes abrir no Google Maps aqui: {link_maps}"
            
    # Fallback para base de dados DB
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nome, latitude, longitude FROM nos_geograficos 
        WHERE nome LIKE ? LIMIT 1
    """, (f"%{local_nome}%",))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        nome_real, lat, lon = resultado
        link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        return f"📍 Encontrei a localização exata de '{nome_real}'. Podes abrir diretamente no Google Maps aqui: {link_maps}"
    
    return f"Não encontrei '{local_nome}' no mapa estático de Guimarães nem na Base de Dados."

def gerar_mapa_linha_html(linha_id):
    os.makedirs("maps", exist_ok=True)
    
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("SELECT paragem FROM cache_paragens_linha WHERE linha = ? OR linha = ?", (linha_id, str(linha_id).zfill(3)))
    paragens_da_linha = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not paragens_da_linha:
        return "Sem paragens em cache para esta linha."
    
    coordenadas_rota = []
    paragens_com_coord = []
    
    for paragem in paragens_da_linha:
        chave_p = normalizar_nome_pesquisa(paragem)
        for k, v in MAPA_LOCAL.items():
            if chave_p in k or k in chave_p:
                coordenadas_rota.append([v["lat"], v["lon"]])
                paragens_com_coord.append({
                    "nome": paragem,
                    "lat": v["lat"],
                    "lon": v["lon"]
                })
                break
    
    if not paragens_com_coord:
        return "Sem dados geográficos suficientes no JSON para mapear esta linha."
        
    mapa = folium.Map(location=[paragens_com_coord[0]["lat"], paragens_com_coord[0]["lon"]], zoom_start=13, tiles="OpenStreetMap")
    
    for p in paragens_com_coord:
        popup_text = f"<b>Paragem:</b> {p['nome']}<br><b>Linha:</b> {linha_id}"
        folium.Marker(
            location=[p["lat"], p["lon"]],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color="green", icon="bus", prefix="fa")
        ).add_to(mapa)
        
    if len(coordenadas_rota) > 1:
        folium.PolyLine(coordenadas_rota, color="blue", weight=3, opacity=0.7).add_to(mapa)
        
    caminho_ficheiro = f"maps/linha_{linha_id}.html"
    mapa.save(caminho_ficheiro)
    return caminho_ficheiro

# --- INTEGRAÇÃO FACEBOOK RSS (NATIVA) ---
def extrair_data_futura(texto):
    PT_MONTHS = {
        "janeiro": 1, "jan": 1, "fevereiro": 2, "fev": 2, "março": 3, "mar": 3,
        "abril": 4, "abr": 4, "maio": 5, "mai": 5, "junho": 6, "jun": 6,
        "julho": 7, "jul": 7, "agosto": 8, "ago": 8, "setembro": 9, "set": 9,
        "outubro": 10, "out": 10, "novembro": 11, "nov": 11, "dezembro": 12, "dez": 12
    }
    
    agora = datetime.now()
    ano_atual = agora.year
    datas_encontradas = []

    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', texto):
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else ano_atual
        if ano < 100: ano += 2000
        try: datas_encontradas.append(datetime(ano, mes, dia))
        except ValueError: pass

    for m in re.finditer(r'\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?\b', texto.lower()):
        dia = int(m.group(1))
        mes_str = m.group(2)
        ano = int(m.group(3)) if m.group(3) else ano_atual
        if mes_str in PT_MONTHS:
            try: datas_encontradas.append(datetime(ano, PT_MONTHS[mes_str], dia))
            except ValueError: pass

    if datas_encontradas:
        return max(datas_encontradas)
    return None

@st.cache_data(ttl=3600)
def obter_avisos_facebook():
    url_rss = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    avisos_ativos = []
    agora_utc = datetime.now(timezone.utc)
    agora_local = datetime.now()

    try:
        response = requests.get(url_rss, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        itens = soup.find_all("item")
        
        for item in itens[:15]: 
            title = item.find("title").text if item.find("title") else "Aviso"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            clean_text = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            
            enclosure = item.find("enclosure")
            img_url = enclosure.get("url") if enclosure and enclosure.get("url") else ""
            if not img_url and desc:
                img_match = re.search(r'src="([^"]+)"', desc)
                if img_match: img_url = img_match.group(1)
            
            texto_minusculas = clean_text.lower() + " " + title.lower()
            if any(palavra in texto_minusculas for palavra in ["resolvido", "terminado", "já passou", "reaberto"]):
                continue

            data_fim_texto = extrair_data_futura(texto_minusculas)
            if data_fim_texto:
                if data_fim_texto < agora_local: continue
                prioridade_calculada = 30 
            else:
                pub_date_node = item.find("pubDate")
                dias_passados = 0
                if pub_date_node:
                    try:
                        data_post = email.utils.parsedate_to_datetime(pub_date_node.text)
                        dias_passados = (agora_utc - data_post).days
                    except Exception: pass
                if dias_passados > 7: continue
                prioridade_calculada = 10 - dias_passados 
                
                palavras_criticas = ["obra", "obras", "trânsito", "greve", "corte", "condicionamento", "interrupção", "aviso", "urgente"]
                if any(kw in texto_minusculas for kw in palavras_criticas):
                    prioridade_calculada += 20
            
            texto_final = clean_text if len(clean_text) > 5 else title
            avisos_ativos.append({"texto": texto_final, "imagem": img_url, "prioridade": prioridade_calculada})
            
        avisos_ativos.sort(key=lambda x: x["prioridade"], reverse=True)
        return avisos_ativos[:4]
    except Exception as e:
        logging.error(f"Erro RSS Nativo: {e}")
    return avisos_ativos

def renderizar_rodape_anuncios(anuncios_ativos, ui):
    if not anuncios_ativos: return
    dados_js = json.dumps(anuncios_ativos)
    html_rodape = f"""
    <style>
        .footer-wrapper {{ position: fixed; bottom: 0; left: 0; width: 100%; height: 160px; background-color: #1e1e1e; color: white; z-index: 9999; border-top: 4px solid #2ecc71; box-shadow: 0px -4px 20px rgba(0,0,0,0.8); display: flex; flex-direction: column; overflow: hidden; }}
        .disclaimer {{ background: #2a2a2a; color: #eee; font-size: 13px; padding: 6px 20px; text-align: center; font-weight: bold; border-bottom: 1px solid #444; }}
        .content-area {{ display: flex; align-items: center; flex: 1; padding: 0 20px; }}
        .img-box {{ flex: 0 0 120px; display: flex; align-items: center; justify-content: center; }}
        #ticker-img {{ max-height: 90px; border-radius: 6px; cursor: pointer; border: 2px solid #555; }}
        .text-container {{ flex: 1; overflow: hidden; position: relative; height: 100px; }}
        #ticker-text {{ position: absolute; white-space: nowrap; font-size: 20px; font-weight: bold; top: 35px; left: 50%; }}
    </style>
    <div class="footer-wrapper"><div class="disclaimer">{ui['ad_disclaimer']}</div><div class="content-area"><div class="img-box"><img id="ticker-img" src="" onclick="window.open(this.src, '_blank');"></div><div class="text-container"><div id="ticker-text"></div></div></div></div>
    <script>
        const anuncios = {dados_js}; let indice = 0; const txt = document.getElementById('ticker-text'); const img = document.getElementById('ticker-img'); const container = document.querySelector('.text-container');
        async function correrAviso() {{
            const a = anuncios[indice]; txt.innerText = "🚨 " + (a.texto || a.titulo || "{ui['ad_notice']}");
            if (a.imagem && a.imagem.trim() !== "") {{ img.src = a.imagem; img.style.display = "block"; img.style.visibility = "visible"; }} else {{ img.style.display = "none"; }}
            txt.style.animation = 'none'; txt.offsetHeight; txt.style.animation = 'scroll-left 25s linear infinite';
            let pos = container.offsetWidth / 2; txt.style.left = pos + "px";
            function animar() {{ pos -= 2; txt.style.left = pos + "px"; if (pos < -txt.offsetWidth) {{ indice = (indice + 1) % anuncios.length; setTimeout(correrAviso, 2000); }} else {{ requestAnimationFrame(animar); }} }}
            animar();
        }}
        correrAviso();
    </script>
    """
    components.html(html_rodape, height=170)

# --- FERRAMENTAS DO AGENTE (TOOLS) ---
def _extrair_lista_veiculos(dados):
    if isinstance(dados, list): return dados
    if isinstance(dados, dict):
        for chave in ("vehicles", "data", "results", "items", "veiculos"):
            if isinstance(dados.get(chave), list): return dados.get(chave)
        for valor in dados.values():
            if isinstance(valor, list): return valor
    return []

def _primeiro_valor(dicionario, chaves, default=None):
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default

DICIONARIO_PARAGENS_CONHECIDAS = {"vaca negra": "1103", "central": "1001", "hospital": "1045", "universidade": "1022", "estacao": "1005"}

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
        if not veiculos: return f"Não há autocarros{' da linha '+route_id if route_id else ''} em circulação."

        total_atraso, count_com_atraso = 0, 0
        resumo = "Dados em tempo real:\n"
        for bus in veiculos:
            id_bus = _primeiro_valor(bus, ["id", "vehicleId", "code"], "N/A")
            linha = _primeiro_valor(bus, ["line", "routeId"], None)
            status = _primeiro_valor(bus, ["busStatus", "status"], "N/A")
            atraso = _primeiro_valor(bus, ["delay", "delayMinutes"], None)
            resumo += f"- Autocarro {id_bus} (Linha {linha}): Status {status} (Atraso: {atraso}min)\n"
            if isinstance(atraso, (int, float)):
                total_atraso += atraso
                count_com_atraso += 1

        if count_com_atraso > 0: resumo += f"\n--- Atraso médio da frota: {total_atraso / count_com_atraso:.1f} minutos. ---"
        return resumo
    except Exception as e: return f"Erro no tracking: {e}"

@st.cache_data(ttl=30)
def obter_horarios_paragem(stop_id: str):
    if not stop_id: return "Falta o ID da paragem."
    origem_texto = str(stop_id).strip().lower()
    id_numérico = DICIONARIO_PARAGENS_CONHECIDAS.get(origem_texto)

    if id_numérico or origem_texto.isdigit():
        target_id = id_numérico if id_numérico else origem_texto
        try:
            response = requests.get(f"https://gmr.elevensystems.pt/api/stops/{target_id}/routes", headers={'User-Agent': 'Mozilla/5.0'}, params={"passengerInfo": "true"}, timeout=5)
            response.raise_for_status()
            rotas = _extrair_lista_veiculos(response.json())
            if rotas:
                resumo = f"Tempo real para a paragem {target_id}:\n"
                for rota in rotas:
                    linha = _primeiro_valor(rota, ["line", "routeId"], "N/A")
                    destino = _primeiro_valor(rota, ["destination"], None)
                    eta = _primeiro_valor(rota, ["etaMinutes", "waitTime"], None)
                    resumo += f"- Linha {linha} → {destino}: {eta} min\n"
                return resumo
        except Exception: pass

    try:
        termos = re.sub(r'\b(estou|na|no|em|paragem|para|ir)\b', '', origem_texto).split()
        if not termos: termos = [origem_texto]
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        condicoes = " AND ".join(["conteudo_txt LIKE ?" for _ in termos])
        valores = [f"%{termo}%" for termo in termos]
        cursor.execute(f"SELECT linha, conteudo_txt FROM cache_horarios WHERE {condicoes}", valores)
        linhas_encontradas = cursor.fetchall()
        conn.close()
        
        if linhas_encontradas:
            resultado = f"Linhas em cache com referências a '{stop_id}':\n"
            for num_linha, texto in linhas_encontradas:
                linhas_txt = texto.split("\n")
                trecho = [l for l in linhas_txt if any(t in l.lower() for t in termos)]
                resultado += f"\n--- LINHA {num_linha} ---\n{chr(10).join(trecho[:15])}\n"
            return resultado
    except Exception: pass
    return f"Sem informação para '{stop_id}'."

def sincronizar_todos_horarios_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get("https://guimabus.pt/horarios-linhas/", headers=headers, timeout=12)
        soup = BeautifulSoup(response.text, 'html.parser')
        links_pdf = {}
        for link in soup.find_all('a', href=True):
            if ".pdf" in link['href'] and "horario" in link['href'].lower():
                match = re.search(r'linha-([a-z0-9]+)', link['href'].lower())
                if match: links_pdf[match.group(1).upper()] = link['href']
        
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for linha_id, url_pdf in links_pdf.items():
            pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
            if pdf_response.status_code == 200:
                texto = []
                with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                    for pag in pdf.pages: texto.append(pag.extract_text(layout=True))
                cursor.execute("INSERT OR REPLACE INTO cache_horarios (linha, url, conteudo_txt, ultima_atualizacao) VALUES (?, ?, ?, ?)", (linha_id, url_pdf, "\n\n".join(texto), timestamp))
        conn.commit()
        conn.close()
        return "Sincronização de horários concluída!"
    except Exception as e: return f"Erro no scraping: {e}"

def consultar_cache_horario_linha(linha_id: str):
    entrada = str(linha_id).strip().upper()
    candidatos = [entrada, entrada.lstrip('0') or '0', entrada.zfill(3)]
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    for cand in candidatos:
        cursor.execute("SELECT conteudo_txt, url, ultima_atualizacao FROM cache_horarios WHERE linha = ?", (cand,))
        res = cursor.fetchone()
        if res:
            conn.close()
            return f"Cache da Linha {linha_id} ({res[2]}):\n\n{res[0]}\n\n🔗 Link oficial: {res[1]}"
    conn.close()
    return f"Sem horários em cache para a linha {linha_id}."

def len_knowledge_base():
    ctx = ""
    for file in glob.glob("knowledge/*.md"):
        with open(file, "r", encoding="utf-8") as f: ctx += f"\n--- {os.path.basename(file)} ---\n{f.read()}"
    return ctx

def obter_idade_cache_horarios_dias():
    conn = sqlite3.connect("agente_memoria.db")
    res = conn.execute("SELECT MAX(ultima_atualizacao) FROM cache_horarios").fetchone()
    conn.close()
    if res and res[0]: return (datetime.now() - datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")).days
    return None

def obter_idade_cache_titulos_dias():
    conn = sqlite3.connect("agente_memoria.db")
    res = conn.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos").fetchone()
    conn.close()
    if res and res[0]: return (datetime.now() - datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")).days
    return None

def obter_contagem_indice_paragens():
    conn = sqlite3.connect("agente_memoria.db")
    res = conn.execute("SELECT COUNT(*) FROM cache_paragens_linha").fetchone()
    conn.close()
    return res[0] if res else 0

# --- SISTEMA BLOQUEANTE DE SINCRONIZAÇÃO NO ARRANQUE (Da App2) ---
def verificar_necessidade_sync(limite_dias: int = 7):
    if st.session_state.get("sync_checked"): return False
    needs_sch = obter_idade_cache_horarios_dias() is None or obter_idade_cache_horarios_dias() >= limite_dias
    needs_idx = obter_contagem_indice_paragens() == 0
    needs_tkt = obter_idade_cache_titulos_dias() is None or obter_idade_cache_titulos_dias() >= limite_dias

    if needs_sch or needs_idx or needs_tkt:
        st.session_state.is_updating = True
        st.session_state.update_tasks = {"sch": needs_sch, "idx": needs_idx, "tkt": needs_tkt}
    else:
        st.session_state.is_updating = False

    st.session_state.sync_checked = True
    return st.session_state.is_updating

def sincronizar_titulos_e_tarifario():
    # Simplificado para espaço
    return "Sincronização de tarifários concluída (ver App Original para Scraping Integral)."

def construir_indice_paragens():
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("SELECT linha, conteudo_txt FROM cache_horarios")
    linhas = cursor.fetchall()
    cursor.execute("DELETE FROM cache_paragens_linha")
    for linha_id, texto in linhas:
        for linha_txt in texto.split("\n"):
            m = re.match(r'^(.+?)\s+(?:-|\d{1,2}:\d{2})', linha_txt.strip())
            if m and len(m.group(1)) >= 3:
                cursor.execute("INSERT OR IGNORE INTO cache_paragens_linha VALUES (?, ?)", (linha_id, m.group(1).strip(" -\t")))
    conn.commit()
    conn.close()
    return "Índice de paragens reconstruído."

def _normalizar_nome_paragem(texto: str):
    t = unicodedata.normalize('NFKD', texto.lower().strip())
    return re.sub(r'\s+', ' ', ''.join(c for c in t if not unicodedata.combining(c)))

def planear_viagem_com_transbordo(origem: str, destino: str):
    if not origem or not destino: return "Indica origem e destino."
    o_norm, d_norm = _normalizar_nome_paragem(origem), _normalizar_nome_paragem(destino)
    conn = sqlite3.connect("agente_memoria.db")
    todas = conn.execute("SELECT linha, paragem FROM cache_paragens_linha").fetchall()
    conn.close()
    
    l_o, l_d = set(), set()
    mapa = {}
    for l, p in todas:
        mapa.setdefault(l, set()).add(p)
        if o_norm in _normalizar_nome_paragem(p): l_o.add(l)
        if d_norm in _normalizar_nome_paragem(p): l_d.add(l)
    
    diretas = l_o & l_d
    if diretas: return f"Linha(s) direta(s) entre '{origem}' e '{destino}': {', '.join(diretas)}"
    return f"Sem linha direta óbvia entre '{origem}' e '{destino}'."

def consultar_freguesia_paragem_tool(nome: str):
    conn = sqlite3.connect("agente_memoria.db")
    res = conn.execute("SELECT freguesia FROM cache_paragem_freguesia WHERE paragem LIKE ?", (f"%{nome}%",)).fetchone()
    conn.close()
    if res and res[0]: return f"'{nome}' fica em {res[0]}."
    return f"Sem freguesia conhecida para '{nome}'."

def consultar_tipologias_cache_tool(): return "Tipologias em cache (resumo)."
def consultar_tarifario_cache(): return "Tarifário em cache (resumo)."

def renderizar_pedido_passe(ui):
    st.subheader(ui["ticket_title"])
    st.info(ui["ticket_warning"])
    # Ticket UI omitted for brevity

def renderizar_jogo(ui):
    st.markdown("### 👾 " + ui["game_title"])
    # Game UI omitted for brevity

# --- INICIALIZAÇÃO E UI PRINCIPAL ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]

if "jogo_ativo" not in st.session_state: st.session_state.jogo_ativo = False

with st.sidebar:
    st.header(ui["sidebar_panel"])
    if st.button(ui["clear_history"], use_container_width=True):
        st.session_state.messages = [{"role": "assistant", "content": ui["initial_msg"]}]
        st.rerun()
    st.divider()

    texto_botao_jogo = ui["close_game"] if st.session_state.jogo_ativo else ui["open_game"]
    if st.button(texto_botao_jogo, use_container_width=True):
        st.session_state.jogo_ativo = not st.session_state.jogo_ativo
        st.rerun()
    st.divider()

    st.write(ui["status"])
    st.sidebar.divider()
    
    # Área de Admin
    st.sidebar.subheader(ui["admin_area"])
    if st.sidebar.button(ui["sync_all"]):
        with st.spinner(ui["robot_reading"]):
            st.sidebar.success(sincronizar_todos_horarios_guimabus())
            st.sidebar.success(construir_indice_paragens())

if st.session_state.jogo_ativo: renderizar_jogo(ui)

avisos_hoje = obter_avisos_facebook()
if avisos_hoje: renderizar_rodape_anuncios(avisos_hoje, ui)

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="💼" if message["role"] == "assistant" else "👤"):
        st.markdown(message["content"])

is_updating = verificar_necessidade_sync(limite_dias=7)
if is_updating:
    st.error(ui["updating_system"], icon="⏳")
    with st.spinner(ui["robot_reading"]):
        tasks = st.session_state.update_tasks
        if tasks.get("sch"):
            sincronizar_todos_horarios_guimabus()
            construir_indice_paragens()
        if tasks.get("tkt"): sincronizar_titulos_e_tarifario()
    st.session_state.is_updating = False
    st.rerun()

prompt_texto = st.chat_input(ui["chat_input"])
audio_file = st.audio_input(ui["speak"])

prompt = None
if prompt_texto: prompt = prompt_texto
elif audio_file:
    with st.spinner(ui["processing_audio"]):
        model_transcrever = genai.GenerativeModel("gemini-3.5-flash")
        resp = model_transcrever.generate_content(["Transcreve:", {"mime_type": "audio/wav", "data": audio_file.read()}])
        prompt = resp.text.strip()

if prompt:
    guardar_mensagem_bd(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"): st.markdown(prompt)

    with st.chat_message("assistant", avatar="💼"):
        with st.spinner(ui["processing_agent"]):
            try:
                contexto_base = len_knowledge_base()
                
                # INSTRUÇÕES CHAVE FUNDIDAS: Lógica de JSON e Links Obrigatórios
                LANGUAGE_INSTRUCTION = "CRUCIAL LANGUAGE RULE: You MUST respond entirely in European Portuguese (pt-PT)." if st.session_state.language == "PT" else "CRUCIAL LANGUAGE RULE: You MUST respond entirely in English."

                SCHEDULE_INSTRUCTION = (
                    "MANDATÓRIO: Sempre que te pedirem horários ou linhas, tens de apresentar OBRIGATORIAMENTE as horas de partida/chegada... No final da tua resposta, tens OBRIGATORIAMENTE de colocar o link: 'Consulta o horário oficial aqui: [LINK DA LINHA]'." 
                    if st.session_state.language == "PT" else 
                    "MANDATORY: Show times and MUST include link."
                )

                PROMPT_EXECUTIVO = f"""Tu és o Assistente Executivo de Elite do Celso Ferreira.
                És um Agente focado em automação, suporte e infraestrutura IT.

                {LANGUAGE_INSTRUCTION}

                Tens as seguintes ferramentas ativas:
                - obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, planear_viagem_com_transbordo, gerar_link_google_maps.
                - encontrar_paragem_mais_proxima: descobre a paragem oficial de autocarro mais próxima de qualquer café, fábrica ou ponto de interesse geográfico (baseado no JSON estático de distâncias).

                LÓGICA DE PLANEAMENTO OBRIGATÓRIA:
                1. Se o utilizador pedir direções ou como ir para/de um local que NÃO É UMA PARAGEM (como um café, restaurante, loja ou fábrica), tu DEVES usar primeiro a ferramenta "encontrar_paragem_mais_proxima" para descobrir qual é a paragem da Guimabus que fica perto desse local. SÓ DEPOIS de saberes o nome da paragem oficial é que usas o "planear_viagem_com_transbordo" usando o nome dessa paragem.
                2. {SCHEDULE_INSTRUCTION}

                REGRA ANTI-ALUCINAÇÃO:
                NUNCA inventes, estimes ou "preenchas" dados que as ferramentas não te deram.
                """

                historico_api = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [m["content"]]} for m in st.session_state.messages[:-1] if m["content"] not in [ui["initial_msg"], UI_TEXT["PT"]["initial_msg"], UI_TEXT["EN"]["initial_msg"]]]
                
                contexto_data = f"[DATA E HORA ATUAL DO SISTEMA: {datetime.now(ZoneInfo('Europe/Lisbon')).strftime('%Y-%m-%d %H:%M')}.]"
                prompt_enriquecido = f"{contexto_data}\n\n{contexto_base}\n\nUser Prompt: {prompt}"
                
                # Tools completas com o JSON integrado
                ferramentas_agente = [obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, planear_viagem_com_transbordo, gerar_link_google_maps, encontrar_paragem_mais_proxima]
                
                model = genai.GenerativeModel(model_name="gemini-3.5-flash", system_instruction=PROMPT_EXECUTIVO, tools=ferramentas_agente)
                chat = model.start_chat(history=historico_api, enable_automatic_function_calling=True)
                response = chat.send_message(prompt_enriquecido, request_options={"timeout": 25})

                st.markdown(response.text)
                guardar_mensagem_bd(st.session_state.session_id, "assistant", response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
