# Smart Sequencing for Conveyor & Buffer Management 🚗🎨⚙️

![Streamlit](https://img.shields.io/badge/Streamlit-app-red)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Status](https://img.shields.io/badge/Status-Prototype-green)
![License](https://img.shields.io/badge/License-MIT-black)

**Goal:** Design and demo an algorithm that sequences jobs across multiple conveyor lines with intermediate buffers to **maximize throughput**, **avoid buffer overflows**, **minimize make-span**, and **respect priorities / changeover costs**.
Deliverables include a runnable prototype, a short report (auto-generated PDF), and an interactive dashboard.

---

## 🎯 Problem Context

* A **common buffer** feeds two ovens: **O1** (4 buffers: L1–L4) and **O2** (5 buffers: L5–L9).
* **O1 can send** to **all 9** buffer lines.
* If **O1 uses L5–L9**, the **O2 exit must stop**, reducing line speed and hurting **JPH (Jobs per Hour)**.
* A **main conveyor** downstream picks **from one buffer line at a time** and feeds a **Top Coat Oven**.

### Buffer Capacities

* **L1–L4**: 14 each
* **L5–L9**: 16 each

### Color Mix (≈900/day; 12 colors)

* C1 40%, C2 25%, C3 12%, C4 8%, C5 3%, C6 2%, C7 2%, C8 2%, C9 2%, C10 2%, C11 2%, C12 1%

> Buffers can also be **blocked at input/output** temporarily, creating scheduling constraints.

---

## 🧠 Core Challenge

Develop algorithms that:

1. **Maximize color grouping** to reduce color changeovers on the main conveyor.
2. **Prevent buffer overflow** (avoid stoppages).
3. **Minimize total processing time** to improve throughput.

---

## 🧩 What’s in this Prototype

* **Two strategies** side-by-side:

  * **Optimized Algorithm** (color grouping, smart buffer choice, O2 temp buffer, penalties modeled)
  * **Round-Robin Baseline** (fair and simple, no color awareness)
* **Interactive Streamlit UI**:

  * Live **simulation controls** (Start/Pause/Reset/Step)
  * **Buffer visualizer** (L1–L9 fill level & colors)
  * **O2 temporary buffer** view (when O2 is blocked)
  * **Recent activity log**
  * **KPIs & trends**: JPH, penalties, color changeovers
  * **PDF report generator** (uses `reportlab`)
* **Time & penalties model**:

  * 1s per vehicle + **1s penalty** for **O1 using L5–L9**
  * 1s **color change** penalty on main conveyor

---

## 🚀 Quickstart

### 1) Clone

```bash
git clone https://github.com/sakshipowar1612/Mindspark_Hackathon.git
cd Mindspark_Hackathon
```

### 2) Dependencies

Create `requirements.txt` (minimal for this app):

```txt
streamlit
pandas
numpy
reportlab
```

Install:

```bash
pip install -r requirements.txt
```

### 3) Run Locally

```bash
streamlit run simulator.py
```

---

## ☁️ One-Click Deploy (Streamlit Community Cloud)

1. Push code to GitHub (branch `main`).
2. Go to **share.streamlit.io** → **New app**.
3. Select repo & branch, set **Main file** = `simulator.py`.
4. Deploy.
   (The Cloud reads `requirements.txt` and builds automatically.)

**Secrets / keys?** Add them in the app settings → **Secrets**.
This app doesn’t require any by default.

---

## 🖥️ How to Use the Dashboard

* **Control Panel (Sidebar)**

  * **Start/Pause/Reset**
  * **Simulation Speed** (0.5×, 1×, 2×, 3×)
  * **Manual Steps**: Generate Colors → Place in Buffers → Conveyor Extract → Full Cycle
  * **Generate PDF Report** (auto KPIs, analysis, activity log)
  * **Toggle buffer I/O** per line (simulate maintenance/blocks)
  * **Color legend** & **Last color**
* **Main Area**

  * **Oven outputs** (new colors each cycle)
  * **O2 Temporary Buffer** (visible when O2 is blocked)
  * **Buffer Lines L1–L9** (color boxes = vehicles; dashed = empty slots)
  * **Main Conveyor (recent 10)** with color-change penalties
  * **Recent Activity** with expandable details
  * **Algorithm Comparison** cards + **JPH/Penalties** graphs over cycles

---

## 📊 KPIs & What They Mean

* **JPH (Jobs Per Hour)**: throughput proxy
* **Color Changeovers**: count of color switches on main conveyor (lower is better)
* **O1 Violations**: times O1 used **L5–L9** (incurs stop penalty on O2 side)
* **Buffer Utilization**: fill % across lines (avoid extremes)
* **Overflows**: when no buffer has space for an incoming vehicle

---

## ⚙️ Algorithm Sketch

### Optimized Algorithm (featured)

* **Placement (O1)**:

  1. Try buffers in **O1 block (L1–L4)** that **match current color** (fully same-color queues first).
  2. If none, use **empty** buffers in O1.
  3. If O1 must use **O2 block (L5–L9)** → apply **penalty** and **block O2**.
  4. If still none, **break the least harmful line** (smallest trailing run length, most space).
* **Placement (O2)**:

  * If blocked or temp queue non-empty → **push into temp buffer**.
  * Else use same color preference; else break least harmful buffer.
* **Extraction (Main Conveyor)**:

  * If **O2 buffers are saturated**, pick color with **longest connected run** at heads.
  * Otherwise try to **continue last color**; else pick **best head-run color**.
* **Penalties**: +1s for **O1→(L5–L9)** & +1s when **main conveyor changes color**.

### Round-Robin Baseline

* Simple **fair rotation** across eligible buffers for both placement and extraction.
* No color awareness, no penalty avoidance.

---

## 🧪 Demo Scenarios to Try

* **High C1/C2 flow** → watch color grouping win in optimized mode.
* **Block L2 output** → see how queues and JPH adapt.
* **Force O1 to use L5–L9** → O2 temp buffer grows; penalties increase.

---

## 📝 Auto PDF Report (1-click)

The **Generate PDF** button captures:

* **KPI summary** (cycles, processed, changeovers, JPH, penalties)
* **Buffer utilization** (per-line & overall)
* **Blocking & overflow** stats
* **Recent activity log**
  Format: polished headings, tables, insights, and a timestamped report ID.

> Requires `reportlab` (already in `requirements.txt`).

---

## 🧰 Project Structure (suggested)

```
Mindspark_Hackathon/
├─ simulator.py                    # Streamlit app (UI + algorithms)
├─ requirements.txt          # streamlit, pandas, numpy, reportlab
├─ .streamlit/               # optional config (e.g., theme)
│  └─ config.toml
└─ README.md                 # you are here
```

Optional `.streamlit/config.toml`:

```toml
[theme]
base="dark"
primaryColor="#2e7d32"
```

---

## 🔧 Configuration (tune without editing logic)

Inside `simulator.py`:

* **Color distribution**

  ```python
  COLOR_DISTRIBUTION = { "C1":0.20, "C2":0.25, "C3":0.12, "C4":0.20, "C5":0.03,
                         "C6":0.02, "C7":0.02, "C8":0.02, "C9":0.10, "C10":0.02,
                         "C11":0.02, "C12":0.01 }
  ```
* **Buffer capacities / ownership** (O1: L1–L4; O2: L5–L9)
* **Timings**

  ```python
  PROCESSING_TIME_PER_VEHICLE = 1        # seconds
  PENALTY_TIME_O1_L5_L9 = 1              # seconds
  PENALTY_TIME_COLOR_CHANGE = 1          # seconds
  ```

---

## 🧮 Evaluation Rubric (mapped to features)

| Criterion (Weight)            | Score 1 (Poor)        | Score 3 (Good)                | Score 5 (Excellent)                   | How we address                                                     |
| ----------------------------- | --------------------- | ----------------------------- | ------------------------------------- | ------------------------------------------------------------------ |
| **Innovation (20%)**          | Standard scheduling   | Some original optimization    | Highly novel OR/simulation hybrid     | Color-aware extraction + temp buffer + penalty modeling            |
| **Technical Execution (30%)** | Weak/inaccurate model | Functional, moderate accuracy | Robust with strong optimization       | Dual strategies, live KPIs, penalty/time model, buffer I/O toggles |
| **Business Relevance (25%)**  | Weak alignment        | Some relevance; partial gains | Clear cost/time efficiency            | JPH gains via changeover reduction & blockage handling             |
| **Visualization & UX (15%)**  | Poor/no visualization | Basic graphs                  | Clear, intuitive dashboards with KPIs | Rich buffer visuals, activity logs, comparison charts              |
| **Presentation & Demo (10%)** | Unclear/incomplete    | Functional demo               | Polished demo with insights           | One-click PDF report + interactive controls                        |

---

## 🛠️ Troubleshooting

* **ModuleNotFoundError** → add missing lib to `requirements.txt`, redeploy.
* **App won’t start in Cloud** → ensure **Main file** is `simulator.py` and branch is `main`.
* **Build too slow or failing** → keep `requirements.txt` **minimal**; avoid OS packages (e.g., `dbus-python`, `python-apt`, CUDA).
* **Graph empty** → run a few **cycles** first (Start or Full Cycle).

---

## 📄 License

MIT — feel free to use, modify, and build upon this work.
(Include a `LICENSE` file if you haven’t already.)

---

## 🙌 Acknowledgements

* Streamlit for rapid interactive dashboards
* Classic OR + simulation ideas for buffer/flow control
* Inspiration from real-world paint shop sequencing constraints

---

### 🔗 Quick Commands

```bash
# Create minimal requirements
printf "streamlit\npandas\nnumpy\nreportlab\n" > requirements.txt

# Run
streamlit run simulator.py
```
