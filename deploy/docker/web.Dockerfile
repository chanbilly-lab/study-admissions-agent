ARG NODE_IMAGE
ARG NGINX_IMAGE
FROM ${NODE_IMAGE} AS builder
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate \
    && pnpm install --frozen-lockfile
COPY apps/web/index.html apps/web/tsconfig.json apps/web/vite.config.ts ./
COPY apps/web/src ./src
COPY packages/contracts /build/packages/contracts
ENV VITE_APP_MODE=auth VITE_AUTH_API_BASE_URL=/api
# This command is defined for a future operator build; it was not executed in T42.
RUN pnpm run build

FROM ${NGINX_IMAGE} AS runtime
RUN groupadd --gid 10001 study \
    && useradd --uid 10001 --gid study --no-create-home study
COPY --from=builder /build/apps/web/dist /usr/share/nginx/html
COPY deploy/docker/nginx.conf.template deploy/docker/proxy.conf deploy/docker/start-web.sh /opt/study/
USER 10001:10001
EXPOSE 8443
ENTRYPOINT ["sh", "/opt/study/start-web.sh"]
