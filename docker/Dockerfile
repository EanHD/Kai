FROM python:3.11-slim

# Install scientific computing libraries
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.2 \
    matplotlib==3.7.1 \
    scipy==1.10.1

# Create non-root user for execution
RUN useradd -m -u 1000 sandbox && \
    mkdir -p /workspace && \
    chown sandbox:sandbox /workspace

# Set working directory
WORKDIR /workspace

# Switch to non-root user
USER sandbox

# Default command (will be overridden)
CMD ["python"]
