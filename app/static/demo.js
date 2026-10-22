"use strict";

// Resolve relative to the page so the same app works at / and /ai-factory-demo/.
const base = new URL("./", window.location.href);
const endpoint = path => new URL(path, base);
const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

async function requestJSON(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 210000);
  try {
    const response = await fetch(endpoint(path), {
      ...options, signal: controller.signal, credentials: "same-origin",
      headers: {Accept: "application/json", ...options.headers},
    });
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("The server did not return a result. Refresh the page and try again.");
    }
    const data = await response.json();
    if (!response.ok) {
      if (response.status === 503) throw new Error("The review service is temporarily unavailable. Please try again.");
      if (response.status === 429) throw new Error("The demo is busy. Please wait a minute and try again.");
      if (Array.isArray(data.detail)) {
        throw new Error(data.detail.map(item => `${item.loc.slice(1).join(" · ")}: ${item.msg}`).join("\n"));
      }
      throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}). Please try again.`);
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The review timed out. Please try again.");
    if (error instanceof TypeError) throw new Error("Could not reach the server. Check your connection and try again.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function runVerification(button, output, getPayload) {
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "Verifying…";
  output.hidden = false;
  output.className = "result pending";
  output.replaceChildren(el("span", "spinner"), document.createTextNode("Checking your listing…"));
  output.append(el("p", "", "Basic checks run first, followed by image safety, text safety, and image–text relevance. This may take a minute."));
  const started = performance.now();
  try {
    const payload = await getPayload();
    const data = await requestJSON("products/verify", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    });
    if (!["approved", "rejected"].includes(data.status) || !Array.isArray(data.comments)) {
      throw new Error("The review returned an unexpected response. Please try again.");
    }
    output.className = `result ${data.status}`;
    const title = el("div", "result-title", data.status === "approved" ? "✓ Approved" : "× Rejected");
    title.append(el("span", "result-time", `${((performance.now() - started) / 1000).toFixed(1)} s`));
    output.replaceChildren(title);
    if (data.status === "approved") output.append(el("p", "", "This listing passed all verification checks."));
    if (data.comments.length) {
      const reasons = el("ul");
      for (const comment of data.comments) reasons.append(el("li", "", comment));
      output.append(reasons);
    }
    const raw = el("details", "raw-result");
    raw.open = true;
    raw.append(el("summary", "", "View JSON response"), el("pre", "", JSON.stringify(data, null, 2)));
    output.append(raw);
  } catch (error) {
    output.className = "result error";
    output.replaceChildren(el("div", "result-title", "Unable to complete verification"), el("p", "", error.message));
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

async function loadCases() {
  const loading = document.getElementById("cases-loading");
  try {
    const cases = await requestJSON("demo/cases");
    for (const item of cases) {
      const card = document.getElementById("case-template").content.firstElementChild.cloneNode(true);
      card.id = item.id;
      const success = item.expected === "approved";
      if (!success) card.classList.add("failure");
      card.querySelector(".case-icon").textContent = success ? "✓" : "×";
      card.querySelector(".case-name").textContent = item.name;
      card.querySelector(".case-subtitle").textContent = item.subtitle;
      card.querySelector(".expected-badge").textContent = `Expected: ${item.expected}`;
      card.querySelector(".listing-title").textContent = item.title;
      card.querySelector(".listing-description").textContent = item.description;
      card.querySelector("img").src = endpoint(item.image);
      const button = card.querySelector("button");
      button.addEventListener("click", () => runVerification(button, card.querySelector(".result"),
        () => requestJSON(`demo/cases/${encodeURIComponent(item.id)}/request`)));
      document.getElementById(success ? "success-cases" : "failure-cases").append(card);
    }
    loading.hidden = true;
  } catch (error) {
    loading.replaceChildren(el("p", "upload-error", error.message));
    const retry = el("button", "run-button", "Reload examples");
    retry.addEventListener("click", () => {
      document.getElementById("success-cases").replaceChildren();
      document.getElementById("failure-cases").replaceChildren();
      loading.textContent = "Loading examples…";
      loadCases();
    });
    loading.append(retry);
  }
}

const selectedImages = [];
const fileInput = document.getElementById("image-files");
const previews = document.getElementById("previews");
const uploadError = document.getElementById("upload-error");
const fields = document.getElementById("custom-fields");
const customRun = document.getElementById("custom-run");
const dropzone = document.getElementById("dropzone");
let readingFiles = false;

function renderPreviews() {
  previews.replaceChildren();
  document.getElementById("image-count").textContent = `${selectedImages.length} / 20`;
  selectedImages.forEach((item, index) => {
    const preview = el("div", "preview");
    const image = el("img");
    image.src = item.data;
    image.alt = item.file.name;
    const remove = el("button", "", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${item.file.name}`);
    remove.addEventListener("click", () => {
      selectedImages.splice(index, 1);
      uploadError.textContent = "";
      renderPreviews();
    });
    preview.append(image, remove, el("p", "", item.file.name));
    previews.append(preview);
  });
}

function readImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({file, data: reader.result});
    reader.onerror = () => reject(new Error(`Could not read ${file.name}. Try adding it again.`));
    reader.onabort = () => reject(new Error("Image reading was interrupted. Please try again."));
    reader.readAsDataURL(file);
  });
}

async function addFiles(files) {
  if (fields.disabled || readingFiles) return;
  uploadError.textContent = "";
  const incoming = Array.from(files);
  if (!incoming.length) return;
  try {
    if (selectedImages.length + incoming.length > 20) throw new Error("Choose at most 20 images.");
    for (const file of incoming) {
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error(`${file.name}: choose a JPG, PNG or WebP image.`);
      if (!file.size || file.size > 5 * 1024 * 1024) throw new Error(`${file.name}: images must be nonempty and at most 5 MiB each.`);
    }
    const size = [...selectedImages.map(item => item.file), ...incoming].reduce((sum, file) => sum + file.size, 0);
    if (size > 20 * 1024 * 1024) throw new Error("The combined image size must be at most 20 MiB.");
    readingFiles = true;
    fields.disabled = true;
    customRun.disabled = true;
    selectedImages.push(...await Promise.all(incoming.map(readImage)));
    renderPreviews();
  } catch (error) {
    uploadError.textContent = error.message;
  } finally {
    readingFiles = false;
    fields.disabled = false;
    customRun.disabled = false;
    fileInput.value = "";
  }
}

fileInput.addEventListener("change", () => addFiles(fileInput.files));
for (const type of ["dragenter", "dragover"]) dropzone.addEventListener(type, event => {
  event.preventDefault();
  if (!fields.disabled) dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", event => {
  if (!dropzone.contains(event.relatedTarget)) dropzone.classList.remove("dragover");
});
dropzone.addEventListener("drop", event => {
  event.preventDefault();
  dropzone.classList.remove("dragover");
  addFiles(event.dataTransfer.files);
});
// Dropping outside the target must not navigate away and discard the form.
window.addEventListener("dragover", event => event.preventDefault());
window.addEventListener("drop", event => event.preventDefault());
for (const [id, limit] of [["title", "200"], ["description", "4,000"]]) {
  const input = document.getElementById(id);
  input.addEventListener("input", () => {
    document.getElementById(`${id}-count`).textContent = `${input.value.length.toLocaleString()} / ${limit}`;
  });
}
document.getElementById("custom-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (customRun.disabled || readingFiles) return;
  const title = document.getElementById("title").value.trim();
  const description = document.getElementById("description").value.trim();
  if (!title || !description) {
    uploadError.textContent = "Enter a nonblank title and description.";
    return;
  }
  if (!selectedImages.length) {
    uploadError.textContent = "Add at least one product image.";
    fileInput.focus();
    return;
  }
  uploadError.textContent = "";
  fields.disabled = true;
  try {
    await runVerification(customRun, document.getElementById("custom-result"), () => ({
      title, description, images: selectedImages.map(item => item.data),
    }));
  } finally {
    fields.disabled = false;
  }
});
loadCases();
