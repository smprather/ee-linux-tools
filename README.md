# ee-linux-tools
* Linux tools compiled to common EDA linux distro targets (EL7/8+). Configured to work offline when applicable.
* Wrappers to detect platform and auto-route to the correct binaries.
* Hopefully PatchELF'd to auto-work with the .so's included
  * May need to hard-code some paths to dynamic linker interpretter as a post-install step. We'll see...

# Architectures
* x86_64
* ARM
 
# Platforms
* EL7, 8, 9
  * Base images: Centos7, Alma for the rest
* Maybe Suse if requested

# Projects (eventually)
| Project | Description |
|---------|-------------|
| [NeoVim](https://github.com/neovim/neovim) | <ul><li>Including many plugins, especially those that require a compiled component (ex: tree-sitter parsers)<li>Configured to work offline<li>Against my better judgement, I'll find the best GVim-like GUI interface for NVim (please don't use it!).</ul> |
| [Python](https://github.com/python) | One language to rule them all? Will include a heavily infused venv. |
| [uv](https://github.com/astral-sh/uv) | The PIP killer. |
| [ty](https://github.com/astral-sh/ty) | Blazing fast Python type-checker w/ language-server interface. |
| [ruff](https://github.com/astral-sh/ruff) | Blazing fast Python linter w/ language-server interface. |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | The grep killer |
| [ugrep](https://github.com/Genivia/ugrep) | 100% grep-compatible alternative |
| [tmux](https://github.com/tmux/tmux/wiki) | Turn a sinlge ssh or gnome-terminal into all you terminals |
| [fd](https://github.com/sharkdp/fd) | For finding files |
| [choose](https://github.com/theryangeary/choose) | `cut` replacement. `cut` is downright user-hostile. |
| [eza](https://github.com/eza-community/eza) | Excellent `ls` alternative. |
| [KLayout](https://github.com/KLayout/klayout) | Free layout editor (GDS, OASIS, LEF/DEF support). |
| [fzf](https://github.com/junegunn/fzf) | FuzzyFinder with shell integrations. |
| [bash](https://github.com/bminor/bash) | Latest version. |
| [zsh](https://github.com/zsh-users/zsh) | Bash alternative. |
| [ohmyzsh](https://github.com/ohmyzsh/ohmyzsh) | Zsh configuration manager. |
| [patchelf](https://github.com/NixOS/patchelf) | Linux binary editor to help with dynamic linking. |
| [stylua](https://github.com/JohnnyMorganz/StyLua) | Lua formatter written in Rust. |
| Much more... | Much much more..... |

