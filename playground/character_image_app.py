import io, uuid
import streamlit as st
from openai import OpenAI
from PIL import Image
import requests
import random, hashlib
import io, base64
import requests, os, json

# ---------- CONFIG ----------
client = OpenAI()
MODEL = "gpt-image-1"           # DALL·E-3 works too (remove seed logic)
IMAGE_SIZE = "1024x1024"
QUALITY = "high"             # low, medium, high
OUTPUT_FORMAT = "png"         # png, jpg, webp
BACKGROUND = "auto"  # transparent,auto
# -----------------------------



def pick_seed(prompt: str, mode="hash"):
    if mode == "hash":
        return int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
    elif mode == "random":
        return random.randint(0, 2**31 - 1)
    else:                      # manual fallback
        return int(mode)
    
def gen_image(prompt: str):
    gen = client.images.generate(
        model  = MODEL,
        prompt = prompt,
        size   = IMAGE_SIZE,
        n      = 1,
        quality = QUALITY,
        output_format=OUTPUT_FORMAT,
        background=BACKGROUND,
        #seed   = st.session_state.seed 
        #generation_config={"seed": st.session_state.seed 
    )
    raw_bytes = base64.b64decode(gen.data[0].b64_json)
    buffer = io.BytesIO(raw_bytes)
    buffer.name = "reference.png"  # set filename for download
    return buffer

def gen_edit(prompt: str, image):
    gen = client.images.edit(
        model  = MODEL,
        image  = [image],
        prompt = prompt,
        size   = IMAGE_SIZE,
        n      = 1,
        quality = QUALITY
        #seed   = st.session_state.seed 
        #generation_config={"seed": st.session_state.seed 
    )
    raw_bytes = base64.b64decode(gen.data[0].b64_json)
    buffer = io.BytesIO(raw_bytes)
    buffer.name = "situation.png"  # set filename for download
    return buffer

st.title("Character Consistency Demo")

# -------- CHARACTER SETUP -------------
canonical_prompt = st.text_area(
    "1️⃣ Canonical character description",
    "Create an image of a baby dragon named bunnytail with butterfly wings"
)

if "ref_image" not in st.session_state:
    st.session_state.ref_image = None
if "seed" not in st.session_state:       # lock anatomy for gpt-image-1
    st.session_state.seed = pick_seed(canonical_prompt, mode="hash")
# --------------------------------------

if st.button("Generate reference portrait"):
    #st.session_state.seed = int(uuid.uuid4().int % 2**31)  # random seed
    # gen = client.images.generate(
    #     model  = MODEL,
    #     prompt = canonical_prompt,
    #     size   = IMAGE_SIZE,
    #     n      = 1,
    #     quality = QUALITY
    #     #seed   = st.session_state.seed 
    #     #generation_config={"seed": st.session_state.seed }   # 👈 accepted by backend
    # )
    # raw_bytes = base64.b64decode(gen.data[0].b64_json)
    # buffer = io.BytesIO(raw_bytes)
    # buffer.seek(0)   

    st.session_state.ref_image = gen_image(canonical_prompt)
    #st.image(st.session_state.ref_image , caption="Reference image ✔️")

# -------- SCENE CREATOR ---------------
if st.session_state.ref_image:
    st.image(st.session_state.ref_image, caption="Reference portrait ✔️")
    scene = st.text_input("2️⃣ Describe a new situation",
                          "presenting her science project at school")
    if st.button("Generate scene image"):
        full_prompt = f"{canonical_prompt} {scene}"
        # gen = client.images.generate(
        #     model  = MODEL,
        #     prompt = full_prompt,
        #     size   = IMAGE_SIZE,
        #     n      = 1,
        #     quality = QUALITY
        #     #seed   = st.session_state.seed  # reuse seed for continuity
        # )

        # raw_bytes = base64.b64decode(gen.data[0].b64_json)
        # buffer = io.BytesIO(raw_bytes)
        # buffer.seek(0)   

        st.session_state.scene_image = gen_edit(full_prompt,st.session_state.ref_image)
        if st.session_state.scene_image:
            st.image(st.session_state.scene_image, caption="Scene with consistent character")
else:
    st.info("Create the reference portrait first.")
