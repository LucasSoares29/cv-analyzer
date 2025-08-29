import streamlit as st
import getpass
import os
from PyPDF2 import PdfReader
from tavily import TavilyClient 
from dotenv import load_dotenv
from prompts import PROMPT_ANALISE_CURRICULO, PROMPT_CURSOS_PROJETOS_CANDIDATO, PROMPT_REDATOR_ANALISE_CANDIDATO, PROMPT_COORDENADOR
from streamlit_modal import Modal
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import convert_to_messages
from langchain.chat_models import init_chat_model
from langgraph_supervisor import create_supervisor
from langchain_core.runnables.graph import MermaidDrawMethod

load_dotenv()

if not os.environ.get("TAVILY_API_KEY"):
    os.environ["TAVILY_API_KEY"] = getpass.getpass("Tavily API key:\n")

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass.getpass("OPENAI API key:\n")


### Funções que ajudarão a imprimir as mensagens trocada entre os agentes
def pretty_print_message(message, indent=False):
    pretty_message = message.pretty_repr(html=True)
    if not indent:
        print(pretty_message)
        return

    indented = "\n".join("\t" + c for c in pretty_message.split("\n"))
    print(indented)


def pretty_print_messages(update, last_message=False):
    is_subgraph = False
    if isinstance(update, tuple):
        ns, update = update
        # skip parent graph updates in the printouts
        if len(ns) == 0:
            return

        graph_id = ns[-1].split(":")[0]
        print(f"Update from subgraph {graph_id}:")
        print("\n")
        is_subgraph = True

    for node_name, node_update in update.items():
        update_label = f"Update from node {node_name}:"
        if is_subgraph:
            update_label = "\t" + update_label

        print(update_label)
        print("\n")

        messages = convert_to_messages(node_update["messages"])
        if last_message:
            messages = messages[-1:]

        for m in messages:
            pretty_print_message(m, indent=is_subgraph)
        print("\n")

def print_graph(agent):
    """Gera a arquitetura em grafo de um agente"""
    png_bytes = agent.get_graph().draw_mermaid_png()

    # Salva em arquivo
    with open("C:\\Users\\NZ366ES\\OneDrive - EY\\Documents\\cvs\\grafo_multiagente.png", "wb") as f:
        f.write(png_bytes)

    print("Arquivo salvo como grafo_multiagente.png")

# >> Agente de busca de cursos - Gestor Assistente
def search_courses_udemy(keyword):
    """
    A tool to search for paid courses on Udemy based upon keywords.
    """
    course_list = []
    client = TavilyClient(os.getenv('TAVILY_API_KEY'))
    response = client.search(
        query=f"Liste os 10 cursos melhor avaliados na Udemy sobre o tema {keyword} em inglês ou português",
        search_depth="advanced",
        max_results=10,
        include_domains=["udemy.com"],
        exclude_domains=["udemy.com/topic","udemy.com/pt/topic"]
    )

    for each_result in response['results']:
        course_list.append(f"Curso: {each_result['title']} - {each_result['url']}")
    return course_list

def search_courses_youtube(keyword):
    """
    A tool to search for free courses on YouTube based upon keywords.
    """
    course_list = []
    client = TavilyClient(os.getenv('TAVILY_API_KEY'))
    response = client.search(
        query=f"""Liste os 5 cursos ou playlists mais relevantes sobre {keyword} no YouTube em inglês ou português. 
        A duração do video ou da playlist deve ser de no mínimo 1 hora""",
        include_domains=["youtube.com"]
    )

    for each_result in response['results']:
        course_list.append(f"Curso: {each_result['title']} - {each_result['url']}")
    return course_list

gestor_assistent_agent = create_react_agent(
    model="openai:gpt-4o-mini",
    tools=[search_courses_udemy, search_courses_youtube],
    prompt=(
        PROMPT_CURSOS_PROJETOS_CANDIDATO
    ),
    name="gestor_assistent_agent",
)

# >> Agente que analisa os candidatos
gestor_pleno_agent = create_react_agent(
    model="openai:gpt-4o-mini",
    tools=[],
    prompt=(
        PROMPT_ANALISE_CURRICULO
    ),
    name="gestor_pleno_agent",
)

# >> Agente que dá o diagnóstico final do candidato
gestor_senior_agent = create_react_agent(
    model="openai:gpt-4o-mini",
    tools=[],
    prompt=(
        PROMPT_REDATOR_ANALISE_CANDIDATO
    ),
    name="gestor_senior_agent",
)


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
descricao_da_vaga = st.text_area("Insira a descrição da vaga a seguir", height=800)

if st.button("Analisar currículo"):
    with st.spinner("Analisando currículo..."):
    
        supervisor = create_supervisor(
            model=init_chat_model("openai:gpt-4o-mini"),
            agents=[gestor_senior_agent, gestor_pleno_agent, gestor_assistent_agent],
            prompt=(
                PROMPT_COORDENADOR
            ),
            add_handoff_back_messages=True,
            output_mode="full_history",
        ).compile()

        if curriculo is not None:
            texto_curriculo = extract_text_from_pdf(curriculo)
        else:
            st.error("Por favor, faça o upload do currículo.")
            st.stop()


        if descricao_da_vaga.strip() != "":
            st.session_state.descricao_vaga = descricao_da_vaga

            for chunk in supervisor.stream(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Descrição da vaga: {descricao_da_vaga}\n Currículo do candidato: {texto_curriculo}",
                        }
                    ]
                },
            ):
                pretty_print_messages(chunk, last_message=True)

            final_message_history = chunk["supervisor"]["messages"]

            with open("chat_history_agents.txt", "w", encoding="utf-8") as f:
                for message in final_message_history:
                    f.write(f"{message}\n")

            analise = final_message_history[-1].content

            modal = Modal("Resultado da análise", key="resultado-analise", padding=10, max_width=800)

            if st.button("Abrir resultado da análise"):
                modal.open()

            if modal.is_open():
                with modal.container():
                    st.markdown("## 🤖 Análise do Currículo:")
                    st.write(analise)
                    if st.button("Fechar"):
                        modal.close()

            try:
                png_bytes = supervisor.get_graph().draw_mermaid_png(max_retries=5, 
                                                                    retry_delay=2.0)

                # Salva em arquivo
                with open("C:\\Users\\NZ366ES\\OneDrive - EY\\Documents\\cvs\\grafo_multiagente.png", "wb") as f:
                    f.write(png_bytes)

                print("Arquivo salvo como grafo_multiagente.png")
            except Exception as e:
                print(f"Erro ao salvar o arquivo grafo_multiagente.png: {e}")
        else:
            st.error("Por favor, insira a descrição da vaga.")



