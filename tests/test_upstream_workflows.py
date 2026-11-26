"""Test the sync gate using real divergent Git histories without network access."""

from pathlib import Path
import subprocess
import sys

import pytest


GUARD = Path(__file__).resolve().parents[1] / '.github/scripts/check_upstream_workflows.py'


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


def commit(repo, path, content):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    git(repo, 'add', '--', path)
    git(repo, 'commit', '-qm', 'fixture')
    return git(repo, 'rev-parse', 'HEAD')


@pytest.fixture
def history(tmp_path):
    git(tmp_path, 'init', '-q', '-b', 'upstream')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    git(tmp_path, 'config', 'commit.gpgsign', 'false')
    git(tmp_path, 'config', 'core.autocrlf', 'false')
    commit(tmp_path, '.github/workflows/ci.yml', 'old desktop job\n')
    git(tmp_path, 'branch', 'fork')
    return tmp_path


def run_guard(repo, target):
    git(repo, 'checkout', '-q', 'fork')
    # Local cleanup must not make every ordinary upstream update require review.
    commit(repo, '.github/workflows/ci.yml', 'source tests only\n')
    return subprocess.run(
        [sys.executable, str(GUARD), target], cwd=repo,
        capture_output=True, text=True,
    )


@pytest.mark.parametrize('path', ['twitch.py', 'README.md', '.github/dependabot.yml'])
def test_application_and_other_nonworkflow_updates_are_allowed(history, path):
    target = commit(history, path, 'ordinary upstream update\n')
    result = run_guard(history, target)
    assert result.returncode == 0, result.stderr
    assert 'may continue' in result.stdout
    assert git(history, 'rev-parse', 'HEAD') != target


@pytest.mark.parametrize('operation', ['add', 'modify', 'delete', 'rename_in', 'rename_out', 'guard'])
def test_upstream_workflow_changes_stop_before_merging(history, operation):
    if operation == 'add':
        target = commit(history, '.github/workflows/extra.yaml', 'extra build\n')
    elif operation == 'modify':
        target = commit(history, '.github/workflows/ci.yml', 'new desktop job\n')
    elif operation == 'guard':
        target = commit(history, '.github/scripts/check_upstream_workflows.py', 'changed guard\n')
    else:
        if operation == 'delete':
            git(history, 'rm', '-q', '.github/workflows/ci.yml')
        elif operation == 'rename_out':
            git(history, 'mv', '.github/workflows/ci.yml', 'ci.txt')
        else:
            commit(history, 'extra.txt', 'workflow content\n')
            git(history, 'mv', 'extra.txt', '.github/workflows/extra.yml')
        git(history, 'commit', '-qm', 'fixture move or deletion')
        target = git(history, 'rev-parse', 'HEAD')
    result = run_guard(history, target)
    assert result.returncode == 1, result.stderr
    assert 'manual review' in result.stdout
    assert git(history, 'rev-parse', 'HEAD') != target


def test_missing_upstream_history_fails_closed(history):
    result = run_guard(history, 'missing-commit')
    assert result.returncode != 0
    assert 'may continue' not in result.stdout
