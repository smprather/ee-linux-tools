import subprocess
from pathlib import Path

from invoke import task


@task
def create_volumes(c):
    c.run("docker volume create build-cache")


@task(pre=[create_volumes])
def build_image(c):
    c.run("docker build -t ee-linux-tools .", pty=True)


@task(pre=[build_image])
def neovim(c):
    build_dir = Path("build")
    nvim_build_dir = Path("external/neovim")
    if not (nvim_build_dir / ".git").exists():
        c.run("git clone ..............")
    mkdir(nvim_build_dir)
    cd(build_dir)
    c.run(
        "docker run -t "
        f"--cpus {subprocess.getoutput('cat /proc/cpuinfo | grep -c Processor')} "
        "-v build-cache:/cache "
        f"-v {Path.cwd()}/deploy:/deploy "
        f"-v {Path.cwd()}/external:/external "
        f"-v {Path.cwd()}/scripts:/scripts "
        "--rm "
        "ee-linux-tools "
        "/scripts/build_neovim.sh",
        echo=True,
        pty=True,
    )


g_dir_stack = []


def mkdir(the_dir: Path, clean=False):
    the_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        subprocess.run(f"rm -fr {the_dir}/*")


def cd(the_dir: Path, clean=False, create_if_needed=True):
    if create_if_needed:
        the_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        subprocess.run(f"rm -fr {the_dir}/*", shell=True)


def pushd(the_dir: Path, create_if_needed=True):
    global g_dir_stack
    g_dir_stack.append(the_dir)
    cd(the_dir, create_if_needed)


def popd():
    global g_dir_stack
    cd(g_dir_stack.pop())
