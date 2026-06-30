import streamlit as st
import google.generativeai as genai
import requests

st.set_page_config(page_title="Super Secretário IA", page_icon="💼")
st.title("💼 O Teu Super Secretário de Produtividade")

# Configuração da API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta nos Secrets.")
    st.stop()

# --- FUNÇÕES DE CONTEXTO ---
def obter_dados_guimabus():
    # URL real da API de tracking
    url = "https://tracking.elevensystems.pt/api/gmr/vehicles"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            resumo = "Dados de frota em tempo real:\n"
            for bus in dados:
                resumo += f"- Autocarro {bus.get('id', 'N/A')}: Status {bus.get('busStatus', 'N/A')} (Atraso: {bus.get('delay', 0)}min)\n"
            return resumo
        return "Tracking indisponível (Erro de servidor)."
    except Exception as e:
        return f"Tracking temporariamente indisponível. Erro: {e}"

def ler_ficheiros_pessoais():
    try:
        with open("biografia.md", "r", encoding="utf-8") as f:
            return f"\n--- BIOGRAFIA DO CELSO ---\n{f.read()}"
    except:
        return ""

# --- CONFIGURAÇÃO ---
PROMPT_SISTEMA = "Tu és um Assistente Executivo de Elite que consulta sempre o contexto fornecido antes de responder."

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar histórico
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

model = genai.GenerativeModel("gemini-3.5-flash", system_instruction=PROMPT_SISTEMA)

# --- FLUXO DE CHAT ---
if prompt := st.chat_input("Como posso ajudar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("A consultar dados..."):
            try:
                # 1. Montar o contexto (Bio + Tracking se solicitado)
                contexto = ler_ficheiros_pessoais()
                if any(word in prompt.lower() for word in ["autocarro", "horário", "tracking"]):
                    contexto += "\n" + obter_dados_guimabus()
                
                # 2. Enviar prompt enriquecido
                prompt_enriquecido = f"{contexto}\n\nPergunta: {prompt}"
                response = model.generate_content(prompt_enriquecido)
                
                full_response = response.text
                st.markdown(full_response)
                
                st.download_button("📥 Descarregar (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
