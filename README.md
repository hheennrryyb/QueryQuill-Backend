# QueryQuill Vector Search Project

QueryQuill is a powerful Django-based vector search system that allows users to upload documents, process them into a vector database, and perform semantic searches on the processed documents. This repository contains the backend code for the QueryQuill project.

## Features

- Document upload and processing
- Vector database creation using FAISS
- Semantic search functionality
- Project management
- User authentication and authorization
- Demo mode for quick testing

## Frontend Repository

The frontend code for QueryQuill can be found at: [https://github.com/hheennrryyb/QueryQuill-Frontend](https://github.com/hheennrryyb/QueryQuill-Frontend)

## Live Demo

Try out QueryQuill live at: [https://query-quill-8pqht.ondigitalocean.app](https://query-quill-8pqht.ondigitalocean.app)

## Requirements

- Python 3.8+
- Django
- langchain
- sentence-transformers
- faiss-cpu
- PyPDF2
- beautifulsoup4

## Comprehensive Setup Instructions

1. Install PostgreSQL:
   - Download and install PostgreSQL from the official website: https://www.postgresql.org/download/
   - During installation, note down the superuser (postgres) password you set

2. Create a PostgreSQL database:
   ```
   psql -U postgres
   CREATE DATABASE vector_search_db;
   \q
   ```

3. Clone the repository:
   ```
   git clone <repository-url>
   cd vector-search-project
   ```

4. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

5. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

6. Update the database configuration in `.env`:
   ```
   DATABASE_URL=postgres://username:password@localhost:5432/vector_search_db
   USE_SQLITE=False  # Set to 'True' to use SQLite
   ```

7. Set up environment variables:
   Create a `.env` file in the project root and add:
   ```
   SECRET_KEY=your_secret_key_here
   DEBUG=True
   ```

8. Apply migrations:
   ```
   python manage.py makemigrations
   python manage.py migrate
   ```

9. Create a superuser:
   ```
   python manage.py createsuperuser
   ```
   Follow the prompts to create your admin account.

10. Run the development server:
    ```
    python manage.py runserver
    ```
    Start Redis Server:
      brew services start redis
      
    Start the Celery worker (in a separate terminal):
      celery -A vector_search_project worker --loglevel=info --pool=solo

11. Access the admin interface:
    Open a browser and go to `http://127.0.0.1:8000/admin/`
    Log in with the superuser credentials you created.

12. Set up the media directory:
    - Create a `media` folder in your project root
    - Update `settings.py` to include:
      ```python
      MEDIA_URL = '/media/'
      MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
      ```

13. Install additional dependencies for vector search:
    ```
    pip install langchain sentence-transformers faiss-cpu PyPDF2 beautifulsoup4
    ```

14. Configure your IDE for the virtual environment:
    - For VS Code, select the Python interpreter from the venv
    - For PyCharm, set the project interpreter to the venv Python


## Usage

1. Upload documents: 
   - Endpoint: POST to `/upload/`
   - Use form-data with key 'documents' and file value(s)

2. Process documents: 
   - Endpoint: POST to `/process/`
   - No body required, processes all unprocessed documents for the user

3. Query documents: 
   - Endpoint: POST to `/query/`
   - Use x-www-form-urlencoded with key 'query' and your search query as value

Note: Ensure you're authenticated before making these requests.

## Project Structure

- `vector_search/`: Main application directory
  - `models.py`: Defines Document and VectorDatabase models
  - `views.py`: Contains views for upload, process, and query endpoints
  - `vector_db_utils.py`: Utility functions for vector database operations

## Configuration

Ensure that the `MEDIA_ROOT` in `settings.py` is correctly configured for your environment. This is where uploaded and processed files will be stored.

## Notes

- This project uses FAISS for efficient similarity search and SentenceTransformer for generating embeddings.
- The system supports PDF and HTML documents. Ensure your uploaded files are in these formats.
