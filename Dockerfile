FROM pytorch/pytorch:2.4.0-cuda11.8-cudnn9-runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y git curl

ENV PYTHONPATH="${PYTHONPATH}:/app/src"

RUN mkdir -p /app/src

RUN addgroup --system python && adduser --system --group python
RUN chown -R python:python /app
USER python

ENV VIRTUAL_ENV=/app/.venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV TZ=UTC

COPY requirements.txt requirements.txt
RUN uv pip install --upgrade pip; uv pip install -r requirements.txt

WORKDIR /app
COPY --chown=python:python ./src/download_models.py ./src/download_models.py
RUN mkdir -p /app/models; python src/download_models.py

WORKDIR /app
COPY --chown=python:python ./src/. ./src