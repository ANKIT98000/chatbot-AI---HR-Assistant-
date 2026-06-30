# Base image Python 3.10
FROM python:3.10

# Working directory set kar rahe hain
WORKDIR /code

# Requirements file copy karke install karo
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Saara code copy karo
COPY . .

# FastAPI ko port 7860 par run karne ki command
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]