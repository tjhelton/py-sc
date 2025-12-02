# py-sc

A collection of Python automation scripts for SafetyCulture API operations. Provides tools for bulk management of templates, sites, issues, and other SafetyCulture resources.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/tjhelton/py-sc.git
cd py-sc

# Install dependencies
pip install -r requirements.txt

# Set up development environment (optional)
cd contribution_tools/
make install
make pre-commit

# Run any script
cd scripts/archive_templates/
# Set your API token in main.py
python main.py
```

## 📁 Available Scripts

> **💡 Each script has its own README with detailed setup instructions, input formats, and usage examples. Click any script link below to view its complete documentation.**

### Template Management
- **[archive_templates/](scripts/archive_templates/)** - Archive SafetyCulture templates in bulk
- **[export_template_access_rules/](scripts/export_template_access_rules/)** - Export template permission matrices

### Site Management
- **[create_groups/](scripts/create_groups/)** - Create SafetyCulture groups
- **[create_sites/](scripts/create_sites/)** - Create SafetyCulture sites with hierarchy support
- **[delete_sites/](scripts/delete_sites/)** - Delete SafetyCulture sites in bulk
- **[get_sites_without_activity/](scripts/get_sites_without_activity/)** - Identify inactive sites
- **[set_inspection_site/](scripts/set_inspection_site/)** - Configure audit-site relationships
- **[update_user_sites/](scripts/update_user_sites/)** - Bulk update user site assignments

### Issues, Actions & Assets
- **[delete_actions/](scripts/delete_actions/)** - Delete SafetyCulture actions in bulk (batches of 300)
- **[delete_assets/](scripts/delete_assets/)** - Archive SafetyCulture assets with detailed logging
- **[export_asset_types/](scripts/export_asset_types/)** - Export asset type definitions
- **[export_issue_relations/](scripts/export_issue_relations/)** - Export issue relationship data to CSV
- **[fetch_issues/](scripts/fetch_issues/)** - Extract all issues with detailed tracking data
- **[get_public_issue_links/](scripts/get_public_issue_links/)** - Generate public sharing links

## 🛠️ Development

### Code Quality
This project uses automated linting and formatting tools. **All linting commands must be run from the `contribution_tools/` directory**:

```bash
cd contribution_tools/
make lint      # Check code quality
make fix       # Auto-fix formatting issues
make help      # See all available commands
```

### Pre-commit Hooks
Automatically format and lint code before commits:

```bash
cd contribution_tools/
make pre-commit
```

### GitHub Actions
- Automated code quality checks on all pull requests
- Linting and formatting validation
- Ensures consistent code standards

## 📋 Prerequisites

- **Python 3.8+** with pip
- **SafetyCulture API Token** - [Get yours here](https://developer.safetyculture.com/reference/getting-started)
- **API Access** - Appropriate permissions for your use case

## 🔧 Dependencies

Install all required dependencies for the scripts:
```bash
pip install -r requirements.txt
```

This installs:
- **pandas** - CSV data processing and manipulation
- **requests** - HTTP requests to SafetyCulture API
- **aiohttp** - Async HTTP requests (for concurrent processing scripts)

## 📖 Usage Patterns

### Standard Workflow
1. Install dependencies: `pip install -r requirements.txt`
2. Navigate to desired script directory
3. Set API token in `main.py` or environment variable
4. Prepare `input.csv` (if required)
5. Run `python main.py`
6. Check output files

### Authentication Methods
- **Token in script**: `TOKEN = 'your-token-here'` (most scripts)
- **Environment variable**: `export SC_API_TOKEN="your-token-here"` (advanced scripts)

## 📊 Input/Output Formats

### Standard Input
Most scripts expect `input.csv` with relevant IDs or parameters. See individual script READMEs for specific formats.

### Standard Output
- CSV files with processing results
- Timestamped output directories (for complex scripts)
- Terminal progress logging

## ⚠️ Important Notes

- **Security**: Never commit API tokens or sensitive data
- **Testing**: Always test with small datasets first
- **Irreversible**: Many operations (delete, archive) cannot be undone
- **Rate Limits**: Scripts include appropriate delays and retry logic

## 📚 API Documentation

- [SafetyCulture API Reference](https://developer.safetyculture.com/reference/)
- [Getting Started Guide](https://developer.safetyculture.com/reference/getting-started)

## 🤝 Contributing

**We'd love your help!** Whether you're fixing a typo, adding a new script, or improving documentation - every contribution makes this project better for everyone.

**Getting Started is Easy:**
1. 🍴 Fork the repository (it's just a click!)
2. 🌿 Create a feature branch (`git checkout -b my-awesome-feature`)
3. 📚 Check out our friendly [contribution guide](contribution_tools/CONTRIBUTE.md)
4. ✨ Make your changes and run `cd contribution_tools/ && make lint`
5. 🚀 Submit a pull request and celebrate!

**First time contributing to open source?** No worries! We're here to help. Start with something small like:
- 📝 Improving documentation or fixing typos
- 🐛 Reporting bugs or suggesting features
- 🔧 Adding error handling to existing scripts
- 💡 Creating a new SafetyCulture API script

**Questions?** Open an issue - we're friendly and happy to guide you! The SafetyCulture API community grows stronger with every contribution.

## 📄 License

This project is provided as-is for SafetyCulture API automation. Use responsibly and in accordance with SafetyCulture's terms of service.
