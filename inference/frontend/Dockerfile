# Simple static frontend image
FROM nginx:1.27-alpine

# Remove default index
RUN rm -rf /usr/share/nginx/html/*

# Copy frontend assets
COPY . /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 6500

# Use default Nginx CMD
