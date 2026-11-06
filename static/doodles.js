// Doodles page: click a picture to see it large in a <dialog>.
(function () {
  "use strict";
  const box = document.getElementById("doodle-lightbox");
  if (!box) return;
  const big = box.querySelector("img");
  document.querySelectorAll("a.doodle").forEach((a) => a.addEventListener("click", (e) => {
    e.preventDefault();
    big.src = a.href;
    big.alt = a.querySelector("img").alt;
    box.showModal();
  }));
  // Click anywhere (backdrop, picture or ×) closes it.
  box.addEventListener("click", () => box.close());
})();
