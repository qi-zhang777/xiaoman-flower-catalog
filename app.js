const FAVORITES_KEY = "xiaoman-flower-favorites";

const demoBouquets = [
  {
    id: "demo-1",
    name: "雾粉清晨",
    subtitle: "低饱和粉调示例款",
    price: 268,
    priceType: "from",
    maxPrice: null,
    tags: ["示例", "温柔", "生日"],
    description: "这是一条示例资料。进入管理模式后，可以替换照片和文字，也可以直接删除。",
    image: "",
    visible: true,
    sample: true,
    createdAt: Date.now() - 3000
  },
  {
    id: "demo-2",
    name: "绿野慢信",
    subtitle: "自然枝叶感示例款",
    price: 398,
    priceType: "fixed",
    maxPrice: null,
    tags: ["示例", "自然", "纪念日"],
    description: "先把旧花束陆续上传进来，再通过隐藏和删除慢慢收拢风格。",
    image: "",
    visible: true,
    sample: true,
    createdAt: Date.now() - 2000
  },
  {
    id: "demo-3",
    name: "暗红回声",
    subtitle: "浓郁复古感示例款",
    price: 520,
    priceType: "range",
    maxPrice: 688,
    tags: ["示例", "复古", "高阶定制"],
    description: "价格可以显示为固定价、起价、区间或到店咨询，适合尚在调整中的定价方式。",
    image: "",
    visible: true,
    sample: true,
    createdAt: Date.now() - 1000
  }
];

const state = {
  bouquets: [],
  favorites: new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]")),
  activeFilter: "all",
  search: "",
  isManaging: false,
  localManager: ["localhost", "127.0.0.1"].includes(location.hostname),
  pendingImage: ""
};

const $ = (selector) => document.querySelector(selector);
const grid = $("#catalogGrid");
const emptyState = $("#emptyState");
const editorDialog = $("#editorDialog");
const detailDialog = $("#detailDialog");

async function getAllBouquets() {
  const source = state.localManager ? "/api/catalog" : `catalog.json?v=${Date.now()}`;
  const response = await fetch(source, { cache: "no-store" });
  if (!response.ok) throw new Error("图册数据读取失败");
  const payload = await response.json();
  return Array.isArray(payload) ? payload : payload.bouquets || [];
}

async function saveBouquet(item) {
  if (!state.localManager) throw new Error("公开网站不能修改图册");
  const response = await fetch("/api/bouquets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(item)
  });
  if (!response.ok) throw new Error("保存失败");
  return response.json();
}

async function deleteBouquet(id) {
  if (!state.localManager) throw new Error("公开网站不能修改图册");
  const response = await fetch(`/api/bouquets/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!response.ok) throw new Error("删除失败");
}

async function initializeData() {
  const items = await getAllBouquets();
  state.bouquets = items.sort((a, b) => b.createdAt - a.createdAt);
  $("#manageButton").classList.toggle("hidden", !state.localManager);
  if (state.localManager) {
    $("#aboutTip").textContent = "这是店主电脑的编辑模式。修改会直接写入网站文件；完成后发布更新，顾客就能看到最新版。";
  }
  render();
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function priceLabel(item) {
  const price = Number(item.price || 0);
  if (item.priceType === "ask") return "价格咨询";
  if (item.priceType === "range" && item.maxPrice) return `¥${price}–${Number(item.maxPrice)}`;
  if (item.priceType === "from") return `¥${price} 起`;
  return `¥${price}`;
}

function filteredBouquets() {
  return state.bouquets.filter((item) => {
    if (!state.isManaging && !item.visible) return false;
    if (state.activeFilter === "under200" && item.price >= 200) return false;
    if (state.activeFilter === "200to399" && (item.price < 200 || item.price >= 400)) return false;
    if (state.activeFilter === "over400" && item.price < 400) return false;
    if (state.activeFilter === "favorite" && !state.favorites.has(item.id)) return false;
    const haystack = [item.name, item.subtitle, item.description, ...(item.tags || [])].join(" ").toLowerCase();
    return haystack.includes(state.search.toLowerCase().trim());
  });
}

function cardImage(item, index) {
  if (item.image) return `<img src="${item.image}" alt="${escapeHtml(item.name)}" loading="lazy" />`;
  return `<div class="image-placeholder placeholder-${index % 3}"><span>${escapeHtml(item.name)}</span></div>`;
}

function render() {
  const items = filteredBouquets();
  const visibleCount = state.bouquets.filter((item) => item.visible).length;
  $("#bouquetCount").textContent = `${visibleCount} 款花束`;

  grid.innerHTML = items.map((item, index) => `
    <article class="bouquet-card" data-id="${item.id}">
      <div class="card-image-wrap" data-action="detail">
        ${cardImage(item, index)}
        ${item.sample ? '<span class="sample-badge">示例资料</span>' : ""}
        ${state.isManaging && !item.visible ? '<span class="visibility-badge">已隐藏</span>' : ""}
        ${!state.isManaging ? `<button class="favorite-button ${state.favorites.has(item.id) ? "is-favorite" : ""}" data-action="favorite" type="button" aria-label="${state.favorites.has(item.id) ? "取消喜欢" : "加入喜欢"}">${state.favorites.has(item.id) ? "♥" : "♡"}</button>` : ""}
      </div>
      <div class="card-body">
        <div class="card-copy" data-action="detail">
          <h3>${escapeHtml(item.name)}</h3>
          <p>${escapeHtml(item.subtitle || "一束正在被记录的花")}</p>
        </div>
        <div class="card-price">${priceLabel(item)}</div>
      </div>
      ${(item.tags || []).length ? `<div class="card-tags">${item.tags.slice(0, 4).map((tag) => `<span class="card-tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      ${state.isManaging ? `
        <div class="admin-card-actions">
          <button data-action="edit" type="button">编辑</button>
          <button data-action="visibility" type="button">${item.visible ? "隐藏" : "显示"}</button>
          <button class="danger" data-action="delete" type="button">删除</button>
        </div>` : ""}
    </article>
  `).join("");

  const hasItems = items.length > 0;
  grid.classList.toggle("hidden", !hasItems);
  emptyState.classList.toggle("hidden", hasItems);
  $("#emptyAddButton").classList.toggle("hidden", !state.isManaging);
  $("#emptyMessage").textContent = state.isManaging ? "从一张喜欢的照片开始。" : "换一个筛选条件试试。";
}

function toggleManageMode(value) {
  if (!state.localManager) return;
  state.isManaging = value;
  $("#adminBar").classList.toggle("hidden", !value);
  $("#manageButton").classList.toggle("hidden", value);
  render();
  showToast(value ? "已进入管理模式" : "图册已保存");
}

function openEditor(item = null) {
  $("#editorForm").reset();
  state.pendingImage = item?.image || "";
  $("#editorTitle").textContent = item ? "编辑花束" : "添加花束";
  $("#itemId").value = item?.id || "";
  $("#nameInput").value = item?.name || "";
  $("#subtitleInput").value = item?.subtitle || "";
  $("#priceInput").value = item?.price ?? "";
  $("#priceTypeInput").value = item?.priceType || "fixed";
  $("#maxPriceInput").value = item?.maxPrice ?? "";
  $("#tagsInput").value = (item?.tags || []).join(", ");
  $("#descriptionInput").value = item?.description || "";
  $("#visibleInput").checked = item?.visible ?? true;
  updatePriceFields();
  updateImagePreview();
  editorDialog.showModal();
}

function updatePriceFields() {
  $("#maxPriceField").classList.toggle("hidden", $("#priceTypeInput").value !== "range");
}

function updateImagePreview() {
  const preview = $("#imagePreview");
  preview.src = state.pendingImage || "";
  preview.classList.toggle("hidden", !state.pendingImage);
  $("#uploadPlaceholder").classList.toggle("hidden", Boolean(state.pendingImage));
}

async function compressImage(file) {
  const dataUrl = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
  const maxSide = 1800;
  const scale = Math.min(1, maxSide / Math.max(image.width, image.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(image.width * scale);
  canvas.height = Math.round(image.height * scale);
  canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.84);
}

async function handleEditorSubmit(event) {
  event.preventDefault();
  const existingId = $("#itemId").value;
  const existing = state.bouquets.find((item) => item.id === existingId);
  const item = {
    id: existingId || `bouquet-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    name: $("#nameInput").value.trim(),
    subtitle: $("#subtitleInput").value.trim(),
    price: Number($("#priceInput").value || 0),
    priceType: $("#priceTypeInput").value,
    maxPrice: $("#priceTypeInput").value === "range" ? Number($("#maxPriceInput").value || 0) : null,
    tags: $("#tagsInput").value.split(/[,，]/).map((tag) => tag.trim()).filter(Boolean),
    description: $("#descriptionInput").value.trim(),
    image: state.pendingImage,
    visible: $("#visibleInput").checked,
    sample: false,
    createdAt: existing?.createdAt || Date.now(),
    updatedAt: Date.now()
  };
  const savedItem = await saveBouquet(item);
  const index = state.bouquets.findIndex((entry) => entry.id === savedItem.id);
  if (index >= 0) state.bouquets[index] = savedItem;
  else state.bouquets.unshift(savedItem);
  editorDialog.close();
  render();
  showToast(existing ? "修改已保存" : "花束已加入图册");
}

function showDetail(item) {
  const image = item.image
    ? `<img src="${item.image}" alt="${escapeHtml(item.name)}" />`
    : `<div class="image-placeholder placeholder-${Math.abs(item.id.length) % 3}"><span>${escapeHtml(item.name)}</span></div>`;
  $("#detailContent").innerHTML = `
    <div class="detail-layout">
      <div class="detail-image">${image}</div>
      <div class="detail-copy">
        <button class="icon-button" type="button" data-close="detailDialog" aria-label="关闭">×</button>
        <p class="section-number">BOUQUET DETAIL</p>
        <h2>${escapeHtml(item.name)}</h2>
        <p class="detail-subtitle">${escapeHtml(item.subtitle || "一束正在被记录的花")}</p>
        <div class="detail-price">${priceLabel(item)}</div>
        <p class="detail-description">${escapeHtml(item.description || "花材会随季节变化，具体细节可以在预订时沟通。")}</p>
        <div class="detail-tags">${(item.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
        <p class="detail-note">鲜花为自然材料，色彩与形态会有轻微差异。图册价格为参考，最终以当日花材为准。</p>
      </div>
    </div>`;
  detailDialog.showModal();
}

async function handleCardAction(event) {
  const button = event.target.closest("[data-action]");
  const card = event.target.closest(".bouquet-card");
  if (!button || !card) return;
  const item = state.bouquets.find((entry) => entry.id === card.dataset.id);
  if (!item) return;
  const action = button.dataset.action;
  if (action === "detail") showDetail(item);
  if (action === "favorite") {
    state.favorites.has(item.id) ? state.favorites.delete(item.id) : state.favorites.add(item.id);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
    render();
  }
  if (action === "edit") openEditor(item);
  if (action === "visibility") {
    item.visible = !item.visible;
    item.updatedAt = Date.now();
    await saveBouquet(item);
    render();
    showToast(item.visible ? "已在顾客图册中显示" : "已隐藏，资料仍然保留");
  }
  if (action === "delete") {
    const confirmed = confirm(`确定删除“${item.name}”吗？\n删除后只能通过之前导出的备份恢复。`);
    if (!confirmed) return;
    await deleteBouquet(item.id);
    state.bouquets = state.bouquets.filter((entry) => entry.id !== item.id);
    state.favorites.delete(item.id);
    localStorage.setItem(FAVORITES_KEY, JSON.stringify([...state.favorites]));
    render();
    showToast("花束已删除");
  }
}

function exportCatalog() {
  const payload = {
    version: 1,
    exportedAt: new Date().toISOString(),
    brand: "小满 flower",
    bouquets: state.bouquets
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `小满flower-图册备份-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("备份已导出");
}

async function importCatalog(file) {
  try {
    const payload = JSON.parse(await file.text());
    if (!Array.isArray(payload.bouquets)) throw new Error("格式不正确");
    const shouldReplace = confirm(`备份中有 ${payload.bouquets.length} 款花束。\n确定导入并覆盖同名编号的资料吗？`);
    if (!shouldReplace) return;
    for (const item of payload.bouquets) await saveBouquet(item);
    state.bouquets = (await getAllBouquets()).sort((a, b) => b.createdAt - a.createdAt);
    render();
    showToast("备份导入完成");
  } catch (error) {
    showToast("导入失败：不是有效的图册备份");
  }
}

let toastTimer;
function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2200);
}

$("#manageButton").addEventListener("click", () => toggleManageMode(true));
$("#exitManageButton").addEventListener("click", () => toggleManageMode(false));
$("#addButton").addEventListener("click", () => openEditor());
$("#emptyAddButton").addEventListener("click", () => openEditor());
$("#aboutButton").addEventListener("click", () => $("#aboutDialog").showModal());
$("#priceTypeInput").addEventListener("change", updatePriceFields);
$("#editorForm").addEventListener("submit", handleEditorSubmit);
grid.addEventListener("click", handleCardAction);

$("#imageInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    state.pendingImage = await compressImage(file);
    updateImagePreview();
  } catch (error) {
    showToast("图片读取失败，请换一张试试");
  }
});

$("#filters").addEventListener("click", (event) => {
  const chip = event.target.closest(".filter-chip");
  if (!chip) return;
  document.querySelectorAll(".filter-chip").forEach((entry) => entry.classList.remove("active"));
  chip.classList.add("active");
  state.activeFilter = chip.dataset.filter;
  render();
});

$("#searchInput").addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});

$("#exportButton").addEventListener("click", exportCatalog);
$("#importButton").addEventListener("click", () => $("#importInput").click());
$("#importInput").addEventListener("change", (event) => {
  if (event.target.files[0]) importCatalog(event.target.files[0]);
  event.target.value = "";
});

document.addEventListener("click", (event) => {
  const closer = event.target.closest("[data-close]");
  if (!closer) return;
  document.getElementById(closer.dataset.close)?.close();
});

document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
});

initializeData().catch(() => {
  state.bouquets = [...demoBouquets];
  render();
  showToast("图册数据读取失败，正在显示示例内容");
});
