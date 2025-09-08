
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
    git clone git@github.com:ServiceNow/grasp.git
  ```


3. Install poetry using the [official guidelines](https://python-poetry.org/docs/#installation).
4. Run the following command to install all core dependencies.
   ```bash
    make setup
    ```
5. (Optional) In your IDE, set your python interpreter to the poetry virtual environment.
   Run `poetry run which python` to see the python interpreter path that you should add in your IDE.

---

# Optional

### GraSP UI Setup

To run GraSP UI, Use the following command:
```bash
    make setup-ui
```
---
### GraSP All features Setup
To utilize both GraSP Core and UI features, Use the following command:
```bash
    make setup-all
```
---
### GraSP Development Setup
To set up your development environment, Use the following command:
```bash
    make setup-dev
```
Refer to [Development Guide](development.md) for more details.
