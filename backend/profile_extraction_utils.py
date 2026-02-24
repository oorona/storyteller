import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


def load_json_config_file(path: str) -> Optional[Dict[str, Any]]:
    if not path:
        return None

    base_dir = os.path.dirname(__file__)
    preferred_path = os.path.join(base_dir, path)
    filepath = preferred_path if os.path.exists(preferred_path) else path
    if not os.path.exists(filepath):
        return None

    try:
        with open(filepath, "r", encoding="utf-8") as input_file:
            parsed = json.load(input_file)
        return parsed if isinstance(parsed, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _split_listish_value(text: str) -> List[str]:
    normalized = str(text or "").replace("\r", "\n").strip()
    if not normalized:
        return []

    numbered = re.sub(r"(?<!\d)(\d{1,2}[.)])\s+", r"\n\1 ", normalized)
    pieces: List[str] = []
    for chunk in numbered.split("\n"):
        line = chunk.strip()
        if not line:
            continue
        line = re.sub(r"^\s*(?:[-*]+|\d{1,2}[.)])\s*", "", line).strip()
        if line:
            pieces.append(line)

    if len(pieces) <= 1 and "," in normalized:
        comma_parts = [segment.strip() for segment in normalized.split(",") if segment.strip()]
        if len(comma_parts) > 1:
            return comma_parts

    return pieces if pieces else [normalized]


def _clean_string_list(value: Any, *, min_items: int, fallback_items: List[str]) -> List[str]:
    if not isinstance(value, list):
        return fallback_items

    cleaned: List[str] = []
    for item in value:
        for text in _split_listish_value(str(item)):
            if text and text not in cleaned:
                cleaned.append(text)

    if len(cleaned) < min_items:
        for item in fallback_items:
            if item not in cleaned:
                cleaned.append(item)

    return cleaned


def normalize_child_profile(raw_data: Any) -> Dict[str, Any]:
    data = raw_data if isinstance(raw_data, dict) else {}

    child_name = str(data.get("child_name", "")).strip() or "Little Explorer"
    learning_objective = str(data.get("learning_objective", "")).strip() or "build confidence"

    keywords = _clean_string_list(
        data.get("personality_keywords"),
        min_items=3,
        fallback_items=["curious", "playful", "kind"],
    )[:8]

    themes = _clean_string_list(
        data.get("story_theme_suggestions"),
        min_items=4,
        fallback_items=[
            "magical forest",
            "ocean adventure",
            "space playground",
            "friendly animal village",
        ],
    )[:8]

    characters = _clean_string_list(
        data.get("character_suggestions"),
        min_items=5,
        fallback_items=[
            "a brave little fox",
            "a helpful moon robot",
            "a singing dolphin friend",
            "a gentle dragon cub",
            "a clever rabbit inventor",
        ],
    )[:10]

    return {
        "child_name": child_name,
        "learning_objective": learning_objective,
        "personality_keywords": keywords,
        "story_theme_suggestions": themes,
        "character_suggestions": characters,
    }


def fallback_profile_from_text(profile_text: str) -> Dict[str, Any]:
    text = (profile_text or "").strip()
    lowered = text.lower()

    name_patterns = [
        r"\b(?:my son|my daughter|my child)\s+([A-Z][a-z]+)\b",
        r"\bname(?:\s+is|:)\s*([A-Z][a-z]+)\b",
        r"\bcalled\s+([A-Z][a-z]+)\b",
    ]
    child_name = ""
    for pattern in name_patterns:
        match = re.search(pattern, text)
        if match:
            child_name = match.group(1).strip()
            break
    if not child_name:
        child_name = "Little Explorer"

    learning_objective = ""
    learn_match = re.search(r"(?:learn|learning|needs to learn)\s+([^.\n]+)", lowered)
    if learn_match:
        learning_objective = learn_match.group(1).strip().strip(",")
    if not learning_objective:
        learning_objective = "build confidence"

    keyword_candidates: List[str] = []
    likes_match = re.search(r"(?:likes|loves|enjoys|interested in)\s+([^.\n]+)", lowered)
    if likes_match:
        segment = likes_match.group(1)
        parts = re.split(r",| and ", segment)
        keyword_candidates = [part.strip() for part in parts if part.strip()]

    if len(keyword_candidates) < 3:
        keyword_candidates.extend(["curious", "kind", "playful"])
    keyword_candidates = [word for word in keyword_candidates if word][:8]

    seed = keyword_candidates[0] if keyword_candidates else "adventure"
    story_themes = [
        f"magical {seed} world",
        "friendly forest village",
        "ocean discovery trip",
        "space learning adventure",
    ]
    character_suggestions = [
        "a brave little fox",
        "a gentle dragon cub",
        "a helpful robot friend",
        "a clever rabbit inventor",
        "a playful dolphin guide",
    ]

    return normalize_child_profile(
        {
            "child_name": child_name,
            "learning_objective": learning_objective,
            "personality_keywords": keyword_candidates,
            "story_theme_suggestions": story_themes,
            "character_suggestions": character_suggestions,
        }
    )


def persist_profile_extraction(
    provider: str,
    prompt_text: str,
    structured_output: Dict[str, Any],
    raw_output_text: str,
) -> Optional[str]:
    output_dir = os.getenv("PROFILE_EXTRACTION_OUTPUT_DIR", "generated/profile_extractions")
    base_dir = os.path.dirname(__file__)
    target_dir = output_dir if os.path.isabs(output_dir) else os.path.join(base_dir, output_dir)

    try:
        os.makedirs(target_dir, exist_ok=True)
        filename = datetime.utcnow().strftime(f"{provider}_%Y%m%d_%H%M%S_%f.json")
        full_path = os.path.join(target_dir, filename)

        payload = {
            "provider": provider,
            "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "prompt": prompt_text,
            "raw_output": raw_output_text,
            "structured_output": structured_output,
        }

        with open(full_path, "w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, ensure_ascii=False, indent=2)

        return full_path
    except OSError:
        return None
