import asyncio
from dotenv import load_dotenv

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.workflow import (
    Workflow, Context, Event, StartEvent, StopEvent, step,
)
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

load_dotenv()          

Settings.llm = GoogleGenAI(model="gemini-2.5-flash")
Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001")
Settings.node_parser = SentenceSplitter(chunk_size=500, chunk_overlap=50)

documents = SimpleDirectoryReader(input_files=["OPS_MANUAL.md"]).load_data()
index = VectorStoreIndex.from_documents(documents)   # chunk + embed + store
retriever = index.as_retriever(similarity_top_k=3)

print(f"Indexed {len(documents)} document(s)")


class RetrieveEvent(Event):
    question: str            # the question being searched RIGHT NOW

class GradeEvent(Event):
    chunks: list[str]

class RewriteEvent(Event):
    pass                     # carries nothing. it only means "try again".

class GenerateEvent(Event):
    chunks: list[str]


# ----------------------------------------------------------------------
# STEPS - each is an async method. One job each.
# ----------------------------------------------------------------------

class SelfCorrectingRAG(Workflow):

    @step
    async def begin(self, ctx: Context, ev: StartEvent) -> RetrieveEvent:
        """Put the things that must survive the loop into the Context."""
        await ctx.store.set("original", ev.question)   # never changes
        await ctx.store.set("attempts", 0)             # the loop guard
        return RetrieveEvent(question=ev.question)

    @step
    async def retrieve(self, ctx: Context, ev: RetrieveEvent) -> GradeEvent:
        attempts = await ctx.store.get("attempts")
        await ctx.store.set("attempts", attempts + 1)
        await ctx.store.set("question", ev.question)

        nodes = await retriever.aretrieve(ev.question)
        print(f"  [retrieve] attempt {attempts + 1} -> {len(nodes)} nodes")
        return GradeEvent(chunks=[n.text for n in nodes])

    @step
    async def grade(
        self, ctx: Context, ev: GradeEvent
    ) -> GenerateEvent | RewriteEvent | StopEvent:
        """One yes/no call decides which of three roads we take.
        The union return type IS the fork. There is no router function."""
        original = await ctx.store.get("original")
        context_text = "\n\n".join(ev.chunks)

        verdict = str(await Settings.llm.acomplete(
            f"""EXTRACTS:
{context_text}

QUESTION: {original}

Can the question be answered using ONLY these extracts?
Reply with one word: YES or NO."""
        )).strip().upper()

        print(f"  [grade] relevant = {verdict.startswith('YES')}")

        if verdict.startswith("YES"):
            return GenerateEvent(chunks=ev.chunks)

        attempts = await ctx.store.get("attempts")
        if attempts >= 3:                              # the ceiling
            return StopEvent(result=(
                "Not in the operations manual - escalate to the duty supervisor. "
                f"(Searched {attempts} times.)"
            ))

        return RewriteEvent()

    @step
    async def rewrite(self, ctx: Context, ev: RewriteEvent) -> RetrieveEvent:
        """Bad chunks usually mean a badly worded search, not a missing document."""
        original = await ctx.store.get("original")
        last = await ctx.store.get("question")

        better = str(await Settings.llm.acomplete(
            f"""The search below returned nothing useful from an operations manual.

ORIGINAL QUESTION: {original}
LAST SEARCH USED: {last}

Rewrite it using the vocabulary a formal SOP document would use.
Return only the rewritten question."""
        )).strip()

        print(f"  [rewrite] -> {better}")
        return RetrieveEvent(question=better)          # <-- the loop

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


async def ask(question: str) -> str:
    workflow = SelfCorrectingRAG(timeout=120, verbose=False)
    print(f"\nQ: {question}")
    answer = await workflow.run(question=question)
    print(f"A: {answer}\n")
    return answer


async def main():
    await ask("Seal number doesn't match the ASN. What do I do?")   # 1 lap
    await ask("truck got the wrong sticker thing at the gate")      # rewrites, then answers
    await ask("What is the annual leave policy?")                   # gives up honestly


if __name__ == "__main__":


    asyncio.run(main())
