# SunChat Frontend Dockerfile

FROM node:18-alpine

WORKDIR /app

# 复制依赖
COPY package*.json ./
RUN npm install --production

# 复制代码
COPY . .

# 构建
RUN npm run build

# 暴露端口
EXPOSE 3000

# 启动命令
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "3000"]
