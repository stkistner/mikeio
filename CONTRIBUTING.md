# Guidelines for contribution

1. Clone the repo
2. Install package in editable mode `pip install -e .[dev]`, including development dependencies
3. If you are fixing a bug, first add a failing test
4. Make changes
5. Verify that all tests passes by running `pytest` from the package root directory
6. Format the code by running [`ruff format`](https://docs.astral.sh/ruff/formatter/)
6. Make a pull request with a summary of the changes

Tests can also be run with tools like VS Code
![testing](images/testing.png)
