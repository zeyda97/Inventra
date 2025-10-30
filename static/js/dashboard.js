document.addEventListener("DOMContentLoaded", () => {
  const marqueSections = Array.from(document.querySelectorAll(".marque-section"));
  const brandFilter = document.getElementById("brandFilter");
  const searchInput = document.getElementById("searchInput");

  const rowsPerPage = 1;
  let currentPage = 1;
  let filteredSections = [...marqueSections];

  const prevBtn = document.getElementById("prevPage");
  const nextBtn = document.getElementById("nextPage");
  const pageInfo = document.getElementById("pageInfo");

function renderPage() {
  const start = (currentPage - 1) * rowsPerPage;
  const end = start + rowsPerPage;
  const totalPages = Math.ceil(filteredSections.length / rowsPerPage) || 1;

  // 🔄 Masquer les sections existantes avec effet de fade
  marqueSections.forEach(section => {
    section.classList.remove("fade-in");
    section.classList.add("fade-out");
    setTimeout(() => {
      section.style.display = "none";
    }, 200);
  });

  // 🎬 Afficher les nouvelles sections avec un petit décalage
  const visibleSections = filteredSections.slice(start, end);
  setTimeout(() => {
    visibleSections.forEach((section, i) => {
      section.style.display = "";
      setTimeout(() => {
        section.classList.remove("fade-out");
        section.classList.add("fade-in");
      }, i * 100);
    });
  }, 200);

  // ⚙️ Pagination
  pageInfo.textContent = `Page ${currentPage} / ${totalPages}`;
  prevBtn.disabled = currentPage === 1;
  nextBtn.disabled = currentPage === totalPages;
}

  // 🔍 Recherche
  searchInput.addEventListener("input", e => {
    const term = e.target.value.toLowerCase();
    filteredSections = marqueSections.filter(section => {
      const marque = section.dataset.marque.toLowerCase();
      const products = Array.from(section.querySelectorAll(".product-row"));
      let visible = false;

      products.forEach(row => {
        const match = row.textContent.toLowerCase().includes(term);
        row.style.display = match ? "" : "none";
        if (match) visible = true;
      });

      return visible || marque.includes(term);
    });
    currentPage = 1;
    renderPage();
  });

  // 🏷️ Filtre
  brandFilter.addEventListener("change", e => {
    const selected = e.target.value.toLowerCase();
    if (!selected) filteredSections = [...marqueSections];
    else filteredSections = marqueSections.filter(section => section.dataset.marque.toLowerCase() === selected);
    currentPage = 1;
    renderPage();
  });

  prevBtn.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage--;
      renderPage();
    }
  });
  nextBtn.addEventListener("click", () => {
    if (currentPage < Math.ceil(filteredSections.length / rowsPerPage)) {
      currentPage++;
      renderPage();
    }
  });

  renderPage();
});
