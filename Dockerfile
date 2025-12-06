FROM public.ecr.aws/lambda/python:3.11

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy all source files (required for hatch build)
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package (includes dependencies)
RUN uv pip install --system .

# Set the Lambda handler
CMD ["productivity_service.main.handler"]
