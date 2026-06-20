// Front-end logic: talk to the Flask routes /build and /ask.

const fileInput  = document.getElementById("fileInput");
const dropzone   = document.getElementById("dropzone");
const fileLabel  = document.getElementById("fileLabel");
const buildBtn   = document.getElementById("buildBtn");
const buildStat  = document.getElementById("buildStatus");
const rulesEl    = document.getElementById("rules");
const chat       = document.getElementById("chat");
const chatEmpty  = document.getElementById("chatEmpty");
const askForm    = document.getElementById("askForm");
const question   = document.getElementById("question");
const askBtn     = document.getElementById("askBtn");

let ready = false;
const history = [];   // [{role:'user'|'assistant', content}] sent for context

// --- file picking ---
// NOTE: the dropzone is a <label> wrapping the hidden <input>, so clicking it
// already opens the file dialog. Do NOT also call fileInput.click() here, or the
// dialog opens twice (asks for the file two times).
["dragover", "dragenter"].forEach(ev =>
  dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave", "drop"].forEach(ev =>
  dropzone.addEventListener(ev, e => { e.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", e => {
  if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; onFile(); }
});
fileInput.addEventListener("change", onFile);

function onFile() {
  const f = fileInput.files[0];
  if (!f) return;
  fileLabel.innerHTML = `<b>${f.name}</b><br><small>${(f.size / 1024).toFixed(1)} KB</small>`;
  dropzone.classList.add("has-file");
  buildBtn.disabled = false;
}

// --- process document ---
buildBtn.addEventListener("click", async () => {
  const f = fileInput.files[0];
  if (!f) return;
  buildBtn.disabled = true;
  buildStat.className = "status";
  buildStat.innerHTML = `<span class="spin"></span>Processing your document…`;

  const form = new FormData();
  form.append("document", f);
  try {
    const res = await fetch("/build", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Could not process the document");

    rulesEl.textContent = data.rules || "(no rules found)";
    buildStat.className = "status ok";
    buildStat.textContent = "✅ Your document is ready. Ask a question below.";

    history.length = 0;   // fresh conversation for the new document
    ready = true;
    question.disabled = false;
    askBtn.disabled = false;
    question.focus();
  } catch (err) {
    buildStat.className = "status err";
    buildStat.textContent = "⚠️ " + err.message;
  } finally {
    buildBtn.disabled = false;
  }
});

// --- ask ---
askForm.addEventListener("submit", async e => {
  e.preventDefault();
  const q = question.value.trim();
  if (!q || !ready) return;
  if (chatEmpty) chatEmpty.remove();

  addMessage("user", q);
  question.value = "";
  askBtn.disabled = true;
  const thinking = addMessage("bot", '<span class="spin"></span>Thinking…', true);

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // send prior turns so follow-ups like "yes" / "continue" work
      body: JSON.stringify({ question: q, history: history.slice(-8) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    thinking.querySelector(".bubble").textContent = data.answer;
    history.push({ role: "user", content: q });
    history.push({ role: "assistant", content: data.answer });
  } catch (err) {
    thinking.querySelector(".bubble").textContent = "⚠️ " + err.message;
  } finally {
    askBtn.disabled = false;
    question.focus();
    chat.scrollTop = chat.scrollHeight;
  }
});

// --- helpers ---
function addMessage(role, html, isHtml) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + (role === "user" ? "user" : "bot");
  const who = document.createElement("div");
  who.className = "who";
  who.textContent = role === "user" ? "You" : "Assistant";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (isHtml) bubble.innerHTML = html; else bubble.textContent = html;
  wrap.appendChild(who);
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}
