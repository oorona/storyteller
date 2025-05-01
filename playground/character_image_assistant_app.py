import streamlit as st
from openai import OpenAI
from PIL import Image
import requests
import io

client = OpenAI()
MODEL = "gpt-4.1-nano"        # any assistants-compatible model
SIZE  = "768x768"

st.title("Assistant-Driven Character Consistency Demo")

# ---------- SESSION -----------
if "assistant_id" not in st.session_state:
    # Build once; reuse every page refresh
    assistant = client.beta.assistants.create(
        name="Character Artist",
        instructions=(
            "You create images that keep a character visually consistent. "
            "Always return exactly one image."
        ),
        model=MODEL,
        tools=[{"type": "image_generation"}],
    )
    st.session_state.assistant_id = assistant.id

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
# ------------------------------

# ---------- STEP 1 : canonical ------------
canonical = st.text_area(
    "1️⃣ Enter canonical character description",
    "Bunnytail – baby dragon, pastel-pink scales, sky-blue eyes, stubby horns, butterfly wings, Ghibli style."
)
if st.button("Create / reset character thread"):
    # New thread for *this* character
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id

    # Add the character sheet as the first user message
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Generate a reference portrait of the following character so we can "
            f"use it as ground truth going forward:\n\n{canonical}\n\n"
            "Return only the image."
        )
    )

    # Run and poll until the image is ready
    run = client.beta.threads.runs.create_and_poll(
        thread_id   = thread.id,
        assistant_id= st.session_state.assistant_id,
        tool_choice = "auto"          # let the assistant pick the image tool
    )

    # The final assistant message contains an image_file
    msgs = client.beta.threads.messages.list(
        thread_id=thread.id, order="asc"
    )
    img_file_id = msgs.data[-1].content[0].image_file.file_id
    url = client.files.content(img_file_id).url
    st.image(url, caption="Reference portrait ✔️")
# -------------------------------------------

# ---------- STEP 2 : new scene -------------
if st.session_state.thread_id:
    scene = st.text_input(
        "2️⃣ Describe a new situation for the SAME character",
        "presenting her science project at school"
    )
    if st.button("Generate scene image"):
        # add new user turn
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=f"Now place the same character in this scene: {scene}. Just return the image."
        )

        run = client.beta.threads.runs.create_and_poll(
            thread_id   = st.session_state.thread_id,
            assistant_id= st.session_state.assistant_id,
            tool_choice = "auto"
        )

        msgs = client.beta.threads.messages.list(
            thread_id=st.session_state.thread_id, order="asc"
        )
        img_file_id = msgs.data[-1].content[0].image_file.file_id
        url = client.files.content(img_file_id).url
        st.image(url, caption="Scene image (consistency check)")
else:
    st.info("Create the reference portrait first.")
