#!/usr/bin/env python3
"""Measure agreement between current GigaChat Vision and saved editorial labels."""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

from PIL import Image

from apps.strategist.image_analysis_test import (
    IMAGE_PROMPT_VERSION,
    IMAGE_RATING_VERSION,
    SAVED_WB_CARDS,
    ImageReviewError,
    _image_prompt,
    review_image,
)
from apps.strategist.providers import GigaChatProvider

DEFAULT_DATASET = BASE_DIR / "docs/ai-knowledge/examples/wb-image-similarity-2026-11-08.csv"
DEFAULT_OUTPUT = BASE_DIR / "var/strategist-eval/image-analysis/latest.json"
VISION_MODEL = "GigaChat-2-Pro"
MAX_LIVE_CASES = 15
VERDICTS = ("recommended", "acceptable", "not_recommended")
REQUIRED_COLUMNS = {
    "article", "image_number", "filename", "sha256", "group",
    "image_rating", "rating_status", "owner_confirmed", "rating_reason",
}


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cases(dataset_path=DEFAULT_DATASET, *, media_root=None):
    if media_root is None:
        from django.conf import settings
        media_root = settings.MEDIA_ROOT
    media_root = Path(media_root)
    dataset_path = Path(dataset_path)
    with dataset_path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError("Image evaluation dataset is missing required columns")
        rows = list(reader)

    if not rows:
        raise ValueError("Image evaluation dataset is empty")
    cases = []
    case_ids = set()
    for row in rows:
        article = row["article"].strip()
        filename = row["filename"].strip()
        try:
            image_number = int(row["image_number"])
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid image number in evaluation dataset") from error
        case_id = f"{article}:{image_number:02d}"
        if not article.isdigit() or image_number < 1 or case_id in case_ids:
            raise ValueError(f"Invalid or duplicate evaluation case: {case_id}")
        if Path(filename).name != filename or not filename:
            raise ValueError(f"Unsafe image filename: {case_id}")
        if article not in SAVED_WB_CARDS:
            raise ValueError(f"Unknown product card: {article}")
        if row["image_rating"] not in VERDICTS:
            raise ValueError(f"Unknown editorial verdict: {case_id}")
        if row["owner_confirmed"].strip().lower() not in {"true", "false"}:
            raise ValueError(f"Invalid owner confirmation: {case_id}")
        category = row["group"].strip()
        if not category:
            raise ValueError(f"Missing category: {case_id}")

        path = media_root / "image-analysis-test" / article / filename
        if not path.is_file():
            raise ValueError(f"Image is missing: {case_id}")
        actual_sha256 = _sha256(path)
        if actual_sha256 != row["sha256"].strip().lower():
            raise ValueError(f"Image SHA-256 mismatch: {case_id}")

        product_name = SAVED_WB_CARDS[article]["title"]
        prompt = _image_prompt(product_name, category)
        cases.append({
            "case_id": case_id,
            "article": article,
            "image_number": image_number,
            "filename": filename,
            "path": path,
            "sha256": actual_sha256,
            "expected": row["image_rating"],
            "rating_status": row["rating_status"],
            "owner_confirmed": row["owner_confirmed"].strip().lower() == "true",
            "rating_reason": row["rating_reason"],
            "product_name": product_name,
            "category": category,
            "prompt": prompt,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        })
        case_ids.add(case_id)
    return cases


def select_cases(cases, *, limit=None, case_ids=None):
    if limit is not None and (type(limit) is not int or limit < 1):
        raise ValueError("Evaluation limit must be a positive integer")
    if case_ids is not None:
        if not case_ids or any(not isinstance(value, str) or not value.strip() for value in case_ids):
            raise ValueError("Case selection must contain nonempty IDs")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Case selection must not contain duplicates")
        known = {case["case_id"] for case in cases}
        unknown = set(case_ids) - known
        if unknown:
            raise ValueError("Unknown evaluation cases: " + ", ".join(sorted(unknown)))
        selected = [case for case in cases if case["case_id"] in case_ids]
    else:
        selected = list(cases)
    if limit is not None:
        selected = selected[:limit]
    return selected


def _public_case(case):
    return {
        key: value for key, value in case.items()
        if key not in {"path", "prompt"}
    }


def summarize(rows, *, selected):
    confusion = {
        expected: {actual: 0 for actual in (*VERDICTS, "error")}
        for expected in VERDICTS
    }
    matches = 0
    evaluated = 0
    errors = 0
    usage_rows = []
    label_groups = {
        label: {"evaluated": 0, "matches": 0, "errors": 0}
        for label in ("owner_confirmed", "editorial")
    }
    for row in rows:
        expected = row["expected"]
        actual = row.get("actual")
        group = label_groups["owner_confirmed" if row.get("owner_confirmed") else "editorial"]
        if actual in VERDICTS:
            confusion[expected][actual] += 1
            evaluated += 1
            matches += actual == expected
            group["evaluated"] += 1
            group["matches"] += actual == expected
        else:
            confusion[expected]["error"] += 1
            errors += 1
            group["errors"] += 1
        if row.get("usage") is not None:
            usage_rows.append(row["usage"])
    usage = {
        key: sum(row[key] or 0 for row in usage_rows) if usage_rows else None
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    recommended = sum(row.get("actual") == "recommended" for row in rows)
    false_recommendations = sum(
        row.get("actual") == "recommended" and row["expected"] != "recommended" for row in rows
    )
    return {
        "selected": selected,
        "completed": len(rows),
        "evaluated": evaluated,
        "errors": errors,
        "agreement": {
            "matches": matches,
            "evaluated": evaluated,
            "ratio": round(matches / evaluated, 4) if evaluated else None,
        },
        "confusion_matrix": confusion,
        "usage": usage,
        "usage_complete": bool(usage_rows) and len(usage_rows) == len(rows) and all(row.get("usage_complete", True) for row in rows) and all(
            all(isinstance(value, int) for value in row.values())
            for row in usage_rows
        ),
        "label_groups": label_groups,
        "recommendation_precision": round((recommended - false_recommendations) / recommended, 4) if recommended else None,
        "false_recommendations": false_recommendations,
        "false_rejections": sum(row.get("actual") == "not_recommended" and row["expected"] == "recommended" for row in rows),
        "manual_review_share": round(sum(row.get("actual") == "acceptable" for row in rows) / evaluated, 4) if evaluated else None,
    }


def evaluate(cases, *, live=False, output_path=DEFAULT_OUTPUT, provider_factory=None, dataset=None):
    if live and not 1 <= len(cases) <= MAX_LIVE_CASES:
        raise ValueError(f"Live evaluation requires between 1 and {MAX_LIVE_CASES} selected images")
    output_path = Path(output_path)
    if live and output_path.exists():
        raise FileExistsError("Use a new output path: existing experiments must not be overwritten")
    prompts = {}
    for case in cases:
        prompts.setdefault(case["prompt_sha256"], {
            "product_name": case["product_name"],
            "category": case["category"],
            "text": case["prompt"],
        })
    report = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live" if live else "dry-run",
        "metric": "agreement_with_dataset_labels_not_population_accuracy",
        "requested_model": VISION_MODEL,
        "prompt_version": IMAGE_PROMPT_VERSION,
        "rating_version": IMAGE_RATING_VERSION,
        "dataset": str(dataset) if dataset is not None else None,
        "dataset_sha256": _sha256(Path(dataset)) if dataset is not None else None,
        "automatic_retries": False,
        "batch_aborted": False,
        "cases": [_public_case(case) for case in cases],
        "prompts": prompts,
        "rows": [],
    }

    def save():
        report["summary"] = summarize(report["rows"], selected=len(cases))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    save()
    if not live:
        return report

    try:
        provider = (provider_factory or GigaChatProvider)()
        with provider._client() as client:
            for case in cases:
                row = _public_case(case)
                row.update({
                    "actual": None,
                    "score": None,
                    "raw_response": None,
                    "usage": None,
                    "error": None,
                    "stages": [],
                })
                file_id = None
                started = time.monotonic()
                try:
                    with Image.open(case["path"]) as source:
                        jpeg = io.BytesIO()
                        source.convert("RGB").save(jpeg, "JPEG", quality=84, optimize=True)
                    uploaded = client.upload_file(
                        (f"evaluation-{case['article']}-{case['image_number']:02d}.jpg", jpeg.getvalue(), "image/jpeg"),
                        purpose="general",
                    )
                    file_id = uploaded.id_
                    review, score, status, label, reasons = review_image(
                        client, file_id, product_name=case["product_name"], category=case["category"],
                        stages=row["stages"], model=VISION_MODEL, prompt=case["prompt"],
                    )
                    row.update({
                        "actual": status,
                        "score": score,
                        "label": label,
                        "reasons": reasons,
                        "review": review,
                        "matches_editorial": status == case["expected"],
                    })
                except ImageReviewError as error:
                    row["error"] = {"type": type(error).__name__, "message": str(error)}
                except Exception as error:
                    row["error"] = {"type": type(error).__name__}
                    report["batch_aborted"] = True
                finally:
                    if row["stages"]:
                        row["raw_response"] = row["stages"][0]["raw_response"]
                        row["response_model"] = row["stages"][0].get("response_model")
                        usages = [stage["usage"] for stage in row["stages"] if stage["usage"] is not None]
                        row["usage"] = {key: sum(usage[key] or 0 for usage in usages) for key in ("prompt_tokens", "completion_tokens", "total_tokens")} if usages else None
                        row["usage_complete"] = len(usages) == len(row["stages"]) and all(
                            all(type(value) is int for value in usage.values()) for usage in usages
                        )
                    if file_id:
                        try:
                            client.delete_file(file_id)
                        except Exception as error:
                            row["file_cleanup_error"] = type(error).__name__
                    row["seconds"] = round(time.monotonic() - started, 3)
                    report["rows"].append(row)
                    save()
                if report["batch_aborted"]:
                    break
    except Exception as error:
        report["provider_error"] = type(error).__name__
        report["batch_aborted"] = True
        save()

    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate files and write a report without API calls (default)")
    mode.add_argument("--live", action="store_true", help="Assess each image and verify candidates (up to two GigaChat Vision calls per image)")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case", dest="case_ids", action="append", help="Select article:image, for example 1221114868:01; repeatable")
    args = parser.parse_args(argv)
    if args.live and args.limit is None and not args.case_ids:
        parser.error("Live evaluation requires an explicit --limit or --case selection")
    return args


def main(argv=None):
    args = parse_args(argv)
    from django.conf import settings
    cases = load_cases(args.dataset, media_root=args.media_root or settings.MEDIA_ROOT)
    selected = select_cases(cases, limit=args.limit, case_ids=args.case_ids)
    report = evaluate(
        selected,
        live=args.live,
        output_path=args.output,
        dataset=args.dataset,
    )
    print(json.dumps({
        "mode": report["mode"],
        "output": str(args.output),
        "batch_aborted": report["batch_aborted"],
        "summary": report["summary"],
    }, ensure_ascii=False, indent=2))
    return 1 if report["batch_aborted"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
