import streamlit as st
import google.generativeai as genai

st.title("Teste de Ligação")

# Configuração simples
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)

# Testar apenas a lista de modelos disponíveis
try:
    models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
    st.write("Modelos disponíveis:")
    st.write(models)
    
    # Tentar gerar uma resposta curta
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content("Olá, estás a ouvir-me?")
    st.success("Sucesso! Resposta da IA: " + response.text)
    
except Exception as e:
    st.error(f"Erro crítico: {e}")
