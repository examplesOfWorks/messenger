FROM python:3.13-slim
RUN groupadd -r groupfastapi && useradd -r -g groupfastapi userchat

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=userchat:groupfastapi . .

RUN mkdir -p /app/media \
    && chown -R userchat:groupfastapi /app/media

EXPOSE 8000

USER userchat
