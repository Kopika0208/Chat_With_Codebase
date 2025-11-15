import os
import re
import traceback
import streamlit as st
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client

from ingest import ingest_repo, VECTOR_DIR

# ===============================
# ⚙️ SETUP
# ===============================
load_dotenv()
st.set_page_config(page_title="Chat with Your Codebase", layout="wide")
st.title("💬 Chat with Your Codebase – Tree-sitter + Multi-Stage Retrieval")

LANGCHAIN_PROJECT = "chat-with-codebase"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

try:
    client = Client()
    print(f"✅ LangSmith connected: {client.api_url}")
except Exception:
    print("⚠️ LangSmith inactive")

EMBED_MODEL = "thenlper/gte-base"
DEFAULT_REPO_PATH = "repos/myrepo"

# ======================================================
# 📥 REPO INGESTION
# ======================================================
st.subheader("📦 Ingest a New Repository")

repo_url = st.text_input("🔗 Enter GitHub Repository URL or Local Path")

if st.button("🚀 Start Ingestion"):
    if not repo_url.strip():
        st.warning("⚠️ Please enter a repository URL or folder path.")
    else:
        try:
            with st.status("⚙️ Ingestion Pipeline Running...", expanded=True) as status:
                status.write("📥 Step 1: Cloning or opening repository...")
                status.write("🧩 Step 2: Parsing with Tree-sitter / AST / Regex...")
                status.write("🧠 Step 3: Embedding & building FAISS index...")
                ingest_repo(repo_url.strip())
                status.update(label="✅ Repository indexed successfully!", state="complete")
            st.success("🎉 Ingestion complete!")
        except Exception as e:
            st.error(f"❌ Error during ingestion: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())

# ======================================================
# 📂 LOAD VECTORSTORE
# ======================================================
if not os.path.exists(VECTOR_DIR):
    st.warning("⚠️ Please ingest a repository first.")
    st.stop()

embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
vectorstore = FAISS.load_local(VECTOR_DIR, embeddings, allow_dangerous_deserialization=True)
print("✅ FAISS loaded successfully")

# ======================================================
# 🧠 LLM SETUP
# ======================================================
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.2)

prompt = ChatPromptTemplate.from_template("""
You are an expert assistant helping a developer understand a codebase.

You are given code context chunks from a repository and a user question.

<context>
{context}
</context>

Sources (file and line ranges):
{sources}

Question: {input}

Respond with:

- **Summary:** Short, precise technical answer.
- **Explanation:** Step-by-step reasoning in simple language.
- **Where in the code:** Mention the most relevant files and line ranges using the format `path: start_line–end_line`.

If the answer is uncertain, say so clearly and suggest where the developer should look in the code.
""")

# ======================================================
# 🧠 METADATA FILTERING (Implicit)
# ======================================================
def infer_metadata_filters_from_query(query: str):
    q = query.lower()
    filters = {}

    lang_map = {
        "python": "python", "py": "python",
        "javascript": "javascript", "js": "javascript",
        "typescript": "typescript", "ts": "typescript",
        "java": "java",
        "c++": "cpp", "cpp": "cpp",
        "rust": "rust",
        "go": "go",
    }
    for k, v in lang_map.items():
        if k in q:
            filters["language"] = v

    if "function" in q or "def " in q:
        filters["node_type"] = "function_definition"
    if "class" in q:
        filters["node_type"] = "class_definition"

    file_hits = re.findall(r"\w+\.(py|js|ts|java|cpp|c|rs|go)", q)
    if file_hits:
        filters["path"] = {"$contains": file_hits[0]}

    print("🧠 Implicit Filters:", filters if filters else "{}")
    return filters

# ======================================================
# 5️⃣ RETRIEVAL SYSTEM – MULTI-STAGE
#    Stage 1: Vector search
#    Stage 2: Metadata post-filter
#    Stage 3: Optional LLM semantic re-ranking
# ======================================================
def stage1_vector_search(query, k=12):
    """Retriever 1: plain vector search (no filters)."""
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=k)
    docs = [d for d, _ in docs_and_scores]
    print(f"🔎 Stage 1 – Vector search retrieved {len(docs)} chunks")
    return docs

def stage2_metadata_filter(docs, inferred_filters):
    """Retriever 2: metadata filter on Stage 1 results."""
    if not inferred_filters:
        print("⚙️ Stage 2 – No filters inferred; skipping metadata filter.")
        return docs

    filtered = []
    for d in docs:
        m = d.metadata or {}
        ok = True

        if "language" in inferred_filters:
            if (m.get("language") or "").lower() != inferred_filters["language"]:
                ok = False

        if ok and "node_type" in inferred_filters:
            if (m.get("node_type") or "").lower() != inferred_filters["node_type"]:
                ok = False

        if ok and "path" in inferred_filters:
            needle = inferred_filters["path"].get("$contains", "").lower()
            if needle and needle not in (m.get("path") or "").lower():
                ok = False

        if ok:
            filtered.append(d)

    if not filtered:
        print("⚠️ Stage 2 – Metadata filter removed all docs; falling back to Stage 1 docs.")
        return docs

    print(f"✅ Stage 2 – Metadata filter kept {len(filtered)} chunks")
    return filtered

LLM_RERANK_PROMPT = """
You are a code relevance scorer.

User Query:
{query}

Code Snippet:
{snippet}

Rate how relevant this snippet is for answering the query.
Respond ONLY with an integer number from 0 (not relevant) to 10 (perfect match).
"""

def stage3_llm_rerank(query, docs, top_k=4):
    """Retriever 3: LLM-based semantic re-ranking. Token-conscious."""
    scored = []
    for d in docs:
        snippet = d.page_content[:800]  # limit tokens
        msg = LLM_RERANK_PROMPT.format(query=query, snippet=snippet)
        try:
            resp = llm.invoke(msg)
            raw = resp.content.strip()
            score = float(int(re.findall(r"-?\d+", raw)[0]))
        except Exception:
            score = 0.0
        scored.append((d, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_docs = [d for d, _ in scored[:top_k]]
    print("🤖 Stage 3 – LLM rerank scores:", [(d.metadata.get("path"), s) for d, s in scored[:top_k]])
    return top_docs

# ======================================================
# 🧩 CONTEXTUAL EXPANSION (NO DOC MUTATION)
# ======================================================
def get_expanded_context(docs, repo_path=DEFAULT_REPO_PATH, window=20):
    expanded_map = {}

    for doc in docs:
        meta = doc.metadata or {}
        expanded_context = ""
        try:
            file_path = os.path.join(repo_path, meta["path"])
            if not os.path.exists(file_path):
                expanded_map[id(doc)] = ""
                continue

            start, end = meta.get("start_line", 1), meta.get("end_line", 1)
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            context_start = max(0, start - window)
            context_end = min(len(lines), end + window)
            expanded_context = "".join(lines[context_start:context_end])
        except Exception:
            expanded_context = ""

        expanded_map[id(doc)] = expanded_context

    return expanded_map

def build_context_and_sources(docs, expanded_map, max_chars_per_doc=1200):
    """Merge chunks + expanded context and build a sources string."""
    context_parts = []
    source_lines = []

    for i, d in enumerate(docs, start=1):
        m = d.metadata or {}
        path = m.get("path", "unknown")
        start = m.get("start_line", "?")
        end = m.get("end_line", "?")
        header = f"### Source {i}: {path} ({start}–{end})"
        chunk_text = d.page_content or ""
        expanded = expanded_map.get(id(d), "") or ""

        merged = chunk_text + "\n\n# Additional Context\n" + expanded
        merged = merged[:max_chars_per_doc]  # safety trim

        context_parts.append(header + "\n" + merged)
        source_lines.append(f"{i}. {path}: {start}–{end}")

    context_str = "\n\n-----\n\n".join(context_parts)
    sources_str = "\n".join(source_lines) if source_lines else "None"

    return context_str, sources_str

# ======================================================
# 💬 QUERY INTERFACE
# ======================================================
st.divider()
st.subheader("💡 Ask Questions About Your Codebase")

enable_llm_rerank = st.checkbox(
    "🤖 Enable LLM Semantic Re-Ranking (more accurate, uses extra tokens)",
    value=False,
)

query = st.text_input("🔍 Your question (e.g., 'Where is judgment prediction implemented?'):")

if query:
    with st.spinner("🔎 Running multi-stage retrieval over your codebase..."):
        try:
            # 1️⃣ Infer metadata filters
            inferred_filters = infer_metadata_filters_from_query(query)

            # 2️⃣ Stage 1 – vector search
            stage1_docs = stage1_vector_search(query, k=12)

            # 3️⃣ Stage 2 – metadata post-filter
            stage2_docs = stage2_metadata_filter(stage1_docs, inferred_filters)

            # 4️⃣ Stage 3 – optional LLM semantic re-rank
            if enable_llm_rerank:
                final_docs = stage3_llm_rerank(query, stage2_docs, top_k=4)
            else:
                final_docs = stage2_docs[:4]

            if not final_docs:
                st.warning("⚠️ No relevant chunks retrieved from the codebase.")
                st.stop()

            # 5️⃣ Contextual expansion
            expanded_map = get_expanded_context(final_docs, repo_path=DEFAULT_REPO_PATH)

            # 6️⃣ Build final context + sources
            context_str, sources_str = build_context_and_sources(final_docs, expanded_map)

            # 7️⃣ Construct prompt and call LLM
            messages = prompt.format_messages(
                context=context_str,
                sources=sources_str,
                input=query,
            )
            response = llm.invoke(messages)
            answer = response.content

            # 8️⃣ Show AI answer
            st.subheader("🤖 AI Answer")
            st.markdown(answer)

            # 9️⃣ Show top matches (code snippets)
            st.subheader("📂 Top Code Matches")
            for i, d in enumerate(final_docs, start=1):
                m = d.metadata or {}
                st.markdown(f"### 🧩 Match {i}")
                st.markdown(f"- **File:** `{m.get('path')}`")
                st.markdown(f"- **Lines:** {m.get('start_line')}–{m.get('end_line')}")
                st.markdown(f"- **Symbol:** `{m.get('symbol_name')}`")
                st.markdown(f"- **Parser:** `{m.get('parser_used')}`")
                st.code(d.page_content, language=m.get("language") or "python")

        except Exception as e:
            st.error(f"❌ Error while answering: {type(e).__name__}: {e}")
            st.text(traceback.format_exc())
