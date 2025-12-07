# FastAPI Backend Deployment Guide

This project can run locally for development or inside Docker for production.
Follow the steps below depending on your environment.

---

## 🚀 Run Locally (Development Mode)

1. Go to the project directory:
```bash
$ uvicorn app.main:app --reload
```
---

## 🐳 Deploy Using Docker & GitHub Container Registry (GHCR)

### 1️⃣ Login to GitHub Container Registry

Before pulling your private image, authenticate:

```bash
$ docker login ghcr.io -u ashehta700
```

> The password is your **GitHub Personal Access Token (PAT)**  
> (not your GitHub account password).

---

### 2️⃣ Pull the latest Docker image

```bash
docker pull ghcr.io/ashehta700/fastapi-app:latest
```

---

### 3️⃣ Prepare environment variables

Make sure you have a valid `.env` file, for example:

```bash
D:\my main laptop\Geo Makanii\SGS project\Website Backend\Fast API\app.env
```
---

### 4️⃣ Run the FastAPI app inside Docker

This command:

- Loads your `.env` file  
- Exposes port `8000`  
- Maps Windows static folder → container static folder  
- Uses your latest GHCR image  


```bash 
$ docker run -d --name fastapi_app --env-file "D:\my main laptop\Geo Makanii\SGS project\Website Backend\Fast API\app\.env"
-p 8000:8000 -v D:\static_fast_api:/app/static
ghcr.io/ashehta700/fastapi-app:latest

```


---

## 🔄 Updating to a New Image Version

Whenever you push to **master**, CI/CD builds and publishes a new Docker image.

To update your server:

### 1️⃣ Stop the running container

```bash
$ docker stop fastapi_app
```

### 2️⃣ Remove the old container

```bash 
$ docker rm fastapi_app
```

### 3️⃣ Pull the updated latest image

```bash 
$ docker pull ghcr.io/ashehta700/fastapi-app:latest
```

### 4️⃣ Run again using the same command:

```bash 

$ docker run -d `
   --name fastapi_app `
   --env-file "D:\my main laptop\Geo Makanii\SGS project\Website Backend\Fast API\app\.env_copy" `
   -e APP_STATIC_ROOT="/app/static" `
   -v "D:\static_backend_files_test:/app/static" `
   -p 8000:8000 `
   fastapi-fastapi_app

   
```

---

## 🗂 Folder Mapping (Important)

**Windows Folder**  


```bash
D:\static_fast_api
```
**Inside Container**  

```bash 
/app/static
````

FastAPI always serves static files at:

```bash
/static
```

So a file at:

```bash
D:\static_fast_api\profile_images\29.png
```

Will be accessible at:

```bash
http://<server-ip>:8000/static/profile_images/29.png
```
---

## ✔ CI/CD Enabled  
💡 When you push to **master**, GitHub Actions automatically:

1. Builds a new Docker image  
2. Tags it as `latest`  
3. Pushes it to GitHub Container Registry (GHCR)  
4. Ready to pull on your server  

---

# 📌 Final Notes

- No static files are stored inside the container  
- Everything persists on the Windows folder  
- You can safely remove the container and recreate it anytime  
- The image stays small and clean  

