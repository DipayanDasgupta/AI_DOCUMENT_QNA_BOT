# frontend/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# Includes app.py and the .streamlit directory
COPY . .

# Make port 8501 available to the world outside this container (Streamlit default port)
EXPOSE 8501

# Define environment variable defaults (optional, can be overridden at runtime)
# Backend URL will likely be different in deployed environment (e.g., service name)
ENV BACKEND_URL="http://backend:8000" # Default assumes a service named 'backend' on port 8000
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 # Allow connections from outside the container

# Run app.py when the container launches
# Use the 'streamlit run' command
# --server.enableCORS=false might be needed depending on setup, but usually fine with 0.0.0.0
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
