// --- Constants ---
const API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
    ? 'http://localhost:5001/api'
    : '/api';

// --- State Management ---
const storyData = {
    child_name: '', learning_objective: '', personality_keywords: [], story_theme: '', character_type: '',
    character_suggestions: [], selected_character_description: '', name_suggestions: [], selected_character_name: '',
    plot_suggestions: [], selected_plot: '',
    // Character Preview State
    generated_character_image_b64: null, characterImageState: 'idle', characterImageError: null,
    // Final Book State
    bookPages: [], // Array of {text: string, image_b64: string}
    currentPageIndex: 0,
    // Removed single story/image state: generated_story_text, generated_image_b64
};

let currentStep = 1;
let isGeneratingBook = false; // Tracks multi-step book generation

// --- DOM Element References ---
const steps = document.querySelectorAll('.step');
const errorElements = { 1: document.getElementById('error-step-1'), 2: document.getElementById('error-step-2'), 3: document.getElementById('error-step-3'), 4: document.getElementById('error-step-4'), 5: document.getElementById('error-step-5'), 6: document.getElementById('error-step-6'), };
const nextButtons = { 2: document.getElementById('btn-step-2-next'), 3: document.getElementById('btn-step-3-next'), 4: document.getElementById('btn-step-4-next'), };
const generateBookButton = document.getElementById('btn-generate-book'); // Updated ID reference
const generationStatus = document.getElementById('generation-status'); // May be less used now
// Step 5 Loading Overlay
const bookLoadingOverlay = document.getElementById('book-loading-overlay');
const bookLoadingStatus = document.getElementById('book-loading-status');
const bookLoadingDetail = document.getElementById('book-loading-detail'); // For future detailed status
// Step 5 Review Content Wrapper (to hide during loading)
const reviewContent = document.getElementById('review-content');
// Character Preview Elements (Step 5)
const characterPreviewContainer = document.getElementById('character-image-preview-container');
const characterImageStatus = document.getElementById('character-image-status');
const characterImagePreview = document.getElementById('character-image-preview');
// Book View Elements (Step 6)
const bookView = document.getElementById('book-view');
const bookImageContainer = document.getElementById('book-image-container');
const bookImage = document.getElementById('book-image');
const bookImageSpinner = document.getElementById('book-image-spinner');
const bookTextContainer = document.getElementById('book-text-container');
const bookText = document.getElementById('book-text');
const bookNav = document.getElementById('book-navigation');
const bookPrevButton = document.getElementById('book-prev-button');
const bookNextButton = document.getElementById('book-next-button');
const bookPageIndicator = document.getElementById('book-page-indicator');
const displayChildNameBook = document.getElementById('display-child-name-book'); // For Step 6 title
// HTML Element ID Mapping
const stepElementIds = { 1: 'step-1-basics', 2: 'step-2-character', 3: 'step-3-name', 4: 'step-4-plot', 5: 'step-5-review', 6: 'step-6-display' };

// --- Utility Functions (showError, clearError, clearAllErrors, postApi - unchanged) ---
function showError(stepNum, message) { const errorEl = errorElements[stepNum]; if (errorEl) { errorEl.textContent = message; errorEl.style.display = 'block'; errorEl.setAttribute('aria-hidden', 'false'); } else { console.error(`Error element for step ${stepNum} not found.`); } console.error(`Error in Step ${stepNum}: ${message}`); }
function clearError(stepNum) { const errorEl = errorElements[stepNum]; if (errorEl) { errorEl.textContent = ''; errorEl.style.display = 'none'; errorEl.setAttribute('aria-hidden', 'true'); } }
function clearAllErrors() { Object.keys(errorElements).forEach(stepNum => clearError(Number(stepNum))); }
async function postApi(endpoint, data = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    console.log(`POSTing to ${url}`);
    let response; // Declare response outside try to access status in catch
    try {
        response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify(data),
        });

        // Try to read the body ONCE. If response is not OK, we'll parse text later.
        // If response IS OK, but body is not JSON, json() will throw.
        const responseData = await response.json();

        // If response.json() succeeded but status is somehow not ok (unlikely but possible)
        if (!response.ok) {
             // We already have parsed JSON (responseData usually contains {'error': ...})
             const errorMessage = responseData?.error || `HTTP error! Status: ${response.status} ${response.statusText}`;
             console.error(`API Error (${url}) after parsing JSON:`, errorMessage, responseData);
             throw new Error(errorMessage);
        }

        console.log(`API Response OK from ${url}`);
        return responseData; // Success path

    } catch (error) {
        // Catch network errors OR errors from response.json() OR errors thrown for !response.ok
        console.error(`Workspace/Processing Error for ${url}:`, error);

        // If we have a response object (meaning fetch itself didn't fail)
        // and the error was likely from response.json() failing
        if (response && error instanceof SyntaxError) {
             console.log("Response was not valid JSON. Reading as text...");
             // Read the body as text (this is the *first* successful read)
             const errorText = await response.text(); // Read body ONCE as text
             console.error("Raw non-JSON response body:", errorText);
              // Throw a new error indicating non-JSON response
             throw new Error(`Server returned non-JSON response (Status: ${response.status}). Check backend logs.`);
        } else if (response && !response.ok) {
            // Error was likely thrown because status was not ok, but we might not have read the body yet
            // Or maybe the error object already has the message we need from the initial check.
            // Re-throw the original error message which might be more specific.
             throw new Error(error.message || `API call failed with status ${response.status}.`);
        }

        // Otherwise (e.g., network error before getting response), re-throw original error
        throw new Error(error.message || 'API call failed or network error.');
    }
}

// --- Navigation & Step Logic (validateStep1, goToStep - unchanged) ---
function validateStep1() { const name = document.getElementById('child-name').value.trim(); const objective = document.getElementById('learning-objective').value.trim(); const keywordsInput = document.getElementById('personality-keywords').value.trim(); const theme = document.getElementById('story-theme').value.trim(); const charType = document.getElementById('character-type').value.trim(); clearError(1); if (!name || !objective || !keywordsInput || !theme || !charType) { showError(1, "Please fill out all fields before proceeding."); return false; } storyData.child_name = name; storyData.learning_objective = objective; const keywordsArray = keywordsInput.split(',').map(k => k.trim()).filter(k => k !== ''); if (keywordsArray.length === 0) { showError(1, "Please provide valid keywords for interests/personality."); return false; } storyData.personality_keywords = keywordsArray; storyData.story_theme = theme; storyData.character_type = charType; return true; }
function goToStep(targetStepNum) { console.log(`Attempting to go to step ${targetStepNum} from step ${currentStep}`); if (currentStep === 1 && targetStepNum > 1 && !validateStep1()) return; if (currentStep === 2 && targetStepNum > 2 && !storyData.selected_character_description) { showError(2, "Please select a character description."); return; } if (currentStep === 3 && targetStepNum > 3 && !storyData.selected_character_name) { showError(3, "Please select a character name."); return; } if (currentStep === 4 && targetStepNum > 4 && !storyData.selected_plot) { showError(4, "Please select a plot idea."); return; } if (currentStep !== targetStepNum) { clearError(currentStep); } steps.forEach(step => step.classList.remove('active')); const targetElementId = stepElementIds[targetStepNum]; if (!targetElementId) { console.error(`No element ID defined for step number: ${targetStepNum}`); return; } const nextStepElement = document.getElementById(targetElementId); if (nextStepElement) { console.log(`Activating step element: ${targetElementId}`); nextStepElement.classList.add('active'); const previousStep = currentStep; currentStep = targetStepNum; try { nextStepElement.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (scrollError) { console.warn("ScrollIntoView failed:", scrollError); } switch (currentStep) { case 2: if (previousStep < currentStep || storyData.character_suggestions.length === 0) fetchCharacterSuggestions(); break; case 3: if (previousStep < currentStep || storyData.name_suggestions.length === 0) fetchNameSuggestions(); break; case 4: if (previousStep < currentStep || storyData.plot_suggestions.length === 0) fetchPlotSuggestions(); break; case 5: updateReviewDetails(); break; case 6: displayCurrentPage(); break; /* Changed from displayFinalStory */ } } else { console.error(`Step element with ID '${targetElementId}' not found in HTML.`); showError(currentStep, `UI Error: Could not display step ${targetStepNum}.`); } }


// --- API Call & Data Handling Functions (fetchSuggestions - unchanged) ---
function setSuggestionsLoading(type) { const container = document.getElementById(`${type}-suggestions`); if (container) container.innerHTML = `<p class="loading-message">Loading ${type} suggestions...</p>`; const nextButton = nextButtons[currentStep]; if (nextButton) nextButton.disabled = true; clearError(currentStep); }
async function fetchCharacterSuggestions() { setSuggestionsLoading('character'); try { const data = await postApi('/characters/suggest', { theme: storyData.story_theme, type: storyData.character_type, personality_keywords: storyData.personality_keywords }); storyData.character_suggestions = data.suggestions || []; displaySuggestions('character', storyData.character_suggestions); } catch (error) { showError(2, `Failed to load character suggestions: ${error.message}`); document.getElementById('character-suggestions').innerHTML = `<p class="error-message">Could not load suggestions. ${error.message}</p>`; } }
async function fetchNameSuggestions() { if (!storyData.selected_character_description) { showError(3, "Cannot fetch names without selecting a character first."); return; } setSuggestionsLoading('name'); try { const data = await postApi('/names/suggest', { character_description: storyData.selected_character_description, theme: storyData.story_theme }); storyData.name_suggestions = data.names || []; displaySuggestions('name', storyData.name_suggestions); } catch (error) { showError(3, `Failed to load name suggestions: ${error.message}`); document.getElementById('name-suggestions').innerHTML = `<p class="error-message">Could not load names. ${error.message}</p>`; } }
async function fetchPlotSuggestions() { if (!storyData.selected_character_description) { showError(4, "Cannot fetch plots without selecting a character first."); return; } setSuggestionsLoading('plot'); try { const data = await postApi('/plot/suggest', { learning_objective: storyData.learning_objective, character_description: storyData.selected_character_description, theme: storyData.story_theme }); storyData.plot_suggestions = data.plots || []; displaySuggestions('plot', storyData.plot_suggestions); } catch (error) { showError(4, `Failed to load plot suggestions: ${error.message}`); document.getElementById('plot-suggestions').innerHTML = `<p class="error-message">Could not load plots. ${error.message}</p>`; } }

// --- Background Character Image Generation (Unchanged from previous version) ---
async function generateCharacterImageInBackground() {
    if (storyData.characterImageState === 'loading' || storyData.characterImageState === 'success') { console.log("Character image gen running/completed."); return; }
    if (!storyData.selected_character_description || !storyData.selected_character_name) { console.log("Skipping char image gen - data missing."); storyData.characterImageState = 'idle'; if (currentStep === 5) updateReviewDetails(); return; }
    console.log("Starting background character image generation...");
    storyData.characterImageState = 'loading'; storyData.characterImageError = null;
    if (currentStep === 5) updateReviewDetails();
    const prompt = `Portrait of a character named ${storyData.selected_character_name}, who is ${storyData.selected_character_description}. Style: simple, colorful, friendly children's book illustration, white background.`;
    try {
        const imageResponse = await postApi('/image/generate', { description: prompt });
        console.log('Backend response for character image raw:', imageResponse);
        console.log('Backend response for character image (stringified):', JSON.stringify(imageResponse, null, 2));

        // *** CORRECTED CHECK: Use b64_json key ***
        if (imageResponse &&
            imageResponse.b64_json && // Use correct key
            typeof imageResponse.b64_json === 'string' &&
            imageResponse.b64_json.length > 10) {

             console.log("Background character image generation successful (data validated).");
             // *** CORRECTED STORAGE: Use correct key from response ***
             storyData.generated_character_image_b64 = imageResponse.b64_json;
             storyData.characterImageState = 'success';
        } else {
             console.error('Data validation failed! Invalid image data received from backend. Response object:', imageResponse);
             let specificError = "Received invalid image data structure from server.";
             if (imageResponse && imageResponse.hasOwnProperty('b64_json')) { // Check correct key here too
                 specificError = "Received empty, null, or non-string image data from server."
             } else if (imageResponse && imageResponse.error) {
                 specificError = `Server explicitly returned error: ${imageResponse.error}`
             }
             throw new Error(specificError);
        }
    } catch (error) {
        console.error("Caught error during background character image generation:", error);
        storyData.characterImageState = 'error';
        storyData.characterImageError = error.message || "Unknown error during generation.";
        storyData.generated_character_image_b64 = null;
    } finally {
         if (currentStep === 5) { console.log("Updating review details after background generation attempt."); updateReviewDetails(); }
    }
}


// --- UI Update Functions (displaySuggestions, selectSuggestion, updateReviewDetails - Unchanged from previous) ---
function displaySuggestions(type, suggestions) { const containerId = `${type}-suggestions`; const container = document.getElementById(containerId); const selectedValue = type === 'character' ? storyData.selected_character_description : type === 'name' ? storyData.selected_character_name : storyData.selected_plot; if (!container) { console.error(`Container not found: ${containerId}`); return; } if (!suggestions || suggestions.length === 0 || (suggestions[0] && suggestions[0].startsWith("Error:"))) { let message = `<p class="error-message">Could not generate ${type} suggestions.`; if (suggestions && suggestions[0]) { message = `<p class="error-message">${suggestions[0]}</p>`; if (!errorElements[currentStep]?.textContent) { showError(currentStep, suggestions[0]); } } else { message += ` Please try different inputs.</p>`; } container.innerHTML = message; return; } const list = document.createElement('ul'); list.className = 'suggestion-list'; list.id = `list-${type}`; list.setAttribute('role', 'listbox'); suggestions.forEach((suggestion) => { const listItem = document.createElement('li'); listItem.textContent = suggestion; listItem.dataset.value = suggestion; listItem.setAttribute('role', 'option'); listItem.setAttribute('tabindex', '0'); listItem.setAttribute('aria-selected', 'false'); if (suggestion === selectedValue) { listItem.classList.add('selected'); listItem.setAttribute('aria-selected', 'true'); } listItem.onclick = () => selectSuggestion(type, listItem, suggestion); listItem.onkeydown = (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectSuggestion(type, listItem, suggestion); } }; list.appendChild(listItem); }); container.innerHTML = ''; container.appendChild(list); const nextButton = nextButtons[currentStep]; if (selectedValue && nextButton) { nextButton.disabled = false; } }
function selectSuggestion(type, selectedListItem, value) { const listId = `list-${type}`; const list = document.getElementById(listId); if (list) { list.querySelectorAll('li').forEach(item => { item.classList.remove('selected'); item.setAttribute('aria-selected', 'false'); }); } selectedListItem.classList.add('selected'); selectedListItem.setAttribute('aria-selected', 'true'); const selectedTextElement = document.getElementById(`selected-${type}-text`); const nextButton = nextButtons[currentStep]; const truncate = (text, length = 60) => text.length > length ? text.substring(0, length) + "..." : text; const resetCharacterPreview = () => { storyData.characterImageState = 'idle'; storyData.generated_character_image_b64 = null; storyData.characterImageError = null; }; const resetName = () => { storyData.selected_character_name = ''; storyData.name_suggestions = []; document.getElementById('selected-name-text').textContent = 'None'; if(nextButtons[3]) nextButtons[3].disabled = true; resetCharacterPreview(); }; const resetPlot = () => { storyData.selected_plot = ''; storyData.plot_suggestions = []; document.getElementById('selected-plot-text').textContent = 'None'; if(nextButtons[4]) nextButtons[4].disabled = true; }; let valueChanged = false; switch (type) { case 'character': if (storyData.selected_character_description !== value) { storyData.selected_character_description = value; resetName(); resetPlot(); valueChanged = true; } selectedTextElement.textContent = truncate(value); break; case 'name': if (storyData.selected_character_name !== value) { storyData.selected_character_name = value; resetPlot(); resetCharacterPreview(); generateCharacterImageInBackground(); valueChanged = true; } selectedTextElement.textContent = value; break; case 'plot': if (storyData.selected_plot !== value) { storyData.selected_plot = value; valueChanged = true; } selectedTextElement.textContent = truncate(value); break; default: console.error("Unknown suggestion type:", type); return; } if (nextButton) nextButton.disabled = false; clearError(currentStep); }
function updateReviewDetails() { clearError(5); document.getElementById('review-child-name').textContent = storyData.child_name; document.getElementById('review-learning-objective').textContent = storyData.learning_objective; document.getElementById('review-character-description').textContent = storyData.selected_character_description; document.getElementById('review-character-name').textContent = storyData.selected_character_name; document.getElementById('review-plot').textContent = storyData.selected_plot; document.getElementById('review-theme').textContent = storyData.story_theme; document.getElementById('review-keywords').textContent = storyData.personality_keywords.join(', '); switch (storyData.characterImageState) { case 'success': if (storyData.generated_character_image_b64) { const dataUrl = `data:image/png;base64,${storyData.generated_character_image_b64}`; characterImagePreview.src = dataUrl; characterImagePreview.alt = `Preview of ${storyData.selected_character_name}`; characterImagePreview.style.display = 'block'; characterImageStatus.style.display = 'none'; characterImagePreview.onerror = () => { characterImageStatus.textContent = 'Error displaying preview image.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; } } else { characterImageStatus.textContent = 'Preview image data unavailable.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; } break; case 'loading': characterImageStatus.textContent = '⏳ Character preview generating...'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; case 'error': characterImageStatus.textContent = `❌ Could not generate character preview: ${storyData.characterImageError || 'Unknown error'}`; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; case 'idle': default: characterImageStatus.textContent = 'Preview will generate after name selection.'; characterImageStatus.style.display = 'block'; characterImagePreview.style.display = 'none'; break; } generationStatus.textContent = ''; generateBookButton.disabled = !(storyData.child_name && storyData.selected_character_description && storyData.selected_character_name && storyData.selected_plot && storyData.generated_character_image_b64); isGeneratingBook = false; } // Also check character image is ready


// --- NEW: Book Generation and Display ---

function showLoadingOverlay(message) {
    bookLoadingStatus.textContent = message || 'Generating your book...';
    bookLoadingDetail.textContent = 'This involves multiple steps and may take a minute or two.'; // Default detail
    reviewContent.style.display = 'none'; // Hide the review form
     // Ensure step 5 error message is hidden during loading
     if(errorElements[5]) errorElements[5].style.display = 'none';
    bookLoadingOverlay.style.display = 'block'; // Show overlay
}

function hideLoadingOverlay() {
    bookLoadingOverlay.style.display = 'none';
    reviewContent.style.display = 'block'; // Show the review form again
}

async function generateBook() {
    // Basic check if prerequisites met (including character image)
    if (!(storyData.child_name && storyData.selected_character_description && storyData.selected_character_name && storyData.selected_plot && storyData.generated_character_image_b64)) {
         showError(5, "Cannot generate book: Missing required selections or character preview image.");
         return;
     }
    if (isGeneratingBook) return; // Prevent multiple clicks
    isGeneratingBook = true;

    clearError(5); // Clear previous errors
    generateBookButton.disabled = true;
    document.getElementById('btn-step-5-back').disabled = true; // Disable back button too
    showLoadingOverlay('📚 Generating your story book...');

    // Prepare payload for the new backend endpoint
    const payload = {
        child_name: storyData.child_name,
        character_name: storyData.selected_character_name,
        character_description: storyData.selected_character_description,
        plot_choice: storyData.selected_plot,
        learning_objective: storyData.learning_objective,
        theme: storyData.story_theme,
        personality_keywords: storyData.personality_keywords,
        character_image_b64: storyData.generated_character_image_b64 // Pass the character preview
    };

    try {
         // Update status - add stages if backend supports it, otherwise just wait
         bookLoadingStatus.textContent = 'Generating story text...';
         // Call the new backend endpoint
         const responseData = await postApi('/book/generate', payload);

         // Check response structure
         if (responseData.pages && Array.isArray(responseData.pages) && responseData.pages.length > 0) {
             storyData.bookPages = responseData.pages;
             storyData.currentPageIndex = 0; // Reset to first page
             console.log(`Book generated with ${storyData.bookPages.length} pages.`);
             hideLoadingOverlay();
             goToStep(6); // Navigate to the book view
         } else {
             throw new Error("Received invalid book data from server.");
         }

    } catch (error) {
         console.error("Book Generation Error:", error);
         hideLoadingOverlay(); // Hide overlay on error
         showError(5, `Failed to generate book: ${error.message}`); // Show error on Step 5
         generateBookButton.disabled = false; // Re-enable button
         document.getElementById('btn-step-5-back').disabled = false;
         isGeneratingBook = false;
    }
    // Note: isGeneratingBook should be reset in startOver if user navigates away
}

function displayCurrentPage() {
    clearError(6);
    if (!storyData.bookPages || storyData.bookPages.length === 0) { showError(6, "No book pages available to display."); if(bookView) bookView.style.display = 'none'; return; }
    if(bookView) bookView.style.display = 'block';

    const pageIndex = storyData.currentPageIndex; const totalPages = storyData.bookPages.length; const pageData = storyData.bookPages[pageIndex];
    if (!pageData) { showError(6, `Invalid page index: ${pageIndex}`); return; }
    console.log(`Displaying page ${pageIndex + 1} of ${totalPages}`);

    if(bookText) bookText.textContent = pageData.text || "This page has no text.";

    bookImage.style.display = 'none'; bookImageSpinner.style.display = 'flex';
    bookImage.removeAttribute('onerror'); bookImage.removeAttribute('onload');

    // *** CORRECTED KEY: Access b64_json for page data ***
    if (pageData.b64_json) {
        const dataUrl = `data:image/png;base64,${pageData.b64_json}`; // Use correct key
        bookImage.src = dataUrl; bookImage.alt = `Illustration for page ${pageIndex + 1}`;
        bookImage.onload = () => { bookImage.style.display = 'block'; bookImageSpinner.style.display = 'none'; };
        bookImage.onerror = () => { console.error(`Error loading image for page ${pageIndex + 1}`); bookImageSpinner.style.display = 'none'; showError(6, `Could not load image for page ${pageIndex + 1}.`); };
        if(bookImage.complete && bookImage.naturalWidth > 0) { bookImage.onload(); }
    } else {
        bookImageSpinner.style.display = 'none'; console.warn(`No image data for page ${pageIndex + 1}`); showError(6, `No image available for page ${pageIndex + 1}.`);
    }

    if(bookPageIndicator) bookPageIndicator.textContent = `Page ${pageIndex + 1} of ${totalPages}`;
    if(bookPrevButton) bookPrevButton.disabled = (pageIndex === 0);
    if(bookNextButton) bookNextButton.disabled = (pageIndex >= totalPages - 1);
    if(displayChildNameBook) displayChildNameBook.textContent = storyData.child_name;
}

function changePage(delta) {
    const newIndex = storyData.currentPageIndex + delta;
    if (newIndex >= 0 && newIndex < storyData.bookPages.length) {
        storyData.currentPageIndex = newIndex;
        displayCurrentPage();
    }
}

// --- Reset Function ---
function startOver() {
    console.log("Starting over...");
    // Reset state object
    Object.keys(storyData).forEach(key => {
        if (key === 'generated_character_image_b64' || key === 'generated_image_b64') { storyData[key] = null; } // Clear b64
        else if (key === 'characterImageState') { storyData[key] = 'idle'; }
        else if (key === 'characterImageError') { storyData[key] = null; }
        else if (key === 'bookPages') { storyData[key] = []; } // Clear book pages
        else if (key === 'currentPageIndex') { storyData[key] = 0; } // Reset index
        else { storyData[key] = Array.isArray(storyData[key]) ? [] : ''; } // Standard reset
    });

    document.getElementById('form-basics').reset();
    ['character', 'name', 'plot'].forEach(type => { const suggestionsContainer = document.getElementById(`${type}-suggestions`); const selectedTextElement = document.getElementById(`selected-${type}-text`); if (suggestionsContainer) suggestionsContainer.innerHTML = ''; if (selectedTextElement) selectedTextElement.textContent = 'None'; });
    document.getElementById('review-details').querySelectorAll('span').forEach(span => span.textContent = '');

    // Reset Step 5 UI
    hideLoadingOverlay(); // Ensure overlay is hidden
    generateBookButton.disabled = true;
    if(document.getElementById('btn-step-5-back')) document.getElementById('btn-step-5-back').disabled = false;
    if(characterImageStatus) characterImageStatus.textContent = 'Preview will generate...'; characterImageStatus.style.display = 'block';
    if(characterImagePreview) { characterImagePreview.src = ''; characterImagePreview.style.display = 'none'; }

    // Reset Step 6 UI
    if(bookView) bookView.style.display = 'none';
    if(bookText) bookText.textContent = '';
    if(bookImage) { bookImage.src = ''; bookImage.style.display = 'none'; }
    if(bookImageSpinner) bookImageSpinner.style.display = 'none';
    if(bookPageIndicator) bookPageIndicator.textContent = '';
    if(bookPrevButton) bookPrevButton.disabled = true;
    if(bookNextButton) bookNextButton.disabled = true;

    clearAllErrors();
    Object.values(nextButtons).forEach(btn => { if(btn) btn.disabled = true; });
    isGeneratingBook = false;
    goToStep(1);
}

// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => {
    fetch(`${API_BASE_URL}/health`)
        .then(response => response.ok ? response.json() : Promise.reject(`Health check failed: ${response.status}`))
        .then(data => console.log("API Health:", data))
        .catch(err => console.warn("API Health check warning:", err));
    startOver();
});