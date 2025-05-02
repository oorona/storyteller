import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import traceback # For detailed error logging

# Imports - Add new service functions
try:
    from openai_service import (
        # Existing suggestion/story funcs...
        get_character_suggestions, get_name_suggestions, get_plot_suggestions, generate_story,
        # Image/Edit funcs...
        generate_image, edit_image_based_on_prompt,
        # New processing funcs...
        get_story_sections, create_image_prompt_for_section,
        # Helper
        is_client_ready
    )
    openai_ready = True
except ImportError as e:
    # ... (Keep dummy function definitions as before, update to return dicts with "error") ...
    logging.error(f"Failed to import from openai_service: {e}. OpenAI features will be disabled.")
    openai_ready = False
    # Define dummy functions if import fails
    def generate_story(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def get_story_sections(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def create_image_prompt_for_section(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def edit_image_based_on_prompt(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    # Add others as needed...

# Logging, Flask App setup, CORS, Health Check... (Keep as before)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='../frontend', static_url_path='/')
CORS(app)
@app.route('/api/health', methods=['GET'])
def health_check(): openai_status = "ready" if openai_ready and is_client_ready() else "unavailable"; return jsonify({"status": "ok", "openai_service": openai_status})

# Existing Suggestion Endpoints & /api/generate_image (for character preview) ...
# ... (Keep suggest_characters, suggest_names, suggest_plots as before, using handle_service_response) ...
# ... (Keep create_image endpoint as before - it's now used for character preview) ...
def handle_service_response(result, success_key):
    if isinstance(result, dict) and "error" in result:
        error_message = result["error"]
        logger.error(f"Service call failed: {error_message}")
        status_code = 500 # Default internal server error
        # Map specific error codes if available
        error_code = result.get("error_code")
        if error_code == "service_unavailable" or "client not ready" in error_message: status_code = 503
        elif error_code == "auth_error" or "Authentication" in error_message: status_code = 401
        elif error_code == "content_policy_error": status_code = 400
        elif error_code == "billing_error": status_code = 402
        elif error_code == "invalid_request": status_code = 400
        elif error_code == "invalid_response" or error_code == "generic_edit_error": status_code = 502 # Bad Gateway / Upstream Error
        elif "template" in error_message: status_code = 500 # Internal config error

        return jsonify({"error": error_message}), status_code
    elif isinstance(result, dict) and success_key in result:
        # Successfully found the expected key
        return jsonify(result), 200
    else:
        # Unexpected format from service function
        logger.error(f"Unexpected response format from service: {result}")
        return jsonify({"error": "An unexpected internal error occurred."}), 500

# --- API Endpoints ---

@app.route('/api/characters/suggest', methods=['POST'])
def suggest_characters():
    if not openai_ready:
        return jsonify({"error": "OpenAI service unavailable."}), 503
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    theme = data.get('theme')
    char_type = data.get('type')
    keywords = data.get('personality_keywords', [])

    if not theme or not char_type:
        logger.warning("Missing theme or type in character suggestion request.")
        return jsonify({"error": "Missing required fields: theme, type"}), 400

    result = get_character_suggestions(theme, char_type, keywords)
    return handle_service_response(result, "suggestions")

@app.route('/api/names/suggest', methods=['POST'])
def suggest_names():
    if not openai_ready:
        return jsonify({"error": "OpenAI service unavailable."}), 503
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    desc = data.get('character_description')
    theme = data.get('theme')

    if not desc or not theme:
        logger.warning("Missing character_description or theme in name suggestion request.")
        return jsonify({"error": "Missing required fields: character_description, theme"}), 400

    result = get_name_suggestions(desc, theme)
    return handle_service_response(result, "names")

@app.route('/api/plot/suggest', methods=['POST'])
def suggest_plots():
    if not openai_ready:
        return jsonify({"error": "OpenAI service unavailable."}), 503
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    obj = data.get('learning_objective')
    desc = data.get('character_description')
    theme = data.get('theme')

    if not obj or not desc or not theme:
        logger.warning("Missing fields in plot suggestion request.")
        return jsonify({"error": "Missing required fields: learning_objective, character_description, theme"}), 400

    result = get_plot_suggestions(obj, desc, theme)
    return handle_service_response(result, "plots")

# This endpoint is used for the Character Preview image generation
@app.route('/api/image/generate', methods=['POST'])
def create_image():
    if not openai_ready:
        return jsonify({"error": "OpenAI service unavailable."}), 503
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    description = data.get('description')
    if not description:
        logger.warning("Missing description for image generation.")
        return jsonify({"error": "Missing required field: description"}), 400

    image_result = generate_image(description)
    # Use handle_service_response, expecting "b64_json" on success
    return handle_service_response(image_result, "b64_json")

# --- NEW Endpoint for Book Generation ---
@app.route('/api/book/generate', methods=['POST'])
def create_book():
    if not openai_ready:
        return jsonify({"error": "OpenAI service is not available."}), 503

    data = request.json
    # ... (Input extraction and validation remain the same) ...
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    required_fields = ['child_name', 'character_name', 'character_description', 'plot_choice', 'learning_objective', 'theme', 'character_image_b64']
    missing_fields = [field for field in required_fields if not data.get(field)];
    if missing_fields: return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
    child_name = data['child_name']; character_name = data['character_name']; character_description = data['character_description'];
    plot_choice = data['plot_choice']; learning_objective = data['learning_objective']; theme = data['theme'];
    personality_keywords = data.get('personality_keywords', []); character_image_b64 = data['character_image_b64'];

    book_pages = []

    try:
        # --- Generate Full Story ---
        logger.info("Step 1/4: Generating full story...")
        story_result = generate_story(child_name, character_name, character_description, plot_choice, learning_objective, theme, personality_keywords)
        if "error" in story_result: raise Exception(f"Story generation failed: {story_result['error']}")
        full_story_text = story_result["story_text"]
        logger.info("Step 1/4: Full story generated.")

        # --- Section Story ---
        logger.info("Step 2/4: Sectioning story...")
        section_result = get_story_sections(full_story_text)
        if "error" in section_result: raise Exception(f"Story sectioning failed: {section_result['error']}")
        story_sections = section_result["sections"]
        logger.info(f"Step 2/4: Story sectioned into {len(story_sections)} parts.")

        # --- Process Each Section ---
        logger.info("Step 3/4: Generating prompts and images for sections...")
        for i, section_text in enumerate(story_sections):
            logger.info(f"Processing section {i+1}/{len(story_sections)}...")
            # Create Image Prompt
            img_prompt_result = create_image_prompt_for_section(section_text, character_name, character_description)
            if "error" in img_prompt_result: raise Exception(f"Image prompt creation failed for section {i+1}: {img_prompt_result['error']}")
            section_image_prompt = img_prompt_result["image_prompt"]
            # Edit Base Image
            edited_image_result = edit_image_based_on_prompt(character_image_b64, section_image_prompt)
            if "error" in edited_image_result: raise Exception(f"Image editing failed for section {i+1}: {edited_image_result['error']}")
            section_image_b64 = edited_image_result["b64_json"] # Value is correctly extracted

            # *** CORRECTED KEY used when building the final response ***
            book_pages.append({
                "text": section_text,
                "b64_json": section_image_b64 # Use consistent key "b64_json"
            })
            logger.info(f"Section {i+1} processing complete.")

        logger.info("Step 3/4: All sections processed.")
        logger.info("Step 4/4: Book generation successful.")
        # --- Return Result ---
        return jsonify({"pages": book_pages}), 200

    except Exception as e:
        logger.error(f"Error during book generation process: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": f"Book generation failed: An internal error occurred."}), 500 # Keep error generic for user


# Static File Serving & Main Execution (remain the same)
# ... (Keep index route and if __name__ == '__main__': block) ...
@app.route('/')
def index(): logger.info(f"Serving index.html from {app.static_folder}"); return send_from_directory(app.static_folder, 'index.html')
if __name__ == '__main__': port = int(os.environ.get('PORT', 5001)); debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'; logger.info(f"Starting Flask server on {port} debug={debug_mode}"); app.run(host='0.0.0.0', port=port, debug=debug_mode)