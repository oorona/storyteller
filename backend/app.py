import os
import re
import io
import base64
import json
import logging
import traceback
import threading
from datetime import datetime
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS

from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from provider_service import (
    create_image_prompt_for_section_with_characters,
    create_image_prompt_for_section,
    edit_image_based_on_prompt,
    extract_child_profile,
    generate_image,
    generate_image_with_references,
    generate_story,
    get_character_suggestions,
    get_default_provider,
    get_main_story_characters,
    get_name_suggestions,
    get_plot_suggestions_from_cast,
    get_plot_suggestions,
    get_provider_health,
    get_settings_options,
    get_story_sections,
    identify_section_characters,
    is_provider_ready,
    normalize_provider,
    prepare_story_cast,
    sanitize_runtime_settings,
    validate_book_match,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)


def parse_provider_context(data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    provider = normalize_provider(data.get("provider") if isinstance(data, dict) else None)
    settings = data.get("settings", {}) if isinstance(data, dict) else {}
    runtime_settings = sanitize_runtime_settings(provider, settings)
    return provider, runtime_settings


def handle_service_response(result: Dict[str, Any], success_key: str):
    if isinstance(result, dict) and "error" in result:
        error_message = result["error"]
        status_code = 500

        error_code = result.get("error_code")
        if error_code in {"service_unavailable"} or "client not ready" in error_message.lower():
            status_code = 503
        elif error_code in {"auth_error"} or "authentication" in error_message.lower():
            status_code = 401
        elif error_code in {"content_policy_error"}:
            status_code = 400
        elif error_code in {"billing_error"}:
            status_code = 402
        elif error_code in {"invalid_request", "invalid_provider"}:
            status_code = 400
        elif error_code in {"invalid_response", "generic_edit_error"}:
            status_code = 502
        elif "template" in error_message.lower():
            status_code = 500

        logger.error(f"Service call failed [{status_code}]: {error_message}")
        return jsonify({"error": error_message}), status_code

    if isinstance(result, dict) and success_key in result:
        return jsonify(result), 200

    logger.error(f"Unexpected response format from service: {result}")
    return jsonify({"error": "An unexpected internal error occurred."}), 500


_CHARACTER_NAME_STOPWORDS = {"the", "a", "an"}


def _character_name_keys(name: str) -> set[str]:
    original_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", name or "")]
    if not original_tokens:
        return set()

    tokens = list(original_tokens)
    while tokens and tokens[-1] in _CHARACTER_NAME_STOPWORDS:
        tokens.pop()
    if not tokens:
        return set()

    keys = {" ".join(tokens)}
    if len(original_tokens) >= 2 and original_tokens[1] in _CHARACTER_NAME_STOPWORDS:
        keys.add(original_tokens[0])
    return {key for key in keys if key}


def normalize_story_characters(raw_value: Any):
    if not isinstance(raw_value, list):
        return []

    normalized: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in raw_value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not name or not description:
            continue
        name_keys = _character_name_keys(name)
        if not name_keys:
            continue
        if any(key in seen_keys for key in name_keys):
            continue
        seen_keys.update(name_keys)
        normalized.append(
            {
                "name": name,
                "description": description,
                "is_child": bool(item.get("is_child", False)),
                "image_b64": str(item.get("image_b64", "")).strip(),
                "mime_type": str(item.get("mime_type", "image/png")).strip() or "image/png",
            }
        )
    return normalized


def _safe_filename(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip())
    sanitized = sanitized.strip("_")
    if not sanitized:
        sanitized = "story_book"
    return sanitized[:80]


def _draw_wrapped_text(
    pdf_canvas: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font_name: str = "Helvetica",
    font_size: int = 12,
    line_height: float = 15.0,
) -> float:
    pdf_canvas.setFont(font_name, font_size)
    remaining_y = y

    paragraphs = (text or "").splitlines() or [""]
    for paragraph in paragraphs:
        words = paragraph.split()
        if not words:
            remaining_y -= line_height
            continue

        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if pdf_canvas.stringWidth(candidate, font_name, font_size) <= max_width:
                line = candidate
                continue

            if line:
                pdf_canvas.drawString(x, remaining_y, line)
                remaining_y -= line_height
            line = word

        if line:
            pdf_canvas.drawString(x, remaining_y, line)
            remaining_y -= line_height

        remaining_y -= 3

    return remaining_y


def _render_page_image(
    pdf_canvas: canvas.Canvas,
    page: Dict[str, Any],
    image_x: float,
    image_y: float,
    image_box_width: float,
    image_box_height: float,
) -> None:
    b64_json = page.get("b64_json")
    if not b64_json:
        pdf_canvas.setStrokeColorRGB(0.8, 0.8, 0.8)
        pdf_canvas.rect(image_x, image_y, image_box_width, image_box_height, stroke=1, fill=0)
        pdf_canvas.setFont("Helvetica-Oblique", 11)
        pdf_canvas.drawCentredString(
            image_x + image_box_width / 2.0,
            image_y + image_box_height / 2.0,
            "No image available for this page.",
        )
        return

    try:
        raw_bytes = base64.b64decode(b64_json)
        image = Image.open(io.BytesIO(raw_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        img_width, img_height = image.size
        if img_width <= 0 or img_height <= 0:
            raise ValueError("Invalid image dimensions")

        scale = min(image_box_width / img_width, image_box_height / img_height)
        draw_width = img_width * scale
        draw_height = img_height * scale
        draw_x = image_x + (image_box_width - draw_width) / 2.0
        draw_y = image_y + (image_box_height - draw_height) / 2.0

        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")
        png_buffer.seek(0)

        pdf_canvas.drawImage(
            ImageReader(png_buffer),
            draw_x,
            draw_y,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )
    except Exception as exc:
        logger.warning(f"Failed to render page image in PDF: {exc}")
        pdf_canvas.setStrokeColorRGB(0.85, 0.5, 0.5)
        pdf_canvas.rect(image_x, image_y, image_box_width, image_box_height, stroke=1, fill=0)
        pdf_canvas.setFont("Helvetica-Oblique", 11)
        pdf_canvas.drawCentredString(
            image_x + image_box_width / 2.0,
            image_y + image_box_height / 2.0,
            "Image could not be embedded in PDF.",
        )


@app.route("/api/health", methods=["GET"])
def health_check():
    provider_health = get_provider_health()
    return jsonify(
        {
            "status": "ok",
            "default_provider": get_default_provider(),
            "providers": provider_health,
        }
    )


@app.route("/api/settings/options", methods=["GET"])
def settings_options():
    return jsonify(get_settings_options())


@app.route("/api/profile/extract", methods=["POST"])
def extract_profile():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    profile_text = str(data.get("profile_text", "")).strip()
    if not profile_text:
        return jsonify({"error": "Missing required field: profile_text"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    logger.info(
        "Profile extraction request received [provider=%s, profile_text_chars=%s]",
        provider,
        len(profile_text),
    )
    result = extract_child_profile(provider, profile_text, runtime_settings=runtime_settings)
    if isinstance(result, dict) and "error" in result:
        return handle_service_response(result, "child_name")

    required_keys = [
        "child_name",
        "learning_objective",
        "personality_keywords",
        "story_theme_suggestions",
        "character_suggestions",
    ]
    if not isinstance(result, dict) or not all(key in result for key in required_keys):
        logger.error(f"Invalid structured profile response: {result}")
        return jsonify({"error": "Failed to extract structured child profile."}), 502

    logger.info(
        "Profile extraction response [provider=%s]: %s",
        provider,
        json.dumps(result, ensure_ascii=False),
    )
    return jsonify(result), 200


@app.route("/api/characters/suggest", methods=["POST"])
def suggest_characters():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    theme = data.get("theme")
    char_type = data.get("type")
    keywords = data.get("personality_keywords", [])

    if not theme or not char_type:
        return jsonify({"error": "Missing required fields: theme, type"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = get_character_suggestions(
        provider,
        theme,
        char_type,
        keywords,
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "suggestions")


@app.route("/api/names/suggest", methods=["POST"])
def suggest_names():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    desc = data.get("character_description")
    theme = data.get("theme")

    if not desc or not theme:
        return jsonify({"error": "Missing required fields: character_description, theme"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = get_name_suggestions(
        provider,
        desc,
        theme,
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "names")


@app.route("/api/plot/suggest", methods=["POST"])
def suggest_plots():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    obj = data.get("learning_objective")
    desc = data.get("character_description")
    theme = data.get("theme")

    if not obj or not desc or not theme:
        return jsonify(
            {
                "error": "Missing required fields: learning_objective, character_description, theme"
            }
        ), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = get_plot_suggestions(
        provider,
        obj,
        desc,
        theme,
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "plots")


@app.route("/api/plot/suggest-from-cast", methods=["POST"])
def suggest_plots_from_cast():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    learning_objective = data.get("learning_objective")
    theme = data.get("theme")
    story_characters = normalize_story_characters(data.get("story_characters"))

    if not learning_objective or not theme:
        return jsonify({"error": "Missing required fields: learning_objective, theme"}), 400
    if len(story_characters) < 2:
        return jsonify({"error": "At least 2 story_characters are required."}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = get_plot_suggestions_from_cast(
        provider,
        learning_objective,
        theme,
        story_characters,
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "plots")


@app.route("/api/story/cast/prepare", methods=["POST"])
def prepare_cast():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    child_name = str(data.get("child_name", "")).strip()
    child_profile_text = str(data.get("child_profile_text", "")).strip()
    learning_objective = str(data.get("learning_objective", "")).strip()
    theme = str(data.get("theme", "")).strip()
    personality_keywords = data.get("personality_keywords", [])
    selected_character_ideas = data.get("selected_character_ideas", [])

    if not learning_objective or not theme:
        return jsonify({"error": "Missing required fields: learning_objective, theme"}), 400
    if not isinstance(selected_character_ideas, list) or len(selected_character_ideas) == 0:
        return jsonify({"error": "Missing required field: selected_character_ideas"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = prepare_story_cast(
        provider,
        child_name,
        child_profile_text,
        learning_objective,
        theme,
        personality_keywords if isinstance(personality_keywords, list) else [],
        selected_character_ideas,
        runtime_settings=runtime_settings,
    )

    if isinstance(result, dict) and "error" in result:
        return handle_service_response(result, "story_characters")

    story_characters = normalize_story_characters((result or {}).get("story_characters", []))
    child_character = (result or {}).get("child_character", {})
    if len(story_characters) < 2:
        return jsonify({"error": "Cast preparation returned less than 2 characters."}), 502
    if not isinstance(child_character, dict):
        child_character = {}

    return jsonify({"child_character": child_character, "story_characters": story_characters}), 200


@app.route("/api/story/main-characters", methods=["POST"])
def suggest_main_story_characters():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    child_name = data.get("child_name")
    character_name = data.get("character_name")
    character_description = data.get("character_description")
    plot_choice = data.get("plot_choice")
    learning_objective = data.get("learning_objective")
    theme = data.get("theme")

    required = [
        ("child_name", child_name),
        ("character_name", character_name),
        ("character_description", character_description),
        ("plot_choice", plot_choice),
        ("learning_objective", learning_objective),
        ("theme", theme),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = get_main_story_characters(
        provider,
        child_name,
        character_name,
        character_description,
        plot_choice,
        learning_objective,
        theme,
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "main_characters")


@app.route("/api/image/generate", methods=["POST"])
def create_image():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    description = data.get("description")
    if not description:
        return jsonify({"error": "Missing required field: description"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    image_result = generate_image(provider, description, runtime_settings=runtime_settings)
    return handle_service_response(image_result, "b64_json")


def process_section_thread(
    section_index: int,
    section_text: str,
    theme: str,
    story_characters,
    provider: str,
    runtime_settings: Dict[str, Any],
    results_list,
):
    generation_trace: Dict[str, Any] = {
        "segment_index": section_index,
        "segment_text": section_text,
    }
    try:
        logger.info(f"Thread-{section_index + 1}: Identifying section characters...")
        section_chars_result = identify_section_characters(
            provider,
            section_text,
            story_characters,
            runtime_settings=runtime_settings,
        )
        if "error" in section_chars_result:
            raise Exception(f"Section character identification failed: {section_chars_result['error']}")

        involved_names = section_chars_result.get("character_names", [])
        generation_trace["detected_character_names"] = involved_names

        character_lookup: Dict[str, Dict[str, Any]] = {}
        for character in story_characters:
            char_name = str(character.get("name", "")).strip()
            if not char_name:
                continue
            for key in _character_name_keys(char_name):
                character_lookup.setdefault(key, character)

        involved_characters = []
        matched_names_seen: set[str] = set()
        for detected_name in involved_names:
            for key in _character_name_keys(str(detected_name).strip()):
                candidate = character_lookup.get(key)
                if not candidate:
                    continue
                candidate_name = str(candidate.get("name", "")).strip()
                if not candidate_name or candidate_name.lower() in matched_names_seen:
                    continue
                involved_characters.append(candidate)
                matched_names_seen.add(candidate_name.lower())
                break

        if not involved_characters and story_characters:
            involved_characters = story_characters[:2]
        generation_trace["matched_character_names"] = [
            str(character.get("name", "")).strip() for character in involved_characters
        ]

        logger.info(f"Thread-{section_index + 1}: Creating character-aware image prompt...")
        img_prompt_result = create_image_prompt_for_section_with_characters(
            provider,
            section_text,
            theme,
            involved_characters,
            runtime_settings=runtime_settings,
        )
        if "error" in img_prompt_result:
            raise Exception(f"Image prompt creation failed: {img_prompt_result['error']}")

        section_image_prompt = img_prompt_result["image_prompt"]
        generation_trace["image_prompt"] = section_image_prompt
        reference_images = [
            {
                "name": character.get("name", ""),
                "b64_json": character.get("image_b64", ""),
                "mime_type": character.get("mime_type", "image/png"),
            }
            for character in involved_characters
            if character.get("image_b64")
        ]
        generation_trace["reference_character_names"] = [ref.get("name", "") for ref in reference_images]

        logger.info(f"Thread-{section_index + 1}: Generating section image with references...")
        image_result = generate_image_with_references(
            provider,
            section_image_prompt,
            reference_images,
            runtime_settings=runtime_settings,
        )
        if "error" in image_result:
            raise Exception(f"Image generation failed: {image_result['error']}")
        revised_prompt = str(image_result.get("revised_prompt", "")).strip()
        if revised_prompt:
            generation_trace["image_revised_prompt"] = revised_prompt

        results_list[section_index] = {
            "text": section_text,
            "segment_index": section_index,
            "segment_text": section_text,
            "b64_json": image_result["b64_json"],
            "mime_type": image_result.get("mime_type", "image/png"),
            "characters": [character.get("name", "") for character in involved_characters],
            "detected_character_names": involved_names,
            "image_prompt": section_image_prompt,
            "reference_character_names": [ref.get("name", "") for ref in reference_images],
            "generation_trace": generation_trace,
        }
    except Exception as exc:
        logger.error(f"Thread-{section_index + 1}: Error processing section: {exc}")
        results_list[section_index] = {
            "text": section_text,
            "segment_index": section_index,
            "segment_text": section_text,
            "b64_json": None,
            "error": str(exc),
            "generation_trace": generation_trace,
        }


@app.route("/api/book/generate", methods=["POST"])
def create_book():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    required_fields = [
        "child_name",
        "plot_choice",
        "learning_objective",
        "theme",
    ]
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    child_name = str(data["child_name"]).strip()
    plot_choice = str(data["plot_choice"]).strip()
    learning_objective = str(data["learning_objective"]).strip()
    theme = str(data["theme"]).strip()
    personality_keywords = data.get("personality_keywords", [])
    story_characters = normalize_story_characters(data.get("story_characters"))

    # Backward compatibility for older single-character payloads.
    if not story_characters:
        legacy_name = str(data.get("character_name", "")).strip()
        legacy_description = str(data.get("character_description", "")).strip()
        legacy_image = str(data.get("character_image_b64", "")).strip()
        if legacy_name and legacy_description:
            story_characters = [
                {
                    "name": legacy_name,
                    "description": legacy_description,
                    "is_child": True,
                    "image_b64": legacy_image,
                    "mime_type": "image/png",
                }
            ]

    if len(story_characters) < 2:
        return jsonify({"error": "At least 2 story_characters are required to generate the book."}), 400

    main_character = story_characters[0]
    character_name = main_character["name"]
    character_description = "; ".join(
        f"{character['name']}: {character['description']}" for character in story_characters
    )

    try:
        logger.info("Step 1/4: Generating full story...")
        story_result = generate_story(
            provider,
            child_name,
            character_name,
            character_description,
            plot_choice,
            learning_objective,
            theme,
            personality_keywords,
            runtime_settings=runtime_settings,
        )
        if "error" in story_result:
            raise Exception(f"Story generation failed: {story_result['error']}")

        full_story_text = story_result["story_text"]

        logger.info("Step 2/4: Sectioning story...")
        section_result = get_story_sections(
            provider,
            full_story_text,
            runtime_settings=runtime_settings,
        )
        if "error" in section_result:
            raise Exception(f"Story sectioning failed: {section_result['error']}")

        story_sections = section_result["sections"]

        logger.info("Step 3/4: Starting parallel generation of prompts and images...")
        threads = []
        section_results = [None] * len(story_sections)

        for index, section_text in enumerate(story_sections):
            thread = threading.Thread(
                target=process_section_thread,
                args=(
                    index,
                    section_text,
                    theme,
                    story_characters,
                    provider,
                    runtime_settings,
                    section_results,
                ),
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        book_pages = []
        encountered_error = False

        for index, result in enumerate(section_results):
            if result is None:
                encountered_error = True
                book_pages.append(
                    {
                        "text": story_sections[index],
                        "segment_index": index,
                        "segment_text": story_sections[index],
                        "error": "Processing failed unexpectedly.",
                        "b64_json": None,
                    }
                )
            elif "error" in result:
                encountered_error = True
                error_page = {
                    "text": result.get("text", story_sections[index]),
                    "segment_index": result.get("segment_index", index),
                    "segment_text": result.get("segment_text", story_sections[index]),
                    "error": result["error"],
                    "b64_json": None,
                }
                for key in (
                    "characters",
                    "detected_character_names",
                    "image_prompt",
                    "reference_character_names",
                    "generation_trace",
                ):
                    if key in result:
                        error_page[key] = result[key]
                book_pages.append(error_page)
            else:
                book_pages.append(result)

        if encountered_error:
            return jsonify(
                {
                    "pages": book_pages,
                    "warning": "Some pages encountered errors during image generation.",
                }
            ), 200

        return jsonify({"pages": book_pages}), 200

    except Exception as exc:
        logger.error(f"Error during book generation: {exc}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Book generation failed: An internal error occurred."}), 500


@app.route("/api/validate/book-match", methods=["POST"])
def validate_book_plot_match():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = [
        "child_name",
        "learning_objective",
        "theme",
        "selected_plot",
        "story_characters",
        "pages",
    ]
    missing = [field for field in required_fields if not data.get(field)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    provider, runtime_settings = parse_provider_context(data)
    if not is_provider_ready(provider):
        return jsonify({"error": f"Provider '{provider}' is not available."}), 503

    result = validate_book_match(
        provider,
        str(data.get("child_name", "")).strip(),
        str(data.get("learning_objective", "")).strip(),
        str(data.get("theme", "")).strip(),
        str(data.get("selected_plot", "")).strip(),
        normalize_story_characters(data.get("story_characters")),
        data.get("pages", []),
        runtime_settings=runtime_settings,
    )
    return handle_service_response(result, "recommendation")


@app.route("/api/book/pdf", methods=["POST"])
def download_book_pdf():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    pages = data.get("pages")
    if not isinstance(pages, list) or len(pages) == 0:
        return jsonify({"error": "Missing required field: pages"}), 400

    child_name = str(data.get("child_name", "")).strip()
    file_base = _safe_filename(child_name) if child_name else "story_book"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    download_name = f"{file_base}_{timestamp}.pdf"

    pdf_buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(pdf_buffer, pagesize=letter)
    page_width, page_height = letter

    margin = 36
    header_gap = 24
    image_box_height = 360
    image_box_width = page_width - (margin * 2)
    image_box_x = margin
    image_box_y = page_height - margin - header_gap - image_box_height

    text_start_y = image_box_y - 20
    text_width = page_width - (margin * 2)

    for index, page in enumerate(pages):
        page_text = str(page.get("text", "")).strip()
        page_title = f"Page {index + 1} of {len(pages)}"

        pdf_canvas.setFont("Helvetica-Bold", 14)
        pdf_canvas.drawString(margin, page_height - margin, page_title)

        _render_page_image(
            pdf_canvas,
            page,
            image_box_x,
            image_box_y,
            image_box_width,
            image_box_height,
        )

        _draw_wrapped_text(
            pdf_canvas,
            page_text if page_text else "No text available for this page.",
            margin,
            text_start_y,
            text_width,
            font_name="Helvetica",
            font_size=11,
            line_height=14,
        )

        if index < len(pages) - 1:
            pdf_canvas.showPage()

    pdf_canvas.save()
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )


@app.route("/")
def index():
    logger.info(f"Serving index.html from {app.static_folder}")
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    logger.info(f"Starting Flask server on {port} debug={debug_mode}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
