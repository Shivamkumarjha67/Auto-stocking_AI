# AutoStock-AI: Master Demo Recording Guide

A compelling **45–75 second screen recording or GIF** is the single highest-converting asset for your portfolio. Hiring managers, AI leads, and recruiters rarely clone repositories locally, but **100% of them will watch a high-energy, well-narrated product walkthrough**.

---

## 1. Pre-Recording Preparation Checklist

Follow these steps before hitting "Record" to ensure everything runs smoothly on the first take:

### 1.1 Reset Database to Fresh Seed State
Run this command in your PowerShell terminal to reset the warehouse database to a clean slate (clears previous tickets and pending reviews, and sets up low-stock and HITL demo items):
```powershell
& ".\.venv\Scripts\python.exe" scripts/reset_db.py
```

### 1.2 Start Services in Separate Terminals
1. **Terminal 1 (FastAPI Backend)**:
   ```powershell
   & ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
   ```
2. **Terminal 2 (Streamlit Frontend)**:
   ```powershell
   & ".\.venv\Scripts\python.exe" -m streamlit run ui/app.py
   ```

### 1.3 Browser Setup
- Open Chrome or Edge at `http://localhost:8501`.
- **Zoom to 110% or 125%** (`Ctrl` + `+`): This makes metrics, text, and JSON badges crisp and legible on mobile screens and LinkedIn feeds.
- Close extraneous browser tabs and bookmarks bar (`Ctrl` + `Shift` + `B`) to keep the frame clean.

---

## 2. Recommended Recording Tools (Windows Setup)

You have four great options depending on your preference:

### Option A: Windows 11 Snipping Tool (Zero-Install, Quickest)
* **Best for**: Instant, clean MP4 recording without installing any software.
* **How to use**:
  1. Press `Win + Shift + R`.
  2. Drag a rectangle around the Streamlit browser window (or full screen).
  3. Ensure the microphone toggle is switched **ON** if speaking.
  4. Click **Start** (3-second countdown).
  5. Perform the walkthrough, then click **Stop** on the top bar.
  6. Click **Save** (`Ctrl + S`) as an `.mp4` file.

### Option B: Loom (Best for Recruiter Polish & Shareable Link)
* **Best for**: Instant cloud hosting, link sharing, and optional face-cam bubble.
* **How to use**:
  1. Install the [Loom Chrome Extension](https://www.loom.com/) or Desktop app.
  2. Select **Screen Only** (or **Screen + Cam** for added personality).
  3. Select your microphone and set resolution to **1080p HD**.
  4. Hit record. Loom gives you an instant shareable link with auto-transcriptions, plus a direct MP4 download.

### Option C: OBS Studio (Best for Studio-Grade 1080p/60fps)
* **Best for**: Complete control, no watermarks, professional audio filtering.
* **How to use**:
  1. Download [OBS Studio](https://obsproject.com/).
  2. Under **Sources**, click `+` ➔ **Window Capture** ➔ Select `chrome.exe` / `AutoStock-AI`.
  3. Set Output to **1920x1080, 30 or 60 fps, MP4 format**.
  4. Click **Start Recording**, perform the demo, and click **Stop Recording**. The video is saved directly to your `Videos` folder.

### Option D: ScreenToGif (Best for Direct README Embedding)
* **Best for**: Creating an animated `.gif` to embed directly at the top of your GitHub `README.md`.
* **How to use**:
  1. Download [ScreenToGif](https://www.screentogif.com/) (portable, single `.exe`).
  2. Position the recording frame over the browser window.
  3. Record at **15–20 fps** (to keep file size under 10MB for GitHub).
  4. Save as `.gif` and place in `screenshots/demo.gif`.

---

## 3. Storyboard & Word-for-Word Voiceover Script (~60 Seconds)

Here is a timed script designed to demonstrate maximum technical depth in 60 seconds:

```
[0:00 - 0:15] Tab 1: Live Stock Surveillance & Mathematical Runway
      │
[0:15 - 0:28] Tab 2: Hybrid RAG & Contract Ingestion
      │
[0:28 - 0:48] Tab 3: Autonomous Agent Execution, LLM Sizing & HITL Review
      │
[0:48 - 1:00] Tab 1: ERP Commit, Replenished Stock & Summary
```

### Scene 1: Live Inventory Surveillance (0:00 – 0:15)
* **Visual**: Streamlit Tab 1 (`📋 Inventory Hub`).
* **Mouse action**: Hover over `SKU-1003` with the red **Critical** badge.
* **Voiceover**:
  > *"Hi everyone! This is AutoStock-AI, an autonomous agentic procurement system. In Tab 1, we monitor live warehouse stock. Notice SKU-1003, a Lithium-Ion Battery Pack with only 18 units in stock and a daily sales velocity of 10 units. The system automatically computes runway at 1.8 days, flagging it as Critical."*

### Scene 2: Hybrid RAG Knowledge Base (0:15 – 0:28)
* **Visual**: Click to Tab 2 (`📚 Knowledge Base`).
* **Mouse action**: Point at the indexed contracts table.
* **Voiceover**:
  > *"To solve this, the agent doesn't guess prices—it references our Hybrid RAG knowledge base. We ingest supplier contracts, SLAs, and corporate procurement policies, indexing them into ChromaDB and BM25 using Reciprocal Rank Fusion to guarantee exact SKU recall."*

### Scene 3: Agent Execution & Human-in-the-Loop Review (0:28 – 0:48)
* **Visual**: Click to Tab 3 (`🤖 Agent Console & HITL`).
* **Mouse action**: Click **🚀 Trigger Autonomous Replenishment**.
* **Handling the ~10s processing time**:
  > *(While the spinner runs, narrate the architecture):*  
  > *"When I trigger replenishment, a 4-node LangGraph state machine kicks off. It queries the database, retrieves the supplier SLA, and runs our fine-tuned model to size the order to restore our 14-day safety buffer."*
* **When the card appears**:
  > *"The agent selected TechCorp—VEND-001—because for Critical items, it overrides price to secure their fast 3-to-5 day lead time. Notice our live telemetry: 420 prompt tokens, latency logged, and cost under one cent."*
* **Scroll down to HITL Gate**:
  > *"Because this total breached our $5,000 threshold or requires sign-off, our Human-in-the-Loop policy gate halted autonomous execution. I'll enter 'Approved express restocking' and click Approve."*

### Scene 4: ERP Fulfillment & Stock Replenishment (0:48 – 1:00)
* **Visual**: Switch back to Tab 1 (`📋 Inventory Hub`). Click **🔄 Refresh Live Inventory**.
* **Mouse action**: Highlight `SKU-1003` updated to a healthy stock level.
* **Voiceover**:
  > *"Returning to the inventory hub and hitting refresh, the purchase order has committed to the ERP database, warehouse stock is replenished, and status updates to Healthy. That is end-to-end autonomous procurement with enterprise policy guardrails. Thank you!"*

---

## 4. Pro-Tips for Maximum Impact

1. **Turn Latency Into a Feature**:
   Because LLM inference + 2 RAG retrieval passes take 10–12 seconds, do not leave dead silence! Use those seconds to explain the LangGraph cycle or mention: *"It's actively cross-referencing MOQs and checking internal procurement spending limits."*
2. **Terminal Split-Screen (Bonus Signal)**:
   If using OBS or recording full screen, you can have your terminal visible on one side showing the structured FastAPI logs:
   ```text
   INFO: autostock.api: Replenishment evaluated for SKU-1003: Vendor=VEND-001, Qty=122, ExecutionTime=1350ms, EstCost=$0.00014
   ```
   This signals that you understand production backend logging.
3. **Keep Mouse Movements Deliberate**:
   Avoid rapid, erratic cursor movements. Move smoothly to the element you are discussing.
4. **Export Format**:
   - For **LinkedIn / Portfolio sites**: Upload the raw 1080p `.mp4` directly (LinkedIn auto-plays video in feed).
   - For **GitHub README**: Convert the first 30 seconds into an optimized `.gif` (under 10MB) using ScreenToGif or [ezgif.com](https://ezgif.com/video-to-gif) and embed it at the top of your `README.md`.
