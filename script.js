const API_URL = "https://incident-tracker-api.onrender.com";
const kommunList = document.getElementById("kommun-list");
KOMMUNER.forEach((k) => {
  const opt = document.createElement("option");
  opt.value = k;
  kommunList.appendChild(opt);
});

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

  const button = form.querySelector("button");
  button.disabled = true;
  button.innerText = "Registrerar…";

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
    status.innerText = "✅ Du är registrerad! Du får e-post när något nytt rapporteras i din kommun.";
    form.reset();
  } catch (err) {
    console.error(err);
    status.className = "error";
    status.innerText = "❌ Kunde inte nå servern. Försök igen om en stund.";
  } finally {
    button.disabled = false;
    button.innerText = "Aktivera bevakning";
  }
});
