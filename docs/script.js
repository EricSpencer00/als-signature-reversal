/* ============================================================
   ALS · SIGNATURE REVERSAL  —  client
   Vanilla JS only, no build step.
   ============================================================ */
(function () {
  "use strict";

  const D = window.ALS_DATA;
  if (!D) return console.error("ALS_DATA missing — site cannot render.");

  /* -------------------- Clock (research-console flourish) -------------------- */
  const clock = document.getElementById("clock");
  function tick() {
    if (!clock) return;
    const t = new Date();
    const hh = String(t.getUTCHours()).padStart(2, "0");
    const mm = String(t.getUTCMinutes()).padStart(2, "0");
    const ss = String(t.getUTCSeconds()).padStart(2, "0");
    clock.textContent = `${hh}:${mm}:${ss} UTC`;
  }
  tick(); setInterval(tick, 1000);

  /* -------------------- Hero line stagger -------------------- */
  document.querySelectorAll(".display .line").forEach(el => {
    const delay = Number(el.dataset.delay || 0);
    setTimeout(() => el.classList.add("in"), 220 + delay);
  });

  /* -------------------- Stat counters -------------------- */
  function countUp(el, target, dur = 1400) {
    const start = performance.now();
    const from = 0;
    function frame(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      const v = Math.round(from + (target - from) * eased);
      el.textContent = v.toLocaleString("en-US");
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
  const counters = document.querySelectorAll("[data-target]");
  // Run hero counters immediately; data-target are <= 1000 so cheap
  counters.forEach(el => {
    const target = Number(el.dataset.target);
    if (Number.isFinite(target)) countUp(el, target);
  });

  /* -------------------- Reveal-on-scroll for section heads + reveals -------------------- */
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    }
  }, { threshold: 0.18 });
  document.querySelectorAll(".section-head, .reveal").forEach(el => io.observe(el));

  /* ====================================================================
     Results table
     ==================================================================== */
  const tbody = document.getElementById("resultsBody");
  const totalEl = document.getElementById("totalCount");
  const visEl = document.getElementById("visibleCount");

  const all = (D.candidates || []).slice();
  totalEl.textContent = all.length;

  // For score → bar-width visualization, normalize against max composite.
  const maxComp = Math.max(...all.map(c => c.composite));
  const minComp = Math.min(...all.map(c => c.composite));
  const compRange = Math.max(0.0001, maxComp - minComp);

  function phaseClass(phase) {
    const p = (phase || "").toLowerCase().replace(/\s+/g, "-");
    if (!p) return "";
    if (p === "launched") return "phase launched";
    if (p === "phase-3") return "phase phase-3";
    if (p === "phase-2") return "phase phase-2";
    if (p === "phase-1") return "phase phase-1";
    return "phase";
  }

  function trialClass(s) {
    if (!s) return "trial";
    if (s === "failed") return "trial failed";
    if (s === "approved") return "trial approved";
    return "trial " + s;
  }

  function row(c) {
    const tr = document.createElement("tr");
    tr.dataset.search = [
      c.name, c.moa, c.target, c.indication, c.phase, c.trial_status,
      (c.signatures || []).join(" "),
    ].join(" ").toLowerCase();

    tr.dataset.multi = c.n_sigs >= 2 ? "1" : "0";
    tr.dataset.hasphase = c.phase ? "1" : "0";
    tr.dataset.hasmoa = c.moa ? "1" : "0";

    const compNorm = (c.composite - minComp) / compRange;
    const barW = Math.max(4, Math.round(compNorm * 110)) + "px";

    tr.innerHTML = `
      <td class="num-col">
        <span class="composite-bar">
          <span class="bar" style="width:${barW}"></span>
          <span class="v">${c.composite.toFixed(3)}</span>
        </span>
      </td>
      <td class="num-col">${c.n_sigs}</td>
      <td class="num-col">${c.score_mean.toFixed(4)}</td>
      <td class="cand"><span class="glitch">${escapeHtml(c.name)}</span></td>
      <td><span class="${phaseClass(c.phase)}">${escapeHtml(c.phase || "—")}</span></td>
      <td class="moa-cell" title="${escapeHtml(c.moa || '')}">${escapeHtml(c.moa || "—")}</td>
      <td>${escapeHtml(c.target || "—")}</td>
      <td><span class="${trialClass(c.trial_status)}">${escapeHtml(c.trial_status || "—")}</span></td>
    `;
    return tr;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;",
      "\"": "&quot;", "'": "&#39;"
    }[c]));
  }

  let sortKey = "composite";
  let sortDir = "desc";
  let filterText = "";
  let filterMode = "all";

  function render() {
    const sorted = all.slice().sort((a, b) => {
      const va = a[sortKey], vb = b[sortKey];
      let cmp;
      if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
      else cmp = String(va || "").localeCompare(String(vb || ""));
      return sortDir === "asc" ? cmp : -cmp;
    });

    const frag = document.createDocumentFragment();
    let vis = 0;
    sorted.forEach((c, i) => {
      const tr = row(c);
      // Apply filters
      const txtMatch = !filterText || tr.dataset.search.includes(filterText);
      const modeMatch =
        filterMode === "all" ||
        (filterMode === "multi" && tr.dataset.multi === "1") ||
        (filterMode === "clinical" && tr.dataset.hasphase === "1") ||
        (filterMode === "moa" && tr.dataset.hasmoa === "1");
      if (!(txtMatch && modeMatch)) tr.style.display = "none";
      else vis++;
      frag.appendChild(tr);
    });
    tbody.replaceChildren(frag);

    // Trigger row reveal animation in waves
    const visibleRows = [...tbody.children].filter(tr => tr.style.display !== "none");
    visibleRows.forEach((tr, i) => {
      setTimeout(() => tr.classList.add("shown"), Math.min(i * 14, 800));
    });
    visEl.textContent = vis;
  }

  document.querySelectorAll("th.sortable").forEach(th => {
    th.addEventListener("click", () => {
      const k = th.dataset.sort;
      if (sortKey === k) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = k;
        sortDir = (k === "name" || k === "phase" || k === "moa" || k === "target") ? "asc" : "desc";
      }
      document.querySelectorAll("th.sortable").forEach(x => x.classList.remove("asc", "desc"));
      th.classList.add(sortDir);
      render();
    });
  });

  const filterInput = document.getElementById("filter");
  filterInput.addEventListener("input", (e) => {
    filterText = e.target.value.trim().toLowerCase();
    render();
  });

  document.querySelectorAll(".chip").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filterMode = btn.dataset.filter;
      render();
    });
  });

  // "/" focuses the filter; Esc clears it
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
      e.preventDefault();
      filterInput.focus();
      filterInput.select();
    } else if (e.key === "Escape" && document.activeElement === filterInput) {
      filterInput.value = "";
      filterText = "";
      render();
      filterInput.blur();
    }
  });

  render();

  /* ====================================================================
     Signature grid
     ==================================================================== */
  const sigGrid = document.getElementById("sigGrid");
  const labelMap = {
    FUS_KO: "FUS knockout",
    FUS_R495X: "FUS R495X",
    FUS_P525L_heteroz: "FUS P525L het.",
    FUS_P525L_homoz: "FUS P525L hom.",
    TARDBP_M337V: "TARDBP M337V",
    SHARED_MN: "Shared MN",
  };
  D.sigGenes.forEach(sig => {
    const isShared = sig.signature === "SHARED_MN";
    const sigStat = (D.sigStats || []).find(x => x.signature === sig.signature) || {};
    const top = sigStat.top || {};
    const card = document.createElement("div");
    card.className = "sig-card" + (isShared ? " shared" : "");
    card.innerHTML = `
      <h3>${labelMap[sig.signature] || sig.signature}${isShared ? '<span class="pill">consensus</span>' : ""}</h3>
      <div class="nums">
        <span><b>${sig.n_significant ?? "—"}</b> DEGs</span>
        <span><b>${sig.n_up}</b> up</span>
        <span><b>${sig.n_down}</b> down</span>
      </div>
      <div class="sig-top">
        ${top.name ? `“${escapeHtml(top.name)}”` : "—"}
        <small>top reversal · ${top.cell_line || "—"} · score ${top.score?.toFixed(4) || "—"}</small>
      </div>
      <div class="genes">
        <span class="lbl">UP</span>
        <span class="vals"><span class="up">${(sig.up_top10 || []).join(", ")}</span></span>
        <span class="lbl">DOWN</span>
        <span class="vals"><span class="down">${(sig.down_top10 || []).join(", ")}</span></span>
      </div>
    `;
    sigGrid.appendChild(card);
  });

  /* ====================================================================
     MoA bars (animates on intersect)
     ==================================================================== */
  const moaWrap = document.getElementById("moaBars");
  const moaMax = Math.max(1, ...D.moaTop.map(m => m.count));
  D.moaTop.forEach(m => {
    const row = document.createElement("div");
    row.className = "moa-row";
    row.innerHTML = `
      <div class="bar-wrap">
        <div class="bar" data-w="${(m.count / moaMax) * 100}%"></div>
        <div class="label">${escapeHtml(m.moa)}</div>
      </div>
      <div class="count">${m.count}</div>
    `;
    moaWrap.appendChild(row);
  });
  const moaIO = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        const bars = e.target.querySelectorAll(".bar");
        bars.forEach((b, i) => {
          setTimeout(() => { b.style.width = b.dataset.w; }, i * 60);
        });
        moaIO.unobserve(e.target);
      }
    });
  }, { threshold: 0.2 });
  moaIO.observe(moaWrap);

  /* -------------------- Build tag -------------------- */
  const buildTag = document.getElementById("buildTag");
  if (buildTag) buildTag.textContent = `v0.1.0 / ${D.generatedAt} / ${all.length} candidates`;

})();
