import streamlit as st
import json
import os
from datetime import datetime
from memory import ShortMemory
from storage import Storage
from openai import OpenAI
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações
PRODUCTS_FILE = "mapeamento.json"
STORAGE_DIR = "data"

# Configurações
openai_api_key = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID = st.secrets["ASSISTANT_ID"]

# Inicialização do cliente OpenAI
client = OpenAI(api_key=openai_api_key)

# Variável global para logs de produtos
if 'products_log' not in st.session_state:
    st.session_state.products_log = []
if 'assistant_thread' not in st.session_state:
    st.session_state.assistant_thread = None
if 'assistant_info' not in st.session_state:
    st.session_state.assistant_info = None


# Inicialização
@st.cache_resource
def init_components():
    storage = Storage(STORAGE_DIR)
    with open(PRODUCTS_FILE) as f:
        products = json.load(f)
    logger.info(f"Carregados {len(products)} produtos do arquivo {PRODUCTS_FILE}")

    # Obter informações do assistente para logar o modelo
    try:
        assistant = client.beta.assistants.retrieve(ASSISTANT_ID)
        st.session_state.assistant_info = assistant
        logger.info(f"Assistente carregado: ID {ASSISTANT_ID}")
        logger.info(f"Modelo configurado no assistente: {assistant.model}")
    except Exception as e:
        logger.error(f"Erro ao recuperar informações do assistente: {str(e)}")
        st.error(f"Erro ao carregar assistente: {str(e)}")
        st.stop()

    return storage, products


try:
    storage, products = init_components()
except Exception as e:
    logger.error(f"Erro ao inicializar componentes: {str(e)}")
    st.error(f"Erro ao inicializar componentes: {str(e)}")
    st.stop()

# Gerenciamento de Estado
if 'memory' not in st.session_state:
    st.session_state.memory = ShortMemory()
if 'current_session' not in st.session_state:
    st.session_state.current_session = None


# Função para criar nova thread no assistente
def create_new_thread():
    try:
        thread = client.beta.threads.create()
        st.session_state.assistant_thread = thread.id
        logger.info(f"Nova thread criada: {thread.id}")
    except Exception as e:
        logger.error(f"Erro ao criar thread: {str(e)}")
        st.error(f"Erro ao criar thread: {str(e)}")


# Funções de Callback
def start_new_negotiation():
    logger.info("Iniciando nova negociação")
    st.session_state.memory.clear()
    st.session_state.current_session = None
    st.session_state.client_name = ""
    st.session_state.client_phone = ""
    st.session_state.products_log = []
    create_new_thread()


def send_message():
    user_input = st.session_state.user_input.strip()
    if not user_input:
        return

    logger.info(f"Usuário enviou mensagem: {user_input}")

    # Adicionar mensagem do usuário
    st.session_state.memory.add("user", user_input)

    # Verificar se temos uma thread ativa
    if not st.session_state.assistant_thread:
        create_new_thread()

    # Adicionar mensagem à thread
    try:
        client.beta.threads.messages.create(
            thread_id=st.session_state.assistant_thread,
            role="user",
            content=user_input
        )
        logger.info(f"Mensagem adicionada à thread {st.session_state.assistant_thread}")
    except Exception as e:
        logger.error(f"Erro ao adicionar mensagem à thread: {str(e)}")
        st.error(f"Erro ao adicionar mensagem: {str(e)}")
        return

    # Executar o assistente
    try:
        with st.spinner("ANA está pensando..."):
            # Log do modelo sendo usado
            logger.info(f"Executando assistente com modelo: {st.session_state.assistant_info.model}")

            run = client.beta.threads.runs.create(
                thread_id=st.session_state.assistant_thread,
                assistant_id=ASSISTANT_ID
            )

            # Aguardar conclusão da execução
            while run.status in ["queued", "in_progress"]:
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.assistant_thread,
                    run_id=run.id
                )

            if run.status != "completed":
                error_msg = f"Erro na execução do assistente: {run.status}"
                logger.error(error_msg)
                st.error(error_msg)
                return

            # Recuperar mensagens do assistente
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.assistant_thread
            )

            # Filtrar apenas a última resposta do assistente
            assistant_messages = [
                msg for msg in messages.data
                if msg.role == "assistant" and msg.run_id == run.id
            ]

            if not assistant_messages:
                logger.warning("Nenhuma mensagem do assistente encontrada")
                return

            # Obter o texto da resposta (considerando que pode ter múltiplos conteúdos)
            response_content = ""
            for content in assistant_messages[0].content:
                if content.type == "text":
                    response_content = content.text.value
                    break

            logger.info(f"Resposta bruta recebida do assistente: {response_content}")

            # Processar informações de log
            log_info = "nenhum"
            cleaned_response = response_content

            # Extrair informações de log se existirem
            if "[LOG: produto_id=" in response_content:
                try:
                    # Extrair parte do log
                    log_part = response_content.split("[LOG: produto_id=")[1].split("]")[0]
                    cleaned_response = response_content.split("[LOG: produto_id=")[0].strip()
                    logger.debug(f"Log extraído: {log_part}")

                    # Registrar no log
                    if log_part != "nenhum":
                        product_ids = [int(id.strip()) for id in log_part.split(",") if id.strip().isdigit()]
                        logger.info(f"IDs de produtos detectados: {product_ids}")

                        # Obter detalhes completos dos produtos
                        for pid in product_ids:
                            product = next((p for p in products if p["id"] == pid), None)
                            if product:
                                logger.info(f"Produto usado: ID {pid} - {product['nome']}")
                                st.session_state.products_log.append({
                                    "id": product["id"],
                                    "nome": product["nome"],
                                    "contexto_uso": product["contexto_uso"],
                                    "content": cleaned_response,
                                    "timestamp": datetime.now().isoformat()
                                })

                    log_info = log_part
                except Exception as e:
                    logger.error(f"Erro ao processar log: {str(e)}")
                    log_info = "erro"
            else:
                logger.info("Nenhum produto detectado na resposta")

            # Adicionar resposta do agente (sem o log)
            st.session_state.memory.add("assistant", cleaned_response)
            logger.info(f"Resposta limpa adicionada ao histórico: {cleaned_response}")

            # Salvar/Atualizar sessão
            if st.session_state.get('client_name') and st.session_state.get('client_phone'):
                save_session()

    except Exception as e:
        logger.error(f"Erro ao executar assistente: {str(e)}")
        st.error(f"Erro ao processar resposta: {str(e)}")

    # Limpar input
    st.session_state.user_input = ""


def save_session():
    try:
        session_data = {
            "client_name": st.session_state.client_name,
            "client_phone": st.session_state.client_phone,
            "created_at": datetime.now().isoformat(),
            "history": st.session_state.memory.get_history(),
            "products_log": st.session_state.products_log,
            "assistant_thread": st.session_state.assistant_thread
        }

        if st.session_state.current_session:
            storage.update_session(st.session_state.current_session, session_data)
            logger.info(f"Sessão atualizada: {st.session_state.current_session}")
        else:
            filename = storage.save_session(session_data)
            st.session_state.current_session = filename
            logger.info(f"Nova sessão salva: {filename}")
    except Exception as e:
        logger.error(f"Erro ao salvar sessão: {str(e)}")
        st.error(f"Erro ao salvar sessão: {str(e)}")


def load_session(filename):
    try:
        session_data = storage.load_session(filename)
        st.session_state.memory.load_history(session_data["history"])
        st.session_state.client_name = session_data["client_name"]
        st.session_state.client_phone = session_data["client_phone"]
        st.session_state.current_session = filename
        st.session_state.products_log = session_data.get("products_log", [])
        st.session_state.assistant_thread = session_data.get("assistant_thread")
        logger.info(f"Sessão carregada: {filename}")
    except Exception as e:
        logger.error(f"Erro ao carregar sessão: {str(e)}")
        st.error(f"Erro ao carregar sessão: {str(e)}")


# Função para mostrar logs de produtos
def show_products_log():
    st.sidebar.subheader("📊 Log de Produtos Usados")

    if not st.session_state.products_log:
        st.sidebar.info("Nenhum produto usado ainda")
        return

    # Agrupar por produto para estatísticas
    product_stats = {}
    for entry in st.session_state.products_log:
        pid = entry["id"]
        if pid not in product_stats:
            product_stats[pid] = {
                "nome": entry["nome"],
                "count": 0,
                "last_used": entry["timestamp"]
            }
        product_stats[pid]["count"] += 1
        if entry["timestamp"] > product_stats[pid]["last_used"]:
            product_stats[pid]["last_used"] = entry["timestamp"]

    # Mostrar estatísticas resumidas
    st.sidebar.write("**Produtos mais usados:**")
    for pid, stats in sorted(product_stats.items(), key=lambda x: x[1]["count"], reverse=True)[:5]:
        st.sidebar.write(f"- {stats['nome']} (ID: {pid}): {stats['count']} vezes")

    # Mostrar log detalhado
    with st.sidebar.expander("📝 Log Completo"):
        for entry in st.session_state.products_log:
            st.write(f"**{entry['nome']}** (ID: {entry['id']})")
            st.caption(f"Usado em: {entry['timestamp'][11:19]}")
            st.write(f"**Contexto:** {entry['contexto_uso']}")
            st.write(f"**Resposta associada:** {entry['content'][:100]}...")
            st.divider()


# Interface Principal
st.title("🤖 Agente de Negociação Avançado (ANA)")
st.caption("Conduza negociações com empatia e estratégia")

# Sidebar - Gerenciamento de Sessões
st.sidebar.title("📂 Sessões de Negociação")
st.sidebar.button("➕ Nova Negociação", on_click=start_new_negotiation)

# Botão para mostrar logs
if st.sidebar.button("📊 Mostrar Log de Produtos"):
    show_products_log()

search_term = st.sidebar.text_input("🔍 Buscar por nome ou telefone")
sessions = storage.list_sessions(search_term)

if sessions:
    st.sidebar.subheader("Sessões Salvas:")
    for session in sessions:
        btn = st.sidebar.button(
            f"{session['client_name']} - {session['client_phone']} | {session['created_at'][:10]}",
            key=session['filename']
        )
        if btn:
            load_session(session['filename'])

# Área de Informações do Cliente
with st.expander("ℹ️ Informações do Cliente"):
    st.text_input("Nome completo", key="client_name")
    st.text_input("Telefone/WhatsApp", key="client_phone")

# Área de Conversação
st.subheader("💬 Conversa de Negociação")
conversation = st.container()

# Exibir histórico
for msg in st.session_state.memory.get_history():
    if msg["role"] == "user":
        conversation.markdown(f"**Cliente:** {msg['content']}")
    else:
        # Verificar se temos log para esta mensagem
        log_entry = next((log for log in st.session_state.products_log if log["content"] == msg["content"]), None)

        if log_entry:
            # Mostrar com ícone de informação e tooltip
            conversation.markdown(f"**ANA:** {msg['content']} 🔍",
                                  help=f"Produto usado: {log_entry['nome']} (ID: {log_entry['id']})")
        else:
            conversation.markdown(f"**ANA:** {msg['content']}")

# Entrada de Mensagem
st.text_input(
    "O que o cliente disse:",
    key="user_input",
    on_change=send_message,
    placeholder="Digite a mensagem do cliente..."
)

# Botões de Ação
col1, col2 = st.columns(2)
col1.button("🔄 Atualizar Visualização")
col2.button("💾 Salvar Sessão", on_click=save_session)
