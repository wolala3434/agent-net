# Agent Internet Dashboard
FROM node:22-alpine AS build

WORKDIR /app

COPY dashboard/package*.json ./
RUN npm ci

COPY dashboard/ ./
RUN npm run build

FROM nginx:1.27-alpine

COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
