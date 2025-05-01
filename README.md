# AI Personalized Children's Story Generator

This is a full-stack web application that allows users (parents) to generate personalized children's stories with text and images using the OpenAI API.

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
│       └── story_generation.txt
│       └── image_style.txt
├── frontend/
│   ├── index.html         # Main HTML file
│   ├── style.css          # CSS for styling
│   └── script.js          # JavaScript for frontend logic
├── Dockerfile             # <-- For building the backend container
├── docker-compose.yaml    # <-- For running the service with Docker Compose
└── README.
```

## Features

* Multi-step guided story creation process.
* AI-powered suggestions for characters, names, and plot outlines.
* Generation of full story text based on user choices.
* Generation of an accompanying image (as base64 data) using DALL-E.
* Configuration driven by environment variables (`.env` file).
* Customizable AI prompts via external text files.

## Technology Stack

* **Backend:** Python 3, Flask, OpenAI Python Library, python-dotenv
* **Frontend:** HTML5, CSS3, JavaScript (ES6+), Fetch API
* **AI:** OpenAI API (Configurable models like GPT-3.5/GPT-4, DALL-E 3)
* **Containerization:** Docker, Docker Compose

## Setup and Running

There are two ways to run this project:

**Method 1: Running Locally (without Docker)**

1.  **Prerequisites:**
    * Python 3.7+ installed.
    * An OpenAI Account and API Key with access to relevant models (e.g., `gpt-3.5-turbo`, `gpt-4-turbo-preview`, `dall-e-3`). Ensure billing is set up if needed.

2.  **Clone or Download:** Get the project code.

3.  **Set up Backend:**
    * Open a terminal and navigate into the `backend` directory:
        ```bash
        cd path/to/ai_story_generator/backend
        ```
    * **Create & Activate Virtual Environment:**
        ```bash
        # Windows
        python -m venv venv
        .\venv\Scripts\activate
        # macOS/Linux
        python3 -m venv venv
        source venv/bin/activate
        ```
    * **Install Dependencies:**
        ```bash
        pip install -r requirements.txt
        ```
    * **Create `.env` File:** Create a file named `.env` in the `backend` directory.
    * **Configure `.env`:** Add your OpenAI API key and other configuration settings. See the example below. **Modify paths and models as needed.**
        ```dotenv
        # --- OpenAI API Key ---
        OPENAI_API_KEY=your_actual_openai_api_key_here

        # --- Prompt File Paths (Relative to backend directory) ---
        PROMPT_FILE_CHARACTER=prompts/character_suggestions.txt
        PROMPT_FILE_NAME=prompts/name_suggestions.txt
        PROMPT_FILE_PLOT=prompts/plot_suggestions.txt
        PROMPT_FILE_STORY=prompts/story_generation.txt
        PROMPT_FILE_IMAGE_STYLE=prompts/image_style.txt

        # --- OpenAI Model Configuration ---
        TEXT_MODEL_SUGGESTIONS=gpt-3.5-turbo
        TEXT_MODEL_STORY=gpt-4-turbo-preview
        IMAGE_MODEL=dall-e-3

        # --- Generation Parameters ---
        MAX_TOKENS_CHARACTER=150
        MAX_TOKENS_NAME=60
        MAX_TOKENS_PLOT=350
        MAX_TOKENS_STORY=1000
        TEMPERATURE_CHARACTER=0.8
        TEMPERATURE_NAME=0.7
        TEMPERATURE_PLOT=0.7
        TEMPERATURE_STORY=0.7
        IMAGE_SIZE=1024x1024
        IMAGE_QUALITY=standard # Options: standard, hd
        STORY_TARGET_WORD_COUNT=400

        # --- Flask Settings ---
        # FLASK_DEBUG=True # Enable for development reloading (default is True if not set)
        # PORT=5001 # Default port if not set
        ```
        **⚠️ SECURITY WARNING:** Keep your `.env` file secure and out of version control. Add `.env` to your `.gitignore` file if using Git.

4.  **Run Backend Server:**
    * Make sure you are in the `backend` directory with the virtual environment activated.
    * Start the Flask server:
        ```bash
        python app.py
        ```
    * The server will typically run on `http://localhost:5001/`. Keep the terminal open.

5.  **Access Frontend:**
    * Open your web browser and go to `http://localhost:5001`.

**Method 2: Running with Docker Compose**

1.  **Prerequisites:**
    * Docker and Docker Compose installed.
    * An OpenAI Account and API Key.

2.  **Clone or Download:** Get the project code.

3.  **Create and Configure `.env` File:**
    * Navigate to the `backend` directory:
        ```bash
        cd path/to/ai_story_generator/backend
        ```
    * Create the `.env` file inside the `backend` directory as described in Method 1, Step 3. **Make sure your `OPENAI_API_KEY` is correctly set.** Docker Compose will use this file.

4.  **Build and Run:**
    * Navigate back to the **root directory** of the project (`ai_story_generator/`).
    * Run Docker Compose:
        ```bash
        docker-compose up --build
        ```
        * `--build` forces Docker to build the image the first time or if the `Dockerfile` or code has changed.
        * `-d` can be added (`docker-compose up -d --build`) to run the container in detached mode (in the background).
    * Docker Compose will build the backend image using the `Dockerfile` and start the service defined in `docker-compose.yaml`. It will automatically load the variables from `backend/.env`.

5.  **Access Frontend:**
    * Open your web browser and go to `http://localhost:5001`.

6.  **Stopping:**
    * If running in the foreground, press `Ctrl + C` in the terminal where `docker-compose up` is running.
    * If running in detached mode (`-d`), use:
        ```bash
        docker-compose down
        ```

## How It Works

* The **Frontend** (`index.html`, `style.css`, `script.js`) provides the user interface in the browser. JavaScript handles user input, makes API requests to the backend using `Workspace`, and displays the results.
* The **Backend** (`app.py`) is a Flask web server running inside a Docker container (if using Docker Compose). It defines API endpoints that the frontend calls.
* The backend reads configuration (model names, prompt file paths, etc.) from environment variables, which are loaded from the `backend/.env` file by Docker Compose or directly by `python-dotenv` when run locally.
* When an API endpoint is hit, Flask routes the request. The corresponding function often calls the `openai_service.py` module.
* The **OpenAI Service** (`openai_service.py`) loads the required prompt template text from the files specified in the configuration (located in the `backend/prompts/` directory). It formats these templates with user data.
* Using the configured model names and parameters, it communicates with the OpenAI API via the `openai` library.
* For **Image Generation**, it requests the image data as `b64_json` (base64 encoded string).
* The backend sends results (text or base64 image data) back to the frontend as JSON.
* The frontend JavaScript displays the text and uses the base64 string to display the image directly via a `data:image/png;base64,...` Data URL.

## Customization

* **Prompts:** Modify the text files in `backend/prompts/` to change the AI's behavior, tone, or instructions. Ensure placeholders (e.g., `{theme}`) remain correct.
* **Configuration:** Adjust models, tokens, temperature, image quality, etc., by changing the values in the `backend/.env` file. Remember to restart the server or rebuild/restart the Docker container after changes.