# Oráculo da Fruticultura — Versão 2

Preparado para Streamlit Community Cloud.

## Melhorias
- Usa `st.secrets` no Streamlit Cloud e `.env` localmente.
- Upload/indexação restritos por senha de administrador.
- `.gitignore` impede publicação acidental de segredos.
- RAG com PDFs, embeddings, fontes por arquivo/página e histórico da sessão.

## Publicação
1. Envie estes arquivos a um repositório GitHub.
2. Não envie `.env` nem `.streamlit/secrets.toml`.
3. No Streamlit Community Cloud, selecione `app.py` como arquivo principal.
4. Em **App settings → Secrets**, copie o conteúdo de `.streamlit/secrets.toml.example` e troque a chave e a senha.
5. Faça o deploy.

## Execução local
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Limitação desta versão
A base vetorial fica em memória. Se o app reiniciar, o administrador deverá indexar os PDFs novamente. Para uso comercial, o próximo passo é persistir documentos e embeddings em PostgreSQL/pgvector, Qdrant ou solução equivalente.
