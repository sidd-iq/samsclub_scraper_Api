# Use an official Python runtime as the base image
FROM python:3.10-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the application code to the container
COPY app/main.py .

# Install the required dependencies
RUN python -m pip install --upgrade pip

RUN pip install  httpx fake-useragent fastapi uvicorn


# Expose the port on which the FastAPI application runs
EXPOSE 8000

# Start the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
