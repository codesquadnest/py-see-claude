FROM python:3.12-slim

# Install system dependencies for process inspection
RUN apt-get update && apt-get install -y --no-install-recommends \
    procps \
    lsof \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir .

# Non-root user for security. Override with --user at runtime
# to match host UID for correct file permissions.
RUN useradd -m -s /bin/sh app
USER app

EXPOSE 3456

# CLAUDE_HOME should point to the mounted .claude directory
ENV CLAUDE_HOME=/home/app/.claude

CMD ["py-see-claude"]
