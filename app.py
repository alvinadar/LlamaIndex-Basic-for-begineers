import asyncio#Non Blocking IO, allows the program to handle multiple tasks concurrently.
#Standard library for asynchronous programming in Python. It provides an event loop, coroutines, and tasks to manage asynchronous operations.


from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

Settings.llm = GoogleGenAI(model="gemini-2.5-flash")
Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001")

documents = SimpleDirectoryReader(input_files=["OPS_MANUAL_logistics_SOP.md"]).load_data()
index = VectorStoreIndex.from_documents(documents)

#Wraps the index as a question-answering-object that can be queried with natural language questions.
#1.Embeds the question into a vector representation.
#2.Retrieves the most relevant documents from the index based on the embedded question.
#3.SUFF THOSE CHUNKS INTO A PROMPT AND SENDS IT TO THE LLM FOR ANSWERING.
#4.RETURNS THE GENERATED ANSWER TO THE USER.
query_engine = index.as_query_engine()

#Setting.node_parser is a global splitter , Llamaindex uses when it turns documents into nodes(Inside Ventor Store Index)
from llama_index.core.node_parser import SentenceSplitter
#Chuck_overlap: Repeat the last ~50 units of the previous chunk at the start of the next. Stops a sentence that straddles a cut from disappearing.
Settings.node_parser = SentenceSplitter(chunk_size=500, chunk_overlap=50)
retriever = index.as_retriever(similarity_top_k=3)#embed the question, return the nearest Nodes.

#response = query_engine.query("truck got the wrong sticker thing at the gate")
#for node in response.source_nodes:
#    print(round(node.score,3),node.text[:120])

from llama_index.core.workflow import (
    Workflow, Context, Event, StartEvent, StopEvent, step,
)

#RetrieveEvent ("Search the library"): The helper takes your question and pulls a stack of relevant books from the shelf.
class RetrieveEvent(Event):
    question: str        # the question being searched RIGHT NOW

#GradeEvent ("Check quality"): They skim the pages they found to see if the information actually answers your question or if it is just irrelevant filler.
class GradeEvent(Event):
    chunks: list[str]

#RewriteEvent ("Try again"): If the pages were useless, this signal flashes. It tells the helper: "These sources suck. Rethink how we asked the question and go search again."
class RewriteEvent(Event):
    pass                 # carries nothing. it only means "try again".

#GenerateEvent ("Write the report"): If the pages passed the quality check, this signal flashes. It tells the helper: "We have great info! Go ahead and draft the final answer."
class GenerateEvent(Event):
    chunks: list[str]

#Workflow Execution Path


class SelfCorrectingRAG(Workflow):

    @step
    async def begin(self, ctx: Context, ev: StartEvent)-> RetrieveEvent:
        await ctx.store("original", ev.question)
        await ctx.store("attempts", 0)
        return RetrieveEvent(question=ev.question)

    @step
    async def retrieve(self, ctx: Context, ev: RetrieveEvent) -> GradeEvent:
        attempts = await ctx.store.get("attempts")#Get the number of attempts made so far from the context store.
        await ctx.store.set("attempts", attempts + 1)
        await ctx.store.set("question", ev.question)

        nodes = await retriever.aretrieve(ev.question)
        print(f"Retrieved {len(nodes)} nodes for question: {ev.question}, attempts: {attempts + 1}")
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
        return RetrieveEvent(question=better) 

    @step
    async def grade(
        self, ctx: Context, ev: GradeEvent) -> StopEvent:

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