/* Attachment lifecycle for the student workspace. */
export function createMaterialManager({ api, maxFiles, onChanged }) {
  let pendingFiles = [];

  function selected() {
    return [...pendingFiles];
  }

  function validate(files) {
    const allowed = [
      "image/jpeg", "image/png", "image/webp", "text/plain", "text/markdown",
      "text/csv", "text/tab-separated-values", "application/json", "application/pdf",
      "application/msword",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.apache.parquet",
    ];
    if (files.length > maxFiles) {
      throw new Error(`一次最多上传 ${maxFiles} 个材料`);
    }
    files.forEach((file) => {
      if (!allowed.includes(file.type)
        && !/\.(md|txt|csv|json|pdf|doc|docx|xlsx|parquet)$/i.test(file.name)) {
        throw new Error(`暂不支持材料类型：${file.name}`);
      }
      if (file.size > 20 * 1024 * 1024) {
        throw new Error(`材料不能超过 20MB：${file.name}`);
      }
    });
  }

  function fileKey(file) {
    return [file.name, file.size, file.type, file.lastModified].join(":");
  }

  function append(files) {
    const known = new Set(pendingFiles.map(fileKey));
    const additions = files.filter((file) => !known.has(fileKey(file)));
    const combined = [...pendingFiles, ...additions];
    validate(combined);
    pendingFiles = combined;
    onChanged(selected());
  }

  function clear() {
    pendingFiles = [];
    onChanged([]);
  }

  function removeAt(index) {
    pendingFiles.splice(index, 1);
    onChanged(selected());
  }

  async function attachExample(button) {
    const imageSrc = button.dataset.imageSrc;
    if (!imageSrc) return;
    const response = await fetch(imageSrc);
    if (!response.ok) throw new Error("示例题图片暂时无法读取");
    const blob = await response.blob();
    append([new File(
      [blob],
      button.dataset.imageName || "question.jpg",
      { type: blob.type || "image/jpeg" },
    )]);
  }

  async function upload() {
    const files = selected();
    if (!files.length) return [];
    validate(files);
    const materials = [];
    for (const file of files) {
      const form = new FormData();
      form.append("upload", file);
      form.append("purpose", "unified_task_material");
      const uploaded = await api("/api/v1/files", { method: "POST", body: form });
      if (["failed", "processing", "pending"].includes(uploaded.ingestion_status)) {
        throw new Error(uploaded.extraction_error || `材料解析失败：${file.name}`);
      }
      materials.push({
        uploaded,
        extractedText: uploaded.extracted_text || "",
        originalType: file.type,
      });
    }
    return materials;
  }

  return { selected, validate, append, clear, removeAt, attachExample, upload };
}
