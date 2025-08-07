FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Install serve globally
RUN npm install -g serve

# Set environment variables
ENV NODE_ENV=production
ENV GENERATE_SOURCEMAP=false
ENV CI=false
ENV PORT=3000

# Expose port
EXPOSE $PORT

# Start command
CMD ["sh", "-c", "serve -s build -l $PORT"]