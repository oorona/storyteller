import copy
import logging
import os
from typing import Any, Dict, Optional

import gemini_service
import openai_service


logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "gemini").strip().lower()

PROVIDERS = {
    "openai": openai_service,
    "gemini": gemini_service,
}

SETTINGS_OPTIONS = {
    "openai": {
        "label": "OpenAI",
        "text_models": [
            "gpt-4.1-nano",
            "gpt-4.1-mini",
            "gpt-4o-mini",
        ],
        "image_models": [
            "gpt-image-1",
        ],
        "image_edit_models": [
            "gpt-image-1",
        ],
        "image_sizes": [
            "1024x1024",
            "1024x1536",
            "1536x1024",
            "auto",
        ],
        "image_qualities": [
            "low",
            "medium",
            "high",
            "auto",
        ],
        "image_output_formats": [
            "png",
            "jpeg",
            "webp",
        ],
        "default_settings": {
            "provider": "openai",
            "text_model": "gpt-4.1-mini",
            "text_temperature": 0.7,
            "image_model": "gpt-image-1",
            "image_edit_model": "gpt-image-1",
            "image_size": "1024x1024",
            "image_edit_size": "1024x1024",
            "image_quality": "low",
            "image_edit_quality": "low",
            "image_output_format": "png",
        },
    },
    "gemini": {
        "label": "Google Gemini",
        "text_models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-3-flash-preview",
        ],
        "image_models": [
            "gemini-2.5-flash-image",
            "gemini-3-pro-image-preview",
        ],
        "image_edit_models": [
            "gemini-2.5-flash-image",
            "gemini-3-pro-image-preview",
        ],
        "gemini_aspect_ratios": [
            "1:1",
            "9:16",
            "16:9",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
        ],
        "gemini_image_sizes": [
            "1K",
            "2K",
            "4K",
        ],
        "default_settings": {
            "provider": "gemini",
            "text_model": "gemini-3-flash-preview",
            "text_temperature": 0.8,
            "image_model": "gemini-2.5-flash-image",
            "image_edit_model": "gemini-2.5-flash-image",
            "gemini_aspect_ratio": "1:1",
            "gemini_image_size": "1K",
            "image_output_format": "png",
        },
    },
}


def normalize_provider(provider: Optional[str]) -> str:
    if not provider:
        return DEFAULT_PROVIDER if DEFAULT_PROVIDER in PROVIDERS else "openai"
    normalized = provider.strip().lower()
    if normalized in PROVIDERS:
        return normalized
    return DEFAULT_PROVIDER if DEFAULT_PROVIDER in PROVIDERS else "openai"


def get_default_provider() -> str:
    return normalize_provider(DEFAULT_PROVIDER)


def get_provider_module(provider: Optional[str]):
    return PROVIDERS.get(normalize_provider(provider))


def is_provider_ready(provider: Optional[str]) -> bool:
    module = get_provider_module(provider)
    return bool(module and module.is_client_ready())


def get_provider_health() -> Dict[str, str]:
    return {
        provider_name: "ready" if module.is_client_ready() else "unavailable"
        for provider_name, module in PROVIDERS.items()
    }


def get_settings_options() -> Dict[str, Any]:
    response = {
        "default_provider": get_default_provider(),
        "providers": copy.deepcopy(SETTINGS_OPTIONS),
        "provider_health": get_provider_health(),
    }
    return response


def sanitize_runtime_settings(provider: str, runtime_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(runtime_settings, dict):
        runtime_settings = {}

    options = SETTINGS_OPTIONS.get(provider, {})
    defaults = options.get("default_settings", {})

    sanitized = dict(defaults)
    for key, value in runtime_settings.items():
        if value in (None, ""):
            continue
        sanitized[key] = value

    # Normalize numeric setting(s)
    if "text_temperature" in sanitized:
        try:
            sanitized["text_temperature"] = float(sanitized["text_temperature"])
        except (TypeError, ValueError):
            sanitized["text_temperature"] = defaults.get("text_temperature", 0.7)

    return sanitized


def _dispatch(provider: str, method_name: str, *args, runtime_settings: Optional[Dict[str, Any]] = None):
    provider_name = normalize_provider(provider)
    module = PROVIDERS.get(provider_name)
    if not module:
        return {"error": f"Unsupported provider '{provider}'.", "error_code": "invalid_provider"}

    if not module.is_client_ready():
        return {
            "error": f"{provider_name.capitalize()} client not ready.",
            "error_code": "service_unavailable",
        }

    settings = sanitize_runtime_settings(provider_name, runtime_settings)

    method = getattr(module, method_name, None)
    if not method:
        return {
            "error": f"Provider '{provider_name}' does not implement {method_name}.",
            "error_code": "provider_missing_method",
        }

    return method(*args, runtime_settings=settings)


def get_character_suggestions(
    provider: str,
    theme: str,
    type: str,
    personality_keywords,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "get_character_suggestions",
        theme,
        type,
        personality_keywords,
        runtime_settings=runtime_settings,
    )


def extract_child_profile(
    provider: str,
    child_profile_text: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "extract_child_profile",
        child_profile_text,
        runtime_settings=runtime_settings,
    )


def get_name_suggestions(
    provider: str,
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "get_name_suggestions",
        character_description,
        theme,
        runtime_settings=runtime_settings,
    )


def get_plot_suggestions(
    provider: str,
    learning_objective: str,
    character_description: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "get_plot_suggestions",
        learning_objective,
        character_description,
        theme,
        runtime_settings=runtime_settings,
    )


def get_main_story_characters(
    provider: str,
    child_name: str,
    character_name: str,
    character_description: str,
    plot_choice: str,
    learning_objective: str,
    theme: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "get_main_story_characters",
        child_name,
        character_name,
        character_description,
        plot_choice,
        learning_objective,
        theme,
        runtime_settings=runtime_settings,
    )


def prepare_story_cast(
    provider: str,
    child_name: str,
    child_profile_text: str,
    learning_objective: str,
    theme: str,
    personality_keywords,
    selected_character_ideas,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "prepare_story_cast",
        child_name,
        child_profile_text,
        learning_objective,
        theme,
        personality_keywords,
        selected_character_ideas,
        runtime_settings=runtime_settings,
    )


def get_plot_suggestions_from_cast(
    provider: str,
    learning_objective: str,
    theme: str,
    story_characters,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "get_plot_suggestions_from_cast",
        learning_objective,
        theme,
        story_characters,
        runtime_settings=runtime_settings,
    )


def generate_story(
    provider: str,
    child_name: str,
    character_name: str,
    character_description: str,
    plot_choice: str,
    learning_objective: str,
    theme: str,
    personality_keywords,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "generate_story",
        child_name,
        character_name,
        character_description,
        plot_choice,
        learning_objective,
        theme,
        personality_keywords,
        runtime_settings=runtime_settings,
    )


def get_story_sections(provider: str, full_story_text: str, runtime_settings: Optional[Dict[str, Any]] = None):
    return _dispatch(
        provider,
        "get_story_sections",
        full_story_text,
        runtime_settings=runtime_settings,
    )


def validate_book_match(
    provider: str,
    child_name: str,
    learning_objective: str,
    theme: str,
    selected_plot: str,
    story_characters,
    pages,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "validate_book_match",
        child_name,
        learning_objective,
        theme,
        selected_plot,
        story_characters,
        pages,
        runtime_settings=runtime_settings,
    )


def identify_section_characters(
    provider: str,
    story_section_text: str,
    story_characters,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "identify_section_characters",
        story_section_text,
        story_characters,
        runtime_settings=runtime_settings,
    )


def create_image_prompt_for_section_with_characters(
    provider: str,
    story_section_text: str,
    theme: str,
    involved_characters,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "create_image_prompt_for_section_with_characters",
        story_section_text,
        theme,
        involved_characters,
        runtime_settings=runtime_settings,
    )


def create_image_prompt_for_section(
    provider: str,
    story_section_text: str,
    character_name: str,
    character_description: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "create_image_prompt_for_section",
        story_section_text,
        character_name,
        character_description,
        runtime_settings=runtime_settings,
    )


def generate_image(provider: str, description: str, runtime_settings: Optional[Dict[str, Any]] = None):
    return _dispatch(
        provider,
        "generate_image",
        description,
        runtime_settings=runtime_settings,
    )


def understand_image(
    provider: str,
    image_b64: str,
    mime_type: str = "image/png",
    character_name: str = "",
    character_description: str = "",
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "understand_image",
        image_b64,
        mime_type,
        character_name,
        character_description,
        runtime_settings=runtime_settings,
    )


def generate_image_with_references(
    provider: str,
    description: str,
    reference_images,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "generate_image_with_references",
        description,
        reference_images,
        runtime_settings=runtime_settings,
    )


def edit_image_based_on_prompt(
    provider: str,
    base_image_b64: str,
    edit_prompt: str,
    runtime_settings: Optional[Dict[str, Any]] = None,
):
    return _dispatch(
        provider,
        "edit_image_based_on_prompt",
        base_image_b64,
        edit_prompt,
        runtime_settings=runtime_settings,
    )
