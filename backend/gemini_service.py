import base64
import io
import json
import logging
import os
import re
import tempfile
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

from profile_extraction_utils import (
    fallback_profile_from_text,
    load_json_config_file,
    normalize_child_profile,
    persist_profile_extraction,
)
from secret_utils import read_secret


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

CONFIG = {
    "api_key": read_secret(
        "GEMINI_API_KEY",
        "GEMINI_API_KEY_FILE",
        "/run/secrets/gemini_api_key",
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
        "suggestions": os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview"),
        "story": os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview"),
        "sectioning": os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview"),
        "img_prompt": os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview"),
        "structured_fallback": os.getenv("GEMINI_STRUCTURED_FALLBACK_MODEL", "gemini-3-flash-preview"),
        "image_gen": os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"),
        "image_edit": os.getenv("GEMINI_IMAGE_EDIT_MODEL", "gemini-2.5-flash-image"),
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
        "aspect_ratio": os.getenv("GEMINI_IMAGE_ASPECT_RATIO", "1:1"),
        "image_size": os.getenv("GEMINI_IMAGE_SIZE", "1K"),
    },
    "story": {
        "word_count": int(os.getenv("STORY_TARGET_WORD_COUNT", 400)),
    },
}

if CONFIG["api_key"]:
    logger.info("Gemini API key loaded.")
else:
    logger.warning("Gemini API key not found. Gemini functionality disabled.")

_genai_client: Optional[Any] = None


def is_client_ready() -> bool:
    return bool(CONFIG["api_key"])


def _get_genai_client():
    global _genai_client
    if not is_client_ready():
        raise RuntimeError("Gemini client not ready.")
    if _genai_client is None:
        _genai_client = genai.Client(api_key=CONFIG["api_key"])
    return _genai_client


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


def _extract_error_message(response_json: Dict[str, Any], status_code: int) -> str:
    error_obj = response_json.get("error", {})
    if isinstance(error_obj, dict):
        message = error_obj.get("message")
        if message:
            return str(message)
    return f"Gemini API request failed with status {status_code}."


def _generate_content(
    model: str,
    parts: List[Dict[str, Any]],
    temperature: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
    system_instruction: Optional[str] = None,
    response_modalities: Optional[List[str]] = None,
    image_config: Optional[Dict[str, Any]] = None,
    response_mime_type: Optional[str] = None,
    response_json_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        raise RuntimeError("Gemini client not ready.")

    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ]
    }

    if system_instruction:
        payload["systemInstruction"] = {
            "parts": [{"text": system_instruction}],
        }

    generation_config: Dict[str, Any] = {}
    if temperature is not None:
        generation_config["temperature"] = float(temperature)
    if max_output_tokens is not None:
        generation_config["maxOutputTokens"] = int(max_output_tokens)
    generation_config["candidateCount"] = 1
    if response_modalities:
        generation_config["responseModalities"] = response_modalities
    if image_config:
        generation_config["imageConfig"] = image_config
    if response_mime_type:
        generation_config["responseMimeType"] = response_mime_type
    if response_json_schema:
        generation_config["responseJsonSchema"] = response_json_schema
        model_name = (model or "").strip().lower()
        if "2.5-flash" in model_name:
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}
    if generation_config:
        payload["generationConfig"] = generation_config

    endpoint = f"{GEMINI_API_BASE}/models/{model}:generateContent"
    response = requests.post(
        endpoint,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": CONFIG["api_key"],
        },
        json=payload,
        timeout=180,
    )

    try:
        response_json = response.json()
    except ValueError:
        response_json = {}

    if response.status_code >= 400:
        message = _extract_error_message(response_json, response.status_code)
        raise RuntimeError(message)

    return response_json


def _iter_candidate_parts(response_json: Dict[str, Any]):
    for candidate in response_json.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            yield part


def _candidate_texts(response_json: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for candidate in response_json.get("candidates", []):
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        chunks: List[str] = []
        for part in parts:
            text = part.get("text")
            if isinstance(text, str):
                chunks.append(text)
        combined = "".join(chunks).strip()
        if combined:
            texts.append(combined)
    return texts


def _extract_text(response_json: Dict[str, Any]) -> str:
    texts = _candidate_texts(response_json)
    return texts[0] if texts else ""


def _extract_image(response_json: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    for part in _iter_candidate_parts(response_json):
        inline_data = part.get("inlineData") or part.get("inline_data")
        if not isinstance(inline_data, dict):
            continue

        data = inline_data.get("data")
        mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png"
        if isinstance(data, str) and data.strip():
            return data, str(mime_type)
    return None


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


def _coerce_parsed_object(payload: Any) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        try:
            dumped = payload.model_dump()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if hasattr(payload, "dict"):
        try:
            dumped = payload.dict()
            if isinstance(dumped, dict):
                return dumped
        except Exception:
            pass
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def _sdk_structured_generate(
    *,
    model: str,
    prompt_text: str,
    system_instruction: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    client = _get_genai_client()
    # For gemini-3-flash-preview structured output, keep config minimal per docs.
    # Adding extra generation params can cause the SDK to return plain text wrappers.
    config: Dict[str, Any] = {
        "response_mime_type": "application/json",
        "response_json_schema": schema,
    }
    full_prompt = prompt_text
    if system_instruction:
        full_prompt = f"{system_instruction.strip()}\n\n{prompt_text}"

    response = client.models.generate_content(
        model=model,
        contents=full_prompt,
        config=config,
    )

    parsed_payload = getattr(response, "parsed", None)
    parsed_object = _coerce_parsed_object(parsed_payload)
    if parsed_object is not None:
        return parsed_object

    response_text = str(getattr(response, "text", "") or "").strip()
    if not response_text:
        raise ValueError("Gemini SDK structured output missing parsed payload and text.")

    try:
        strict_parsed = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini SDK response.text was not valid JSON: {exc}. sample={response_text[:220]!r}"
        ) from exc

    if not isinstance(strict_parsed, dict):
        raise ValueError(
            "Gemini SDK response.text parsed as JSON but not an object."
            f" type={type(strict_parsed).__name__}"
        )
    return strict_parsed


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


def _generate_structured_object(
    *,
    runtime_settings: Optional[Dict[str, Any]],
    model_key: str,
    schema_key: str,
    system_instruction: str,
    prompt_text: str,
) -> Dict[str, Any]:
    schema = load_schema(schema_key)
    if not schema:
        raise RuntimeError(f"Schema not found for {schema_key}.")

    selected_model = _text_model(runtime_settings, model_key)
    fallback_model = str(CONFIG["models"].get("structured_fallback", "")).strip()
    models_to_try: List[str] = [selected_model]
    if fallback_model and fallback_model not in models_to_try:
        models_to_try.append(fallback_model)

    # For SDK structured output calls we intentionally avoid extra generation params
    # because gemini-3-flash-preview can drop schema mode when they are set.

    parse_errors: List[str] = []
    for model in models_to_try:
        attempts: List[Dict[str, Any]] = []
        try:
            attempts.append(
                _sdk_structured_generate(
                    model=model,
                    prompt_text=prompt_text,
                    system_instruction=system_instruction,
                    schema=schema,
                )
            )
        except Exception as exc:
            parse_errors.append(f"model={model}: request failed: {exc}")

        try:
            attempts.append(
                _sdk_structured_generate(
                    model=model,
                    prompt_text=(
                        f"{prompt_text}\n\n"
                        "Return only one valid JSON object matching the schema."
                    ),
                    system_instruction="Return strict JSON only.",
                    schema=schema,
                )
            )
        except Exception as exc:
            parse_errors.append(f"model={model}: strict retry failed: {exc}")

        for parsed_object in attempts:
            if isinstance(parsed_object, dict):
                return parsed_object

    error_summary = " | ".join(parse_errors[:4]) if parse_errors else "Unknown parse error."
    logger.warning(f"Gemini structured output parse failed [{schema_key}]: {error_summary}")
    raise ValueError(f"Could not parse a valid JSON object from model output. {error_summary}")


def extract_child_profile(
    child_profile_text: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("child_profile_extraction")
    if not template:
        return {"error": "Could not load child profile extraction prompt template."}

    prompt = ""
    try:
        prompt = format_prompt(template, {"child_profile_text": child_profile_text})
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="child_profile_extraction",
            system_instruction="You extract structured child story profile data as strict JSON.",
            prompt_text=prompt,
        )
        normalized = normalize_child_profile(parsed_output)
        persist_profile_extraction("gemini", prompt, normalized, json.dumps(parsed_output))
        return normalized
    except Exception as exc:
        logger.warning(f"Primary Gemini structured extraction failed: {exc}")
        fallback = fallback_profile_from_text(child_profile_text)
        persist_profile_extraction(
            "gemini",
            prompt or child_profile_text,
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
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="character_suggestions",
            system_instruction="Generate child-friendly character suggestions in structured JSON.",
            prompt_text=prompt,
        )
        suggestions = _sanitize_string_list(parsed_output.get("suggestions"))
        return {"suggestions": suggestions if suggestions else ["No suggestions generated."]}
    except Exception as exc:
        logger.error(f"Error generating Gemini character suggestions: {exc}")
        return {"error": f"Error generating suggestions: {exc}"}


def get_name_suggestions(
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="name_suggestions",
            system_instruction="Generate character name suggestions in structured JSON.",
            prompt_text=prompt,
        )
        names = _sanitize_string_list(parsed_output.get("names"), allow_comma_split=True)
        return {"names": names if names else ["No names generated."]}
    except Exception as exc:
        logger.error(f"Error generating Gemini name suggestions: {exc}")
        return {"error": f"Error generating names: {exc}"}


def get_plot_suggestions(
    learning_objective: str,
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="plot_suggestions",
            system_instruction="Generate plot ideas in structured JSON.",
            prompt_text=prompt,
        )
        parsed = _sanitize_string_list(parsed_output.get("plots"))
        return {"plots": parsed if parsed else ["No plot ideas generated."]}
    except Exception as exc:
        logger.error(f"Error generating Gemini plot suggestions: {exc}")
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
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="main_story_characters",
            system_instruction="Extract the main story characters and return structured JSON.",
            prompt_text=prompt,
        )
        characters = _sanitize_string_list(parsed_output.get("main_characters"))
        return {"main_characters": characters if characters else ["No main characters identified."]}
    except Exception as exc:
        logger.error(f"Error extracting Gemini main story characters: {exc}")
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
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="story_cast",
            system_instruction="Build a coherent child-friendly story cast in strict JSON.",
            prompt_text=prompt,
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
        logger.error(f"Error preparing Gemini story cast: {exc}")
        return {"error": f"Error preparing story cast: {exc}"}


def get_plot_suggestions_from_cast(
    learning_objective: str,
    theme: str,
    story_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="suggestions",
            schema_key="plot_suggestions",
            system_instruction="Generate cast-based plot options in strict JSON.",
            prompt_text=prompt,
        )
        plots = _sanitize_string_list(parsed_output.get("plots"))
        return {"plots": plots if plots else ["No plot ideas generated."]}
    except Exception as exc:
        logger.error(f"Error generating Gemini cast-based plot suggestions: {exc}")
        return {"error": f"Error generating plot ideas: {exc}"}


def identify_section_characters(
    story_section_text: str,
    story_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="sectioning",
            schema_key="page_characters",
            system_instruction="Identify which listed characters appear in the section and return strict JSON.",
            prompt_text=prompt,
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
        logger.error(f"Error identifying Gemini section characters: {exc}")
        return {"error": f"Error identifying section characters: {exc}"}


def create_image_prompt_for_section_with_characters(
    story_section_text: str,
    theme: str,
    involved_characters: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="img_prompt",
            schema_key="image_prompt",
            system_instruction="Return one concise section image prompt in strict JSON.",
            prompt_text=prompt,
        )
        image_prompt_text = _sanitize_string(parsed_output.get("image_prompt"))
        if not image_prompt_text:
            return {"error": "AI failed to generate a non-empty image prompt."}
        return {"image_prompt": image_prompt_text}
    except Exception as exc:
        logger.error(f"Error creating Gemini image prompt with characters: {exc}")
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
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="sectioning",
            schema_key="book_match_validation",
            system_instruction="Evaluate semantic alignment and return strict JSON only.",
            prompt_text=prompt,
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
        logger.error(f"Error validating Gemini book match: {exc}")
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
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="story",
            schema_key="story_text",
            system_instruction="Write a complete story and return it in structured JSON.",
            prompt_text=prompt,
        )
        story_text = _sanitize_string(parsed_output.get("story_text"))
        if len(story_text) < 50:
            return {
                "story_text": "The generated story was too short. Please try again.",
                "warning": "short_story",
            }
        return {"story_text": story_text}
    except Exception as exc:
        logger.error(f"Error generating Gemini story: {exc}")
        return {"error": f"Oops! Error generating the story: {exc}"}


def get_story_sections(
    full_story_text: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

    template = load_prompt_template("story_sectioning")
    if not template:
        return {"error": "Could not load story sectioning prompt template."}

    try:
        prompt = format_prompt(template, {"full_story_text": full_story_text})
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="sectioning",
            schema_key="story_sections",
            system_instruction="Split the story into ordered sections and return structured JSON.",
            prompt_text=prompt,
        )
        sections = _sanitize_string_list(parsed_output.get("sections"))
        if not sections:
            return {"error": "Failed to parse sections."}
        return {"sections": sections}
    except Exception as exc:
        logger.error(f"Error sectioning Gemini story: {exc}")
        return {"error": f"Error sectioning story: {exc}"}


def create_image_prompt_for_section(
    story_section_text: str,
    character_name: str,
    character_description: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

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
        parsed_output = _generate_structured_object(
            runtime_settings=runtime_settings,
            model_key="img_prompt",
            schema_key="image_prompt",
            system_instruction="Return one concise image prompt in structured JSON.",
            prompt_text=prompt,
        )
        image_prompt_text = _sanitize_string(parsed_output.get("image_prompt"))
        if not image_prompt_text:
            return {"error": "AI failed to generate a non-empty image prompt."}
        return {"image_prompt": image_prompt_text}
    except Exception as exc:
        logger.error(f"Error creating Gemini image prompt: {exc}")
        return {"error": f"Error creating image prompt: {exc}"}


def _supports_image_size(model_name: str) -> bool:
    return "gemini-3-pro-image-preview" in model_name


def _gemini_image_config(runtime_settings: Optional[Dict[str, Any]], model_name: str) -> Dict[str, Any]:
    aspect_ratio = str(
        _runtime_value(
            runtime_settings,
            "gemini_aspect_ratio",
            CONFIG["image"]["aspect_ratio"],
        )
    )
    image_size = str(
        _runtime_value(
            runtime_settings,
            "gemini_image_size",
            CONFIG["image"]["image_size"],
        )
    )

    config: Dict[str, Any] = {"aspectRatio": aspect_ratio}
    if _supports_image_size(model_name):
        config["imageSize"] = image_size
    return config


def generate_image(
    description: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

    style_prompt_template = load_prompt_template("image_style")
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{description}. {style_prompt}".strip()

    model = str(_runtime_value(runtime_settings, "image_model", CONFIG["models"]["image_gen"]))

    try:
        response_json = _generate_content(
            model=model,
            parts=[{"text": full_prompt}],
            response_modalities=["IMAGE"],
            image_config=_gemini_image_config(runtime_settings, model),
            temperature=_runtime_float(runtime_settings, "image_temperature", 1.0),
            max_output_tokens=256,
        )
        image_payload = _extract_image(response_json)
        if not image_payload:
            return {"error": "Gemini image API did not return image data.", "error_code": "invalid_response"}

        b64_data, mime_type = image_payload
        revised_prompt = _extract_text(response_json)
        return {
            "b64_json": b64_data,
            "revised_prompt": revised_prompt,
            "mime_type": mime_type,
        }
    except Exception as exc:
        logger.error(f"Error generating Gemini image: {exc}")
        return {"error": f"Failed to generate image: {exc}", "error_code": "generic_error"}


def generate_image_with_references(
    description: str,
    reference_images: List[Dict[str, Any]],
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}

    if not reference_images:
        return generate_image(description, runtime_settings=runtime_settings)

    style_prompt_template = load_prompt_template("image_style")
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{description}. {style_prompt}".strip()

    model = str(_runtime_value(runtime_settings, "image_model", CONFIG["models"]["image_gen"]))
    if "pro-image-preview" not in model:
        model = "gemini-3-pro-image-preview"
    aspect_ratio = str(_runtime_value(runtime_settings, "gemini_aspect_ratio", CONFIG["image"]["aspect_ratio"]))
    image_size = str(_runtime_value(runtime_settings, "gemini_image_size", CONFIG["image"]["image_size"]))

    contents: List[Any] = [full_prompt]
    used_reference_names: List[str] = []
    for reference in reference_images[:6]:
        if not isinstance(reference, dict):
            continue
        b64_data = _sanitize_string(reference.get("b64_json"))
        if not b64_data:
            continue
        if "," in b64_data and b64_data.lower().startswith("data:"):
            b64_data = b64_data.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64_data)
            image_obj = Image.open(io.BytesIO(raw_bytes))
            if image_obj.mode not in ("RGB", "L"):
                image_obj = image_obj.convert("RGB")
            contents.append(image_obj)
            name = _sanitize_string(reference.get("name"))
            if name:
                used_reference_names.append(name)
        except Exception as exc:
            logger.warning(f"Skipping invalid reference image for Gemini generation: {exc}")

    if len(contents) <= 1:
        return generate_image(description, runtime_settings=runtime_settings)

    image_config_kwargs: Dict[str, Any] = {"aspect_ratio": aspect_ratio}
    if _supports_image_size(model):
        image_config_kwargs["image_size"] = image_size

    config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(**image_config_kwargs),
    )

    try:
        client = _get_genai_client()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        revised_prompt_parts: List[str] = []
        output_b64 = ""
        output_mime = "image/png"

        for part in getattr(response, "parts", []) or []:
            text_part = getattr(part, "text", None)
            if text_part:
                revised_prompt_parts.append(str(text_part))

            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                raw_data = getattr(inline_data, "data", None)
                mime_type = str(getattr(inline_data, "mime_type", "") or "image/png")
                if raw_data:
                    if isinstance(raw_data, bytes):
                        output_b64 = base64.b64encode(raw_data).decode("utf-8")
                    elif isinstance(raw_data, str):
                        # Gemini SDK commonly returns base64 string here.
                        output_b64 = raw_data
                    else:
                        output_b64 = base64.b64encode(bytes(raw_data)).decode("utf-8")
                    output_mime = mime_type
                    break

            image_obj = None
            try:
                image_obj = part.as_image() if hasattr(part, "as_image") else None
            except Exception:
                image_obj = None

            if image_obj is not None:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                try:
                    image_obj.save(tmp_path)
                    with open(tmp_path, "rb") as image_file:
                        output_b64 = base64.b64encode(image_file.read()).decode("utf-8")
                    output_mime = "image/png"
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                break

        if not output_b64:
            return {
                "error": "Gemini image API did not return image data.",
                "error_code": "invalid_response",
            }

        return {
            "b64_json": output_b64,
            "mime_type": output_mime,
            "revised_prompt": " ".join(revised_prompt_parts).strip(),
            "reference_names": used_reference_names,
        }
    except Exception as exc:
        logger.error(f"Error generating Gemini image with references: {exc}")
        return {"error": f"Failed to generate image: {exc}", "error_code": "generic_error"}


def edit_image_based_on_prompt(
    base_image_b64: str,
    edit_prompt: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not is_client_ready():
        return {"error": "Gemini client not ready.", "error_code": "service_unavailable"}
    if not base_image_b64:
        return {"error": "Base image data is missing.", "error_code": "missing_base_image"}

    style_prompt_template = load_prompt_template("image_style")
    style_prompt = style_prompt_template.strip() if style_prompt_template else ""
    full_prompt = f"{edit_prompt}. {style_prompt}".strip()

    model = str(_runtime_value(runtime_settings, "image_edit_model", CONFIG["models"]["image_edit"]))

    try:
        response_json = _generate_content(
            model=model,
            parts=[
                {"text": full_prompt},
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": base_image_b64,
                    }
                },
            ],
            response_modalities=["IMAGE"],
            image_config=_gemini_image_config(runtime_settings, model),
            temperature=_runtime_float(runtime_settings, "image_temperature", 1.0),
            max_output_tokens=256,
        )
        image_payload = _extract_image(response_json)
        if not image_payload:
            return {"error": "Gemini image edit API did not return image data.", "error_code": "invalid_response"}

        b64_data, mime_type = image_payload
        return {"b64_json": b64_data, "mime_type": mime_type}
    except Exception as exc:
        logger.error(f"Error editing Gemini image: {exc}")
        return {"error": f"Failed to edit image: {exc}", "error_code": "generic_edit_error"}
