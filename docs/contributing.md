# GraSP Development Guide

This guide covers development practices for the GraSP project, including code style, linting, and testing procedures.

## Development Setup

To set up your development environment:

```bash
# Clone the repository
git clone https://github.com/ServiceNow/GraSP.git
cd GraSP

# Set up development environment with all tools
make setup-dev
```

## Code Style and Linting

GraSP uses several tools to ensure code quality:

- **Black**: For code formatting
- **isort**: For import sorting
- **flake8**: For style guide enforcement
- **pylint**: For code quality analysis
- **mypy**: For static type checking

### Using the Linting Tools

You can run all linters at once with:

```bash
make lint
```

Or run individual linters:

```bash
make lint-flake8  # Run flake8
make lint-pylint  # Run pylint
make lint-mypy    # Run mypy
```

### Code Formatting

To format your code according to the project standards:

```bash
make format
```

This will run both black and isort. You can run them individually:

```bash
make format-black  # Format code with black
make format-isort  # Sort imports with isort
```

### Checking Format Without Modifying Files

If you want to check your code formatting without changing files:

```bash
make check-format
```

Or check specific formatters:

```bash
make check-format-black
make check-format-isort
```

## Testing

Run the test suite:

```bash
make test
```

Run tests with verbose output:

```bash
make test-verbose
```

Run tests with coverage:

```bash
make test-coverage
```

## Continuous Integration

Run all CI steps locally:

```bash
make ci
```

This runs formatting, linting, and tests in sequence.

## Working with Optional Dependencies

GraSP has optional dependency groups that can be installed based on your needs:

- `ui`: Streamlit and related UI dependencies
- `audio`: Audio processing capabilities
- `dev`: Development tools including linting and testing

Install all extras:

```bash
poetry install --all-extras
```

Or install specific extras:

```bash
poetry install --extras "ui audio"
```

## Release Process

1. Update version numbers in `pyproject.toml`
2. Update CHANGELOG.md
3. Run tests and linting: `make ci`
4. Build the package: `make build`
5. Push changes and create a new GitHub release

## Configuration

Configuration for all tools is in `pyproject.toml`, including:

- Black configuration: `[tool.black]` section
- isort configuration: `[tool.isort]` section
- pylint configuration: `[tool.pylint]` section
- mypy configuration: `[tool.mypy]` section
- flake8 configuration: `[tool.flake8]` section

You can customize these settings to match your project's specific requirements.