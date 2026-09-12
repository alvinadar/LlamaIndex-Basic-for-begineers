# Running Your RAG on a Local Model

**CodeRangers · student handout**
**Why you are reading this:** your script stopped with a red wall of text ending in `429 RESOURCE_EXHAUSTED`.

---

## Part 1 — What actually went wrong

Read the important line of the error, not the 90 lines above it:

```
429 RESOURCE_EXHAUSTED
Quota exceeded for metric: generate_content_free_tier_requests,
limit: 5, model: gemini-2.5-flash
Please retry in 16.5s
```

**Limit: 5.** Five requests per minute, on the free tier.

Now count what our workflow spends on one question:

| Step | Calls the LLM? |
|---|---|
| retrieve | No |
| grade | **Yes** |
| rewrite | **Yes** (only when it loops) |
| generate | **Yes** |

One clean question = 2 calls. One question that loops three times = **7 calls**. Ask three questions in a row and you are at 15 calls in under a minute. The free tier allows 5.

> **This is not a bug in your code.** Your code is working exactly as designed. It is a design that costs more calls than a free key allows — which is a completely normal thing to discover, and the reason this handout exists.

**And in a classroom of 20 people, it gets worse.** Cloud keys have limits per project, per model, per minute. Twenty students hitting the same API in the same ten minutes is the single most reliable way to fail a workshop.

## Part 2 — The fix: run the model on your own laptop

Instead of sending your question to Google, you run a smaller model **on your own machine**.

| | Cloud (Gemini) | Local (Ollama) |
|---|---|---|
| Rate limits | 5/min on free tier | **None. Ever.** |
| Cost | Per token | **RM 0.00** |
| Internet | Required | Only for the first download |
| Your documents | Leave your laptop | **Never leave your laptop** |
| Speed | Fast | Slower — seconds per answer |
| Answer quality | Better | Good enough to learn on |

That last row is honest: a 3-billion-parameter model on a MacBook Air is not Gemini. But **you are learning how workflows work, not shipping a product this afternoon** — and a slightly worse answer that always arrives beats a great answer that returns 429.

The privacy row is the one that matters for real work. A factory's SOPs, a bank's policy manual, a hospital's protocol — many of these are simply not allowed to be sent to an API. Local models are not a beginner's compromise; for some clients they are the only option.

---

## Part 3 — Install Ollama

> **If you already typed `ollama pull llama3.2` and got `zsh: command not found: ollama` — that is this section. The command does not exist yet because Ollama is not installed. Start at Step 1.**

### Understand what you are installing

Ollama is **two things in one download**, and knowing that makes every error message readable:

| Piece | What it is | How you notice it |
|---|---|---|
| **The server** | A background program holding models in memory and answering requests on `http://localhost:11434` | Your Python code talks to this |
| **The CLI** | The `ollama` command in your terminal | You type this to pull and test models |

`command not found` means **the CLI is missing**. `connection refused` means **the server is not running**. Two different problems, two different fixes.

### Step 1 — Install it

Find your operating system below. **Install one way only** — mixing two installs is how you end up with two copies and a version that will not update.

---

#### macOS

Pick **one** of these. If you already have Homebrew — and you do, your Python came from `/opt/homebrew` — option A is the cleanest.

**Option A — Homebrew (recommended):**

```bash
brew install --cask ollama-app
```

Note the name: **`ollama-app`**, with the hyphen. The old `ollama` cask name was retired, so `brew install ollama` may give you something unexpected or nothing at all. This installs the app to `/Applications` and links the command into `/opt/homebrew/bin/ollama`, which is already on your PATH.

**Option B — one-line installer:**

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Installs both the command-line tool and the desktop app.

**Option C — download it by hand:**

Go to **ollama.com/download**, get the macOS `.zip` or `.dmg`, and drag **Ollama.app** into Applications. Then **open the app once.** This matters: the app installs the terminal command on first launch, and shows a dialog asking for your password to do it. **If you skipped that dialog, you have the app but no `ollama` command** — which is the single most common cause of the error you hit.

---

#### Windows

You need **Windows 10 or 11**, about **4 GB free** for the program, and more for the models themselves. No administrator rights required — Ollama installs into your own user account.

**Option A — winget (recommended).** Open **PowerShell** from the Start menu and run:

```powershell
winget install --id Ollama.Ollama
```

`winget` is Windows' built-in package manager, already present on Windows 11 and recent Windows 10. If it says the command is unrecognised, use Option B.

**Option B — the installer.** Go to **ollama.com/download**, choose Windows, and run **OllamaSetup.exe**. Click through it; there are no choices to make.

Either way you get three things: the program in `%LOCALAPPDATA%\Programs\Ollama`, a llama icon in your **system tray** (bottom-right, sometimes hidden under the `^` arrow) which is the server running in the background, and the folder added to your **user PATH** so `ollama` works in any terminal.

**Then close every terminal you have open and open a brand new one.** Not a new tab — a new window. A terminal reads PATH once when it starts, so any window opened before the install will insist the command does not exist, no matter how many times you retry. This catches almost every Windows student.

> **Which terminal?** PowerShell or Command Prompt both work fine. If you use VS Code's built-in terminal, **restart VS Code completely** after installing, for the same PATH reason.

> **Short on C: drive space?** Models are several GB each and land in `C:\Users\<you>\.ollama` by default. To put them elsewhere, search the Start menu for *environment variables*, and add a user variable **`OLLAMA_MODELS`** set to something like `D:\ollama-models`. Do this **before** pulling any models.

> **Not WSL.** If you have WSL installed, do not install Ollama inside it for this workshop. The Windows version runs natively and uses your GPU; the WSL route adds a networking problem you do not need today.

---

#### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Installs the CLI and sets up the background service.

### Step 2 — Prove the command exists

Open a **new terminal window** — an old one still has the old PATH and will keep telling you the command is missing even after a successful install.

```bash
ollama --version
```

A version number means the CLI is installed. Now check the server is up.

**macOS / Linux:**

```bash
curl http://localhost:11434
```

**Windows:** open **http://localhost:11434** in your browser instead. (In PowerShell, `curl` is an alias for something else and gives confusing output — use `curl.exe http://localhost:11434` if you want the terminal version.)

Either way you should see a short "Ollama is running". If nothing answers: on macOS open the Ollama app from Applications, on Windows launch Ollama from the Start menu — or on any system, run `ollama serve` in a spare terminal and leave that window open.

### Still `command not found`? Work down this list

**macOS:**

| Check | Command | If it fails |
|---|---|---|
| Is it installed at all? | `ls /Applications/Ollama.app` | Go back to Step 1 |
| Where is the command? | `which -a ollama` | Nothing printed = CLI never linked |
| Did you open a new terminal? | — | Close it, open a fresh one |
| Is the folder even there? | `ls /usr/local/bin` | `sudo mkdir -p /usr/local/bin`, then reopen the app |
| Homebrew path on PATH? | `echo $PATH \| grep homebrew` | Add `/opt/homebrew/bin` to your `~/.zshrc` |

That fourth row is a real and genuinely confusing bug: on a clean Mac `/usr/local/bin` sometimes does not exist, so the app tries to install the command into a folder that is not there, fails quietly, and asks you for your password again on every launch. Create the folder and relaunch.

**Windows** — the error reads `'ollama' is not recognized as an internal or external command`:

| Check | Command (PowerShell) | If it fails |
|---|---|---|
| Is it installed at all? | `dir $env:LOCALAPPDATA\Programs\Ollama` | Not found = go back to Step 1 |
| Where is the command? | `where.exe ollama` | Nothing printed = PATH problem, see below |
| Brand new window? | — | Close **every** terminal, open one fresh. Restart VS Code too |
| Is it on PATH? | `$env:PATH -split ';' \| Select-String Ollama` | Nothing = add it, see below |
| Is the server running? | look in the system tray | No llama icon = launch Ollama from the Start menu |

**To add it to PATH by hand:** search the Start menu for *environment variables* → **Environment Variables** → under **User variables** select **Path** → **Edit** → **New** → paste `%LOCALAPPDATA%\Programs\Ollama` → OK all the way out → **open a new terminal**.

> **The one rule that fixes most Windows cases:** a terminal reads PATH when it opens and never again. After any install or PATH change, the old window is lying to you. Open a new one before you believe the error.

> **Being inside your `py312` virtual environment is irrelevant here.** `ollama` is a system program, not a Python package. `pip install ollama` will **not** give you the command — that is a different thing entirely, and installing it will make your confusion worse, not better.

### Step 3 — Download two models

Yes, two — the same split you already know from RAG.

```bash
ollama pull llama3.2          # the chat model  (~2 GB)
ollama pull nomic-embed-text  # the embedding model (~274 MB)
```

**Why two?** Because RAG needs two different jobs done:

- **`nomic-embed-text`** turns text into coordinates. Used once per chunk when you build the index, and once per question. It is tiny and fast because it does not write anything — it only measures meaning.
- **`llama3.2`** writes the sentences. Used by grade, rewrite and generate.

This is the same pair you had with Gemini (`gemini-embedding-001` and `gemini-2.5-flash`). Nothing about the architecture changed. Only where the models live.

### Step 4 — Test it before touching your code

```bash
ollama run llama3.2 "Say hello in one sentence."
```

If you get a sentence back, you are done installing. Type `/bye` to exit. **Never debug your Python until this command works** — if the terminal cannot talk to the model, your script has no chance, and you will waste an hour reading the wrong traceback.

> **Laptop too slow or low on disk?** Use `ollama pull llama3.2:1b` instead — about 1.3 GB, noticeably dumber, but it runs comfortably on 8 GB of RAM. Change the model name in your code to match.

## Part 4 — Change your code

Install the two LlamaIndex adapters:

```bash
pip install llama-index-llms-ollama llama-index-embeddings-ollama
```

Now change **four lines** in your script. Everything else — every event, every step, the loop, the guard — stays exactly as it is.

**Before:**

```python
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

Settings.llm = GoogleGenAI(model="gemini-2.5-flash")
Settings.embed_model = GoogleGenAIEmbedding(model_name="gemini-embedding-001")
```

**After:**

```python
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

Settings.llm = Ollama(model="llama3.2", request_timeout=180.0, temperature=0)
Settings.embed_model = OllamaEmbedding(model_name="nomic-embed-text")
```

**That is the whole migration.** Delete `load_dotenv()` and your API key if you like — a local model has no key to leak.

> ### Why this is the good news
> `Settings.llm` is a **slot**. LlamaIndex does not care what you put in it, as long as it can answer `.acomplete()`. Gemini, Ollama, OpenAI, Claude, a model running on a server in your office — same slot, same four lines. **You just learned how to change model providers in every LlamaIndex project you will ever write.**

### Two settings worth understanding

- **`request_timeout=180.0`** — a local model on a laptop can take 30+ seconds for a long answer. The default timeout is short and you will get a confusing connection error instead of a slow answer. Set it generously.
- **`temperature=0`** — makes the model as predictable as it can be. Your grader is supposed to answer YES or NO. You do not want creativity there.

## Part 5 — Re-index. Not optional.

You changed the embedding model, so **every coordinate in your index is from a different map.**

`gemini-embedding-001` and `nomic-embed-text` produce vectors of different lengths that mean different things. Mixing them makes similarity scores meaningless — and it usually does not crash, it just quietly returns nonsense.

Our script builds the index in memory on every run, so **restarting is enough**. If you ever save an index to disk, delete the folder and rebuild it after a model change.

> **Remember this rule:** *change the embedding model → throw away the index.* No exceptions. You will meet this again in every RAG project you ever build.

## Part 6 — When it goes wrong

| What you see | What it means | What to do |
|---|---|---|
| `Connection refused` on port 11434 | Ollama is not running | Open the Ollama app, or run `ollama serve` |
| `'ollama' is not recognized` (Windows) | PATH not picked up yet | Close every terminal, open a new one. See Part 3 |
| Windows Firewall popup on first run | Ollama opening its local port | Allow it on **private** networks only |
| `model "llama3.2" not found` | You never pulled it | `ollama pull llama3.2`, check spelling with `ollama list` |
| Timeout after ~30 seconds | Your laptop is thinking, not broken | Raise `request_timeout`, or use `llama3.2:1b` |
| Laptop fan screaming, everything slow | The model is in RAM and working | Close Chrome tabs. Seriously. |
| Grader says NO to everything | Small models ramble instead of answering YES/NO | See below |
| First question very slow, rest fast | Model loading into memory | Normal. It stays warm for 5 minutes. |

### The grader problem — read this one carefully

Your grader asks for one word. Gemini obeys. A 3B model often replies:

> "Based on the extracts provided, YES, the question can be answered..."

Your check is `verdict.startswith("YES")`, and that string does not start with YES. **So the grader says NO to everything, your workflow rewrites forever, and you blame the model.**

Make the check forgiving instead of exact:

```python
verdict = str(await Settings.llm.acomplete(prompt)).strip().upper()
relevant = "YES" in verdict[:40]        # look in the first 40 characters
```

> **The real lesson, and it is bigger than Ollama:** never assume a model will obey a formatting instruction. **Parse defensively.** A prompt is a request, not a contract — and the smaller the model, the more true that gets.

## Part 7 — Before you blame anything, check the manual

One more habit, because it would have saved you an hour today. If the grader keeps saying NO, prove the answer is even in there:

```python
nodes = retriever.retrieve("Seal number doesn't match the ASN. What do I do?")
print(f"Got {len(nodes)} nodes")
for n in nodes:
    print(round(n.score, 3), "|", n.text[:200].replace("\n", " "))
```

Three things this tells you instantly:

1. **How many nodes came back.** If you asked for `similarity_top_k=3` and got 2, your whole manual is only 2 chunks — it is far too short, and no amount of rewriting will help.
2. **The scores.** Below about 0.4 means nothing relevant was found.
3. **The actual text.** Read it. Does it contain the answer? If not, the problem is your document, not your model, not your prompt, and not your framework.

**Fix the document before you tune anything else.** A RAG system cannot retrieve what you did not give it.

---

## Your checklist

- [ ] `ollama --version` prints a version (the CLI exists)
- [ ] `curl http://localhost:11434` answers (the server is running)
- [ ] `ollama run llama3.2 "hello"` works in the terminal
- [ ] Both models pulled — chat **and** embedding
- [ ] Four lines swapped, everything else untouched
- [ ] Script restarted so the index rebuilt with the new embeddings
- [ ] Grader check widened to `"YES" in verdict[:40]`
- [ ] Retrieved nodes printed at least once, and you read them

## The three things to take away

1. **`429` is an architecture message, not a bug.** Count your LLM calls per question — you now know a loop multiplies them.
2. **The model is a slot.** Swapping providers is four lines, because LlamaIndex only cares that something can answer `.acomplete()`.
3. **Change the embedding model, throw away the index.** Different map, meaningless coordinates.
