# Contributing to SEC Rule 15c3-5 Market Access Controls Example

Thank you for your interest in contributing! This is an educational project designed for graduate-level data engineering courses, demonstrating pre-trade risk controls that meet SEC Rule 15c3-5 requirements.

## Types of Contributions

We welcome:
- **Bug fixes**: Corrections to code, documentation, or configuration
- **Documentation improvements**: Clarifications, examples, tutorials
- **New exercises**: Additional student exercises (see docs/05-exercises.md)
- **Performance optimizations**: Improvements to latency, throughput, or cost
- **Security enhancements**: Better security practices (see docs/08-security-notes.md)
- **Testing**: Unit tests, integration tests, chaos engineering
- **Tooling**: Scripts, utilities, monitoring dashboards

## Getting Started

1. **Fork the repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/streaming-risk-controls.git
   cd streaming-risk-controls
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make changes** (see guidelines below)
5. **Test locally** (see Testing section)
6. **Commit and push**:
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin feature/your-feature-name
   ```
7. **Open a Pull Request**

## Development Setup

### Local Development
```bash
# Install Python dependencies
pip install -r services/order_generator/requirements.txt

# Start local environment
cd local
docker-compose up -d

# Run tests (if available)
pytest tests/
```

### AWS Development
```bash
# Build Lambda packages
make build-lambdas

# Deploy to dev environment
cd terraform/envs/dev
terraform apply

# Test changes
./tools/run-demo.sh
```

## Code Guidelines

### Python
- **Style**: Follow PEP 8
- **Formatting**: Use `black` for formatting
- **Linting**: Use `pylint` or `flake8`
- **Type hints**: Use type hints where appropriate
- **Docstrings**: Use Google-style docstrings

Example:
```python
def process_order(order: dict) -> tuple[bool, str]:
    """
    Process an order through kill switch logic.
    
    Args:
        order: Order event dictionary with required fields
        
    Returns:
        Tuple of (should_drop, reason)
        
    Raises:
        ValueError: If order is missing required fields
    """
    # Implementation
```

### Terraform
- **Style**: Use `terraform fmt`
- **Validation**: Run `terraform validate`
- **Modules**: Keep modules focused and reusable
- **Variables**: Document all variables with descriptions
- **Outputs**: Provide useful outputs for debugging

### Documentation
- **Markdown**: Use standard Markdown
- **Code blocks**: Include language hints for syntax highlighting
- **Examples**: Provide runnable examples
- **Diagrams**: Use Mermaid for diagrams
- **Links**: Use relative links for internal docs

## Testing

### Unit Tests
```bash
# Run Python unit tests
pytest tests/unit/

# Run with coverage
pytest --cov=services tests/
```

### Integration Tests
```bash
# Test local environment
cd local
docker-compose up -d
./tests/integration/test_local.sh

# Test AWS environment
./tests/integration/test_aws.sh
```

### Manual Testing
```bash
# Test order generation
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 60}' response.json

# Verify orders flowing
./tools/tail-topic.sh orders.v1

# Test kill switch
curl -X POST $API_URL/kill \
  -H "Content-Type: application/json" \
  -d '{"scope": "GLOBAL", "reason": "Test"}'

# Verify enforcement
./tools/tail-topic.sh audit.v1
```

## Pull Request Process

1. **Update documentation** if you change functionality
2. **Add tests** for new features
3. **Update CHANGELOG.md** (if exists)
4. **Ensure all tests pass**
5. **Update README.md** if adding major features
6. **Request review** from maintainers

### PR Title Format
```
[Type] Brief description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation only
- style: Code style changes (formatting)
- refactor: Code refactoring
- test: Adding tests
- chore: Maintenance tasks
```

### PR Description Template
```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- List of specific changes
- Another change

## Testing
How was this tested?

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] Tests pass locally
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Follows code style guidelines
```

## Commit Message Guidelines

Use conventional commits:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Examples:
```
feat(spark): add symbol concentration detection

Add new risk signal for symbol concentration in Spark job.
Emits kill command when single symbol exceeds 70% of orders.

Closes #123

fix(lambda): handle missing account_id in orders

Add validation to check for required fields before processing.
Returns 400 error if account_id is missing.

docs(readme): update deployment instructions

Clarify Terraform version requirements and add troubleshooting
section for common MSK connection issues.
```

## Code Review Process

Reviewers will check:
- **Functionality**: Does it work as intended?
- **Code quality**: Is it readable and maintainable?
- **Testing**: Are there adequate tests?
- **Documentation**: Is it well-documented?
- **Security**: Are there security implications?
- **Performance**: Are there performance concerns?
- **Cost**: Does it impact AWS costs?

## Areas for Contribution

### High Priority
- [ ] Unit tests for Lambda functions
- [ ] Integration tests for end-to-end flow
- [ ] Terraform module tests
- [ ] Performance benchmarks
- [ ] Cost optimization analysis

### Medium Priority
- [ ] Additional student exercises
- [ ] Video tutorials
- [ ] Troubleshooting guide expansion
- [ ] Multi-region deployment guide
- [ ] Monitoring dashboard improvements

### Low Priority
- [ ] Alternative cloud providers (GCP, Azure)
- [ ] Alternative streaming platforms (Pulsar, Redpanda)
- [ ] Machine learning risk detection
- [ ] Web UI for operator console

## Documentation Contributions

### Adding New Docs
1. Create file in `docs/` directory
2. Use clear, descriptive filename
3. Add to README.md table of contents
4. Include code examples
5. Add diagrams where helpful

### Improving Existing Docs
1. Fix typos and grammar
2. Add clarifications
3. Update outdated information
4. Add missing examples
5. Improve formatting

## Bug Reports

Use GitHub Issues with this template:

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Deploy infrastructure
2. Run command X
3. See error

**Expected behavior**
What should happen

**Actual behavior**
What actually happens

**Environment**
- OS: [e.g., macOS 14.0]
- Terraform version: [e.g., 1.6.0]
- AWS region: [e.g., us-east-1]
- Python version: [e.g., 3.11]

**Logs**
```
Paste relevant logs here
```

**Screenshots**
If applicable

**Additional context**
Any other relevant information
```

## Feature Requests

Use GitHub Issues with this template:

```markdown
**Feature description**
Clear description of the feature

**Use case**
Why is this feature needed?

**Proposed solution**
How should it work?

**Alternatives considered**
Other approaches you've thought about

**Additional context**
Any other relevant information
```

## Questions and Support

- **Documentation**: Check [docs/](docs/) first
- **Issues**: Search existing issues
- **Discussions**: Use GitHub Discussions for questions
- **Email**: Contact course instructor (for students)

## Code of Conduct

### Our Standards
- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions
- Respect different viewpoints

### Unacceptable Behavior
- Harassment or discrimination
- Trolling or insulting comments
- Personal attacks
- Publishing private information
- Other unprofessional conduct

### Enforcement
Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

Report violations to project maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see LICENSE file).

## Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md (if created)
- Mentioned in release notes
- Credited in documentation

## Questions?

Open an issue or discussion if you have questions about contributing!

Thank you for helping make this educational resource better! 🎓
