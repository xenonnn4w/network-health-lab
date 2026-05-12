FROM python:3.12-alpine3.22
RUN apk add --no-cache iproute2 iptables bind-tools curl
WORKDIR /opt/lab
COPY health.py /opt/lab/health.py
CMD ["sleep", "infinity"]
