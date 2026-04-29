FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY . .

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "medminder.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]
