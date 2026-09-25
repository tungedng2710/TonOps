ARG CLEARML_SERVER_BASE=clearml/server:latest

# Build the checked-in Angular application and report widgets.
FROM node:20-bookworm-slim AS webapp
WORKDIR /src/clearml-web
RUN corepack enable && corepack prepare pnpm@10.18.3 --activate
COPY clearml-web/package.json clearml-web/pnpm-lock.yaml clearml-web/pnpm-workspace.yaml clearml-web/.npmrc ./
RUN pnpm install --frozen-lockfile
COPY clearml-web/ ./
ENV NODE_OPTIONS=--max-old-space-size=4096
RUN pnpm run build && pnpm run build-widgets

# Keep the upstream ClearML runtime and replace its OSS source with this fork.
FROM ${CLEARML_SERVER_BASE} AS runtime
COPY clearml-server/apiserver/ /opt/clearml/apiserver/
COPY clearml-server/fileserver/ /opt/clearml/fileserver/
RUN rm -rf /usr/share/nginx/html /usr/share/nginx/widgets
COPY --from=webapp /src/clearml-web/build/browser/ /usr/share/nginx/html/
COPY --from=webapp /src/clearml-web/dist/report-widgets/browser/ /usr/share/nginx/widgets/
