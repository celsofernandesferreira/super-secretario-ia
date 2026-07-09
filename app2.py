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
import threading
import pdfplumber
import unicodedata
import folium
import math  # <-- ADICIONADO: Para cálculos de distância GPS
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# 1. CONFIGURAÇÃO DE LOGS (Auditoria Técnica)
logging.basicConfig(
    filename="auditoria_agente.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)

# 2. CONFIGURAÇÃO DA BASE DE DADOS (SQLite Persistente com High Scores e Cache de Horários)
def inicializar_bd():
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    # Modo WAL: permite leituras normais da app enquanto a sincronização em segundo plano
    # (numa thread separada) está a escrever, em vez de bloquear tudo à espera.
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    # Tabela de histórico global
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historico_global (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            session_id TEXT,
            role TEXT,
            content TEXT
        )
    """)
    # Tabela: Sistema de High Scores
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS high_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            nome TEXT,
            pontor INTEGER
        )
    """)
    # Tabela: Cache de Horários Locais (Evita queries constantes à Web)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_horarios (
            linha TEXT PRIMARY KEY,
            url TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    # Tabela: Cache das Tipologias de Passe (scraped de guimabus.pt/titulos/)
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
    # Tabela: Cache do Tarifário (scraped de guimabus.pt/tarifarios/, PDF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_tarifario (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            url_pdf TEXT,
            conteudo_txt TEXT,
            ultima_atualizacao TEXT
        )
    """)
    # Tabela: Índice Paragem <-> Linha (construído a partir do texto dos horários já em cache),
    # usado para sugerir transbordos entre linhas.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragens_linha (
            linha TEXT,
            paragem TEXT,
            PRIMARY KEY (linha, paragem)
        )
    """)
    # Tabela: Título/descrição de cada linha (ex: "171 Quintães - Guimarães (via S. Torcato e Atães)").
    # Os títulos mencionam frequentemente freguesias que os nomes de paragem, por si só, não indicam.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_titulo_linha (
            linha TEXT PRIMARY KEY,
            titulo TEXT,
            ultima_atualizacao TEXT
        )
    """)
    # Tabela: Freguesia de cada paragem (enriquecimento único via geocodificação OpenStreetMap/Nominatim)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cache_paragem_freguesia (
            paragem TEXT PRIMARY KEY,
            freguesia TEXT,
            fonte TEXT,
            ultima_atualizacao TEXT
        )
    """)
    
    # --- NOVA TABELA: BASE GEOGRÁFICA UNIFICADA ---
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
    # Índice para buscas incrivelmente rápidas de locais
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

# Inicializa a BD no arranque
inicializar_bd()

# 3. Configuração da página 
st.set_page_config(page_title="Super Secretário IA", page_icon="💼", layout="wide")
st.title("💼 O Teu Super Secretário de Produtividade")

# Identificador único de sessão
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%H%M%S%f")

# --- CAPTURA DE RECORDES VIA URL ---
query_params = st.query_params
if "save_nome" in query_params and "save_pontos" in query_params:
    nome_recorde = query_params["save_nome"].upper()
    pontos_recorde = int(query_params["save_pontos"])
    
    guardar_score_bd(nome_recorde, pontos_recorde)
    st.toast(f"💾 Recorde de {nome_recorde} ({pontos_recorde} pas.) guardado com sucesso!")
    
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
    logging.error("Falha ao inicializar a aplicação: Chave API ausente nos Secrets.")
    st.stop()

# --- INTEGRAÇÃO FACEBOOK RSS (COM INTELIGÊNCIA ARTIFICIAL PARA DATAS) ---
@st.cache_data(ttl=3600)
def obter_avisos_facebook():
    url_rss = "https://rss.app/feeds/xF3kb9tGqqFDxAsF.xml"
    avisos_ativos = []
    
    agora = datetime.now(ZoneInfo("Europe/Lisbon"))
    data_hoje_str = agora.strftime("%d de %B de %Y")

    try:
        response = requests.get(url_rss, timeout=10)
        soup = BeautifulSoup(response.content, "xml") 
        itens = soup.find_all("item")
        posts = []
        
        for i, item in enumerate(itens[:10]):
            titulo = item.find("title").text if item.find("title") else "Aviso"
            content_encoded = item.find("content:encoded")
            desc = content_encoded.text if content_encoded else (item.find("description").text if item.find("description") else "")
            texto_limpo = BeautifulSoup(desc, "html.parser").get_text(separator=" ").strip()
            
            # --- Lógica de Extração de Imagem Robusta ---
            enclosure = item.find("enclosure")
            img_url = enclosure.get("url") if enclosure and enclosure.get("url") else ""
            
            if not img_url and desc:
                img_match = re.search(r'src="([^"]+)"', desc)
                if img_match:
                    img_url = img_match.group(1)
            
            posts.append({
                "id": i, 
                "titulo": titulo, 
                "texto": texto_limpo, 
                "imagem": img_url
            })

        # IA para filtragem e prioridade
        prompt = f"""
        Hoje é {data_hoje_str}. Analisa os posts abaixo.
        1. Identifica a data limite de cada aviso.
        2. Se a data limite já passou em relação a {data_hoje_str}, considera o aviso EXPIROU.
        3. Se o aviso é sobre obras/trânsito/greves, prioridade 5. Caso contrário, prioridade 1.
        4. Devolve APENAS um JSON: [ {{"id": 0, "prioridade": 5}}, ... ] (apenas os ATIVOS).
        Posts: {json.dumps(posts, ensure_ascii=False)}
        """
        
        model = genai.GenerativeModel("gemini-3.5-flash")
        resp = model.generate_content(prompt)
        match = re.search(r'\[(.*?)\]', resp.text, re.DOTALL)
        
        if match:
            resultado = json.loads("[" + match.group(1) + "]")
            for r in resultado:
                p = next((x for x in posts if x["id"] == r["id"]), None)
                if p:
                    avisos_ativos.append({
                        "texto": p["texto"], 
                        "imagem": p["imagem"], 
                        "prioridade": r["prioridade"]
                    })
            avisos_ativos.sort(key=lambda x: x["prioridade"], reverse=True)
            
    except Exception as e:
        logging.error(f"Erro RSS: {e}")
    return avisos_ativos

def renderizar_rodape_anuncios(anuncios_ativos):
    if not anuncios_ativos: return
    
    dados_js = json.dumps(anuncios_ativos)
    
    html_rodape = f"""
    <style>
        .footer-wrapper {{
            position: fixed; bottom: 0; left: 0; width: 100%; height: 160px;
            background-color: #1e1e1e; color: white; z-index: 9999;
            border-top: 4px solid #2ecc71; box-shadow: 0px -4px 20px rgba(0,0,0,0.8);
            display: flex; flex-direction: column; overflow: hidden;
        }}
        .disclaimer {{
            background: #2a2a2a; color: #eee; font-size: 13px; padding: 6px 20px;
            text-align: center; font-weight: bold; border-bottom: 1px solid #444;
        }}
        .content-area {{ 
            display: flex; align-items: center; flex: 1; padding: 0 20px; 
        }}
        .img-box {{ flex: 0 0 120px; display: flex; align-items: center; justify-content: center; }}
        #ticker-img {{ max-height: 90px; border-radius: 6px; cursor: pointer; border: 2px solid #555; }}
        .text-container {{ flex: 1; overflow: hidden; position: relative; height: 100px; }}
        #ticker-text {{ 
            position: absolute; white-space: nowrap; font-size: 20px; 
            font-weight: bold; top: 35px; left: 50%;
        }}
    </style>
    
    <div class="footer-wrapper">
        <div class="disclaimer">
            ⚠️ Aviso importante: Esta é uma ferramenta de apoio e verificação preliminar. Não é um canal oficial de submissão à Guimabus.
        </div>
        <div class="content-area">
            <div class="img-box">
                <img id="ticker-img" src="" onclick="window.open(this.src, '_blank');">
            </div>
            <div class="text-container">
                <div id="ticker-text"></div>
            </div>
        </div>
    </div>

    <script>
        const anuncios = {dados_js};
        let indice = 0;
        const txt = document.getElementById('ticker-text');
        const img = document.getElementById('ticker-img');
        const container = document.querySelector('.text-container');

        async function correrAviso() {{
            const a = anuncios[indice];
            
            txt.innerText = "🚨 " + (a.texto || a.titulo || "Aviso");
            
            if (a.imagem && a.imagem.trim() !== "") {{
                img.src = a.imagem;
                img.style.display = "block";
                img.style.visibility = "visible";
            }} else {{
                img.style.display = "none";
            }}
            
            txt.style.animation = 'none';
            txt.offsetHeight;
            txt.style.animation = 'scroll-left 25s linear infinite';
            
            let pos = container.offsetWidth / 2;
            txt.style.left = pos + "px";
            
            function animar() {{
                pos -= 2; 
                txt.style.left = pos + "px";
                if (pos < -txt.offsetWidth) {{
                    indice = (indice + 1) % anuncios.length;
                    setTimeout(correrAviso, 2000); 
                }} else {{
                    requestAnimationFrame(animar);
                }}
            }}
            animar();
        }}
        correrAviso();
    </script>
    """
    components.html(html_rodape, height=170)

# --- NOVAS FUNÇÕES GEOGRÁFICAS (JSON ESTÁTICO) ---
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
    """Lê o ficheiro JSON de Guimarães diretamente para a memória."""
    try:
        with open("geo_guimaraes.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar geo_guimaraes.json: {e}")
        return {}

# O mapa global carregado em milissegundos
MAPA_LOCAL = carregar_mapa_estatico()

def calcular_distancia(lat1, lon1, lat2, lon2):
    """Calcula a distância em metros entre dois pontos GPS usando a Fórmula de Haversine."""
    R = 6371.0 # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c * 1000 # Distância em metros

def encontrar_paragem_mais_proxima(local_nome: str):
    """Encontra a paragem de autocarro mais próxima de qualquer café, rua ou fábrica."""
    if not MAPA_LOCAL:
        return "O mapa estático não está carregado. Verifica o ficheiro geo_guimaraes.json."

    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    local_encontrado = None

    # 1. Encontrar as coordenadas do local pedido (Ex: "Cachorrão")
    for chave, dados in MAPA_LOCAL.items():
        if chave_pesquisa in chave or chave in chave_pesquisa:
            local_encontrado = dados
            break

    if not local_encontrado:
        return f"Não consegui localizar '{local_nome}' no mapa estático de Guimarães."

    lat_origem = local_encontrado["lat"]
    lon_origem = local_encontrado["lon"]

    # 2. Iterar por todas as paragens e calcular a distância matemática
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
    """Procura no JSON estático e gera o link do Maps"""
    if not MAPA_LOCAL:
        return "O mapa estático não foi carregado corretamente. Verifica se o ficheiro geo_guimaraes.json está na pasta."

    chave_pesquisa = normalizar_nome_pesquisa(local_nome)
    
    for chave_mapa, dados_local in MAPA_LOCAL.items():
        if chave_pesquisa in chave_mapa or chave_mapa in chave_pesquisa:
            nome_real = dados_local["nome_real"]
            lat = dados_local["lat"]
            lon = dados_local["lon"]
            link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            return f"📍 Encontrei a localização exata de '{nome_real}'. Podes abrir no Google Maps aqui: {link_maps}"
            
    return f"Não encontrei '{local_nome}' no mapa estático de Guimarães."

def gerar_mapa_linha_html(linha_id):
    """Gera o mapa visual folium cruzando a cache SQLite com o JSON Estático"""
    os.makedirs("maps", exist_ok=True)
    
    # 1. Pega nas paragens da linha
    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    cursor.execute("SELECT paragem FROM cache_paragens_linha WHERE linha = ? OR linha = ?", (linha_id, str(linha_id).zfill(3)))
    paragens_da_linha = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not paragens_da_linha:
        return "Sem paragens em cache para esta linha."
    
    coordenadas_rota = []
    paragens_com_coord = []
    
    # 2. Pesquisa cada paragem no JSON Estático
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

# --- FUNÇÕES DE CONTEXTO / FERRAMENTAS (TOOLS) ---
def _extrair_lista_veiculos(dados):
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict):
        for chave in ("vehicles", "data", "results", "items", "veiculos"):
            valor = dados.get(chave)
            if isinstance(valor, list):
                return valor
        for valor in dados.values():
            if isinstance(valor, list):
                return valor
    return []

def _primeiro_valor(dicionario, chaves, default=None):
    for chave in chaves:
        if isinstance(dicionario, dict) and chave in dicionario and dicionario[chave] is not None:
            return dicionario[chave]
    return default

# Dicionário auxiliar para mapeamento rápido de paragens críticas que dão problemas na API
DICIONARIO_PARAGENS_CONHECIDAS = {
    "vaca negra": "1103",
    "central": "1001",
    "hospital": "1045",
    "universidade": "1022",
    "estacao": "1005"
}

@st.cache_data(ttl=60)
def obter_dados_guimabus(route_id: str = None):
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
            return "Não foi possível ler os dados da Guimabus (resposta em formato inesperado)."

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
    if not stop_id:
        return "É necessário indicar o ID da paragem."
    
    origem_texto = str(stop_id).strip().lower()
    id_numérico = None
    
    for nome_p, id_p in DICIONARIO_PARAGENS_CONHECIDAS.items():
        if nome_p in origem_texto:
            id_numérico = id_p
            break
            
    if id_numérico or origem_texto.isdigit():
        target_id = id_numérico if id_numérico else origem_texto
        headers = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        url = f"https://gmr.elevensystems.pt/api/stops/{target_id}/routes"
        params = {"shape": "true", "passengerInfo": "true"}

        try:
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            dados = response.json()
            rotas = _extrair_lista_veiculos(dados)
            if rotas:
                resumo = f"Horários/previsões em tempo real para a paragem {target_id}:\n"
                for rota in rotas:
                    linha = _primeiro_valor(rota, ["line", "lineName", "route", "routeShortName", "routeId"], "N/A")
                    destino = _primeiro_valor(rota, ["destination", "headsign", "direction"], None)
                    eta = _primeiro_valor(rota, ["eta", "etaMinutes", "waitTime", "waitingTime", "arrivalTime", "nextArrival"], None)
                    destino_txt = f" → {destino}" if destino else ""
                    eta_txt = f"{eta} min" if eta is not None else "sem previsão"
                    resumo += f"- Linha {linha}{destino_txt}: {eta_txt}\n"
                return resumo
        except Exception:
            pass

    try:
        termos_pesquisa = re.sub(r'\b(estou|na|no|em|paragem|para|ir|as|os|a|o|da|do|linhas|linha|central|guimaraes|guimarães|tenho|quais|quero)\b', '', origem_texto).split()
        if not termos_pesquisa:
            termos_pesquisa = [origem_texto]

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        
        condicoes = " AND ".join(["conteudo_txt LIKE ?" for _ in termos_pesquisa])
        valores = [f"%{termo}%" for termo in termos_pesquisa]
        
        query_sql = f"SELECT linha, conteudo_txt FROM cache_horarios WHERE {condicoes}"
        cursor.execute(query_sql, valores)
        linhas_encontradas = cursor.fetchall()
        conn.close()
        
        if linhas_encontradas:
            resultado_busca = f"Varri a cache de horários local e identifiquei com sucesso as linhas que contêm referências a '{stop_id}':\n"
            for row in linhas_encontradas:
                num_linha = row[0]
                texto_completo = row[1]
                
                linhas_texto = texto_completo.split("\n")
                trecho_relevante = []
                for l in linhas_texto:
                    if any(termo in l.lower() for termo in termos_pesquisa) or "página" in l.lower() or "tabela" in l.lower():
                        trecho_relevante.append(l)
                
                contexto_linha = "\n".join(trecho_relevante[:25])
                resultado_busca += f"\n--- MAPEAMENTO AUTOMÁTICO DETETADO: LINHA {num_linha} ---\n{contexto_linha}\n"
            
            return resultado_busca
            
    except Exception as e_db:
        logging.error(f"Erro no varrimento avançado de texto em BD: {e_db}")

    return f"Não foi possível obter informação em tempo real nem encontrar registos em cache para a localização '{stop_id}'."

def sincronizar_todos_horarios_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url_principal = "https://guimabus.pt/horarios-linhas/"
    
    try:
        response = requests.get(url_principal, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links_pdf = {}
        titulos_linha = {}
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href and "horario" in href.lower():
                match = re.search(r'linha-([a-z0-9]+)', href.lower())
                if match:
                    linha_id = match.group(1).upper()
                    if linha_id not in links_pdf:
                        links_pdf[linha_id] = href
                        texto_link = link.get_text(strip=True)
                        if texto_link:
                            titulos_linha[linha_id] = texto_link
        
        if not links_pdf:
            return "Nenhum ficheiro PDF de horários localizado na página principal."
        
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        
        linhas_processadas = []
        linhas_falhadas = []
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for linha_id, url_pdf in links_pdf.items():
            sucesso = False
            ultimo_erro = None
            for tentativa in range(2):
                try:
                    pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
                    if pdf_response.status_code != 200:
                        ultimo_erro = f"HTTP {pdf_response.status_code}"
                        time.sleep(1)
                        continue

                    texto_extraido = []
                    with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
                        for idx, pagina in enumerate(pdf.pages):
                            texto_pag = pagina.extract_text(layout=True)
                            if texto_pag:
                                texto_extraido.append(f"[PÁGINA {idx+1}]\n{texto_pag}")

                    conteudo_final = "\n\n".join(texto_extraido)
                    if not conteudo_final.strip():
                        conteudo_final = "PDF em formato de imagem ou protegido contra leitura."

                    cursor.execute("""
                        INSERT OR REPLACE INTO cache_horarios (linha, url, conteudo_txt, ultima_atualizacao)
                        VALUES (?, ?, ?, ?)
                    """, (linha_id, url_pdf, conteudo_final, timestamp_atual))

                    if linha_id in titulos_linha:
                        cursor.execute("""
                            INSERT OR REPLACE INTO cache_titulo_linha (linha, titulo, ultima_atualizacao)
                            VALUES (?, ?, ?)
                        """, (linha_id, titulos_linha[linha_id], timestamp_atual))

                    linhas_processadas.append(linha_id)
                    sucesso = True
                    break
                except Exception as e:
                    ultimo_erro = str(e)
                    time.sleep(1)
                    continue

            if not sucesso:
                linhas_falhadas.append(linha_id)
                logging.error(f"Falha ao processar o PDF da linha {linha_id} após 2 tentativas: {ultimo_erro}")

            time.sleep(0.4)

        conn.commit()
        conn.close()
        
        msg_sucesso = f"Sincronização concluída: {len(linhas_processadas)}/{len(links_pdf)} PDFs descarregados e convertidos na BD local!"
        if linhas_falhadas:
            msg_sucesso += f" Falharam: {', '.join(linhas_falhadas)}."
        logging.info(msg_sucesso)
        return msg_sucesso
        
    except Exception as e:
        error_msg = f"Falha na automação de scraping dos PDFs: {e}"
        logging.error(error_msg)
        return error_msg

def consultar_cache_horario_linha(linha_id: str):
    try:
        entrada = str(linha_id).strip().upper()
        if not entrada:
            return "É necessário indicar o número da linha."

        candidatos = [entrada]
        if entrada.isdigit():
            sem_zeros = entrada.lstrip('0') or '0'
            if sem_zeros not in candidatos:
                candidatos.append(sem_zeros)
            com_tres_digitos = entrada.zfill(3)
            if com_tres_digitos not in candidatos:
                candidatos.append(com_tres_digitos)

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        resultado = None
        for candidato in candidatos:
            cursor.execute("SELECT conteudo_txt, url, ultima_atualizacao FROM cache_horarios WHERE linha = ?", (candidato,))
            resultado = cursor.fetchone()
            if resultado:
                break
        conn.close()
        
        if resultado:
            conteudo_txt, url_pdf, ultima_atualizacao = resultado
            link_txt = f"\n\n🔗 Link oficial para confirmares: {url_pdf}" if url_pdf else ""
            return f"Horários em Cache para a Linha {linha_id} (Atualizado em {ultima_atualizacao}):\n\n{conteudo_txt}{link_txt}"
        return f"Não existem horários em cache para a linha {linha_id}. Peça ao administrador para rodar a Sincronização Geral."
    except Exception as e:
        return f"Erro na leitura da cache SQLite: {e}"

def len_knowledge_base():
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "Sem documentação extra encontrada na Knowledge Base."

def obter_idade_cache_horarios_dias():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_horarios")
        resultado = cursor.fetchone()
        conn.close()
        if not resultado or not resultado[0]:
            return None
        ultima = datetime.strptime(resultado[0], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - ultima).days
    except Exception as e:
        logging.error(f"Erro ao verificar idade da cache de horários: {e}")
        return None

def obter_idade_cache_titulos_dias():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos")
        resultado = cursor.fetchone()
        conn.close()
        if not resultado or not resultado[0]:
            return None
        ultima = datetime.strptime(resultado[0], "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - ultima).days
    except Exception as e:
        logging.error(f"Erro ao verificar idade da cache de títulos: {e}")
        return None

def obter_contagem_indice_paragens():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cache_paragens_linha")
        resultado = cursor.fetchone()
        conn.close()
        return resultado[0] if resultado else 0
    except Exception as e:
        logging.error(f"Erro ao contar índice de paragens: {e}")
        return 0

# --- THREADS / BACKGROUND JOBS ---
def _sync_horarios_em_background():
    try:
        resultado = sincronizar_todos_horarios_guimabus()
        logging.info(f"[Segundo plano] Sincronização de horários: {resultado}")
        resultado_indice = construir_indice_paragens()
        logging.info(f"[Segundo plano] {resultado_indice}")
    except Exception as e:
        logging.error(f"[Segundo plano] Falha na sincronização de horários: {e}")

def _construir_indice_em_background():
    try:
        resultado_indice = construir_indice_paragens()
        logging.info(f"[Segundo plano] {resultado_indice}")
    except Exception as e:
        logging.error(f"[Segundo plano] Falha ao construir índice de paragens: {e}")

def _sync_titulos_tarifario_em_background():
    try:
        resultado = sincronizar_titulos_e_tarifario()
        logging.info(f"[Segundo plano] Sincronização de títulos/tarifário: {resultado}")
    except Exception as e:
        logging.error(f"[Segundo plano] Falha na sincronização de títulos/tarifário: {e}")

def sincronizar_automaticamente_se_necessario(limite_dias: int = 7):
    if st.session_state.get("sync_automatico_tentado_nesta_sessao"):
        return
    st.session_state.sync_automatico_tentado_nesta_sessao = True

    idade_horarios = obter_idade_cache_horarios_dias()
    if idade_horarios is None or idade_horarios >= limite_dias:
        threading.Thread(target=_sync_horarios_em_background, daemon=True).start()
        logging.info("Sincronização de horários iniciada em segundo plano.")
    elif obter_contagem_indice_paragens() == 0:
        threading.Thread(target=_construir_indice_em_background, daemon=True).start()
        logging.info("Construção do índice de paragens iniciada em segundo plano.")

    idade_titulos = obter_idade_cache_titulos_dias()
    if idade_titulos is None or idade_titulos >= limite_dias:
        threading.Thread(target=_sync_titulos_tarifario_em_background, daemon=True).start()
        logging.info("Sincronização de títulos/tarifário iniciada em segundo plano.")

TIPOLOGIAS_PASSE_FALLBACK = {
    "Mensal": {
        "descricao": "Válido para o mês e Origem/Destino para o qual foi adquirido, com nº de viagens ilimitado.",
        "preco": "Consultar tabela tarifária",
        "custo_cartao": "5€",
        "prazo": "Só pode ser emitido ou carregado até ao dia 18 de cada mês.",
        "documentos": ["Cartão de Cidadão / Documento de identificação"],
    },
}

def sincronizar_titulos_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url = "https://guimabus.pt/titulos/"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        for tag in soup.find_all(['nav', 'footer', 'form', 'script', 'style']):
            tag.decompose()

        texto_completo = soup.get_text(separator="\n")
        linhas_texto = [l.strip() for l in texto_completo.split("\n")]
        linhas_texto = [l for l in linhas_texto if l]
        texto_normalizado = "\n".join(linhas_texto)

        blocos = re.split(r'\nPASSE\n', "\n" + texto_normalizado)
        blocos = [b for b in blocos[1:]]

        if not blocos:
            return "Não foi possível identificar nenhuma tipologia de passe na página."

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tipologias_processadas = []

        for bloco in blocos:
            linhas_bloco = bloco.split("\n")
            if not linhas_bloco:
                continue
            nome_tipologia = linhas_bloco[0].strip()
            if not nome_tipologia:
                continue

            resto_texto = "\n".join(linhas_bloco[1:])

            match_prazo = re.search(r'(Só podem ser emitidos.*?\.)', resto_texto, re.IGNORECASE)
            prazo = match_prazo.group(1).strip() if match_prazo else "Prazo não indicado na página."

            match_preco = re.search(r'Preço:\s*(.+)', resto_texto)
            if match_preco:
                preco = match_preco.group(1).strip()
            elif re.search(r'\bGRATUITO\b', resto_texto, re.IGNORECASE):
                preco = "Gratuito"
            else:
                match_desconto = re.search(r'(\d{1,3}%\s*de desconto[^\n.]*\.)', resto_texto, re.IGNORECASE)
                preco = match_desconto.group(1).strip() if match_desconto else "Consultar tabela tarifária"

            match_cartao = re.search(r'Custo do cartão:\s*([\d,]+€)', resto_texto)
            custo_cartao = match_cartao.group(1).strip() if match_cartao else "Não indicado"

            match_descricao = re.match(r'(.*?)(?:Preço:|GRATUITO|Gratuito|\*\*Documentos necessários)', resto_texto, re.DOTALL)
            descricao = match_descricao.group(1).strip().replace("\n", " ") if match_descricao else ""

            match_docs = re.search(r'\*\*Documentos necessários:\*\*(.*?)(?:Só podem ser emitidos|$)', resto_texto, re.DOTALL)
            documentos = []
            if match_docs:
                candidatos_doc = [d.strip() for d in match_docs.group(1).split("\n") if d.strip()]
                for d in candidatos_doc:
                    if re.match(r'^(Custo do cartão|Preço)', d, re.IGNORECASE):
                        continue
                    documentos.append(d)
            if not documentos:
                documentos = ["Cartão de Cidadão / Documento de Identificação"]

            cursor.execute("""
                INSERT OR REPLACE INTO cache_titulos (tipologia, descricao, preco, custo_cartao, prazo, documentos_json, ultima_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nome_tipologia, descricao, preco, custo_cartao, prazo, json.dumps(documentos, ensure_ascii=False), timestamp_atual))
            tipologias_processadas.append(nome_tipologia)

        conn.commit()
        conn.close()

        msg = f"Sincronização de títulos concluída: {len(tipologias_processadas)} tipologias."
        logging.info(msg)
        return msg

    except Exception as e:
        error_msg = f"Falha ao sincronizar títulos de passe: {e}"
        logging.error(error_msg)
        return error_msg

def sincronizar_tarifario_guimabus():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url_pagina = "https://guimabus.pt/tarifarios/"

    try:
        response = requests.get(url_pagina, headers=headers, timeout=12)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        url_pdf = None
        for link in soup.find_all('a', href=True):
            href = link['href']
            if ".pdf" in href.lower() and ("tarifa" in href.lower() or "tabela" in href.lower()):
                url_pdf = href
                break
        if not url_pdf:
            for link in soup.find_all('a', href=True):
                if ".pdf" in link['href'].lower():
                    url_pdf = link['href']
                    break

        if not url_pdf:
            return "Não foi encontrado nenhum PDF de tarifário na página."

        pdf_response = requests.get(url_pdf, headers=headers, timeout=20)
        pdf_response.raise_for_status()

        texto_extraido = []
        with pdfplumber.open(io.BytesIO(pdf_response.content)) as pdf:
            for idx, pagina in enumerate(pdf.pages):
                texto_pag = pagina.extract_text(layout=True)
                if texto_pag:
                    texto_extraido.append(f"[PÁGINA {idx+1}]\n{texto_pag}")

        conteudo_final = "\n\n".join(texto_extraido)
        if not conteudo_final.strip():
            conteudo_final = "PDF em formato de imagem."

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT OR REPLACE INTO cache_tarifario (id, url_pdf, conteudo_txt, ultima_atualizacao)
            VALUES (1, ?, ?, ?)
        """, (url_pdf, conteudo_final, timestamp_atual))
        conn.commit()
        conn.close()

        msg = f"Sincronização do tarifário concluída (fonte: {url_pdf})."
        logging.info(msg)
        return msg

    except Exception as e:
        error_msg = f"Falha ao sincronizar tarifário: {e}"
        logging.error(error_msg)
        return error_msg

def sincronizar_titulos_e_tarifario():
    resultado_titulos = sincronizar_titulos_guimabus()
    resultado_tarifario = sincronizar_tarifario_guimabus()
    return f"{resultado_titulos}\n{resultado_tarifario}"

def _extrair_paragens_de_texto(texto: str):
    paragens = set()
    padrao = re.compile(r'^(?P<nome>.+?)\s+(?P<horarios>(?:-|\d{1,2}:\d{2})(?:\s+(?:-|\d{1,2}:\d{2})){2,})\s*$')
    for linha_texto in texto.split("\n"):
        linha_texto = linha_texto.strip()
        if not linha_texto or "|" in linha_texto or linha_texto.startswith("[PÁGINA") or linha_texto.startswith("[P"):
            continue
        m = padrao.match(linha_texto)
        if m:
            nome = m.group("nome").strip(" -\t")
            if len(nome) >= 3:
                paragens.add(nome)
    return paragens

def construir_indice_paragens():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, conteudo_txt FROM cache_horarios")
        linhas_cache = cursor.fetchall()

        cursor.execute("DELETE FROM cache_paragens_linha")
        total_paragens = 0
        for linha_id, conteudo_txt in linhas_cache:
            if not conteudo_txt:
                continue
            paragens = _extrair_paragens_de_texto(conteudo_txt)
            for paragem in paragens:
                cursor.execute(
                    "INSERT OR IGNORE INTO cache_paragens_linha (linha, paragem) VALUES (?, ?)",
                    (linha_id, paragem)
                )
                total_paragens += 1
        conn.commit()
        conn.close()
        msg = f"Índice de paragens reconstruído: {total_paragens} associações linha-paragem."
        logging.info(msg)
        return msg
    except Exception as e:
        error_msg = f"Falha ao construir índice de paragens: {e}"
        logging.error(error_msg)
        return error_msg

def _normalizar_nome_paragem(texto: str):
    t = texto.lower().strip()
    t = re.sub(r'\bsão\b', 's.', t)
    t = re.sub(r'\bsanta\b', 'sta.', t)
    t = re.sub(r'\bsanto\b', 'sto.', t)
    t = t.replace('.', '')
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def _procurar_linhas_por_titulo(termo_norm: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, titulo FROM cache_titulo_linha")
        todos_titulos = cursor.fetchall()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao consultar títulos de linha: {e}")
        return set(), []

    linhas_encontradas = set()
    titulos_encontrados = []
    for linha_id, titulo in todos_titulos:
        if not titulo:
            continue
        titulo_norm = _normalizar_nome_paragem(titulo)
        if re.search(r'\b' + re.escape(termo_norm) + r'\b', titulo_norm):
            linhas_encontradas.add(linha_id)
            titulos_encontrados.append(f"Linha {linha_id}: {titulo}")
    return linhas_encontradas, titulos_encontrados

def enriquecer_paragens_com_freguesia(progresso_callback=None):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT paragem FROM cache_paragens_linha")
        todas_paragens = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT paragem FROM cache_paragem_freguesia")
        ja_feitas = {row[0] for row in cursor.fetchall()}
        conn.close()
    except Exception as e:
        return f"Erro ao preparar o enriquecimento: {e}"

    paragens_a_fazer = [p for p in todas_paragens if p not in ja_feitas]
    if not paragens_a_fazer:
        return "Todas as paragens já têm freguesia associada — nada a fazer."

    headers = {
        'User-Agent': 'SuperSecretarioIA-Guimaraes/1.0'
    }

    conn = sqlite3.connect("agente_memoria.db")
    cursor = conn.cursor()
    timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sucesso = 0
    falha = 0

    for idx, paragem in enumerate(paragens_a_fazer):
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": f"{paragem}, Guimarães, Portugal",
                    "format": "json",
                    "addressdetails": 1,
                    "countrycodes": "pt",
                    "limit": 1,
                },
                headers=headers,
                timeout=10
            )
            resp.raise_for_status()
            resultados = resp.json()
            freguesia = None
            if resultados:
                endereco = resultados[0].get("address", {})
                freguesia = (endereco.get("suburb") or endereco.get("city_district")
                             or endereco.get("village") or endereco.get("town")
                             or endereco.get("municipality"))

            if freguesia:
                cursor.execute("""
                    INSERT OR REPLACE INTO cache_paragem_freguesia (paragem, freguesia, fonte, ultima_atualizacao)
                    VALUES (?, ?, ?, ?)
                """, (paragem, freguesia, "nominatim", timestamp_atual))
                sucesso += 1
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO cache_paragem_freguesia (paragem, freguesia, fonte, ultima_atualizacao)
                    VALUES (?, ?, ?, ?)
                """, (paragem, None, "sem_resultado", timestamp_atual))
                falha += 1

            if progresso_callback:
                progresso_callback(idx + 1, len(paragens_a_fazer), paragem)

        except Exception as e:
            logging.warning(f"Falha ao geocodificar '{paragem}': {e}")
            falha += 1

        time.sleep(1.1)

    conn.commit()
    conn.close()

    msg = f"Enriquecimento de freguesias concluído: {sucesso} paragens associadas, {falha} sem resultado."
    logging.info(msg)
    return msg

def obter_freguesia_de_paragem(nome_paragem: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao consultar freguesia de paragem: {e}")
        return None

    nome_norm = _normalizar_nome_paragem(nome_paragem)
    for paragem, freguesia in todas:
        paragem_norm = _normalizar_nome_paragem(paragem)
        match_direto = re.search(r'\b' + re.escape(nome_norm) + r'\b', paragem_norm)
        match_inverso = re.search(r'\b' + re.escape(paragem_norm) + r'\b', nome_norm)
        if match_direto or match_inverso:
            return freguesia
    return None

def procurar_paragens_por_freguesia(nome_freguesia: str):
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT paragem, freguesia FROM cache_paragem_freguesia WHERE freguesia IS NOT NULL")
        todas = cursor.fetchall()
        conn.close()
    except Exception as e:
        logging.error(f"Erro ao procurar paragens por freguesia: {e}")
        return []

    freguesia_norm = _normalizar_nome_paragem(nome_freguesia)
    return [
        paragem for paragem, freguesia in todas 
        if re.search(r'\b' + re.escape(freguesia_norm) + r'\b', _normalizar_nome_paragem(freguesia))
    ]

def planear_viagem_com_transbordo(origem: str, destino: str):
    if not origem or not destino:
        return "É necessário indicar a paragem de origem e a paragem de destino."

    origem_norm = _normalizar_nome_paragem(origem)
    destino_norm = _normalizar_nome_paragem(destino)

    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT linha, paragem FROM cache_paragens_linha")
        todas = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"Erro ao consultar o índice de paragens: {e}"

    if not todas:
        return ("O índice de paragens ainda não foi construído. Peça ao administrador para "
                "sincronizar os horários.")

    linhas_origem = set()
    paragens_origem_encontradas = set()
    linhas_destino = set()
    paragens_destino_encontradas = set()
    mapa_linha_paragens = {}

    for linha_id, paragem in todas:
        mapa_linha_paragens.setdefault(linha_id, set()).add(paragem)
        paragem_norm = _normalizar_nome_paragem(paragem)
        if re.search(r'\b' + re.escape(origem_norm) + r'\b', paragem_norm):
            linhas_origem.add(linha_id)
            paragens_origem_encontradas.add(paragem)
        if re.search(r'\b' + re.escape(destino_norm) + r'\b', paragem_norm):
            linhas_destino.add(linha_id)
            paragens_destino_encontradas.add(paragem)

    if not linhas_origem:
        linhas_origem, titulos_origem = _procurar_linhas_por_titulo(origem_norm)
        aviso_origem_por_titulo = bool(linhas_origem)
    else:
        aviso_origem_por_titulo = False
    if not linhas_destino:
        linhas_destino, titulos_destino = _procurar_linhas_por_titulo(destino_norm)
        aviso_destino_por_titulo = bool(linhas_destino)
    else:
        aviso_destino_por_titulo = False

    aviso_origem_por_freguesia = None
    aviso_destino_por_freguesia = None
    if not linhas_origem:
        paragens_da_freguesia = procurar_paragens_por_freguesia(origem)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalizar_nome_paragem(paragem_freg) == _normalizar_nome_paragem(paragem_indice):
                        linhas_origem.add(linha_id)
                        paragens_origem_encontradas.add(paragem_indice)
            if linhas_origem:
                aviso_origem_por_freguesia = paragens_da_freguesia
    if not linhas_destino:
        paragens_da_freguesia = procurar_paragens_por_freguesia(destino)
        if paragens_da_freguesia:
            for paragem_freg in paragens_da_freguesia:
                for linha_id, paragem_indice in todas:
                    if _normalizar_nome_paragem(paragem_freg) == _normalizar_nome_paragem(paragem_indice):
                        linhas_destino.add(linha_id)
                        paragens_destino_encontradas.add(paragem_indice)
            if linhas_destino:
                aviso_destino_por_freguesia = paragens_da_freguesia

    if not linhas_origem:
        return f"Não encontrei nenhuma paragem nem freguesia que corresponda a '{origem}'."
    if not linhas_destino:
        return f"Não encontrei nenhuma paragem nem freguesia que corresponda a '{destino}'."

    aviso_precisao = ""
    if aviso_origem_por_titulo:
        aviso_precisao += f"\n⚠️ Nota: '{origem}' encontrada pelo TÍTULO da linha (ex: {', '.join(titulos_origem[:2])})."
    if aviso_destino_por_titulo:
        aviso_precisao += f"\n⚠️ Nota: '{destino}' encontrada pelo TÍTULO da linha (ex: {', '.join(titulos_destino[:2])})."
    if aviso_origem_por_freguesia:
        aviso_precisao += f"\n📍 '{origem}' é freguesia. Paragens: {', '.join(aviso_origem_por_freguesia[:4])}."
    if aviso_destino_por_freguesia:
        aviso_precisao += f"\n📍 '{destino}' é freguesia. Paragens: {', '.join(aviso_destino_por_freguesia[:4])}."

    linhas_diretas = linhas_origem & linhas_destino
    if linhas_diretas:
        resumo = f"Encontrei linha(s) DIRETA(S) entre '{origem}' e '{destino}' (sem transbordo):\n"
        for linha_id in linhas_diretas:
            resumo += f"- Linha {linha_id}\n"
        resumo += aviso_precisao
        return resumo

    stops_linhas_origem = set()
    for linha_id in linhas_origem:
        stops_linhas_origem |= mapa_linha_paragens.get(linha_id, set())
    stops_linhas_destino = set()
    for linha_id in linhas_destino:
        stops_linhas_destino |= mapa_linha_paragens.get(linha_id, set())

    transbordos_candidatos = stops_linhas_origem & stops_linhas_destino
    transbordos_candidatos -= paragens_origem_encontradas
    transbordos_candidatos -= paragens_destino_encontradas

    if not transbordos_candidatos:
        return f"Não encontrei nenhuma linha direta nem um ponto de transbordo óbvio entre '{origem}' e '{destino}'."

    resumo = f"Não há linha direta entre '{origem}' e '{destino}'. Sugestão de transbordo:\n\n"
    for paragem_transbordo in sorted(transbordos_candidatos):
        linhas_ate_transbordo = [l for l in linhas_origem if paragem_transbordo in mapa_linha_paragens.get(l, set())]
        linhas_desde_transbordo = [l for l in linhas_destino if paragem_transbordo in mapa_linha_paragens.get(l, set())]
        resumo += f"- Via **{paragem_transbordo}**: apanha a linha {'/'.join(linhas_ate_transbordo)} desde '{origem}', desce em '{paragem_transbordo}', e apanha a linha {'/'.join(linhas_desde_transbordo)} até '{destino}'.\n"

    resumo += aviso_precisao
    return resumo

def consultar_freguesia_paragem_tool(nome: str):
    if not nome:
        return "É necessário indicar o nome da paragem ou da freguesia."

    freguesia = obter_freguesia_de_paragem(nome)
    if freguesia:
        return f"A paragem '{nome}' fica na freguesia de {freguesia}."

    paragens = procurar_paragens_por_freguesia(nome)
    if paragens:
        return f"Paragens conhecidas na freguesia de '{nome}': {', '.join(paragens)}."

    return f"Não tenho ainda informação de freguesia para '{nome}'."

def obter_tipologias_cache():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tipologia, descricao, preco, custo_cartao, prazo, documentos_json FROM cache_titulos ORDER BY tipologia")
        linhas = cursor.fetchall()
        conn.close()

        if not linhas:
            return TIPOLOGIAS_PASSE_FALLBACK, None

        resultado = {}
        for tipologia, descricao, preco, custo_cartao, prazo, documentos_json in linhas:
            try:
                documentos = json.loads(documentos_json)
            except Exception:
                documentos = [documentos_json]
            resultado[tipologia] = {
                "descricao": descricao,
                "preco": preco,
                "custo_cartao": custo_cartao,
                "prazo": prazo,
                "documentos": documentos,
            }

        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(ultima_atualizacao) FROM cache_titulos")
        ultima_atualizacao = cursor.fetchone()[0]
        conn.close()

        return resultado, ultima_atualizacao
    except Exception as e:
        logging.error(f"Erro ao ler cache de tipologias: {e}")
        return TIPOLOGIAS_PASSE_FALLBACK, None

def consultar_tarifario_cache():
    try:
        conn = sqlite3.connect("agente_memoria.db")
        cursor = conn.cursor()
        cursor.execute("SELECT conteudo_txt, ultima_atualizacao FROM cache_tarifario WHERE id = 1")
        resultado = cursor.fetchone()
        conn.close()
        if resultado:
            return f"Tabela tarifária (atualizada em {resultado[1]}):\n\n{resultado[0]}"
        return "O tarifário ainda não foi sincronizado."
    except Exception as e:
        return f"Erro na leitura da cache do tarifário: {e}"

def consultar_tipologias_cache_tool():
    tipologias, ultima_atualizacao = obter_tipologias_cache()
    if not tipologias:
        return "Não existem tipologias de passe em cache."
    aviso_idade = f" (dados de {ultima_atualizacao})" if ultima_atualizacao else ""
    resumo = f"Tipologias de passe disponíveis{aviso_idade}:\n\n"
    for nome, info in tipologias.items():
        docs_txt = "; ".join(info["documentos"])
        resumo += f"- **{nome}**: {info['descricao']} Preço: {info['preco']}. Custo do cartão: {info['custo_cartao']}. Prazo: {info['prazo']}. Documentos: {docs_txt}.\n"
    return resumo

def verificar_documentos_passe(tipologia: str, ficheiros_carregados: dict):
    tipologias_atuais, _ = obter_tipologias_cache()
    info = tipologias_atuais.get(tipologia, {"documentos": ["documento não especificado"]})
    partes = [
        f"Vais rever documentos carregados por um utilizador que pediu um passe do tipo '{tipologia}'.\n"
        f"Documentos exigidos para este tipo de passe: {', '.join(info['documentos'])}.\n\n"
        "Para CADA documento carregado abaixo (pela ordem em que aparecem), diz:\n"
        "1. Que tipo de documento parece ser.\n"
        "2. Se parece corresponder a um dos documentos exigidos.\n"
        "3. Se está legível e completo.\n"
        "Sê direto e claro. Diz também se falta carregar algum dos documentos exigidos."
    ]

    nomes_documentos = []
    for nome_doc, ficheiro in ficheiros_carregados.items():
        if ficheiro is None:
            continue
        nomes_documentos.append(nome_doc)
        try:
            dados_bytes = ficheiro.getvalue()
            mime = ficheiro.type or "application/octet-stream"
            partes.append(f"\n--- Documento carregado para: '{nome_doc}' ---")
            partes.append({"mime_type": mime, "data": dados_bytes})
        except Exception as e:
            logging.error(f"Erro ao ler ficheiro carregado '{nome_doc}': {e}")

    if not nomes_documentos:
        return "Nenhum documento foi carregado ainda."

    try:
        model_verificacao = genai.GenerativeModel("gemini-3.5-flash")
        resposta = model_verificacao.generate_content(partes, request_options={"timeout": 40})
        return resposta.text
    except Exception as e:
        return f"Não foi possível verificar os documentos neste momento: {e}"

def recomendar_tipologias_passe(respostas: dict, tipologias_disponiveis: dict):
    idade = respostas.get("idade")
    estudante = respostas.get("estudante")
    nivel_estudo = respostas.get("nivel_estudo")
    residente_gmr = respostas.get("residente_gmr")
    incapacidade_60 = respostas.get("incapacidade_60")
    antigo_combatente = respostas.get("antigo_combatente")
    usa_passe_cp = respostas.get("usa_passe_cp")
    reforma_antecipada = respostas.get("reforma_antecipada")

    candidatas = []

    def _tem(nome_parcial):
        for nome in tipologias_disponiveis:
            if nome_parcial.lower() in nome.lower():
                return nome
        return None

    if antigo_combatente and _tem("Antigo Combatente"): candidatas.append(_tem("Antigo Combatente"))
    if incapacidade_60 and _tem("Mobilidade Condicionada"): candidatas.append(_tem("Mobilidade Condicionada"))
    if idade is not None and idade >= 65 and residente_gmr and _tem("65+"): candidatas.append(_tem("65+"))
    if reforma_antecipada and idade is not None and 60 <= idade < 65 and _tem("Reformado"): candidatas.append(_tem("Reformado"))
    if estudante:
        if nivel_estudo == "superior":
            if residente_gmr and _tem("Universitário Residente"): candidatas.append(_tem("Universitário Residente"))
            elif _tem("Universitário Não Residente"): candidatas.append(_tem("Universitário Não Residente"))
        elif nivel_estudo == "ate_18" and _tem("18+TP"): candidatas.append(_tem("18+TP"))
        elif nivel_estudo == "ate_23" and _tem("23+TP"): candidatas.append(_tem("23+TP"))
    if usa_passe_cp and _tem("Mensal CP"): candidatas.append(_tem("Mensal CP"))

    if not candidatas:
        if residente_gmr and _tem("CIM AVE 50% + 10% CMG"): candidatas.append(_tem("CIM AVE 50% + 10% CMG"))
        elif residente_gmr and _tem("CIM AVE 50%"): candidatas.append(_tem("CIM AVE 50%"))
        elif _tem("Mensal") and not _tem("CIM"):
            for nome in tipologias_disponiveis:
                if nome.strip().lower() == "mensal":
                    candidatas.append(nome)
                    break

    vistos = set()
    candidatas_unicas = []
    for c in candidatas:
        if c and c not in vistos:
            vistos.add(c)
            candidatas_unicas.append(c)
    return candidatas_unicas

def renderizar_pedido_passe():
    st.subheader("🎫 Pedido de Passe — Guimabus")
    st.info("⚠️ **Aviso importante:** este formulário é uma ferramenta de apoio e verificação preliminar. **Não é um canal oficial de submissão.**")

    TIPOLOGIAS_PASSE, ultima_atualizacao = obter_tipologias_cache()
    if ultima_atualizacao:
        st.caption(f"📅 Dados de tipologias atualizados em: {ultima_atualizacao}")

    with st.expander("🧭 Não sabes qual tipologia é a tua? Responde a estas perguntas", expanded=False):
        col1, col2 = st.columns(2)
        idade = col1.number_input("A tua idade", min_value=0, max_value=120, value=25, step=1, key="wizard_idade")
        residente_gmr = col2.checkbox("Resides no concelho de Guimarães?", key="wizard_residente")

        estudante = st.checkbox("És estudante?", key="wizard_estudante")
        nivel_estudo = None
        if estudante:
            nivel_estudo = st.radio("Que nível de ensino?", options=["ate_18", "ate_23", "superior"], key="wizard_nivel")

        col3, col4 = st.columns(2)
        incapacidade_60 = col3.checkbox("Grau de incapacidade ≥ 60%?", key="wizard_incapacidade")
        antigo_combatente = col4.checkbox("Antigo combatente ou viúvo(a)?", key="wizard_combatente")

        col5, col6 = st.columns(2)
        reforma_antecipada = col5.checkbox("Reforma antecipada (60-65 anos)?", key="wizard_reforma")
        usa_passe_cp = col6.checkbox("Já tens passe CP?", key="wizard_cp")

        if st.button("🔍 Recomendar tipologia", key="wizard_recomendar"):
            respostas = {"idade": idade, "residente_gmr": residente_gmr, "estudante": estudante, "nivel_estudo": nivel_estudo, "incapacidade_60": incapacidade_60, "antigo_combatente": antigo_combatente, "reforma_antecipada": reforma_antecipada, "usa_passe_cp": usa_passe_cp}
            recomendadas = recomendar_tipologias_passe(respostas, TIPOLOGIAS_PASSE)
            if recomendadas: st.success(f"A(s) tipologia(s) mais indicada(s): **{' / '.join(recomendadas)}**")
            else: st.warning("O passe **Mensal** normal é provavelmente a opção aplicável.")

    tipologia_escolhida = st.selectbox("Escolhe a tipologia:", list(TIPOLOGIAS_PASSE.keys()))
    info = TIPOLOGIAS_PASSE[tipologia_escolhida]

    st.markdown(f"**Descrição:** {info['descricao']}\n**Preço:** {info['preco']} | **Custo do cartão:** {info['custo_cartao']}")
    st.markdown("**Documentos necessários para esta tipologia:**")
    ficheiros_carregados = {}
    for i, nome_doc in enumerate(info["documentos"]):
        ficheiros_carregados[nome_doc] = st.file_uploader(f"📄 {nome_doc}", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_passe_{tipologia_escolhida}_{i}")

    if st.button("🔍 Verificar documentos carregados", use_container_width=True):
        if not any(f is not None for f in ficheiros_carregados.values()): st.warning("Carrega pelo menos um documento.")
        else:
            with st.spinner("A analisar os documentos (em memória)..."):
                st.markdown(verificar_documentos_passe(tipologia_escolhida, ficheiros_carregados))

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

        <div style="margin-top: 15px; display: inline-block; width: 100%; text-align: center;">
            <div style="margin-bottom: 5px;">
                <button data-dir="cima" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▲</button>
            </div>
            <div style="display: flex; justify-content: center; gap: 10px;">
                <button data-dir="esquerda" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">◀</button>
                <button data-dir="baixo" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▼</button>
                <button data-dir="direita" style="padding: 12px 24px; background: #34495e; color: white; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; font-size: 18px;">▶</button>
            </div>
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

                ctx.fillStyle = '#3498db'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-4)/2, 0, 2 * Math.PI); ctx.fill();
                ctx.fillStyle = '#ffffff'; ctx.beginPath();
                ctx.arc(apple.x + tnt/2, apple.y + tnt/2, (tnt-12)/2, 0, 2 * Math.PI); ctx.fill();
                
                for(var i=0; i<snake.length; i++) {
                    if (i === 0) {
                        ctx.fillStyle = '#27ae60'; ctx.fillRect(snake[i].x, snake[i].y, tnt-1, tnt-1);
                        ctx.fillStyle = '#f1c40f';
                        if (dx > 0) { ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + tnt - 4, snake[i].y + tnt - 6, 3, 3); }
                        else if (dx < 0) { ctx.fillRect(snake[i].x + 1, snake[i].y + 2, 3, 3); ctx.fillRect(snake[i].x + 1, snake[i].y + tnt - 6, 3, 3); }
                        else if (dy < 0) { ctx.fillStyle = '#2ecc71'; ctx.fillRect(snake[i].x + 1, snake[i].y + 1, tnt-3, tnt-3); }
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
            function gravarRecorde() {
                var nome = nomeInput.value.trim().toUpperCase();
                if(!nome) { alert('Por favor introduz o teu nome!'); return; }
                btnGravar.disabled = true;
                btnGravar.innerText = "💾...";
                
                var finalScore = (score / 10);
                window.parent.location.search = "?save_nome=" + encodeURIComponent(nome) + "&save_pontos=" + finalScore;
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
            document.querySelectorAll('button[data-dir]').forEach(function(btn) {
                btn.addEventListener('click', function() { mudarDirecao(btn.getAttribute('data-dir')); });
            });
            drawScene();
        </script>
    </div>
    """.replace("JSON_SCORES_PLACEHOLDER", json_scores)
    return components.html(html_jogo, height=650)

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

# Mantém a cache de horários sempre fresca sem depender de um admin lembrar-se de clicar
sincronizar_automaticamente_se_necessario(limite_dias=7)

# --- SIDEBAR DE ELITE (GERENCIAMENTO DO AGENTE) ---
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

    st.subheader("🎫 Títulos de Transporte")
    if "passe_ativo" not in st.session_state:
        st.session_state.passe_ativo = False
    texto_botao_passe = "Fechar Pedido de Passe X" if st.session_state.passe_ativo else "Pedir Passe 🎫"
    if st.button(texto_botao_passe, use_container_width=True):
        st.session_state.passe_ativo = not st.session_state.passe_ativo
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
    
    st.sidebar.subheader("🔒 Área de Administrador")
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
        
        st.sidebar.subheader("🕷️ Automação Web")
        if st.sidebar.button("🔄 Sincronizar Todos os Horários (Scraping)", use_container_width=True):
            with st.spinner("O robô está a ler o site da Guimabus..."):
                resultado_scraping = sincronizar_todos_horarios_guimabus()
                resultado_indice = construir_indice_paragens()
                st.sidebar.success(resultado_scraping)
                st.sidebar.success(resultado_indice)

        if st.sidebar.button("🗺️ Reconstruir Índice de Paragens", use_container_width=True):
            with st.spinner("A reconstruir o índice a partir da cache já existente..."):
                st.sidebar.success(construir_indice_paragens())

        if st.sidebar.button("📍 Descobrir Freguesia de Cada Paragem", use_container_width=True):
            st.sidebar.caption("A perguntar ao OpenStreetMap onde fica cada paragem...")
            barra_progresso = st.sidebar.progress(0.0)
            texto_progresso = st.sidebar.empty()

            def _atualizar_progresso(atual, total, paragem_atual):
                barra_progresso.progress(atual / total)
                texto_progresso.caption(f"{atual}/{total}: {paragem_atual}")

            resultado_enriquecimento = enriquecer_paragens_com_freguesia(progresso_callback=_atualizar_progresso)
            st.sidebar.success(resultado_enriquecimento)

        if st.sidebar.button("🔄 Sincronizar Títulos e Tarifário", use_container_width=True):
            with st.spinner("O robô está a ler titulos/ e tarifarios/..."):
                resultado_titulos = sincronizar_titulos_e_tarifario()
                st.sidebar.success(resultado_titulos)
                
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

if st.session_state.jogo_ativo:
    renderizar_jogo()

if st.session_state.get("passe_ativo"):
    renderizar_pedido_passe()

avisos_hoje = obter_avisos_facebook()
if avisos_hoje:
    renderizar_rodape_anuncios(avisos_hoje)

for message in st.session_state.messages:
    avatar_tipo = "💼" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar_tipo):
        st.markdown(message["content"])

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

                Tens estas ferramentas relacionadas com a frota local da Guimabus:
                - obter_dados_guimabus: estado em tempo real da frota.
                - obter_horarios_paragem: previsão de tempos de espera para uma paragem específica.
                - consultar_cache_horario_linha: consulta a cache local para ler os horários e tabelas fixas.
                - consultar_tipologias_cache_tool: lê as tipologias de passe.
                - consultar_tarifario_cache: lê a tabela tarifária completa.
                - planear_viagem_com_transbordo: dado o nome de uma paragem de origem e destino, diz se há linha direta ou sugere transbordo.
                - consultar_freguesia_paragem_tool: diz em que freguesia fica uma paragem.
                - gerar_link_google_maps: recebe o nome de um local (paragem, café, hospital, rua) e devolve um link direto do Google Maps para esse sítio.
                - encontrar_paragem_mais_proxima: descobre a paragem oficial de autocarro mais próxima de qualquer café, fábrica ou ponto de interesse (ex: "Coelima", "Cachorrão").

                LÓGICA DE PLANEAMENTO OBRIGATÓRIA:
                Se o utilizador pedir direções ou como ir para/de um local que NÃO É UMA PARAGEM (como um café, restaurante, loja ou fábrica), tu DEVES usar primeiro a ferramenta "encontrar_paragem_mais_proxima" para descobrir qual é a paragem da Guimabus que fica perto desse local. SÓ DEPOIS de saberes o nome da paragem oficial é que usas o "planear_viagem_com_transbordo" usando o nome dessa paragem.

                REGRA DE EXECUÇÃO DE FERRAMENTAS (TOOL CALLING) - CRÍTICA:
                NUNCA descrevas os passos que vais tomar para pesquisar (ex: "Vou procurar...", "Aguarde um momento...", "Deixe-me verificar..."). NUNCA tentes calcular rotas mentalmente. Se precisares de procurar uma paragem ou uma rota, EXECUTA a ferramenta correspondente IMEDIATAMENTE e em silêncio. Só deves gerar texto para o utilizador DEPOIS de teres recebido a resposta da ferramenta.

                Usa sempre consultar_tipologias_cache_tool e consultar_tarifario_cache para perguntas sobre preços, tipologias de passe ou documentos exigidos.

                REGRA ANTI-ALUCINAÇÃO — A MAIS IMPORTANTE DE TODAS:
                NUNCA inventes, estimes ou "preenchas" dados que as ferramentas ou a Knowledge Base não te deram. Usa SEMPRE e apenas a informação em "[DATA E HORA ATUAL DO SISTEMA]". Se não souberes, admite que não tens a informação disponível."""

                PROMPT_RECRUITER = """You are an expert IT Technical Recruiter interviewing Celso Ferreira for an IT role.
                Conduct the interview strictly in English. Ask one tough, deep technical or behavioral question at a time.
                Evaluate Celso's response professionally based on IT best practices and keep the interviewer persona realistic."""
                
                PROMPT_HELPDESK_TUTOR = """Tu és um Tutor Técnico de Helpdesk e Suporte de IT.
                O teu objetivo é atuar como uma fonte interminável de resolução de problemas de IT.
                Independentemente do problema de suporte, deves começar a tua resposta OBRIGATORIAMENTE com a seguinte frase padrão: 
                'O Celso faria desta maneira para resolver este problema de IT:'
                Depois, detalha passos de troubleshooting técnicos, comandos em PowerShell ou Linux, e boas práticas aplicadas com precisão."""

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

                historico_api = []
                for msg in st.session_state.messages[:-1]:
                    if msg["content"] != MENSAGEM_INICIAL:
                        role_api = "model" if msg["role"] == "assistant" else "user"
                        historico_api.append({"role": role_api, "parts": [msg["content"]]})
                
                DIAS_SEMANA_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
                MESES_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

                def _formatar_data_pt(dt):
                    return f"{DIAS_SEMANA_PT[dt.weekday()]}, {dt.day} de {MESES_PT[dt.month - 1]} de {dt.year}"

                agora = datetime.now(ZoneInfo("Europe/Lisbon"))
                amanha = agora + timedelta(days=1)
                contexto_data = (
                    f"[DATA E HORA ATUAL DO SISTEMA: "
                    f"Hoje é {_formatar_data_pt(agora)}, são {agora.strftime('%H:%M')}. "
                    f"Amanhã será {_formatar_data_pt(amanha)}.]"
                )

                prompt_enriquecido = f"{contexto_data}\n\n{contexto_base}\n\nUser Prompt: {prompt}"
                
                ferramentas_agente = [
                    obter_dados_guimabus, obter_horarios_paragem, consultar_cache_horario_linha, 
                    consultar_tipologias_cache_tool, consultar_tarifario_cache, 
                    planear_viagem_com_transbordo, consultar_freguesia_paragem_tool, 
                    gerar_link_google_maps, gerar_mapa_linha_html, encontrar_paragem_mais_proxima
                ]
                
                TIMEOUT_SEGUNDOS = 25
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
                        break
                    except Exception as e:
                        ultimo_erro_modelo = e
                        continue

                if response is None:
                    if ultimo_erro_modelo is not None and "429" in str(ultimo_erro_modelo):
                        st.error("🚫 Limite diário gratuito da API do Gemini esgotado. Tenta novamente mais tarde.")
                    else:
                        st.error("🚫 Não foi possível obter resposta de nenhum modelo disponível neste momento.")
                    st.stop()

                full_response = response.text
                st.markdown(full_response)
                
                logging.info(f"Resposta gerada com sucesso ({len(full_response)} caracteres).")
                guardar_mensagem_bd(st.session_state.session_id, "assistant", full_response)
                
                st.download_button("📥 Descarregar Resposta (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Erro detetado no pipeline do agente: {e}")
                logging.error(f"Falha crítica no pipeline do agente: {e}")
