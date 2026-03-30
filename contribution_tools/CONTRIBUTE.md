# Contributing to py-sc

Welcome! This guide will help you contribute to the py-sc repository while maintaining code quality and consistency.

## 🚀 Quick Start for Contributors

```bash
# 1. Navigate to the contribution_tools directory
cd contribution_tools/

# 2. Install development dependencies
make install

# 3. Set up pre-commit hooks (runs linters automatically)
make pre-commit

# 4. Check your code before committing
make lint

# 5. Auto-fix formatting issues
make fix
```

## 📋 Development Workflow

### Before Making Changes
1. **Set up your environment** with the commands above
2. **Create a new branch** for your feature/fix
3. **Make your changes** to the relevant script directories

### Before Committing
1. **Run linting**: `make lint` to check for issues
2. **Auto-fix formatting**: `make fix` to automatically resolve style issues
3. **Test your changes** to ensure functionality is preserved
4. **Commit your changes** (pre-commit hooks will run automatically)

### Submitting Changes
1. **Push your branch** to GitHub
2. **Create a Pull Request**
3. **Automated linting** will run on your PR
4. **Address any feedback** from reviewers

## 🔧 Available Development Commands

### Essential Commands
- `make help` - Show all available commands
- `make lint` - Run all linters (check mode)
- `make fix` - Auto-fix formatting and style issues
- `make check-deps` - Verify linting tools are installed

### Individual Linter Commands
- `make black-check` / `make black-fix` - Code formatting
- `make isort-check` / `make isort-fix` - Import sorting
- `make flake8` - Style guide enforcement
- `make mypy` - Type checking

### Direct Script Access
- `python3 lint-and-fix.py` - Run linters directly
- `python3 lint-and-fix.py --fix` - Run with auto-fix
- `python3 lint-and-fix.py --check-deps` - Verify dependencies

### Maintenance Commands
- `make clean` - Remove temporary files and caches
- `make install` - Install/update development dependencies

## 🛠️ Code Quality Tools

### What Gets Checked
Our linting system checks all script directories under `scripts/`, organized by category:
- `scripts/actions/*` - Action management scripts
- `scripts/assets/*` - Asset management scripts
- `scripts/courses/*` - Course assignment scripts
- `scripts/groups/*` - Group management scripts
- `scripts/inspections/*` - Inspection management scripts
- `scripts/issues/*` - Issue management scripts
- `scripts/nuke_account/` - Account cleanup tool
- `scripts/organizations/*` - Organization management scripts
- `scripts/sites/*` - Site management scripts
- `scripts/templates/*` - Template management scripts
- `scripts/users/*` - User management scripts

**Excluded from linting**: `venv/`, `dump/`, `contribution_tools/`, `.git/`, `__pycache__/`

### Linting Tools Used

#### Black (Code Formatting)
- **Line length**: 88 characters
- **String preservation**: Won't change existing quote styles to avoid breaking API calls
- **Safe formatting**: Only improves code style, never changes logic

#### isort (Import Sorting)
- **Conservative mode**: Sorts imports without breaking functionality
- **Black compatible**: Follows Black's formatting preferences

#### flake8 (Style Guide)
- **PEP 8 compliance**: Enforces Python style standards
- **Relaxed rules**: Ignores documentation requirements to avoid forced changes
- **Line length**: Consistent with Black (88 characters)

#### mypy (Type Checking)
- **Relaxed mode**: Won't force type annotations on existing code
- **Optional**: Type checking helps catch potential issues but won't block contributions

## 🔄 Automated Features

### Pre-commit Hooks
Once installed with `make pre-commit`, these hooks automatically run before each git commit:
- Code formatting (Black)
- Import sorting (isort)
- Basic style checks (flake8)
- Type checking (mypy)

### GitHub Actions Integration
Pull requests automatically trigger:
- **Linting checks** using Python 3.11
- **Formatting validation**: Ensures no auto-fixable changes remain

### Safe Auto-fixing
When you run `make fix`, the system will:
- ✅ **Format code style** (spacing, line breaks, etc.)
- ✅ **Sort imports** conservatively
- ✅ **Preserve string quotes** (API URLs, tokens, file paths remain unchanged)
- ❌ **Never modify logic or functionality**
- ❌ **Never touch files outside script directories**

## 📁 Project Structure

```
py-sc/
├── scripts/                        # 🚀 SafetyCulture API Scripts
│   ├── actions/                    # Action management (delete_actions, delete_action_schedules)
│   ├── assets/                     # Asset management (export_assets, export_asset_types, update_assets, delete_assets)
│   ├── courses/                    # Course management (assign_courses)
│   ├── groups/                     # Group management (create_groups, export_group_assignees)
│   ├── inspections/                # Inspection management (archive, complete, delete, export, unarchive, update)
│   ├── issues/                     # Issue management (export_issue_public_links, export_issue_relations)
│   ├── nuke_account/               # ⚠️ Full account cleanup tool
│   ├── organizations/              # Organization management (export_contractor_companies)
│   ├── sites/                      # Site management (create, delete, export_inactive, update_users)
│   ├── templates/                  # Template management (archive, export_access_rules, export_questions)
│   └── users/                      # User management (deactivate_users, export_user_custom_fields)
├── contribution_tools/             # 🔧 Development tools (this directory)
│   ├── CONTRIBUTE.md               # This guide
│   ├── Makefile                    # Development commands
│   ├── lint-and-fix.py             # Main linting script
│   ├── pyproject.toml              # Linter configurations
│   ├── .pre-commit-config.yaml     # Pre-commit setup
│   └── requirements-dev.txt        # Development dependencies
├── requirements.txt                # Script dependencies
└── README.md                       # Main project documentation
```

## 🐛 Troubleshooting

### Common Issues

**"Command not found" errors**
```bash
cd contribution_tools/
make install
```

**Pre-commit hooks not running**
```bash
cd contribution_tools/
make pre-commit
```

**Linting fails after making changes**
```bash
cd contribution_tools/
make fix  # Auto-fix what can be fixed
make lint # Check remaining issues
```

**Virtual environment conflicts**
Make sure you're in the py-sc root, not inside venv/:
```bash
pwd  # Should show .../py-sc, not .../py-sc/venv
cd contribution_tools/
make install
```

### Getting Help

1. **Check command help**: `make help`
2. **Verify setup**: `make check-deps`
3. **Clean and restart**: `make clean && make install`
4. **Check this guide**: Re-read the relevant sections above

## 🎯 Contribution Guidelines

### Code Style
- **Follow existing patterns** in each script directory
- **Preserve functionality** - never change the core logic of existing scripts
- **Use descriptive variable names** and comments where helpful
- **Test your changes** before submitting

### API Integration
- **Always use the existing session/retry patterns** in scripts
- **Preserve authentication headers** and API token handling
- **Follow existing error handling patterns**
- **Test with the SafetyCulture API** to ensure functionality

### Documentation
- **Update README files** in script directories when adding features
- **Include usage examples** for new functionality
- **Document any new environment variables** or configuration options

### Commit Messages
- **Use clear, descriptive commit messages**
- **Reference issue numbers** when applicable
- **Follow conventional commit format** when possible

## 📚 Additional Resources

- **SafetyCulture API Documentation**: https://developer.safetyculture.com/reference/
- **Python Style Guide (PEP 8)**: https://pep8.org/
- **Black Code Formatter**: https://black.readthedocs.io/
- **Pre-commit Framework**: https://pre-commit.com/

---

Thank you for contributing to py-sc! Your improvements help make SafetyCulture API automation better for everyone. 🚀
