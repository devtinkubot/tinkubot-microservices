FROM redis:7-alpine
RUN apk add --no-cache tzdata
ENV TZ=America/Guayaquil
COPY redis.conf /etc/redis/redis.conf
CMD ["redis-server", "/etc/redis/redis.conf"]
