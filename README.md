# cross-references-predictor

## Developer Setup

This project uses [mise](https://mise.en.dev/) to manage tool versions (Python, Just, etc.).

### Prerequisites

1. Install mise:
   ```bash
   curl https://mise.run | sh
   ```

2. Trust the project configuration:
   ```bash
   mise trust
   ```

### Quick Start

```bash
# Install all tools and create virtual environment automatically
mise install

# Activate virtual environment
source .venv/bin/activate
```

### Available Commands

Run `just --list` to see all available commands:

| Command | Description |
|---------|-------------|
| `just install` | Install project dependencies |
| `just install_venv` | Create/update virtual environment |
| `just test` | Run tests |
| `just start` | Start services with Docker |
| `just formatter` | Format code with black |
| `just check_format` | Check code formatting |

### How Mise Works

- **Python** is pinned to version `3.14.4` in `.mise.toml`
- **Just** is pinned to version `1.50.0` for consistent task running
- The virtual environment path (`.venv/bin`) is automatically added to PATH when the venv exists
- On first `mise install`, the venv is automatically created and dependencies are installed

### Switching Python Versions

```bash
mise use python@3.13
```

This updates the Python version and triggers the post-install hook to recreate the venv.