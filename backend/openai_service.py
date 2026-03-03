import base64
import io
import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from profile_extraction_utils import (
    fallback_profile_from_text,
    load_json_config_file,
    normalize_child_profile,
    persist_profile_extraction,
)
from secret_utils import read_secret


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

CONFIG = {
    "api_key": read_secret(
        "OPENAI_API_KEY",
        "OPENAI_API_KEY_FILE",
        "/run/secrets/openai_api_key",
    ),
    "prompt_files": {
        "character": os.getenv("PROMPT_FILE_CHARACTER", "prompts/character_suggestions.txt"),
        "name": os.getenv("PROMPT_FILE_NAME", "prompts/name_suggestions.txt"),
        "plot": os.getenv("PROMPT_FILE_PLOT", "prompts/plot_suggestions.txt"),
        "story": os.getenv("PROMPT_FILE_STORY", "prompts/story_generation.txt"),
        "image_style": os.getenv("PROMPT_FILE_IMAGE_STYLE", "prompts/image_style.txt"),
        "story_sectioning": os.getenv("PROMPT_FILE_STORY_SECTIONING", "prompts/story_sectioning_prompt.txt"),
        "image_prompt_creation": os.getenv(
            "PROMPT_FILE_IMAGE_PROMPT_CREATION",
            "prompts/image_prompt_creation_prompt.txt",
        ),
        "child_profile_extraction": os.getenv(
            "PROMPT_FILE_CHILD_PROFILE_EXTRACTION",
            "prompts/child_profile_extraction_prompt.txt",
        ),
        "main_story_characters": os.getenv(
            "PROMPT_FILE_MAIN_STORY_CHARACTERS",
            "prompts/main_story_characters.txt",
        ),
        "story_cast_preparation": os.getenv(
            "PROMPT_FILE_STORY_CAST_PREPARATION",
            "prompts/story_cast_preparation.txt",
        ),
        "plot_from_cast": os.getenv(
            "PROMPT_FILE_PLOT_FROM_CAST",
            "prompts/plot_suggestions_from_cast.txt",
        ),
        "section_characters": os.getenv(
            "PROMPT_FILE_SECTION_CHARACTERS",
            "prompts/section_characters_from_page.txt",
        ),
        "image_prompt_with_characters": os.getenv(
            "PROMPT_FILE_IMAGE_PROMPT_WITH_CHARACTERS",
            "prompts/image_prompt_with_characters.txt",
        ),
        "book_match_validation": os.getenv(
            "PROMPT_FILE_BOOK_MATCH_VALIDATION",
            "prompts/book_match_validation.txt",
        ),
    },
    "schema_files": {
        "child_profile_extraction": os.getenv(
            "SCHEMA_FILE_CHILD_PROFILE_EXTRACTION",
            "schemas/child_profile_extraction_schema.json",
        ),
        "character_suggestions": os.getenv(
            "SCHEMA_FILE_CHARACTER_SUGGESTIONS",
            "schemas/character_suggestions_schema.json",
        ),
        "name_suggestions": os.getenv(
            "SCHEMA_FILE_NAME_SUGGESTIONS",
            "schemas/name_suggestions_schema.json",
        ),
        "plot_suggestions": os.getenv(
            "SCHEMA_FILE_PLOT_SUGGESTIONS",
            "schemas/plot_suggestions_schema.json",
        ),
        "story_text": os.getenv(
            "SCHEMA_FILE_STORY_TEXT",
            "schemas/story_text_schema.json",
        ),
        "story_sections": os.getenv(
            "SCHEMA_FILE_STORY_SECTIONS",
            "schemas/story_sections_schema.json",
        ),
        "image_prompt": os.getenv(
            "SCHEMA_FILE_IMAGE_PROMPT",
            "schemas/image_prompt_schema.json",
        ),
        "main_story_characters": os.getenv(
            "SCHEMA_FILE_MAIN_STORY_CHARACTERS",
            "schemas/main_story_characters_schema.json",
        ),
        "story_cast": os.getenv(
            "SCHEMA_FILE_STORY_CAST",
            "schemas/story_cast_schema.json",
        ),
        "page_characters": os.getenv(
            "SCHEMA_FILE_PAGE_CHARACTERS",
            "schemas/page_characters_schema.json",
        ),
        "book_match_validation": os.getenv(
            "SCHEMA_FILE_BOOK_MATCH_VALIDATION",
            "schemas/book_match_validation_schema.json",
        ),
    },
    "models": {
        "suggestions": os.getenv("TEXT_MODEL_SUGGESTIONS", "gpt-4.1-nano"),
        "story": os.getenv("TEXT_MODEL_STORY", "gpt-4.1-mini"),
        "sectioning": os.getenv("TEXT_MODEL_SECTIONING", "gpt-4.1-nano"),
        "img_prompt": os.getenv("TEXT_MODEL_IMG_PROMPT", "gpt-4.1-nano"),
        "image_gen": os.getenv("IMAGE_MODEL", "gpt-image-1"),
        "image_edit": os.getenv("IMAGE_EDIT_MODEL", "gpt-image-1"),
    },
    "max_tokens": {
        "character": int(os.getenv("MAX_TOKENS_CHARACTER", 240)),
        "name": int(os.getenv("MAX_TOKENS_NAME", 180)),
        "plot": int(os.getenv("MAX_TOKENS_PLOT", 650)),
        "story": int(os.getenv("MAX_TOKENS_STORY", 1000)),
        "sectioning": int(os.getenv("MAX_TOKENS_SECTIONING", 1000)),
        "img_prompt": int(os.getenv("MAX_TOKENS_IMG_PROMPT", 120)),
        "main_story_characters": int(os.getenv("MAX_TOKENS_MAIN_STORY_CHARACTERS", 240)),
        "story_cast": int(os.getenv("MAX_TOKENS_STORY_CAST", 500)),
        "plot_from_cast": int(os.getenv("MAX_TOKENS_PLOT_FROM_CAST", 700)),
        "section_characters": int(os.getenv("MAX_TOKENS_SECTION_CHARACTERS", 180)),
        "img_prompt_with_characters": int(os.getenv("MAX_TOKENS_IMG_PROMPT_WITH_CHARACTERS", 180)),
        "book_match_validation": int(os.getenv("MAX_TOKENS_BOOK_MATCH_VALIDATION", 420)),
    },
    "temperature": {
        "character": float(os.getenv("TEMPERATURE_CHARACTER", 0.8)),
        "name": float(os.getenv("TEMPERATURE_NAME", 0.7)),
        "plot": float(os.getenv("TEMPERATURE_PLOT", 0.7)),
        "story": float(os.getenv("TEMPERATURE_STORY", 0.7)),
        "sectioning": float(os.getenv("TEMPERATURE_SECTIONING", 0.5)),
        "img_prompt": float(os.getenv("TEMPERATURE_IMG_PROMPT", 0.6)),
        "main_story_characters": float(os.getenv("TEMPERATURE_MAIN_STORY_CHARACTERS", 0.4)),
        "story_cast": float(os.getenv("TEMPERATURE_STORY_CAST", 0.5)),
        "plot_from_cast": float(os.getenv("TEMPERATURE_PLOT_FROM_CAST", 0.7)),
        "section_characters": float(os.getenv("TEMPERATURE_SECTION_CHARACTERS", 0.2)),
        "img_prompt_with_characters": float(os.getenv("TEMPERATURE_IMG_PROMPT_WITH_CHARACTERS", 0.5)),
        "book_match_validation": float(os.getenv("TEMPERATURE_BOOK_MATCH_VALIDATION", 0.1)),
    },
    "image": {
        "size": os.getenv("IMAGE_SIZE", "1024x1024"),
        "quality": os.getenv("IMAGE_QUALITY", "low"),
        "output_format": os.getenv("OUTPUT_FORMAT", "png"),
    },
    "image_edit": {
        "size": os.getenv("IMAGE_EDIT_SIZE", os.getenv("IMAGE_SIZE", "1024x1024")),
        "quality": os.getenv("IMAGE_EDIT_QUALITY", os.getenv("IMAGE_QUALITY", "low")),
    },
    "story": {
        "word_count": int(os.getenv("STORY_TARGET_WORD_COUNT", 400)),
    },
}

client: Optional[OpenAI] = None
if CONFIG["api_key"]:
    try:
        client = OpenAI(api_key=CONFIG["api_key"])
        logger.info("OpenAI client initialized successfully.")
    except Exception as exc:
        logger.error(f"Failed to initialize OpenAI client: {exc}")
else:
    logger.warning("OpenAI API key not found. OpenAI functionality disabled.")


def is_client_ready() -> bool:
    return client is not None


@lru_cache(maxsize=16)
def load_prompt_template(prompt_type: str) -> Optional[str]:
    filename = CONFIG["prompt_files"].get(prompt_type)
    if not filename:
        logger.error(f"Prompt file path not configured for type: {prompt_type}")
        return None

    base_dir = os.path.dirname(__file__)
    preferred_path = os.path.join(base_dir, filename)

    filepath = preferred_path if os.path.exists(preferred_path) else filename
    if not os.path.exists(filepath):
        logger.error(f"Prompt file not found: {preferred_path}")
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as prompt_file:
            return prompt_file.read()
    except Exception as exc:
        logger.error(f"Error loading prompt file {filepath}: {exc}")
        return None


@lru_cache(maxsize=8)
def load_schema(schema_type: str) -> Optional[Dict[str, Any]]:
    filename = CONFIG["schema_files"].get(schema_type)
    if not filename:
        logger.error(f"Schema path not configured for type: {schema_type}")
        return None
    return load_json_config_file(filename)


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _extract_balanced_json_object(text: str) -> Optional[str]:
    start_index = text.find("{")
    if start_index == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    return None


def _parse_json_object_from_text(raw_text: str) -> Dict[str, Any]:
    cleaned = _strip_code_fences(raw_text)
    if not cleaned:
        return {}

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    object_slice = _extract_balanced_json_object(cleaned)
    if object_slice:
        parsed = json.loads(object_slice)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Could not parse a valid JSON object from model output.")


def _sanitize_string(value: Any, fallback: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or fallback


def _split_listish_string(text: str, *, allow_comma_split: bool = False) -> List[str]:
    if not text:
        return []

    normalized = text.replace("\r", "\n").strip()
    if not normalized:
        return []

    numbered = re.sub(r"(?<!\d)(\d{1,2}[.)])\s+", r"\n\1 ", normalized)
    raw_parts: List[str] = []
    for chunk in numbered.split("\n"):
        line = chunk.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]+|\d{1,2}[.)])\s*", "", line).strip()
        if line:
            raw_parts.append(line)

    if allow_comma_split and len(raw_parts) <= 1 and "," in normalized:
        comma_parts = [segment.strip() for segment in normalized.split(",") if segment.strip()]
        if len(comma_parts) > 1:
            return comma_parts

    return raw_parts if raw_parts else [normalized]


def _sanitize_string_list(
    value: Any,
    fallback: Optional[List[str]] = None,
    *,
    allow_comma_split: bool = False,
) -> List[str]:
    fallback = fallback or []
    if not isinstance(value, list):
        return fallback

    cleaned: List[str] = []
    for item in value:
        text = _sanitize_string(item)
        if not text:
            continue
        for segment in _split_listish_string(text, allow_comma_split=allow_comma_split):
            if segment and segment not in cleaned:
                cleaned.append(segment)
    return cleaned if cleaned else fallback


def _sanitize_profile_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return _sanitize_string_list(value, fallback=[])
    if isinstance(value, str):
        return _split_listish_string(value, allow_comma_split=True)
    return []


def _normalize_visual_profile_payload(
    payload: Dict[str, Any],
    *,
    character_name: str = "",
    character_description: str = "",
) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}

    source = payload
    nested_profile = payload.get("visual_profile")
    if isinstance(nested_profile, dict):
        source = nested_profile

    summary = _sanitize_string(source.get("summary") or source.get("profile_summary"))
    appearance = _sanitize_profile_list(source.get("appearance"))
    clothing = _sanitize_profile_list(source.get("clothing"))
    colors = _sanitize_profile_list(source.get("colors"))
    accessories = _sanitize_profile_list(source.get("accessories"))
    distinctive_features = _sanitize_profile_list(source.get("distinctive_features"))
    style_notes = _sanitize_profile_list(source.get("style_notes"))
    consistency_prompt = _sanitize_string(source.get("consistency_prompt"))

    if not summary:
        summary_parts: List[str] = []
        if character_name:
            summary_parts.append(f"{character_name} visual reference.")
        if clothing:
            summary_parts.append(f"Clothing: {', '.join(clothing[:4])}.")
        if colors:
            summary_parts.append(f"Color palette: {', '.join(colors[:4])}.")
        if distinctive_features:
            summary_parts.append(f"Distinctive features: {', '.join(distinctive_features[:4])}.")
        if not summary_parts and character_description:
            summary_parts.append(character_description)
        summary = " ".join(summary_parts).strip()

    if not consistency_prompt:
        prompt_parts: List[str] = []
        if character_name:
            prompt_parts.append(f"Keep {character_name} consistent across all scenes.")
        if clothing:
            prompt_parts.append(f"Maintain clothing: {', '.join(clothing[:5])}.")
        if colors:
            prompt_parts.append(f"Use recurring colors: {', '.join(colors[:5])}.")
        if accessories:
            prompt_parts.append(f"Retain accessories: {', '.join(accessories[:5])}.")
        if distinctive_features:
            prompt_parts.append(f"Preserve distinctive features: {', '.join(distinctive_features[:5])}.")
        consistency_prompt = " ".join(prompt_parts).strip()

    normalized: Dict[str, Any] = {}
    if summary:
        normalized["summary"] = summary[:800]
    if appearance:
        normalized["appearance"] = appearance[:16]
    if clothing:
        normalized["clothing"] = clothing[:16]
    if colors:
        normalized["colors"] = colors[:16]
    if accessories:
        normalized["accessories"] = accessories[:16]
    if distinctive_features:
        normalized["distinctive_features"] = distinctive_features[:16]
    if style_notes:
        normalized["style_notes"] = style_notes[:16]
    if consistency_prompt:
        normalized["consistency_prompt"] = consistency_prompt[:1200]
    return normalized


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


def _sanitize_character_objects(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    cleaned: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        name = _sanitize_string(item.get("name"))
        description = _sanitize_string(item.get("description"))
        if not name or not description:
            continue
        name_keys = _character_name_keys(name)
        if not name_keys:
            continue
        if any(key in seen_keys for key in name_keys):
            continue
        seen_keys.update(name_keys)
        cleaned.append(
            {
                "name": name,
                "description": description,
                "is_child": bool(item.get("is_child", False)),
            }
        )
    return cleaned


def _name_from_character_idea(idea: str, fallback_index: int) -> str:
    tokens = re.findall(r"[A-Za-z]+", idea or "")
    if not tokens:
        return f"Friend {fallback_index}"
    if len(tokens) == 1:
        return tokens[0].capitalize()
    if tokens[1].lower() in _CHARACTER_NAME_STOPWORDS:
        return tokens[0].capitalize()
    return " ".join(token.capitalize() for token in tokens[:2])


def format_prompt(template: str, data: Dict[str, Any]) -> str:
    try:
        return template.format(**data)
    except KeyError as exc:
        raise ValueError(f"Prompt template error: missing key {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Prompt template formatting error: {exc}") from exc


def _runtime_value(runtime_settings: Optional[Dict[str, Any]], key: str, default: Any) -> Any:
    if not isinstance(runtime_settings, dict):
        return default
    value = runtime_settings.get(key)
    return default if value in (None, "") else value


def _runtime_float(runtime_settings: Optional[Dict[str, Any]], key: str, default: float) -> float:
    value = _runtime_value(runtime_settings, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _runtime_int(runtime_settings: Optional[Dict[str, Any]], key: str, default: int) -> int:
    value = _runtime_value(runtime_settings, key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _profile_max_tokens(runtime_settings: Optional[Dict[str, Any]], default: int = 1200) -> int:
    env_default = int(os.getenv("PROFILE_MAX_TOKENS", str(default)))
    return _runtime_int(runtime_settings, "profile_max_tokens", env_default)


def _text_model(runtime_settings: Optional[Dict[str, Any]], task_model_key: str) -> str:
    return str(
        _runtime_value(
            runtime_settings,
            "text_model",
            CONFIG["models"][task_model_key],
        )
    )


def _temperature(runtime_settings: Optional[Dict[str, Any]], task_temp_key: str) -> float:
    return _runtime_float(runtime_settings, "text_temperature", CONFIG["temperature"][task_temp_key])


def _structured_chat_object(
    *,
    runtime_settings: Optional[Dict[str, Any]],
    task_model_key: str,
    task_temp_key: str,
    max_tokens: int,
    schema_key: str,
    schema_name: str,
    system_text: str,
    user_prompt: str,
) -> Dict[str, Any]:
    if not is_client_ready():
        raise RuntimeError("OpenAI client not ready.")

    schema = load_schema(schema_key)
    if not schema:
        raise RuntimeError(f"Schema not found for {schema_key}.")

    model = _text_model(runtime_settings, task_model_key)
    temperature = _temperature(runtime_settings, task_temp_key)
    max_token_value = _runtime_int(runtime_settings, "text_max_tokens", max_tokens)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_text},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_token_value,
            temperature=temperature,
            n=1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        raw_output = (response.choices[0].message.content or "").strip()
        return _parse_json_object_from_text(raw_output)
    except Exception:
        fallback_response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_token_value,
            temperature=0.0,
            n=1,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        fallback_output = (fallback_response.choices[0].message.content or "").strip()
        return _parse_json_object_from_text(fallback_output)


def extract_child_profile(
    child_profile_text: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("child_profile_extraction")
    if not template:
        return {"error": "Could not load child profile extraction prompt template."}

    try:
        prompt = format_prompt(template, {"child_profile_text": child_profile_text})
    except ValueError as exc:
        return {"error": str(exc)}

    try:
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="character",
            max_tokens=_profile_max_tokens(runtime_settings, 1200),
            schema_key="child_profile_extraction",
            schema_name="child_profile_extraction",
            system_text="You extract structured child story profile data as strict JSON.",
            user_prompt=prompt,
        )
        normalized = normalize_child_profile(parsed_output)
        persist_profile_extraction("openai", prompt, normalized, json.dumps(parsed_output))
        return normalized
    except Exception as exc:
        logger.error(f"Error extracting child profile: {exc}")
        fallback = fallback_profile_from_text(child_profile_text)
        persist_profile_extraction(
            "openai",
            prompt,
            fallback,
            f"FALLBACK_USED: {exc}",
        )
        fallback["warning"] = "Used fallback extraction because model JSON output was invalid."
        return fallback


def get_character_suggestions(
    theme: str,
    type: str,
    personality_keywords: List[str],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("character")
    if not template:
        return {"error": "Could not load character prompt template."}

    try:
        prompt = format_prompt(
            template,
            {
                "theme": theme,
                "type": type,
                "personality_keywords_str": ", ".join(personality_keywords)
                if personality_keywords
                else "not specified",
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="character",
            max_tokens=CONFIG["max_tokens"]["character"],
            schema_key="character_suggestions",
            schema_name="character_suggestions",
            system_text="Generate child-friendly character suggestions in structured JSON.",
            user_prompt=prompt,
        )
        suggestions = _sanitize_string_list(parsed_output.get("suggestions"))
        return {"suggestions": suggestions if suggestions else ["No suggestions generated."]}
    except Exception as exc:
        logger.error(f"Error generating character suggestions: {exc}")
        return {"error": f"Error generating suggestions: {exc}"}


def get_name_suggestions(
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("name")
    if not template:
        return {"error": "Could not load name prompt template."}

    try:
        prompt = format_prompt(
            template,
            {
                "character_description": character_description,
                "theme": theme,
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="name",
            max_tokens=CONFIG["max_tokens"]["name"],
            schema_key="name_suggestions",
            schema_name="name_suggestions",
            system_text="Generate character name suggestions in structured JSON.",
            user_prompt=prompt,
        )
        names = _sanitize_string_list(parsed_output.get("names"), allow_comma_split=True)
        return {"names": names if names else ["No names generated."]}
    except Exception as exc:
        logger.error(f"Error generating name suggestions: {exc}")
        return {"error": f"Error generating names: {exc}"}


def get_plot_suggestions(
    learning_objective: str,
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("plot")
    if not template:
        return {"error": "Could not load plot prompt template."}

    try:
        prompt = format_prompt(
            template,
            {
                "learning_objective": learning_objective,
                "character_description": character_description,
                "theme": theme,
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="plot",
            max_tokens=CONFIG["max_tokens"]["plot"],
            schema_key="plot_suggestions",
            schema_name="plot_suggestions",
            system_text="Generate plot ideas in structured JSON.",
            user_prompt=prompt,
        )
        parsed = _sanitize_string_list(parsed_output.get("plots"))
        return {"plots": parsed if parsed else ["No plot ideas generated."]}
    except Exception as exc:
        logger.error(f"Error generating plot suggestions: {exc}")
        return {"error": f"Error generating plot ideas: {exc}"}


def get_main_story_characters(
    child_name: str,
    character_name: str,
    character_description: str,
    plot_choice: str,
    learning_objective: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("main_story_characters")
    if not template:
        return {"error": "Could not load main story characters prompt template."}

    try:
        prompt = format_prompt(
            template,
            {
                "child_name": child_name,
                "character_name": character_name,
                "character_description": character_description,
                "plot_choice": plot_choice,
                "learning_objective": learning_objective,
                "theme": theme,
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="main_story_characters",
            max_tokens=CONFIG["max_tokens"]["main_story_characters"],
            schema_key="main_story_characters",
            schema_name="main_story_characters",
            system_text="Extract the main story characters and return structured JSON.",
            user_prompt=prompt,
        )
        characters = _sanitize_string_list(parsed_output.get("main_characters"))
        return {"main_characters": characters if characters else ["No main characters identified."]}
    except Exception as exc:
        logger.error(f"Error extracting main story characters: {exc}")
        return {"error": f"Error extracting main story characters: {exc}"}


def prepare_story_cast(
    child_name: str,
    child_profile_text: str,
    learning_objective: str,
    theme: str,
    personality_keywords: List[str],
    selected_character_ideas: List[str],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("story_cast_preparation")
    if not template:
        return {"error": "Could not load story cast preparation prompt template."}

    selected_character_ideas = _sanitize_string_list(selected_character_ideas)

    try:
        prompt = format_prompt(
            template,
            {
                "child_name": child_name or "",
                "child_profile_text": child_profile_text or "",
                "learning_objective": learning_objective,
                "theme": theme,
                "personality_keywords_str": ", ".join(personality_keywords)
                if personality_keywords
                else "not specified",
                "selected_character_ideas_str": json.dumps(selected_character_ideas, ensure_ascii=False),
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="story_cast",
            max_tokens=CONFIG["max_tokens"]["story_cast"],
            schema_key="story_cast",
            schema_name="story_cast",
            system_text="Build a coherent child-friendly story cast in strict JSON.",
            user_prompt=prompt,
        )

        child = parsed_output.get("child_character")
        child_name_value = _sanitize_string((child or {}).get("name"), child_name or "Little Explorer")
        child_description = _sanitize_string(
            (child or {}).get("description"),
            "The child hero who learns and grows through the adventure.",
        )
        child_character = {
            "name": child_name_value,
            "description": child_description,
            "is_child": True,
        }

        story_characters = _sanitize_character_objects(parsed_output.get("story_characters"))
        story_characters = [char for char in story_characters if char["name"].lower() != child_name_value.lower()]
        story_characters.insert(0, child_character)
        existing_name_keys: set[str] = set()
        for character in story_characters:
            existing_name_keys.update(_character_name_keys(character.get("name", "")))

        for idx, idea in enumerate(selected_character_ideas, start=1):
            if len(story_characters) >= 8:
                break
            if not idea:
                continue
            generated_name = _name_from_character_idea(idea, idx)
            candidate_keys = _character_name_keys(generated_name)
            if not candidate_keys or candidate_keys.intersection(existing_name_keys):
                continue
            story_characters.append(
                {
                    "name": generated_name,
                    "description": _sanitize_string(idea),
                    "is_child": False,
                }
            )
            existing_name_keys.update(candidate_keys)

        if len(story_characters) < 2:
            story_characters.append(
                {
                    "name": "Helpful Friend",
                    "description": "A supportive friend who joins the child in the story adventure.",
                    "is_child": False,
                }
            )

        return {"child_character": child_character, "story_characters": story_characters[:8]}
    except Exception as exc:
        logger.error(f"Error preparing story cast: {exc}")
        return {"error": f"Error preparing story cast: {exc}"}


def get_plot_suggestions_from_cast(
    learning_objective: str,
    theme: str,
    story_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("plot_from_cast")
    if not template:
        return {"error": "Could not load cast-based plot prompt template."}

    characters = _sanitize_character_objects(story_characters)
    if len(characters) < 2:
        return {"error": "At least 2 characters are required to generate cast-based plots."}

    try:
        prompt = format_prompt(
            template,
            {
                "learning_objective": learning_objective,
                "theme": theme,
                "story_characters_json": json.dumps(characters, ensure_ascii=False),
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="suggestions",
            task_temp_key="plot_from_cast",
            max_tokens=CONFIG["max_tokens"]["plot_from_cast"],
            schema_key="plot_suggestions",
            schema_name="plot_suggestions",
            system_text="Generate cast-based plot options in strict JSON.",
            user_prompt=prompt,
        )
        plots = _sanitize_string_list(parsed_output.get("plots"))
        return {"plots": plots if plots else ["No plot ideas generated."]}
    except Exception as exc:
        logger.error(f"Error generating cast-based plot suggestions: {exc}")
        return {"error": f"Error generating plot ideas: {exc}"}


def identify_section_characters(
    story_section_text: str,
    story_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("section_characters")
    if not template:
        return {"error": "Could not load section character identification prompt template."}

    characters = _sanitize_character_objects(story_characters)
    if not characters:
        return {"error": "No story characters provided."}

    try:
        prompt = format_prompt(
            template,
            {
                "story_section_text": story_section_text,
                "story_characters_json": json.dumps(characters, ensure_ascii=False),
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="sectioning",
            task_temp_key="section_characters",
            max_tokens=CONFIG["max_tokens"]["section_characters"],
            schema_key="page_characters",
            schema_name="page_characters",
            system_text="Identify which listed characters appear in the section and return strict JSON.",
            user_prompt=prompt,
        )

        requested_names = _sanitize_string_list(parsed_output.get("character_names"))
        allowed_map = {char["name"].lower(): char["name"] for char in characters}
        selected_names: List[str] = []
        for raw_name in requested_names:
            normalized_name = raw_name.strip().lower()
            if normalized_name in allowed_map and allowed_map[normalized_name] not in selected_names:
                selected_names.append(allowed_map[normalized_name])

        if not selected_names:
            selected_names = [characters[0]["name"]]
            if len(characters) > 1:
                selected_names.append(characters[1]["name"])
        return {"character_names": selected_names[:6]}
    except Exception as exc:
        logger.error(f"Error identifying section characters: {exc}")
        return {"error": f"Error identifying section characters: {exc}"}


def create_image_prompt_for_section_with_characters(
    story_section_text: str,
    theme: str,
    involved_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("image_prompt_with_characters")
    if not template:
        return {"error": "Could not load image prompt with characters template."}

    characters = _sanitize_character_objects(involved_characters)
    if not characters:
        return {"error": "No involved characters provided for image prompt creation."}

    try:
        prompt = format_prompt(
            template,
            {
                "story_section_text": story_section_text,
                "theme": theme,
                "involved_characters_json": json.dumps(characters, ensure_ascii=False),
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="img_prompt",
            task_temp_key="img_prompt_with_characters",
            max_tokens=CONFIG["max_tokens"]["img_prompt_with_characters"],
            schema_key="image_prompt",
            schema_name="image_prompt",
            system_text="Return one concise section image prompt in strict JSON.",
            user_prompt=prompt,
        )
        image_prompt_text = _sanitize_string(parsed_output.get("image_prompt"))
        if not image_prompt_text:
            return {"error": "AI failed to generate a non-empty image prompt."}
        return {"image_prompt": image_prompt_text}
    except Exception as exc:
        logger.error(f"Error creating image prompt with characters: {exc}")
        return {"error": f"Error creating image prompt: {exc}"}


def validate_book_match(
    child_name: str,
    learning_objective: str,
    theme: str,
    selected_plot: str,
    story_characters: List[Dict[str, Any]],
    pages: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("book_match_validation")
    if not template:
        return {"error": "Could not load book match validation prompt template."}

    characters = _sanitize_character_objects(story_characters)
    if not isinstance(pages, list) or not pages:
        return {"error": "Pages are required for book match validation."}

    safe_pages: List[Dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        safe_pages.append(
            {
                "text": _sanitize_string(page.get("text")),
                "characters": _sanitize_string_list(page.get("characters"), fallback=[]),
            }
        )

    try:
        prompt = format_prompt(
            template,
            {
                "child_name": child_name,
                "learning_objective": learning_objective,
                "theme": theme,
                "selected_plot": selected_plot,
                "story_characters_json": json.dumps(characters, ensure_ascii=False),
                "pages_json": json.dumps(safe_pages, ensure_ascii=False),
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="sectioning",
            task_temp_key="book_match_validation",
            max_tokens=CONFIG["max_tokens"]["book_match_validation"],
            schema_key="book_match_validation",
            schema_name="book_match_validation",
            system_text="Evaluate semantic alignment and return strict JSON only.",
            user_prompt=prompt,
        )

        recommendation = _sanitize_string(parsed_output.get("recommendation")).lower()
        normalized_recommendation = recommendation if recommendation in {"pass", "review", "fail"} else "review"
        issues = _sanitize_string_list(parsed_output.get("issues"), fallback=[])

        result = {
            "is_match": bool(parsed_output.get("is_match", False)),
            "overall_score": float(parsed_output.get("overall_score", 0.0)),
            "plot_alignment_score": float(parsed_output.get("plot_alignment_score", 0.0)),
            "character_consistency_score": float(parsed_output.get("character_consistency_score", 0.0)),
            "learning_goal_alignment_score": float(parsed_output.get("learning_goal_alignment_score", 0.0)),
            "issues": issues,
            "recommendation": normalized_recommendation,
        }

        if result["recommendation"] == "pass":
            result["is_match"] = True
        return result
    except Exception as exc:
        logger.error(f"Error validating book match: {exc}")
        return {"error": f"Error validating book match: {exc}"}


def generate_story(
    child_name: str,
    character_name: str,
    character_description: str,
    plot_choice: str,
    learning_objective: str,
    theme: str,
    personality_keywords: List[str],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("story")
    if not template:
        return {"error": "Could not load story prompt template."}

    try:
        prompt = format_prompt(
            template,
            {
                "story_word_count": CONFIG["story"]["word_count"],
                "child_name": child_name,
                "character_name": character_name,
                "character_description": character_description,
                "plot_choice": plot_choice,
                "learning_objective": learning_objective,
                "theme": theme,
                "personality_keywords_str": ", ".join(personality_keywords)
                if personality_keywords
                else "not specified",
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="story",
            task_temp_key="story",
            max_tokens=CONFIG["max_tokens"]["story"],
            schema_key="story_text",
            schema_name="story_text",
            system_text="Write a complete story and return it in structured JSON.",
            user_prompt=prompt,
        )
        story_text = _sanitize_string(parsed_output.get("story_text"))
        if len(story_text) < 50:
            return {
                "story_text": "The generated story was too short. Please try again.",
                "warning": "short_story",
            }
        return {"story_text": story_text}
    except Exception as exc:
        logger.error(f"Error generating story: {exc}")
        return {"error": f"Oops! Error generating the story: {exc}"}


def get_story_sections(
    full_story_text: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("story_sectioning")
    if not template:
        return {"error": "Could not load story sectioning prompt template."}

    try:
        prompt = format_prompt(template, {"full_story_text": full_story_text})
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="sectioning",
            task_temp_key="sectioning",
            max_tokens=CONFIG["max_tokens"]["sectioning"],
            schema_key="story_sections",
            schema_name="story_sections",
            system_text="Split the story into ordered sections and return structured JSON.",
            user_prompt=prompt,
        )
        sections = _sanitize_string_list(parsed_output.get("sections"))
        if not sections:
            return {"error": "Failed to parse sections."}
        return {"sections": sections}
    except Exception as exc:
        logger.error(f"Error sectioning story: {exc}")
        return {"error": f"Error sectioning story: {exc}"}


def create_image_prompt_for_section(
    story_section_text: str,
    character_name: str,
    character_description: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("image_prompt_creation")
    if not template:
        return {"error": "Could not load image prompt creation template."}

    try:
        prompt = format_prompt(
            template,
            {
                "story_section_text": story_section_text,
                "character_name": character_name,
                "character_description": character_description,
            },
        )
        parsed_output = _structured_chat_object(
            runtime_settings=runtime_settings,
            task_model_key="img_prompt",
            task_temp_key="img_prompt",
            max_tokens=CONFIG["max_tokens"]["img_prompt"],
            schema_key="image_prompt",
            schema_name="image_prompt",
            system_text="Return one concise image prompt in structured JSON.",
            user_prompt=prompt,
        )
        image_prompt_text = _sanitize_string(parsed_output.get("image_prompt"))
        if not image_prompt_text:
            return {"error": "AI failed to generate a non-empty image prompt."}
        return {"image_prompt": image_prompt_text}
    except Exception as exc:
        logger.error(f"Error creating image prompt: {exc}")
        return {"error": f"Error creating image prompt: {exc}"}


def _image_mime_type_from_format(output_format: str) -> str:
    lowered = (output_format or "png").lower()
    if lowered in {"jpg", "jpeg"}:
        return "image/jpeg"
    if lowered == "webp":
        return "image/webp"
    return "image/png"


def _map_image_error(exc: Exception, prefix: str = "generate") -> Dict[str, Any]:
    error_text = str(exc).lower()
    error_code = "generic_error" if prefix == "generate" else "generic_edit_error"
    user_message = "Failed to generate image: An unexpected error occurred."
    if prefix != "generate":
        user_message = "Failed to edit image: An unexpected error occurred."

    if "content policy" in error_text or "safety system" in error_text:
        error_code = "content_policy_error"
        user_message = (
            "Image generation failed due to content policy."
            if prefix == "generate"
            else "Image editing failed due to content policy."
        )
    elif "billing" in error_text or "quota" in error_text:
        error_code = "billing_error"
        user_message = (
            "Image generation failed due to account limits."
            if prefix == "generate"
            else "Image editing failed due to account limits."
        )
    elif "authentication" in error_text or "api key" in error_text:
        error_code = "auth_error"
        user_message = (
            "Image generation failed due to authentication error."
            if prefix == "generate"
            else "Image editing failed due to authentication error."
        )
    elif "invalid_request_error" in error_text:
        error_code = "invalid_request"
        user_message = (
            f"Image generation failed: Invalid request ({exc})"
            if prefix == "generate"
            else f"Image editing failed: Invalid request ({exc})"
        )

    if "image must be square" in error_text:
        error_code = "image_format_error"
        user_message = "Image editing failed: Base image must be square for the selected model."

    return {"error": user_message, "error_code": error_code}


def understand_image(
    image_b64: str,
    mime_type: str = "image/png",
    character_name: str = "",
    character_description: str = "",
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    clean_b64 = _sanitize_string(image_b64)
    if not clean_b64:
        return {"error": "Image data is required.", "error_code": "invalid_request"}
    if clean_b64.startswith("data:") and "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]

    safe_mime = _sanitize_string(mime_type, "image/png")
    if not safe_mime.startswith("image/"):
        safe_mime = "image/png"

    model = _text_model(runtime_settings, "sectioning")
    analysis_prompt = (
        "Analyze this single character image and return one strict JSON object with fields: "
        "summary (string), appearance (array), clothing (array), colors (array), "
        "accessories (array), distinctive_features (array), style_notes (array), "
        "consistency_prompt (string). Focus only on visible details."
    )
    if character_name:
        analysis_prompt += f" Character name: {character_name}."
    if character_description:
        analysis_prompt += f" Story context: {character_description}."

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You extract structured visual character details as strict JSON."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{safe_mime};base64,{clean_b64}"},
                        },
                    ],
                },
            ],
            max_tokens=_runtime_int(runtime_settings, "text_max_tokens", 600),
            temperature=0.1,
            n=1,
            response_format={"type": "json_object"},
        )
        raw_output = _sanitize_string((response.choices[0].message.content or ""))
        parsed = _parse_json_object_from_text(raw_output)
        profile = _normalize_visual_profile_payload(
            parsed,
            character_name=character_name,
            character_description=character_description,
        )
        if not profile:
            return {"error": "Image understanding returned an empty profile.", "error_code": "invalid_response"}
        return {"visual_profile": profile}
    except Exception as exc:
        logger.error(f"Error calling OpenAI image understanding: {exc}")
        return {"error": f"Failed to understand image: {exc}", "error_code": "invalid_response"}


def generate_image(
    description: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}

    style_prompt_template = load_prompt_template("image_style")
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{description}. {style_prompt}".strip()

    model = str(_runtime_value(runtime_settings, "image_model", CONFIG["models"]["image_gen"]))
    size = str(_runtime_value(runtime_settings, "image_size", CONFIG["image"]["size"]))
    quality = str(_runtime_value(runtime_settings, "image_quality", CONFIG["image"]["quality"]))
    output_format = str(
        _runtime_value(
            runtime_settings,
            "image_output_format",
            CONFIG["image"]["output_format"],
        )
    )

    try:
        response = client.images.generate(
            model=model,
            prompt=full_prompt,
            size=size,
            quality=quality,
            output_format=output_format,
            n=1,
        )

        if response.data and response.data[0].b64_json:
            revised_prompt = getattr(response.data[0], "revised_prompt", "")
            return {
                "b64_json": response.data[0].b64_json,
                "revised_prompt": revised_prompt,
                "mime_type": _image_mime_type_from_format(output_format),
            }
        return {"error": "Invalid response from image API.", "error_code": "invalid_response"}
    except Exception as exc:
        logger.error(f"Error calling OpenAI image generate: {exc}")
        return _map_image_error(exc, prefix="generate")


def generate_image_with_references(
    description: str,
    reference_images: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # OpenAI image generation in this project does not support passing multiple reference images
    # in the same path used for Gemini. We preserve behavior by enriching the prompt with
    # referenced character names and generating a new image.
    reference_names = []
    for item in reference_images or []:
        if isinstance(item, dict):
            name = _sanitize_string(item.get("name"))
            if name and name not in reference_names:
                reference_names.append(name)

    enriched_prompt = description
    if reference_names:
        enriched_prompt = f"{description}. Characters to include: {', '.join(reference_names)}."
    return generate_image(enriched_prompt, runtime_settings=runtime_settings)


def edit_image_based_on_prompt(
    base_image_b64: str,
    edit_prompt: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "OpenAI client not ready.", "error_code": "service_unavailable"}
    if not base_image_b64:
        return {"error": "Base image data is missing.", "error_code": "missing_base_image"}

    model = str(_runtime_value(runtime_settings, "image_edit_model", CONFIG["models"]["image_edit"]))
    size = str(
        _runtime_value(
            runtime_settings,
            "image_edit_size",
            CONFIG["image_edit"]["size"],
        )
    )
    quality = str(
        _runtime_value(
            runtime_settings,
            "image_edit_quality",
            CONFIG["image_edit"]["quality"],
        )
    )
    style_prompt_template = load_prompt_template("image_style")
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{edit_prompt}. {style_prompt}".strip()

    try:
        image_bytes = base64.b64decode(base_image_b64)
        image_file = io.BytesIO(image_bytes)
        image_file.name = "base_image.png"
    except Exception:
        return {"error": "Invalid base image data provided.", "error_code": "decode_error"}

    try:
        response = client.images.edit(
            model=model,
            image=image_file,
            prompt=full_prompt,
            size=size,
            quality=quality,
            n=1,
        )

        if response.data and response.data[0].b64_json:
            return {
                "b64_json": response.data[0].b64_json,
                "mime_type": "image/png",
            }
        return {
            "error": "Invalid response format from image edit API.",
            "error_code": "invalid_response",
        }
    except Exception as exc:
        logger.error(f"Error calling OpenAI image edit: {exc}")
        return _map_image_error(exc, prefix="edit")
