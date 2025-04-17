# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools if needed (e.g., for packages with C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Image ---
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user and group
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --no-create-home appuser

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY phase1/ /app/phase1/
COPY phase1_ui.py /app/
# Copy .env loading depends on it being in the build context or provided at runtime
# If needed at build time only (unlikely for this service), copy from builder
# COPY --from=builder /build/.env /app/.env

# Adjust permissions for non-root user
# Ensure the app directory and code are owned by the appuser
# Need to own site-packages too? Usually not needed if installed globally
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 7860

# Command to run the application
# The Gradio app already listens on 0.0.0.0:7860 due to previous edits
CMD ["python", "phase1_ui.py"] 