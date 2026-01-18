"""
Invoke tasks for building open source tools across multiple platforms
Install invoke with: pip install invoke
"""

import os
from datetime import datetime
from pathlib import Path

from invoke import task

# Configuration
BUILD_DIR = "build"
TEST_DIR = "test"


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
    if os.path.exists(filepath):
        return datetime.fromtimestamp(os.path.getmtime(filepath))
    return None


def should_rebuild_docker_image(c, image_name, dockerfile_path, force=False):
    """Determine if Docker image needs to be rebuilt (make-like behavior)"""
    if force:
        print(f"Force rebuild requested for '{image_name}'")
        return True

    # Check if Dockerfile exists
    if not os.path.exists(dockerfile_path):
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
    if not os.path.exists(base_dir):
        return []
    return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]


def get_tools_for_platform(platform, base_dir, script_prefix):
    """Get list of available tools for a platform by scanning for build/test scripts"""
    platform_dir = os.path.join(base_dir, platform)
    if not os.path.exists(platform_dir):
        return []

    tools = []
    for filename in os.listdir(platform_dir):
        if filename.startswith(script_prefix) and filename.endswith(".sh"):
            # Extract tool name from script filename
            # e.g., "build_neovim.sh" -> "neovim"
            tool_name = filename[len(script_prefix) : -3]
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
    dockerfile_path = os.path.join(base_dir, platform, "Dockerfile")
    image_name = f"builder-{platform.lower()}"

    if should_rebuild_docker_image(c, image_name, dockerfile_path, force):
        print(f"\nBuilding Docker image for platform: {platform}")
        print(f"Dockerfile: {dockerfile_path}")
        c.run(
            f"docker build -t {image_name} -f {dockerfile_path} {os.path.join(base_dir, platform)}"
        )
        print(f"Docker image '{image_name}' build complete!\n")

    return image_name


@task(
    help={
        "tools": "Comma-separated list of tools to build (e.g., neovim). Default: all tools for each platform",
        "platforms": "Comma-separated list of platforms (e.g., GLIBC227,EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
    }
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
            platform_dir = os.path.join(BUILD_DIR, platform)
            c.run(
                f"docker run --rm "
                f"-v $(pwd)/{platform_dir}:/workspace "
                f"-w /workspace "
                f"{image_name} "
                f"/workspace/build_{tool}.sh",
                pty=True,
            )

            print(f"\n{tool} build complete for {platform}!")


@task(
    help={
        "tools": "Comma-separated list of tools to test (e.g., neovim). Default: all tools for each platform",
        "platforms": "Comma-separated list of platforms (e.g., EL7). Default: all platforms",
        "force_image_rebuild": "Force rebuild of Docker images",
        "debug": "Run in interactive debug mode with debug.sh script",
    }
)
def test(c, tools=None, platforms=None, force_image_rebuild=False, debug=False):
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

    # In debug mode, only support one platform
    if debug:
        if len(platform_list) > 1:
            print("Debug mode supports only one platform at a time.")
            print(f"Using first platform: {platform_list[0]}")
            platform_list = platform_list[:1]

    # Test for each platform and tool combination
    for platform in platform_list:
        print(f"\n{'=' * 70}")
        print(f"Platform: {platform}")
        print(f"{'=' * 70}")

        # Get tools for this platform - default to all if not specified
        if debug:
            # In debug mode, we don't need a tool list
            tool_list = []
        else:
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

        if debug:
            print(f"\n{'-' * 70}")
            print(f"Starting debug session on {platform}...")
            print(f"{'-' * 70}\n")

            # Run debug script in interactive mode
            platform_dir = os.path.join(TEST_DIR, platform)
            c.run(
                f"docker run --rm -it "
                f"-v $(pwd)/{platform_dir}:/workspace "
                f"-w /workspace "
                f"{image_name} "
                f"/workspace/debug.sh",
                pty=True,
            )
        else:
            for tool in tool_list:
                print(f"\n{'-' * 70}")
                print(f"Testing {tool} on {platform}...")
                print(f"{'-' * 70}\n")

                # Run tests in Docker container
                platform_dir = os.path.join(TEST_DIR, platform)
                c.run(
                    f"docker run --rm "
                    f"-v $(pwd)/{platform_dir}:/workspace "
                    f"-w /workspace "
                    f"{image_name} "
                    f"/workspace/test_{tool}.sh",
                    pty=True,
                )

                print(f"\n{tool} tests complete for {platform}!")


@task(
    help={
        "tools": "Tool to debug (only one supported)",
        "platforms": "Platform to debug on (only one supported)",
        "force_image_rebuild": "Force rebuild of Docker image",
    }
)
def debug(c, tools=None, platforms=None, force_image_rebuild=False):
    """Launch interactive debug session for specified tool and platform"""

    # Get platforms
    if not platforms:
        available = get_available_platforms(BUILD_DIR)
        if not available:
            print(f"Error: No platform directories found in {BUILD_DIR}/")
            return
        print(f"No platforms specified. Available: {', '.join(available)}")
        return

    platform_list = validate_platforms(platforms, BUILD_DIR)
    if platform_list is None:
        return

    if len(platform_list) > 1:
        print("Debug mode supports only one platform at a time.")
        print(f"Using first platform: {platform_list[0]}")
        platform_list = platform_list[:1]

    platform = platform_list[0]

    print(f"\n{'=' * 70}")
    print(f"Starting debug session on {platform}...")
    print(f"{'=' * 70}\n")

    # Build Docker image for this platform
    image_name = build_docker_image_for_platform(
        c, platform, BUILD_DIR, force_image_rebuild
    )

    # Launch interactive shell in Docker container
    platform_dir = os.path.join(BUILD_DIR, platform)
    c.run(
        f"docker run --rm -it "
        f"-v $(pwd)/{platform_dir}:/workspace "
        f"-w /workspace "
        f"{image_name} "
        f"/bin/bash",
        pty=True,
    )


@task
def clean(c):
    """Clean build artifacts from all platform directories"""
    print("Cleaning build artifacts...")

    for platform in get_available_platforms(BUILD_DIR):
        platform_dir = os.path.join(BUILD_DIR, platform)
        artifacts_dir = os.path.join(platform_dir, "artifacts")
        if os.path.exists(artifacts_dir):
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
