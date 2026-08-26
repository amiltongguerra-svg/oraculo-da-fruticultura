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
fruticultura tropical e subtropical. Responda prioritariamente com base nos
documentos da base privada. Não invente doses, registros, legislação ou
referências. Se os documentos não bastarem, diga isso claramente. Para
defensivos, recomende verificar registro vigente, bula e orientação de
profissional habilitado. Cite pelo nome os arquivos usados. Escreva em português
do Brasil, de forma técnica, clara e objetiva."""


def upload_pdf(uploaded_file):
    """Envia um PDF à OpenAI e aguarda sua indexação no Vector Store."""
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
    for vector_file in page.auto_paging_iter():
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
    """Remove o documento do Vector Store e também da Files API."""
    client.vector_stores.files.delete(
        vector_store_id=VECTOR_STORE_ID, file_id=file_id
    )
    client.files.delete(file_id)


def answer(question):
    response = client.responses.create(
        model=CHAT_MODEL,
        instructions=SYSTEM,
        input=question,
        tools=[
            {
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID],
                "max_num_results": TOP_K,
            }
        ],
    )
    return response.output_text


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
