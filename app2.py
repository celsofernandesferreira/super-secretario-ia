import streamlit as st
import google.generativeai as genai
import requests
import os
import glob

# Configuração da página
st.set_page_config(page_title="Super Secretário IA", page_icon="💼")
st.title("💼 O Teu Super Secretário de Produtividade")

# Configuração da API
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception:
    st.error("Erro: Chave API em falta.")
    st.stop()

# --- FUNÇÕES DE CONTEXTO ---
def obter_dados_guimabus():
    url = "https://tracking.elevensystems.pt/api/gmr/vehicles"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
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
    # Lê todos os ficheiros .md na pasta 'knowledge/'
    contexto = ""
    files = glob.glob("knowledge/*.md")
    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            contexto += f"\n--- CONTEÚDO DE {os.path.basename(file)} ---\n{f.read()}"
    return contexto if contexto else "\n--- Nota: Sem documentos na pasta 'knowledge/'. ---"

# --- CONFIGURAÇÃO ---
PROMPT_SISTEMA = "Tu és um Assistente Executivo de Elite que consulta sempre o contexto fornecido (Bio e Dados de Tracking) antes de responder."

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- INTERFACE ---
if st.button("🗑️ Limpar Histórico de Conversa"):
    st.session_state.messages = []
    st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- FLUXO DE CHAT ---
if prompt := st.chat_input("Como posso ajudar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("A consultar dados..."):
            try:
                # Montar contexto enriquecido
                contexto = ler_knowledge_base()
                if any(word in prompt.lower() for word in ["autocarro", "horário", "tracking", "onde está"]):
                    contexto += "\n" + obter_dados_guimabus()
                
                prompt_enriquecido = f"{contexto}\n\nPergunta do Utilizador: {prompt}"
                
                # Estratégia de Fallback
                try:
                    model = genai.GenerativeModel("gemini-3.5-flash", system_instruction=PROMPT_SISTEMA)
                    response = model.generate_content(prompt_enriquecido)
                except Exception as e:
                    if "429" in str(e):
                        model = genai.GenerativeModel("gemini-2.0-flash-lite", system_instruction=PROMPT_SISTEMA)
                        response = model.generate_content(prompt_enriquecido)
                    else:
                        raise e

                full_response = response.text
                st.markdown(full_response)
                st.download_button("📥 Descarregar (.txt)", full_response, "resposta.txt")
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"Erro ao processar: {e}")
