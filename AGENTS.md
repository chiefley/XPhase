# Agent Instructions

This project is a small numerical RF engineering tool.

Rules:
- Do not add a GUI unless explicitly requested.
- Do not add unnecessary dependencies.
- Use clear, testable numerical functions.
- Prefer simple Python modules over clever abstractions.
- Keep input/output formats stable.
- Do not change the JSON case schema without updating docs and tests.
- Every implementation change should include or update pytest tests.
- Every change should pass pytest.
- The solver must optimize for the desired voltage/current ratio and input match, not SWR alone.
- Use the validation case in cases/ as the first numerical anchor.

Use these dependencies only for now:
numpy
scipy
pytest
matplotlib
