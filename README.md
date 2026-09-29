# DIT349 – Assignment 3: Architectural Styles in Code

Three independent modules, one per architectural style. Each has its own README,
`requirements.txt` and test suite.

| Module | Style | Directory |
|---|---|---|
| 1 | Pipe-and-Filter | `module1-pipeline/` |
| 2 | Microservices | `module2-microservices/` |
| 3 | Publish-Subscribe | `module3-pubsub/` |

Requirements: Python 3.10+. Run `python -m pytest -q` inside a module directory.
The CI pipeline (`.gitlab-ci.yml`) runs the same tests on every push; do not edit
that file or the `tests/` directories.
