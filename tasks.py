"""
Invoke tasks for building open source tools across multiple platforms
Install invoke with: pip install invoke
"""

import os
import re
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import yaml
from invoke import Context, task

tasks_file_path = Path(__file__).resolve().parent
print(f"Changing directory to {tasks_file_path}")
os.chdir(tasks_file_path)

# Configuration
BUILD_DIR = Path("build").resolve()
TEST_DIR = Path("test").resolve()
DIST_DIR = Path("dist").resolve()
TOOL_REPOS_DIR = Path("tool_repos").resolve()
DEPLOY_DIR = Path("deploy").resolve()


def generate_wrapper_script(exe_name: str) -> str:
    """Generate platform-detection wrapper script"""

    # Determine if this executable needs XDG support
    needs_xdg = exe_name == "nvim"

    # Generate XDG directory creation if needed (must run before LD_LIBRARY_PATH is set)
    xdg_dirs_setup = ""
    xdg_exports = ""
    if needs_xdg:
        xdg_dirs_setup = """
            # Create XDG directories if they don't exist (before LD_LIBRARY_PATH to avoid glibc conflicts)
            mkdir -p "$platform_dir/nvim/config/nvim"
            mkdir -p "$platform_dir/nvim/share"
            mkdir -p "$platform_dir/nvim/cache"
            mkdir -p "$platform_dir/nvim/local/state"
"""
        xdg_exports = """
            # Set XDG environment variables for NeoVim configuration
            export XDG_CONFIG_HOME="$platform_dir/nvim/config"
            export XDG_DATA_HOME="$platform_dir/nvim/share"
            export XDG_CACHE_HOME="$platform_dir/nvim/cache"
            export XDG_STATE_HOME="$platform_dir/nvim/local/state"
"""

    return f"""#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
DIST_ROOT="$(dirname "$SCRIPT_DIR")"

# Platform detection loop
for platform_dir in "$DIST_ROOT"/*; do
    if [[ -d "$platform_dir" && -f "$platform_dir/detect_platform.sh" ]]; then
        platform_name=$(basename "$platform_dir")

        # Skip the bin directory itself
        if [[ "$platform_name" == "bin" ]]; then
            continue
        fi

        # Source the detect script to check if it matches
        if (cd "$platform_dir" && source detect_platform.sh); then
            # Platform match found!
{xdg_dirs_setup}
            export LD_LIBRARY_PATH="/lib64:$platform_dir/lib:$LD_LIBRARY_PATH"
{xdg_exports}
            exec "$platform_dir/bin/{exe_name}" "$@"
        fi
    fi
done

# No platform matched
echo "Error: No compatible platform found for this system" >&2
echo "Available platforms:" >&2
for platform_dir in "$DIST_ROOT"/*; do
    [[ -d "$platform_dir" && "$platform_dir" != */bin ]] && echo "  - $(basename "$platform_dir")" >&2
done
exit 1
"""


@task
def create_cache_volume(c: Context) -> None:
    c.run("docker volume create build-cache")


def get_docker_image_creation_time(c: Context, image_name: str) -> datetime | None:
    """Get the creation timestamp of a Docker image"""
    result = c.run(
        f"docker image inspect {image_name} --format='{{{{.Created}}}}'",
        hide=True,
        warn=True,
    )

    if result is not None:
        if result.ok:
            return datetime.fromisoformat(result.stdout.strip().replace("Z", "+00:00"))
        else:
            return None
    else:
        raise Exception("Internal Error")


def get_file_modification_time(filepath: str | Path) -> datetime | None:
    """Get the modification timestamp of a file"""
    path = Path(filepath)
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    else:
        return None


def should_rebuild_docker_image(
    c: Context, image_name: str, dockerfile_path: str | Path, force: bool = False
) -> bool:
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

    if dockerfile_time is None:
        raise Exception(f"Error: Cannot read '{Path.cwd()}/Dockerfile'")

    # If Dockerfile is newer than image, rebuild
    if dockerfile_time > image_time:
        print(f"Dockerfile modified at {dockerfile_time}")
        print(f"Image created at {image_time}")
        print("Dockerfile is newer than image. Will rebuild.")
        return True

    print(f"Docker image '{image_name}' is up to date. Skipping build.")
    return False


def get_available_platforms(base_dir: Path) -> list[str]:
    """Get list of available platform directories"""
    if not base_dir.exists():
        return []
    return [d.name for d in base_dir.iterdir() if d.is_dir()]


def get_tools_for_platform(
    platform: str, base_dir: str | Path, script_prefix: str
) -> list[str]:
    """Get list of available tools for a platform by scanning for build/test scripts

    Scripts must be named: {script_prefix}<tool>.<N>.sh where N is a non-negative integer
    representing the build order. Returns tools sorted by order number.
    """
    platform_dir = Path(base_dir) / platform
    if not platform_dir.exists():
        return []

    # Pattern: build_<tool>.<N>.sh or test_<tool>.<N>.sh
    pattern = re.compile(rf"^{re.escape(script_prefix)}(.+)\.(\d+)\.sh$")

    tool_order_map = {}
    for script in platform_dir.iterdir():
        match = pattern.match(script.name)
        if match:
            tool_name = match.group(1)
            order_num = int(match.group(2))

            # If tool appears multiple times, keep the one with lowest order number
            if tool_name not in tool_order_map or order_num < tool_order_map[tool_name]:
                tool_order_map[tool_name] = order_num

    # Sort by order number, then return just the tool names
    sorted_tools = sorted(tool_order_map.items(), key=lambda x: x[1])
    return [tool_name for tool_name, _ in sorted_tools]


def get_script_path_for_tool(
    platform: str, base_dir: str | Path, script_prefix: str, tool_name: str
) -> str | None:
    """Get the script filename for a specific tool

    Returns the script filename (e.g., 'build_tree-sitter.1.sh') or None if not found
    """
    platform_dir = Path(base_dir) / platform
    if not platform_dir.exists():
        return None

    # Pattern: build_<tool>.<N>.sh or test_<tool>.<N>.sh
    pattern = re.compile(rf"^{re.escape(script_prefix)}{re.escape(tool_name)}\.(\d+)\.sh$")

    # Find the script with the lowest order number for this tool
    matching_scripts = []
    for script in platform_dir.iterdir():
        match = pattern.match(script.name)
        if match:
            order_num = int(match.group(1))
            matching_scripts.append((script.name, order_num))

    if not matching_scripts:
        return None

    # Return the script with the lowest order number
    matching_scripts.sort(key=lambda x: x[1])
    return matching_scripts[0][0]


def validate_tools(
    tools_str: str | None, platform: str, base_dir: str | Path, script_prefix: str
) -> list[str] | None:
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


def validate_platforms(
    platforms_str: str | None,
    base_dir: Path,
) -> list[str] | None:
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


def build_docker_image_for_platform(
    c: Context,
    platform: str,
    base_dir: Path,
    image_prefix: str,
    force: bool = False,
) -> str:
    """Build Docker image for a specific platform if needed"""
    platform_dir = base_dir / platform
    dockerfile_path = platform_dir / "Dockerfile"
    image_name = f"{image_prefix}-{platform.lower()}"

    if should_rebuild_docker_image(c, image_name, dockerfile_path, force):
        print(f"\nBuilding Docker image for platform: {platform}")
        print(f"Dockerfile: {dockerfile_path}")
        c.run(
            f"docker build -t {image_name} -f {dockerfile_path} {platform_dir}",
            pty=True,
            echo=True,
        )
        print(f"Docker image '{image_name}' build complete!\n")

        c.run(
            f"docker run --rm "
            "-v build-cache:/cache "
            f"{image_name} "
            "/bin/mkdir -p /cache/go /cache/cargo /cache/cmake /cache/npm /cache/uv /cache/ccache",
            pty=True,
            echo=True,
        )

        post_build_script = platform_dir / "post_image_build.sh"
        if post_build_script.exists():
            c.run(
                "docker run --rm "
                "-v build-cache:/cache "
                f"-v {platform_dir}:/workspace "
                "-w /workspace "
                f"{image_name} "
                f"./{post_build_script.name}",
                pty=True,
                echo=True,
            )

    return image_name


@task
def update_repos(c: Context) -> None:
    """Clone or update tool repositories from tool_repos.yaml"""
    repos_file = Path("tool_repos.yaml")

    # Check if tool_repos.yaml exists
    if not repos_file.exists():
        print(f"Error: {repos_file} not found!")
        return

    # Create tool_repos directory if it doesn't exist
    TOOL_REPOS_DIR.mkdir(exist_ok=True)
    print(f"Using repository directory: {TOOL_REPOS_DIR}")

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

        tool_path = TOOL_REPOS_DIR / tool_name

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
        "platform": "Comma-separated list of platforms (e.g., GLIBC227,EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
    },
)
def build(
    c: Context,
    tools: str | None = None,
    platform: str | None = None,
    force_image_rebuild: bool = False,
) -> None:
    """Build specified tools for specified platforms"""

    # Get platforms - default to all if not specified
    if not platform:
        platform_list = get_available_platforms(BUILD_DIR)
        if not platform_list:
            print(f"Error: No platform directories found in {BUILD_DIR}/")
            return
        print(
            f"No platforms specified. Building for all platforms: {', '.join(platform_list)}"
        )
    else:
        platform_list = validate_platforms(platform, BUILD_DIR)
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
            c,
            platform,
            BUILD_DIR,
            "builder",
            force_image_rebuild,
        )

        for tool in tool_list:
            print(f"\n{'-' * 70}")
            print(f"Building {tool} for {platform}...")
            print(f"{'-' * 70}\n")

            # Get the build script filename for this tool
            build_script = get_script_path_for_tool(platform, BUILD_DIR, "build_", tool)
            if not build_script:
                print(f"Error: Build script not found for {tool}")
                continue

            # Run build in Docker container
            platform_dir = BUILD_DIR / platform
            c.run(
                f"docker run --rm "
                f"--cpus {subprocess.getoutput('cat /proc/cpuinfo | grep -c Processor')} "
                "-v build-cache:/cache "
                f"-v {TOOL_REPOS_DIR}:/tool_repos "
                f"-v {DEPLOY_DIR}:/deploy "
                f"-v {platform_dir}:/workspace "
                f"-w /workspace "
                f"-e PLATFORM={platform} "
                f"{image_name} "
                f"/workspace/{build_script}",
                pty=True,
                echo=True,
            )

            print(f"\n{tool} build complete for {platform}!")

            # Collect dependencies
            print(f"\n{'-' * 70}")
            print(f"Collecting dependencies for {tool} on {platform}...")
            print(f"{'-' * 70}\n")

            c.run(
                f"docker run --rm "
                f"-v {DEPLOY_DIR}:/deploy "
                f"-v {platform_dir}:/workspace "
                f"-w /workspace "
                f"{image_name} "
                f"./collect_dependencies.sh",
                pty=True,
                echo=True,
            )


@task(
    help={
        "tools": "Comma-separated list of tools to test (e.g., neovim). Default: all tools for each platform",
        "platform": "Comma-separated list of platforms (e.g., EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
    }
)
def test(
    c: Context,
    tools: str | None = None,
    platform: str | None = None,
    force_image_rebuild: bool = False,
) -> None:
    """Run tests for specified tools on specified platforms"""

    # Get platforms - default to all if not specified
    if not platform:
        platform_list = get_available_platforms(TEST_DIR)
        if not platform_list:
            print(f"Error: No platform directories found in {TEST_DIR}/")
            return
        print(
            f"No platforms specified. Testing on all platforms: {', '.join(platform_list)}"
        )
    else:
        platform_list = validate_platforms(platform, TEST_DIR)
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
            c,
            platform,
            TEST_DIR,
            image_prefix="tester",
            force=force_image_rebuild,
        )

        for tool in tool_list:
            print(f"\n{'-' * 70}")
            print(f"Testing {tool} on {platform}...")
            print(f"{'-' * 70}\n")

            # Get the test script filename for this tool
            test_script = get_script_path_for_tool(platform, TEST_DIR, "test_", tool)
            if not test_script:
                print(f"Error: Test script not found for {tool}")
                continue

            # Run tests in Docker container
            platform_dir = TEST_DIR / platform
            c.run(
                f"docker run --rm "
                f"-v {TOOL_REPOS_DIR}:/tool_repos "
                f"-v {DEPLOY_DIR}:/deploy "
                f"-v {platform_dir}:/workspace "
                f"-v {DIST_DIR}/latest:/dist "
                f"-w /workspace "
                f"{image_name} "
                f"./{test_script}",
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
def debug_build(
    c: Context, platform: str | None = None, force_image_rebuild: bool = False
) -> None:
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
        c,
        platform,
        BUILD_DIR,
        image_prefix="builder",
        force=force_image_rebuild,
    )

    # Launch interactive shell in Docker container
    platform_dir = BUILD_DIR / platform

    # Build docker command as list for exec
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-v",
        "build-cache:/cache",
        "-v",
        f"{TOOL_REPOS_DIR}:/tool_repos",
        "-v",
        f"{DEPLOY_DIR}:/deploy",
        "-v",
        f"{platform_dir}:/workspace",
        "-w",
        "/workspace",
        image_name,
        "/bin/bash",
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
def debug_test(
    c: Context, platform: str | None = None, force_image_rebuild: bool = False
) -> None:
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
        c,
        platform,
        TEST_DIR,
        image_prefix="tester",
        force=force_image_rebuild,
    )

    # Launch interactive shell in Docker container
    platform_dir = Path(TEST_DIR) / platform

    # Build docker command as list for exec
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-v",
        f"{DIST_DIR}/latest:/dist",
        "-v",
        f"{TOOL_REPOS_DIR}:/tool_repos",
        "-v",
        f"{DEPLOY_DIR}:/deploy",
        "-v",
        f"{platform_dir}:/workspace",
        "-w",
        "/workspace",
        image_name,
        "/bin/bash",
    ]

    print(f"Executing: {' '.join(docker_cmd)}")

    # Replace current process with docker
    os.execvp("docker", docker_cmd)


@task
def clean(c: Context) -> None:
    """Clean build artifacts from all platform directories"""
    print("Cleaning build artifacts...")

    for platform in get_available_platforms(BUILD_DIR):
        platform_dir = Path(BUILD_DIR) / platform
        artifacts_dir = platform_dir / "artifacts"
        if artifacts_dir.exists():
            print(f"  Cleaning {artifacts_dir}")
            c.run(f"rm -rf {artifacts_dir}/*")

    print("Clean complete!")


@task(help={"platform": "Comma-separated list of platforms to remove images for"})
def clean_docker(c: Context, platform: str | None = None) -> None:
    """Remove Docker images for specified platforms"""
    if not platform:
        # Clean all platform images
        all_platforms = set(
            get_available_platforms(BUILD_DIR) + get_available_platforms(TEST_DIR)
        )
        platforms = ",".join(all_platforms)

    platform_list = platform.split(",")

    for platform in platform_list:
        platform = platform.strip()

        # Remove builder image
        builder_image = f"builder-{platform.lower()}"
        print(f"Removing Docker image: {builder_image}")
        c.run(f"docker rmi {builder_image}", warn=True)

        # Remove tester image
        tester_image = f"tester-{platform.lower()}"
        print(f"Removing Docker image: {tester_image}")
        c.run(f"docker rmi {tester_image}", warn=True)


@task
def list_platforms(c: Context) -> None:
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
def list_tools(c: Context) -> None:
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


@task
def create_dist(c: Context) -> None:
    """Create distributable package from deploy/ directory"""

    # Read version from pyproject.toml
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found!")
        return

    with pyproject_path.open("rb") as f:
        pyproject_data = tomllib.load(f)

    version = pyproject_data.get("project", {}).get("version")
    if not version:
        print("Error: Could not find version in pyproject.toml")
        return

    print(f"Creating distribution for version {version}...")

    dist_dir = Path(f"dist/ee-linux-tools_v{version}")
    dist_bin = dist_dir / "bin"

    # Create dist directory structure
    dist_dir.mkdir(parents=True, exist_ok=True)
    dist_bin.mkdir(exist_ok=True)

    # Copy all platform builds from deploy/
    deploy_dir = Path("deploy")
    if not deploy_dir.exists():
        print(f"Error: {deploy_dir} directory not found!")
        print("Please run 'invoke build' first to create deployable builds.")
        return

    platform_count = 0
    for platform_dir in deploy_dir.iterdir():
        if platform_dir.is_dir():
            platform_name = platform_dir.name
            dest_platform = dist_dir / platform_name

            print(f"  Copying platform: {platform_name}")
            # Copy entire platform directory
            shutil.copytree(platform_dir, dest_platform, dirs_exist_ok=True)

            # Copy detect_platform.sh from build/{platform}/
            # Find matching build directory by checking PLATFORM env var in Dockerfile
            detect_found = False
            for build_platform in Path("build").iterdir():
                if build_platform.is_dir():
                    dockerfile = build_platform / "Dockerfile"
                    if dockerfile.exists():
                        with dockerfile.open() as f:
                            content = f.read()
                            # Look for ENV PLATFORM="..." in Dockerfile
                            match = re.search(
                                r'ENV\s+PLATFORM\s*=\s*["\']?([^"\'\s]+)["\']?', content
                            )
                            if match and match.group(1) == platform_name:
                                detect_script = build_platform / "detect_platform.sh"
                                if detect_script.exists():
                                    shutil.copy(
                                        detect_script,
                                        dest_platform / "detect_platform.sh",
                                    )
                                    print(
                                        f"    Copied detect_platform.sh from {build_platform.name}"
                                    )
                                    detect_found = True
                                    break

            if not detect_found:
                print(
                    f"    Warning: Could not find detect_platform.sh for platform {platform_name}"
                )

            platform_count += 1

    if platform_count == 0:
        print(f"Error: No platform directories found in {deploy_dir}/")
        print("Please run 'invoke build' first to create deployable builds.")
        return

    # Read executables.yaml and generate wrappers
    executables_file = Path("executables.yaml")
    if not executables_file.exists():
        print(f"Error: {executables_file} not found!")
        return

    with executables_file.open() as f:
        executables = yaml.safe_load(f)

    if not executables:
        print("Warning: No executables defined in executables.yaml")
        return

    print(f"\nGenerating wrapper scripts for {len(executables)} executable(s)...")
    for exe_path in executables:
        exe_name = Path(exe_path).name
        wrapper_path = dist_bin / exe_name

        # Generate wrapper script
        wrapper_content = generate_wrapper_script(exe_name)
        wrapper_path.write_text(wrapper_content)
        wrapper_path.chmod(0o755)
        print(f"  Created wrapper: bin/{exe_name}")

    print(f"\n{'=' * 70}")
    print("Distribution created successfully!")
    print(f"{'=' * 70}")
    print(f"Location: {dist_dir}")
    print(f"Platforms: {platform_count}")
    print(f"Executables: {len(executables)}")
    print("\nTo package for distribution:")
    print("  cd dist")
    print(f"  tar czf ee-linux-tools_v{version}.tar.gz ee-linux-tools_v{version}/")
    print()
