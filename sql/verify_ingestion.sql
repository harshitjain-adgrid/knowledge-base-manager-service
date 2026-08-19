-- ═══════════════════════════════════════════════════════════════════════════
-- Chotu RAG — pgvector verification queries
--
-- Run these in DataGrip against the tunnelled connection:
--     ssh -i "<your-key>.pem" -N -L 5434:localhost:5434 <user>@<db-host>
--     host=localhost  port=5434  db=vector_qa  user=qa
--
-- Run them top-to-bottom after uploading a PDF from the frontend.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 0. Connection sanity ────────────────────────────────────────────────────
SELECT current_database(), current_user, inet_server_port();

-- pgvector must be installed. Expect one row, e.g. vector | 0.7.4
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';


-- ── 1. Schema check — did init_db() create the tables? ──────────────────────
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
-- Expect: knowledge_chunks, knowledge_documents

-- Confirm the embedding column is vector(3072), not vector(1536) / bytea.
SELECT a.attname            AS column_name,
       format_type(a.atttypid, a.atttypmod) AS column_type
FROM pg_attribute a
JOIN pg_class t ON t.oid = a.attrelid
WHERE t.relname = 'knowledge_chunks'
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY a.attnum;
-- Expect the row:  embedding | vector(3072)


-- ── 2. THE MAIN ONE — every document + its chunk/embedding counts ───────────
SELECT d.id,
       d.title,
       d.doc_type,
       d.file_name,
       round(d.file_size / 1024.0, 1)      AS file_kb,
       d.folder_path,
       d.metadata ->> 'page_count'         AS pages,
       length(d.content)                   AS content_chars,
       count(c.id)                         AS chunks,
       count(c.embedding)                  AS chunks_embedded,
       count(c.id) - count(c.embedding)    AS chunks_missing_embedding,
       d.created_at
FROM knowledge_documents d
LEFT JOIN knowledge_chunks c ON c.document_id = d.id
GROUP BY d.id
ORDER BY d.created_at DESC;
-- HEALTHY: chunks > 0 AND chunks_embedded = chunks AND missing = 0


-- ── 3. Inspect the chunks of the most recently uploaded document ────────────
-- Never `SELECT embedding` raw — it prints 3072 floats and freezes the grid.
-- This truncates it and shows dims + L2 norm instead.
WITH latest AS (
    SELECT id FROM knowledge_documents ORDER BY created_at DESC LIMIT 1
)
SELECT c.chunk_index,
       length(c.content)                             AS chars,
       left(replace(c.content, E'\n', ' '), 90)      AS content_preview,
       vector_dims(c.embedding)                      AS dims,
       round((c.embedding <-> array_fill(0::real, ARRAY[3072])::vector)::numeric, 4)
                                                     AS l2_norm,
       left(c.embedding::text, 55) || ' … ]'         AS embedding_head,
       c.metadata
FROM knowledge_chunks c
JOIN latest l ON l.id = c.document_id
ORDER BY c.chunk_index;
-- HEALTHY: dims = 3072 on every row, l2_norm ≈ 1.0000, embedding_head shows
--          small signed floats like [-0.0069,0.0188,0.0118, … ]


-- ── 4. Fast red-flag check across the whole table ───────────────────────────
SELECT count(*)                                        AS total_chunks,
       count(*) FILTER (WHERE embedding IS NULL)       AS null_embeddings,
       count(DISTINCT vector_dims(embedding))          AS distinct_dims,
       min(vector_dims(embedding))                     AS min_dims,
       max(vector_dims(embedding))                     AS max_dims
FROM knowledge_chunks;
-- HEALTHY: null_embeddings = 0, distinct_dims = 1, min = max = 3072


-- ── 5. Semantic self-test — do the vectors actually mean anything? ──────────
-- Uses chunk 0 of the newest doc as the probe. Row 1 must be chunk 0 itself
-- at similarity 1.0; neighbouring chunks should score noticeably higher than
-- unrelated ones. If everything scores ~identically, embeddings are garbage.
WITH probe AS (
    SELECT c.embedding
    FROM knowledge_chunks c
    JOIN (SELECT id FROM knowledge_documents ORDER BY created_at DESC LIMIT 1) l
      ON l.id = c.document_id
    WHERE c.chunk_index = 0
)
SELECT c.chunk_index,
       d.title,
       left(replace(c.content, E'\n', ' '), 70)                    AS content_preview,
       round((1 - (c.embedding <=> p.embedding))::numeric, 4)      AS cosine_similarity
FROM knowledge_chunks c
JOIN knowledge_documents d ON d.id = c.document_id
CROSS JOIN probe p
ORDER BY c.embedding <=> p.embedding
LIMIT 10;


-- ── 6. Reset between test uploads (chunks cascade automatically) ────────────
-- DELETE FROM knowledge_documents WHERE id = '<paste-uuid-here>';
-- TRUNCATE knowledge_documents CASCADE;   -- nukes everything
