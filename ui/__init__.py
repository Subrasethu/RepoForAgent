# This file marks ui as a Python module
# Do not run this file directly
```

Press **`Ctrl + S`** to save.

---

## The Golden Rule
```
__init__.py  →  NEVER press F5 on this file
ingest.py    →  Press F5 to test
main.py      →  Press F5 to run the full agent
```

---

## Now run the correct file

Click on **`ticketrepoagent\ingest.py`** in the left panel and press **`F5`**

You should see:
```
Project root detected as: C:\Users\Admin\OneDrive\...\AgentBuild
Loading config from: ...\AgentBuild\config.yaml
Looking for CSV files in: ...\AgentBuild\data\input
Reading file: tickets.csv
Total resolved tickets loaded: 10
Tickets after cleaning: 10