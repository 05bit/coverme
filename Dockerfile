FROM alpine:3.18

RUN apk --no-cache add \
  bash \
  build-base \
  ca-certificates \
  curl \
  postgresql15-client \
  mysql-client \
  python3 \
  py3-pip

RUN pip3 install coverme>=0.8.0

COPY etc/periodic/ /etc/periodic/

RUN chmod -R +x /etc/periodic/

CMD ["/usr/sbin/crond", "-f"]
