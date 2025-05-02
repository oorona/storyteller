import os
import base64 # Needed for decoding image data
import io # Needed for image bytes handling
from openai import OpenAI
from dotenv import load_dotenv
import logging
import json # For parsing sectioning result
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
        'story_sectioning': os.getenv("PROMPT_FILE_STORY_SECTIONING", "prompts/story_sectioning_prompt.txt"),
        'image_prompt_creation': os.getenv("PROMPT_FILE_IMAGE_PROMPT_CREATION", "prompts/image_prompt_creation_prompt.txt"),
    },
    "models": {
        'suggestions': os.getenv("TEXT_MODEL_SUGGESTIONS", "gpt-3.5-turbo"),
        'story': os.getenv("TEXT_MODEL_STORY", "gpt-4-turbo-preview"),
        'sectioning': os.getenv("TEXT_MODEL_STORY", "gpt-3.5-turbo"),
        'img_prompt': os.getenv("TEXT_MODEL_SUGGESTIONS", "gpt-3.5-turbo"),
        'image_gen': os.getenv("IMAGE_MODEL", "dall-e-3"),
        'image_edit': os.getenv("IMAGE_EDIT_MODEL", "dall-e-2"),
    },
    "max_tokens": {
        'character': int(os.getenv("MAX_TOKENS_CHARACTER", 150)),
        'name': int(os.getenv("MAX_TOKENS_NAME", 60)),
        'plot': int(os.getenv("MAX_TOKENS_PLOT", 350)),
        'story': int(os.getenv("MAX_TOKENS_STORY", 1000)),
        'sectioning': int(os.getenv("MAX_TOKENS_STORY", 1000)),
        'img_prompt': int(os.getenv("MAX_TOKENS_NAME", 60)),
    },
    "temperature": {
        'character': float(os.getenv("TEMPERATURE_CHARACTER", 0.8)),
        'name': float(os.getenv("TEMPERATURE_NAME", 0.7)),
        'plot': float(os.getenv("TEMPERATURE_PLOT", 0.7)),
        'story': float(os.getenv("TEMPERATURE_STORY", 0.7)),
        'sectioning': float(os.getenv("TEMPERATURE_STORY", 0.5)),
        'img_prompt': float(os.getenv("TEMPERATURE_NAME", 0.6)),
    },
    "image": { # Settings for initial generation
        'size': os.getenv("IMAGE_SIZE", "1024x1024"),
        'quality': os.getenv("IMAGE_QUALITY", "standard"),
        'output_format': os.getenv("OUTPUT_FORMAT", "png")
    },
    "image_edit": { # Settings for image editing
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
    # This function needs to return True only if client is not None
    return client is not None

# --- Prompt Loading (Cached) ---
@lru_cache(maxsize=10)
def load_prompt_template(prompt_type):
    """Loads a prompt template from the configured file path."""
    filename = CONFIG["prompt_files"].get(prompt_type)
    if not filename:
        logger.error(f"Prompt file path not configured for type: {prompt_type}")
        return None
    try:
        # Construct path relative to this script's directory
        filepath = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(filepath):
             logger.error(f"Prompt file not found at expected path: {filepath}")
             # Fallback: try relative to current working directory
             if os.path.exists(filename):
                 filepath = filename
                 logger.warning(f"Using fallback path relative to cwd for prompt: {filepath}")
             else:
                 return None # File truly not found

        with open(filepath, 'r', encoding='utf-8') as f:
            template = f.read()
        logger.info(f"Successfully loaded prompt template for '{prompt_type}' from {filepath}")
        return template
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
        raise ValueError(f"Prompt template error: Missing key {e}")
    except Exception as e:
        logger.error(f"Unexpected error formatting prompt: {e}")
        raise ValueError(f"Prompt template formatting error: {e}")


# --- Text Generation Helpers (Suggestions) ---

def get_character_suggestions(theme, type, personality_keywords):
    """Generates character ideas using OpenAI."""
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('character')
    if not template: return {"error": "Could not load character prompt template."}

    try:
        prompt = format_prompt(
            template,
            {'theme': theme, 'type': type, 'personality_keywords_str': ', '.join(personality_keywords) if personality_keywords else 'not specified'}
        )
    except ValueError as e:
        return {"error": str(e)}

    logger.info(f"Character prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['suggestions'],
            messages=[ {"role": "system", "content": "You are a creative assistant generating ideas for children's stories."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['character'], temperature=CONFIG['temperature']['character'], n=1
        )
        suggestions_raw = response.choices[0].message.content.strip()
        # Parsing logic - improved slightly
        suggestion_list = []
        potential_lines = suggestions_raw.split('\n')
        for line in potential_lines:
            line = line.strip()
            if line and line[0].isdigit():
                 first_space_index = -1
                 for i in range(len(line)):
                     if not line[i].isdigit() and line[i] != '.':
                         if line[i] == ' ': first_space_index = i; break
                 if first_space_index == -1 and '.' in line: first_space_index = line.find('.')
                 if first_space_index != -1:
                    suggestion_text = line[first_space_index+1:].strip()
                    if suggestion_text: suggestion_list.append(suggestion_text)
        if not suggestion_list and suggestions_raw:
             logger.warning("Could not parse numbered list for characters, using raw lines.")
             suggestion_list = [s.strip() for s in suggestions_raw.split('\n') if s.strip()]
        logger.info(f"Character suggestions received: {suggestion_list}")
        return {"suggestions": suggestion_list if suggestion_list else ["No suggestions generated."]}
    except Exception as e:
        logger.error(f"Error calling OpenAI for character suggestions: {e}")
        error_msg = f"Error generating suggestions: {e}"
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
             if e.response.status_code == 401: error_msg = "Error: OpenAI Authentication failed. Check API Key."
             elif e.response.status_code == 429: error_msg = "Error: OpenAI Rate limit exceeded."
        return {"error": error_msg}


def get_name_suggestions(character_description, theme):
    """Generates character name suggestions using OpenAI."""
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
            messages=[ {"role": "system", "content": "You are a creative assistant naming characters."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['name'], temperature=CONFIG['temperature']['name'], n=1
        )
        names_string = response.choices[0].message.content.strip()
        name_list = [name.strip() for name in names_string.split(',') if name.strip()]
        logger.info(f"Name suggestions received: {name_list}")
        return {"names": name_list if name_list else ["No names generated."]}
    except Exception as e:
        logger.error(f"Error calling OpenAI for name suggestions: {e}")
        # Add specific error check?
        return {"error": f"Error generating names: {e}"}


def get_plot_suggestions(learning_objective, character_description, theme):
    """Generates plot outline suggestions using OpenAI."""
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('plot')
    if not template: return {"error": "Could not load plot prompt template."}

    try:
        prompt = format_prompt(template, {'learning_objective': learning_objective, 'character_description': character_description, 'theme': theme})
    except ValueError as e:
         return {"error": str(e)}

    logger.info(f"Plot prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['suggestions'],
            messages=[ {"role": "system", "content": "You are a creative assistant outlining plots."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['plot'], temperature=CONFIG['temperature']['plot'], n=1
        )
        plots_raw = response.choices[0].message.content.strip()
        # Parsing logic
        plot_list = []
        current_plot = ""
        for line in plots_raw.split('\n'):
            stripped_line = line.strip()
            if stripped_line and stripped_line[0].isdigit() and (stripped_line.find('.') > 0 or stripped_line.find(' ') > 0):
                if current_plot: plot_list.append(current_plot.strip())
                first_separator = -1
                for i in range(len(stripped_line)):
                    if not stripped_line[i].isdigit() and stripped_line[i] not in ['.',' ']:
                        break # Stop after number/dot/space
                    if stripped_line[i] in ['.',' ']:
                        first_separator = i
                if first_separator != -1:
                    current_plot = stripped_line[first_separator+1:].strip()
                else: # Fallback for just number? Unlikely based on prompt.
                    current_plot = stripped_line # Keep whole line if parse fails weirdly
            elif current_plot:
                current_plot += " " + stripped_line
        if current_plot: plot_list.append(current_plot.strip())
        if not plot_list and plots_raw: # Fallback
             logger.warning("Could not parse numbered list for plots, using raw split.")
             plot_list = [p.strip() for p in plots_raw.split('\n\n') if p.strip()]
             if len(plot_list) < 2: plot_list = [p.strip() for p in plots_raw.split('\n') if p.strip()]

        logger.info(f"Plot suggestions received: {plot_list}")
        return {"plots": plot_list if plot_list else ["No plot ideas generated."]}
    except Exception as e:
        logger.error(f"Error calling OpenAI for plot suggestions: {e}")
        return {"error": f"Error generating plot ideas: {e}"}


# --- Story Generation (Full Story) ---
def generate_story(child_name, character_name, character_description, plot_choice, learning_objective, theme, personality_keywords):
    """Generates the full story text using OpenAI."""
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('story')
    if not template: return {"error": "Could not load story prompt template."}

    try:
        prompt_data = { 'story_word_count': CONFIG['story']['word_count'], 'child_name': child_name, 'character_name': character_name, 'character_description': character_description, 'plot_choice': plot_choice, 'learning_objective': learning_objective, 'theme': theme, 'personality_keywords_str': ', '.join(personality_keywords) if personality_keywords else 'not specified' }
        prompt = format_prompt(template, prompt_data)
    except ValueError as e:
         return {"error": str(e)}

    logger.info(f"Story generation prompt length: {len(prompt)}")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['story'],
            messages=[ {"role": "system", "content": "You are a warm and imaginative storyteller for young children."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['story'], temperature=CONFIG['temperature']['story'], n=1
        )
        story_text = response.choices[0].message.content.strip()
        logger.info(f"Story generated successfully (length: {len(story_text)} chars).")
        if len(story_text) < 50: logger.warning("Generated story seems very short."); return {"story_text": "The generated story was too short. Please try again.", "warning": "short_story"}
        return {"story_text": story_text}
    except Exception as e:
        logger.error(f"Error calling OpenAI for story generation: {e}")
        return {"error": f"Oops! Error generating the story: {e}"}

# --- Story Sectioning Function ---
def get_story_sections(full_story_text):
    """Divides the full story text into sections using AI."""
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('story_sectioning')
    if not template: return {"error": "Could not load story sectioning prompt template."}

    try: prompt = format_prompt(template, {'full_story_text': full_story_text})
    except ValueError as e: return {"error": str(e)}

    logger.info("Requesting story sectioning from AI...")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['sectioning'],
            messages=[ {"role": "system", "content": "You are a helpful assistant that structures stories into JSON format."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['sectioning'], temperature=CONFIG['temperature']['sectioning'], n=1
        )
        response_text = response.choices[0].message.content.strip()
        logger.debug(f"Raw sectioning response: {response_text}")
        try:
            if response_text.startswith("```json"): response_text = response_text[7:]
            if response_text.endswith("```"): response_text = response_text[:-3]
            response_text = response_text.strip()
            sections = json.loads(response_text)
            if isinstance(sections, list) and all(isinstance(s, str) for s in sections): logger.info(f"Story sectioned into {len(sections)} parts."); return {"sections": sections}
            else: logger.error(f"Sectioning response not valid JSON array of strings: {response_text}"); return {"error": "Failed to parse sections (Invalid format)."}
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed JSON decode for sectioning: {json_err}. Response: {response_text}")
            # Fallback split? Be cautious, might merge sections.
            sections = [s.strip() for s in response_text.split("\n\n") if s.strip()] # Example: Split by double newline
            if len(sections) > 1 and len(response_text) > 100: # Basic sanity check
                logger.warning("Using fallback split for story sections.")
                return {"sections": sections, "warning": "JSON parsing failed, used fallback split"}
            else:
                 return {"error": "Failed to parse sections (JSONDecodeError/No fallback)."}
    except Exception as e: logger.error(f"Error calling OpenAI for story sectioning: {e}"); return {"error": f"Error sectioning story: {e}"}

# --- Image Prompt Creation Function ---
def create_image_prompt_for_section(story_section_text, character_name, character_description):
    """Creates a specific image prompt for a story section using AI."""
    if not is_client_ready(): return {"error": "OpenAI client not ready."}
    template = load_prompt_template('image_prompt_creation')
    if not template: return {"error": "Could not load image prompt creation template."}

    try: prompt = format_prompt(template, { 'story_section_text': story_section_text, 'character_name': character_name, 'character_description': character_description })
    except ValueError as e: return {"error": str(e)}

    logger.info(f"Requesting image prompt creation for section...")
    try:
        response = client.chat.completions.create(
            model=CONFIG['models']['img_prompt'],
            messages=[ {"role": "system", "content": "You extract concise visual prompts from text."}, {"role": "user", "content": prompt} ],
            max_tokens=CONFIG['max_tokens']['img_prompt'], temperature=CONFIG['temperature']['img_prompt'], n=1
        )
        image_prompt_text = response.choices[0].message.content.strip().replace('"', '').replace("CONCISE IMAGE PROMPT:", "").strip()
        logger.info(f"Generated image prompt: {image_prompt_text}")
        if not image_prompt_text: return {"error": "AI failed to generate a non-empty image prompt."}
        return {"image_prompt": image_prompt_text}
    except Exception as e: logger.error(f"Error calling OpenAI for image prompt creation: {e}"); return {"error": f"Error creating image prompt: {e}"}


# --- Image Generation / Editing ---

# Initial Character Image Generation (Used by Background Task)
def generate_image(description):
    """Generates an initial image using DALL-E and returns base64 JSON."""
    if not is_client_ready(): return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}
    style_prompt_template = load_prompt_template('image_style')
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{description}. {style_prompt}".strip()
    logger.info(f"Image generation prompt: {full_prompt}")
    try:
        response = client.images.generate(
            model=CONFIG['models']['image_gen'], 
            prompt=full_prompt, 
            size=CONFIG['image']['size'],
            output_format=CONFIG['image']['output_format'],
            quality=CONFIG['image']['quality'], 
            n=1,
        )
        if response.data and response.data[0].b64_json:
            b64_json_string = response.data[0].b64_json
            revised_prompt = response.data[0].revised_prompt
            logger.info(f"Image generated successfully as base64 JSON.")
            return {"b64_json": b64_json_string, "revised_prompt": revised_prompt}
        else: logger.error("OpenAI image gen response invalid."); return {"error": "Invalid response from image API.", "error_code": "invalid_response"}
    except Exception as e:
        logger.error(f"Error calling OpenAI DALL-E generate: {e}"); error_str = str(e).lower(); error_code = "generic_error"; user_message = f"Failed to generate image: An unexpected error occurred."
        if "content policy" in error_str or "safety system" in error_str: error_code = "content_policy_error"; user_message = "Image generation failed due to content policy."
        elif "billing" in error_str or "quota" in error_str: error_code = "billing_error"; user_message = "Image generation failed due to account limits."
        elif "authentication" in error_str or "api key" in error_str: error_code = "auth_error"; user_message = "Image generation failed due to authentication error."
        elif "invalid_request_error" in error_str: error_code = "invalid_request"; user_message = f"Image generation failed: Invalid request ({e})"
        logger.warning(f"Image generation failed - Code: {error_code}, Message: {e}")
        return {"error": user_message, "error_code": error_code}


# Book Page Image Editing Function
def edit_image_based_on_prompt(base_image_b64, edit_prompt):
    """Edits a base image using a prompt with DALL-E Edit API."""
    if not is_client_ready(): return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}
    if not base_image_b64: return {"error": "Base image data is missing.", "error_code": "missing_base_image"}

    logger.info(f"Requesting image edit with prompt: {edit_prompt}")
    try:
        try:
            image_bytes = base64.b64decode(base_image_b64)
            image_file = io.BytesIO(image_bytes)
            image_file.name = "base_image.png" # Provide a filename
        except Exception as decode_err: logger.error(f"Failed to decode base64 image data: {decode_err}"); return {"error": "Invalid base image data provided.", "error_code": "decode_error"}

        style_prompt_template = load_prompt_template('image_style')
        style_prompt = style_prompt_template.strip() if style_prompt_template else ""
        full_edit_prompt = f"{edit_prompt}. {style_prompt}".strip() # Append style to edit prompt
        logger.info(f"Full edit prompt: {full_edit_prompt}")

        response = client.images.edit(
                model=CONFIG['models']['image_edit'],
                image=image_file,  # Pass the file-like object
                prompt=full_edit_prompt,
                size=CONFIG['image_edit']['size'],
                quality=CONFIG['image_edit']['quality'],
                n=1,
        )
        if response.data and response.data[0].b64_json:
            b64_json_string = response.data[0].b64_json
            logger.info(f"Image edited successfully.")
            return {"b64_json": b64_json_string}
        else: logger.error("OpenAI image edit response invalid."); return {"error": "Invalid response format from image edit API.", "error_code": "invalid_response"}
    except Exception as e:
        logger.error(f"Error calling OpenAI DALL-E edit: {e}"); error_str = str(e).lower(); error_code = "generic_edit_error"; user_message = f"Failed to edit image: An unexpected error occurred."
        # Reuse error code logic from generate_image
        if "content policy" in error_str or "safety system" in error_str: error_code = "content_policy_error"; user_message = "Image editing failed due to content policy."
        elif "billing" in error_str or "quota" in error_str: error_code = "billing_error"; user_message = "Image editing failed due to account limits."
        elif "authentication" in error_str or "api key" in error_str: error_code = "auth_error"; user_message = "Image editing failed due to authentication error."
        elif "invalid_request_error" in error_str: error_code = "invalid_request"; user_message = f"Image editing failed: Invalid request ({e})"
        # DALL-E 2 Edit specific errors?
        elif "image must be square" in error_str: error_code = "image_format_error"; user_message = "Image editing failed: Base image must be square for DALL-E 2 edit."
        elif "mask" in error_str and "same size" in error_str: error_code = "mask_error"; user_message = "Image editing failed: Mask issue." # Simplify message

        logger.warning(f"Image editing failed - Code: {error_code}, Message: {e}")
        return {"error": user_message, "error_code": error_code}