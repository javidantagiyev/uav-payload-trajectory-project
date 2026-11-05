# Testing Guide

## Running Tests

Make sure you're in the project root directory:

```powershell
cd D:\uav-payload-trajectory-project
```

### 1. Run a specific test file

```bash
python -m pytest tests/test_gravity.py -v
```

### 2. Run all tests

```bash
python -m pytest tests/ -v
```

### 3. Run all tests with a shorter traceback

```bash
python -m pytest tests/ -v --tb=short
```

## Notes

- `-v`: Displays detailed test results.
- `--tb=short`: Displays shorter error tracebacks.
- Always run tests from the project root.
- Use `python -m pytest` instead of executing test files directly.
