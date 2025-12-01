// ✅ Variables globales
let marqueSections = [];
let filteredSections = [];
let currentPage = 1;
const rowsPerPage = 1;

// ✅ Fonction d'initialisation du dashboard (votre code original)
function initializeDashboard() {
  marqueSections = Array.from(document.querySelectorAll(".marque-section"));
  const brandFilter = document.getElementById("brandFilter");
  const searchInput = document.getElementById("searchInput");

  filteredSections = [...marqueSections];

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
}

// ✅ Fonction de chargement dynamique des données
async function loadDashboardData() {
  try {
    console.log('🔄 Chargement des données...');
    
    const response = await fetch('/report');
    
    if (!response.ok) {
      throw new Error(`Erreur HTTP: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('✅ Données chargées:', data.length, 'marques');
    
    // Afficher l'heure de mise à jour
    const now = new Date();
    document.getElementById('last-update').textContent = 
      now.toLocaleString('fr-CA', { 
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    
    // Remplir le filtre des marques
    const brandFilter = document.getElementById('brandFilter');
    brandFilter.innerHTML = '<option value="">Marque</option>';
    data.forEach(marque => {
      const option = document.createElement('option');
      option.value = marque.Marque;
      option.textContent = marque.Marque;
      brandFilter.appendChild(option);
    });
    
    // Générer le HTML du dashboard
    const container = document.getElementById('dashboard-container');
    container.innerHTML = data.map(marque => `
      <div class="marque-section" data-marque="${marque.Marque}">
        <div class="marque-header">${marque.Marque}</div>
        
        <table class="table">
          <tbody>
            <tr class="totaux-row">
              <td class="totaux-label">💰 TOTAUX (Net Sales)</td>
              <td class="totaux-value">${Math.round(marque.Totaux["Valeur Stock Total ($)"]).toLocaleString('fr-CA')} $</td>
              <td class="totaux-value">${Math.round(marque.Totaux["Montant V60 Total ($)"]).toLocaleString('fr-CA')} $</td>
              <td class="totaux-value">${Math.round(marque.Totaux["Montant V120 Total ($)"]).toLocaleString('fr-CA')} $</td>
              <td class="totaux-value">${Math.round(marque.Totaux["Montant V180 Total ($)"]).toLocaleString('fr-CA')} $</td>
              <td class="totaux-value">${Math.round(marque.Totaux["Montant V365 Total ($)"]).toLocaleString('fr-CA')} $</td>
              <td></td>
              <td></td>
            </tr>
          </tbody>
          
          <thead>
            <tr>
              <th>Produit</th>
              <th>Stock</th>
              <th>V60</th>
              <th>V120</th>
              <th>V180</th>
              <th>V365</th>
              <th>Suggestion (3m)</th>
              <th>Alerte</th>
            </tr>
          </thead>
          
          <tbody>
            ${marque.Produits.map(p => `
              <tr class="product-row">
                <td>${p.Produit}</td>
                <td class="${p.Stock === 0 ? 'stock-zero' : p.Stock < 5 ? 'stock-faible' : ''}">
                  ${p.Stock}
                </td>
                <td>${p.V60}</td>
                <td>${p.V120}</td>
                <td>${p.V180}</td>
                <td>${p.V365}</td>
                <td>${p["Suggestion (3m)"]}</td>
                <td>
                  <span class="${p.Alerte.includes('OK') ? 'alerte-ok' : 'alerte-rupture'}">
                    ${p.Alerte}
                  </span>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `).join('');
    
    // Masquer le loading, afficher le contenu
    document.getElementById('loading').style.display = 'none';
    document.getElementById('main-content').style.display = 'block';
    
    // ✅ Appeler la fonction d'initialisation
    initializeDashboard();
    
    console.log('✅ Dashboard affiché avec succès');
    
  } catch (error) {
    console.error('❌ Erreur de chargement:', error);
    document.getElementById('loading').innerHTML = `
      <div class="text-center">
        <p class="text-red-600 text-xl font-bold mb-4">❌ Erreur de chargement des données</p>
        <p class="text-gray-600 mb-4">${error.message}</p>
        <button 
          onclick="location.reload()" 
          class="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg shadow-md transition"
        >
          🔄 Réessayer
        </button>
      </div>
    `;
  }
}

// ✅ Démarrage au chargement de la page
window.addEventListener('DOMContentLoaded', loadDashboardData);
