# Contributing to Things MCP

Thank you for your interest in contributing to the Things MCP server! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

Please be respectful and considerate of others when contributing to this project. We aim to foster an inclusive and welcoming community.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue on the GitHub repository with the following information:

1. A clear, descriptive title
2. A detailed description of the issue
3. Steps to reproduce the bug
4. Expected behavior
5. Actual behavior
6. Screenshots (if applicable)
7. Environment details (OS, Python version, etc.)

### Feature Requests

We welcome feature requests! Please create an issue on GitHub with:

1. A clear title
2. A detailed description of the feature
3. The motivation behind the feature
4. Examples of how the feature would be used

### Pull Requests

We welcome pull requests! Here's how to submit one:

1. Fork the repository
2. Create a new branch with a descriptive name
3. Make your changes
4. Add or update tests as necessary
5. Ensure all tests pass
6. Update documentation if needed
7. Submit a pull request

## Development Environment

To set up a development environment:

```bash
# Clone the repository
git clone https://github.com/hald/things-mcp
cd things-mcp

# Set up a virtual environment with development dependencies
uv venv
uv pip install -e ".[dev]"
```

## Testing

Please make sure to run tests before submitting a pull request:

```bash
# Run tests
pytest
```

## Code Style

We follow PEP 8 style guidelines. Please format your code using `ruff`:

```bash
# Format code
ruff format .

# Check code style
ruff check .
```

## Documentation

Please update the documentation when necessary. This includes:

- README.md
- Docstrings in the code
- CHANGELOG.md for any changes

## Versioning

We follow [Semantic Versioning](https://semver.org/). Please make sure any changes are properly versioned.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's MIT license.

## Questions?

If you have any questions, feel free to open an issue on GitHub or reach out to the maintainers directly.

Thank you for your contributions!
