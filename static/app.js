(() => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const galleryPanel = document.getElementById("gallery-panel");
  const gallery = document.getElementById("gallery");
  const photoCount = document.getElementById("photo-count");
  const addMoreBtn = document.getElementById("add-more-btn");
  const configPanel = document.getElementById("config-panel");
  const lunaLabelInput = document.getElementById("luna-label");
  const generateBtn = document.getElementById("generate-btn");
  const statusPanel = document.getElementById("status-panel");
  const statusTitle = document.getElementById("status-title");
  const statusSub = document.getElementById("status-sub");
  const progressFill = document.getElementById("progress-fill");
  const resultPanel = document.getElementById("result-panel");
  const resultIcon = document.getElementById("result-icon");
  const resultTitle = document.getElementById("result-title");
  const resultDetail = document.getElementById("result-detail");
  const warningsBox = document.getElementById("warnings-box");
  const warningsTitle = document.getElementById("warnings-title");
  const warningsList = document.getElementById("warnings-list");
  const downloadLink = document.getElementById("download-link");
  const resetBtn = document.getElementById("reset-btn");
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxClose = document.getElementById("lightbox-close");

  let uploadedFiles = []; // {id, original_name, url}

  // --- drop zone ---
  dropZone.addEventListener("click", () => fileInput.click());
  addMoreBtn.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) uploadFiles(fileInput.files);
    fileInput.value = "";
  });

  ["dragenter", "dragover"].forEach(evt => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach(evt => {
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    });
  });
  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
  });

  async function uploadFiles(fileList) {
    const formData = new FormData();
    for (const f of fileList) formData.append("photos", f);

    dropZone.classList.add("dragover");
    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || "Eroare la incarcare");
        return;
      }
      uploadedFiles = uploadedFiles.concat(data.files);
      renderGallery();
    } catch (err) {
      alert("Eroare de retea la incarcare: " + err.message);
    } finally {
      dropZone.classList.remove("dragover");
    }
  }

  function renderGallery() {
    gallery.innerHTML = "";
    uploadedFiles.forEach(file => {
      const card = document.createElement("div");
      card.className = "photo-card";

      const img = document.createElement("img");
      img.src = file.url;
      img.alt = file.original_name;
      img.addEventListener("click", () => openLightbox(file.url));

      const label = document.createElement("div");
      label.className = "photo-label";
      label.textContent = file.original_name;

      const removeBtn = document.createElement("button");
      removeBtn.className = "remove-btn";
      removeBtn.textContent = "\u00d7";
      removeBtn.title = "Sterge poza";
      removeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        removeFile(file.id);
      });

      card.appendChild(img);
      card.appendChild(label);
      card.appendChild(removeBtn);
      gallery.appendChild(card);
    });

    photoCount.textContent = uploadedFiles.length;
    galleryPanel.hidden = uploadedFiles.length === 0;
    configPanel.hidden = uploadedFiles.length === 0;
    updateGenerateEnabled();
  }

  async function removeFile(id) {
    try {
      await fetch(`/api/uploads/${id}`, { method: "DELETE" });
    } catch (err) {
      // continuam oricum sa scoatem din UI
    }
    uploadedFiles = uploadedFiles.filter(f => f.id !== id);
    renderGallery();
  }

  function openLightbox(url) {
    lightboxImg.src = url;
    lightbox.hidden = false;
  }
  lightboxClose.addEventListener("click", () => { lightbox.hidden = true; });
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) lightbox.hidden = true;
  });

  function updateGenerateEnabled() {
    generateBtn.disabled = uploadedFiles.length === 0;
  }

  // --- generation ---
  generateBtn.addEventListener("click", startGeneration);

  async function startGeneration() {
    const lunaLabel = lunaLabelInput.value.trim() || "curse";

    configPanel.hidden = true;
    galleryPanel.hidden = true;
    statusPanel.hidden = false;
    resultPanel.hidden = true;
    statusTitle.textContent = "Se trimit pozele...";
    statusSub.textContent = "";
    progressFill.style.width = "5%";

    try {
      const res = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_ids: uploadedFiles.map(f => f.id),
          luna_label: lunaLabel,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        showError(data.error || "Eroare la pornirea generarii");
        return;
      }
      pollStatus(data.job_id);
    } catch (err) {
      showError("Eroare de retea: " + err.message);
    }
  }

  function pollStatus(jobId) {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/status/${jobId}`);
        const job = await res.json();

        if (job.status === "extracting" && job.progress) {
          const { current, total, filename } = job.progress;
          statusTitle.textContent = `Citesc pozele (${current}/${total})`;
          statusSub.textContent = filename;
          progressFill.style.width = `${10 + (current / total) * 70}%`;
        } else if (job.status === "building") {
          statusTitle.textContent = "Generez documentul Word...";
          statusSub.textContent = "";
          progressFill.style.width = "90%";
        } else if (job.status === "done") {
          clearInterval(interval);
          progressFill.style.width = "100%";
          showResult(job.result);
        } else if (job.status === "error") {
          clearInterval(interval);
          showError(job.error || "Eroare necunoscuta la generare");
        }
      } catch (err) {
        clearInterval(interval);
        showError("Am pierdut legatura cu serverul local.");
      }
    }, 900);
  }

  function showResult(result) {
    statusPanel.hidden = true;
    resultPanel.hidden = false;
    resultIcon.className = "result-icon";
    resultIcon.textContent = "\u2713";
    resultTitle.textContent = "Word generat cu succes";
    resultDetail.textContent =
      `${result.randuri_count} randuri, total ${result.total_general} RON+TVA.`;

    const warnings = [];
    if (result.randuri_fara_pret && result.randuri_fara_pret.length) {
      result.randuri_fara_pret.forEach(r => {
        warnings.push(`${r.data} — ${r.ruta}: ruta noua, pret gol in Word (completeaza manual)`);
      });
    }
    if (result.randuri_neclare && result.randuri_neclare.length) {
      result.randuri_neclare.forEach(r => {
        warnings.push(`${r.data || "data neclara"} — ${r.text_partial || "?"} (${r.motiv || "neclar"}) — nu a fost inclus`);
      });
    }

    if (warnings.length) {
      warningsBox.hidden = false;
      warningsTitle.textContent = `De verificat manual (${warnings.length})`;
      warningsList.innerHTML = "";
      warnings.forEach(w => {
        const li = document.createElement("li");
        li.textContent = w;
        warningsList.appendChild(li);
      });
    } else {
      warningsBox.hidden = true;
    }

    downloadLink.href = result.output_url;
    downloadLink.setAttribute("download", result.output_file);
  }

  function showError(message) {
    statusPanel.hidden = true;
    resultPanel.hidden = false;
    resultIcon.className = "result-icon error";
    resultIcon.textContent = "\u2715";
    resultTitle.textContent = "Ceva nu a mers";
    resultDetail.textContent = message;
    warningsBox.hidden = true;
    downloadLink.style.display = "none";
  }

  resetBtn.addEventListener("click", () => {
    location.reload();
  });
})();
