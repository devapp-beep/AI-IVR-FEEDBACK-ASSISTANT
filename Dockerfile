# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy credentials file
COPY credentials.json /app/credentials.json

# Copy project files into the container
COPY . /app


# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port if your app uses Flask or FastAPI
EXPOSE 8000

# Command to run your Python script
CMD ["python", "app.py"]
