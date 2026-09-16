# PowerTrace AI frontend: build, then serve as static files behind nginx which
# also proxies the API and the WebSocket. One origin means no CORS, one
# certificate, and a WebSocket that inherits the page's TLS.

FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# VITE_API_BASE is deliberately not set: nginx below puts the API on this same
# origin. Set it only when the backend lives on a different host.
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /src/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
