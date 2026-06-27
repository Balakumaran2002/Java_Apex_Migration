# AI-Powered Java Migration & Conversion Engine: Complete Reconstruction Guide

Welcome! This guide explains the entire project from scratch, using simple explanations (like explaining to a baby!) and provides step-by-step instructions to recreate the project if it is ever deleted by mistake.

---

## 🧸 Let's Understand the Project 

Think of this project as a **smart toy workshop**:
1. **The Painter (Frontend - React + Vite):** This is the screen you see. It has buttons, charts, and boxes. It draws everything beautifully and tells the brain what button you clicked.
2. **The Worker's Brain (Backend - FastAPI):** This is the master. It listens to the Painter's requests. When the Painter says "Run this", the Brain starts working.
3. **The Mailbox (Redis):** If a job is too big (like converting a huge project), the Brain doesn't want to freeze. It drops a message in the Mailbox (Redis).
4. **The Helper (Celery Worker):** This helper sits next to the Mailbox. As soon as a message drops in, it picks it up, runs the long job in the background, and updates the Mailbox.
5. **The Smart Friend (Google Gemini/OpenAI/Groq):** When we get stuck with a compiler error or need code converted, the Brain asks this Smart Friend for help, and it gives us the fixed code. If Gemini is too busy, it automatically falls back to Groq!
6. **The Library (RAG & FAISS):** This is a bookshelf of migration manuals. The helper looks through these books to find tips on how to upgrade Java code.
7. **The Playground (Project Runner & Live Preview):** Once the project is upgraded, the Brain builds it and starts it up internally, allowing you to play with the converted Java app directly inside the Painter's screen without leaving the app!

---

## 📁 Directory Structure

Here is how the folders are structured on your computer:

```text
java_convertion/
├── explanatiom.md                      <-- This Guide File
├── apache-maven-3.9.6/                 <-- Bundled Maven build tool
├── knowledge_base/                     <-- Markdown files containing Java upgrade instructions
│   └── java_rules.md                   <-- Example rule sheet
├── python_backend/                     <-- Backend Folder
│   ├── .env                            <-- Environment Variables (API Keys, config)
│   ├── main.py                         <-- FastAPI Entry Point
│   ├── requirements.txt                <-- Python Library Dependencies
│   └── app/
│       ├── __init__.py
│       ├── celery_app.py               <-- Celery configuration
│       ├── config.py                   <-- Config loader (with python-dotenv!)
│       ├── models.py                   <-- Request/Response models
│       ├── tasks.py                    <-- Background task functions
│       ├── ai/
│       │   ├── __init__.py
│       │   ├── ai_factory.py           <-- Factory to choose Gemini/OpenAI/Groq/Ollama
│       │   ├── gemini_client.py        <-- Gemini API Client
│       │   ├── groq_client.py          <-- Groq API Client
│       │   └── fallback_client.py      <-- Smart Failover Network (Handles rate limits)
│       └── services/
│           ├── analysis_service.py     <-- Clones and checks target Java code
│           ├── migration_service.py    <-- Runs OpenRewrite AST transformations
│           ├── build_validation.py     <-- Compiles code and triggers AI self-healing
│           ├── code_conversion.py      <-- Converts Java files to Python FastAPI files
│           ├── execution_service.py    <-- Runs/Simulates code startup and logs
│           ├── project_runner_service.py<-- Dynamically boots migrated Java web apps
│           ├── rag_service.py          <-- Vectorizes knowledge_base using FAISS
│           └── report_service.py       <-- Generates PDF reports using ReportLab
└── frontend/                           <-- Frontend Folder
    ├── package.json                    <-- Node.js Dependencies and Scripts
    ├── index.html                      <-- Webpage template
    ├── tailwind.config.js              <-- CSS styling rules
    └── src/
        ├── main.jsx                    <-- React app mounting point
        ├── App.jsx                     <-- Page router and layouts
        ├── api.js                      <-- Backend API endpoints caller
        ├── components/
        │   ├── LivePreviewPanel.jsx    <-- Embeds running Java app in an iframe
        │   ├── ChatbotWidget.jsx       <-- Floating RAG Chatbot
        │   └── ExecutionConsole.jsx    <-- Terminal Emulator
        └── pages/
            ├── Dashboard.jsx           <-- Project Summary and Metrics
            ├── RepositoryAnalysis.jsx  <-- Git repository analysis UI
            ├── MigrationCenter.jsx     <-- Target versions selection and progress log
            ├── MigrationReport.jsx     <-- PDF viewing and diff code explorer
            └── CodeConversionCenter.jsx<-- Drag-and-drop Java files conversion UI
```

---

## 🛠️ Step-by-Step Reconstruction Guide

If the project is deleted, follow these exact baby steps to build it again from scratch:

### **Step 1: Install Prerequisites**
Make sure you have these programs installed on your Windows machine:
1. **Node.js** (v18 or higher) - [Download from nodejs.org](https://nodejs.org/)
2. **Python** (3.10 or 3.11) - [Download from python.org](https://www.python.org/)
3. **Redis Server** (For Windows, you can run it via WSL or use Memurai or a native windows port).
4. **Git** - [Download from git-scm.com](https://git-scm.com/)
5. **Java JDK 17, 21, or 25** - Make sure `JAVA_HOME` environment variable is set.

---

### **Step 2: Recreate the Backend**

1. Create a folder named `python_backend`.
2. Inside `python_backend`, create a file named `requirements.txt` and paste this:
   ```text
   fastapi
   uvicorn
   pydantic
   gitpython
   reportlab
   faiss-cpu
   sentence-transformers
   numpy
   google-genai
   openai
   ollama
   httpx
   python-multipart
   groq
   celery
   redis
   python-dotenv
   ```
3. Create a file named `.env` and paste this (replace placeholder keys with your active keys):
   ```ini
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL_NAME=gemini-2.5-flash
   OPENAI_API_KEY=your_openai_api_key_here
   GROQ_API_KEY=your_groq_api_key_here
   GROQ_MODEL_NAME=llama-3.3-70b-versatile
   APP_WORK_DIR=workspace
   REDIS_URL=redis://localhost:6379/0
   ```

*(Due to length limits, script file recreation steps are abbreviated. You can reference the actual python_backend/app directory for the source scripts).*

---

### **Step 3: Setup and Start the Backend Environment**

Open your PowerShell terminal and run:

```powershell
# 1. Enter the backend folder
cd python_backend

# 2. Create Python virtual environment (use Python 3.10/3.11 for safety!)
py -m venv venv

# 3. Activate the virtual environment
.\venv\Scripts\activate

# 4. Install all Python packages
pip install -r requirements.txt

# 5. Start the FastAPI server (Runs on port 8000)
python main.py
```

Open a **second terminal** to start the Celery Worker (which listens to the Redis queue on Windows):

```powershell
# 1. Enter the backend folder and activate virtual environment
cd python_backend
.\venv\Scripts\activate

# 2. Start Celery worker using solo pool (crucial for Windows!)
celery -A app.celery_app.celery_app worker --loglevel=info -P solo
```

---

### **Step 4: Recreate the Frontend**

1. Create a folder named `frontend`.
2. Generate Vite app: `npm create vite@latest . -- --template react`
3. Run commands to install packages and start the frontend:
   ```powershell
   # 1. Enter frontend folder
   cd frontend
   
   # 2. Install node packages
   npm install
   npm install tailwindcss postcss autoprefixer axios react-router-dom lucide-react
   
   # 3. Start Vite developer server (Runs on port 5173)
   npm run dev
   ```

---

## 🌟 Key Backend Pipelines Explained

### **1. Repository Analysis pipeline (`/api/analyze`)**
- Clones a remote repository to the `python_backend/workspace/` folder.
- Scans `pom.xml` or `build.gradle` to extract Java and Spring Boot versions.
- Generates vectors of raw configuration files and searches the local FAISS index (built on `knowledge_base/*.md` files) for relevant migration instructions.
- Passes files + RAG search results to the selected AI Provider to create a migration plan.

### **2. AST Migration & Compiler Resilience (`/api/migrate`)**
- Receives version target (e.g. Java 17, 21, or 25).
- Automatically patches `pom.xml` files with robust compiler settings (e.g., dynamically bumping `lombok.version` to `1.18.42` to prevent `TypeTag :: UNKNOWN` crashes on JDK 25).
- Runs **OpenRewrite Recipes** command to completely restructure the AST.
- Invokes **Build Validation** (`mvn clean compile`). If compilation errors occur:
  - Captures compiler stdout.
  - Sends stdout to AI Factory.
  - AI returns precise JSON replacements to edit compiler-broken files.
  - Re-runs build validation (supports up to 3 self-healing attempts).

### **3. The Playground: Project Runner & Live Preview (`/api/run/*`)**
- This module allows users to compile and launch migrated Java applications dynamically!
- **Port Allocation**: The `project_runner_service.py` automatically scans for an open local port (e.g., 8081).
- **Execution**: It spawns a background process running `mvn spring-boot:run -Dspring-boot.run.arguments=--server.port=8081`.
- **Proxy**: It proxies incoming frontend requests from `http://localhost:8000/api/preview/...` straight to the Java backend.
- **UI Integration**: The frontend uses a `LivePreviewPanel.jsx` iframe component, effectively embedding the migrated Java app seamlessly inside the Migration Assistant.

### **4. Smart AI Fallback Network (`ai_factory.py`)**
- Sometimes Google Gemini hits a rate limit (HTTP 429 Too Many Requests). 
- To prevent the migration tool from crashing, the AI factory dynamically creates a `FallbackClient`.
- If a request fails, the `FallbackClient` automatically reroutes the prompt to the ultra-fast Groq API (`llama-3.3-70b-versatile`), completely hiding the failure from the user and keeping the workflow smooth.

### **5. Chatbot Assistant (`/api/chat`)**
- On startup, the backend chunks markdown documents in `knowledge_base` and indexes them in a local FAISS store via `all-MiniLM-L6-v2`.
- It dynamically queries this index when the user asks a question, providing repository-aware and rule-aware context.

---

## 👶 Summary: How to run it every day

1. Open **Redis Server** (ensure it's running).
2. Start **FastAPI Backend**:
   - `cd python_backend`
   - `.\venv\Scripts\activate`
   - `python main.py`
3. Start **Celery Worker**:
   - `cd python_backend`
   - `.\venv\Scripts\activate`
   - `python -m celery -A app.celery_app.celery_app worker -P solo` (Note: Using `python -m celery` is critical on Windows to ensure Celery runs inside the active virtual environment instead of a global script path)
4. Start **React Frontend**:
   - `cd frontend`
   - `npm run dev`
5. Open your browser to **[http://localhost:5173/](http://localhost:5173/)**!
