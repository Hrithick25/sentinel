"""
Backward-compatible setup.py.
Primary config is in pyproject.toml (PEP 621).
This file exists for `pip install -e .` compatibility on older pip versions.
"""
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = ""
readme = here / "README.md"
if readme.exists():
    long_description = readme.read_text(encoding="utf-8")

setup(
    name="sentinel-guardrails-sdk",
    version="4.0.0",
    description="SENTINEL — Drop-in LLM Trust & Safety SDK. 19-agent parallel mesh.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="SENTINEL Labs",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(include=["sentinel", "sentinel.*"]),
    package_data={"sentinel": ["py.typed"]},

    # ── Core SDK: ULTRA-LIGHTWEIGHT (~2MB) ────────────────────────────────────
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.7.0",
    ],
    extras_require={
        # LLM framework integrations
        "langchain": ["langchain-core>=0.1.0"],
        "llamaindex": ["llama-index-core>=0.10.0"],

        # Self-hosted gateway (Docker)
        "server": [
            "fastapi>=0.111.0", "uvicorn[standard]>=0.29.0",
            "pydantic-settings>=2.2.0", "python-dotenv>=1.0.1",
            "sqlalchemy>=2.0.30", "asyncpg>=0.29.0", "alembic>=1.13.1",
            "redis>=5.0.4", "python-jose[cryptography]>=3.3.0",
            "passlib[bcrypt]>=1.7.4", "python-multipart>=0.0.9",
            "orjson>=3.10.3", "websockets>=12.0", "prometheus-client>=0.20.0",
        ],

        # Supabase cloud backend
        "supabase": [
            "supabase>=2.4.0",
            "pydantic-settings>=2.2.0", "python-dotenv>=1.0.1",
        ],

        # ML/NLP agents
        "ml": [
            "sentence-transformers>=2.7.0", "faiss-cpu>=1.8.0",
            "spacy>=3.7.4", "transformers>=4.40.0", "torch>=2.2.0",
            "detoxify>=0.5.2", "numpy>=1.26.4",
        ],

        # Kafka audit layer
        "kafka": ["aiokafka>=0.10.0"],

        # Everything
        "full": [
            # Server
            "fastapi>=0.111.0", "uvicorn[standard]>=0.29.0",
            "pydantic-settings>=2.2.0", "python-dotenv>=1.0.1",
            "sqlalchemy>=2.0.30", "asyncpg>=0.29.0", "alembic>=1.13.1",
            "redis>=5.0.4", "python-jose[cryptography]>=3.3.0",
            "passlib[bcrypt]>=1.7.4", "python-multipart>=0.0.9",
            "orjson>=3.10.3", "websockets>=12.0", "prometheus-client>=0.20.0",
            # ML
            "sentence-transformers>=2.7.0", "faiss-cpu>=1.8.0",
            "spacy>=3.7.4", "transformers>=4.40.0", "torch>=2.2.0",
            "detoxify>=0.5.2", "numpy>=1.26.4",
            # Kafka
            "aiokafka>=0.10.0",
            # Frameworks
            "langchain-core>=0.1.0", "llama-index-core>=0.10.0",
            # Payments
            "stripe>=9.5.0",
        ],
        "dev": [
            "pytest>=8.2.0", "pytest-asyncio>=0.23.6",
            "ruff>=0.4.0", "mypy>=1.10.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sentinel-gateway=sentinel.gateway.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Security",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    project_urls={
        "Homepage": "https://github.com/sentinel-ai/sentinel-sdk",
        "Documentation": "https://docs.sentinel-ai.dev",
        "Repository": "https://github.com/sentinel-ai/sentinel-sdk",
        "Issues": "https://github.com/sentinel-ai/sentinel-sdk/issues",
    },
)
