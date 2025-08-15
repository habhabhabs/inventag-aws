---
title: Contributing Guide
description: Development setup and guidelines for contributing to InvenTag
sidebar_position: 1
---

# Contributing to InvenTag

Thank you for your interest in contributing to **InvenTag**! This document provides guidelines and information for contributors.

> **InvenTag**: Python tool to check on AWS™ cloud inventory and tagging. Integrate into your CI/CD flow to meet your organization's stringent compliance requirements.

> **Disclaimer**: AWS™ is a trademark of Amazon Web Services, Inc. InvenTag is not affiliated with AWS.

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- AWS CLI (for testing with real data)
- GitHub account

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/inventag-aws.git
   cd inventag-aws
   ```

2. **Set up Development Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # If it exists
   ```

3. **Install Development Tools**
   ```bash
   pip install black flake8 mypy pytest pytest-cov
   ```

## 📋 Pull Request Process

### Before You Start

1. **Check existing issues** - Look for related issues or feature requests
2. **Create an issue** - If none exists, create one to discuss your proposal
3. **Get feedback** - Wait for maintainer feedback before starting large changes

### Making Changes

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Follow Naming Conventions**
   - `feature/`: New features
   - `fix/`: Bug fixes
   - `docs/`: Documentation updates
   - `refactor/`: Code refactoring
   - `test/`: Test additions/modifications

3. **Make Your Changes**
   - Write clear, commented code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

4. **Test Your Changes**
   ```bash
   # Run linting
   flake8 scripts/
   
   # Format code
   black scripts/
   
   # Type checking
   mypy scripts/
   
   # Run tests (if tests directory exists)
   if [ -d "tests" ]; then
     pytest tests/ -v --cov=inventag
   fi
   
   # Test all main scripts
   python scripts/bom_converter.py --help
   python scripts/tag_compliance_checker.py --help
   python scripts/cicd_bom_generation.py --help
   
   # Test core package imports
   python -c "import inventag; print('InvenTag package imports successfully')"
   ```

### Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples:**
```
feat(bom): add account_id extraction from ARNs
fix(parser): resolve S3 bucket name parsing issue
docs: update README with new CLI options
```

### Pull Request Checklist

Before submitting your PR, ensure:

- [ ] Code follows project style guidelines
- [ ] All tests pass locally
- [ ] New code has appropriate test coverage
- [ ] Documentation is updated
- [ ] Commit messages follow conventional format
- [ ] PR description explains the changes
- [ ] No secrets or sensitive data in code
- [ ] Breaking changes are clearly documented

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Quick regression testing (validates core functionality)
python3 tests/regression/test_quick_regression.py

# Full regression testing (comprehensive end-to-end validation)
python3 tests/regression/test_full_regression.py

# Run with coverage
pytest tests/ --cov=scripts --cov-report=html

# Run specific test file
pytest tests/test_bom_converter.py
```

**📖 For comprehensive testing guidance, see [Regression Testing Guide](regression-testing.md)**

### Writing Tests

- Place tests in the `tests/` directory
- Use descriptive test names
- Test both success and failure cases
- Mock external dependencies (AWS APIs)

Example test structure:
```python
def test_bom_converter_basic_functionality():
    """Test basic BOM conversion functionality."""
    # Arrange
    sample_data = {...}
    
    # Act
    result = convert_data(sample_data)
    
    # Assert
    assert result is not None
    assert len(result) > 0
```

## 🎯 Code Style

### Python Style Guidelines

- Follow [PEP 8](https://pep8.org/)
- Use [Black](https://black.readthedocs.io/) for code formatting
- Line length: 88 characters (Black default)
- Use type hints where possible
- Write docstrings for functions and classes

### Code Structure

```python
def function_name(param: str, optional_param: int = 0) -> Dict[str, Any]:
    """
    Brief description of function.
    
    Args:
        param: Description of parameter
        optional_param: Description with default value
        
    Returns:
        Description of return value
        
    Raises:
        Exception: Description of when this is raised
    """
    # Implementation
    pass
```

## 🐛 Reporting Issues

### Bug Reports

Include:
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS)
- Sample data (anonymized)
- Error messages/stack traces

### Feature Requests

Include:
- Clear use case description
- Proposed solution
- Alternative solutions considered
- Additional context

## 📖 Documentation

InvenTag uses a dual-platform documentation system with both GitHub-compatible markdown and a Docusaurus-powered documentation site.

### Documentation Structure

```
docs/
├── architecture/           # System architecture docs
├── development/           # Developer documentation
├── examples/             # Configuration examples
├── getting-started/      # Installation and quick start
└── user-guides/         # User guides and tutorials
```

### Documentation Workflow

#### 1. **Editing Documentation**

All documentation source files are in the `docs/` directory:

```bash
# Edit documentation files directly
vim docs/user-guides/cli-user-guide.md
vim docs/architecture/core-module-integration.md
```

#### 2. **Local Testing**

Test documentation changes locally using the Docusaurus development server:

```bash
# Start local documentation server
npm run docs:start

# Or test the full pipeline
npm run docs:pipeline:test
```

#### 3. **Documentation Standards**

- **Frontmatter**: All documentation files must include YAML frontmatter:
  ```yaml
  ---
  title: Page Title
  description: Brief description of the page content
  sidebar_position: 1
  ---
  ```

- **GitHub Compatibility**: Use relative links that work in both GitHub and Docusaurus:
  ```markdown
  # Good - works in both platforms
  [Configuration Guide](../user-guides/configuration-examples)
  
  # Avoid - absolute GitHub links
  [Guide](https://github.com/habhabhabs/inventag-aws/blob/main/docs/guide.md)
  ```

- **Asset Management**: Place images and files in `docs/assets/`:
  ```markdown
  ![Architecture Diagram](/img/architecture-overview.png)
  ```

#### 4. **Testing Documentation Changes**

Before submitting documentation PRs:

```bash
# Run comprehensive documentation tests
npm run docs:test

# Quick validation
npm run docs:test:quick

# Build and validate
npm run docs:build
```

#### 5. **Documentation Site**

The documentation is automatically deployed to [https://habhabhabs.github.io/inventag-aws/](https://habhabhabs.github.io/inventag-aws/) when changes are merged to the main branch.

### Code Documentation

- Write clear docstrings for all functions and classes
- Comment complex logic and algorithms
- Include usage examples in docstrings
- Document parameters, return values, and exceptions

### Contributing to Documentation

When contributing documentation changes:

1. **Update Both Platforms**: Ensure changes work on both GitHub and the documentation site
2. **Test Locally**: Always test using `npm run docs:start` before submitting
3. **Check Links**: Verify all internal links work correctly
4. **Follow Conventions**: Use consistent formatting and structure
5. **Add to Navigation**: Update `website/sidebars.js` if adding new pages

## 🔒 Security

### Security Guidelines

- Never commit secrets, API keys, or credentials
- Use environment variables for sensitive data
- Validate all inputs
- Follow secure coding practices
- Report security issues privately

### Sensitive Data

- Use `.gitignore` to exclude sensitive files
- Anonymize sample data
- Don't include real AWS account IDs or ARNs

## 🎉 Recognition

Contributors will be recognized in:
- README contributors section
- Release notes
- GitHub contributor graphs

## ❓ Getting Help

- **Issues**: Create a GitHub issue
- **Discussions**: Use GitHub Discussions
- **Email**: Contact maintainers directly for sensitive issues

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to InvenTag! 🚀
