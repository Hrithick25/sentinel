# Contributing to Sentinel

First off, thank you for considering contributing to Sentinel! It's people like you that make Sentinel such a great tool for AI security.

## Architecture & Codebase

Sentinel is structured as a robust 19-agent mesh with a Python-based Gateway and a React/Node.js Dashboard.

- **Gateway/SDK**: `/sentinel`
- **Dashboard**: `/dashboard`
- **Docs**: Available within `/dashboard/src/pages/Docs.jsx`

## Workflow

1. **Fork** the repo on GitHub
2. **Clone** the project to your own machine
3. **Commit** changes to your own branch
4. **Push** your work back up to your fork
5. Submit a **Pull request** so that we can review your changes

## Local Development

See our `README.md` for full instructions on setting up Sentinel using Docker or lightweight mode.

```bash
# Gateway
python -m venv env
source env/bin/activate
pip install -r requirements.txt
python -m sentinel.gateway.main

# Dashboard
cd dashboard
npm install
npm run dev
```

## Pull Request Guidelines

- Ensure your branch is rebased against the latest `main` branch.
- Run tests before submitting.
- Follow the formatting standards established in the repository.
- Use meaningful commit messages (we recommend [Conventional Commits](https://www.conventionalcommits.org/)).

## Code of Conduct

Please note we have a code of conduct, please follow it in all your interactions with the project.

We look forward to your contributions!
