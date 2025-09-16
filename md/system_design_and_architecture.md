# Part 1 — System Design & Architecture

## End-to-end flow
Daily ingestion of user-uploaded product images → preprocessing → enrichment → storage → downstream ML/GenAI.

**Pipeline stages:**
- **Ingestion:** FastAPI upload API + Queue + Object Storage (Bronze)
- **Preprocessing:** Validation, resize (max side 512px), EXIF strip, de-dup (pHash)
- **Enrichment:** CLIP embeddings, OCR, classifier → Delta/SQLite tables
- **Storage & Usage:** Silver (cleaned images), Gold (curated tables), Vector index, Model serving
- **Cross-cutting:** Orchestration (Airflow/Workflows), Monitoring (MLflow), Security (IAM/KMS)

## Diagram (Mermaid)
```mermaid
flowchart LR
    A[Upload API] --> B[Queue/Event Bus]
    B --> C[Bronze: Raw Images]
    C --> D[Preprocessing: validate, resize 512px, pHash]
    D --> E[Enrichment: CLIP, OCR, Classifier]
    E --> F[Silver: Clean Images]
    E --> G[Gold: Curated Tables]
    G --> H[Vector Index]
    H --> I[Apps: Search, Similarity, RAG]
