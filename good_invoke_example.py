# In the past years, my projects included a Makefile to help with small automations needed to set up the environment I was about to work in. For those who may not know, a Makefile is a handy script that lets developers define repetitive commands and run them in a simple and convenient way. The downside of using it is that Makefiles can easily become messy, limited, and clunky, especially on Windows.
#
# As Python continues to modernize, new approaches are often welcome. I recently came across a tool that may be a useful addition to my workflow. I want to introduce Invoke, a Python-based task runner that offers the same capabilities as Make but with a more user-friendly approach.
#
# Get Matheus’s stories in your inbox
# Join Medium for free to get updates from this writer.
#
# Enter your email
# Subscribe
# This article explains what Invoke is, why it’s useful, and how you can start using it today with a real example.
#
# What Is Invoke?
# Invoke is a Python task execution library, essentially a more Pythonic replacement for Make. Instead of writing shell snippets in a Makefile, Invoke lets you define tasks using regular Python functions.
#
# Why developers use Invoke:
# It works on Linux, macOS, and Windows with no changes.
# Tasks are written in Python, not shell.
# You can organize tasks with imports, helper functions, loops, variables, and modules.
# The command-line interface is clean and intuitive:
# invoke clean
# invoke test
# invoke build
# To install it:
# pip install invoke
# Once installed, Invoke looks for a tasks.py file in your project root, just like how Make looks for a Makefile.
#
# A Real Project Example
# Let’s say you have a typical Python project structure:
#
# my-project/
# │
# ├── src/
# ├── tests/
# ├── tasks.py
# ├── pyproject.toml
# └── README.md
# Here’s the script I plan to use in every project from now on.
#
# tasks.py
import os
import platform
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional

from invoke import task


# ================ Helper Functions ================= #


def format_print(message: str) -> None:
    """Print a formatted message."""
    print(f"=============== {message} ===============")


def require(cmd: str) -> None:
    """Raise if a required CLI tool is missing."""
    print(f"→ Checking for {cmd}...")

    if shutil.which(cmd) is None:
        raise RuntimeError(f"{cmd} is not installed or not on PATH.")


def ensure_file_exists(path: Path, default_content: str = "") -> None:
    """Create a file if it does not exist."""
    if not path.exists():
        print(f"  - Creating missing file: {path}")
        path.write_text(default_content)
    else:
        print(f"  - File already exists: {path}")


def ensure_precommit_config() -> None:
    """Create a minimal .pre-commit-config.yaml if missing."""
    pre_commit_file: Path = Path(".pre-commit-config.yaml")

    default_config: str = dedent("""
    repos:
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v6.0.0
      hooks:
        - id: trailing-whitespace
          name: Trim trailing whitespace
        - id: check-yaml
          name: Validate YAML
        - id: check-json
          name: Validate JSON
        - id: check-toml
          name: Validate TOML
        - id: check-added-large-files
          name: Validate large files

    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.12.8
      hooks:
        - id: ruff
          name: Ruff Linter
          description: "Run 'ruff' for extremely fast Python linting"
          language: python
        - id: ruff-format
          name: Ruff Code Format
          description: "Run 'ruff format' for extremely fast Python formatting"
          language: python
    """)

    ensure_file_exists(pre_commit_file, default_config)


def get_poetry_env_paths(c) -> Optional[dict[str, Path]]:
    """
    Return a dict with paths for the current Poetry virtualenv:
    {
        "env_dir": Path,
        "bin_dir": Path,
        "python": Path,
        "pip": Path,
        "activate": Path
    }
    or None if Poetry env is not created yet.
    """
    result: Any = c.run("poetry env info --path", hide=True, warn=True)
    if not result.ok:
        return None

    env_dir: Path = Path(result.stdout.strip())
    system: str = platform.system()

    if system == "Windows":
        bin_dir: Path = env_dir / "Scripts"
    else:
        bin_dir: Path = env_dir / "bin"

    python: Path = bin_dir / "python"
    pip: Path = bin_dir / "pip"
    activate: Path = bin_dir / "activate"

    return {
        "env_dir": env_dir,
        "bin_dir": bin_dir,
        "python": python,
        "pip": pip,
        "activate": activate,
    }


# ================ Tasks ================= #

CLEAN_DIRS: list[str] = [
    ".venv",
    "cdk.out",
    "build",
    "dist",
    ".pytest_cache",
    "node_modules",
    ".coverage",
    ".ruff_cache",
]


@task
def clean(c):
    """Remove build artifacts and caches."""
    format_print("Clean Task")

    print("Cleaning build artifacts and caches...")
    for directory in CLEAN_DIRS:
        path: Path = Path(directory)
        if path.exists():
            print(f"  - Removing {directory}")
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)

    for path in Path(".").rglob("*.egg-info"):
        print(f"  - Removing {path}")
        shutil.rmtree(path, ignore_errors=True)

    format_print("Clean Task Done!")
    print("\n")


@task
def venv(c):
    """Create .venv from pyproject.toml using Poetry."""
    format_print("Venv Task")

    print("→ Defining Poetry configs...")
    c.run(
        "poetry config --list | grep -q 'virtualenvs.in-project = true' "
        "|| poetry config virtualenvs.in-project true",
        warn=True,
    )

    print("→ Installing dependencies with Poetry...")
    c.run("poetry install --quiet")
    print("✓ Virtual environment and dependencies ready.")

    format_print("Venv Task Done!")
    print("\n")


@task
def setup(c):
    """Setup the project environment (git, .env, pre-commit)."""
    format_print("Setup Task")

    print("→ Checking Git repository...")
    if not Path(".git").exists():
        print("  - Initializing Git repository...")
        c.run("git init")
    else:
        print("  - Git already initialized.")

    print("→ Ensuring environment files...")

    ensure_file_exists(Path(".env.template"), default_content="# ENV template\n")

    env_file = Path(".env")
    env_template = Path(".env.template")

    if not env_file.exists():
        print("  - Creating .env from .env.template")
        env_file.write_text(env_template.read_text())
    else:
        print("  - .env already exists.")

    print("→ Ensuring .pre-commit-config.yaml exists...")
    ensure_precommit_config()

    print("→ Installing pre-commit hooks...")
    c.run("pre-commit clean", warn=True)
    c.run("pre-commit autoupdate")
    c.run("pre-commit install")

    print("→ To activate your venv, run: eval $(poetry env activate)")

    format_print("Setup Task Done!")
    print("\n")


@task
def check_deps(c):
    """Check for required tools; fail fast if any are missing."""
    format_print("Check Dependencies Task")

    print("Checking required tools...")
    require("poetry")
    require("pre-commit")
    print("All required tools found.")

    format_print("Check Dependencies Done!")
    print("\n")


@task
def test(c, args=""):
    """Run pytest with coverage."""
    format_print("Test Task")

    print("Running tests with coverage...")
    cmd = (
        "poetry run pytest "
        "--cov=tests/ --cov-report=term-missing --cov-report=html "
        f"{args}"
    )
    c.run(cmd, pty=True)
    print("Tests completed.")

    format_print("Test Task Done!")
    print("\n")


@task
def up(c):
    """Start Docker compose stack."""
    format_print("Start Docker Task")

    print("Starting Docker stack...")
    c.run("docker compose up -d")
    print("Docker stack started.")

    format_print("Start Docker Done!")
    print("\n")


@task
def down(c):
    """Stop Docker compose stack and remove volumes."""
    format_print("Stop Docker Task")

    print("Stopping Docker stack...")
    c.run("docker compose down -v", warn=True)

    docker_container = os.environ.get("DOCKER_CONTAINER")
    if docker_container:
        print(f"Checking running container {docker_container}...")
        result = c.run(
            f"docker ps -q -f name={docker_container}",
            hide=True,
            warn=True,
        )
        if result.stdout.strip():
            print("  - Terminating running container...")
            c.run(f"docker rm {docker_container}", warn=True)

    print("Docker shutdown done.")

    format_print("Start Docker Done!")
    print("\n")


@task
def ruff_format(c):
    """Format code using Ruff."""
    format_print("Ruff format Task")

    print("Running: ruff format")
    c.run("ruff format", pty=True)
    print("Ruff format completed.")

    format_print("Ruff format Done!")
    print("\n")


@task
def ruff_check(c, fix=False):
    """Run Ruff linting (optionally with --fix)."""
    format_print("Ruff linter Task")

    cmd: str = "ruff check"
    if fix:
        cmd += " --fix"

    print(f"Running: {cmd}")
    c.run(cmd, pty=True)
    print("Ruff check completed.")

    format_print("Ruff linter Done!")
    print("\n")


@task
def show_info(c):
    """Show Poetry env info and paths."""
    format_print("Show Info Task")

    print(f"OS: {platform.system()}")

    env_paths = get_poetry_env_paths(c)
    if not env_paths:
        print("Poetry environment not created yet. Run: invoke venv")
        return

    print(f"Env dir: {env_paths['env_dir']}")
    print(f"Bin directory: {env_paths['bin_dir']}")
    print(f"Python path: {env_paths['python']}")
    print(f"Pip path: {env_paths['pip']}")
    print(f"Activate script: {env_paths['activate']}")

    if env_paths["python"].exists():
        c.run(f"{env_paths['python']} --version", warn=True)

    c.run("poetry --version", warn=True)
    c.run("poetry env info", warn=True)

    format_print("Show Info Done!")
    print("\n")


@task
def activate(c):
    """Print instructions on how to activate the virtual environment."""
    format_print("Activate Task")

    env_paths = get_poetry_env_paths(c)

    print("To activate the virtual environment, you can run:\n")
    print("Using Poetry (recommended, cross-platform):")
    print("   poetry shell")
    print("or:")
    print("   eval $(poetry env activate)\n")

    if env_paths:
        print("Directly via venv (if you prefer):")
        if platform.system() == "Windows":
            print(f"   {env_paths['activate']}")
        else:
            print(f"   source {env_paths['activate']}")
    else:
        print("Poetry environment not created yet. Run: invoke venv")

    format_print("Activate Done!")
    print("\n")


@task(pre=[clean, venv, setup, check_deps, show_info])
def init(c):
    """Default init target to bootstrap the project."""
    activate(c)
    print("Project initialized.")
