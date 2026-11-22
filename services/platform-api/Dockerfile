# platform-api image: one image for the private API, the public hook receiver and the jobs.
# PLATFORM_APP_MODE (api or hooks) chooses the mode at run time; `platform-cli job <name>`
# runs a job from the same image. Cloud Run sends traffic to port 8080, its default $PORT.

# Stage 1: build the virtual environment. Dependencies first, so that a change to src/
# reuses the cached dependency layer.
FROM python:3.12-slim AS build
# uv, pinned, installed from PyPI into the build stage only
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
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
