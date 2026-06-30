import streamlit as st
import google.generativeai as genai
import requests

st.set_page_config(page_title="Super Secretário IA", page_icon="💼")
st.title("💼 O Teu Super Secretário de Produtividade")

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- FUNÇÕES DE CONTEXTO ---
def obter_dados_guimabus():
    # Substitui pelo URL real que encontraste no Network
    url = "https://tracking.elevensystems.pt/gmr" 
    try:
        dados = requests.get(url).json()
        resumo = "Horários/Tracking em tempo real:\n"
        for bus in dados:
            resumo += f"- Autocarro {bus['id']}: {bus['busStatus']} (Atraso: {bus['delay']}min)\n"
        return resumo
    except:
        return "Tracking temporariamente indisponível."

def ler_ficheiros_pessoais():
    # Lê a tua biografia/currículo
    try:
        with open("biografia.md", "r", encoding="utf-8") as f:
            return f"\n--- BIOGRAFIA DO CELSO ---\n{f.read()}"
    except:
        return ""

# --- CONFIGURAÇÃO ---
PROMPT_SISTEMA = "Tu és um Assistente Executivo de Elite que consulta sempre o contexto fornecido antes de responder."

if "messages" not in st.session_state:
    st.session_state.messages = []

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
                # 1. Montar o contexto dinâmico
                contexto = ler_ficheiros_pessoais()
                if "autocarro" in prompt.lower() or "horário" in prompt.lower():
                    contexto += "\n" + obter_dados_guimabus()
                
                # 2. Enviar prompt enriquecido com os dados
                prompt_enriquecido = f"{contexto}\n\nPergunta: {prompt}"
                response = model.generate_content(prompt_enriquecido)
                
                full_response = response.text
                st.markdown(full_response)
                
                st.download_button("📥 Descarregar (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Erro: {e}")
