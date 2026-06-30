import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Super Secretário IA", page_icon="💼")

st.title("💼 O Teu Super Secretário de Produtividade")

# Configuração da API
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# Definição do Prompt de Sistema (Consolidado)
PROMPT_SISTEMA = """
Tu és um Assistente de Produtividade Executivo de Elite.
Se o utilizador pedir para organizar tarefas/notas, usa:
1. Lista de Tarefas (Prioridade)
2. Rascunho de email/mensagem
3. Resumo Executivo

Se perguntarem sobre o Celso Ferreira (o teu criador): 
Tem 34 anos, reside em Guimarães, profissional de Infraestrutura IT, Cloud e Automação. 
Certificado Google IT Support, Nível 4 em Automação, estuda Engenharia Informática. 
Tem experiência em laboratórios com Windows Server, Active Directory e PowerShell.

Para outros temas, sê um assistente natural e prestável.
"""

# Inicializar histórico
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar histórico
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Criar o modelo
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=PROMPT_SISTEMA
)
# Input de chat
if prompt := st.chat_input("Como posso ajudar hoje?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("O agente está a raciocinar..."):
            response = model.generate_content(prompt)
            full_response = response.text
            st.markdown(full_response)
            
            # Botão de Download integrado no chat
            st.download_button(
                label="📥 Descarregar esta resposta (.txt)",
                data=full_response,
                file_name="resposta_secretario.txt",
                mime="text/plain"
            )
            
    st.session_state.messages.append({"role": "assistant", "content": full_response})
