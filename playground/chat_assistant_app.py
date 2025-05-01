import streamlit as st
from openai import OpenAI

# ----------  CONFIG  ----------
client = OpenAI()               # uses OPENAI_API_KEY env var
MODEL = "gpt-4.1-nano"           # any Assistants-compatible model
# ------------------------------

st.title("Assistant Chat Playground")

# ----------  SESSION STATE ----------
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
# ------------------------------------

# -----  SIDEBAR: build / swap personality  -----
st.sidebar.header("🛠️ Assistant personality")

new_name        = st.sidebar.text_input("Name",  "Helpful Bot")
new_instructions = st.sidebar.text_area(
    "Instructions (system prompt)",
    "Output ≤ 30 words. Programador senior (30 a). Sarcástico, estoico, mordaz, hiriente, directo; desprecia inútiles y “expertos” de teclado. Rompe ilusiones con ≤ 30 palabras: filo, ingenio, Siempre responde en el idioma del usuario."
)
if st.sidebar.button("💾 Create / Replace Assistant"):
    # create a fresh Assistant
    assistant = client.beta.assistants.create(
        name=new_name,
        instructions=new_instructions,
        model=MODEL
    )
    st.session_state.assistant_id = assistant.id
    st.session_state.thread_id    = client.beta.threads.create().id
    st.sidebar.success("Assistant ready!")
# -----------------------------------------------

if not st.session_state.assistant_id:
    st.info("Create an Assistant in the sidebar first.")
    st.stop()

# ---------  MAIN CHAT WINDOW ----------
chat_placeholder = st.container()
user_msg = st.chat_input("Type your message…")

if user_msg:
    # (1) add user turn
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=user_msg
    )
    # (2) run the assistant
    run = client.beta.threads.runs.create_and_poll(
        thread_id   = st.session_state.thread_id,
        assistant_id= st.session_state.assistant_id,
    )
    # (3) get the assistant’s reply (the last message in the thread)
    messages = client.beta.threads.messages.list(
        thread_id=st.session_state.thread_id,
        order="asc"
    )
    assistant_reply = messages.data[-1].content[0].text.value

    # streamlit chat UI
    with chat_placeholder:
        st.chat_message("user").write(user_msg)
        st.chat_message("assistant").write(assistant_reply)
