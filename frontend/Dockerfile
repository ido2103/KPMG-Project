# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

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
COPY frontend/ /app/frontend/

# Set environment variable for backend URL (using service name from docker-compose)
ENV BACKEND_API_URL=http://rag_api:8000

# Adjust permissions for non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 7861

# Command to run the application
# The Gradio app already listens on 0.0.0.0:7861 due to previous edits
CMD ["python", "frontend/ui.py"] 