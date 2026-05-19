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

## Usage

The service exposes a REST API to manage cross-document reference predictions. Below is a typical workflow:

### 1. Send Data

#### Prior references of type Location / Names / Organizations / Dates

```bash
curl -X POST http://localhost:8000/destinations \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "my_project",
    "language": "en",
    "destinations": [
      {"name": "Paris",   "type": "Location",     "external_id": "loc_01", "alternative_names": ["París"]},
      {"name": "Acme Corp", "type": "Organization", "external_id": "org_01", "alternative_names": []}
    ]
  }'
```

#### Prior references of type Reference (text → destination mappings)

```bash
curl -X POST http://localhost:8000/reference_occurrences \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "my_project",
    "language": "en",
    "occurrences": [
      {"text": "the Company", "destination": "Acme Corp", "pdf_name": "doc1.pdf", "page": 3, "segment_text": "the Company signed the agreement"}
    ]
  }'
```

#### Prior negative samples for cross references

```bash
curl -X POST http://localhost:8000/negative_samples \
  -H "Content-Type: application/json" \
  -d '{
    "namespace": "my_project",
    "language": "en",
    "destination": "Paris",
    "segments": [
      {"text": "Paris is a beautiful city", "pdf_name": "doc1.pdf", "page": 1}
    ]
  }'
```

### 2. Update Data

```bash
curl -X PUT http://localhost:8000/destinations/Paris \
  -H "Content-Type: application/json" \
  -d '{"name": "Paris", "type": "Location", "external_id": "loc_01", "alternative_names": ["París", "City of Light"]}'
```

### 3. Get New Cross-Document Predictions

Process a document (PDF or raw text) and get predicted cross-references:

```bash
# With a PDF file
curl -X POST http://localhost:8000/ \
  -F "namespace=my_project" \
  -F "language=en" \
  -F "file=@document.pdf"

# With raw text
curl -X POST http://localhost:8000/ \
  -F "namespace=my_project" \
  -F "language=en" \
  -F "identifier=doc_01" \
  -F "text=The Company headquartered in Paris announced..."
```

### 4. Delete Namespace

```bash
curl -X POST http://localhost:8000/delete_namespace \
  -F "namespace=my_project" \
  -F "language=en"
```

## Switching Python Versions

```bash
mise use python@3.13
```

This updates the Python version and triggers the post-install hook to recreate the venv.