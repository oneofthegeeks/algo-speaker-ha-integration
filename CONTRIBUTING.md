# Contributing to Algo Speaker Home Assistant Integration

Thank you for your interest in contributing to this project! This document provides guidelines and information for contributors.

## How to Contribute

### Reporting Issues

1. Check if the issue already exists in the [Issues](https://github.com/yourusername/algo-speaker-ha-integration/issues) section
2. If not, create a new issue with:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Your Home Assistant version
   - Algo speaker model and firmware version

### Suggesting Enhancements

1. Check if the enhancement is already requested
2. Create a new issue with the "enhancement" label
3. Provide detailed description of the proposed feature
4. Explain why it would be useful

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Ensure code follows the style guidelines
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to your branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Home Assistant (for testing)

### Local Development

1. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/algo-speaker-ha-integration.git
   cd algo-speaker-ha-integration
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. Install development dependencies:
   ```bash
   pip install -r requirements.txt[dev]
   ```

### Code Style

This project follows these style guidelines:

- **Python**: Follow PEP 8
- **YAML**: Use 2 spaces for indentation
- **Markdown**: Follow standard markdown conventions

#### Code Formatting

We use `black` for Python code formatting and `isort` for import sorting:

```bash
# Format Python code
black .

# Sort imports
isort .

# Check formatting
black --check .
isort --check-only .
```

#### Linting

We use `flake8` for linting:

```bash
flake8 .
```

### Testing

Run tests with pytest:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=. --cov-report=html
```

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Add tests for new functionality
3. Update documentation if needed
4. Ensure all tests pass
5. Update the CHANGELOG.md if applicable
6. Request review from maintainers

### PR Template

When creating a pull request, please include:

- Description of changes
- Related issues
- Screenshots (if UI changes)
- Testing instructions
- Breaking changes (if any)

## Supported Algo Speaker Models

- 8180: Basic IP speaker
- 8188: IP speaker with additional features
- 8189: IP speaker with enhanced capabilities
- 8196: Advanced IP speaker with full feature set

## Home Assistant Compatibility

This integration is tested with:
- Home Assistant Core 2023.1.0+
- Home Assistant OS
- Home Assistant Supervised

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing, please:
1. Check the [Issues](https://github.com/yourusername/algo-speaker-ha-integration/issues) section
2. Create a new issue with the "question" label
3. Contact the maintainers

Thank you for contributing! 🎉
