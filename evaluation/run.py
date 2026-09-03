from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import httpx
import yaml

from app.services.badge_prompt import build_badge_prompt
from app.services.model_output import extract_json_from_response
from app.prompts.badge_options import (
    CRITERION_TEMPLATES,
    LEVEL_DESCRIPTIONS,
    STYLE_DESCRIPTIONS,
    SUPPORTED_LANGUAGES,
    TONE_DESCRIPTIONS,
)


ROOT = Path(__file__).resolve().parents[1]
METRIC_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_count",
    "prompt_eval_duration",
    "eval_count",
    "eval_duration",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_from_root(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("Evaluation config must be a YAML object")
    return config


def comparable_config(config: Mapping[str, Any]) -> Dict[str, Any]:
    """Ignore removed presentation-only options when resuming older campaigns."""
    normalized = json.loads(json.dumps(config))
    experiment = normalized.get("experiment")
    if isinstance(experiment, dict):
        experiment.pop("blinding_seed", None)
    return normalized


def validate_config(config: Mapping[str, Any]) -> None:
    required_sections = ("experiment", "ollama", "dataset", "models", "generation", "badge", "prompt")
    missing = [name for name in required_sections if name not in config]
    if missing:
        raise ValueError(f"Missing config sections: {', '.join(missing)}")

    experiment_id = str(config["experiment"].get("id", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", experiment_id):
        raise ValueError("experiment.id may contain only letters, digits, dot, underscore and dash")

    models = normalize_models(config["models"])
    if not models:
        raise ValueError("At least one model is required")

    generation = config["generation"]
    seeds = generation.get("seeds")
    if not isinstance(seeds, list) or not seeds or not all(isinstance(seed, int) for seed in seeds):
        raise ValueError("generation.seeds must be a non-empty list of integers")

    badge = config["badge"]
    explicit_badge_fields = (
        "language",
        "badge_style",
        "badge_tone",
        "criterion_style",
        "badge_level",
        "institution",
        "custom_instructions",
    )
    missing_badge = [field for field in explicit_badge_fields if field not in badge]
    if missing_badge:
        raise ValueError(f"Missing explicit badge fields: {', '.join(missing_badge)}")
    non_empty_fields = (
        "language",
        "badge_style",
        "badge_tone",
        "criterion_style",
        "badge_level",
    )
    empty_badge = [field for field in non_empty_fields if not str(badge[field]).strip()]
    if empty_badge:
        raise ValueError(f"These badge fields cannot be empty: {', '.join(empty_badge)}")


def normalize_models(raw_models: Sequence[Any]) -> List[str]:
    result: List[str] = []
    for item in raw_models:
        name = item if isinstance(item, str) else item.get("name") if isinstance(item, dict) else None
        if not name or not str(name).strip():
            raise ValueError(f"Invalid model entry: {item!r}")
        result.append(str(name).strip())
    if len(result) != len(set(result)):
        raise ValueError("Model names must be unique")
    return result


def serialize_course_plan(plan: Mapping[str, Any], serializer: str) -> str:
    if serializer != "deterministic_json":
        raise ValueError(f"Unsupported dataset serializer: {serializer}")
    return json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=2)


def load_dataset(pattern: str, serializer: str, limit: Optional[int]) -> List[Dict[str, Any]]:
    files = sorted(ROOT.glob(pattern))
    if limit is not None:
        files = files[:limit]
    if not files:
        raise ValueError(f"No course plans found with pattern: {pattern}")

    cases: List[Dict[str, Any]] = []
    for path in files:
        with path.open("r", encoding="utf-8") as stream:
            plan = json.load(stream)
        course = plan.get("course") or {}
        course_id = str(plan.get("document_id") or course.get("code") or path.stem)
        course_name = str(course.get("name") or course_id)
        source_institution = str(plan.get("institution") or "").strip() or None
        serialized = serialize_course_plan(plan, serializer)
        cases.append(
            {
                "course_id": course_id,
                "course_name": course_name,
                "source_institution": source_institution,
                "source_path": str(path.relative_to(ROOT)),
                "serialized": serialized,
                "input_sha256": sha256_text(serialized),
            }
        )
    return cases


def institution_for_case(case: Mapping[str, Any], config: Mapping[str, Any]) -> Optional[str]:
    """Prefer the plan issuer and use the configured institution only as a fallback."""
    source_institution = str(case.get("source_institution") or "").strip()
    configured_institution = str(config["badge"].get("institution") or "").strip()
    return source_institution or configured_institution or None


def prompt_for_case(case: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    badge = config["badge"]
    language_code = str(badge["language"]).lower()
    language = SUPPORTED_LANGUAGES.get(language_code)
    if not language:
        available = ", ".join(sorted(SUPPORTED_LANGUAGES))
        raise ValueError(f"Unsupported badge.language '{language_code}'. Available: {available}")

    badge_params = {
        "badge_style": str(badge["badge_style"]),
        "badge_tone": str(badge["badge_tone"]),
        "criterion_style": str(badge["criterion_style"]),
        "badge_level": str(badge["badge_level"]),
    }
    return build_badge_prompt(
        course_input=str(case["serialized"]),
        language=language,
        badge_params=badge_params,
        style_descriptions=STYLE_DESCRIPTIONS,
        tone_descriptions=TONE_DESCRIPTIONS,
        level_descriptions=LEVEL_DESCRIPTIONS,
        criterion_templates=CRITERION_TEMPLATES,
        badge_style=badge_params["badge_style"],
        institution=institution_for_case(case, config),
        custom_instructions=str(badge["custom_instructions"]) or None,
    )


def output_checks(raw_output: str, parsed: Mapping[str, Any]) -> Dict[str, Any]:
    try:
        strict_value = json.loads(raw_output)
        strict_json = isinstance(strict_value, dict)
    except (json.JSONDecodeError, TypeError):
        strict_json = False

    criteria = parsed.get("criteria")
    narrative = criteria.get("narrative") if isinstance(criteria, dict) else None
    badge_name = parsed.get("badge_name")
    description = parsed.get("badge_description")
    required_structure = (
        isinstance(badge_name, str)
        and bool(badge_name.strip())
        and isinstance(description, str)
        and bool(description.strip())
        and isinstance(narrative, str)
        and bool(narrative.strip())
    )
    return {
        "strict_json": strict_json,
        "parser_recovered_json": isinstance(parsed, dict) and "error" not in parsed,
        "required_structure": required_structure,
        "badge_name_words": len(badge_name.split()) if isinstance(badge_name, str) else 0,
    }


def derive_performance(metrics: Mapping[str, Any], wall_time_seconds: float) -> Dict[str, Any]:
    eval_count = metrics.get("eval_count") or 0
    eval_seconds = (metrics.get("eval_duration") or 0) / 1_000_000_000
    prompt_count = metrics.get("prompt_eval_count") or 0
    prompt_seconds = (metrics.get("prompt_eval_duration") or 0) / 1_000_000_000
    return {
        "wall_time_seconds": wall_time_seconds,
        "generation_tokens_per_second": eval_count / eval_seconds if eval_seconds else None,
        "prompt_tokens_per_second": prompt_count / prompt_seconds if prompt_seconds else None,
    }


def git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


async def ollama_metadata(client: httpx.AsyncClient) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    version: Optional[str] = None
    models: List[Dict[str, Any]] = []
    version_response = await client.get("/api/version")
    version_response.raise_for_status()
    version = version_response.json().get("version")
    tags_response = await client.get("/api/tags")
    tags_response.raise_for_status()
    models = tags_response.json().get("models") or []
    return version, models


def find_model_metadata(models: Iterable[Mapping[str, Any]], model_name: str) -> Optional[Mapping[str, Any]]:
    for model in models:
        if model.get("name") == model_name or model.get("model") == model_name:
            return model
    return None


async def pull_model(client: httpx.AsyncClient, model_name: str) -> None:
    print(f"Baixando {model_name}...", flush=True)
    response = await client.post(
        "/api/pull",
        json={"model": model_name, "stream": False},
        timeout=None,
    )
    response.raise_for_status()


async def loaded_model_resources(client: httpx.AsyncClient, model_name: str) -> Dict[str, Any]:
    try:
        response = await client.get("/api/ps")
        response.raise_for_status()
    except httpx.HTTPError:
        return {}
    loaded = find_model_metadata(response.json().get("models") or [], model_name)
    if not loaded:
        return {}
    return {
        "ollama_loaded_size_bytes": loaded.get("size"),
        "ollama_size_vram_bytes": loaded.get("size_vram"),
        "expires_at": loaded.get("expires_at"),
    }


async def generate(
    client: httpx.AsyncClient,
    *,
    model_name: str,
    system_prompt: str,
    prompt: str,
    options: Mapping[str, Any],
    keep_alive: str,
) -> Tuple[str, Dict[str, Any], float]:
    started = time.perf_counter()
    response = await client.post(
        "/api/generate",
        json={
            "model": model_name,
            "system": system_prompt,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "options": dict(options),
        },
    )
    response.raise_for_status()
    elapsed = time.perf_counter() - started
    body = response.json()
    raw_output = str(body.get("response") or "").strip()
    metrics = {field: body.get(field) for field in METRIC_FIELDS}
    if body.get("done_reason") is not None:
        metrics["done_reason"] = body.get("done_reason")
    return raw_output, metrics, elapsed


def completed_keys(results_path: Path) -> set[Tuple[str, str, int]]:
    completed: set[Tuple[str, str, int]] = set()
    if not results_path.exists():
        return completed
    with results_path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("status") == "success":
                completed.add((record["course_id"], record["model"], int(record["seed"])))
    return completed


async def run_experiment(args: argparse.Namespace) -> Optional[Path]:
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    validate_config(config)

    all_models = normalize_models(config["models"])
    models = args.model or all_models
    unknown_models = sorted(set(models) - set(all_models))
    if unknown_models:
        raise ValueError(f"--model not present in config: {', '.join(unknown_models)}")

    dataset = load_dataset(
        str(config["dataset"]["glob"]),
        str(config["dataset"].get("serializer", "deterministic_json")),
        args.limit,
    )
    seeds = list(config["generation"]["seeds"])
    total = len(models) * len(dataset) * len(seeds)
    print(f"Experimento: {config['experiment']['id']}")
    print(f"Modelos: {len(models)} | planos: {len(dataset)} | seeds: {len(seeds)} | gerações: {total}")
    if args.dry_run:
        return None

    output_root = resolve_from_root(str(config["experiment"].get("output_dir", "evaluation/results")))
    result_dir = output_root / str(config["experiment"]["id"])
    results_path = result_dir / "runs.jsonl"
    if result_dir.exists() and results_path.exists() and not args.resume:
        raise FileExistsError(
            f"Results already exist at {results_path}. Use --resume or change experiment.id."
        )
    result_dir.mkdir(parents=True, exist_ok=True)
    config_snapshot = result_dir / "config.yaml"
    if config_snapshot.exists():
        saved_config = load_config(config_snapshot)
        if comparable_config(saved_config) != comparable_config(config):
            raise ValueError(
                "The config differs from this experiment's config.yaml. "
                "Restore it or use a new experiment.id to avoid mixing results."
            )
    else:
        shutil.copyfile(config_path, config_snapshot)

    system_prompt_path = resolve_from_root(str(config["prompt"]["system_prompt_path"]))
    system_prompt = system_prompt_path.read_text(encoding="utf-8").strip()
    system_prompt_hash = sha256_text(system_prompt)
    config_hash = sha256_text(json.dumps(config, ensure_ascii=False, sort_keys=True))
    completed = completed_keys(results_path) if args.resume else set()

    ollama_config = config["ollama"]
    timeout = httpx.Timeout(float(ollama_config.get("timeout_seconds", 600)))
    base_url = str(ollama_config.get("base_url", "http://localhost:11434")).rstrip("/")
    keep_alive = str(ollama_config.get("keep_alive", "30m"))
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        version, installed = await ollama_metadata(client)
        missing = [name for name in models if find_model_metadata(installed, name) is None]
        if missing and not args.pull:
            joined = ", ".join(missing)
            raise RuntimeError(f"Models not installed: {joined}. Re-run with --pull to download them.")
        for model_name in missing:
            await pull_model(client, model_name)
        if missing:
            _, installed = await ollama_metadata(client)

        common_options = {
            key: value
            for key, value in config["generation"].items()
            if key != "seeds"
        }
        commit = git_commit()
        sequence = 0
        with results_path.open("a", encoding="utf-8") as output:
            for model_name in models:
                model_meta = find_model_metadata(installed, model_name) or {}
                pending_for_model = any(
                    (case["course_id"], model_name, seed) not in completed
                    for case in dataset
                    for seed in seeds
                )
                if pending_for_model and ollama_config.get("warmup", True):
                    print(f"Aquecendo {model_name}...", flush=True)
                    await generate(
                        client,
                        model_name=model_name,
                        system_prompt=system_prompt,
                        prompt="Responda apenas OK.",
                        options={"temperature": 0, "num_predict": 1},
                        keep_alive=keep_alive,
                    )

                for case in dataset:
                    prompt = prompt_for_case(case, config)
                    for seed in seeds:
                        key = (case["course_id"], model_name, seed)
                        if key in completed:
                            print(f"[skip] {model_name} | {case['course_id']} | seed {seed}")
                            continue
                        sequence += 1
                        print(
                            f"[{sequence}/{total}] {model_name} | {case['course_id']} | seed {seed}",
                            flush=True,
                        )
                        options = dict(common_options)
                        options["seed"] = seed
                        record: Dict[str, Any] = {
                            "experiment_id": config["experiment"]["id"],
                            "run_id": str(uuid.uuid4()),
                            "started_at": utc_now(),
                            "git_commit": commit,
                            "config_sha256": config_hash,
                            "ollama_version": version,
                            "model": model_name,
                            "model_digest": model_meta.get("digest"),
                            "model_size_bytes": model_meta.get("size"),
                            "model_details": model_meta.get("details"),
                            "course_id": case["course_id"],
                            "course_name": case["course_name"],
                            "source_institution": case["source_institution"],
                            "effective_institution": institution_for_case(case, config),
                            "source_path": case["source_path"],
                            "input_sha256": case["input_sha256"],
                            "system_prompt_sha256": system_prompt_hash,
                            "prompt_sha256": sha256_text(prompt),
                            "seed": seed,
                            "think": False,
                            "parameters": options,
                        }
                        try:
                            raw, metrics, wall_time = await generate(
                                client,
                                model_name=model_name,
                                system_prompt=system_prompt,
                                prompt=prompt,
                                options=options,
                                keep_alive=keep_alive,
                            )
                            parsed = extract_json_from_response(raw)
                            record.update(
                                {
                                    "status": "success",
                                    "raw_output": raw,
                                    "parsed_output": parsed,
                                    "checks": output_checks(raw, parsed),
                                    "ollama_metrics": metrics,
                                    "performance": derive_performance(metrics, wall_time),
                                    "resources": await loaded_model_resources(client, model_name),
                                }
                            )
                        except Exception as exc:
                            record.update(
                                {
                                    "status": "error",
                                    "error_type": type(exc).__name__,
                                    "error": str(exc),
                                }
                            )
                            print(f"  erro: {type(exc).__name__}: {exc}", file=sys.stderr)
                        output.write(json.dumps(record, ensure_ascii=False) + "\n")
                        output.flush()

    from evaluation.report import generate_reports

    generate_reports(results_path)
    return result_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare Ollama models on structured course plans")
    parser.add_argument("--config", default="evaluation/models.yaml", help="YAML experiment config")
    parser.add_argument("--model", action="append", help="Run only this configured model; repeat as needed")
    parser.add_argument("--limit", type=int, help="Use only the first N course plans")
    parser.add_argument("--pull", action="store_true", help="Download missing models through Ollama")
    parser.add_argument("--resume", action="store_true", help="Skip successful runs already in runs.jsonl")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and show experiment size only")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result_dir = asyncio.run(run_experiment(args))
    except (ValueError, RuntimeError, FileExistsError, OSError, httpx.HTTPError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if result_dir is not None:
        print(f"Resultados: {result_dir}")
        print(f"Comparação detalhada: {result_dir / 'comparison.html'}")
        print(f"Comparação em Markdown: {result_dir / 'comparison.md'}")


if __name__ == "__main__":
    main()
