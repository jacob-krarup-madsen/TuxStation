FROM ghcr.io/blue-build/cli:latest AS builder
COPY . /config
RUN /blue-build build /config/recipe.yml

FROM scratch
COPY --from=builder / /
