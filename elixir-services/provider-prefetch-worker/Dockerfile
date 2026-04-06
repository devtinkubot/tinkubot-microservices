FROM elixir:1.17-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mix local.hex --force && mix local.rebar --force

COPY mix.exs mix.lock* ./
COPY config ./config
RUN mix deps.get --only prod
RUN MIX_ENV=prod mix deps.compile

COPY lib ./lib
RUN MIX_ENV=prod mix compile
RUN MIX_ENV=prod mix release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    openssl \
    ca-certificates \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV MIX_ENV=prod
ENV LANG=C.UTF-8

COPY --from=build /app/_build/prod/rel/provider_prefetch_worker ./

CMD ["/app/bin/provider_prefetch_worker", "start"]
