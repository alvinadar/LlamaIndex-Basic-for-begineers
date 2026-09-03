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

response = query_engine.query("truck got the wrong sticker thing at the gate")
for node in response.source_nodes:
    print(round(node.score,3),node.text[:120])

