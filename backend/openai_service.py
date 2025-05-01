import os
import base64 # For potential future use if needed, not directly used for b64_json handling
from openai import OpenAI
from dotenv import load_dotenv
import logging
from functools import lru_cache # Cache loaded prompts

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Load Configuration from Environment ---
load_dotenv()

CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "prompt_files": {
        'character': os.getenv("PROMPT_FILE_CHARACTER", "prompts/character_suggestions.txt"),
        'name': os.getenv("PROMPT_FILE_NAME", "prompts/name_suggestions.txt"),
        'plot': os.getenv("PROMPT_FILE_PLOT", "prompts/plot_suggestions.txt"),
        'story': os.getenv("PROMPT_FILE_STORY", "prompts/story_generation.txt"),
        'image_style': os.getenv("PROMPT_FILE_IMAGE_STYLE", "prompts/image_style.txt"),
    },
    "models": {
        'suggestions': os.getenv("TEXT_MODEL_SUGGESTIONS", "gpt-3.5-turbo"),
        'story': os.getenv("TEXT_MODEL_STORY", "gpt-4-turbo-preview"),
        'image': os.getenv("IMAGE_MODEL", "dall-e-3"),
    },
    "max_tokens": {
        'character': int(os.getenv("MAX_TOKENS_CHARACTER", 150)),
        'name': int(os.getenv("MAX_TOKENS_NAME", 60)),
        'plot': int(os.getenv("MAX_TOKENS_PLOT", 350)),
        'story': int(os.getenv("MAX_TOKENS_STORY", 1000)),
    },
    "temperature": {
        'character': float(os.getenv("TEMPERATURE_CHARACTER", 0.8)),
        'name': float(os.getenv("TEMPERATURE_NAME", 0.7)),
        'plot': float(os.getenv("TEMPERATURE_PLOT", 0.7)),
        'story': float(os.getenv("TEMPERATURE_STORY", 0.7)),
    },
    "image": {
        'size': os.getenv("IMAGE_SIZE", "1024x1024"),
        'quality': os.getenv("IMAGE_QUALITY", "standard")
    },
    "story": {
        'word_count': int(os.getenv("STORY_TARGET_WORD_COUNT", 400))
    }
}

# --- OpenAI Client Initialization ---
client = None
if CONFIG["api_key"]:
    try:
        client = OpenAI(api_key=CONFIG["api_key"])
        logger.info("OpenAI client initialized successfully.")
    except Exception as e:
         logger.error(f"Failed to initialize OpenAI client: {e}")
else:
    logger.warning("OPENAI_API_KEY not found in environment variables. OpenAI functionality disabled.")

def is_client_ready():
    """Checks if the OpenAI client is initialized."""
    if client is None:
        logger.error("OpenAI client is not initialized. Check API Key and environment.")
        return False
    return True

# --- Prompt Loading (Cached) ---
@lru_cache(maxsize=10)
def load_prompt_template(prompt_type):
    """Loads a prompt template from the configured file path."""
    filename = CONFIG["prompt_files"].get(prompt_type)
    if not filename:
        logger.error(f"Prompt file path not configured for type: {prompt_type}")
        return None
    try:
        # Assume paths in .env are relative to the backend directory (where this script is)
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
             logger.error(f"Prompt file not found at expected path: {filepath}")
             # Fallback: try relative to current working directory (less reliable)
             if os.path.exists(filename):
                 filepath = filename
                 logger.warning(f"Using fallback path relative to cwd for prompt: {filepath}")
             else:
                 return None # File truly not found

        with open(filepath, 'r', encoding='utf-8') as f:
            template = f.read()
        logger.info(f"Successfully loaded prompt template for '{prompt_type}' from {filepath}")
        return template
    except FileNotFoundError:
        # This case might be redundant due to exists check, but good practice
        logger.error(f"Prompt file not found during open: {filepath}")
        return None
    except Exception as e:
        logger.error(f"Error loading prompt file {filepath}: {e}")
        return None

# --- Helper to Safely Format Prompts ---
def format_prompt(template, data):
    """Safely formats a prompt template using provided data."""
    try:
        return template.format(**data)
    except KeyError as e:
        logger.error(f"Missing placeholder key '{e}' in prompt template.")
        raise ValueError(f"Prompt template error: Missing key {e}") # Raise to signal error
    except Exception as e:
        logger.error(f"Unexpected error formatting prompt: {e}")
        raise ValueError(f"Prompt template formatting error: {e}")


# --- Text Generation Helpers (Using Config and Loaded Prompts) ---

def get_character_suggestions(theme, type, personality_keywords):
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('character')
    if not template: return {"error": "Could not load character prompt template."}

    try:
        prompt_data = {
            'theme': theme,
            'type': type,
            'personality_keywords_str': ', '.join(personality_keywords) if personality_keywords else 'not specified'
        }
        prompt = format_prompt(template, prompt_data)
    except ValueError as e:
        return {"error": str(e)}

    logger.info(f"Character prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['suggestions'],
            messages=[
                {"role": "system", "content": "You are a creative assistant generating ideas for children's stories."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=CONFIG['max_tokens']['character'],
            temperature=CONFIG['temperature']['character'],
            n=1
        )
        suggestions_raw = response.choices[0].message.content.strip()
        # Parsing logic (keep as before or improve)
        suggestion_list = [line[line.find(' ')+1:].strip() for line in suggestions_raw.split('\n') if line.strip() and line[0].isdigit() and ' ' in line]
        if not suggestion_list and suggestions_raw: # Fallback
             suggestion_list = [s.strip() for s in suggestions_raw.split('\n') if s.strip()]

        logger.info(f"Character suggestions received: {suggestion_list}")
        return {"suggestions": suggestion_list if suggestion_list else ["No suggestions generated."]}

    except Exception as e:
        logger.error(f"Error calling OpenAI for character suggestions: {e}")
        return {"error": f"Error generating suggestions: {e}"}


def get_name_suggestions(character_description, theme):
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('name')
    if not template: return {"error": "Could not load name prompt template."}

    try:
        prompt = format_prompt(template, {'character_description': character_description, 'theme': theme})
    except ValueError as e:
         return {"error": str(e)}

    logger.info(f"Name prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['suggestions'],
            messages=[
                {"role": "system", "content": "You are a creative assistant helping name characters in children's stories."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=CONFIG['max_tokens']['name'],
            temperature=CONFIG['temperature']['name'],
            n=1
        )
        names_string = response.choices[0].message.content.strip()
        name_list = [name.strip() for name in names_string.split(',') if name.strip()]
        logger.info(f"Name suggestions received: {name_list}")
        return {"names": name_list if name_list else ["No names generated."]}
    except Exception as e:
        logger.error(f"Error calling OpenAI for name suggestions: {e}")
        return {"error": f"Error generating names: {e}"}


def get_plot_suggestions(learning_objective, character_description, theme):
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('plot')
    if not template: return {"error": "Could not load plot prompt template."}

    try:
        prompt_data = {
            'learning_objective': learning_objective,
            'character_description': character_description,
            'theme': theme
        }
        prompt = format_prompt(template, prompt_data)
    except ValueError as e:
         return {"error": str(e)}

    logger.info(f"Plot prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['suggestions'],
            messages=[
                {"role": "system", "content": "You are a creative assistant outlining simple plots for children's stories focusing on a learning goal."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=CONFIG['max_tokens']['plot'],
            temperature=CONFIG['temperature']['plot'],
            n=1
        )
        plots_raw = response.choices[0].message.content.strip()
        # Parsing logic (keep as before or improve)
        plot_list = []
        current_plot = ""
        for line in plots_raw.split('\n'):
            stripped_line = line.strip()
            if stripped_line and stripped_line[0].isdigit() and ' ' in stripped_line:
                if current_plot: plot_list.append(current_plot.strip())
                current_plot = stripped_line[stripped_line.find(' ')+1:].strip()
            elif current_plot:
                current_plot += " " + stripped_line
        if current_plot: plot_list.append(current_plot.strip())
        if not plot_list and plots_raw: # Fallback
             plot_list = [p.strip() for p in plots_raw.split('\n\n') if p.strip()]
             if len(plot_list) < 2: plot_list = [p.strip() for p in plots_raw.split('\n') if p.strip()]


        logger.info(f"Plot suggestions received: {plot_list}")
        return {"plots": plot_list if plot_list else ["No plot ideas generated."]}
    except Exception as e:
        logger.error(f"Error calling OpenAI for plot suggestions: {e}")
        return {"error": f"Error generating plot ideas: {e}"}


def generate_story(child_name, character_name, character_description, plot_choice, learning_objective, theme, personality_keywords):
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('story')
    if not template: return {"error": "Could not load story prompt template."}

    try:
        prompt_data = {
            'story_word_count': CONFIG['story']['word_count'],
            'child_name': child_name,
            'character_name': character_name,
            'character_description': character_description,
            'plot_choice': plot_choice,
            'learning_objective': learning_objective,
            'theme': theme,
            'personality_keywords_str': ', '.join(personality_keywords) if personality_keywords else 'not specified'
        }
        prompt = format_prompt(template, prompt_data)
    except ValueError as e:
         return {"error": str(e)}

    logger.info(f"Story generation prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['story'],
            messages=[
                {"role": "system", "content": "You are a warm and imaginative storyteller for young children, creating personalized tales based on specific inputs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=CONFIG['max_tokens']['story'],
            temperature=CONFIG['temperature']['story'],
            n=1
        )
        story_text = response.choices[0].message.content.strip()
        logger.info(f"Story generated successfully (length: {len(story_text)} chars).")
        if len(story_text) < 50:
             logger.warning("Generated story seems very short.")
             return {"story_text": "The generated story was too short. Please try again."} # Return dict
        return {"story_text": story_text}
    except Exception as e:
        logger.error(f"Error calling OpenAI for story generation: {e}")
        return {"error": f"Oops! Error generating the story: {e}"}


# --- Image Generation Helper (Returns Base64) ---
def generate_image(description):
    """Generates an image using OpenAI DALL-E and returns base64 JSON."""
    if not is_client_ready(): return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    style_prompt_template = load_prompt_template('image_style')
    style_prompt = style_prompt_template.strip() if style_prompt_template else "" # Use empty if file fails

    full_prompt = f"{description}. {style_prompt}".strip() # Combine and remove trailing space if style is empty
    logger.info(f"Image generation prompt: {full_prompt}")

    try:
        response = client.images.generate(
            model=CONFIG['models']['image'],
            prompt=full_prompt,            
            size=CONFIG['image']['size'],
            quality=CONFIG['image']['quality'],
            n=1
        )

        if response.data and response.data[0].b64_json:
            b64_json_string = response.data[0].b64_json
            revised_prompt = response.data[0].revised_prompt
            logger.info(f"Image generated successfully as base64 JSON (length: {len(b64_json_string)}).")
            return {"b64_json": b64_json_string, "revised_prompt": revised_prompt}
        else:
             logger.error("OpenAI image response did not contain expected b64_json data.")
             return {"error": "Invalid response format from image API.", "error_code": "invalid_response"}

    except Exception as e:
        logger.error(f"Error calling OpenAI DALL-E: {e}")
        # Improved error code detection
        error_str = str(e).lower()
        error_code = "generic_error"
        user_message = f"Failed to generate image: An unexpected error occurred."

        if "content policy" in error_str or "safety system" in error_str:
            error_code = "content_policy_error"
            user_message = "Image generation failed due to content policy. Try a different description."
        elif "billing" in error_str or "quota" in error_str:
             error_code = "billing_error"
             user_message = "Image generation failed due to account limits."
        elif "authentication" in error_str or "api key" in error_str:
             error_code = "auth_error"
             user_message = "Image generation failed due to authentication error. Check API Key."
        elif "invalid_request_error" in error_str: # e.g., invalid size/model
            error_code = "invalid_request"
            user_message = f"Image generation failed: Invalid request ({e})" # Include specific error detail
        # Add more specific error checks if needed based on OpenAI API documentation

        logger.warning(f"Image generation failed - Code: {error_code}, Message: {e}")
        return {"error": user_message, "error_code": error_code}