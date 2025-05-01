# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY ./backend/requirements.txt /app/backend/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the entire backend directory (including prompts) into the container WORKDIR/backend
# This makes paths relative to /app/backend inside the container
COPY ./backend /app/backend
COPY ./frontend /app/frontend 

# Expose the port the app runs on
# Use ARG to allow overriding port via docker-compose build args if needed, default to 5001
ARG PORT=5001
ENV PORT=${PORT}
EXPOSE ${PORT}

# Define the command to run the application
# It will run from /app, so Python needs to target the script inside the backend subdir
CMD ["python", "backend/app.py"]