# Vector Search Project

This Django project implements a vector search system that allows users to upload documents, process them into a vector database, and perform semantic searches on the processed documents.

## Requirements

- Python 3.8+
- Django
- langchain
- sentence-transformers
- faiss-cpu
- PyPDF2
- beautifulsoup4

## Setup

1. Clone the repository:
   ```
   git clone <repository-url>
   cd vector-search-project
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install django langchain sentence-transformers faiss-cpu PyPDF2 beautifulsoup4
   ```

4. Initialize the Django project:
   ```
   python manage.py makemigrations
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. Run the development server:
   ```
   python manage.py runserver
   ```

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