
# Installation Guide

1. Create an environment with Python `3.9` or higher, using `pyenv` or `conda`.
    * For `pyenv`, use the following commands:
        ```bash
        brew install pyenv
        pyenv install 3.9
        pyenv local 3.9
        ```
    * To set up your PATH automatically every time you open a shell session, add this to your .zshrc file:
        ```bash
        eval "$(pyenv init -)"
        ```
2. Clone the repository.

    ```bash
    git clone git@github.com:ServiceNow/sygra.git
    ```


3. Install uv (fast Python package manager)
    ```bash
    # macOS/Linux (script)
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # or with pipx
    pipx install uv
    ```
4. Run the following command to install all core dependencies.
    ```bash
    make setup
    ```
5. (Optional) In your IDE, set your Python interpreter to the project virtual environment created by uv.
   The interpreter will be at `.venv/bin/python` in the project root after `make setup`.

---

# Optional

### SyGra UI Setup

To run SyGra UI, Use the following command:
```bash
  make setup-ui
```
---
### SyGra All features Setup
To utilize both SyGra Core and UI features, Use the following command:
```bash
  make setup-all
```
---
### SyGra Development Setup
To set up your development environment, Use the following command:
```bash
  make setup-dev
```
Refer to [Development Guide](development.md) for more details.
