// Reading taste page: shuffle the recommendations, and load the playlist only on request.
(function () {
  "use strict";

  // --- "What to read next": show a different random set, one book per genre.
  const list = document.getElementById("taste-picks");
  const shuffle = document.getElementById("picks-shuffle");
  if (list && shuffle) {
    const cards = Array.from(list.children);
    const count = Number(list.dataset.count) || 6;
    shuffle.addEventListener("click", () => {
      const order = cards.slice();
      for (let i = order.length - 1; i > 0; i--) {   // Fisher-Yates
        const j = Math.floor(Math.random() * (i + 1));
        [order[i], order[j]] = [order[j], order[i]];
      }
      const genres = new Set();
      const chosen = new Set();
      for (const card of order) {
        if (chosen.size === count) break;
        if (genres.has(card.dataset.genre)) continue;
        genres.add(card.dataset.genre);
        chosen.add(card);
      }
      cards.forEach((card) => { card.hidden = !chosen.has(card); });
      chosen.forEach((card) => list.appendChild(card));
    });
  }

  // --- Playlist: nothing loads until the play button is pressed; then it plays shuffled.
  const box = document.getElementById("taste-music");
  const button = document.getElementById("taste-play");
  const slot = document.getElementById("taste-embed");
  if (!box || !button || !slot) return;

  function start() {
    const target = document.createElement("div");
    slot.replaceChildren(target);
    slot.hidden = false;
    button.hidden = true;
    new YT.Player(target, {
      host: "https://www.youtube-nocookie.com",
      width: "100%",
      height: "352",
      playerVars: { listType: "playlist", list: box.dataset.playlist, autoplay: 1, rel: 0 },
      events: {
        onReady(e) {
          // Shuffle the playlist, then start from its first (now random) track.
          e.target.setShuffle(true);
          e.target.playVideoAt(0);
        },
      },
    });
  }

  button.addEventListener("click", () => {
    if (window.YT && YT.Player) return start();
    window.onYouTubeIframeAPIReady = start;
    const api = document.createElement("script");
    api.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(api);
  });
})();
