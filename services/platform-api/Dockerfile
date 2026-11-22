# platform-api image: one image for the private API, the public hook receiver and the jobs.
# PLATFORM_APP_MODE (api or hooks) chooses the mode at run time; `platform-cli job <name>`
# runs a job from the same image. Cloud Run sends traffic to port 8080, its default $PORT.
#
# Build from the REPOSITORY ROOT, because the service depends on packages/substack-desk, which
# lies outside services/platform-api:
#   docker build -f services/platform-api/Dockerfile -t platform-api:local .
# The files that enter the build are listed in services/platform-api/Dockerfile.dockerignore.

# Stage 1: build the virtual environment. Dependencies first, so that a change to the
# service's src/ reuses the cached dependency layer. The layout of the repository is kept
# (/app/packages/substack-desk, /app/services/platform-api) so that the path in
# [tool.uv.sources] resolves.
FROM python:3.12-slim AS build
# uv, pinned, installed from PyPI into the build stage only
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY packages/substack-desk/pyproject.toml packages/substack-desk/README.md ./packages/substack-desk/
COPY services/platform-api/pyproject.toml services/platform-api/uv.lock ./services/platform-api/
WORKDIR /app/services/platform-api
# Third-party dependencies only: the project and the local substack-desk package come later.
RUN uv sync --frozen --no-dev --no-install-project --no-install-local
COPY packages/substack-desk/src /app/packages/substack-desk/src
COPY services/platform-api/src ./src
RUN uv sync --frozen --no-dev --no-editable

# Stage 2: the runtime. Only the virtual environment is copied: no uv, no sources, no tests.
FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1
WORKDIR /app
USER 10001
EXPOSE 8080
CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
