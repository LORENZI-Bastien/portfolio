FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
 && rm -rf /var/lib/apt/lists/* && useradd -u 1000 -m politique
WORKDIR /app
COPY point_politique.py .
USER politique
ENV PYTHONUNBUFFERED=1
CMD ["python", "point_politique.py"]
