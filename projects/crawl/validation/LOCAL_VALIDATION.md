# Local Validation Report

- **Overall:** PASS
- **Generated:** 2026-08-20 20:04:24 -06:00
- **Branch:** `agent/world-v0.3-slice3-production`
- **Code commit tested:** `741cb0441f88fcc25f48556f264d7d111bb2aa30`
- **Duration:** 366.58 seconds
- **Python:** Python 3.14.2
- **Node:** v24.12.0
- **npm:** 11.6.2

## Working tree before validation

```text
clean
```

## Slice 6 continent/frontier/warfare/balance/benchmark/API tests

Exit code: **0**

```text
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Living
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 39 items

tests\test_continent_generation.py ....                                  [ 10%]
tests\test_migration.py ...                                              [ 17%]
tests\test_border_policy.py ....                                         [ 28%]
tests\test_frontier.py ....                                              [ 38%]
tests\test_warfare.py ......                                             [ 53%]
tests\test_benchmark.py .....                                            [ 66%]
tests\test_long_term_balance.py .......                                  [ 84%]
tests\test_api_continent.py ..                                           [ 89%]
tests\test_api_border_policy.py ..                                       [ 94%]
tests\test_api_frontier.py .                                             [ 97%]
tests\test_api_warfare.py .                                              [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Living\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 39 passed, 1 warning in 27.24s ========================
```

## v0.3 politics, balance, collapse, benchmark, and API tests

Exit code: **0**

```text
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Living
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 28 items

tests\test_politics.py .........                                         [ 32%]
tests\test_politics_balance.py .....                                     [ 50%]
tests\test_political_collapse.py ........                                [ 78%]
tests\test_politics_benchmark.py ...                                     [ 89%]
tests\test_politics_integrity.py ..                                      [ 96%]
tests\test_api_politics.py .                                             [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Living\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 28 passed, 1 warning in 31.62s ========================
```

## Full backend regression

Exit code: **0**

```text
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\Living
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 125 items

tests\test_api.py ...                                                    [  2%]
tests\test_api_border_policy.py ..                                       [  4%]
tests\test_api_continent.py ..                                           [  5%]
tests\test_api_frontier.py .                                             [  6%]
tests\test_api_institutions.py .                                         [  7%]
tests\test_api_politics.py .                                             [  8%]
tests\test_api_production.py .                                           [  8%]
tests\test_api_warfare.py .                                              [  9%]
tests\test_benchmark.py .....                                            [ 13%]
tests\test_border_policy.py ....                                         [ 16%]
tests\test_commands.py ...                                               [ 19%]
tests\test_continent_generation.py ....                                  [ 22%]
tests\test_emergence.py ...                                              [ 24%]
tests\test_frontier.py ....                                              [ 28%]
tests\test_generation.py ...                                             [ 30%]
tests\test_institution_benchmark.py ..                                   [ 32%]
tests\test_institution_fiscal_balance.py ...                             [ 34%]
tests\test_institution_strategic_budget.py ...                           [ 36%]
tests\test_institutions.py .......                                       [ 42%]
tests\test_long_term_balance.py .......                                  [ 48%]
tests\test_migration.py ...                                              [ 50%]
tests\test_political_collapse.py ........                                [ 56%]
tests\test_politics.py .........                                         [ 64%]
tests\test_politics_balance.py .....                                     [ 68%]
tests\test_politics_benchmark.py ...                                     [ 70%]
tests\test_politics_integrity.py ..                                      [ 72%]
tests\test_production.py .........                                       [ 79%]
tests\test_production_benchmark.py ...                                   [ 81%]
tests\test_production_food_balance.py ......                             [ 86%]
tests\test_resilience.py ....                                            [ 89%]
tests\test_simulation.py .....                                           [ 93%]
tests\test_warfare.py ......                                             [ 98%]
tests\test_warfare_political_reconciliation.py ..                        [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\Living\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================= 125 passed, 1 warning in 296.94s (0:04:56) ==================
```

## Front/supply/siege/peace smoke test

Exit code: **0**

```text
Fronts: 5; attacker supply: 1.00
Occupied: Moonstead; siege complete
Peace ceded Moonstead; population still 100000
```

## Dashboard production build

Exit code: **0**

```text

> livingworld-dashboard@0.1.0 build
> tsc --noEmit && vite build

vite v8.2.1 building client environment for production...
[2K
transforming...✓ 18 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.47 kB │ gzip:  0.30 kB
dist/assets/index-Kn7b73lK.css    6.91 kB │ gzip:  2.33 kB
dist/assets/index-CW_Df-OD.js   205.93 kB │ gzip: 64.13 kB

✓ built in 415ms
```


