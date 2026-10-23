"""Dataset-scoped descriptive summaries backed by persisted DB records."""

from app.repositories import dataset_repository, learner_repository


def get_summary(dataset_id: str, owner_id: str, workspace_id: str) -> dict | None:
    if dataset_id == "all":
        datasets = dataset_repository.list_all_owned_datasets(
            owner_id=owner_id, workspace_id=workspace_id
        )
        processed_ids = [
            row["id"] for row in datasets
            if row.get("status") == "processed" and isinstance(row.get("id"), str)
        ]
        summaries = dataset_repository.get_dashboard_summaries(processed_ids)
        by_id = {row.get("dataset_id"): row for row in summaries}
        if not set(by_id).issubset(set(processed_ids)):
            raise RuntimeError("dashboard_summary_incomplete")
        zero_summary = {
            "total_learner_records": 0,
            "course_presentation_count": 0,
            "learners_with_prediction": 0,
            "low_risk_count": 0,
            "medium_risk_count": 0,
            "high_risk_count": 0,
        }
        for dataset_key in processed_ids:
            by_id.setdefault(dataset_key, {"dataset_id": dataset_key, **zero_summary})
        summaries = [by_id[key] for key in processed_ids]
        course_rows = learner_repository.list_course_insight_rows(
            "all", dataset_ids=processed_ids
        ) if processed_ids else []
        course_presentations = {
            (row.get("code_module"), row.get("code_presentation"))
            for row in course_rows
            if row.get("code_module") and row.get("code_presentation")
        }
        total = sum(int(row.get("total_learner_records") or 0) for row in summaries)
        with_prediction = sum(int(row.get("learners_with_prediction") or 0) for row in summaries)
        risk = {
            key: sum(int(row.get(f"{key}_risk_count") or 0) for row in summaries)
            for key in ("low", "medium", "high")
        }
        dataset_by_id = {row.get("id"): row for row in datasets}
        comparison = []
        for dataset_id in processed_ids:
            row = by_id[dataset_id]
            records = int(row.get("total_learner_records") or 0)
            predictions = int(row.get("learners_with_prediction") or 0)
            metadata = dataset_by_id[dataset_id]
            comparison.append({
                "dataset_id": dataset_id,
                "dataset_name": metadata.get("dataset_name") or metadata.get("filename") or "Dataset",
                "learner_course_records": records,
                "available_predictions": predictions,
                "prediction_coverage": predictions / records if records else None,
                "low_risk_count": int(row.get("low_risk_count") or 0),
                "medium_risk_count": int(row.get("medium_risk_count") or 0),
                "high_risk_count": int(row.get("high_risk_count") or 0),
            })
        return {
            "dataset_id": "all",
            "scope": "all",
            "dataset_count": len(processed_ids),
            "total_learner_records": total,
            "course_presentation_count": len(course_presentations),
            "learners_with_prediction": with_prediction,
            "prediction_coverage": with_prediction / total if total else None,
            "risk_distribution": risk if with_prediction else None,
            "dataset_comparison": comparison,
            "prediction_state": "available" if with_prediction else "not_available",
            "descriptive_statistics": {
                "learner_course_records": total,
                "course_presentations": len(course_presentations),
            },
        }

    dataset = dataset_repository.get_owned_dataset(dataset_id, owner_id, workspace_id)
    if dataset is None or dataset.get("status") != "processed":
        return None
    row = dataset_repository.get_dashboard_summary(dataset_id) or {
        "total_learner_records": 0,
        "course_presentation_count": 0,
        "learners_with_prediction": 0,
        "low_risk_count": 0,
        "medium_risk_count": 0,
        "high_risk_count": 0,
    }
    total = int(row.get("total_learner_records") or 0)
    with_prediction = int(row.get("learners_with_prediction") or 0)
    has_predictions = with_prediction > 0
    coverage = with_prediction / total if total else None
    return {
        "dataset_id": dataset_id,
        "scope": "dataset",
        "dataset_count": 1,
        "total_learner_records": total,
        "course_presentation_count": int(row.get("course_presentation_count") or 0),
        "learners_with_prediction": with_prediction,
        "prediction_coverage": coverage,
        "risk_distribution": (
            {
                "low": int(row.get("low_risk_count") or 0),
                "medium": int(row.get("medium_risk_count") or 0),
                "high": int(row.get("high_risk_count") or 0),
            }
            if has_predictions else None
        ),
        "prediction_state": "available" if has_predictions else "not_available",
        "descriptive_statistics": {
            "learner_course_records": total,
            "course_presentations": int(row.get("course_presentation_count") or 0),
        },
    }


def get_course_insights(dataset_id: str, owner_id: str, workspace_id: str) -> dict | None:
    """Aggregate real learner and latest prediction rows by course presentation."""
    if dataset_id == "all":
        datasets = dataset_repository.list_all_owned_datasets(
            owner_id=owner_id, workspace_id=workspace_id
        )
        dataset_ids = [
            row["id"] for row in datasets
            if row.get("status") == "processed" and isinstance(row.get("id"), str)
        ]
        rows = learner_repository.list_course_insight_rows(dataset_id, dataset_ids=dataset_ids)
    else:
        dataset = dataset_repository.get_owned_dataset(dataset_id, owner_id, workspace_id)
        if dataset is None or dataset.get("status") != "processed":
            return None
        rows = learner_repository.list_course_insight_rows(dataset_id)
    grouped: dict[tuple[str, str], dict] = {}
    for row in rows:
        module = str(row.get("code_module") or "").strip()
        presentation = str(row.get("code_presentation") or "").strip()
        if not module or not presentation:
            continue
        key = (module, presentation)
        item = grouped.setdefault(key, {
            "code_module": module,
            "code_presentation": presentation,
            "learner_course_records": 0,
            "learners_with_prediction": 0,
            "low_risk_count": 0,
            "medium_risk_count": 0,
            "high_risk_count": 0,
            "risk_probability_sum": 0.0,
            "risk_probability_count": 0,
        })
        item["learner_course_records"] += 1
        category = row.get("latest_risk_category")
        probability = row.get("latest_risk_probability")
        prediction_id = row.get("latest_prediction_id")
        if prediction_id:
            item["learners_with_prediction"] += 1
        if category in {"low", "medium", "high"}:
            item[f"{category}_risk_count"] += 1
        if isinstance(probability, (float, int)) and not isinstance(probability, bool):
            item["risk_probability_sum"] += float(probability)
            item["risk_probability_count"] += 1

    courses = []
    for item in grouped.values():
        scored = item["learners_with_prediction"]
        item["prediction_coverage"] = scored / item["learner_course_records"] if item["learner_course_records"] else None
        probability_count = item.pop("risk_probability_count")
        item["average_risk_probability"] = item.pop("risk_probability_sum") / probability_count if probability_count else None
        courses.append(item)
    courses.sort(key=lambda item: (item["code_module"], item["code_presentation"]))
    return {
        "dataset_id": dataset_id,
        "scope": "all" if dataset_id == "all" else "dataset",
        "learner_course_records": sum(item["learner_course_records"] for item in courses),
        "course_presentation_count": len(courses),
        "learners_with_prediction": sum(item["learners_with_prediction"] for item in courses),
        "courses": courses,
        "weekly_activity_available": False,
    }
