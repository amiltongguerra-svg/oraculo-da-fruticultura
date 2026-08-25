import os, io, hashlib
from typing import List, Dict, Any
import streamlit as st
import numpy as np
from pypdf import PdfReader
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

API_KEY = cfg('OPENAI_API_KEY')
CHAT_MODEL = cfg('OPENAI_CHAT_MODEL', 'gpt-5.5')
EMBED_MODEL = cfg('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
ADMIN_PASSWORD = cfg('ADMIN_PASSWORD', '')
TOP_K = int(cfg('TOP_K', '5'))
CHUNK_SIZE = int(cfg('CHUNK_SIZE', '1400'))
OVERLAP = int(cfg('CHUNK_OVERLAP', '250'))

st.set_page_config(page_title='Oráculo da Fruticultura', page_icon='🌱', layout='wide')
st.title('🌱 Oráculo da Fruticultura')
st.caption('Assistente técnico com RAG e respostas fundamentadas em documentos.')

if not API_KEY:
    st.error('Configure OPENAI_API_KEY em App settings → Secrets no Streamlit Cloud.')
    st.stop()
client = OpenAI(api_key=API_KEY)

for key, value in {'messages': [], 'chunks': [], 'embeddings': None, 'admin_ok': False}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def norm(t): return ' '.join((t or '').replace('\x00',' ').split())

def split_text(text):
    text = norm(text); out=[]; start=0
    while start < len(text):
        end=min(start+CHUNK_SIZE,len(text)); chunk=text[start:end]
        if end < len(text):
            p=chunk.rfind('. ')
            if p > int(CHUNK_SIZE*0.55): end=start+p+1; chunk=text[start:end]
        if chunk.strip(): out.append(chunk.strip())
        if end >= len(text): break
        start=max(0,end-OVERLAP)
    return out

def extract_pdf(f):
    data=f.getvalue(); reader=PdfReader(io.BytesIO(data)); rec=[]
    for n,page in enumerate(reader.pages,1):
        text=norm(page.extract_text() or '')
        if text: rec.append({'source':f.name,'page':n,'text':text,'hash':hashlib.sha256(data).hexdigest()})
    return rec

def build_chunks(files):
    out=[]
    for f in files:
        for page in extract_pdf(f):
            for i,ch in enumerate(split_text(page['text']),1):
                out.append({'source':page['source'],'page':page['page'],'chunk':i,'text':ch})
    return out

def embed_texts(texts, batch=64):
    vec=[]
    for i in range(0,len(texts),batch):
        r=client.embeddings.create(model=EMBED_MODEL,input=texts[i:i+batch],encoding_format='float')
        vec.extend(x.embedding for x in r.data)
    a=np.array(vec,dtype=np.float32); n=np.linalg.norm(a,axis=1,keepdims=True); n[n==0]=1
    return a/n

def retrieve(q):
    r=client.embeddings.create(model=EMBED_MODEL,input=q,encoding_format='float')
    v=np.array(r.data[0].embedding,dtype=np.float32); n=np.linalg.norm(v); v=v if n==0 else v/n
    scores=st.session_state.embeddings @ v; idx=np.argsort(scores)[::-1][:TOP_K]
    out=[]
    for i in idx:
        x=dict(st.session_state.chunks[int(i)]); x['score']=float(scores[int(i)]); out.append(x)
    return out

SYSTEM='''Você é o Oráculo da Fruticultura, assistente técnico especializado em fruticultura tropical e subtropical. Responda prioritariamente com base no contexto documental. Não invente doses, registros, legislação ou referências. Se o contexto não bastar, diga isso claramente. Para defensivos, recomende verificar registro vigente, bula e orientação de profissional habilitado. Ao final, informe arquivo e página das fontes usadas. Escreva em português do Brasil, de forma técnica, clara e objetiva.'''

def answer(q, results):
    context='\n\n'.join([f"[FONTE {i}] {x['source']} | página {x['page']}\n{x['text']}" for i,x in enumerate(results,1)])
    prompt=f"PERGUNTA:\n{q}\n\nCONTEXTO:\n{context}\n\nResponda fundamentando as afirmações nas fontes acima."
    r=client.responses.create(model=CHAT_MODEL,instructions=SYSTEM,input=prompt)
    return r.output_text

with st.sidebar:
    st.header('⚙️ Administração')
    if ADMIN_PASSWORD:
        pwd=st.text_input('Senha do administrador',type='password')
        if st.button('Entrar como administrador',use_container_width=True):
            st.session_state.admin_ok=(pwd==ADMIN_PASSWORD)
            if not st.session_state.admin_ok: st.error('Senha incorreta.')
    else:
        st.warning('ADMIN_PASSWORD não configurada; upload aberto nesta sessão.')
        st.session_state.admin_ok=True

    if st.session_state.admin_ok:
        st.success('Modo administrador ativo.')
        files=st.file_uploader('Base técnica — envie PDFs',type=['pdf'],accept_multiple_files=True)
        if st.button('🔎 Indexar documentos',use_container_width=True):
            if not files: st.warning('Envie pelo menos um PDF.')
            else:
                with st.spinner('Criando a base vetorial...'):
                    chunks=build_chunks(files)
                    if not chunks: st.error('Não foi possível extrair texto. PDFs digitalizados podem exigir OCR.')
                    else:
                        st.session_state.chunks=chunks
                        st.session_state.embeddings=embed_texts([x['text'] for x in chunks])
                        st.success(f'Base criada: {len(chunks)} trechos indexados.')
    st.divider()
    st.metric('Trechos indexados nesta sessão',len(st.session_state.chunks))
    if st.button('🧹 Limpar conversa',use_container_width=True):
        st.session_state.messages=[]; st.rerun()

if st.session_state.embeddings is None:
    st.info('A base técnica ainda não foi indexada nesta sessão pelo administrador.')

for m in st.session_state.messages:
    with st.chat_message(m['role']): st.markdown(m['content'])

q=st.chat_input('Pergunte sobre culturas, pragas, doenças, irrigação, adubação...')
if q:
    st.session_state.messages.append({'role':'user','content':q})
    with st.chat_message('user'): st.markdown(q)
    with st.chat_message('assistant'):
        if st.session_state.embeddings is None:
            ans='A base técnica ainda não foi carregada pelo administrador.'; st.markdown(ans)
        else:
            with st.spinner('Consultando a base técnica...'):
                results=retrieve(q); ans=answer(q,results)
            st.markdown(ans)
            with st.expander('Trechos recuperados pelo RAG'):
                for i,x in enumerate(results,1):
                    st.markdown(f"**{i}. {x['source']} — página {x['page']} (similaridade {x['score']:.3f})**")
                    st.write(x['text'])
    st.session_state.messages.append({'role':'assistant','content':ans})
