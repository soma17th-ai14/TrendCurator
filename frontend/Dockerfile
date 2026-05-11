FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir streamlit requests

COPY frontend/streamlit_app.py ./streamlit_app.py

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
