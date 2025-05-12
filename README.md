# AI Personalized Children's Story Generator

This is a full-stack web application that allows users (parents) to generate personalized, multi-page children's story "books" with unique text and images for each page, powered by the OpenAI API.

## Project Structure
```
ai_story_generator/
├── backend/
│   ├── app.py             # Main Flask application
│   ├── openai_service.py  # Handles OpenAI API calls
│   ├── .env               # <-- IMPORTANT: Contains API key & config
│   ├── requirements.txt   # Python dependencies
│   └── prompts/           # <-- Stores prompt templates
│       ├── character_suggestions.txt
│       ├── name_suggestions.txt
│       ├── plot_suggestions.txt
│       ├── story_generation.txt
│       ├── image_style.txt
│       ├── story_sectioning_prompt.txt       
│       └── image_prompt_creation_prompt.txt  
├── playground
│   ├─ chat_assistant_app.py         
│   ├─ character_image_assistant_app.py
│   ├─ setup_env.sh                  
│   ├─ run_chat.sh                   
│   ├─ run_image.sh                 
│   ├─ requirements.txt
│   └─ README.md
├── frontend/
│   ├── index.html         # Main HTML file
│   ├── style.css          # CSS for styling
│   └── script.js          # JavaScript for frontend logic
├── Dockerfile             # <-- For building the backend container
├── docker-compose.yaml    # <-- For running the service with Docker Compose
└── README.md              # This file
```

## Features

* Multi-step guided story creation process.
* AI-powered suggestions for characters, names, and plot outlines.
* **Background generation** of a character preview image after name selection.
* Generation of a **multi-page story book** with distinct text sections.
* Creation of **unique illustrations for each story section** using OpenAI's Image Edit API, based on the character preview and section content.
* Displays final output in an **interactive book-like interface** with page navigation.
* Configuration driven by environment variables (`.env` file).
* Customizable AI prompts via external text files.
* Utilizes **parallel processing (threading)** in the backend for faster book page image generation.

## Technology Stack

* **Backend:** Python 3, Flask, OpenAI Python Library, python-dotenv, `threading`
* **Frontend:** HTML5, CSS3, JavaScript (ES6+), Fetch API
* **AI:** OpenAI API (Configurable models like GPT-3.5/GPT-4, DALL-E 3 for generation, DALL-E 2 for editing)
* **Containerization:** Docker, Docker Compose

## Setup and Running

(Choose Method 1 or Method 2)

**Method 1: Running Locally (without Docker)**

1.  **Prerequisites:**
    * Python 3.7+ installed.
    * An OpenAI Account and API Key with access to relevant models (e.g., `gpt-3.5-turbo`, `gpt-4-turbo-preview`, `dall-e-3`, `dall-e-2`). Ensure billing is set up.

2.  **Clone or Download:** Get the project code.

3.  **Set up Backend:**
    * Navigate into the `backend` directory: `cd path/to/ai_story_generator/backend`
    * **Create & Activate Virtual Environment:** (e.g., `python -m venv venv`, `source venv/bin/activate`)
    * **Install Dependencies:** `pip install -r requirements.txt`
    * **Create `.env` File:** Create `backend/.env`.
    * **Configure `.env`:** Add your API key and **all** required configuration settings. **Ensure paths and models are correct.**

        ```dotenv
        # --- OpenAI API Key ---
        OPENAI_API_KEY=your_actual_openai_api_key_here

        # --- Prompt File Paths (Relative to backend directory) ---
        PROMPT_FILE_CHARACTER=prompts/character_suggestions.txt
        PROMPT_FILE_NAME=prompts/name_suggestions.txt
        PROMPT_FILE_PLOT=prompts/plot_suggestions.txt
        PROMPT_FILE_STORY=prompts/story_generation.txt
        PROMPT_FILE_IMAGE_STYLE=prompts/image_style.txt
        PROMPT_FILE_STORY_SECTIONING=prompts/story_sectioning_prompt.txt
        PROMPT_FILE_IMAGE_PROMPT_CREATION=prompts/image_prompt_creation_prompt.txt

        # --- OpenAI Model Configuration ---
        TEXT_MODEL_SUGGESTIONS=gpt-3.5-turbo
        TEXT_MODEL_STORY=gpt-4-turbo-preview
        TEXT_MODEL_SECTIONING=gpt-3.5-turbo # Model used to section the story
        TEXT_MODEL_IMG_PROMPT=gpt-3.5-turbo # Model used to create image prompts from sections
        IMAGE_MODEL=dall-e-3           # Model for initial character image generation
        IMAGE_EDIT_MODEL=dall-e-2      # Model for editing images for book pages (DALL-E 2 required for edit API)

        # --- Generation Parameters ---
        MAX_TOKENS_CHARACTER=150
        MAX_TOKENS_NAME=60
        MAX_TOKENS_PLOT=350
        MAX_TOKENS_STORY=1000
        MAX_TOKENS_SECTIONING=1000     # Allow enough for sectioned JSON output
        MAX_TOKENS_IMG_PROMPT=60       # Image prompts should be concise
        TEMPERATURE_CHARACTER=0.8
        TEMPERATURE_NAME=0.7
        TEMPERATURE_PLOT=0.7
        TEMPERATURE_STORY=0.7
        TEMPERATURE_SECTIONING=0.5     # Lower temp for more predictable structure
        TEMPERATURE_IMG_PROMPT=0.6     # Moderately creative image prompts
        IMAGE_SIZE=1024x1024           # Size for generation AND editing (must match for DALL-E 2 Edit)
        IMAGE_QUALITY=standard         # Options: standard, hd (applies to generation)
        STORY_TARGET_WORD_COUNT=400

        # --- Flask Settings ---
        # FLASK_DEBUG=False # Set to False for production-like access, True for dev reloading
        # PORT=5001 # Default port if not set
        ```
        **⚠️ SECURITY WARNING:** Keep your `.env` file secure and out of version control.

4.  **Run Backend Server:**
    * Ensure you are in the `backend` directory with the virtual environment activated.
    * Start Flask: `python app.py`
    * Server runs, typically on `http://localhost:5001/`. Listen on `0.0.0.0` for external access (default in `app.py`). Keep terminal open.

5.  **Access Frontend:**
    * Open browser to `http://localhost:5001` (or `http://<your_server_ip>:5001` for external access if configured and firewall allows).

**Method 2: Running with Docker Compose**

1.  **Prerequisites:**
    * Docker and Docker Compose installed.
    * OpenAI Account and API Key.

2.  **Create and Configure `backend/.env` File:**
    * Navigate to the `backend` directory (`cd path/to/ai_story_generator/backend`).
    * Create the `.env` file as shown in Method 1, Step 3, ensuring `OPENAI_API_KEY` and all other variables are set.

3.  **Build and Run:**
    * Navigate to the **root directory** (`ai_story_generator/`).
    * Run: `docker-compose up --build`
    * Use `docker-compose up -d --build` to run detached.

4.  **Access Frontend:**
    * Open browser to `http://localhost:5001` (or `http://<your_server_ip>:5001`).

5.  **Stopping:**
    * Foreground: `Ctrl + C`.
    * Detached: `docker-compose down`.

## How It Works (Updated Flow)

1.  **Input & Suggestions (Steps 1-4):** The user provides initial details. The **Frontend** makes requests to the Flask **Backend** (`/api/.../suggest`) which uses `openai_service.py` and configured prompts/models to get suggestions for characters, names, and plots via the OpenAI API.
2.  **Character Preview Generation (Step 3 Background):** When a character name is selected, the Frontend JavaScript *immediately* triggers an asynchronous call to the Backend endpoint `/api/image/generate`. It sends a prompt specifically asking for a portrait of the chosen character. The backend uses `openai_service.generate_image` (likely DALL-E 3) to create this image and returns the base64 data. The Frontend stores this base64 data (`generated_character_image_b64`) without waiting for it to finish before proceeding.
3.  **Review (Step 5):** The user reaches the review step. The Frontend checks the status of the background character image generation. If complete, it displays the generated character preview image using the stored base64 data.
4.  **Book Generation Trigger (Step 5 Button):** The user clicks "Generate Book". The Frontend shows a loading indicator. It sends a request to the new `/api/book/generate` endpoint on the Backend, passing *all* the story parameters AND the `generated_character_image_b64` data for the character preview.
5.  **Backend Book Generation Process:** The `/api/book/generate` endpoint orchestrates the following:
    * Calls `generate_story` to get the full story text.
    * Calls `get_story_sections` (using AI via `story_sectioning_prompt.txt`) to divide the full text into logical sections.
    * **In Parallel (using `threading`):** For *each* story section:
        * Calls `create_image_prompt_for_section` (using AI via `image_prompt_creation_prompt.txt`) to generate a concise visual prompt for that section.
        * Calls `edit_image_based_on_prompt`. This function decodes the base character image B64 (received from the frontend) back into bytes. It then calls the OpenAI **Image Edit API** (likely DALL-E 2) using the base character image bytes and the section-specific visual prompt to create a unique illustration for that page. It returns the resulting image as base64.
    * Waits for all parallel tasks to complete.
    * Assembles the results into a JSON array: `{"pages": [{"text": "...", "b64_json": "..."}, ...]}`.
    * Sends the complete book data back to the frontend.
6.  **Frontend Book Display (Step 6):** The Frontend receives the `pages` array. It hides the loading indicator and displays the new book interface. JavaScript handles displaying the current page's text and image (using the `b64_json` data for the `src` attribute) and enables the "Previous"/"Next" navigation buttons.

## API Endpoints

* `POST /api/characters/suggest`: Get character ideas.
* `POST /api/names/suggest`: Get character name suggestions.
* `POST /api/plot/suggest`: Get plot outline suggestions.
* `POST /api/image/generate`: Generate an initial image from a description (used for character preview). Returns `{"b64_json": "...", "revised_prompt": "..."}`.
* `POST /api/book/generate`: Orchestrates the entire book creation process (story text, sectioning, parallel image prompt creation & editing). Requires character details and the base character image base64 in the request. Returns `{"pages": [{"text": "...", "b64_json": "..."}, ...]}`.

## Customization

* **Prompts:** Modify text files in `backend/prompts/` to change AI behavior for suggestions, story style, sectioning logic, image prompt creation, and base image styling. Keep placeholders (e.g., `{theme}`) intact.
* **Configuration:** Adjust models, tokens, temperature, image size/quality etc., via `backend/.env`. Restart backend after changes.

## Notes

* **API Costs:** The book generation process now involves significantly more API calls (1 story + 1 sectioning + N prompt creations + N image edits). Monitor your OpenAI usage and costs.
* **Image Editing (DALL-E 2):** The OpenAI Image Edit API typically uses DALL-E 2, which requires the input image to be square (e.g., 1024x1024) and PNG format. Our setup generates the character preview accordingly. The quality/coherence of edits depends heavily on the prompts and model capabilities.
* **Error Handling:** While basic error handling is present, complex multi-step AI processes can fail in various ways. Further refinement might be needed for production. Check backend logs for details if generation fails.
* **Parallel Processing:** Using `threading` speeds up I/O-bound tasks. For very high concurrency, an `asyncio`-based approach (using `Quart` instead of Flask or async task queues) might be considered in a larger deployment.
