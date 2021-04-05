FROM alpine:3.13

RUN apk --no-cache add \
  bash \
  build-base \
  ca-certificates \
  curl \
  postgresql \
  python3 \
  py3-pip

RUN pip3 install coverme>=0.7.0

COPY etc/periodic/ /etc/periodic/

RUN chmod -R +x /etc/periodic/

CMD ["/usr/sbin/crond", "-f"]
