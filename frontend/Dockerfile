FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.28-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/default.conf.template /etc/nginx/templates/default.conf.template
ENV AGENT_UPSTREAM=http://backend:8000
ENV NGINX_ENVSUBST_FILTER=^AGENT_UPSTREAM$
EXPOSE 80
