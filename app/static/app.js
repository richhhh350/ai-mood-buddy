const input = document.querySelector("#mood-input");
const analyzeButton = document.querySelector("#analyze-button");
const inputMessage = document.querySelector("#input-message");
const resultEmpty = document.querySelector("#result-empty");
const moodCard = document.querySelector("#mood-card");
const historyList = document.querySelector("#history-list");
const clearHistoryButton = document.querySelector("#clear-history");
const serviceStatus = document.querySelector("#service-status");
const historyMessage = document.querySelector("#history-message");

let history = [];
let busy = false;
let selectedId = null;
let historyVersion = 0;

function resetMoodCard() {
  selectedId = null;
  moodCard.innerHTML = "";
  moodCard.hidden = true;
  resultEmpty.hidden = false;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value);
  return element.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function formatCreatedAt(value) {
  return new Date(value).toLocaleString("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function makeStars(intensity) {
  return "●".repeat(intensity) + "○".repeat(5 - intensity);
}

function renderMoodCard(entry) {
  selectedId = entry.id;
  resultEmpty.hidden = true;
  moodCard.hidden = false;
  moodCard.innerHTML = `
    <div class="mood-title">
      <span class="mood-emoji" aria-hidden="true">${escapeHtml(entry.emoji)}</span>
      <div><h3>${escapeHtml(entry.mood)}</h3><span class="intensity" aria-label="情绪强度 ${entry.intensity} 级">${makeStars(entry.intensity)}</span></div>
    </div>
    <p>${escapeHtml(entry.original_text)}</p>
    <p class="service-note">${formatCreatedAt(entry.created_at)} · AI 生成，仅供自我整理参考</p>
    <p class="response">${escapeHtml(entry.response)}</p>
    <div class="action-box"><strong>现在可以做</strong><p>${escapeHtml(entry.action)}</p></div>`;
}

function renderHistory() {
  if (history.length === 0) {
    historyList.innerHTML = '<p class="empty-history">还没有记录，写下第一份心情吧。</p>';
    return;
  }
  historyList.innerHTML = history.map((entry) => `
    <article class="history-item">
      <span class="emoji" aria-hidden="true">${escapeHtml(entry.emoji)}</span>
      <div><h3>${escapeHtml(entry.mood)} · ${formatCreatedAt(entry.created_at)}</h3><p>${escapeHtml(entry.original_text)}</p></div>
      <div class="history-actions"><button class="view-button text-button" type="button" data-id="${escapeHtml(entry.id)}" aria-label="查看这条心情的完整分析">查看</button>
      <button class="delete-button" type="button" data-id="${escapeHtml(entry.id)}" aria-label="删除这条心情记录">删除</button>
      </div>
    </article>`).join("");
}

input.addEventListener("input", () => {
  inputMessage.classList.remove("error");
  inputMessage.innerHTML = `<span id="character-count">${Array.from(input.value.trim()).length}</span> / 500`;
});

analyzeButton.addEventListener("click", async () => {
  if (busy) return;
  const originalText = input.value.trim();
  if (!originalText) {
    inputMessage.textContent = "请先写下你现在的感受";
    inputMessage.classList.add("error");
    input.focus();
    return;
  }
  if (Array.from(originalText).length > 500) {
    inputMessage.textContent = "最多输入 500 个字符";
    inputMessage.classList.add("error");
    return;
  }

  busy = true;
  input.disabled = true;
  analyzeButton.disabled = true;
  analyzeButton.textContent = "正在分析……";
  inputMessage.classList.remove("error");
  // 整个网络等待最多 45 秒；超时后服务端可能仍在完成保存。
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 45000);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: originalText }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(errorBody.detail?.message || "输入不符合要求或分析失败，请检查后重试。");
    }

    const reply = await response.json();
    if (reply.status === "support_needed") {
      selectedId = null;
      resultEmpty.hidden = true;
      moodCard.hidden = false;
      moodCard.textContent = reply.message;
      inputMessage.textContent = "本次未保存为心情记录。";
      return;
    }
    historyVersion++;
    history = [reply, ...history.filter(entry => entry.id !== reply.id)].slice(0, 20);
    renderMoodCard(reply);
    renderHistory();
    input.value = "";
    inputMessage.innerHTML = '<span id="character-count">0</span> / 500';
  } catch (error) {
    inputMessage.textContent = error.name === "AbortError"
      ? "等待超时，请刷新历史记录确认是否保存，再决定是否重试。"
      : (error instanceof TypeError ? "暂时没有分析成功，请稍后重试" : error.message);
    inputMessage.classList.add("error");
  } finally {
    window.clearTimeout(timer);
    busy = false;
    input.disabled = false;
    analyzeButton.disabled = false;
    analyzeButton.textContent = "分析一下";
  }
});

historyList.addEventListener("click", async (event) => {
  const viewButton = event.target.closest(".view-button");
  if (viewButton) {
    const entry = history.find(item => item.id === viewButton.dataset.id);
    if (entry) {
      renderMoodCard(entry);
      moodCard.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
    }
    return;
  }
  const deleteButton = event.target.closest(".delete-button");
  if (!deleteButton) return;
  deleteButton.disabled = true;
  try {
    const response = await fetch(`/api/entries/${encodeURIComponent(deleteButton.dataset.id)}`, {
      method: "DELETE",
    });
    if (!response.ok && response.status !== 404) throw new Error("删除失败，请重试。");
    historyVersion++;
    history = history.filter(entry => entry.id !== deleteButton.dataset.id);
    if (selectedId === deleteButton.dataset.id) resetMoodCard();
    renderHistory();
    await loadHistory();
  } catch (error) {
    historyMessage.textContent = "删除未确认，请刷新历史记录后重试。";
  } finally {
    deleteButton.disabled = false;
  }
});

clearHistoryButton.addEventListener("click", async () => {
  if (!window.confirm("清空数据库中的全部心情记录？删除后无法撤销。")) return;
  clearHistoryButton.disabled = true;
  try {
    const response = await fetch("/api/entries", { method: "DELETE" });
    if (!response.ok) throw new Error("清空失败");
    historyVersion++;
    history = [];
    resetMoodCard();
    renderHistory();
    await loadHistory();
  } catch (error) {
    historyMessage.textContent = "清空未确认，请刷新历史记录后重试。";
  } finally {
    clearHistoryButton.disabled = false;
  }
});

async function loadHistory() {
  const version = ++historyVersion;
  try {
    const response = await fetch("/api/entries");
    if (!response.ok) throw new Error(`请求失败：${response.status}`);
    const entries = await response.json();
    if (version !== historyVersion) return;
    history = entries;
    renderHistory();
    historyMessage.textContent = "";
  } catch (error) {
    if (version !== historyVersion) return;
    historyMessage.textContent = "历史记录暂时无法加载，请刷新页面重试。";
  }
}

loadHistory();

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("status unavailable");
    const status = await response.json();
    analyzeButton.disabled = !status.ai_configured;
    const provider = status.provider_label || "AI 服务商";
    document.querySelector("#privacy-message").textContent =
      `点击分析后，本次输入会发送给 ${provider} 生成回应；不会发送历史记录。`;
    serviceStatus.textContent = status.ai_configured
      ? `${provider} 已配置，实际可用性将在提交时检查。`
      : (status.error || `尚未配置 ${provider}：请在项目 .env 填入 ${status.key_variable || "API Key"} 后刷新。已有记录仍可查看。`);
  } catch (error) {
    analyzeButton.disabled = true;
    serviceStatus.textContent = "后端暂不可用，请启动服务后刷新页面。";
  }
}

loadStatus();
