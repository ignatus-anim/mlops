const API_BASE = "http://localhost:7000/api"; 

let currentPredictionId = null;

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
    
    // Store prediction ID for feedback
    currentPredictionId = data.prediction_id;
    
    // Show result
    const resultDiv = document.getElementById("result");
    resultDiv.textContent = `Estimated price: ₹ ${data.estimated_price} lakhs`;
    resultDiv.classList.remove("d-none");
    
    // Show feedback section
    document.getElementById("feedback-section").classList.remove("d-none");
    
  } catch (err) {
    console.error(err);
    alert("Prediction failed");
  }
}

async function submitQuickFeedback(feedbackType) {
  if (!currentPredictionId) {
    alert("No prediction to provide feedback for");
    return;
  }
  
  try {
    const res = await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prediction_id: currentPredictionId,
        feedback_type: feedbackType
      })
    });
    
    if (res.ok) {
      showFeedbackSuccess("Thank you for your feedback!");
    } else {
      alert("Failed to submit feedback");
    }
  } catch (err) {
    console.error(err);
    alert("Failed to submit feedback");
  }
}

async function submitDetailedFeedback() {
  if (!currentPredictionId) {
    alert("No prediction to provide feedback for");
    return;
  }
  
  // Get rating
  const rating = document.querySelector('input[name="rating"]:checked');
  const comment = document.getElementById("feedback-comment").value;
  const actualPrice = document.getElementById("actual-price").value;
  
  if (!rating && !comment && !actualPrice) {
    alert("Please provide at least one type of feedback");
    return;
  }
  
  try {
    const payload = {
      prediction_id: currentPredictionId,
      feedback_type: "rating",
      feedback_text: comment
    };
    
    if (rating) {
      payload.feedback_value = parseInt(rating.value);
    } else if (actualPrice) {
      payload.feedback_type = "actual_price";
      payload.feedback_value = parseFloat(actualPrice);
    }
    
    const res = await fetch(`${API_BASE}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      showFeedbackSuccess("Thank you for your detailed feedback!");
      clearFeedbackForm();
    } else {
      alert("Failed to submit feedback");
    }
  } catch (err) {
    console.error(err);
    alert("Failed to submit feedback");
  }
}

function showFeedbackSuccess(message) {
  const feedbackSection = document.getElementById("feedback-section");
  feedbackSection.innerHTML = `
    <div class="alert alert-success text-center">
      <h5> ${message}</h5>
      <p>Your feedback helps us improve our predictions!</p>
    </div>
  `;
  
  // Hide after 3 seconds
  setTimeout(() => {
    feedbackSection.classList.add("d-none");
  }, 3000);
}

function clearFeedbackForm() {
  document.querySelectorAll('input[name="rating"]').forEach(r => r.checked = false);
  document.getElementById("feedback-comment").value = "";
  document.getElementById("actual-price").value = "";
}

document.getElementById("predict-form").addEventListener("submit", predict);
loadLocations();
