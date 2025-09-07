

1. Create an environment with Python `3.11` or higher, using `pyenv` or `conda`.
    * For `pyenv`, use the following commands:
        ```bash
        brew install pyenv
        pyenv install 3.11
        pyenv local 3.11
        ```
    * To set up your PATH automatically every time you open a shell session, add this to your .zshrc file:
        ```bash
        eval "$(pyenv init -)"
        ```
2. Clone the repository.

  ```
    git clone git@github.com:ServiceNow/grasp.git
  ```

> [!IMPORTANT]
> If you have already cloned GraSP locally, follow the steps below to update your remote to point to the correct URL: 
> ```bash
> git remote set-url origin git@github.com:ServiceNow/grasp.git
> git fetch --prune
> ```

3. Install poetry using the [official guidelines](https://python-poetry.org/docs/#installation).
4. Run `poetry install`.
5. (Optional) In your IDE, set your python interpreter to the poetry virtual environment.
   Run `poetry run which python` to see the python interpreter path that you should add in your IDE.

---