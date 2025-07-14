const API_BASE = "http://localhost:6001/api"; 

async function loadLocations() {
  try {
    const res = await fetch(`${API_BASE}/get_location_names`);
    const data = await res.json();
    const sel = document.getElementById("location");
    sel.innerHTML = "";
    data.locations.forEach((loc) => {
      const opt = document.createElement("option");
      opt.value = loc;
      opt.textContent = loc;
      sel.appendChild(opt);
    });
  } catch (err) {
    console.error(err);
    alert("Failed to load locations");
  }
}

async function predict(e) {
  e.preventDefault();
  const form = e.target;
  const fd = new FormData();
  fd.append("total_sqft", document.getElementById("sqft").value);
  fd.append("location", document.getElementById("location").value);
  fd.append("bhk", document.getElementById("bhk").value);
  fd.append("bath", document.getElementById("bath").value);

  try {
    const res = await fetch(`${API_BASE}/predict_home_price`, {
      method: "POST",
      body: fd,
    });
    const data = await res.json();
    const resultDiv = document.getElementById("result");
    resultDiv.textContent = `Estimated price: ₹ ${data.estimated_price} lakhs`;
    resultDiv.classList.remove("d-none");
  } catch (err) {
    console.error(err);
    alert("Prediction failed");
  }
}

document.getElementById("predict-form").addEventListener("submit", predict);
loadLocations();
