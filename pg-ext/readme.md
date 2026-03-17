# docker

### 1. build dockerfile
```bash
docker build -t pg-ext:dev .
```

### 2. save docker image
```bash
docker save -o ./pg-ext-dev.tar pg-ext:dev
```

### 2. load docker image
```bash
docker load -i pg-ext-dev.tar
```

### 3. run docker container
```bash
docker run -d --name pg-ext -p 9432:5432 -e POSTGRES_DB=rag -e POSTGRES_HOST_AUTH_METHOD=trust pg-ext:dev
```