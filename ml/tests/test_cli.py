from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "ml.src.prepare_oulad", *map(str, args)],
        cwd=REPO_ROOT, text=True, capture_output=True, check=False,
    )


def test_cli_writes_requested_outputs_and_repeats_deterministically(sample_tables, write_tables, tmp_path):
    data_dir = write_tables(sample_tables)
    output = tmp_path / "out" / "features.csv"
    report = tmp_path / "out" / "prep.md"
    dictionary = tmp_path / "out" / "dict.csv"
    args = ["--data-dir", data_dir, "--output", output, "--report", report,
            "--feature-dictionary", dictionary, "--cutoff-day", "30", "--sample-learners", "3", "--seed", "9"]
    first = _run(*args)
    assert first.returncode == 0, first.stderr
    assert "Prepared" in first.stdout
    first_data = pd.read_csv(output)
    second = _run(*args)
    assert second.returncode == 0, second.stderr
    pd.testing.assert_frame_equal(first_data, pd.read_csv(output))
    assert report.is_file() and dictionary.is_file()


def test_cli_missing_data_fails_nonzero_with_actionable_error(tmp_path):
    result = _run("--data-dir", tmp_path / "missing", "--sample-learners", "1")
    assert result.returncode != 0
    assert "studentInfo.csv" in result.stderr
    assert "--data-dir" in result.stderr


def test_cli_rejects_invalid_cutoff_and_sample_args(tmp_path):
    negative_cutoff = _run("--data-dir", tmp_path, "--cutoff-day", "-1")
    assert negative_cutoff.returncode != 0
    assert "non-negative" in negative_cutoff.stderr
    zero_sample = _run("--data-dir", tmp_path, "--sample-learners", "0")
    assert zero_sample.returncode != 0
    assert "positive integer" in zero_sample.stderr


def test_cli_rejects_empty_csv(tmp_path, sample_tables, write_tables):
    data_dir = write_tables(sample_tables)
    (data_dir / "studentVle.csv").write_text("id_student,code_module,code_presentation,id_site,date,sum_click\n", encoding="utf-8")
    result = _run("--data-dir", data_dir, "--output", tmp_path / "f.csv", "--sample-learners", "2")
    assert result.returncode != 0
    assert "studentVle.csv is empty" in result.stderr
