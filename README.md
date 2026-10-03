# Simple-Python-Game
A small, simple, text based game.

# 💻 Launch Your Software Development Career Today!  

🎓 **No degree? No problem!** My program equips you with everything you need to break into tech and land an entry-level software development role.  

🚀 **Why Join?**  
- 💼 **$70k+ starting salary potential**  
- 🕐 **Self-paced:** Complete on your own time  
- 🤑 **Affordable:** Low risk compared to expensive bootcamps or degrees
- 🎯 **45,000+ job openings** in the market  

👉 **[Start your journey today!](https://techwithtim.net/dev)**  
No experience needed—just your determination. Future-proof your career and unlock six-figure potential like many of our students have!  

# 🧪 Tests

The quiz logic is split into `normalize_answer` (input normalization),
`initial_state`/`advance` (state advancement), `finish` (score clamping
and pass/fail outcome) and `play` (natural termination on EOF).

Run the test suite (exhaustively plays every short input sequence and
records each path's final state to `tests/path_states.jsonl`):

```
python3 -m pytest
```
