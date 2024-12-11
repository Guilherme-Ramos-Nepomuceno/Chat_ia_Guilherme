import streamlit as st
from langchain_core.chat_history import InMemoryChatMessageHistory 
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
import sqlite3
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, insert
from sqlalchemy.exc import SQLAlchemyError



# Inicializando o cliente OpenAI
client = ChatOpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Definindo as configurações iniciais no session_state
llm = ChatOpenAI(model="gpt-4o-mini")
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None

if "messages" not in st.session_state:
    st.session_state["messages"] = []

if "session_id" not in st.session_state:
    st.session_state["session_id"] = "default_session"

if "messages_saved" not in st.session_state:  # Marcador de mensagens salvas
    st.session_state["messages_saved"] = []


store = {}  # memory

st.set_page_config(layout="wide")

# Título da aplicação
st.title(":green[Guilherme] falando")

def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

# Exibindo as mensagens já existentes
for message_data in st.session_state.messages:
    with st.chat_message(message_data["role"]):
        st.markdown(message_data["content"])

# Capturando a entrada do usuário
if prompt := st.chat_input("Digite sua resposta aqui..."):
    # Adiciona a mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)

    # Gerando a resposta usando o modelo OpenAI
    chain = RunnableWithMessageHistory(llm, get_session_history)
    response = chain.invoke(
        input={
            "messages": [
                {"role": "system", "content": "Você deve responder em português."}
            ] + [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.messages
            ] + [
                {"role": "user", "content": prompt}
            ]
        },
        config={
            "configurable": {
                "session_id": st.session_state["session_id"]
            }
        }
    )
    
    # Verifica a estrutura da resposta e extrai o texto
    if hasattr(response, 'content'):
        response_text = response.content
    else:
        response_text = str(response)  # Converte a resposta para string, se necessário
    
    # Adiciona a resposta do assistente
    with st.chat_message("assistant"):
        st.markdown(response_text)

    st.session_state.messages.append({"role": "assistant", "content": response_text})


#jogando as informações para o banco de dados 
# Configurações do PostgreSQL
db_user = 'postgres'
db_password = ''
db_host = 'localhost'
db_port = ''
db_name = 'postgres'

# Criar a URL de conexão com o PostgreSQL
db_url = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
engine = create_engine(db_url)

# Metadados e tabela no PostgreSQL
metadata = MetaData()
conversas_pg2 = Table('conversas_pg2', metadata,
    Column('id', Integer, primary_key=True),
    Column('role', String),
    Column('content', String),
)

# Criar a tabela no PostgreSQL se não existir
metadata.create_all(engine)

# Conectando ao banco de dados SQLite (ou criando se não existir)
conn_sqlite = sqlite3.connect('conversa.db')
cursor_sqlite = conn_sqlite.cursor()

# Criando a tabela no SQLite se não existir
cursor_sqlite.execute('''
CREATE TABLE IF NOT EXISTS conversas2 (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT,
    content TEXT
)
''')

# Listas para acumular perguntas e respostas
def inserir_mensagens_pg(messages, engine):
    with engine.connect() as connection_pg:
        with connection_pg.begin() as transaction:  # Inicia a transação
            novas_mensagens = [m for m in messages if m not in st.session_state["messages_saved"]]
            
            for message in novas_mensagens:
                role = message['role']
                content = message['content']

                try:
                    # Insere no PostgreSQL
                    inserir_pg = insert(conversas_pg2).values(role=role, content=content)
                    connection_pg.execute(inserir_pg)

                    # Marca a mensagem como salva
                    st.session_state["messages_saved"].append(message)

                except SQLAlchemyError as e:
                    st.write(f"Erro ao inserir no PostgreSQL: {e}")

# Chame a função para inserir as mensagens
inserir_mensagens_pg(st.session_state.messages, engine)
      