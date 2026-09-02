import os
import time
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def cfg(name, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.getenv(name, default)


API_KEY = cfg("OPENAI_API_KEY")
VECTOR_STORE_ID = cfg("VECTOR_STORE_ID")
CHAT_MODEL = cfg("OPENAI_CHAT_MODEL", "gpt-5.5")
ADMIN_PASSWORD = cfg("ADMIN_PASSWORD", "")
TOP_K = int(cfg("TOP_K", "5")) 
PUBLIC_SOURCE_DOMAINS = ["embrapa.br", "scielo.br", "edu.br", "iac.sp.gov.br", "idrparana.pr.gov.br", "incaper.es.gov.br", "empaer.mt.gov.br", "epagri.sc.gov.br", "epamig.br", "ipa.br", "emparn.rn.gov.br"]
st.set_page_config(
    page_title="Oráculo da Fruticultura", page_icon="🌱", layout="wide"
)
st.title("🌱 Oráculo da Fruticultura")
st.caption("Assistente técnico com base documental privada e permanente.")

missing = [
    name
    for name, value in {
        "OPENAI_API_KEY": API_KEY,
        "VECTOR_STORE_ID": VECTOR_STORE_ID,
        "ADMIN_PASSWORD": ADMIN_PASSWORD,
    }.items()
    if not value
]
if missing:
    st.error(
        "Configuração incompleta. Adicione nos Secrets do Streamlit: "
        + ", ".join(missing)
        + "."
    )
    st.stop()

client = OpenAI(api_key=API_KEY)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "admin_ok" not in st.session_state:
    st.session_state.admin_ok = False




SYSTEM = """Você é o Oráculo da Fruticultura, assistente técnico especializado em
fruticultura tropical e subtropical.

ORDEM DE PRIORIDADE DAS FONTES:
1. Consulte prioritariamente os documentos da base privada.
2. Consulte publicações técnicas oficiais da Embrapa, incluindo o Boletim 100 quando pertinente.
3. Consulte publicações oficiais de instituições estaduais de pesquisa e extensão agropecuária, incluindo IAC, IDR-Paraná/IAPAR, Incaper, Empaer, Epagri, EPAMIG, IPA e EMPARN.
4. Se necessário, complemente com artigos científicos da SciELO.
5. Depois, consulte publicações de universidades públicas brasileiras e outras instituições públicas de pesquisa agropecuária.
6. Priorize sempre fontes técnicas, científicas e oficiais, utilizando informações atualizadas quando disponíveis.

Não invente doses, registros, legislação, resultados científicos ou referências.
Se as fontes disponíveis não forem suficientes, informe isso claramente.
Para defensivos agrícolas, recomende verificar registro vigente, bula e
orientação de profissional habilitado.

IMPORTANTE: não escreva, gere ou crie uma seção chamada "Fontes consultadas".
Não coloque nomes de documentos, referências, URLs, links ou citações no corpo da resposta.
Apresente somente a resposta técnica. O sistema acrescentará automaticamente
as fontes realmente consultadas ao final da resposta.
Escreva em português do Brasil, de forma técnica, clara e objetiva."""

def upload_pdf(uploaded_file):
   # Envia um PDF à OpenAI e aguarda sua indexação no Vector Store.
    created = client.files.create(
        file=(uploaded_file.name, BytesIO(uploaded_file.getvalue()), "application/pdf"),
        purpose="assistants",
    )
    try:
        vector_file = client.vector_stores.files.create(
            vector_store_id=VECTOR_STORE_ID, file_id=created.id
        )
        for _ in range(120):
            vector_file = client.vector_stores.files.retrieve(
                vector_store_id=VECTOR_STORE_ID, file_id=created.id
            )
            if vector_file.status == "completed":
                return created.id
            if vector_file.status in {"failed", "cancelled"}:
                detail = getattr(vector_file, "last_error", None)
                raise RuntimeError(f"Falha na indexação: {detail or vector_file.status}")
            time.sleep(1)
        raise TimeoutError("A indexação demorou mais que o esperado.")
    except Exception:
        # Evita deixar um arquivo órfão caso a vinculação/indexação falhe.
        try:
            client.files.delete(created.id)
        except Exception:
            pass
        raise


def list_documents():
    documents = []
    page = client.vector_stores.files.list(
        vector_store_id=VECTOR_STORE_ID, limit=100, order="desc"
    )
    for vector_file in page.data:
        source = client.files.retrieve(vector_file.id)
        documents.append(
            {
                "id": vector_file.id,
                "name": source.filename,
                "status": vector_file.status,
            }
        )
    return documents


def delete_document(file_id):
# Remove o documento do Vector Store e também da Files API.
    client.vector_stores.files.delete(
        vector_store_id=VECTOR_STORE_ID, file_id=file_id
    )
    client.files.delete(file_id)


def answer(question):
    public_search_terms = (
        "embrapa",
        "fonte pública",
        "fontes públicas",
        "fonte oficial",
        "fontes oficiais",
        "informação atual",
        "informações atuais",
        "recomendação atual",
        "recomendações atuais",
                "IAC",
        "IAPAR",
        "IDR-Parana",
        "EPAGRI",
        "EMPAER",
        "INCAPER",
    )
    require_public_search = any(
        term in question.casefold() for term in public_search_terms
    )

    request = {
        "model": CHAT_MODEL,
        "instructions": SYSTEM,
        "input": question,
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID],
                "max_num_results": TOP_K,
            },
            {
                "type": "web_search",
                "filters": {"allowed_domains": PUBLIC_SOURCE_DOMAINS},
                "search_context_size": "medium",
            },
        ],
    }
   
    response = client.responses.create(**request)
    answer = response.output_text
    answer = "\n".join(
        line for line in answer.splitlines()
        if not line.strip().lower().startswith("consultas utilizadas:")
    )
    file_sources = []
    web_sources = []

    for item in response.output:
        for content in getattr(item, "content", []):
            for annotation in getattr(content, "annotations", []):
                annotation_type = getattr(annotation, "type", "")
                url = None
                if annotation_type == "file_citation":
                    filename = getattr(annotation, "filename", None)
                    if filename and filename not in file_sources:
                        file_sources.append(filename)
                elif annotation_type == "url_citation":            
                    url = getattr(annotation, "url", None)
            
            source_names = {
                "embrapa.br": "Embrapa",
                "iac.sp.gov.br": "IAC — Instituto Agronômico",
                "idrparana.pr.gov.br": "IDR-Paraná / IAPAR",
                "incaper.es.gov.br": "Incaper",
                "empaer.mt.gov.br": "Empaer",
                "epagri.sc.gov.br": "Epagri",
                "epamig.br": "EPAMIG",
                "ipa.br": "IPA",
                "emparn.rn.gov.br": "EMPARN",
                "scielo.br": "SciELO",
            }
            
            title = getattr(annotation, "title", None) or "Fonte pública"
            
            if url:
                for domain, source_name in source_names.items():
                    if domain in url:
                        title = source_name
                        break
            
            if url and url not in [source[1] for source in web_sources]:
                web_sources.append((title, url))
    if file_sources or web_sources:
        answer += "\n\n**Fontes consultadas:**\n"
        answer += "\n".join(
            f"- Documento privado: `{filename}`" for filename in file_sources
        )
        if file_sources and web_sources:
            answer += "\n"
        answer += "\n".join(
            f"- Fonte pública: [{title}]({url})" for title, url in web_sources
        )

    return answer
with st.sidebar:
    st.header("⚙️ Administração")

    if not st.session_state.admin_ok:
        with st.form("admin_login", clear_on_submit=True):
            password = st.text_input("Senha do administrador", type="password")
            login = st.form_submit_button(
                "Entrar como administrador", use_container_width=True
            )
        if login:
            st.session_state.admin_ok = password == ADMIN_PASSWORD
            if st.session_state.admin_ok:
                st.rerun()
            st.error("Senha incorreta.")
    else:
        st.success("Modo administrador ativo.")
        if st.button("Sair do modo administrador", use_container_width=True):
            st.session_state.admin_ok = False
            st.rerun()

        files = st.file_uploader(
            "Adicionar PDFs à base privada",
            type=["pdf"],
            accept_multiple_files=True,
        )
        if st.button("Enviar e indexar", use_container_width=True):
            if not files:
                st.warning("Selecione pelo menos um PDF.")
            else:
                successes = 0
                progress = st.progress(0)
                for index, uploaded_file in enumerate(files, start=1):
                    try:
                        with st.spinner(f"Indexando {uploaded_file.name}..."):
                            upload_pdf(uploaded_file)
                        successes += 1
                    except Exception as exc:
                        st.error(f"{uploaded_file.name}: {exc}")
                    progress.progress(index / len(files))
                if successes:
                    st.success(f"{successes} documento(s) indexado(s) permanentemente.")

        st.subheader("Documentos da base")
        try:
            documents = list_documents()
            if not documents:
                st.caption("Nenhum documento indexado.")
            for document in documents:
                left, right = st.columns([4, 1])
                left.caption(f"{document['name']} · {document['status']}")
                if right.button(
                    "Remover", key=f"remove_{document['id']}", type="secondary"
                ):
                    try:
                        delete_document(document["id"])
                        st.success(f"{document['name']} removido.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível remover: {exc}")
        except Exception as exc:
            st.error(f"Não foi possível listar os documentos: {exc}")

    st.divider()
    if st.button("🧹 Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

question = st.chat_input(
    "Pergunte sobre culturas, pragas, doenças, irrigação, adubação..."
)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Consultando a base técnica privada..."):
                response_text = answer(question)
        except Exception as exc:
            response_text = (
                "Não foi possível consultar a base agora. "
                f"Detalhe técnico: {exc}"
            ) 
        st.markdown(response_text)
    st.session_state.messages.append(
        {"role": "assistant", "content": response_text}
    )
