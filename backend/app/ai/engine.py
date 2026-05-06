"""
NVIDIA NIM AI Engine - Embedding + Similarity Search
Uses OpenAI-compatible API at integrate.api.nvidia.com/v1
"""
import time
import uuid
from typing import List, Optional
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.models.models import Doubt, AIResponseLog, SimilarDoubtMatch, AIConfig, DoubtStatus, DoubtResolution


def get_nvidia_client() -> OpenAI:
    return OpenAI(
        base_url=settings.NVIDIA_BASE_URL,
        api_key=settings.NVIDIA_API_KEY,
    )


def get_ai_config(db: Session) -> AIConfig:
    config = db.query(AIConfig).filter(AIConfig.is_active == True).first()
    if not config:
        # Create default config
        config = AIConfig(
            similarity_threshold=0.75,
            auto_resolve_threshold=0.90,
            max_suggestions=3,
            embedding_model=settings.NVIDIA_EMBEDDING_MODEL,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def generate_embedding(text_input: str) -> Optional[List[float]]:
    """Generate embedding vector using NVIDIA NIM."""
    if not settings.NVIDIA_API_KEY or settings.NVIDIA_API_KEY == "nvapi-your-key-here":
        print("[AI] NVIDIA_API_KEY not configured - skipping embedding")
        return None
    try:
        client = get_nvidia_client()
        response = client.embeddings.create(
            input=[text_input],
            model=settings.NVIDIA_EMBEDDING_MODEL,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "NONE"},
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[AI] Embedding error: {e}")
        return None


def find_similar_doubts(
    db: Session,
    query_embedding: List[float],
    limit: int = 3,
    exclude_doubt_id: Optional[str] = None,
) -> List[dict]:
    """
    Use pgvector cosine similarity to find similar resolved doubts.
    Returns list of dicts with doubt info + resolution.
    """
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
    exclude_clause = f"AND d.id != '{exclude_doubt_id}'" if exclude_doubt_id else ""

    sql = text(f"""
        SELECT
            d.id,
            d.title,
            d.description,
            d.subject,
            dr.answer_text,
            1 - (d.embedding <=> :embedding::vector) AS similarity
        FROM doubts d
        LEFT JOIN doubt_resolutions dr ON dr.doubt_id = d.id
        WHERE d.embedding IS NOT NULL
          AND d.status = 'resolved'
          {exclude_clause}
        ORDER BY d.embedding <=> :embedding::vector
        LIMIT :limit
    """)

    try:
        result = db.execute(sql, {"embedding": embedding_str, "limit": limit})
        rows = result.fetchall()
        return [
            {
                "matched_doubt_id": str(row[0]),
                "matched_title": row[1],
                "matched_description": row[2],
                "subject": row[3],
                "answer_text": row[4],
                "similarity_score": float(row[5]) if row[5] is not None else 0.0,
            }
            for row in rows
        ]
    except Exception as e:
        print(f"[AI] Similarity search error: {e}")
        return []


def store_embedding(db: Session, doubt_id: str, embedding: List[float]):
    """Store embedding vector in the doubts table."""
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
    try:
        db.execute(
            text("UPDATE doubts SET embedding = :emb::vector WHERE id = :id"),
            {"emb": embedding_str, "id": doubt_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[AI] Store embedding error: {e}")


def process_doubt_ai(db: Session, doubt: Doubt) -> dict:
    """
    Full AI pipeline for a newly created doubt:
    1. Generate embedding
    2. Store embedding
    3. Search for similar doubts
    4. Apply decision logic
    5. Log results
    Returns dict with action and suggestions.
    """
    start_time = time.time()
    config = get_ai_config(db)

    query_text = f"{doubt.title}\n{doubt.description}"
    embedding = generate_embedding(query_text)

    if not embedding:
        return {"action": "skipped", "suggestions": [], "reason": "AI not configured"}

    # Store embedding
    store_embedding(db, str(doubt.id), embedding)

    # Search similar
    similar = find_similar_doubts(
        db,
        embedding,
        limit=config.max_suggestions,
        exclude_doubt_id=str(doubt.id),
    )

    processing_ms = int((time.time() - start_time) * 1000)
    top_score = similar[0]["similarity_score"] if similar else 0.0

    # Decision logic
    if top_score >= config.auto_resolve_threshold:
        action = "auto_resolved"
        new_status = DoubtStatus.ai_suggested
    elif top_score >= config.similarity_threshold:
        action = "suggested"
        new_status = DoubtStatus.ai_suggested
    else:
        action = "skipped"
        new_status = DoubtStatus.pending_faculty

    # Update doubt status
    doubt.status = new_status
    db.add(doubt)

    # Log AI response
    log = AIResponseLog(
        doubt_id=doubt.id,
        model_used=settings.NVIDIA_EMBEDDING_MODEL,
        similarity_score=top_score,
        action_taken=action,
        processing_time_ms=processing_ms,
    )
    db.add(log)

    # Store similar matches
    for rank, match in enumerate(similar, start=1):
        if match["similarity_score"] >= config.similarity_threshold:
            sm = SimilarDoubtMatch(
                source_doubt_id=doubt.id,
                matched_doubt_id=uuid.UUID(match["matched_doubt_id"]),
                similarity_score=match["similarity_score"],
                rank=rank,
            )
            db.add(sm)

    db.commit()

    suggestions = [
        {
            "matched_doubt_id": m["matched_doubt_id"],
            "matched_title": m["matched_title"],
            "matched_description": m["matched_description"],
            "similarity_score": m["similarity_score"],
            "answer_text": m["answer_text"],
            "rank": rank,
        }
        for rank, m in enumerate(similar, start=1)
        if m["similarity_score"] >= config.similarity_threshold
    ]

    return {"action": action, "suggestions": suggestions, "top_score": top_score}
