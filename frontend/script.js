const API_BASE_URL =
    window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1")
        ? "http://localhost:5001/api"
        : "/api";

const FALLBACK_SETTINGS_OPTIONS = {
    default_provider: "gemini",
    providers: {
        openai: {
            label: "OpenAI",
            text_models: ["gpt-4.1-nano", "gpt-4.1-mini", "gpt-4o-mini"],
            image_models: ["gpt-image-1"],
            image_edit_models: ["gpt-image-1"],
            image_sizes: ["1024x1024", "1024x1536", "1536x1024", "auto"],
            image_qualities: ["low", "medium", "high", "auto"],
            image_output_formats: ["png", "jpeg", "webp"],
            default_settings: {
                provider: "openai",
                text_model: "gpt-4.1-mini",
                text_temperature: 0.7,
                image_model: "gpt-image-1",
                image_edit_model: "gpt-image-1",
                image_size: "1024x1024",
                image_edit_size: "1024x1024",
                image_quality: "low",
                image_edit_quality: "low",
                image_output_format: "png",
            },
        },
        gemini: {
            label: "Google Gemini",
            text_models: ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"],
            image_models: ["gemini-2.5-flash-image", "gemini-3-pro-image-preview"],
            image_edit_models: ["gemini-2.5-flash-image", "gemini-3-pro-image-preview"],
            gemini_aspect_ratios: ["1:1", "9:16", "16:9", "3:4", "4:3", "4:5", "5:4"],
            gemini_image_sizes: ["1K", "2K", "4K"],
            default_settings: {
                provider: "gemini",
                text_model: "gemini-3-flash-preview",
                text_temperature: 0.8,
                image_model: "gemini-2.5-flash-image",
                image_edit_model: "gemini-2.5-flash-image",
                gemini_aspect_ratio: "1:1",
                gemini_image_size: "1K",
                image_output_format: "png",
            },
        },
    },
    provider_health: {
        openai: "unknown",
        gemini: "unknown",
    },
};

let settingsOptions = FALLBACK_SETTINGS_OPTIONS;

const storyData = {
    child_profile_input: "",
    extracted_profile_source: "",

    child_name: "",
    learning_objective: "",
    personality_keywords: [],
    story_theme: "",
    story_theme_suggestions: [],

    character_suggestions: [],
    selected_character_descriptions: [],
    selected_character_description: "",
    name_suggestions: [],
    selected_character_name: "",
    plot_suggestions: [],
    selected_plot: "",
    child_character: null,
    story_characters: [],
    storyCastState: "idle",
    storyCastError: null,
    storyCastSourceKey: "",
    characterReferencesState: "idle",
    characterReferencesError: null,
    main_story_characters: [],
    mainStoryCharactersState: "idle",
    mainStoryCharactersError: null,
    mainStoryCharactersSourceKey: "",

    generated_character_image_b64: null,
    generated_character_image_mime: "image/png",
    characterImageState: "idle",
    characterImageError: null,

    bookPages: [],
    currentPageIndex: 0,

    aiSettings: { ...FALLBACK_SETTINGS_OPTIONS.providers.gemini.default_settings },
};

let currentStep = 1;
let isGeneratingBook = false;
let isDownloadingPdf = false;
let isExtractingProfile = false;
let bookLoadingFeedbackInterval = null;
let bookLoadingStartedAt = 0;
let bookLoadingStageIndex = 0;

const BOOK_LOADING_STAGES = [
    {
        key: "story",
        status: "Generating story text...",
        detail: "Creating a personalized story from your selected plot and goals.",
    },
    {
        key: "sections",
        status: "Splitting into story pages...",
        detail: "Organizing the story into clean page sections.",
    },
    {
        key: "images",
        status: "Creating page illustrations...",
        detail: "Generating images for each page. This is usually the longest step.",
    },
    {
        key: "finalize",
        status: "Finalizing your book...",
        detail: "Assembling text and images into your final book.",
    },
];

const steps = document.querySelectorAll(".step");
const errorElements = {
    1: document.getElementById("error-step-1"),
    2: document.getElementById("error-step-2"),
    3: document.getElementById("error-step-3"),
    4: document.getElementById("error-step-4"),
    5: document.getElementById("error-step-5"),
    6: document.getElementById("error-step-6"),
};
const nextButtons = {
    2: document.getElementById("btn-step-2-next"),
    3: document.getElementById("btn-step-3-next"),
    4: document.getElementById("btn-step-4-next"),
};
const generateBookButton = document.getElementById("btn-generate-book");
const generationStatus = document.getElementById("generation-status");

const bookLoadingOverlay = document.getElementById("book-loading-overlay");
const bookLoadingStatus = document.getElementById("book-loading-status");
const bookLoadingDetail = document.getElementById("book-loading-detail");
const bookLoadingElapsed = document.getElementById("book-loading-elapsed");
const bookLoadingPulse = document.getElementById("book-loading-pulse");
const bookLoadingSteps = document.getElementById("book-loading-steps");
const reviewContent = document.getElementById("review-content");

const characterImageStatus = document.getElementById("character-image-status");
const characterImagePreview = document.getElementById("character-image-preview");

const bookView = document.getElementById("book-view");
const bookImage = document.getElementById("book-image");
const bookImageSpinner = document.getElementById("book-image-spinner");
const bookText = document.getElementById("book-text");
const bookPrevButton = document.getElementById("book-prev-button");
const bookNextButton = document.getElementById("book-next-button");
const bookPageIndicator = document.getElementById("book-page-indicator");
const displayChildNameBook = document.getElementById("display-child-name-book");
const downloadPdfButton = document.getElementById("btn-download-pdf");

const reviewAiProvider = document.getElementById("review-ai-provider");
const reviewTextModel = document.getElementById("review-text-model");
const reviewImageModels = document.getElementById("review-image-models");
const reviewMainCharacters = document.getElementById("review-main-characters");
const reviewMainCharactersStatus = document.getElementById("review-main-characters-status");
const childProfileInput = document.getElementById("child-profile-input");
const profileExtractionSummary = document.getElementById("profile-extraction-summary");
const extractedChildName = document.getElementById("extracted-child-name");
const extractedLearningGoal = document.getElementById("extracted-learning-goal");
const extractedInterests = document.getElementById("extracted-interests");
const storyCastStatus = document.getElementById("story-cast-status");
const storyCastList = document.getElementById("story-cast-list");

const providerSelect = document.getElementById("provider-select");
const textModelSelect = document.getElementById("text-model-select");
const textTemperatureInput = document.getElementById("text-temperature-input");
const imageModelSelect = document.getElementById("image-model-select");
const imageEditModelSelect = document.getElementById("image-edit-model-select");
const openaiSettingsContainer = document.getElementById("openai-settings");
const geminiSettingsContainer = document.getElementById("gemini-settings");
const settingsStatus = document.getElementById("settings-status");

const openaiImageSizeSelect = document.getElementById("openai-image-size-select");
const openaiImageEditSizeSelect = document.getElementById("openai-image-edit-size-select");
const openaiImageQualitySelect = document.getElementById("openai-image-quality-select");
const openaiImageEditQualitySelect = document.getElementById("openai-image-edit-quality-select");
const openaiImageFormatSelect = document.getElementById("openai-image-format-select");

const geminiAspectRatioSelect = document.getElementById("gemini-aspect-ratio-select");
const geminiImageSizeSelect = document.getElementById("gemini-image-size-select");

const stepElementIds = {
    1: "step-1-basics",
    2: "step-2-character",
    3: "step-3-name",
    4: "step-4-plot",
    5: "step-5-review",
    6: "step-6-display",
};

function showError(stepNum, message) {
    const errorEl = errorElements[stepNum];
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = "block";
        errorEl.setAttribute("aria-hidden", "false");
    }
    console.error(`Error in Step ${stepNum}: ${message}`);
}

function clearError(stepNum) {
    const errorEl = errorElements[stepNum];
    if (errorEl) {
        errorEl.textContent = "";
        errorEl.style.display = "none";
        errorEl.setAttribute("aria-hidden", "true");
    }
}

function clearAllErrors() {
    Object.keys(errorElements).forEach((stepNum) => clearError(Number(stepNum)));
}

async function postApi(endpoint, data = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    let response;

    try {
        response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(data),
        });

        const contentType = response.headers.get("content-type") || "";
        let responseBody = null;

        if (contentType.includes("application/json")) {
            responseBody = await response.json();
        } else {
            const textBody = await response.text();
            throw new Error(
                `Server returned non-JSON response (status ${response.status}): ${textBody.slice(0, 120)}`
            );
        }

        if (!response.ok) {
            const errorMessage =
                responseBody?.error || `HTTP error ${response.status}: ${response.statusText}`;
            throw new Error(errorMessage);
        }

        return responseBody;
    } catch (error) {
        console.error(`API error for ${url}:`, error);
        throw new Error(error.message || "API call failed.");
    }
}

function buildPdfFilename(baseName) {
    const safeBase = (baseName || "story_book")
        .toString()
        .trim()
        .replace(/[^a-zA-Z0-9_-]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .slice(0, 80) || "story_book";

    const now = new Date();
    const parts = [
        now.getUTCFullYear().toString().padStart(4, "0"),
        (now.getUTCMonth() + 1).toString().padStart(2, "0"),
        now.getUTCDate().toString().padStart(2, "0"),
        "_",
        now.getUTCHours().toString().padStart(2, "0"),
        now.getUTCMinutes().toString().padStart(2, "0"),
        now.getUTCSeconds().toString().padStart(2, "0"),
    ];
    return `${safeBase}_${parts.join("")}.pdf`;
}

function setSelectOptions(selectElement, options, selectedValue) {
    if (!selectElement) {
        return;
    }

    const values = Array.isArray(options) ? options : [];
    selectElement.innerHTML = "";

    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === selectedValue) {
            option.selected = true;
        }
        selectElement.appendChild(option);
    });

    if (values.length > 0 && !values.includes(selectElement.value)) {
        selectElement.value = values[0];
    }
}

function getProviderConfig(provider) {
    return settingsOptions.providers[provider] || settingsOptions.providers.openai;
}

function getDefaultSettings(provider) {
    const providerConfig = getProviderConfig(provider);
    return { ...(providerConfig.default_settings || {}) };
}

function setSettingsStatus(provider) {
    const status = settingsOptions.provider_health?.[provider] || "unknown";
    const label = getProviderConfig(provider).label || provider;

    if (status === "ready") {
        settingsStatus.textContent = `${label} is available.`;
        settingsStatus.style.color = "#2f6f2f";
        return;
    }

    if (status === "unavailable") {
        settingsStatus.textContent = `${label} is currently unavailable (missing key or configuration).`;
        settingsStatus.style.color = "#a13b3b";
        return;
    }

    settingsStatus.textContent = `${label} availability could not be confirmed.`;
    settingsStatus.style.color = "#666";
}

function supportsGeminiHighRes(modelName) {
    return typeof modelName === "string" && modelName.includes("gemini-3-pro-image-preview");
}

function renderProviderSettings(provider, explicitSettings = null) {
    const providerConfig = getProviderConfig(provider);
    const defaults = getDefaultSettings(provider);
    const existing = explicitSettings && explicitSettings.provider === provider ? explicitSettings : {};
    const mergedSettings = { ...defaults, ...existing, provider };

    setSelectOptions(textModelSelect, providerConfig.text_models, mergedSettings.text_model);
    setSelectOptions(imageModelSelect, providerConfig.image_models, mergedSettings.image_model);
    setSelectOptions(
        imageEditModelSelect,
        providerConfig.image_edit_models,
        mergedSettings.image_edit_model
    );

    textTemperatureInput.value =
        mergedSettings.text_temperature !== undefined ? mergedSettings.text_temperature : defaults.text_temperature;

    setSelectOptions(openaiImageSizeSelect, providerConfig.image_sizes || [], mergedSettings.image_size);
    setSelectOptions(
        openaiImageEditSizeSelect,
        providerConfig.image_sizes || [],
        mergedSettings.image_edit_size
    );
    setSelectOptions(
        openaiImageQualitySelect,
        providerConfig.image_qualities || [],
        mergedSettings.image_quality
    );
    setSelectOptions(
        openaiImageEditQualitySelect,
        providerConfig.image_qualities || [],
        mergedSettings.image_edit_quality
    );
    setSelectOptions(
        openaiImageFormatSelect,
        providerConfig.image_output_formats || [],
        mergedSettings.image_output_format
    );

    setSelectOptions(
        geminiAspectRatioSelect,
        providerConfig.gemini_aspect_ratios || [],
        mergedSettings.gemini_aspect_ratio
    );

    const sizeOptions = supportsGeminiHighRes(imageModelSelect.value)
        ? providerConfig.gemini_image_sizes || ["1K"]
        : ["1K"];
    setSelectOptions(geminiImageSizeSelect, sizeOptions, mergedSettings.gemini_image_size);

    openaiSettingsContainer.style.display = provider === "openai" ? "block" : "none";
    geminiSettingsContainer.style.display = provider === "gemini" ? "block" : "none";

    storyData.aiSettings = collectAiSettingsFromForm();
    setSettingsStatus(provider);
}

function collectAiSettingsFromForm() {
    const provider = providerSelect.value;
    const settings = {
        provider,
        text_model: textModelSelect.value,
        text_temperature: Number(textTemperatureInput.value),
        image_model: imageModelSelect.value,
        image_edit_model: imageEditModelSelect.value,
        image_output_format: openaiImageFormatSelect.value || "png",
    };

    if (provider === "openai") {
        settings.image_size = openaiImageSizeSelect.value;
        settings.image_edit_size = openaiImageEditSizeSelect.value;
        settings.image_quality = openaiImageQualitySelect.value;
        settings.image_edit_quality = openaiImageEditQualitySelect.value;
    }

    if (provider === "gemini") {
        settings.gemini_aspect_ratio = geminiAspectRatioSelect.value;
        settings.gemini_image_size = geminiImageSizeSelect.value;
    }

    return settings;
}

function getRequestContext() {
    return {
        provider: storyData.aiSettings.provider,
        settings: { ...storyData.aiSettings },
    };
}

function cleanSuggestionText(value) {
    const text = String(value || "")
        .replace(/\r/g, "\n")
        .replace(/\n+/g, " ")
        .replace(/^\s*(?:[-*]+|\d+[.)])\s*/g, "")
        .replace(/\s+/g, " ")
        .trim();
    return text;
}

function normalizeSuggestionKey(value) {
    return cleanSuggestionText(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .trim();
}

function isNearDuplicateSuggestion(currentValue, existingValue) {
    const a = normalizeSuggestionKey(currentValue);
    const b = normalizeSuggestionKey(existingValue);
    if (!a || !b) {
        return false;
    }
    if (a === b) {
        return true;
    }
    if (a.length >= 8 && b.length >= 8 && (a.includes(b) || b.includes(a))) {
        return true;
    }

    const tokensA = new Set(a.split(" ").filter((token) => token.length > 2));
    const tokensB = new Set(b.split(" ").filter((token) => token.length > 2));
    if (tokensA.size === 0 || tokensB.size === 0) {
        return false;
    }

    let overlap = 0;
    tokensA.forEach((token) => {
        if (tokensB.has(token)) {
            overlap += 1;
        }
    });

    const ratio = overlap / Math.min(tokensA.size, tokensB.size);
    return ratio >= 0.85;
}

function normalizeSuggestionItems(type, suggestions) {
    if (!Array.isArray(suggestions)) {
        return [];
    }

    const minLengthByType = {
        theme: 6,
        character: 9,
        plot: 20,
        name: 2,
    };
    const minLength = minLengthByType[type] || 4;

    const unique = [];
    suggestions.forEach((rawItem) => {
        const text = cleanSuggestionText(rawItem);
        if (!text || text.length < minLength) {
            return;
        }

        const duplicate = unique.some((existing) =>
            type === "name"
                ? normalizeSuggestionKey(existing) === normalizeSuggestionKey(text)
                : isNearDuplicateSuggestion(text, existing)
        );
        if (!duplicate) {
            unique.push(text);
        }
    });

    return unique;
}

function getOptionLabel(type, index) {
    const labels = {
        theme: "Theme",
        character: "Character",
        name: "Name",
        plot: "Plot",
    };
    const prefix = labels[type] || "Option";
    return `${prefix} ${index + 1}`;
}

function splitSuggestionIntoTitleAndDetail(type, suggestion) {
    const text = cleanSuggestionText(suggestion);
    if (!text) {
        return { title: "", detail: "" };
    }
    if (type === "name") {
        return { title: text, detail: "" };
    }

    if (type === "plot") {
        const sentences = text.match(/[^.!?]+[.!?]?/g) || [text];
        const title = sentences[0] || text;
        const detail = sentences.slice(1).join(" ").trim();
        return { title, detail };
    }

    const separators = [" - ", ": ", "; ", ", "];
    for (const separator of separators) {
        const idx = text.indexOf(separator);
        if (idx > 0) {
            return {
                title: text.slice(0, idx).trim(),
                detail: text.slice(idx + separator.length).trim(),
            };
        }
    }

    const words = text.split(" ");
    if (words.length > 7) {
        return {
            title: words.slice(0, 7).join(" "),
            detail: words.slice(7).join(" "),
        };
    }

    return { title: text, detail: "" };
}

function renderSuggestionList(container, type, suggestions, selectedValue) {
    const list = document.createElement("ul");
    list.className = "suggestion-list";
    list.id = `list-${type}`;
    list.setAttribute("role", "listbox");

    suggestions.forEach((rawSuggestion, index) => {
        const suggestion = cleanSuggestionText(rawSuggestion);
        const { title, detail } = splitSuggestionIntoTitleAndDetail(type, suggestion);
        const listItem = document.createElement("li");
        listItem.dataset.value = suggestion;
        listItem.setAttribute("role", "option");
        listItem.setAttribute("tabindex", "0");
        listItem.setAttribute("aria-selected", "false");

        const topRow = document.createElement("div");
        topRow.className = "suggestion-item-top";

        const optionLabel = document.createElement("span");
        optionLabel.className = "option-label";
        optionLabel.textContent = getOptionLabel(type, index);
        topRow.appendChild(optionLabel);

        const titleElement = document.createElement("span");
        titleElement.className = "suggestion-title";
        titleElement.textContent = title || suggestion;
        topRow.appendChild(titleElement);
        listItem.appendChild(topRow);

        if (detail) {
            const detailElement = document.createElement("p");
            detailElement.className = "suggestion-detail";
            detailElement.textContent = detail;
            listItem.appendChild(detailElement);
        }

        const isSelected =
            type === "character" && Array.isArray(selectedValue)
                ? selectedValue.some(
                      (value) => normalizeSuggestionKey(suggestion) === normalizeSuggestionKey(value)
                  )
                : normalizeSuggestionKey(suggestion) === normalizeSuggestionKey(selectedValue);

        if (isSelected) {
            listItem.classList.add("selected");
            listItem.setAttribute("aria-selected", "true");
        }

        listItem.onclick = () => selectSuggestion(type, listItem, suggestion);
        listItem.onkeydown = (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                selectSuggestion(type, listItem, suggestion);
            }
        };

        list.appendChild(listItem);
    });

    container.innerHTML = "";
    container.appendChild(list);
}

function updateProfileExtractionSummary() {
    if (
        !storyData.child_name &&
        !storyData.learning_objective &&
        (!storyData.personality_keywords || storyData.personality_keywords.length === 0)
    ) {
        profileExtractionSummary.style.display = "none";
        return;
    }

    extractedChildName.textContent = storyData.child_name || "-";
    extractedLearningGoal.textContent = storyData.learning_objective || "-";
    extractedInterests.textContent =
        storyData.personality_keywords && storyData.personality_keywords.length > 0
            ? storyData.personality_keywords.join(", ")
            : "-";
    profileExtractionSummary.style.display = "block";
}

function clearProfileExtractionData() {
    storyData.extracted_profile_source = "";
    storyData.child_name = "";
    storyData.learning_objective = "";
    storyData.personality_keywords = [];
    storyData.story_theme_suggestions = [];
    storyData.story_theme = "";
    storyData.character_suggestions = [];
    storyData.selected_character_descriptions = [];
    storyData.selected_character_description = "";
    storyData.name_suggestions = [];
    storyData.selected_character_name = "";
    storyData.plot_suggestions = [];
    storyData.selected_plot = "";
    storyData.child_character = null;
    storyData.story_characters = [];
    storyData.storyCastState = "idle";
    storyData.storyCastError = null;
    storyData.storyCastSourceKey = "";
    storyData.characterReferencesState = "idle";
    storyData.characterReferencesError = null;
    resetMainStoryCharactersState();
    if (storyCastStatus) {
        storyCastStatus.textContent = "";
    }
    if (storyCastList) {
        storyCastList.innerHTML = "";
    }
    updateProfileExtractionSummary();
}

async function extractProfileFromInput(force = false) {
    const profileText = childProfileInput.value.trim();
    if (!profileText) {
        showError(1, "Please tell us about your child first.");
        return false;
    }

    if (
        !force &&
        storyData.extracted_profile_source === profileText &&
        storyData.child_name &&
        storyData.character_suggestions.length > 0 &&
        storyData.story_theme_suggestions.length > 0
    ) {
        return true;
    }

    isExtractingProfile = true;
    clearError(1);
    settingsStatus.textContent = "Extracting child profile...";
    settingsStatus.style.color = "#555";

    try {
        const result = await postApi("/profile/extract", {
            profile_text: profileText,
            ...getRequestContext(),
        });

        storyData.child_profile_input = profileText;
        storyData.extracted_profile_source = profileText;
        storyData.child_name = result.child_name || "";
        storyData.learning_objective = result.learning_objective || "";
        storyData.personality_keywords = Array.isArray(result.personality_keywords)
            ? result.personality_keywords
            : [];
        storyData.story_theme_suggestions = normalizeSuggestionItems("theme", result.story_theme_suggestions);
        storyData.story_theme = storyData.story_theme_suggestions[0] || "";
        storyData.character_suggestions = normalizeSuggestionItems("character", result.character_suggestions);

        resetStoryCastState();
        storyData.name_suggestions = [];
        storyData.plot_suggestions = [];
        storyData.selected_plot = "";
        resetCharacterPreviewState();
        resetMainStoryCharactersState();

        updateProfileExtractionSummary();
        setSettingsStatus(storyData.aiSettings.provider);
        return true;
    } catch (error) {
        showError(1, `Could not extract child profile: ${error.message}`);
        return false;
    } finally {
        isExtractingProfile = false;
    }
}

function resetCharacterPreviewState() {
    storyData.characterImageState = "idle";
    storyData.characterImageError = null;
    storyData.generated_character_image_b64 = null;
    storyData.generated_character_image_mime = "image/png";
}

function resetStoryCastState() {
    storyData.selected_character_descriptions = [];
    storyData.child_character = null;
    storyData.story_characters = [];
    storyData.storyCastState = "idle";
    storyData.storyCastError = null;
    storyData.storyCastSourceKey = "";
    storyData.characterReferencesState = "idle";
    storyData.characterReferencesError = null;
    storyData.selected_character_name = "";
    storyData.selected_character_description = "";
}

function resetMainStoryCharactersState() {
    storyData.main_story_characters = [];
    storyData.mainStoryCharactersState = "idle";
    storyData.mainStoryCharactersError = null;
    storyData.mainStoryCharactersSourceKey = "";
}

function buildMainStoryCharactersSourceKey() {
    return [
        storyData.child_name,
        storyData.selected_character_name,
        storyData.selected_character_description,
        storyData.selected_plot,
        storyData.learning_objective,
        storyData.story_theme,
        storyData.aiSettings.provider,
        storyData.aiSettings.text_model,
        String(storyData.aiSettings.text_temperature),
    ]
        .map((value) => cleanSuggestionText(value))
        .join("||");
}

async function fetchMainStoryCharacters(force = false) {
    const required = [
        storyData.child_name,
        storyData.selected_character_name,
        storyData.selected_character_description,
        storyData.selected_plot,
        storyData.learning_objective,
        storyData.story_theme,
    ];
    if (required.some((value) => !value)) {
        return;
    }

    const sourceKey = buildMainStoryCharactersSourceKey();
    if (
        !force &&
        storyData.mainStoryCharactersState === "success" &&
        storyData.mainStoryCharactersSourceKey === sourceKey &&
        storyData.main_story_characters.length > 0
    ) {
        return;
    }
    if (storyData.mainStoryCharactersState === "loading") {
        return;
    }

    storyData.mainStoryCharactersState = "loading";
    storyData.mainStoryCharactersError = null;
    storyData.main_story_characters = [];
    if (currentStep === 5) {
        updateReviewDetails();
    }

    try {
        const data = await postApi("/story/main-characters", {
            child_name: storyData.child_name,
            character_name: storyData.selected_character_name,
            character_description: storyData.selected_character_description,
            plot_choice: storyData.selected_plot,
            learning_objective: storyData.learning_objective,
            theme: storyData.story_theme,
            ...getRequestContext(),
        });

        storyData.main_story_characters = normalizeSuggestionItems(
            "name",
            data.main_characters || []
        );
        storyData.mainStoryCharactersState = "success";
        storyData.mainStoryCharactersError = null;
        storyData.mainStoryCharactersSourceKey = sourceKey;
    } catch (error) {
        storyData.main_story_characters = [];
        storyData.mainStoryCharactersState = "error";
        storyData.mainStoryCharactersError = error.message || "Unknown extraction error.";
        storyData.mainStoryCharactersSourceKey = "";
    } finally {
        if (currentStep === 5) {
            updateReviewDetails();
        }
    }
}

function handleAiSettingsChange() {
    const previousProvider = storyData.aiSettings.provider;
    storyData.aiSettings = collectAiSettingsFromForm();

    if (storyData.aiSettings.provider !== previousProvider) {
        clearProfileExtractionData();
    }

    resetStoryCastState();
    resetCharacterPreviewState();
    resetMainStoryCharactersState();
    storyData.bookPages = [];
    storyData.currentPageIndex = 0;

    if (currentStep === 5) {
        updateReviewDetails();
        generateCharacterReferencesInBackground(true);
    }
}

function registerSettingsEvents() {
    providerSelect.addEventListener("change", () => {
        renderProviderSettings(providerSelect.value);
        handleAiSettingsChange();
    });

    imageModelSelect.addEventListener("change", () => {
        if (providerSelect.value === "gemini") {
            const providerConfig = getProviderConfig("gemini");
            const sizeOptions = supportsGeminiHighRes(imageModelSelect.value)
                ? providerConfig.gemini_image_sizes || ["1K"]
                : ["1K"];
            setSelectOptions(geminiImageSizeSelect, sizeOptions, geminiImageSizeSelect.value);
        }
        handleAiSettingsChange();
    });

    [
        textModelSelect,
        textTemperatureInput,
        imageEditModelSelect,
        openaiImageSizeSelect,
        openaiImageEditSizeSelect,
        openaiImageQualitySelect,
        openaiImageEditQualitySelect,
        openaiImageFormatSelect,
        geminiAspectRatioSelect,
        geminiImageSizeSelect,
    ].forEach((element) => {
        element.addEventListener("change", handleAiSettingsChange);
    });

    childProfileInput.addEventListener("input", () => {
        if (storyData.extracted_profile_source !== childProfileInput.value.trim()) {
            clearProfileExtractionData();
            resetCharacterPreviewState();
        }
    });
}

async function loadSettingsOptions() {
    try {
        const response = await fetch(`${API_BASE_URL}/settings/options`);
        if (!response.ok) {
            throw new Error(`Failed to load settings options (${response.status}).`);
        }
        const data = await response.json();
        if (!data.providers) {
            throw new Error("Settings response was incomplete.");
        }

        settingsOptions = data;
    } catch (error) {
        console.warn("Using fallback settings options:", error.message);
        settingsOptions = FALLBACK_SETTINGS_OPTIONS;
    }

    let provider = settingsOptions.default_provider || "gemini";
    if (settingsOptions.provider_health?.[provider] !== "ready") {
        const firstReadyProvider = Object.entries(settingsOptions.provider_health || {}).find(
            ([, status]) => status === "ready"
        );
        if (firstReadyProvider) {
            provider = firstReadyProvider[0];
        }
    }
    providerSelect.value = provider;
    renderProviderSettings(provider);
    registerSettingsEvents();
}

function validateStep1() {
    const profileText = childProfileInput.value.trim();
    clearError(1);

    if (!profileText || profileText.length < 20) {
        showError(1, "Please add a few sentences about your child so we can extract story settings.");
        return false;
    }

    storyData.child_profile_input = profileText;
    storyData.aiSettings = collectAiSettingsFromForm();
    return true;
}

async function goToStep(targetStepNum) {
    if (isExtractingProfile) {
        return;
    }
    if (currentStep === 1 && targetStepNum > 1 && !validateStep1()) {
        return;
    }
    if (currentStep === 1 && targetStepNum > 1) {
        const extractionOk = await extractProfileFromInput();
        if (!extractionOk) {
            return;
        }
    }
    if (
        currentStep === 2 &&
        targetStepNum > 2 &&
        (!Array.isArray(storyData.selected_character_descriptions) ||
            storyData.selected_character_descriptions.length === 0)
    ) {
        showError(2, "Please select one or more character options.");
        return;
    }
    if (currentStep === 2 && targetStepNum > 2 && !storyData.story_theme) {
        showError(2, "Please select a story theme.");
        return;
    }
    if (currentStep === 3 && targetStepNum > 3 && (!storyData.story_characters || storyData.story_characters.length < 2)) {
        showError(3, "Story cast is not ready yet. Please wait.");
        return;
    }
    if (currentStep === 4 && targetStepNum > 4 && !storyData.selected_plot) {
        showError(4, "Please select a plot idea.");
        return;
    }

    if (currentStep !== targetStepNum) {
        clearError(currentStep);
    }

    steps.forEach((step) => step.classList.remove("active"));

    const targetElementId = stepElementIds[targetStepNum];
    const nextStepElement = document.getElementById(targetElementId);
    if (!nextStepElement) {
        showError(currentStep, `UI Error: Could not display step ${targetStepNum}.`);
        return;
    }

    const previousStep = currentStep;
    nextStepElement.classList.add("active");
    currentStep = targetStepNum;

    try {
        nextStepElement.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (scrollError) {
        console.warn("Scroll failed:", scrollError);
    }

    if (currentStep === 2 && (previousStep < currentStep || storyData.character_suggestions.length === 0)) {
        fetchCharacterSuggestions();
    }
    if (currentStep === 3) {
        await prepareStoryCast();
    }
    if (currentStep === 4 && (previousStep < currentStep || storyData.plot_suggestions.length === 0)) {
        fetchPlotSuggestions();
    }
    if (currentStep === 5) {
        updateReviewDetails();
        await generateCharacterReferencesInBackground();
    }
    if (currentStep === 6) {
        displayCurrentPage();
    }
}

function setSuggestionsLoading(type) {
    const container = document.getElementById(`${type}-suggestions`);
    if (container) {
        container.innerHTML = `<p class="loading-message">Loading ${type} suggestions...</p>`;
    }

    const nextButton = nextButtons[currentStep];
    if (nextButton) {
        nextButton.disabled = true;
    }

    clearError(currentStep);
}

async function fetchCharacterSuggestions() {
    setSuggestionsLoading("character");
    displayThemeSuggestions();
    if (storyData.character_suggestions.length > 0) {
        displaySuggestions("character", storyData.character_suggestions);
        return;
    }
    showError(2, "No character suggestions were extracted. Please go back and try different child details.");
    document.getElementById("character-suggestions").innerHTML =
        "<p class=\"error-message\">No character suggestions available.</p>";
}

function displayThemeSuggestions() {
    const container = document.getElementById("theme-suggestions");
    if (!container) {
        return;
    }

    const suggestions = normalizeSuggestionItems("theme", storyData.story_theme_suggestions || []);
    storyData.story_theme_suggestions = suggestions;
    if (suggestions.length === 0) {
        container.innerHTML = "<p class=\"error-message\">No theme suggestions available.</p>";
        return;
    }

    if (!storyData.story_theme || !suggestions.includes(storyData.story_theme)) {
        storyData.story_theme = suggestions[0];
    }

    renderSuggestionList(container, "theme", suggestions, storyData.story_theme);
    const selectedThemeText = document.getElementById("selected-theme-text");
    if (selectedThemeText) {
        selectedThemeText.textContent = storyData.story_theme || "None";
    }
}

function buildStoryCastSourceKey() {
    return [
        storyData.child_name,
        storyData.learning_objective,
        storyData.story_theme,
        ...(storyData.selected_character_descriptions || []),
        storyData.aiSettings.provider,
        storyData.aiSettings.text_model,
        String(storyData.aiSettings.text_temperature),
    ]
        .map((value) => cleanSuggestionText(value))
        .join("||");
}

function renderStoryCastPreview() {
    if (!storyCastList || !storyCastStatus) {
        return;
    }

    storyCastList.innerHTML = "";
    if (storyData.storyCastState === "loading") {
        storyCastStatus.textContent = "Creating story cast from selected characters...";
        return;
    }
    if (storyData.storyCastState === "error") {
        storyCastStatus.textContent =
            `Could not prepare story cast: ${storyData.storyCastError || "Unknown error."}`;
        return;
    }
    if (!Array.isArray(storyData.story_characters) || storyData.story_characters.length === 0) {
        storyCastStatus.textContent = "Select a theme and characters first.";
        return;
    }

    storyCastStatus.textContent = `Cast ready: ${storyData.story_characters.length} characters.`;
    storyData.story_characters.forEach((character) => {
        const listItem = document.createElement("li");
        listItem.className = "story-cast-item";
        const role = character.is_child ? "Child Hero" : "Supporting Character";
        listItem.textContent = `${character.name} (${role}) - ${character.description}`;
        storyCastList.appendChild(listItem);
    });
}

async function prepareStoryCast(force = false) {
    if (!storyData.story_theme || !storyData.selected_character_descriptions.length) {
        return false;
    }

    const sourceKey = buildStoryCastSourceKey();
    if (
        !force &&
        storyData.storyCastState === "success" &&
        storyData.storyCastSourceKey === sourceKey &&
        Array.isArray(storyData.story_characters) &&
        storyData.story_characters.length >= 2
    ) {
        renderStoryCastPreview();
        return true;
    }
    if (storyData.storyCastState === "loading") {
        return false;
    }

    storyData.storyCastState = "loading";
    storyData.storyCastError = null;
    storyData.story_characters = [];
    storyData.child_character = null;
    storyData.storyCastSourceKey = "";
    storyData.characterReferencesState = "idle";
    storyData.characterReferencesError = null;
    if (nextButtons[3]) {
        nextButtons[3].disabled = true;
    }
    renderStoryCastPreview();
    clearError(3);

    try {
        const data = await postApi("/story/cast/prepare", {
            child_name: storyData.child_name,
            learning_objective: storyData.learning_objective,
            theme: storyData.story_theme,
            personality_keywords: storyData.personality_keywords,
            selected_character_ideas: storyData.selected_character_descriptions,
            child_profile_text: storyData.child_profile_input,
            ...getRequestContext(),
        });

        storyData.child_character = data.child_character || null;
        storyData.story_characters = Array.isArray(data.story_characters) ? data.story_characters : [];
        storyData.storyCastState = "success";
        storyData.storyCastError = null;
        storyData.storyCastSourceKey = sourceKey;

        if (storyData.child_character?.name) {
            storyData.selected_character_name = storyData.child_character.name;
            storyData.selected_character_description = storyData.child_character.description || "";
            const selectedNameText = document.getElementById("selected-name-text");
            if (selectedNameText) {
                selectedNameText.textContent = storyData.selected_character_name;
            }
        }

        if (nextButtons[3]) {
            nextButtons[3].disabled = !(storyData.story_characters.length >= 2);
        }
        renderStoryCastPreview();
        return storyData.story_characters.length >= 2;
    } catch (error) {
        storyData.storyCastState = "error";
        storyData.storyCastError = error.message || "Unknown cast preparation error.";
        if (nextButtons[3]) {
            nextButtons[3].disabled = true;
        }
        showError(3, `Failed to prepare story cast: ${storyData.storyCastError}`);
        renderStoryCastPreview();
        return false;
    }
}

async function generateCharacterReferencesInBackground(force = false) {
    if (!Array.isArray(storyData.story_characters) || storyData.story_characters.length < 2) {
        return;
    }
    if (storyData.characterReferencesState === "loading") {
        return;
    }

    const needGeneration = storyData.story_characters.some((character) => !character.image_b64);
    if (!force && !needGeneration) {
        storyData.characterReferencesState = "success";
        storyData.characterReferencesError = null;
        if (currentStep === 5) {
            updateReviewDetails();
        }
        return;
    }

    storyData.characterReferencesState = "loading";
    storyData.characterReferencesError = null;
    storyData.characterImageState = "loading";
    storyData.characterImageError = null;
    if (currentStep === 5) {
        updateReviewDetails();
    }

    try {
        for (const character of storyData.story_characters) {
            if (character.image_b64) {
                continue;
            }
            const prompt =
                `Create a single character portrait for a children's story. ` +
                `Character: ${character.name}. Description: ${character.description}. ` +
                `One character only, clear pose, plain background.`;
            const imageResponse = await postApi("/image/generate", {
                description: prompt,
                ...getRequestContext(),
            });
            if (!imageResponse?.b64_json) {
                throw new Error(`Image generation failed for ${character.name}.`);
            }
            character.image_b64 = imageResponse.b64_json;
            character.mime_type = imageResponse.mime_type || "image/png";
        }

        const childRef =
            storyData.story_characters.find((char) => char.is_child && char.image_b64) ||
            storyData.story_characters.find((char) => char.image_b64);
        if (childRef) {
            storyData.generated_character_image_b64 = childRef.image_b64;
            storyData.generated_character_image_mime = childRef.mime_type || "image/png";
            storyData.characterImageState = "success";
        }
        storyData.characterReferencesState = "success";
        storyData.characterReferencesError = null;
    } catch (error) {
        storyData.characterReferencesState = "error";
        storyData.characterReferencesError = error.message || "Unknown character image generation error.";
        storyData.characterImageState = "error";
        storyData.characterImageError = storyData.characterReferencesError;
    } finally {
        if (currentStep === 5) {
            updateReviewDetails();
        }
    }
}

async function fetchNameSuggestions() {
    if (!storyData.selected_character_description) {
        showError(3, "Cannot fetch names without selecting a character first.");
        return;
    }

    setSuggestionsLoading("name");
    try {
        const data = await postApi("/names/suggest", {
            character_description: storyData.selected_character_description,
            theme: storyData.story_theme,
            ...getRequestContext(),
        });
        storyData.name_suggestions = normalizeSuggestionItems("name", data.names || []);
        displaySuggestions("name", storyData.name_suggestions);
    } catch (error) {
        showError(3, `Failed to load name suggestions: ${error.message}`);
        document.getElementById("name-suggestions").innerHTML =
            `<p class="error-message">Could not load names. ${error.message}</p>`;
    }
}

async function fetchPlotSuggestions() {
    if (!storyData.story_characters || storyData.story_characters.length < 2) {
        showError(4, "Cannot fetch plots without a prepared story cast.");
        return;
    }

    setSuggestionsLoading("plot");
    try {
        const data = await postApi("/plot/suggest-from-cast", {
            learning_objective: storyData.learning_objective,
            theme: storyData.story_theme,
            story_characters: storyData.story_characters.map((character) => ({
                name: character.name,
                description: character.description,
                is_child: !!character.is_child,
            })),
            ...getRequestContext(),
        });
        storyData.plot_suggestions = normalizeSuggestionItems("plot", data.plots || []);
        displaySuggestions("plot", storyData.plot_suggestions);
    } catch (error) {
        showError(4, `Failed to load plot suggestions: ${error.message}`);
        document.getElementById("plot-suggestions").innerHTML =
            `<p class="error-message">Could not load plots. ${error.message}</p>`;
    }
}

async function generateCharacterImageInBackground() {
    if (storyData.characterImageState === "loading" || storyData.characterImageState === "success") {
        return;
    }
    if (!storyData.selected_character_description || !storyData.selected_character_name) {
        storyData.characterImageState = "idle";
        if (currentStep === 5) {
            updateReviewDetails();
        }
        return;
    }

    storyData.characterImageState = "loading";
    storyData.characterImageError = null;
    if (currentStep === 5) {
        updateReviewDetails();
    }

    const prompt =
        `Portrait of a character named ${storyData.selected_character_name}, ` +
        `who is ${storyData.selected_character_description}. Style: simple, colorful, friendly children's book illustration, white background.`;

    try {
        const imageResponse = await postApi("/image/generate", {
            description: prompt,
            ...getRequestContext(),
        });

        if (
            imageResponse &&
            typeof imageResponse.b64_json === "string" &&
            imageResponse.b64_json.length > 10
        ) {
            storyData.generated_character_image_b64 = imageResponse.b64_json;
            storyData.generated_character_image_mime = imageResponse.mime_type || "image/png";
            storyData.characterImageState = "success";
        } else {
            throw new Error("Received invalid image data from server.");
        }
    } catch (error) {
        storyData.characterImageState = "error";
        storyData.characterImageError = error.message || "Unknown error during generation.";
        storyData.generated_character_image_b64 = null;
        storyData.generated_character_image_mime = "image/png";
    } finally {
        if (currentStep === 5) {
            updateReviewDetails();
        }
    }
}

function displaySuggestions(type, suggestions) {
    const container = document.getElementById(`${type}-suggestions`);
    const selectedValue =
        type === "character"
            ? storyData.selected_character_descriptions
            : type === "name"
              ? storyData.selected_character_name
              : storyData.selected_plot;

    if (!container) {
        return;
    }

    const normalizedSuggestions = normalizeSuggestionItems(type, suggestions);
    if (type === "character") {
        storyData.character_suggestions = normalizedSuggestions;
    } else if (type === "name") {
        storyData.name_suggestions = normalizedSuggestions;
    } else if (type === "plot") {
        storyData.plot_suggestions = normalizedSuggestions;
    }

    if (!normalizedSuggestions || normalizedSuggestions.length === 0 || normalizedSuggestions[0]?.startsWith("Error:")) {
        const message = suggestions?.[0]
            ? `<p class="error-message">${suggestions[0]}</p>`
            : `<p class="error-message">Could not generate ${type} suggestions.</p>`;
        container.innerHTML = message;
        return;
    }
    renderSuggestionList(container, type, normalizedSuggestions, selectedValue);

    const nextButton = nextButtons[currentStep];
    if (selectedValue && nextButton) {
        if (currentStep === 2) {
            nextButton.disabled = !(storyData.story_theme && storyData.selected_character_descriptions.length > 0);
        } else {
            nextButton.disabled = false;
        }
    }
}

function selectSuggestion(type, selectedListItem, value) {
    value = cleanSuggestionText(value);
    const list = document.getElementById(`list-${type}`);
    if (type === "character") {
        const existsIndex = storyData.selected_character_descriptions.findIndex(
            (item) => normalizeSuggestionKey(item) === normalizeSuggestionKey(value)
        );
        if (existsIndex >= 0) {
            storyData.selected_character_descriptions.splice(existsIndex, 1);
            selectedListItem.classList.remove("selected");
            selectedListItem.setAttribute("aria-selected", "false");
        } else {
            storyData.selected_character_descriptions.push(value);
            selectedListItem.classList.add("selected");
            selectedListItem.setAttribute("aria-selected", "true");
        }

        const selectedTextElement = document.getElementById("selected-character-text");
        if (selectedTextElement) {
            if (storyData.selected_character_descriptions.length === 0) {
                selectedTextElement.textContent = "None";
            } else {
                selectedTextElement.textContent = `${storyData.selected_character_descriptions.length} selected`;
            }
        }

        storyData.story_characters = [];
        storyData.child_character = null;
        storyData.storyCastState = "idle";
        storyData.storyCastError = null;
        storyData.storyCastSourceKey = "";
        storyData.plot_suggestions = [];
        storyData.selected_plot = "";
        storyData.main_story_characters = [];
        storyData.characterReferencesState = "idle";
        storyData.characterReferencesError = null;

        const selectedPlotText = document.getElementById("selected-plot-text");
        if (selectedPlotText) {
            selectedPlotText.textContent = "None";
        }
        if (nextButtons[4]) {
            nextButtons[4].disabled = true;
        }
        if (nextButtons[2]) {
            nextButtons[2].disabled = !(storyData.story_theme && storyData.selected_character_descriptions.length > 0);
        }
        clearError(currentStep);
        return;
    }

    if (list) {
        list.querySelectorAll("li").forEach((item) => {
            item.classList.remove("selected");
            item.setAttribute("aria-selected", "false");
        });
    }

    selectedListItem.classList.add("selected");
    selectedListItem.setAttribute("aria-selected", "true");

    const selectedTextElement = document.getElementById(`selected-${type}-text`);
    const nextButton = nextButtons[currentStep];
    const truncate = (text, length = 60) =>
        text.length > length ? `${text.substring(0, length)}...` : text;

    const resetName = () => {
        storyData.selected_character_name = "";
        storyData.name_suggestions = [];
        document.getElementById("selected-name-text").textContent = "None";
        if (nextButtons[3]) {
            nextButtons[3].disabled = true;
        }
        resetCharacterPreviewState();
        resetMainStoryCharactersState();
    };

    const resetPlot = () => {
        storyData.selected_plot = "";
        storyData.plot_suggestions = [];
        document.getElementById("selected-plot-text").textContent = "None";
        if (nextButtons[4]) {
            nextButtons[4].disabled = true;
        }
        resetMainStoryCharactersState();
    };

    if (type === "theme") {
        if (storyData.story_theme !== value) {
            storyData.story_theme = value;
            resetName();
            resetPlot();
            storyData.story_characters = [];
            storyData.child_character = null;
            storyData.storyCastState = "idle";
            storyData.storyCastError = null;
            storyData.storyCastSourceKey = "";
            storyData.characterReferencesState = "idle";
            storyData.characterReferencesError = null;
        }
        selectedTextElement.textContent = truncate(value, 70);
        displayThemeSuggestions();
    }

    if (type === "name") {
        if (storyData.selected_character_name !== value) {
            storyData.selected_character_name = value;
            resetPlot();
            resetCharacterPreviewState();
            generateCharacterImageInBackground();
        }
        selectedTextElement.textContent = value;
    }

    if (type === "plot") {
        if (storyData.selected_plot !== value) {
            storyData.selected_plot = value;
            resetMainStoryCharactersState();
        }
        selectedTextElement.textContent = truncate(value);
    }

    if (nextButton) {
        if (currentStep === 2) {
            nextButton.disabled = !(storyData.story_theme && storyData.selected_character_descriptions.length > 0);
        } else {
            nextButton.disabled = false;
        }
    }

    clearError(currentStep);
}

function updateReviewDetails() {
    clearError(5);

    const cast = Array.isArray(storyData.story_characters) ? storyData.story_characters : [];
    const castNames = cast.map((character) => character.name).filter(Boolean);
    storyData.main_story_characters = castNames;

    document.getElementById("review-child-name").textContent = storyData.child_name;
    document.getElementById("review-learning-objective").textContent = storyData.learning_objective;
    document.getElementById("review-character-description").textContent =
        storyData.selected_character_descriptions.join(", ");
    document.getElementById("review-character-name").textContent =
        storyData.child_character?.name || storyData.selected_character_name;
    document.getElementById("review-plot").textContent = storyData.selected_plot;
    document.getElementById("review-theme").textContent = storyData.story_theme;
    document.getElementById("review-keywords").textContent = storyData.personality_keywords.join(", ");

    if (reviewMainCharacters) {
        reviewMainCharacters.innerHTML = "";
        cast.forEach((character) => {
            const listItem = document.createElement("li");
            const hasImage = !!character.image_b64;
            listItem.textContent = hasImage ? `${character.name} (reference ready)` : `${character.name} (pending)`;
            reviewMainCharacters.appendChild(listItem);
        });
    }
    if (reviewMainCharactersStatus) {
        if (storyData.storyCastState === "loading") {
            reviewMainCharactersStatus.textContent = "Preparing story cast...";
        } else if (storyData.storyCastState === "error") {
            reviewMainCharactersStatus.textContent =
                `Could not prepare story cast: ${storyData.storyCastError || "Unknown error."}`;
        } else if (storyData.characterReferencesState === "loading") {
            reviewMainCharactersStatus.textContent = "Generating character reference images...";
        } else if (storyData.characterReferencesState === "error") {
            reviewMainCharactersStatus.textContent =
                `Reference image generation issue: ${storyData.characterReferencesError || "Unknown error."}`;
        } else if (cast.length > 0) {
            reviewMainCharactersStatus.textContent = `${cast.length} characters ready for the story.`;
        } else {
            reviewMainCharactersStatus.textContent = "Story cast not ready yet.";
        }
    }

    const providerLabel = getProviderConfig(storyData.aiSettings.provider).label;
    reviewAiProvider.textContent = providerLabel;
    reviewTextModel.textContent = `${storyData.aiSettings.text_model} (temp ${storyData.aiSettings.text_temperature})`;
    reviewImageModels.textContent =
        `Generate: ${storyData.aiSettings.image_model}, Edit: ${storyData.aiSettings.image_edit_model}`;

    if (storyData.characterImageState === "success") {
        if (storyData.generated_character_image_b64) {
            const dataUrl =
                `data:${storyData.generated_character_image_mime || "image/png"};base64,` +
                storyData.generated_character_image_b64;
            characterImagePreview.src = dataUrl;
            characterImagePreview.alt = `Preview of ${storyData.child_character?.name || "story character"}`;
            characterImagePreview.style.display = "block";
            characterImageStatus.style.display = "none";
        } else {
            characterImageStatus.textContent = "Preview image data unavailable.";
            characterImageStatus.style.display = "block";
            characterImagePreview.style.display = "none";
        }
    } else if (storyData.characterImageState === "loading") {
        characterImageStatus.textContent = "Character preview generating...";
        characterImageStatus.style.display = "block";
        characterImagePreview.style.display = "none";
    } else if (storyData.characterImageState === "error") {
        characterImageStatus.textContent =
            `Could not generate character preview: ${storyData.characterImageError || "Unknown error"}`;
        characterImageStatus.style.display = "block";
        characterImagePreview.style.display = "none";
    } else {
        characterImageStatus.textContent = "Character reference preview will appear after cast generation.";
        characterImageStatus.style.display = "block";
        characterImagePreview.style.display = "none";
    }

    generationStatus.textContent = "";
    generateBookButton.disabled = !(
        storyData.child_name &&
        storyData.story_characters &&
        storyData.story_characters.length >= 2 &&
        storyData.selected_plot &&
        storyData.characterReferencesState !== "loading"
    );
    isGeneratingBook = false;
}

function setBookLoadingStage(index, overrideStatus = "", overrideDetail = "") {
    const safeIndex = Math.max(0, Math.min(index, BOOK_LOADING_STAGES.length - 1));
    bookLoadingStageIndex = safeIndex;

    const stage = BOOK_LOADING_STAGES[safeIndex];
    bookLoadingStatus.textContent = overrideStatus || stage.status;
    bookLoadingDetail.textContent = overrideDetail || stage.detail;

    if (bookLoadingSteps) {
        const items = Array.from(bookLoadingSteps.querySelectorAll("li"));
        items.forEach((item, itemIndex) => {
            item.classList.remove("is-active", "is-done");
            if (itemIndex < safeIndex) {
                item.classList.add("is-done");
            } else if (itemIndex === safeIndex) {
                item.classList.add("is-active");
            }
        });
    }
}

function startBookLoadingFeedback() {
    bookLoadingStartedAt = Date.now();
    setBookLoadingStage(0);

    if (bookLoadingElapsed) {
        bookLoadingElapsed.textContent = "Elapsed: 0s";
    }
    if (bookLoadingPulse) {
        bookLoadingPulse.textContent = "Working.";
    }

    if (bookLoadingFeedbackInterval) {
        clearInterval(bookLoadingFeedbackInterval);
    }

    bookLoadingFeedbackInterval = window.setInterval(() => {
        const elapsedSec = Math.max(0, Math.floor((Date.now() - bookLoadingStartedAt) / 1000));
        if (bookLoadingElapsed) {
            bookLoadingElapsed.textContent = `Elapsed: ${elapsedSec}s`;
        }
        if (bookLoadingPulse) {
            const dots = ".".repeat((elapsedSec % 3) + 1);
            bookLoadingPulse.textContent = `Working${dots}`;
        }

        const autoStageIndex = elapsedSec < 6 ? 0 : elapsedSec < 12 ? 1 : elapsedSec < 24 ? 2 : 3;
        if (autoStageIndex > bookLoadingStageIndex) {
            setBookLoadingStage(autoStageIndex);
        }
    }, 1000);
}

function stopBookLoadingFeedback() {
    if (bookLoadingFeedbackInterval) {
        clearInterval(bookLoadingFeedbackInterval);
        bookLoadingFeedbackInterval = null;
    }
}

function showLoadingOverlay(message) {
    if (message) {
        bookLoadingStatus.textContent = message;
    }
    bookLoadingDetail.textContent = "This involves multiple steps and may take a minute or two.";
    reviewContent.style.display = "none";
    if (errorElements[5]) {
        errorElements[5].style.display = "none";
    }
    bookLoadingOverlay.style.display = "flex";
    startBookLoadingFeedback();
}

function hideLoadingOverlay() {
    stopBookLoadingFeedback();
    bookLoadingOverlay.style.display = "none";
    reviewContent.style.display = "block";
}

async function generateBook() {
    if (!storyData.child_name || !storyData.selected_plot) {
        showError(5, "Cannot generate book: Missing child details or selected plot.");
        return;
    }
    if (!Array.isArray(storyData.story_characters) || storyData.story_characters.length < 2) {
        showError(5, "Cannot generate book: Story cast must include at least 2 characters.");
        return;
    }

    if (isGeneratingBook) {
        return;
    }

    isGeneratingBook = true;
    clearError(5);
    generateBookButton.disabled = true;
    document.getElementById("btn-step-5-back").disabled = true;
    if (downloadPdfButton) {
        downloadPdfButton.disabled = true;
    }
    showLoadingOverlay("Generating your story book...");

    await generateCharacterReferencesInBackground(true);
    const missingCharacterRefs = storyData.story_characters.some((character) => !character.image_b64);
    if (missingCharacterRefs) {
        hideLoadingOverlay();
        showError(
            5,
            `Cannot generate book: missing character references. ${storyData.characterReferencesError || ""}`.trim()
        );
        generateBookButton.disabled = false;
        document.getElementById("btn-step-5-back").disabled = false;
        isGeneratingBook = false;
        return;
    }

    const childCharacter =
        storyData.child_character ||
        storyData.story_characters.find((character) => character.is_child) ||
        storyData.story_characters[0];
    const castDescription = storyData.story_characters
        .map((character) => `${character.name}: ${character.description}`)
        .join("; ");

    const payload = {
        child_name: storyData.child_name,
        character_name: childCharacter?.name || storyData.selected_character_name || "Child Hero",
        character_description: castDescription,
        plot_choice: storyData.selected_plot,
        learning_objective: storyData.learning_objective,
        theme: storyData.story_theme,
        personality_keywords: storyData.personality_keywords,
        character_image_b64: childCharacter?.image_b64 || storyData.generated_character_image_b64,
        story_characters: storyData.story_characters.map((character) => ({
            name: character.name,
            description: character.description,
            is_child: !!character.is_child,
            image_b64: character.image_b64,
            mime_type: character.mime_type || "image/png",
        })),
        ...getRequestContext(),
    };

    try {
        setBookLoadingStage(0, "Generating story text...", "Creating your personalized story draft.");
        const responseData = await postApi("/book/generate", payload);

        if (Array.isArray(responseData.pages) && responseData.pages.length > 0) {
            setBookLoadingStage(3, "Finalizing your book...", "Almost done. Preparing your pages.");
            storyData.bookPages = responseData.pages;
            storyData.currentPageIndex = 0;
            if (downloadPdfButton) {
                downloadPdfButton.disabled = false;
            }
            hideLoadingOverlay();
            goToStep(6);
        } else {
            throw new Error("Received invalid book data from server.");
        }
    } catch (error) {
        hideLoadingOverlay();
        showError(5, `Failed to generate book: ${error.message}`);
        generateBookButton.disabled = false;
        document.getElementById("btn-step-5-back").disabled = false;
        isGeneratingBook = false;
    }
}

async function downloadBookPdf() {
    clearError(6);

    if (!Array.isArray(storyData.bookPages) || storyData.bookPages.length === 0) {
        showError(6, "No generated book pages available to export.");
        return;
    }
    if (isDownloadingPdf) {
        return;
    }

    isDownloadingPdf = true;
    const originalButtonText = downloadPdfButton ? downloadPdfButton.textContent : "";
    if (downloadPdfButton) {
        downloadPdfButton.disabled = true;
        downloadPdfButton.textContent = "Preparing PDF...";
    }

    try {
        const response = await fetch(`${API_BASE_URL}/book/pdf`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/pdf",
            },
            body: JSON.stringify({
                child_name: storyData.child_name,
                pages: storyData.bookPages,
            }),
        });

        if (!response.ok) {
            let message = `Failed to generate PDF (${response.status}).`;
            try {
                const errorJson = await response.json();
                if (errorJson && errorJson.error) {
                    message = errorJson.error;
                }
            } catch (parseError) {
                // Keep default message if body is not JSON.
            }
            throw new Error(message);
        }

        const pdfBlob = await response.blob();
        const fileName = buildPdfFilename(storyData.child_name);
        const url = window.URL.createObjectURL(pdfBlob);
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        showError(6, `Could not download PDF: ${error.message}`);
    } finally {
        isDownloadingPdf = false;
        if (downloadPdfButton) {
            downloadPdfButton.disabled = !(Array.isArray(storyData.bookPages) && storyData.bookPages.length > 0);
            downloadPdfButton.textContent = originalButtonText || "Download PDF";
        }
    }
}

function displayCurrentPage() {
    clearError(6);

    if (!storyData.bookPages || storyData.bookPages.length === 0) {
        showError(6, "No book pages available to display.");
        if (downloadPdfButton) {
            downloadPdfButton.disabled = true;
        }
        if (bookView) {
            bookView.style.display = "none";
        }
        return;
    }

    if (downloadPdfButton && !isDownloadingPdf) {
        downloadPdfButton.disabled = false;
    }

    if (bookView) {
        bookView.style.display = "block";
    }

    const pageIndex = storyData.currentPageIndex;
    const totalPages = storyData.bookPages.length;
    const pageData = storyData.bookPages[pageIndex];

    if (!pageData) {
        showError(6, `Invalid page index: ${pageIndex}`);
        return;
    }

    if (bookText) {
        bookText.textContent = pageData.text || "This page has no text.";
    }

    bookImage.style.display = "none";
    bookImageSpinner.style.display = "flex";
    bookImage.onerror = null;
    bookImage.onload = null;

    if (pageData.b64_json) {
        const mimeType = pageData.mime_type || "image/png";
        const dataUrl = `data:${mimeType};base64,${pageData.b64_json}`;
        bookImage.src = dataUrl;
        bookImage.alt = `Illustration for page ${pageIndex + 1}`;

        bookImage.onload = () => {
            bookImage.style.display = "block";
            bookImageSpinner.style.display = "none";
        };

        bookImage.onerror = () => {
            bookImageSpinner.style.display = "none";
            showError(6, `Could not load image for page ${pageIndex + 1}.`);
        };

        if (bookImage.complete && bookImage.naturalWidth > 0) {
            bookImage.onload();
        }
    } else {
        bookImageSpinner.style.display = "none";
        showError(6, `No image available for page ${pageIndex + 1}.`);
    }

    if (bookPageIndicator) {
        bookPageIndicator.textContent = `Page ${pageIndex + 1} of ${totalPages}`;
    }
    if (bookPrevButton) {
        bookPrevButton.disabled = pageIndex === 0;
    }
    if (bookNextButton) {
        bookNextButton.disabled = pageIndex >= totalPages - 1;
    }
    if (displayChildNameBook) {
        displayChildNameBook.textContent = storyData.child_name;
    }
}

function changePage(delta) {
    const newIndex = storyData.currentPageIndex + delta;
    if (newIndex >= 0 && newIndex < storyData.bookPages.length) {
        storyData.currentPageIndex = newIndex;
        displayCurrentPage();
    }
}

function startOver() {
    const preservedSettings = { ...storyData.aiSettings };

    storyData.child_profile_input = "";
    storyData.extracted_profile_source = "";
    storyData.child_name = "";
    storyData.learning_objective = "";
    storyData.personality_keywords = [];
    storyData.story_theme = "";
    storyData.story_theme_suggestions = [];
    storyData.character_suggestions = [];
    storyData.selected_character_descriptions = [];
    storyData.selected_character_description = "";
    storyData.child_character = null;
    storyData.story_characters = [];
    storyData.storyCastState = "idle";
    storyData.storyCastError = null;
    storyData.storyCastSourceKey = "";
    storyData.characterReferencesState = "idle";
    storyData.characterReferencesError = null;
    storyData.name_suggestions = [];
    storyData.selected_character_name = "";
    storyData.plot_suggestions = [];
    storyData.selected_plot = "";
    storyData.main_story_characters = [];
    storyData.mainStoryCharactersState = "idle";
    storyData.mainStoryCharactersError = null;
    storyData.mainStoryCharactersSourceKey = "";
    storyData.bookPages = [];
    storyData.currentPageIndex = 0;

    resetCharacterPreviewState();

    document.getElementById("form-basics").reset();
    childProfileInput.value = "";
    updateProfileExtractionSummary();

    ["theme", "character", "name", "plot"].forEach((type) => {
        const suggestionsContainer = document.getElementById(`${type}-suggestions`);
        const selectedTextElement = document.getElementById(`selected-${type}-text`);
        if (type === "name") {
            if (storyCastStatus) {
                storyCastStatus.textContent = "";
            }
            if (storyCastList) {
                storyCastList.innerHTML = "";
            }
        } else if (suggestionsContainer) {
            suggestionsContainer.innerHTML = "";
        }
        if (selectedTextElement) {
            selectedTextElement.textContent = "None";
        }
    });

    document
        .getElementById("review-details")
        .querySelectorAll("span")
        .forEach((span) => {
            span.textContent = "";
        });
    if (reviewMainCharacters) {
        reviewMainCharacters.innerHTML = "";
    }
    if (reviewMainCharactersStatus) {
        reviewMainCharactersStatus.textContent = "";
    }
    if (storyCastList) {
        storyCastList.innerHTML = "";
    }
    if (storyCastStatus) {
        storyCastStatus.textContent = "";
    }

    hideLoadingOverlay();
    generateBookButton.disabled = true;
    document.getElementById("btn-step-5-back").disabled = false;

    characterImageStatus.textContent = "Character preview will generate after cast setup.";
    characterImageStatus.style.display = "block";
    characterImagePreview.src = "";
    characterImagePreview.style.display = "none";

    if (bookView) {
        bookView.style.display = "none";
    }
    if (bookText) {
        bookText.textContent = "";
    }
    if (bookImage) {
        bookImage.src = "";
        bookImage.style.display = "none";
    }
    if (bookImageSpinner) {
        bookImageSpinner.style.display = "none";
    }
    if (bookPageIndicator) {
        bookPageIndicator.textContent = "";
    }
    if (bookPrevButton) {
        bookPrevButton.disabled = true;
    }
    if (bookNextButton) {
        bookNextButton.disabled = true;
    }
    if (downloadPdfButton) {
        downloadPdfButton.disabled = true;
        downloadPdfButton.textContent = "Download PDF";
    }

    clearAllErrors();
    Object.values(nextButtons).forEach((button) => {
        if (button) {
            button.disabled = true;
        }
    });

    storyData.aiSettings = preservedSettings;
    providerSelect.value = preservedSettings.provider || settingsOptions.default_provider || "gemini";
    renderProviderSettings(providerSelect.value, preservedSettings);

    isGeneratingBook = false;
    isDownloadingPdf = false;
    goToStep(1);
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        if (healthResponse.ok) {
            const healthData = await healthResponse.json();
            console.log("API health:", healthData);
        }
    } catch (error) {
        console.warn("API health check warning:", error);
    }

    await loadSettingsOptions();
    startOver();
});
