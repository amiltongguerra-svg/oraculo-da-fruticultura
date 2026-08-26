# Oráculo da Fruticultura — base privada permanente

Aplicação Streamlit com OpenAI Responses API, `file_search` e Vector Stores.

## O que mudou

- A indexação temporária em memória foi removida.
- Os PDFs são enviados diretamente à OpenAI e vinculados a um Vector Store permanente.
- Somente o administrador autenticado pode enviar, listar e remover PDFs.
- Usuários públicos podem consultar a base, mas não administrar documentos.
- PDFs, chave da API, senha e ID do Vector Store não ficam no GitHub.
- A remoção exclui o documento do Vector Store e da Files API, evitando arquivos órfãos.

## Arquivos que podem ir ao GitHub

- `app.py`
- `requirements.txt`
- `README.md`
- `secrets.toml.example` (contém apenas exemplos, nunca valores reais)

Nunca envie ao GitHub:

- PDFs da base técnica;
- `.streamlit/secrets.toml`;
- `.env` ou qualquer arquivo com chaves e senhas.

## Secrets necessários no Streamlit

Em **App settings → Secrets**, configure:

```toml
OPENAI_API_KEY = "sua-chave-existente"
VECTOR_STORE_ID = "vs_..."
ADMIN_PASSWORD = "uma-senha-forte-e-exclusiva"
OPENAI_CHAT_MODEL = "gpt-5.5"
TOP_K = "5"
```

O `OPENAI_API_KEY` existente deve ser reutilizado. Não copie o valor para o código.

## Como obter o VECTOR_STORE_ID

Crie um único Vector Store no projeto correto da OpenAI e copie somente o ID
iniciado por `vs_`. Salve esse ID nos Secrets do Streamlit. O aplicativo não cria
um novo Vector Store a cada reinicialização, portanto a base permanece disponível.

## Publicação

1. Substitua os arquivos do projeto pelas versões atualizadas.
2. Confirme que `.streamlit/secrets.toml`, `.env` e PDFs estão ignorados pelo Git.
3. Atualize os Secrets no Streamlit Cloud.
4. Reinicie/reimplante o aplicativo.
5. Entre como administrador, envie um PDF de teste e faça uma consulta.

## Execução local

Crie `.streamlit/secrets.toml` com os valores reais (esse arquivo não deve ser
versionado) e execute:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Privacidade

Os documentos deixam de existir apenas na memória efêmera do Streamlit e passam
a ficar no projeto da OpenAI associado à chave utilizada. Restrinja o acesso ao
projeto/chave da OpenAI e ao painel do Streamlit às pessoas autorizadas.
