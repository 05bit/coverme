FROM alpine:3.12

RUN apk --no-cache add \
  bash \
  build-base \
  ca-certificates \
  curl \
  postgresql \
  python3 \
  py3-pip

RUN pip3 install coverme>=0.6.2

COPY etc/periodic/ /etc/periodic/

RUN chmod -R +x /etc/periodic/

CMD ["/usr/sbin/crond", "-f"]
