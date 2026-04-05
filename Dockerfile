# Use a slim Python 3.11 image
FROM python:3.11-slim

# Install system dependencies & Node.js 20.x
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000 (required for HF Spaces)
RUN useradd -m -u 1000 user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

# Change ownership to the new user and switch to them
WORKDIR $HOME/app
RUN chown user:user $HOME/app
USER user

# Copy files over, passing ownership to user
COPY --chown=user:user . .

# Install python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install frontend dependencies and build Next.js
# We use npm install here for resilience
RUN cd frontend && npm install && npm run build

# Expose the standard HF Spaces Port
EXPOSE 7860

# Ensure start script has executable permissions
RUN chmod +x start.sh

# Run both the backend and frontend
CMD ["./start.sh"]
