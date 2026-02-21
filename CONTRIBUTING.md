# Contributing to R&S CMW500 MCP Server

Thanks for your interest in contributing! This document covers the development workflow, code style, and how to add new technologies.

## Development Setup

```bash
git clone https://github.com/RFingAdam/mcp-rs-cmw500.git
cd mcp-rs-cmw500
uv pip install -e ".[dev]"
```

## Code Style

- **Formatter**: [ruff](https://docs.astral.sh/ruff/) with `line-length = 100`
- **Linter**: ruff with rules `E, F, I, N, W, UP`
- **Type checker**: mypy in strict mode
- **Target**: Python 3.10+

Run before committing:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Testing

All tests run without hardware. The test suite uses `pytest-asyncio` with `asyncio_mode = "auto"`.

```bash
# Run all tests
uv run pytest tests/ -q

# Run with coverage
uv run pytest tests/ --cov=rs_cmw500_mcp --cov-report=term-missing

# Run a specific test file
uv run pytest tests/test_wlan.py -q
```

Tests requiring a real CMW500 should be marked with `@pytest.mark.integration`.

## Project Structure

```
src/rs_cmw500_mcp/
├── driver/cmw500_driver.py   # SCPI command implementations
├── models/cmw_types.py       # Enums, dataclasses, configs
├── tools/                    # MCP tool definitions & handlers
│   ├── registry.py           # Tool registration singleton
│   └── <technology>.py       # One module per technology
├── templates/                # Pre-built measurement configs
└── safety/validators.py      # RF safety enforcement
```

## Adding a New Technology

Follow the existing pattern (WLAN, Bluetooth):

### 1. Data Models (`models/cmw_types.py`)

Add enums, config dataclasses, and result dataclasses:

```python
class MyStandard(str, Enum):
    """My technology standards."""
    MODE_A = "ModeA"

@dataclass
class MyMeasConfig:
    """Configuration for my measurement."""
    standard: MyStandard = MyStandard.MODE_A
    frequency_hz: float = 1e9
    meas_instance: int = 1

@dataclass
class MyResult:
    """My measurement result."""
    power_dbm: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in vars(self).items() if v is not None}
```

### 2. Driver Methods (`driver/cmw500_driver.py`)

Add async methods that send SCPI commands:

```python
async def my_set_standard(self, standard: str, meas_instance: int = 1) -> None:
    sanitize_scpi_param(standard)
    await self._scpi.send(
        f"CONFigure:MY:MEAS{meas_instance}:STANdard {standard}"
    )
```

### 3. MCP Tools (`tools/my_technology.py`)

Create a new module that registers tools with the registry:

```python
from .registry import registry
from .shared import _get_cmw, _format_result

async def _handle_my_tool(args):
    cmw = await _get_cmw(args.get("host"), args.get("port"))
    await cmw.my_set_standard(args["standard"])
    return _format_result({"status": "ok"})

registry.register(
    Tool(name="cmw_my_set_standard", description="...", inputSchema={...}),
    _handle_my_tool,
)
```

Import the module in `tools/__init__.py` to trigger registration.

### 4. Tests

Create two test files:

- `tests/test_my_technology.py` -- driver-level tests with mock SCPI
- `tests/test_tools_my_technology.py` -- tool handler tests with mock driver

### 5. Templates (optional)

Add a template class in `templates/` and register it in `tools/shared.py`.

## Pull Request Process

1. Create a feature branch from `master`
2. Make your changes with tests
3. Ensure all checks pass: `ruff check`, `ruff format --check`, `pytest`
4. Submit a PR with a clear description of what and why
5. Maintainer will review and merge

## Reporting Issues

Open an issue on [GitHub](https://github.com/RFingAdam/mcp-rs-cmw500/issues) with:

- What you expected vs. what happened
- CMW500 firmware version (if relevant)
- Python version and OS
- Steps to reproduce
