// --- Constants ---
const API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? 'http://localhost:5001/api' // Local development backend URL
    : '/api'; // Production backend URL (relative path)

// --- State Management ---
const storyData = {
    child_name: '',
    learning_objective: '',
    personality_keywords: [],
    story_theme: '',
    character_type: '',
    character_suggestions: [],
    selected_character_description: '',
    name_suggestions: [],
    selected_character_name: '',
    plot_suggestions: [],
    selected_plot: '',
    generated_story_text: '',
    generated_image_b64: null, // For final story image
    // --- Character Preview Image State ---
    generated_character_image_b64: null,
    characterImageState: 'idle', // 'idle', 'loading', 'success', 'error'
    characterImageError: null,
};

let currentStep = 1;
let isGenerating = false; // Tracks final story/image generation

// --- DOM Element References ---
const steps = document.querySelectorAll('.step');
const errorElements = { 1: document.getElementById('error-step-1'), 2: document.getElementById('error-step-2'), 3: document.getElementById('error-step-3'), 4: document.getElementById('error-step-4'), 5: document.getElementById('error-step-5'), 6: document.getElementById('error-step-6'), };
const nextButtons = { // Buttons that need explicit disabling/enabling after step 1
    2: document.getElementById('btn-step-2-next'),
    3: document.getElementById('btn-step-3-next'),
    4: document.getElementById('btn-step-4-next'),
};
const generateButton = document.getElementById('btn-generate-story');
const generationStatus = document.getElementById('generation-status');
// Story Image Elements (Step 6)
const imageContainer = document.getElementById('story-image-container');
const imageSpinner = document.getElementById('image-spinner');
const imageStatus = document.getElementById('image-status');
const storyImage = document.getElementById('story-image');
// Story Text Elements (Step 6)
const storyTextContainer = document.getElementById('story-text-container');
const storyTextStatus = document.getElementById('story-text-status');
const storyTextElement = document.getElementById('story-text');
// Character Preview Elements (Step 5)
const characterPreviewContainer = document.getElementById('character-image-preview-container');
const characterImageStatus = document.getElementById('character-image-status');
const characterImagePreview = document.getElementById('character-image-preview');
// HTML Element ID Mapping
const stepElementIds = { 1: 'step-1-basics', 2: 'step-2-character', 3: 'step-3-name', 4: 'step-4-plot', 5: 'step-5-review', 6: 'step-6-display' };

// --- Utility Functions (showError, clearError, clearAllErrors, postApi) ---
function showError(stepNum, message) {
    const errorEl = errorElements[stepNum];
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        errorEl.setAttribute('aria-hidden', 'false');
        // Don't scroll into view automatically for all errors, can be jarring
        // errorEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else { console.error(`Error element for step ${stepNum} not found.`); }
    console.error(`Error in Step ${stepNum}: ${message}`);
}
function clearError(stepNum) {
    const errorEl = errorElements[stepNum];
    if (errorEl) { errorEl.textContent = ''; errorEl.style.display = 'none'; errorEl.setAttribute('aria-hidden', 'true'); }
}
function clearAllErrors() {
    Object.keys(errorElements).forEach(stepNum => clearError(Number(stepNum))); // Ensure stepNum is number
}
async function postApi(endpoint, data = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    console.log(`POSTing to ${url}`); // Debug log
    try {
        const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Accept': 'application/json', }, body: JSON.stringify(data), });
        let responseData;
        try { responseData = await response.json(); } catch (e) { console.error("Failed to parse JSON response:", e); const responseText = await response.text(); console.error("Raw server response:", responseText); throw new Error(`Server returned non-JSON response (Status: ${response.status} ${response.statusText}). Check backend logs.`); }
        if (!response.ok) { const errorMessage = responseData?.error || `HTTP error! Status: ${response.status} ${response.statusText}`; console.error(`API Error (${url}):`, errorMessage, responseData); throw new Error(errorMessage); }
        console.log(`API Response OK from ${url}`); // Debug log
        return responseData;
    } catch (error) { console.error('Fetch Error:', error); throw new Error(error.message || 'Network error or failed to fetch.'); }
}

// --- Navigation & Step Logic (validateStep1, goToStep) ---
function validateStep1() {
    const name = document.getElementById('child-name').value.trim();
    const objective = document.getElementById('learning-objective').value.trim();
    const keywordsInput = document.getElementById('personality-keywords').value.trim();
    const theme = document.getElementById('story-theme').value.trim();
    const charType = document.getElementById('character-type').value.trim();
    clearError(1);
    if (!name || !objective || !keywordsInput || !theme || !charType) { showError(1, "Please fill out all fields before proceeding."); return false; }
    storyData.child_name = name; storyData.learning_objective = objective;
    // Ensure keywords are actually present after split/trim
    const keywordsArray = keywordsInput.split(',').map(k => k.trim()).filter(k => k !== '');
    if (keywordsArray.length === 0) { showError(1, "Please provide valid keywords for interests/personality (use commas to separate if needed)."); return false; }
    storyData.personality_keywords = keywordsArray;
    storyData.story_theme = theme; storyData.character_type = charType;
    return true;
}

function goToStep(targetStepNum) {
    console.log(`Attempting to go to step ${targetStepNum} from step ${currentStep}`); // Debug log
    // --- Validation before leaving current step ---
    if (currentStep === 1 && targetStepNum > 1 && !validateStep1()) return;
    if (currentStep === 2 && targetStepNum > 2 && !storyData.selected_character_description) { showError(2, "Please select a character description."); return; }
    if (currentStep === 3 && targetStepNum > 3 && !storyData.selected_character_name) { showError(3, "Please select a character name."); return; }
    if (currentStep === 4 && targetStepNum > 4 && !storyData.selected_plot) { showError(4, "Please select a plot idea."); return; }

    if (currentStep !== targetStepNum) { clearError(currentStep); } // Clear error only when moving away

    // Hide all steps
    steps.forEach(step => step.classList.remove('active'));

    const targetElementId = stepElementIds[targetStepNum];
    if (!targetElementId) { console.error(`No element ID defined for step number: ${targetStepNum}`); return; }
    const nextStepElement = document.getElementById(targetElementId);

    if (nextStepElement) {
        console.log(`Activating step element: ${targetElementId}`); // Debug log
        nextStepElement.classList.add('active');
        const previousStep = currentStep;
        currentStep = targetStepNum;
        try { // Add try/catch for potential scrollIntoView errors on hidden elements? (unlikely needed)
            nextStepElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (scrollError) { console.warn("ScrollIntoView failed:", scrollError); }

        // --- Trigger actions when ENTERING a specific step ---
        switch (currentStep) {
            case 2: if (previousStep < currentStep || storyData.character_suggestions.length === 0) fetchCharacterSuggestions(); break;
            case 3: if (previousStep < currentStep || storyData.name_suggestions.length === 0) fetchNameSuggestions(); break;
            case 4: if (previousStep < currentStep || storyData.plot_suggestions.length === 0) fetchPlotSuggestions(); break;
            case 5: updateReviewDetails(); break;
            case 6: displayFinalStory(); break;
        }
    } else {
        console.error(`Step element with ID '${targetElementId}' not found in HTML.`);
        showError(currentStep, `UI Error: Could not display step ${targetStepNum}. Required HTML element missing.`);
    }
}

// --- API Call & Data Handling Functions (fetchSuggestions) ---
function setSuggestionsLoading(type) {
    const container = document.getElementById(`${type}-suggestions`);
    if (container) container.innerHTML = `<p class="loading-message">Loading ${type} suggestions...</p>`;
    // Disable the NEXT button associated with the CURRENT step (where loading is shown)
    const nextButton = nextButtons[currentStep];
    if (nextButton) nextButton.disabled = true;
    clearError(currentStep);
}
async function fetchCharacterSuggestions() { setSuggestionsLoading('character'); try { const data = await postApi('/characters/suggest', { theme: storyData.story_theme, type: storyData.character_type, personality_keywords: storyData.personality_keywords }); storyData.character_suggestions = data.suggestions || []; displaySuggestions('character', storyData.character_suggestions); } catch (error) { showError(2, `Failed to load character suggestions: ${error.message}`); document.getElementById('character-suggestions').innerHTML = `<p class="error-message">Could not load suggestions. ${error.message}</p>`; } }
async function fetchNameSuggestions() { if (!storyData.selected_character_description) { showError(3, "Cannot fetch names without selecting a character first."); return; } setSuggestionsLoading('name'); try { const data = await postApi('/names/suggest', { character_description: storyData.selected_character_description, theme: storyData.story_theme }); storyData.name_suggestions = data.names || []; displaySuggestions('name', storyData.name_suggestions); } catch (error) { showError(3, `Failed to load name suggestions: ${error.message}`); document.getElementById('name-suggestions').innerHTML = `<p class="error-message">Could not load names. ${error.message}</p>`; } }
async function fetchPlotSuggestions() { if (!storyData.selected_character_description) { showError(4, "Cannot fetch plots without selecting a character first."); return; } setSuggestionsLoading('plot'); try { const data = await postApi('/plot/suggest', { learning_objective: storyData.learning_objective, character_description: storyData.selected_character_description, theme: storyData.story_theme }); storyData.plot_suggestions = data.plots || []; displaySuggestions('plot', storyData.plot_suggestions); } catch (error) { showError(4, `Failed to load plot suggestions: ${error.message}`); document.getElementById('plot-suggestions').innerHTML = `<p class="error-message">Could not load plots. ${error.message}</p>`; } }

// --- Background Character Image Generation ---
async function generateCharacterImageInBackground() {
    if (storyData.characterImageState === 'loading' || storyData.characterImageState === 'success') { console.log("Character image generation already running or completed."); return; }
    if (!storyData.selected_character_description || !storyData.selected_character_name) { console.log("Skipping character image generation - description or name missing."); storyData.characterImageState = 'idle'; return; }
    console.log("Starting background character image generation...");
    storyData.characterImageState = 'loading'; storyData.characterImageError = null;
    // Update preview status immediately if user is on step 5
    if (currentStep === 5) updateReviewDetails();
    const prompt = `Portrait of a character named ${storyData.selected_character_name}, who is ${storyData.selected_character_description}. Style: simple, colorful, friendly children's book illustration, white background.`;
    try {
        const imageResponse = await postApi('/image/generate', { description: prompt });
        if (imageResponse.image_b64_json) { console.log("Background character image generation successful."); storyData.generated_character_image_b64 = imageResponse.image_b64_json; storyData.characterImageState = 'success'; } else { throw new Error(imageResponse.error || "Received invalid image data from server."); }
    } catch (error) { console.error("Background character image generation failed:", error); storyData.characterImageState = 'error'; storyData.characterImageError = error.message || "Unknown error during generation."; storyData.generated_character_image_b64 = null; }
    // Update review section again when done, if user is currently on step 5
    if (currentStep === 5) updateReviewDetails();
}

// --- UI Update Functions (displaySuggestions, selectSuggestion, updateReviewDetails) ---
function displaySuggestions(type, suggestions) { const containerId = `${type}-suggestions`; const container = document.getElementById(containerId); const selectedValue = type === 'character' ? storyData.selected_character_description : type === 'name' ? storyData.selected_character_name : storyData.selected_plot; if (!container) { console.error(`Container element not found: ${containerId}`); return; } if (!suggestions || suggestions.length === 0 || (suggestions[0] && suggestions[0].startsWith("Error:"))) { let message = `<p class="error-message">Sorry, we couldn't generate ${type} suggestions right now.`; if (suggestions && suggestions[0]) { message = `<p class="error-message">${suggestions[0]}</p>`; if (!errorElements[currentStep]?.textContent) { showError(currentStep, suggestions[0]); } } else { message += ` Please try adjusting your inputs or try again later.</p>`; } container.innerHTML = message; return; } const list = document.createElement('ul'); list.className = 'suggestion-list'; list.id = `list-${type}`; list.setAttribute('role', 'listbox'); suggestions.forEach((suggestion) => { const listItem = document.createElement('li'); listItem.textContent = suggestion; listItem.dataset.value = suggestion; listItem.setAttribute('role', 'option'); listItem.setAttribute('tabindex', '0'); listItem.setAttribute('aria-selected', 'false'); if (suggestion === selectedValue) { listItem.classList.add('selected'); listItem.setAttribute('aria-selected', 'true'); } listItem.onclick = () => selectSuggestion(type, listItem, suggestion); listItem.onkeydown = (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectSuggestion(type, listItem, suggestion); } }; list.appendChild(listItem); }); container.innerHTML = ''; container.appendChild(list); const nextButton = nextButtons[currentStep]; if (selectedValue && nextButton) { nextButton.disabled = false; } }
function selectSuggestion(type, selectedListItem, value) { const listId = `list-${type}`; const list = document.getElementById(listId); if (list) { list.querySelectorAll('li').forEach(item => { item.classList.remove('selected'); item.setAttribute('aria-selected', 'false'); }); } selectedListItem.classList.add('selected'); selectedListItem.setAttribute('aria-selected', 'true'); const selectedTextElement = document.getElementById(`selected-${type}-text`); const nextButton = nextButtons[currentStep]; const truncate = (text, length = 60) => text.length > length ? text.substring(0, length) + "..." : text; const resetCharacterPreview = () => { storyData.characterImageState = 'idle'; storyData.generated_character_image_b64 = null; storyData.characterImageError = null; }; const resetName = () => { storyData.selected_character_name = ''; storyData.name_suggestions = []; document.getElementById('selected-name-text').textContent = 'None'; if(nextButtons[3]) nextButtons[3].disabled = true; resetCharacterPreview(); }; const resetPlot = () => { storyData.selected_plot = ''; storyData.plot_suggestions = []; document.getElementById('selected-plot-text').textContent = 'None'; if(nextButtons[4]) nextButtons[4].disabled = true; }; let valueChanged = false; switch (type) { case 'character': if (storyData.selected_character_description !== value) { storyData.selected_character_description = value; resetName(); resetPlot(); valueChanged = true; } selectedTextElement.textContent = truncate(value); break; case 'name': if (storyData.selected_character_name !== value) { storyData.selected_character_name = value; resetPlot(); resetCharacterPreview(); generateCharacterImageInBackground(); valueChanged = true; } selectedTextElement.textContent = value; break; case 'plot': if (storyData.selected_plot !== value) { storyData.selected_plot = value; valueChanged = true; } selectedTextElement.textContent = truncate(value); break; default: console.error("Unknown suggestion type:", type); return; } if (nextButton) nextButton.disabled = false; clearError(currentStep); }
function updateReviewDetails() { clearError(5); document.getElementById('review-child-name').textContent = storyData.child_name; document.getElementById('review-learning-objective').textContent = storyData.learning_objective; document.getElementById('review-character-description').textContent = storyData.selected_character_description; document.getElementById('review-character-name').textContent = storyData.selected_character_name; document.getElementById('review-plot').textContent = storyData.selected_plot; document.getElementById('review-theme').textContent = storyData.story_theme; document.getElementById('review-keywords').textContent = storyData.personality_keywords.join(', '); switch (storyData.characterImageState) { case 'success': if (storyData.generated_character_image_b64) { const dataUrl = `data:image/png;base64,${storyData.generated_character_image_b64}`; characterImagePreview.src = dataUrl; characterImagePreview.alt = `Preview of ${storyData.selected_character_name}`; characterImagePreview.style.display = 'block'; characterImageStatus.style.display = 'none'; characterImagePreview.onerror = () => { characterImageStatus.textContent = 'Error displaying preview image.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; } } else { characterImageStatus.textContent = 'Preview image data unavailable.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; } break; case 'loading': characterImageStatus.textContent = '⏳ Character preview generating...'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; case 'error': characterImageStatus.textContent = `❌ Could not generate character preview: ${storyData.characterImageError || 'Unknown error'}`; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; case 'idle': default: characterImageStatus.textContent = 'Preview will generate after name selection.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; } generationStatus.textContent = ''; generateButton.disabled = !(storyData.child_name && storyData.selected_character_description && storyData.selected_character_name && storyData.selected_plot); isGenerating = false; }

// --- Final Story/Image Generation and Display (generateStoryAndImage, displayFinalStory) ---
async function generateStoryAndImage() { if (isGenerating) return; isGenerating = true; clearError(5); generateButton.disabled = true; generationStatus.textContent = '✨ Generating final story text...'; storyTextElement.textContent = ''; storyTextStatus.textContent = 'Waiting for story...'; storyTextStatus.style.display = 'block'; storyImage.src = ''; storyImage.alt = ''; storyImage.style.display = 'none'; imageSpinner.style.display = 'none'; imageStatus.textContent = 'Waiting for final image...'; imageStatus.style.display = 'none'; try { const storyResponse = await postApi('/story/generate', { child_name: storyData.child_name, character_name: storyData.selected_character_name, character_description: storyData.selected_character_description, plot_choice: storyData.selected_plot, learning_objective: storyData.learning_objective, theme: storyData.story_theme, personality_keywords: storyData.personality_keywords }); storyData.generated_story_text = storyResponse.story_text; generationStatus.textContent = '✅ Story text generated! Generating final image...'; storyTextElement.textContent = storyData.generated_story_text; storyTextStatus.style.display = 'none'; } catch (error) { showError(5, `Story Generation Failed: ${error.message}`); generationStatus.textContent = '❌ Story generation failed.'; generateButton.disabled = false; isGenerating = false; storyTextStatus.textContent = 'Story generation failed.'; return; } const imagePrompt = `Children's book illustration depicting the story about ${storyData.selected_character_name}. Plot point: ${storyData.selected_plot.substring(0,100)}... Setting: ${storyData.story_theme}. Learning theme: ${storyData.learning_objective}. Style: simple, colorful, friendly.`; imageStatus.style.display = 'none'; imageSpinner.style.display = 'flex'; storyImage.style.display = 'none'; try { const imageResponse = await postApi('/image/generate', { description: imagePrompt }); if (imageResponse.image_b64_json) { storyData.generated_image_b64 = imageResponse.image_b64_json; generationStatus.textContent = '✅ Story and Final Image Generated Successfully!'; imageSpinner.style.display = 'none'; const dataUrl = `data:image/png;base64,${storyData.generated_image_b64}`; storyImage.src = dataUrl; storyImage.alt = `Illustration for the story about ${storyData.selected_character_name}`; if (imageResponse.revised_prompt) console.log("Revised prompt:", imageResponse.revised_prompt); storyImage.onload = () => { storyImage.style.display = 'block'; imageStatus.style.display = 'none'; imageSpinner.style.display = 'none'; }; storyImage.onerror = () => { console.error("Error loading base64 story image data."); imageSpinner.style.display = 'none'; imageStatus.textContent = '❌ Error displaying generated story image.'; imageStatus.style.display = 'block'; storyImage.style.display = 'none'; }; } else { throw new Error(imageResponse.error || "Received invalid image data from server."); } goToStep(6); } catch (error) { console.error("Final Image Generation Error:", error); const imageErrorMessage = `Final Image Generation Failed: ${error.message}`; showError(5, imageErrorMessage); generationStatus.textContent = '✅ Story generated, but final image failed.'; storyData.generated_image_b64 = null; imageSpinner.style.display = 'none'; imageStatus.textContent = `❌ ${imageErrorMessage}`; imageStatus.style.display = 'block'; storyImage.style.display = 'none'; goToStep(6); } finally { isGenerating = false; } }
function displayFinalStory() { clearError(6); document.getElementById('display-child-name').textContent = storyData.child_name; if (storyData.generated_story_text) { storyTextElement.textContent = storyData.generated_story_text; storyTextStatus.style.display = 'none'; } else { storyTextElement.textContent = ''; if (!storyTextStatus.textContent || storyTextStatus.textContent === 'Waiting for story...') { storyTextStatus.textContent = 'Story text is unavailable.'; } storyTextStatus.style.display = 'block'; } if (storyData.generated_image_b64) { const dataUrl = `data:image/png;base64,${storyData.generated_image_b64}`; if (storyImage.src !== dataUrl) { storyImage.src = dataUrl; storyImage.alt = `Illustration for the story about ${storyData.selected_character_name}`; } storyImage.onload = () => { storyImage.style.display = 'block'; imageStatus.style.display = 'none'; imageSpinner.style.display = 'none';}; storyImage.onerror = () => { console.error("Error loading base64 story image data in displayFinalStory."); imageStatus.textContent = '❌ Error displaying story image.'; imageStatus.style.display = 'block'; storyImage.style.display = 'none'; imageSpinner.style.display = 'none';}; if(storyImage.complete && storyImage.naturalWidth > 0) { storyImage.style.display = 'block'; imageStatus.style.display = 'none'; imageSpinner.style.display = 'none'; } else if (!storyImage.hasAttribute('onerror')) { /* Check if onerror was attached and failed */ if (!imageStatus.textContent || imageStatus.textContent === 'Waiting for final image...') { imageStatus.textContent = '⏳ Loading final image...'; } imageStatus.style.display = 'block'; storyImage.style.display = 'none'; imageSpinner.style.display = 'none'; } } else { storyImage.src = ''; storyImage.style.display = 'none'; imageSpinner.style.display = 'none'; if (!imageStatus.textContent || imageStatus.textContent === 'Waiting for final image...') { imageStatus.textContent = 'No final image was generated or generation failed.'; } imageStatus.style.display = 'block'; } }

// --- Reset Function ---
function startOver() { console.log("Starting over..."); Object.keys(storyData).forEach(key => { storyData[key] = Array.isArray(storyData[key]) ? [] : (key.includes('image_b64') ? null : (key === 'characterImageState' ? 'idle' : (key === 'characterImageError' ? null : ''))); }); document.getElementById('form-basics').reset(); ['character', 'name', 'plot'].forEach(type => { const suggestionsContainer = document.getElementById(`${type}-suggestions`); const selectedTextElement = document.getElementById(`selected-${type}-text`); if (suggestionsContainer) suggestionsContainer.innerHTML = ''; if (selectedTextElement) selectedTextElement.textContent = 'None'; }); document.getElementById('review-details').querySelectorAll('span').forEach(span => span.textContent = ''); storyTextElement.textContent = ''; storyTextStatus.textContent = 'Waiting for story...'; storyTextStatus.style.display = 'block'; storyImage.src = ''; storyImage.alt = ''; storyImage.style.display = 'none'; imageSpinner.style.display = 'none'; imageStatus.textContent = 'Waiting for final image...'; imageStatus.style.display = 'none'; generationStatus.textContent = ''; if(characterImageStatus) characterImageStatus.textContent = 'Preview will generate...'; characterImageStatus.style.display = 'none'; // Initially hide status text
if(characterImagePreview) { characterImagePreview.src = ''; characterImagePreview.style.display = 'none'; } clearAllErrors(); Object.values(nextButtons).forEach(btn => { if(btn) btn.disabled = true; }); generateButton.disabled = true; isGenerating = false; goToStep(1); }

// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => { fetch(`${API_BASE_URL}/health`).then(response => response.ok ? response.json() : Promise.reject(`Health check failed: ${response.status}`)).then(data => console.log("API Health:", data)).catch(err => console.warn("API Health check warning:", err)); startOver(); });