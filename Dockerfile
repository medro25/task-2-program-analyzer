# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jre-jammy

ARG JOERN_VERSION=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOERN_HOME=/opt/joern \
    JOERN_PATH=/opt/joern/joern-cli/joern

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3 \
        python3-pip \
        python3-venv \
        unzip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt joern-install.sh ./

RUN python -m pip install --no-cache-dir -r requirements.txt \
    && chmod +x ./joern-install.sh \
    && ./joern-install.sh --install-dir=/opt/joern ${JOERN_VERSION:+--version=$JOERN_VERSION} \
    && rm -f joern-cli-*.zip

COPY . .

RUN python -m unittest discover -s tests

VOLUME ["/app/reports"]

ENTRYPOINT ["python", "analyzer.py"]
CMD ["dataset"]
