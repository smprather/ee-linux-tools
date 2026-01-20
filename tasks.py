"""
Invoke tasks for building open source tools across multiple platforms
Install invoke with: pip install invoke
"""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from invoke import task

# Configuration
BUILD_DIR = "build"
TEST_DIR = "test"


@task
def create_cache_volume(c):
    c.run("docker volume create build-cache")


def get_docker_image_creation_time(c, image_name):
    """Get the creation timestamp of a Docker image"""
    result = c.run(
        f"docker image inspect {image_name} --format='{{{{.Created}}}}'",
        hide=True,
        warn=True,
    )
    if result.ok:
        return datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
    return None


def get_file_modification_time(filepath):
    """Get the modification timestamp of a file"""
    path = Path(filepath)
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return None


def should_rebuild_docker_image(c, image_name, dockerfile_path, force=False):
    """Determine if Docker image needs to be rebuilt (make-like behavior)"""
    if force:
        print(f"Force rebuild requested for '{image_name}'")
        return True

    # Check if Dockerfile exists
    dockerfile = Path(dockerfile_path)
    if not dockerfile.exists():
        print(f"Error: {dockerfile_path} not found!")
        return False

    # Get Docker image creation time
    image_time = get_docker_image_creation_time(c, image_name)

    # If image doesn't exist, build it
    if image_time is None:
        print(f"Docker image '{image_name}' does not exist. Will build.")
        return True

    # Get Dockerfile modification time
    dockerfile_time = get_file_modification_time(dockerfile_path)

    # If Dockerfile is newer than image, rebuild
    if dockerfile_time > image_time:
        print(f"Dockerfile modified at {dockerfile_time}")
        print(f"Image created at {image_time}")
        print("Dockerfile is newer than image. Will rebuild.")
        return True

    print(f"Docker image '{image_name}' is up to date. Skipping build.")
    return False


def get_available_platforms(base_dir):
    """Get list of available platform directories"""
    base_path = Path(base_dir)
    if not base_path.exists():
        return []
    return [d.name for d in base_path.iterdir() if d.is_dir()]


def get_tools_for_platform(platform, base_dir, script_prefix):
    """Get list of available tools for a platform by scanning for build/test scripts"""
    platform_dir = Path(base_dir) / platform
    if not platform_dir.exists():
        return []

    tools = []
    for script in platform_dir.iterdir():
        if script.name.startswith(script_prefix) and script.name.endswith(".sh"):
            # Extract tool name from script filename
            # e.g., "build_neovim.sh" -> "neovim"
            tool_name = script.name[len(script_prefix) : -3]
            tools.append(tool_name)

    return sorted(tools)


def validate_tools(tools_str, platform, base_dir, script_prefix):
    """Validate and parse the tools argument for a specific platform"""
    available_tools = get_tools_for_platform(platform, base_dir, script_prefix)

    if not available_tools:
        print(
            f"Warning: No {script_prefix}*.sh scripts found in {base_dir}/{platform}/"
        )
        return []

    # If no tools specified, return all available tools
    if not tools_str:
        return available_tools

    tools = [t.strip() for t in tools_str.split(",")]
    invalid_tools = [t for t in tools if t not in available_tools]

    if invalid_tools:
        print(
            f"Error: Invalid tools for platform {platform}: {', '.join(invalid_tools)}"
        )
        print(f"Available tools: {', '.join(available_tools)}")
        return None

    return tools


def validate_platforms(platforms_str, base_dir):
    """Validate and parse the platforms argument"""
    if not platforms_str:
        return []

    available_platforms = get_available_platforms(base_dir)

    if not available_platforms:
        print(f"Error: No platform directories found in {base_dir}/")
        return None

    platforms = [p.strip() for p in platforms_str.split(",")]
    invalid_platforms = [p for p in platforms if p not in available_platforms]

    if invalid_platforms:
        print(f"Error: Invalid platforms: {', '.join(invalid_platforms)}")
        print(f"Valid platforms in {base_dir}/: {', '.join(available_platforms)}")
        return None

    return platforms


def build_docker_image_for_platform(c, platform, base_dir, force=False):
    """Build Docker image for a specific platform if needed"""
    platform_dir = Path(base_dir) / platform
    dockerfile_path = platform_dir / "Dockerfile"
    image_name = f"builder-{platform.lower()}"

    if should_rebuild_docker_image(c, image_name, dockerfile_path, force):
        print(f"\nBuilding Docker image for platform: {platform}")
        print(f"Dockerfile: {dockerfile_path}")
        c.run(
            f"docker build -t {image_name} -f {dockerfile_path} {platform_dir}",
            pty=True,
            echo=True,
        )
        print(f"Docker image '{image_name}' build complete!\n")

    return image_name


@task
def update_repos(c):
    """Clone or update tool repositories from tool_repos.yaml"""
    import yaml

    repos_dir = Path("tool_repos")
    repos_file = Path("tool_repos.yaml")

    # Check if tool_repos.yaml exists
    if not repos_file.exists():
        print(f"Error: {repos_file} not found!")
        return

    # Create tool_repos directory if it doesn't exist
    repos_dir.mkdir(exist_ok=True)
    print(f"Using repository directory: {repos_dir.absolute()}")

    # Read tool_repos.yaml
    with repos_file.open() as f:
        repos = yaml.safe_load(f)

    if not repos:
        print("No repositories defined in tool_repos.yaml")
        return

    print(f"Found {len(repos)} repository/repositories to process\n")

    # Clone or update each repository
    for tool_name, repo_info in repos.items():
        url = repo_info.get("url")
        branch = repo_info.get("branch", "main")

        if not url:
            print(f"Warning: No URL specified for {tool_name}, skipping")
            continue

        tool_path = repos_dir / tool_name

        if tool_path.exists():
            print(f"{'-' * 70}")
            print(f"Updating {tool_name}...")
            print(f"{'-' * 70}")
            c.run(f"cd {tool_path} && git pull", pty=True)
        else:
            print(f"{'-' * 70}")
            print(f"Cloning {tool_name} from {url} (branch: {branch})...")
            print(f"{'-' * 70}")
            c.run(f"git clone -b {branch} {url} {tool_path}", pty=True)

        print()

    print("Repository updates complete!")


@task(
    pre=[create_cache_volume, update_repos],
    help={
        "tools": "Comma-separated list of tools to build (e.g., neovim). Default: all tools for each platform",
        "platforms": "Comma-separated list of platforms (e.g., GLIBC227,EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
    },
)
def build(c, tools=None, platforms=None, force_image_rebuild=False):
    """Build specified tools for specified platforms"""

    # Get platforms - default to all if not specified
    if not platforms:
        platform_list = get_available_platforms(BUILD_DIR)
        if not platform_list:
            print(f"Error: No platform directories found in {BUILD_DIR}/")
            return
        print(
            f"No platforms specified. Building for all platforms: {', '.join(platform_list)}"
        )
    else:
        platform_list = validate_platforms(platforms, BUILD_DIR)
        if platform_list is None:
            return

    # Build for each platform and tool combination
    for platform in platform_list:
        print(f"\n{'=' * 70}")
        print(f"Platform: {platform}")
        print(f"{'=' * 70}")

        # Get tools for this platform - default to all if not specified
        tool_list = validate_tools(tools, platform, BUILD_DIR, "build_")
        if tool_list is None:
            continue

        if not tool_list:
            print(f"No build scripts found for platform {platform}. Skipping.")
            continue

        if not tools:
            print(f"Building all tools for {platform}: {', '.join(tool_list)}")

        # Build Docker image for this platform
        image_name = build_docker_image_for_platform(
            c, platform, BUILD_DIR, force_image_rebuild
        )

        for tool in tool_list:
            print(f"\n{'-' * 70}")
            print(f"Building {tool} for {platform}...")
            print(f"{'-' * 70}\n")

            # Run build in Docker container
            platform_dir = Path(BUILD_DIR) / platform
            c.run(
                f"docker run --rm "
                f"--cpus {subprocess.getoutput('cat /proc/cpuinfo | grep -c Processor')} "
                "-v build-cache:/cache "
                f"-v {Path.cwd()}/tool_repos:/tool_repos "
                f"-v {Path.cwd()}/deploy:/deploy "
                f"-v $(pwd)/{platform_dir}:/workspace "
                f"-w /workspace "
                f"{image_name} "
                f"/workspace/build_{tool}.sh",
                pty=True,
                echo=True,
            )

            print(f"\n{tool} build complete for {platform}!")


@task(
    help={
        "tools": "Comma-separated list of tools to test (e.g., neovim). Default: all tools for each platform",
        "platforms": "Comma-separated list of platforms (e.g., EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
    }
)
def test(c, tools=None, platforms=None, force_image_rebuild=False):
    """Run tests for specified tools on specified platforms"""

    # Get platforms - default to all if not specified
    if not platforms:
        platform_list = get_available_platforms(TEST_DIR)
        if not platform_list:
            print(f"Error: No platform directories found in {TEST_DIR}/")
            return
        print(
            f"No platforms specified. Testing on all platforms: {', '.join(platform_list)}"
        )
    else:
        platform_list = validate_platforms(platforms, TEST_DIR)
        if platform_list is None:
            return

    # Test for each platform and tool combination
    for platform in platform_list:
        print(f"\n{'=' * 70}")
        print(f"Platform: {platform}")
        print(f"{'=' * 70}")

        # Get tools for this platform - default to all if not specified
        tool_list = validate_tools(tools, platform, TEST_DIR, "test_")
        if tool_list is None:
            continue

        if not tool_list:
            print(f"No test scripts found for platform {platform}. Skipping.")
            continue

        if not tools:
            print(f"Testing all tools for {platform}: {', '.join(tool_list)}")

        # Build Docker image for this platform
        image_name = build_docker_image_for_platform(
            c, platform, TEST_DIR, force_image_rebuild
        )

        for tool in tool_list:
            print(f"\n{'-' * 70}")
            print(f"Testing {tool} on {platform}...")
            print(f"{'-' * 70}\n")

            # Run tests in Docker container
            platform_dir = Path(TEST_DIR) / platform
            c.run(
                f"docker run --rm "
                f"-v {Path.cwd()}/tool_repos:/tool_repos "
                f"-v {Path.cwd()}/deploy:/deploy "
                f"-v $(pwd)/{platform_dir}:/workspace "
                f"-w /workspace "
                f"{image_name} "
                f"/workspace/test_{tool}.sh",
                pty=True,
                echo=True,
            )

            print(f"\n{tool} tests complete for {platform}!")


@task(
    help={
        "platform": "Platform to debug (optional - will prompt if not provided)",
        "force_image_rebuild": "Force rebuild of Docker image",
    }
)
def debug_build(c, platform=None, force_image_rebuild=False):
    """Launch interactive debug session for a build platform"""

    # If platform not provided, prompt user to choose
    if not platform:
        available = get_available_platforms(BUILD_DIR)
        if not available:
            print(f"Error: No platform directories found in {BUILD_DIR}/")
            return

        print(f"Available platforms: {', '.join(available)}")

        # Create a simple interactive prompt
        print("\nSelect a platform:")
        for i, p in enumerate(available, 1):
            print(f"  {i}. {p}")

        try:
            choice = input("\nEnter platform number or name: ").strip()

            # Check if it's a number
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    platform = available[idx]
                else:
                    print(f"Error: Invalid selection {choice}")
                    return
            elif choice in available:
                platform = choice
            else:
                print(f"Error: Invalid platform '{choice}'")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled")
            return

    platform_list = validate_platforms(platform, BUILD_DIR)
    if platform_list is None:
        return

    platform = platform_list[0]

    print(f"\n{'=' * 70}")
    print(f"Starting debug session on build platform: {platform}...")
    print(f"{'=' * 70}\n")

    # Build Docker image for this platform
    image_name = build_docker_image_for_platform(
        c, platform, BUILD_DIR, force_image_rebuild
    )

    # Launch interactive shell in Docker container
    platform_dir = Path(BUILD_DIR) / platform
    cwd = Path.cwd()

    # Build docker command as list for exec
    docker_cmd = [
        "docker", "run", "--rm", "-it",
        "-v", "build-cache:/cache",
        "-v", f"{cwd}/tool_repos:/tool_repos",
        "-v", f"{cwd}/deploy:/deploy",
        "-v", f"{cwd}/{platform_dir}:/workspace",
        "-w", "/workspace",
        image_name,
        "/bin/bash"
    ]

    print(f"Executing: {' '.join(docker_cmd)}")

    # Replace current process with docker
    os.execvp("docker", docker_cmd)


@task(
    help={
        "platform": "Platform to debug (optional - will prompt if not provided)",
        "force_image_rebuild": "Force rebuild of Docker image",
    }
)
def debug_test(c, platform=None, force_image_rebuild=False):
    """Launch interactive debug session for a test platform"""

    # If platform not provided, prompt user to choose
    if not platform:
        available = get_available_platforms(TEST_DIR)
        if not available:
            print(f"Error: No platform directories found in {TEST_DIR}/")
            return

        print(f"Available platforms: {', '.join(available)}")

        # Create a simple interactive prompt
        print("\nSelect a platform:")
        for i, p in enumerate(available, 1):
            print(f"  {i}. {p}")

        try:
            choice = input("\nEnter platform number or name: ").strip()

            # Check if it's a number
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(available):
                    platform = available[idx]
                else:
                    print(f"Error: Invalid selection {choice}")
                    return
            elif choice in available:
                platform = choice
            else:
                print(f"Error: Invalid platform '{choice}'")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled")
            return

    platform_list = validate_platforms(platform, TEST_DIR)
    if platform_list is None:
        return

    platform = platform_list[0]

    print(f"\n{'=' * 70}")
    print(f"Starting debug session on test platform: {platform}...")
    print(f"{'=' * 70}\n")

    # Build Docker image for this platform
    image_name = build_docker_image_for_platform(
        c, platform, TEST_DIR, force_image_rebuild
    )

    # Launch interactive shell in Docker container
    platform_dir = Path(TEST_DIR) / platform
    cwd = Path.cwd()

    # Build docker command as list for exec
    docker_cmd = [
        "docker", "run", "--rm", "-it",
        "-v", f"{cwd}/tool_repos:/tool_repos",
        "-v", f"{cwd}/deploy:/deploy",
        "-v", f"{cwd}/{platform_dir}:/workspace",
        "-w", "/workspace",
        image_name,
        "/bin/bash"
    ]

    print(f"Executing: {' '.join(docker_cmd)}")

    # Replace current process with docker
    os.execvp("docker", docker_cmd)


@task
def clean(c):
    """Clean build artifacts from all platform directories"""
    print("Cleaning build artifacts...")

    for platform in get_available_platforms(BUILD_DIR):
        platform_dir = Path(BUILD_DIR) / platform
        artifacts_dir = platform_dir / "artifacts"
        if artifacts_dir.exists():
            print(f"  Cleaning {artifacts_dir}")
            c.run(f"rm -rf {artifacts_dir}/*")

    print("Clean complete!")


@task(help={"platforms": "Comma-separated list of platforms to remove images for"})
def clean_docker(c, platforms=None):
    """Remove Docker images for specified platforms"""
    if not platforms:
        # Clean all platform images
        all_platforms = set(
            get_available_platforms(BUILD_DIR) + get_available_platforms(TEST_DIR)
        )
        platforms = ",".join(all_platforms)

    platform_list = platforms.split(",")

    for platform in platform_list:
        image_name = f"builder-{platform.strip().lower()}"
        print(f"Removing Docker image: {image_name}")
        c.run(f"docker rmi {image_name}", warn=True)


@task
def list_platforms(c):
    """List all available platforms"""
    build_platforms = get_available_platforms(BUILD_DIR)
    test_platforms = get_available_platforms(TEST_DIR)

    print("\n=== Available Platforms ===\n")
    print("Build platforms:")
    for p in build_platforms:
        print(f"  - {p}")

    print("\nTest platforms:")
    for p in test_platforms:
        print(f"  - {p}")
    print()


@task
def list_tools(c):
    """List all available tools per platform"""
    print("\n=== Available Tools ===\n")

    print("Build tools by platform:")
    for platform in get_available_platforms(BUILD_DIR):
        tools = get_tools_for_platform(platform, BUILD_DIR, "build_")
        if tools:
            print(f"  {platform}: {', '.join(tools)}")
        else:
            print(f"  {platform}: (no build scripts found)")

    print("\nTest tools by platform:")
    for platform in get_available_platforms(TEST_DIR):
        tools = get_tools_for_platform(platform, TEST_DIR, "test_")
        if tools:
            print(f"  {platform}: {', '.join(tools)}")
        else:
            print(f"  {platform}: (no test scripts found)")
    print()
