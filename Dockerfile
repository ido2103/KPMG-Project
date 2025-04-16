# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /code

# Install system dependencies
# - supervisor for process management
# - git needed if any dependencies install from git repos (sometimes indirectly)
RUN apt-get update && apt-get install -y supervisor git && rm -rf /var/lib/apt/lists/*

# Copy dependency definition files first for layer caching
COPY app/requirements.txt /code/app/
# If you have a root requirements.txt that includes Phase 1 + Frontend deps, use it instead:
# COPY requirements.txt /code/

# Install Python dependencies
# Install backend deps first
RUN pip install --no-cache-dir -r app/requirements.txt

# Install Phase 1 UI and Phase 2 Frontend specific deps if not in a root requirements.txt
# Assumes these are the core runtime dependencies needed beyond the backend ones.
# NOTE: Ensure all dependencies for phase1_ui.py are also included here or in app/requirements.txt
RUN pip install --no-cache-dir \
    gradio \
    requests \
    azure-ai-documentintelligence

# Copy the rest of the application code
# This will copy everything in the build context (current directory)
# IMPORTANT: This assumes the user has run data_ingest/build_vector_store.py locally first
# so that vector_store.faiss and vector_store_metadata.json exist in the context.
COPY . /code/

# Remove explicit COPY for vector store files, rely on COPY . above
# COPY vector_store.faiss /code/
# COPY vector_store_metadata.json /code/

# Copy the supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create log directory for supervisor
RUN mkdir -p /var/log

# Expose the ports the applications will run on
EXPOSE 8000 
EXPOSE 7860 
EXPOSE 7861

# Command to run supervisor which will start all the services
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"] 