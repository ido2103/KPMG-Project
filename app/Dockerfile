# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build essentials for potential C extensions (like in numpy/faiss)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install ALL dependencies needed for runtime AND ingestion
# This is simpler than managing separate installs across stages for this case
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy ingestion script and data source path reference (relative to build context)
# Ensure the 'assignment' directory structure exists for the script
COPY data_ingest/ /build/data_ingest/
RUN mkdir -p /build/assignment
COPY assignment/phase2_data/ /build/assignment/phase2_data/
# Copy .env for build-time ingestion script (ensure .env is in build context)
COPY .env .

# --- Run Ingestion Script ---
# Define output paths for the ingestion script within the build stage
ENV OUTPUT_INDEX_PATH=/build/vector_store.faiss
ENV OUTPUT_METADATA_PATH=/build/vector_store_metadata.json

RUN python data_ingest/build_vector_store.py

# Check if ingestion artifacts were created
RUN if [ ! -f $OUTPUT_INDEX_PATH ] || [ ! -f $OUTPUT_METADATA_PATH ]; then \
      echo "Vector store files not found after ingestion script ran."; \
      exit 1; \
    fi

# --- Stage 2: Final Image ---
FROM python:3.11-slim

WORKDIR /app

# Create a non-root user and group
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --no-create-home appuser

# Copy installed dependencies from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code from build context
COPY app/ /app/app/

# Copy vector store artifacts from builder stage *into* the /app directory
# Use explicit paths from the builder stage, not ENV vars from that stage
COPY --from=builder /build/vector_store.faiss /app/
COPY --from=builder /build/vector_store_metadata.json /app/

# Adjust permissions for non-root user
# Own the base directory and the copied application code directory
# The vector store files copied above will retain root ownership, which is fine for read-only access.
RUN chown appuser:appgroup /app && \
    chown -R appuser:appgroup /app/app

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 