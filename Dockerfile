FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && \
    curl -L -o /tmp/xray.zip https://github.com/XTLS/Xray-core/releases/latest/download/Xray-linux-64.zip && \
    unzip /tmp/xray.zip -d /usr/local/bin xray && \
    chmod +x /usr/local/bin/xray && \
    rm /tmp/xray.zip && \
    apt-get remove -y unzip && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
