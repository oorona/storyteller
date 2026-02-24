#!/usr/bin/env python3
import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


DEFAULT_PROFILES: List[str] = [
    "My child Sophia loves frogs, taekwondo, and nature walks. She is energetic and sometimes gets nervous before sparring. I want her to learn bravery and confidence.",
    "My son Mateo likes space, robots, and building with blocks. He gets frustrated when things do not work quickly. I want him to practice patience and problem solving.",
    "My daughter Aria enjoys music, dance, and butterflies. She is kind but shy in new groups. I want her to build social confidence and make friends.",
    "My child Liam loves trucks, dinosaurs, and mud play. He has a big imagination but struggles with sharing toys. I want him to learn cooperation.",
    "My daughter Zoe likes painting, oceans, and dolphins. She gets upset when plans change suddenly. I want her to learn flexibility and calm transitions.",
    "My son Noah likes soccer, dragons, and adventure maps. He can be competitive and upset when losing. I want him to practice teamwork and sportsmanship.",
    "My child Mila loves cats, baking, and fairy tales. She sometimes avoids hard tasks. I want her to develop persistence and a growth mindset.",
    "My son Ethan likes trains, puzzles, and rainstorms. He asks many questions and worries about mistakes. I want him to be comfortable trying new things.",
]


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] if text else "item"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(text)


def decode_image_to_file(b64_data: str, output_path: Path) -> None:
    raw = base64.b64decode(b64_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        f.write(raw)


def post_json(base_url: str, endpoint: str, payload: Dict[str, Any], expect: str = "json") -> Tuple[int, Any, Dict[str, str]]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if expect == "pdf":
        headers["Accept"] = "application/pdf"
    else:
        headers["Accept"] = "application/json"

    response = requests.post(url, headers=headers, json=payload, timeout=600)
    response_headers = {k.lower(): v for k, v in response.headers.items()}

    if expect == "pdf":
        return response.status_code, response.content, response_headers

    content_type = response_headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return response.status_code, response.json(), response_headers
        except Exception:
            return response.status_code, {"error": f"Invalid JSON response: {response.text[:200]}"}, response_headers

    return response.status_code, {"error": f"Unexpected content type: {content_type}", "raw": response.text[:200]}, response_headers


def ensure_success(status_code: int, data: Any, step_name: str) -> Dict[str, Any]:
    if status_code >= 400:
        message = data.get("error") if isinstance(data, dict) else str(data)
        raise RuntimeError(f"{step_name} failed [{status_code}]: {message}")
    if not isinstance(data, dict):
        raise RuntimeError(f"{step_name} returned non-JSON object.")
    if "error" in data:
        raise RuntimeError(f"{step_name} error: {data['error']}")
    return data


def get_runtime_settings(base_url: str, provider: str) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/settings/options"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    data = response.json()
    provider_opts = (data.get("providers") or {}).get(provider) or {}
    defaults = provider_opts.get("default_settings") or {}
    defaults["provider"] = provider
    return defaults


def run_attempt(
    base_url: str,
    provider: str,
    settings: Dict[str, Any],
    profile_text: str,
    attempt_dir: Path,
    semantic_threshold: float,
    attempt_index: int,
) -> Dict[str, Any]:
    attempt_dir.mkdir(parents=True, exist_ok=True)
    write_text(attempt_dir / "input_profile.txt", profile_text)

    request_context = {"provider": provider, "settings": settings}
    write_json(attempt_dir / "request_context.json", request_context)

    # Step 1: Profile extraction
    profile_payload = {"profile_text": profile_text, **request_context}
    status, data, _ = post_json(base_url, "/profile/extract", profile_payload)
    profile_data = ensure_success(status, data, "profile_extract")
    write_json(attempt_dir / "step_01_profile_extract.json", profile_data)

    child_name = str(profile_data.get("child_name") or "Little Explorer").strip()
    learning_objective = str(profile_data.get("learning_objective") or "Build confidence").strip()
    personality_keywords = profile_data.get("personality_keywords") or []
    theme_suggestions = profile_data.get("story_theme_suggestions") or []
    character_suggestions = profile_data.get("character_suggestions") or []

    if not theme_suggestions:
        raise RuntimeError("No theme suggestions were returned.")
    if len(character_suggestions) < 2:
        raise RuntimeError("Not enough character suggestions were returned.")

    theme = theme_suggestions[0]
    selected_character_ideas = character_suggestions[:3] if len(character_suggestions) >= 3 else character_suggestions[:2]

    selection_snapshot = {
        "theme": theme,
        "selected_character_ideas": selected_character_ideas,
        "child_name": child_name,
        "learning_objective": learning_objective,
        "personality_keywords": personality_keywords,
    }
    write_json(attempt_dir / "step_02_selection.json", selection_snapshot)

    # Step 2: Cast prepare
    cast_payload = {
        "child_name": child_name,
        "child_profile_text": profile_text,
        "learning_objective": learning_objective,
        "theme": theme,
        "personality_keywords": personality_keywords,
        "selected_character_ideas": selected_character_ideas,
        **request_context,
    }
    status, data, _ = post_json(base_url, "/story/cast/prepare", cast_payload)
    cast_data = ensure_success(status, data, "story_cast_prepare")
    write_json(attempt_dir / "step_03_cast_prepare.json", cast_data)

    story_characters = cast_data.get("story_characters") or []
    child_character = cast_data.get("child_character") or {}
    if len(story_characters) < 2:
        raise RuntimeError("Prepared cast has fewer than 2 characters.")

    # Step 3: Plot from cast
    plot_payload = {
        "learning_objective": learning_objective,
        "theme": theme,
        "story_characters": [
            {
                "name": c.get("name"),
                "description": c.get("description"),
                "is_child": bool(c.get("is_child", False)),
            }
            for c in story_characters
        ],
        **request_context,
    }
    status, data, _ = post_json(base_url, "/plot/suggest-from-cast", plot_payload)
    plot_data = ensure_success(status, data, "plot_suggest_from_cast")
    write_json(attempt_dir / "step_04_plot_suggestions.json", plot_data)

    plots = plot_data.get("plots") or []
    if not plots:
        raise RuntimeError("No plots returned.")
    selected_plot = plots[min(attempt_index, len(plots) - 1)]
    write_json(attempt_dir / "step_05_selected_plot.json", {"selected_plot": selected_plot})

    # Step 4: Character reference images
    char_dir = attempt_dir / "characters"
    char_dir.mkdir(parents=True, exist_ok=True)
    character_refs: List[Dict[str, Any]] = []

    for idx, character in enumerate(story_characters, start=1):
        name = str(character.get("name") or f"Character {idx}").strip()
        description = str(character.get("description") or "Story character").strip()
        image_prompt = (
            "Create a single character portrait for a children's story. "
            f"Character: {name}. Description: {description}. "
            "One character only, clear pose, plain background."
        )
        payload = {"description": image_prompt, **request_context}
        status, image_data, _ = post_json(base_url, "/image/generate", payload)
        image_result = ensure_success(status, image_data, f"image_generate_{slugify(name)}")

        b64_json = image_result.get("b64_json")
        mime_type = image_result.get("mime_type", "image/png")
        if not b64_json:
            raise RuntimeError(f"No b64 image returned for character {name}.")

        ext = ".png"
        if "jpeg" in mime_type or "jpg" in mime_type:
            ext = ".jpg"
        elif "webp" in mime_type:
            ext = ".webp"

        image_path = char_dir / f"{idx:02d}_{slugify(name)}{ext}"
        decode_image_to_file(b64_json, image_path)

        enriched = {
            "name": name,
            "description": description,
            "is_child": bool(character.get("is_child", False)),
            "image_b64": b64_json,
            "mime_type": mime_type,
            "image_file": str(image_path.relative_to(attempt_dir)),
        }
        character_refs.append(enriched)

    write_json(attempt_dir / "step_06_character_references.json", {"story_characters": character_refs})

    # Step 5: Book generate
    child_ref = next((c for c in character_refs if c.get("is_child")), character_refs[0])
    character_description = "; ".join(f"{c['name']}: {c['description']}" for c in character_refs)
    book_payload = {
        "child_name": child_name,
        "character_name": child_ref.get("name", child_name),
        "character_description": character_description,
        "plot_choice": selected_plot,
        "learning_objective": learning_objective,
        "theme": theme,
        "personality_keywords": personality_keywords,
        "character_image_b64": child_ref.get("image_b64"),
        "story_characters": character_refs,
        **request_context,
    }
    status, book_data, _ = post_json(base_url, "/book/generate", book_payload)
    book_result = ensure_success(status, book_data, "book_generate")
    write_json(attempt_dir / "step_07_book_generate.json", book_result)

    pages = book_result.get("pages") or []
    if not pages:
        raise RuntimeError("Book generation returned no pages.")
    write_json(attempt_dir / "book_pages.json", pages)
    page_generation_traces = []
    for idx, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        page_generation_traces.append(
            {
                "page_index": idx,
                "segment_index": page.get("segment_index"),
                "segment_text": page.get("segment_text") or page.get("text"),
                "detected_character_names": page.get("detected_character_names", []),
                "matched_character_names": page.get("characters", []),
                "reference_character_names": page.get("reference_character_names", []),
                "image_prompt": page.get("image_prompt", ""),
                "generation_trace": page.get("generation_trace", {}),
                "error": page.get("error"),
            }
        )
    write_json(attempt_dir / "page_generation_traces.json", page_generation_traces)

    # Step 6: PDF export
    pdf_payload = {"child_name": child_name, "pages": pages}
    status, pdf_bytes, headers = post_json(base_url, "/book/pdf", pdf_payload, expect="pdf")
    if status >= 400:
        raise RuntimeError(f"book_pdf failed [{status}]")

    pdf_path = attempt_dir / "book.pdf"
    pdf_path.write_bytes(pdf_bytes)

    # Step 7: Semantic validation
    validation_payload = {
        "child_name": child_name,
        "learning_objective": learning_objective,
        "theme": theme,
        "selected_plot": selected_plot,
        "story_characters": [
            {
                "name": c.get("name"),
                "description": c.get("description"),
                "is_child": bool(c.get("is_child", False)),
            }
            for c in character_refs
        ],
        "pages": pages,
        **request_context,
    }
    status, validation_data, _ = post_json(base_url, "/validate/book-match", validation_payload)
    validation_result = ensure_success(status, validation_data, "validate_book_match")
    write_json(attempt_dir / "validation_semantic.json", validation_result)

    # Deterministic checks + semantic checks
    page_errors = [p.get("error") for p in pages if isinstance(p, dict) and p.get("error")]
    missing_page_images = [idx + 1 for idx, p in enumerate(pages) if not p.get("b64_json")]
    recommendation = str(validation_result.get("recommendation", "review")).lower()
    overall_score = float(validation_result.get("overall_score", 0.0))

    success = (
        len(page_errors) == 0
        and len(missing_page_images) == 0
        and recommendation != "fail"
        and overall_score >= semantic_threshold
    )

    status_payload = {
        "success": success,
        "child_name": child_name,
        "theme": theme,
        "selected_plot": selected_plot,
        "characters": [c.get("name") for c in character_refs],
        "page_count": len(pages),
        "page_errors": page_errors,
        "missing_page_images": missing_page_images,
        "semantic_recommendation": recommendation,
        "semantic_overall_score": overall_score,
        "semantic_issues": validation_result.get("issues", []),
        "pdf_file": str(pdf_path.relative_to(attempt_dir)),
        "pdf_content_type": headers.get("content-type", "application/pdf"),
    }
    write_json(attempt_dir / "status.json", status_payload)
    return status_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end API validation for story books.")
    parser.add_argument("--base-url", default="http://localhost:5001/api")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--books", type=int, default=5)
    parser.add_argument("--retry-per-book", type=int, default=1)
    parser.add_argument("--semantic-threshold", type=float, default=70.0)
    parser.add_argument("--output-dir", default="backend/generated/validation_runs")
    args = parser.parse_args()

    started = datetime.utcnow()
    run_name = started.strftime("run_%Y%m%d_%H%M%S")
    run_dir = Path(args.output_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    batch_log = run_dir / "batch.log"

    def log(message: str) -> None:
        line = f"[{datetime.utcnow().isoformat()}] {message}"
        print(line)
        with batch_log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log("Starting batch validation run")

    try:
        settings = get_runtime_settings(args.base_url, args.provider)
        log(f"Loaded runtime settings for provider={args.provider}")
    except Exception as exc:
        log(f"Failed to load runtime settings: {exc}")
        return 2

    summary: Dict[str, Any] = {
        "run_name": run_name,
        "started_utc": started.isoformat(),
        "provider": args.provider,
        "base_url": args.base_url,
        "books_requested": args.books,
        "retry_per_book": args.retry_per_book,
        "semantic_threshold": args.semantic_threshold,
        "results": [],
    }

    successes = 0
    total_attempts = 0

    for book_index in range(1, args.books + 1):
        book_dir = run_dir / f"book_{book_index:02d}"
        book_dir.mkdir(parents=True, exist_ok=True)

        profile_text = DEFAULT_PROFILES[(book_index - 1) % len(DEFAULT_PROFILES)]
        write_text(book_dir / "input_profile.txt", profile_text)

        book_result: Dict[str, Any] = {
            "book_index": book_index,
            "success": False,
            "attempts": [],
        }

        max_attempts = 1 + max(0, args.retry_per_book)
        for attempt in range(1, max_attempts + 1):
            total_attempts += 1
            attempt_dir = book_dir / f"attempt_{attempt}"
            attempt_started = time.time()
            log(f"Book {book_index}/{args.books}, attempt {attempt}/{max_attempts} started")

            try:
                attempt_status = run_attempt(
                    base_url=args.base_url,
                    provider=args.provider,
                    settings=settings,
                    profile_text=profile_text,
                    attempt_dir=attempt_dir,
                    semantic_threshold=args.semantic_threshold,
                    attempt_index=attempt - 1,
                )
                duration = round(time.time() - attempt_started, 2)
                attempt_record = {
                    "attempt": attempt,
                    "duration_seconds": duration,
                    "status": attempt_status,
                }
                book_result["attempts"].append(attempt_record)
                write_json(book_dir / f"attempt_{attempt}_status.json", attempt_record)

                if attempt_status.get("success"):
                    book_result["success"] = True
                    book_result["selected_plot"] = attempt_status.get("selected_plot")
                    book_result["characters"] = attempt_status.get("characters", [])
                    successes += 1
                    log(f"Book {book_index} succeeded on attempt {attempt}")
                    break

                log(f"Book {book_index} attempt {attempt} did not pass validation")
            except Exception as exc:
                duration = round(time.time() - attempt_started, 2)
                err = {
                    "attempt": attempt,
                    "duration_seconds": duration,
                    "success": False,
                    "error": str(exc),
                }
                book_result["attempts"].append(err)
                write_json(book_dir / f"attempt_{attempt}_status.json", err)
                write_text(attempt_dir / "error.txt", str(exc))
                log(f"Book {book_index} attempt {attempt} failed: {exc}")

        write_json(book_dir / "status.json", book_result)
        summary["results"].append(book_result)

    summary["finished_utc"] = datetime.utcnow().isoformat()
    summary["books_succeeded"] = successes
    summary["books_failed"] = args.books - successes
    summary["total_attempts"] = total_attempts
    summary["success_rate"] = round((successes / args.books) * 100.0, 2) if args.books else 0.0

    write_json(run_dir / "summary.json", summary)
    log(
        "Run completed: "
        f"{successes}/{args.books} books succeeded, total_attempts={total_attempts}, output={run_dir}"
    )

    return 0 if successes == args.books else 1


if __name__ == "__main__":
    sys.exit(main())
