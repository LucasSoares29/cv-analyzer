import streamlit as st
import os
from PyPDF2 import PdfReader
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from dotenv import load_dotenv




def extract_text_from_pdf(pdf_file):
    """Extrai texto de um arquivo PDF"""
    text = ""
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        text += page.extract_text()
    return text

# Sidebar
st.sidebar.title("Analisador de currículos")
st.sidebar.write("Faça o upload do seu currículo abaixo")
curriculo = st.sidebar.file_uploader("Upload do currículo", type=["pdf"], accept_multiple_files=False)

# Parte principal
descricao_da_vaga = st.text_area("Insira a descrição da vaga a seguir", height=400)

if st.button("Analisar currículo"):
    with st.spinner("Analisando currículo..."):
        load_dotenv()
        llm = ChatOpenAI(temperature=0, 
                         model="gpt-4o-mini",
                         api_key=os.getenv('OPENAI_API_KEY'))

        prompt = PromptTemplate(
            input_variables=["curriculo", "descricao_vaga"],
            template="""Você vai receber a descrição da experiência profissional e competencias de um candidato, além da descrição da vaga. 
            Sua missão é fazer uma análise, apontando em formato de bulletpoints os eventuais pontos de match e pontos que é requisitado na vaga, 
            mas está ausente no currículo do candidato. Monte um plano de ação para que o candidato esteja mais aderente à vaga. 
            No fim responda se o candidato deve ou não se candidatar a vaga baseado na probabilidade de 
            match com a vaga e na análise feita.
            \n
            Descrição do currículo:
            {curriculo}
            \n
            Descrição da vaga:
            {descricao_vaga}
            """
        )

        if curriculo is not None:
            texto_curriculo = extract_text_from_pdf(curriculo)
        else:
            st.error("Por favor, faça o upload do currículo.")


        if descricao_da_vaga.strip() != "":
            st.session_state.descricao_vaga = descricao_da_vaga

            chain = prompt | llm | StrOutputParser()

            analise = chain.invoke({
                "curriculo": texto_curriculo,
                "descricao_vaga": st.session_state.descricao_vaga
            })

            st.write("🤖 Análise do Currículo:")
            st.write(analise)
        else:
            st.error("Por favor, insira a descrição da vaga.")

