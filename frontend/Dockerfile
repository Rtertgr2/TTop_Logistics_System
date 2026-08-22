FROM node:20-alpine AS build

WORKDIR /app

# คัดลอก package files
COPY package*.json ./

# ติดตั้ง dependencies (npm ci = reproducible, faster than npm install)
RUN npm ci

# คัดลอก source code
COPY . .

# Build production
RUN npm run build

# Production stage
FROM nginx:alpine

# คัดลอก nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# คัดลอก build files
COPY --from=build /app/dist /usr/share/nginx/html

# ตั้งสิทธิ์ให้ nginx user (ไม่รัน as root)
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown nginx:nginx /var/run/nginx.pid

USER nginx

# Expose port
EXPOSE 80

# เริ่ม nginx
CMD ["nginx", "-g", "daemon off;"]
