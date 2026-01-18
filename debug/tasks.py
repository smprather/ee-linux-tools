import subprocess
from pathlib import Path

from invoke import task


@task()
def build_image(c):
    c.run("docker build -t el7 .", pty=True)


@task(pre=[build_image])
def el7(c):
    c.run(
        "docker run -t "
        f"-v {(Path.cwd() / '../deploy/GLIBC_227').resolve()}:/ee-linux-tools "
        "--rm "
        "el7 ",
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
