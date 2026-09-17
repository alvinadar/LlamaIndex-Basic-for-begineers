"""
rag_workflow_local.py - Self-correcting RAG on a LOCAL model
CodeRangers - no API key, no rate limits, no internet after setup

Setup (once):
    ollama pull llama3.2
    ollama pull nomic-embed-text
    pip install llama-index-llms-ollama llama-index-embeddings-ollama

Run:  python rag_workflow_local.py
"""

import asyncio

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.workflow import (
    Workflow, Context, Event, StartEvent, StopEvent, step,
)

# ----------------------------------------------------------------------
# THE ONLY LINES THAT CHANGED. Everything below this block is identical
# to the cloud version.
# ----------------------------------------------------------------------

from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(
    model="llama3.2",          # use "llama3.2:1b" if your laptop struggles
    request_timeout=180.0,     # local models are slow. be patient in code too.
    temperature=0,             # the grader must be predictable, not creative
)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")

# For reference, this is what you replaced:
#   Settings.llm = GoogleGenAI(model="gemini-2.5-flash")
#   Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001")
# NOTE: different embedding model = different map. The index below is built
# fresh every run, so restarting IS the re-index. Never mix the two.

Settings.node_parser = SentenceSplitter(chunk_size=500, chunk_overlap=50)

documents = SimpleDirectoryReader(input_files=["OPS_MANUAL.md"]).load_data()
index = VectorStoreIndex.from_documents(documents)
retriever = index.as_retriever(similarity_top_k=3)


# ----------------------------------------------------------------------
# DIAGNOSTIC - run this BEFORE blaming the model.
# If the answer is not in the retrieved text, nothing downstream can help.
# ----------------------------------------------------------------------

def inspect(question: str) -> None:
    nodes = retriever.retrieve(question)
    print(f"\n--- retrieval check: {question!r}")
    print(f"    asked for 3 nodes, got {len(nodes)}")
    for n in nodes:
        print(f"    {n.score:.3f} | {n.text[:180].replace(chr(10), ' ')}")
    print("--- if the answer is not in that text, fix the MANUAL, not the code.\n")


# ----------------------------------------------------------------------
# EVENTS - unchanged
# ----------------------------------------------------------------------

class RetrieveEvent(Event):
    question: str

class GradeEvent(Event):
    chunks: list[str]

class RewriteEvent(Event):
    pass

class GenerateEvent(Event):
    chunks: list[str]


# ----------------------------------------------------------------------
# STEPS - unchanged, EXCEPT the grader now parses defensively.
# ----------------------------------------------------------------------

class SelfCorrectingRAG(Workflow):

    @step
    async def begin(self, ctx: Context, ev: StartEvent) -> RetrieveEvent:
        await ctx.store.set("original", ev.question)
        await ctx.store.set("attempts", 0)
        return RetrieveEvent(question=ev.question)

    @step
    async def retrieve(self, ctx: Context, ev: RetrieveEvent) -> GradeEvent:
        attempts = await ctx.store.get("attempts")
        await ctx.store.set("attempts", attempts + 1)
        await ctx.store.set("question", ev.question)

        nodes = await retriever.aretrieve(ev.question)
        top = f"{nodes[0].score:.3f}" if nodes else "none"
        print(f"  [retrieve] attempt {attempts + 1} -> {len(nodes)} nodes, top score {top}")
        return GradeEvent(chunks=[n.text for n in nodes])

    @step
    async def grade(
        self, ctx: Context, ev: GradeEvent
    ) -> GenerateEvent | RewriteEvent | StopEvent:
        original = await ctx.store.get("original")
        context_text = "\n\n".join(ev.chunks)

        raw = str(await Settings.llm.acomplete(
            f"""You are checking whether some manual extracts can answer a question.

EXTRACTS:
{context_text}

QUESTION: {original}

Can this question be answered using ONLY the extracts above?
Answer with a single word: YES or NO. Do not explain."""
        )).strip().upper()

        # A small local model will say "BASED ON THE EXTRACTS, YES..." instead
        # of "YES". Never trust a format instruction. Parse defensively.
        relevant = "YES" in raw[:40]

        print(f"  [grade] model said {raw[:40]!r} -> relevant = {relevant}")

        if relevant:
            return GenerateEvent(chunks=ev.chunks)

        attempts = await ctx.store.get("attempts")
        if attempts >= 3:
            return StopEvent(result=(
                "Not in the operations manual - escalate to the duty supervisor. "
                f"(Searched {attempts} times.)"
            ))

        return RewriteEvent()

    @step
    async def rewrite(self, ctx: Context, ev: RewriteEvent) -> RetrieveEvent:
        original = await ctx.store.get("original")
        last = await ctx.store.get("question")

        better = str(await Settings.llm.acomplete(
            f"""The search below returned nothing useful from an operations manual.

ORIGINAL QUESTION: {original}
LAST SEARCH USED: {last}

Rewrite it as a short search phrase using the vocabulary a formal SOP
document would use. Return only the phrase, under 15 words."""
        )).strip().strip('"')

        print(f"  [rewrite] -> {better}")
        return RetrieveEvent(question=better)

    @step
    async def generate(self, ctx: Context, ev: GenerateEvent) -> StopEvent:
        original = await ctx.store.get("original")
        context_text = "\n\n".join(ev.chunks)

        answer = await Settings.llm.acomplete(
            f"""You are an operations assistant for a warehouse team.

Answer using ONLY the manual extracts below. Be brief.

MANUAL EXTRACTS:
{context_text}

QUESTION: {original}"""
        )
        return StopEvent(result=str(answer).strip())


# ----------------------------------------------------------------------
# RUN
# ----------------------------------------------------------------------

async def ask(question: str) -> str:
    workflow = SelfCorrectingRAG(timeout=600, verbose=False)
    print(f"\nQ: {question}")
    answer = await workflow.run(question=question)
    print(f"A: {answer}\n")
    return answer


async def main():
    await ask("Seal number doesn't match the ASN. What do I do?")
    await ask("truck got the wrong sticker thing at the gate")
    await ask("What is the annual leave policy?")


if __name__ == "__main__":
    # Look at what the retriever actually found before running the workflow.
    inspect("Seal number doesn't match the ASN. What do I do?")

    asyncio.run(main())