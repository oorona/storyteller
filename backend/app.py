import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

# Imports remain the same
try:
    from openai_service import (
        get_character_suggestions,
        get_name_suggestions,
        get_plot_suggestions,
        generate_story,
        generate_image,
        is_client_ready
    )
    openai_ready = True
except ImportError as e:
    logging.error(f"Failed to import from openai_service: {e}. OpenAI features will be disabled.")
    openai_ready = False
    # Define dummy functions to return error dicts
    def get_character_suggestions(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def get_name_suggestions(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def get_plot_suggestions(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def generate_story(*args, **kwargs): return {"error": "OpenAI service unavailable."}
    def generate_image(*args, **kwargs): return {"error": "OpenAI service unavailable.", "error_code": "service_unavailable"}
    def is_client_ready(): return False

# Logging and Flask setup remain the same
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
app = Flask(__name__, static_folder='../frontend', static_url_path='/')
CORS(app)

# Health check remains the same
@app.route('/api/health', methods=['GET'])
def health_check():
    openai_status = "ready" if openai_ready and is_client_ready() else "not configured or unavailable"
    return jsonify({"status": "ok", "openai_service": openai_status})


# --- API Endpoints (Updated to handle dict responses) ---

def handle_service_response(result, success_key):
    """Helper function to process dict responses from the service layer."""
    if isinstance(result, dict) and "error" in result:
        error_message = result["error"]
        # Log the detailed error server-side
        logger.error(f"Service call failed: {error_message}")
        # Determine appropriate status code (optional refinement)
        status_code = 500 # Default internal server error
        if "client not ready" in error_message or "unavailable" in error_message:
            status_code = 503
        elif "template" in error_message: # Config error
             status_code = 500
        elif "Authentication" in error_message:
            status_code = 401
        # Return only the error message part to the client
        return jsonify({"error": error_message}), status_code
    elif isinstance(result, dict) and success_key in result:
        return jsonify(result), 200 # Return the whole dict {success_key: data}
    else:
        # Unexpected format
        logger.error(f"Unexpected response format from service: {result}")
        return jsonify({"error": "An unexpected internal error occurred."}), 500


@app.route('/api/characters/suggest', methods=['POST'])
def suggest_characters():
    if not openai_ready: return jsonify({"error": "OpenAI service is not available."}), 503
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    # Basic input validation
    theme = data.get('theme'); char_type = data.get('type'); personality_keywords = data.get('personality_keywords', [])
    if not theme or not char_type: return jsonify({"error": "Missing required fields: theme, type"}), 400

    result = get_character_suggestions(theme, char_type, personality_keywords)
    return handle_service_response(result, "suggestions")


@app.route('/api/names/suggest', methods=['POST'])
def suggest_names():
    if not openai_ready: return jsonify({"error": "OpenAI service not available."}), 503
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    character_description = data.get('character_description'); theme = data.get('theme')
    if not character_description or not theme: return jsonify({"error": "Missing required fields: character_description, theme"}), 400

    result = get_name_suggestions(character_description, theme)
    return handle_service_response(result, "names")


@app.route('/api/plot/suggest', methods=['POST'])
def suggest_plots():
    if not openai_ready: return jsonify({"error": "OpenAI service not available."}), 503
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    learning_objective = data.get('learning_objective'); character_description = data.get('character_description'); theme = data.get('theme')
    if not learning_objective or not character_description or not theme: return jsonify({"error": "Missing required fields: learning_objective, character_description, theme"}), 400

    result = get_plot_suggestions(learning_objective, character_description, theme)
    return handle_service_response(result, "plots")


@app.route('/api/story/generate', methods=['POST'])
def create_story():
    if not openai_ready: return jsonify({"error": "OpenAI service not available."}), 503
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    required_fields = ['child_name', 'character_name', 'character_description', 'plot_choice', 'learning_objective', 'theme']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields: return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    result = generate_story(
        data['child_name'], data['character_name'], data['character_description'], data['plot_choice'],
        data['learning_objective'], data['theme'], data.get('personality_keywords', [])
    )
    return handle_service_response(result, "story_text")


@app.route('/api/image/generate', methods=['POST'])
def create_image():
    if not openai_ready: return jsonify({"error": "OpenAI service not available."}), 503
    data = request.json
    if not data: return jsonify({"error": "Invalid JSON payload"}), 400
    description = data.get('description')
    if not description: return jsonify({"error": "Missing required field: description"}), 400

    image_result = generate_image(description) # Service now returns dict

    if isinstance(image_result, dict) and "error" in image_result:
        error_message = image_result["error"]
        error_code = image_result.get("error_code", "generic_error")
        status_code = 500 # Default
        # Map specific error codes (as done in the service, but re-checked here for status)
        if error_code == "content_policy_error": status_code = 400
        elif error_code == "billing_error": status_code = 402
        elif error_code == "auth_error": status_code = 401
        elif error_code == "service_unavailable": status_code = 503
        elif error_code == "invalid_request": status_code = 400
        elif error_code == "invalid_response": status_code = 502 # Bad Gateway (API returned unexpected)

        logger.warning(f"Image generation failed: {error_message} (Code: {error_code})")
        return jsonify({"error": error_message}), status_code # Return only the user-friendly message
    elif isinstance(image_result, dict) and "b64_json" in image_result:
        # Success: Return the base64 string and optionally the revised prompt
        response_data = {"image_b64_json": image_result["b64_json"]}
        if "revised_prompt" in image_result:
            response_data["revised_prompt"] = image_result["revised_prompt"]
        return jsonify(response_data), 200
    else:
        logger.error(f"Unexpected response format from generate_image service: {image_result}")
        return jsonify({"error": "Failed to generate image due to an unexpected internal error."}), 500


# Static File Serving & Main Execution remain the same
@app.route('/')
def index():
    logger.info(f"Serving index.html from {app.static_folder}")
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    logger.info(f"Starting Flask server on port {port} with debug mode: {debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)