# AI Character & Chat Playground

A lightweight Streamlit tool‑suite that showcases **OpenAI’s latest text and image models**:

* **GPT‑4o‑mini** (via the **Assistants API**) for natural‑language conversations and metadata extraction.
* **gpt‑image‑1** (and DALL·E 3) for high‑fidelity, reference‑consistent image generation, variations, and edits.

The project demonstrates how to:

1. Persist *conversation* and *character* context on OpenAI’s servers instead of inside your client code.
2. Generate structured **metadata** (canon prompts, scene directives, edit masks) from free‑form text.
3. Feed that metadata straight into OpenAI’s new **image generation endpoints**—all in memory, zero temp files.

---

## Table of Contents
1. [Features](#features)
2. [Architecture](#architecture)
3. [Quick Start](#quick-start)
4. [Usage Guide](#usage-guide)
5. [AI Workflow Details](#ai-workflow-details)
6. [Project Structure](#project-structure)
7. [Roadmap](#roadmap)
8. [License](#license)

---

## Features
| Area | Capability |
|------|------------|
| **Interactive chat** | Spin up or swap *Assistants* with custom system prompts; chat in real time while OpenAI stores the thread history. |
| **Canonical character sheets** | Capture a one‑sentence *metadata* profile (appearance, style, mood) that travels with every image request. |
| **Reference portrait** | One click generates a stable reference shot of the character. |
| **Scene composer** | Enter a new situation; the app merges the canonical sheet + scene text → sends to `gpt-image-1` → shows a visually consistent render. |
| **Image edits & variations** | In‑memory PNG + mask workflow demonstrates OpenAI’s `images/edits` and `images/variations` endpoints—no disk I/O. |
| **Environment scripts** | `setup_env.sh`, `run_chat.sh`, `run_image.sh` handle venv creation, dependency install, and key loading from `../.env`. |

---

## Architecture
```mermaid
flowchart TD
    subgraph Browser
        A[Streamlit UI]
    end
    subgraph Server‑Side (OpenAI)
        B[Assistant Thread \n GPT‑4o‑mini]
        C[gpt‑image‑1 \n Image Tool]
    end
    A -- system prompt / user text --> B
    A -- canonical prompt / scene text --> B
    B -- tool call + image metadata --> C
    C -- b64 image --> B -- message --> A
```

* **Assistants API** holds the entire message thread plus the canonical character description.
* GPT‑4o reads that context, emits structured **image‑tool metadata** (`model`, `prompt`, `size`, `mask`) which is forwarded to the image engine.
* The image endpoint returns a base‑64 PNG which the app decodes and streams back to the UI—reference + scene side by side.

---

## Quick Start
```bash
# 1 Clone and enter the repo
$ git clone https://github.com/you/ai-playground.git
$ cd ai-playground

# 2 Place your OpenAI key one directory up
$ echo "OPENAI_API_KEY=sk‑…" > ../.env

# 3 Install Python 3.11+ and run setup
$ ./setup_env.sh

# 4 Launch either demo
$ ./run_chat.sh   # text playground
$ ./run_image.sh  # character & scenes
```
Open your browser at the Streamlit URL (usually http://localhost:8501).

---

## Usage Guide
### Chat Playground (`chat_assistant_app.py`)
1. **Define personality** in the sidebar → *Create / Replace Assistant*.
2. Chat naturally; the thread persists on the server, not in your payload.
3. Click *Reset Conversation* (optional) to start a fresh thread.

### Character & Scene Demo (`character_image_assistant_app.py`)
1. **Describe the character** → *Generate reference*.
2. The app stores the returned PNG bytes as `ref_img`.
3. **Describe a scene** → *Generate scene image*.
4. The UI shows reference first, then the new scene—exactly in that order.
5. *Generate scene* again to overwrite both images with the latest pair.

---

## AI Workflow Details
### 1 Metadata Extraction
* GPT‑4o distills the free‑text description into a **canonical prompt** – a compact piece of metadata that enforces color palette, anatomy, and art style.
* The canonical prompt is injected once into the Assistant thread and reused forever.

### 2 Scene Directive
* Each new scene textbox value forms the **scene directive metadata** (`"sitting on a moonlit rooftop"`).
* GPT‑4o concatenates sheet + scene → full image prompt.

### 3 Image Generation & Consistency
1. Assistant calls the `image_generation` tool with `model="gpt-image-1"`, `prompt`, `size`, `style`, etc.
2. The engine returns a **base‑64 PNG** (`response_format="b64_json"`).
3. The UI decodes the bytes on the fly (`base64 -> BytesIO`) and displays them—no temp files.
4. For rock‑solid consistency the second demo also shows how to feed the reference back into **`/images/edits`** or **`/images/variations`** using an in‑memory mask.

### 4 Why GPT‑4o + gpt‑image‑1?
* GPT‑4o’s long context lets us embed rich personality plus a running summary.
* `gpt-image-1` brings superior edge‑detail and style adherence vs. DALL·E 3, while exposing edit & variation routes for iterative workflows.

---

## Project Structure
```
├─ chat_assistant_app.py          # text playground
├─ character_image_assistant_app.py
├─ setup_env.sh                  # venv + pip install
├─ run_chat.sh                   # loads ../.env key, launches chat
├─ run_image.sh                  # loads ../.env key, launches image demo
├─ requirements.txt
└─ README.md
```

---

## Roadmap
* **SDK upgrade** once OpenAI exposes deterministic seeding in the public Images API.
* **Mask editor UI** – draw masks directly in the browser.
* **User accounts** – map each visitor to their own Assistant threads.
* **Vector‑store memory** – retrieve older scenes on demand.

---

## License
MIT – see `LICENSE` file for details.
