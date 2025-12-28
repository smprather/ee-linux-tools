from invoke import task

def mkdir(the_dir):
    the_dir..mkdir(parents=True, exist_ok=True)

@task
def build_image(c):
    c.run("docker build -t ee-tools .", pty=True)

@task
def neovim(c):
    nvim_build_dir = Path("neovim")
    mkdir(nvim_build_dir)

    make_cmd_base = "make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFIX=$(pwd)/install install"
    c.run("docker run ee-tools make CMAKE_BUILD_TYPE=RelWithDebInfo CMAKE_INSTALL_PREFIX=$(pwd)/install install"

