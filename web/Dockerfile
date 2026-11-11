# --- Build stage ---
FROM node:20 AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --include=dev --force
COPY . .
RUN node node_modules/vite/bin/vite.js build 


# --- Production stage ---
FROM nginx:alpine

# Copy Vite production build to Nginx
COPY --from=builder /app/dist /usr/share/nginx/html
RUN rm /etc/nginx/conf.d/default.conf
COPY ./nginx-conf/default.conf /etc/nginx/conf.d/default.conf



# Nginx already listens on 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
