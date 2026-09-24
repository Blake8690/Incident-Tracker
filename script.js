const kommunList = document.getElementById("kommun-list");
KOMMUNER.forEach((k) => {
  const opt = document.createElement("option");
  opt.value = k;
  kommunList.appendChild(opt);
});

document.getElementById("theme-toggle").addEventListener("click", () => {
  document.body.classList.toggle("light");
});

const API_URL = "https://indicent-tracker-com.onrender.com";
const form = document.getElementById("form");
const status = document.getElementById("status");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("name").value.trim();
  const email = document.getElementById("email").value.trim().toLowerCase();
  const kommun = document.getElementById("area-search").value.trim();

  status.className = "";
  status.innerText = "";

  if (!KOMMUNER.includes(kommun)) {
    status.className = "error";
    status.innerText = "Välj en kommun från listan.";
    return;
  }

  try {
    const res = await fetch(`${API_URL}/api/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, kommun }),
    });
    const data = await res.json();
    if (!res.ok) {
      status.className = "error";
      status.innerText = data.error || "Något gick fel.";
      return;
    }
    status.className = "success";
    status.innerText = "✅ Du är registrerad!";
    form.reset();
  } catch {
    status.className = "error";
    status.innerText = "❌ Kunde inte nå servern.";
  }
});