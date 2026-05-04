FROM python:3.12-slim

WORKDIR /app

# Copy project metadata and source together so the editable install
# can find the package.  We copy pyproject.toml + src/ first so that
# Docker can cache the pip install layer when only test/config files change.
COPY pyproject.toml ./
COPY src/ ./src/

# Install the package (editable) with dev extras
RUN pip install --no-cache-dir -e ".[dev]"

# Copy everything else (tests, alembic, etc.)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "medminder.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]
