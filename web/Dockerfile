# --- Build stage ---
FROM node:20 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build


# --- Production stage ---
# Pinned: nginx < 1.31.9 is affected by CVE-2026-123007 (NGINX2Root), see SCRUM-106.
FROM nginx:1.31.10-alpine

# Copy Vite production build to Nginx
COPY --from=builder /app/dist /usr/share/nginx/html
RUN rm /etc/nginx/conf.d/default.conf
COPY ./nginx-conf/default.conf /etc/nginx/conf.d/default.conf



# Nginx already listens on 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
