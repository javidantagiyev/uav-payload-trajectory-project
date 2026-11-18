# Testing Guide

## Running Tests

Make sure you're in the project root directory:

```powershell
cd <path-to-cloned-repository>
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


## Offline numerical experiment

```bash
python experiments/offline_dynamics/baseline.py --config configs/offline_dynamics/baseline.json --output results/offline_dynamics/local_run
```

The whole test suite covers the original `src/physics/` methods as well as the new numerical-verification components. Run it before pushing changes.
