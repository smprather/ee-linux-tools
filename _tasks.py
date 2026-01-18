import subprocess
from pathlib import Path

# import pysnooper as s
from invoke import task
from pysnooper import snoop as s


@task
def create_volumes(c):
    c.run("docker volume create build-cache")


@task(pre=[create_volumes])
@s()
def build_image(c, force=False):
    c.run("docker build -t ee-linux-tools .", pty=True)


# @s()
@task(pre=[build_image])
def build(c, force=False, tools=["neovim"]):
    cd(build)
    for tool in tools:
        print(tool)


# @s()
def build_neovim(c):
    build_dir = Path("build")
    nvim_build_dir = Path("external/neovim")
    return
    if not (nvim_build_dir / ".git").exists():
        c.run("cd external; git clone https://github.com/neovim/neovim.git")
    else:
        c.run("cd external/neovim; git pull")
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
