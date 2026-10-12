// Maude's Library — page behaviour.
//
// Python (build.py) already rendered every book and every year's statistics
// into the HTML. This script only SHOWS, HIDES and RE-ORDERS what's there:
//   - year switcher       -> show the chosen year's cards and books
//   - search / genre      -> hide books that don't match
//   - sort                -> re-order books using rank numbers from stats.py
//   - List / Cards        -> show one of the two views (remembered in localStorage)
//   - "More"              -> appears only when some text is cut off; opens a pop-up

(function () {
  "use strict";

  // Short helpers: $ finds one element, $$ finds many (as a real array).
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const yearSelect = $("#year-select");
  if (!yearSelect) return; // no books at all

  const searchInput = $("#search");
  const genreSelect = $("#genre-filter");
  const sortSelect = $("#sort");
  const highButton = $("#high-only"); // "80%+" toggle
  const views = { list: $("#view-list"), cards: $("#view-cards") };
  const containers = { list: $("#view-list .table-body"), cards: $("#view-cards") };

  // ---------------------------------------------------------------------------
  // Saving the List / Cards choice. localStorage can be unavailable (private
  // browsing), so every access is wrapped in try/catch.
  // ---------------------------------------------------------------------------
  const VIEW_KEY = "maudes-library:view";
  function loadView() {
    try { return localStorage.getItem(VIEW_KEY) === "cards" ? "cards" : "list"; }
    catch (e) { return "list"; }
  }
  function saveView(view) {
    try { localStorage.setItem(VIEW_KEY, view); } catch (e) { /* ignore */ }
  }

  let currentView = loadView();

  // ---------------------------------------------------------------------------
  // Apply year + search + genre + sort to both views
  // ---------------------------------------------------------------------------
  function update() {
    const year = yearSelect.value;                 // "2026" … or "all"
    const allYears = year === "all";
    const yearLabel = yearSelect.selectedOptions[0].dataset.label; // "2026" or "All years"
    const query = searchInput.value.trim().toLowerCase();
    const queryDigits = query.replace(/[-\s]/g, ""); // so "978-0-14..." finds an ISBN
    const genre = genreSelect.value;
    const highOnly = highButton.getAttribute("aria-pressed") === "true";
    const sortKey = "rank" + sortSelect.value[0].toUpperCase() + sortSelect.value.slice(1); // "rankTitle"

    // 1. Statistics cards: show only the chosen period's.
    $$(".year-part").forEach((el) => { el.hidden = el.dataset.year !== year; });
    $$(".hide-on-all").forEach((el) => { el.hidden = allYears; });
    $$("[data-year-label]").forEach((el) => { el.textContent = yearLabel; });

    // 2. Books: decide which are visible, in both views.
    let inYear = 0;
    let shown = 0;
    for (const view of ["list", "cards"]) {
      const items = $$(".book-item", containers[view]);

      // Re-order by the rank Python computed (smaller number = earlier).
      items.sort((a, b) => Number(a.dataset[sortKey]) - Number(b.dataset[sortKey]));
      items.forEach((el) => containers[view].appendChild(el));

      for (const el of items) {
        const matchesYear = allYears || el.dataset.year === year;
        const matchesGenre = !genre || el.dataset.genre === genre;
        const matchesHigh = !highOnly || el.dataset.high === "1"; // flag set by Python
        const text = el.dataset.search;
        const matchesSearch = !query || text.includes(query) ||
          (queryDigits.length > 3 && text.replace(/[-\s]/g, "").includes(queryDigits));
        el.hidden = !(matchesYear && matchesGenre && matchesHigh && matchesSearch);

        if (view === "list") {
          if (matchesYear) inYear += 1;
          if (!el.hidden) {
            shown += 1;
            $(".c-num", el).textContent = shown; // row number: 1, 2, 3… in current order
          }
        }
      }
    }

    // 3. Counters and the "no results" message.
    const plural = (n) => n + (n === 1 ? " book" : " books");
    const forWhat = allYears ? " across all years" : " for " + year;
    $("#shelf-count").textContent = plural(inYear);
    $("#showing").textContent = shown === inYear
      ? "Showing " + plural(inYear) + forWhat
      : "Showing " + shown + " of " + plural(inYear) + forWhat;
    $("#no-results").hidden = shown > 0;

    // 4. Show the chosen view.
    for (const [name, el] of Object.entries(views)) el.hidden = name !== currentView;
    $$(".view-toggle button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === currentView)));

    refreshMoreButtons();
  }

  // ---------------------------------------------------------------------------
  // "More" buttons: visible only if some clamped text in that book is cut off.
  // A cut-off element is taller (or wider, for one-line text) inside than out.
  // ---------------------------------------------------------------------------
  function isTruncated(el) {
    return el.scrollHeight > el.clientHeight + 1 || el.scrollWidth > el.clientWidth + 1;
  }

  function refreshMoreButtons() {
    const view = views[currentView];
    $$(".book-item", view).forEach((item) => {
      if (item.hidden) return; // hidden items have no size; checked again when shown
      const cut = $$(".clamp", item).some(isTruncated);
      $(".more", item).hidden = !cut;
    });
  }

  // Re-check after the window is resized (text may wrap differently).
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(refreshMoreButtons, 150);
  });
  // Web fonts change text width, so re-check once they've loaded.
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(refreshMoreButtons);

  // ---------------------------------------------------------------------------
  // Pop-up (uses the built-in <dialog> element)
  // ---------------------------------------------------------------------------
  const modal = $("#book-modal");
  const modalBody = $(".modal-body", modal);
  let opener = null; // the "More" button that opened the pop-up

  function openModal(bookId, button) {
    const tpl = document.getElementById("detail-" + bookId);
    if (!tpl) return;
    opener = button;
    modalBody.replaceChildren(tpl.content.cloneNode(true));
    modalBody.scrollTop = 0;
    document.documentElement.classList.add("modal-open"); // lock page scroll
    modal.showModal();
    $(".modal-close", modal).focus();
  }

  function closeModal() {
    if (modal.open) modal.close();
  }

  // Runs however the dialog closes (× button, Esc, or backdrop click).
  modal.addEventListener("close", () => {
    document.documentElement.classList.remove("modal-open");
    if (opener) opener.focus(); // return focus to the "More" button
    opener = null;
  });

  $(".modal-close", modal).addEventListener("click", closeModal);

  // A click on the dialog element itself (not its panel) is a backdrop click.
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });

  // Keep Tab / Shift+Tab inside the pop-up.
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const focusable = $$("button, [href], input, select, [tabindex]:not([tabindex='-1'])", modal)
      .filter((el) => !el.hidden && !el.disabled);
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  // One listener for every "More" button on the page.
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".more");
    if (btn) openModal(btn.dataset.more, btn);
  });

  // ---------------------------------------------------------------------------
  // Wire up the controls
  // ---------------------------------------------------------------------------
  yearSelect.addEventListener("change", update);
  genreSelect.addEventListener("change", update);
  sortSelect.addEventListener("change", update);
  searchInput.addEventListener("input", update);
  highButton.addEventListener("click", () => {
    const on = highButton.getAttribute("aria-pressed") === "true";
    highButton.setAttribute("aria-pressed", String(!on));
    update();
  });
  $$(".view-toggle button").forEach((b) => b.addEventListener("click", () => {
    currentView = b.dataset.view;
    saveView(currentView);
    update();
  }));

  update();
})();
